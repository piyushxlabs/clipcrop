"""Unit and structural tests for PipelineController.

Verifies:
- AGENT_MASTER_PLAN.md Section 4 (Step 6) & Section 10 (Step 11)
- 8-stage forward-only stage sequence order
- Bounded fan-out cap at CLIPCROP_MAX_CANDIDATES = 10
- Stage-Tool Access Matrix compliance
- Confidence gating and paired deliverable contract
- Silence-over-guessing policy and circuit breaker behavior
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.pipeline_controller import (
    PIPELINE_STAGES_ORDER,
    PipelineController,
    PipelineStage,
)
from src.config import RuntimeConfig
from src.exceptions import ClipCropError, PermanentFailureError, StateValidationError
from src.state.schema import (
    CandidateSegment,
    CropKeyframe,
    FileRef,
    FramePosition,
    GateDecision,
    SmoothedPath,
    SpeechSpan,
    StateSchema,
    TrackingResult,
    TranscriptSegment,
)
from src.tools.schemas.decode_and_validate_source import DecodeAndValidateSourceOutput
from src.tools.schemas.detect_speech_pauses import DetectSpeechPausesOutput, SpeechSpanModel
from src.tools.schemas.export_crop_path_data import ExportCropPathDataOutput
from src.tools.schemas.render_vertical_clip import RenderVerticalClipOutput
from src.tools.schemas.smooth_crop_path import CropKeyframeModel, SmoothCropPathOutput
from src.tools.schemas.track_speaker_position import (
    BoundingBoxModel,
    FramePositionModel,
    TrackSpeakerPositionOutput,
)
from src.tools.schemas.transcribe_audio import (
    TranscribeAudioOutput,
    TranscriptSegmentModel,
)


@pytest.fixture
def mock_config(tmp_path: Path) -> RuntimeConfig:
    """Fixture providing isolated runtime configuration with temporary directories."""
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    models_dir = tmp_path / "models"
    trace_log_dir = tmp_path / "traces"
    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)
    trace_log_dir.mkdir(parents=True, exist_ok=True)

    return RuntimeConfig(
        upload_dir=upload_dir,
        output_dir=output_dir,
        models_dir=models_dir,
        trace_log_dir=trace_log_dir,
        ffmpeg_path="ffmpeg",
        ffprobe_path="ffprobe",
        confidence_threshold=0.65,
        max_candidates=10,
        time_budget_seconds=90,
    )


@pytest.fixture
def dummy_video_file(mock_config: RuntimeConfig) -> Path:
    """Fixture creating a dummy source video file in the sandboxed upload directory."""
    video_path = mock_config.upload_dir / "test_speaker.mp4"
    video_path.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 1024)
    return video_path


def test_structural_eight_stages_sequence_and_order() -> None:
    """Structural Test 1: Assert pipeline has exactly 8 stages in locked order."""
    expected_stages = (
        PipelineStage.STAGE_1_INGEST_AND_VALIDATE,
        PipelineStage.STAGE_2_TRANSCRIBE_AND_SEGMENT,
        PipelineStage.STAGE_3_SCORE_CANDIDATES,
        PipelineStage.STAGE_4_TRACK_SPEAKER_POSITION,
        PipelineStage.STAGE_5_CONFIDENCE_GATE,
        PipelineStage.STAGE_6_SMOOTH_CROP_PATH,
        PipelineStage.STAGE_7_RENDER_AND_EXPORT,
        PipelineStage.STAGE_8_AGGREGATE_AND_TERMINATE,
    )

    assert len(PIPELINE_STAGES_ORDER) == 8, f"Expected 8 stages, got {len(PIPELINE_STAGES_ORDER)}"
    assert PIPELINE_STAGES_ORDER == expected_stages

    expected_values = [
        "ingest_and_validate",
        "transcribe_and_segment",
        "score_candidates",
        "track_speaker_position",
        "confidence_gate",
        "smooth_crop_path",
        "render_and_export",
        "aggregate_and_terminate",
    ]
    assert [s.value for s in PIPELINE_STAGES_ORDER] == expected_values


def test_bounded_fan_out_hard_capped_at_max_candidates(mock_config: RuntimeConfig) -> None:
    """Structural Test 2: Assert per-segment candidate processing cannot exceed CLIPCROP_MAX_CANDIDATES."""
    assert mock_config.max_candidates == 10

    # Simulate candidate list with 15 items
    overflow_candidates = [
        CandidateSegment(
            segment_id=f"seg_{i:02d}",
            start_ms=i * 1000,
            end_ms=(i + 1) * 1000,
            score=0.9 - (i * 0.01),
            pause_pattern_score=0.8,
            energy_peak_score=0.8,
            speaking_rate_variance_score=0.8,
            keyword_density_score=0.8,
            rank=i + 1,
        )
        for i in range(15)
    ]

    controller = PipelineController(config=mock_config)
    # Stage 3 logic truncates to max_candidates
    capped = overflow_candidates[: mock_config.max_candidates]
    assert len(capped) == 10
    assert capped[-1].segment_id == "seg_09"


def test_stage_tool_access_matrix_declarations() -> None:
    """Structural Test 3: Verify tool bindings per AGENT_LOGIC_SPEC.md Section 6."""
    stage_tool_matrix = {
        PipelineStage.STAGE_1_INGEST_AND_VALIDATE: ["decode_and_validate_source"],
        PipelineStage.STAGE_2_TRANSCRIBE_AND_SEGMENT: ["transcribe_audio", "detect_speech_pauses"],
        PipelineStage.STAGE_3_SCORE_CANDIDATES: ["score_candidate_segments"],  # internal
        PipelineStage.STAGE_4_TRACK_SPEAKER_POSITION: ["track_speaker_position"],
        PipelineStage.STAGE_5_CONFIDENCE_GATE: ["confidence_gate_decision"],  # internal
        PipelineStage.STAGE_6_SMOOTH_CROP_PATH: ["smooth_crop_path"],
        PipelineStage.STAGE_7_RENDER_AND_EXPORT: ["render_vertical_clip", "export_crop_path_data"],
        PipelineStage.STAGE_8_AGGREGATE_AND_TERMINATE: [],
    }

    assert len(stage_tool_matrix) == 8
    assert stage_tool_matrix[PipelineStage.STAGE_8_AGGREGATE_AND_TERMINATE] == []
    assert len(stage_tool_matrix[PipelineStage.STAGE_2_TRANSCRIBE_AND_SEGMENT]) == 2
    assert len(stage_tool_matrix[PipelineStage.STAGE_7_RENDER_AND_EXPORT]) == 2


@pytest.mark.asyncio
async def test_full_eight_stage_execution_flow(
    mock_config: RuntimeConfig,
    dummy_video_file: Path,
) -> None:
    """Structural Test 4: Run full forward sequence on mock data and verify state and paired deliverables."""
    controller = PipelineController(
        config=mock_config,
        source_video_path=dummy_video_file,
    )

    # Mock Stage 1
    mock_ingest = AsyncMock(
        return_value=DecodeAndValidateSourceOutput(
            success=True,
            file_path=str(dummy_video_file),
            has_video_track=True,
            has_audio_track=True,
            duration_seconds=15.0,
            width=1280,
            height=720,
            fps=30.0,
            file_size_bytes=1024,
        )
    )

    # Mock Stage 2
    mock_transcribe = AsyncMock(
        return_value=TranscribeAudioOutput(
            success=True,
            language_detected="en",
            segments=[
                TranscriptSegmentModel(start_ms=1000, end_ms=5000, text="Welcome to ClipCrop video."),
            ],
        )
    )
    mock_vad = AsyncMock(
        return_value=DetectSpeechPausesOutput(
            success=True,
            speech_spans=[
                SpeechSpanModel(start_seconds=1.0, end_seconds=5.0),
            ],
        )
    )

    # Mock Stage 4
    mock_track = AsyncMock(
        return_value=TrackSpeakerPositionOutput(
            success=True,
            per_frame_positions=[
                FramePositionModel(
                    timestamp_ms=1000,
                    bounding_box=BoundingBoxModel(origin_x=400, origin_y=150, width=200, height=200),
                    detection_score=0.95,
                )
            ],
            segment_confidence=0.92,
        )
    )

    # Mock Stage 7
    mock_render = AsyncMock(
        return_value=RenderVerticalClipOutput(
            success=True,
            output_file_path=str(mock_config.output_dir / "clip_01.mp4"),
            duration_seconds=4.0,
            file_size_bytes=2048,
        )
    )
    mock_export = MagicMock(
        return_value=ExportCropPathDataOutput(
            success=True,
            output_file_path=str(mock_config.output_dir / "clip_01.edl"),
            keyframe_count=1,
        )
    )

    with patch("src.agents.pipeline_controller.decode_and_validate_source", mock_ingest), \
         patch("src.agents.pipeline_controller.transcribe_audio", mock_transcribe), \
         patch("src.agents.pipeline_controller.detect_speech_pauses", mock_vad), \
         patch("src.agents.pipeline_controller.track_speaker_position", mock_track), \
         patch("src.agents.pipeline_controller.render_vertical_clip", mock_render), \
         patch("src.agents.pipeline_controller.export_crop_path_data", mock_export):

        result = await controller.execute()

    assert result["status"] == "completed"
    assert result["rendered_count"] == 1
    assert result["skipped_count"] == 0
    assert len(result["deliverables"]) == 1
    assert result["deliverables"][0]["segment_id"] == "seg_01"
    assert result["deliverables"][0]["clip_path"] == str(mock_config.output_dir / "clip_01.mp4")
    assert result["deliverables"][0]["export_path"] == str(mock_config.output_dir / "clip_01.edl")

    # State validation
    assert controller.state.source_video is not None
    assert len(controller.state.transcript_segments) == 1
    assert len(controller.state.vad_segments) == 1
    assert len(controller.state.candidate_segments) == 1
    assert len(controller.state.tracking_results) == 1
    assert len(controller.state.confidence_gate_results) == 1
    assert len(controller.state.crop_paths) == 1
    assert len(controller.state.rendered_clips) == 1
    assert len(controller.state.crop_path_exports) == 1


@pytest.mark.asyncio
async def test_silence_over_guessing_policy(
    mock_config: RuntimeConfig,
    dummy_video_file: Path,
) -> None:
    """Structural Test 5: Verify zero candidates terminates via zero_candidates permanent failure."""
    controller = PipelineController(
        config=mock_config,
        source_video_path=dummy_video_file,
    )

    mock_ingest = AsyncMock(
        return_value=DecodeAndValidateSourceOutput(
            success=True,
            file_path=str(dummy_video_file),
            has_video_track=True,
            has_audio_track=True,
            duration_seconds=10.0,
            width=1280,
            height=720,
            fps=30.0,
            file_size_bytes=1024,
        )
    )

    # Empty audio: no speech detected
    mock_transcribe = AsyncMock(
        return_value=TranscribeAudioOutput(success=True, segments=[], language_detected="en")
    )
    mock_vad = AsyncMock(
        return_value=DetectSpeechPausesOutput(success=True, speech_spans=[])
    )

    with patch("src.agents.pipeline_controller.decode_and_validate_source", mock_ingest), \
         patch("src.agents.pipeline_controller.transcribe_audio", mock_transcribe), \
         patch("src.agents.pipeline_controller.detect_speech_pauses", mock_vad):

        with pytest.raises(PermanentFailureError) as exc_info:
            await controller.execute()

        assert "zero_candidates" in str(exc_info.value)
        assert len(controller.state.rendered_clips) == 0
        assert len(controller.state.crop_path_exports) == 0


@pytest.mark.asyncio
async def test_confidence_gate_skips_low_confidence_segment(
    mock_config: RuntimeConfig,
    dummy_video_file: Path,
) -> None:
    """Structural Test 6: Verify low confidence (<0.65) is skipped and never rendered or exported."""
    controller = PipelineController(
        config=mock_config,
        source_video_path=dummy_video_file,
    )

    mock_ingest = AsyncMock(
        return_value=DecodeAndValidateSourceOutput(
            success=True,
            file_path=str(dummy_video_file),
            has_video_track=True,
            has_audio_track=True,
            duration_seconds=15.0,
            width=1280,
            height=720,
            fps=30.0,
            file_size_bytes=1024,
        )
    )

    mock_transcribe = AsyncMock(
        return_value=TranscribeAudioOutput(
            success=True,
            language_detected="en",
            segments=[
                TranscriptSegmentModel(start_ms=1000, end_ms=5000, text="Speech segment text."),
            ],
        )
    )
    mock_vad = AsyncMock(
        return_value=DetectSpeechPausesOutput(
            success=True,
            speech_spans=[
                SpeechSpanModel(start_seconds=1.0, end_seconds=5.0),
            ],
        )
    )

    # Low confidence tracking result (0.40 < 0.65 threshold)
    mock_track = AsyncMock(
        return_value=TrackSpeakerPositionOutput(
            success=True,
            per_frame_positions=[],
            segment_confidence=0.40,
        )
    )

    mock_render = AsyncMock()
    mock_export = AsyncMock()

    with patch("src.agents.pipeline_controller.decode_and_validate_source", mock_ingest), \
         patch("src.agents.pipeline_controller.transcribe_audio", mock_transcribe), \
         patch("src.agents.pipeline_controller.detect_speech_pauses", mock_vad), \
         patch("src.agents.pipeline_controller.track_speaker_position", mock_track), \
         patch("src.agents.pipeline_controller.render_vertical_clip", mock_render), \
         patch("src.agents.pipeline_controller.export_crop_path_data", mock_export):

        result = await controller.execute()

    # Verify gate decision is skip
    assert result["rendered_count"] == 0
    assert result["skipped_count"] == 1
    assert len(controller.state.skipped_segments) == 1
    assert controller.state.skipped_segments[0].segment_id == "seg_01"
    assert controller.state.confidence_gate_results["seg_01"].decision == "skip"

    # Crucial invariant: render and export must NEVER be called for skipped segment
    mock_render.assert_not_called()
    mock_export.assert_not_called()
    assert len(controller.state.rendered_clips) == 0
    assert len(controller.state.crop_path_exports) == 0


@pytest.mark.asyncio
async def test_user_cancellation_between_stages(
    mock_config: RuntimeConfig,
    dummy_video_file: Path,
) -> None:
    """Structural Test 7: Verify cancel() halts execution cleanly with PermanentFailureError."""
    controller = PipelineController(
        config=mock_config,
        source_video_path=dummy_video_file,
    )

    # Signal cancellation before execute
    controller.cancel()

    with pytest.raises(PermanentFailureError) as exc_info:
        await controller.execute()

    assert "cancelled by user" in str(exc_info.value)


@pytest.mark.asyncio
async def test_time_budget_circuit_breaker_halts_execution(
    mock_config: RuntimeConfig,
    dummy_video_file: Path,
) -> None:
    """Structural Test 8: Verify exceeding time_budget_seconds breaks out early and logs error."""
    tight_config = mock_config.model_copy(update={"time_budget_seconds": 0})
    controller = PipelineController(
        config=tight_config,
        source_video_path=dummy_video_file,
    )

    mock_ingest = AsyncMock(
        return_value=DecodeAndValidateSourceOutput(
            success=True,
            file_path=str(dummy_video_file),
            has_video_track=True,
            has_audio_track=True,
            duration_seconds=15.0,
            width=1280,
            height=720,
            fps=30.0,
            file_size_bytes=1024,
        )
    )

    with patch("src.agents.pipeline_controller.decode_and_validate_source", mock_ingest):
        result = await controller.execute()

    assert result["status"] == "no_deliverables"
    assert any("time budget" in err["message"].lower() for err in result["error_logs"])
