"""Unit tests for ClipCrop tools and schemas.

Verifies:
- 100% parameter equivalence between Pydantic V2 models and strict JSON Schema constants
- Functional execution and defensive sandboxing across all tools
- Tool 7 CMX 3600 EDL serialization with valid HH:MM:SS:FF timecode format
- Candidate scoring determinism and silence-over-guessing compliance
- Confidence gate deterministic cutoff
"""

from __future__ import annotations

from pathlib import Path
import re
import pytest
from pydantic import ValidationError

from src.config import RuntimeConfig
from src.state.schema import SpeechSpan, TranscriptSegment
from src.tools import (
    confidence_gate_decision,
    decode_and_validate_source,
    export_crop_path_data,
    score_candidate_segments,
    smooth_crop_path,
)
from src.tools.export_crop_path_data import _ms_to_timecode, _serialize_to_edl
from src.tools.schemas import (
    CANDIDATE_SEGMENT_SCORE_SCHEMA,
    CONFIDENCE_GATE_DECISION_SCHEMA,
    DECODE_AND_VALIDATE_SOURCE_SCHEMA,
    DETECT_SPEECH_PAUSES_SCHEMA,
    EXPORT_CROP_PATH_DATA_SCHEMA,
    RENDER_VERTICAL_CLIP_SCHEMA,
    SMOOTH_CROP_PATH_SCHEMA,
    TRACK_SPEAKER_POSITION_SCHEMA,
    TRANSCRIBE_AUDIO_SCHEMA,
    BoundingBoxModel,
    CandidateSegmentScore,
    ConfidenceGateDecision,
    CropKeyframeModel,
    DecodeAndValidateSourceInput,
    DetectSpeechPausesInput,
    ExportCropPathDataInput,
    FramePositionModel,
    RenderVerticalClipInput,
    SmoothCropPathInput,
    TrackSpeakerPositionInput,
    TranscribeAudioInput,
)


@pytest.fixture
def mock_config() -> RuntimeConfig:
    """Fixture providing a valid RuntimeConfig instance."""
    from src.config import load_config_from_env
    return load_config_from_env()


# ---------------------------------------------------------------------------
# 1. Pydantic V2 vs JSON Schema Parameter Diff Tests (All 7 Tools)
# ---------------------------------------------------------------------------


def test_schema_parameter_parity_for_all_tools() -> None:
    """Assert Pydantic V2 models and JSON Schema constants have identical parameter sets."""
    tools = [
        (DecodeAndValidateSourceInput, DECODE_AND_VALIDATE_SOURCE_SCHEMA),
        (TranscribeAudioInput, TRANSCRIBE_AUDIO_SCHEMA),
        (DetectSpeechPausesInput, DETECT_SPEECH_PAUSES_SCHEMA),
        (TrackSpeakerPositionInput, TRACK_SPEAKER_POSITION_SCHEMA),
        (SmoothCropPathInput, SMOOTH_CROP_PATH_SCHEMA),
        (RenderVerticalClipInput, RENDER_VERTICAL_CLIP_SCHEMA),
        (ExportCropPathDataInput, EXPORT_CROP_PATH_DATA_SCHEMA),
    ]

    for model_cls, json_schema in tools:
        model_fields = set(model_cls.model_fields.keys())
        schema_props = set(json_schema["parameters"]["properties"].keys())
        diff = model_fields.symmetric_difference(schema_props)
        assert not diff, (
            f"Schema diff mismatch for {json_schema['name']}: "
            f"Model has {model_fields}, Schema has {schema_props}. Diff: {diff}"
        )


def test_structured_output_schema_parameter_parity() -> None:
    """Assert internal structured output schemas match Pydantic models."""
    # CandidateSegmentScore
    cand_model_fields = set(CandidateSegmentScore.model_fields.keys())
    cand_schema_props = set(CANDIDATE_SEGMENT_SCORE_SCHEMA["schema"]["properties"].keys())
    assert cand_model_fields == cand_schema_props

    # ConfidenceGateDecision
    gate_model_fields = set(ConfidenceGateDecision.model_fields.keys())
    gate_schema_props = set(CONFIDENCE_GATE_DECISION_SCHEMA["schema"]["properties"].keys())
    assert gate_model_fields == gate_schema_props


# ---------------------------------------------------------------------------
# 2. Tool 1: decode_and_validate_source Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decode_and_validate_source_on_fixture(mock_config: RuntimeConfig) -> None:
    """Assert decode_and_validate_source succeeds on simple_case fixture."""
    fixture_path = "tests/fixtures/simple_case.mp4"
    assert Path(fixture_path).exists(), "simple_case.mp4 fixture must exist"

    inp = DecodeAndValidateSourceInput(source_path=fixture_path)
    out = await decode_and_validate_source(inp, mock_config)

    assert out.success is True
    assert out.has_video_track is True
    assert out.has_audio_track is True
    assert out.width == 1280
    assert out.height == 720
    assert out.duration_seconds is not None and out.duration_seconds > 0


@pytest.mark.asyncio
async def test_decode_and_validate_source_rejects_path_traversal(mock_config: RuntimeConfig) -> None:
    """Assert path traversal sequences are rejected unconditionally."""
    with pytest.raises(ValidationError, match="path-traversal"):
        DecodeAndValidateSourceInput(source_path="uploads/../secret.mp4")


# ---------------------------------------------------------------------------
# 3. Tool 5: smooth_crop_path Tests
# ---------------------------------------------------------------------------


def test_smooth_crop_path_reduces_jitter_and_preserves_bounds() -> None:
    """Assert smooth_crop_path generates valid keyframes with reduced coordinate jitter."""
    # Create raw positions with simulated jitter (e.g. oscillating between 300 and 340)
    raw_positions = [
        FramePositionModel(
            timestamp_ms=i * 100,
            bounding_box=BoundingBoxModel(
                origin_x=300 if i % 2 == 0 else 340,
                origin_y=100,
                width=200,
                height=200,
            ),
            detection_score=0.9,
        )
        for i in range(10)
    ]

    inp = SmoothCropPathInput(
        segment_id="seg_01",
        raw_positions=raw_positions,
        smoothing_method="ema",
        smoothing_strength=0.5,
        source_width=1280,
        source_height=720,
    )
    out = smooth_crop_path(inp)

    assert out.success is True
    assert out.crop_keyframes is not None
    assert len(out.crop_keyframes) == 10

    # Assert 9:16 dimensions
    kf0 = out.crop_keyframes[0]
    assert kf0.height == 720
    assert kf0.width == int(round(720 * 9 / 16))

    # Assert frame-to-frame delta is reduced compared to raw 40px jitter
    deltas = [
        abs(out.crop_keyframes[i].x - out.crop_keyframes[i - 1].x)
        for i in range(1, len(out.crop_keyframes))
    ]
    max_delta = max(deltas)
    assert max_delta < 40  # Jitter was smoothed


# ---------------------------------------------------------------------------
# 4. Tool 6: render_vertical_clip Sandbox Defense Tests
# ---------------------------------------------------------------------------


def test_render_vertical_clip_rejects_source_overwrite() -> None:
    """Assert render_vertical_clip rejects output_path equal to source_video_path."""
    kf = [CropKeyframeModel(timestamp_ms=0, x=100, y=0, width=405, height=720)]

    # 1. Direct sandbox validation check
    from src.tools.render_vertical_clip import _validate_output_sandbox
    with pytest.raises(ValueError, match="must not equal or overwrite source_video_path"):
        _validate_output_sandbox("uploads/video.mp4", "uploads/video.mp4", Path("outputs"))

    # 2. Pydantic model validator check on instantiation
    with pytest.raises(ValidationError, match="output_path cannot overwrite source video"):
        RenderVerticalClipInput(
            segment_id="seg_01",
            source_video_path="uploads/video.mp4",
            segment_start_ms=0,
            segment_end_ms=5000,
            crop_keyframes=kf,
            output_width=1080,
            output_height=1920,
            output_path="uploads/video.mp4",  # Collision!
            video_codec="libx264",
            crf=20,
            preset="fast",
        )


# ---------------------------------------------------------------------------
# 5. Tool 7: export_crop_path_data & CMX 3600 Timecode Tests
# ---------------------------------------------------------------------------


def test_cmx3600_timecode_serialization_format() -> None:
    """Assert timecode converter produces exact HH:MM:SS:FF strings."""
    assert _ms_to_timecode(0, fps=30) == "00:00:00:00"
    assert _ms_to_timecode(1000, fps=30) == "00:00:01:00"
    assert _ms_to_timecode(61000, fps=30) == "00:01:01:00"
    assert _ms_to_timecode(3661000, fps=30) == "01:01:01:00"
    # Fractional frames: 33ms at 30fps is frame 1
    tc = _ms_to_timecode(33, fps=30)
    assert re.match(r"^\d{2}:\d{2}:\d{2}:\d{2}$", tc)


def test_export_crop_path_data_edl_output(tmp_path: Path, mock_config: RuntimeConfig) -> None:
    """Assert Tool 7 serializes CMX 3600 EDL file with valid format and markers."""
    keyframes = [
        CropKeyframeModel(timestamp_ms=0, x=200, y=0, width=405, height=720),
        CropKeyframeModel(timestamp_ms=1000, x=205, y=0, width=405, height=720),
    ]
    out_file = tmp_path / "test_clip.edl"

    test_config = RuntimeConfig(
        upload_dir=mock_config.upload_dir,
        output_dir=tmp_path,
        models_dir=mock_config.models_dir,
        ffmpeg_path=mock_config.ffmpeg_path,
        ffprobe_path=mock_config.ffprobe_path,
        confidence_threshold=mock_config.confidence_threshold,
        max_candidates=mock_config.max_candidates,
        time_budget_seconds=mock_config.time_budget_seconds,
        trace_log_dir=mock_config.trace_log_dir,
    )

    inp = ExportCropPathDataInput(
        segment_id="seg_01",
        crop_keyframes=keyframes,
        output_path=str(out_file),
        format="edl",
    )
    res = export_crop_path_data(inp, config=test_config)

    assert res.success is True
    assert res.keyframe_count == 2
    assert out_file.exists()

    content = out_file.read_text(encoding="utf-8")
    assert "TITLE: CLIPCROP_EXPORT" in content
    assert "FCM: NON-DROP FRAME" in content
    assert "001  AX       V     C" in content
    assert "CROP_X=200" in content
    assert "CROP_X=205" in content


# ---------------------------------------------------------------------------
# 6. Candidate Scorer Determinism & Silence-Over-Guessing Tests
# ---------------------------------------------------------------------------


def test_candidate_scorer_silence_over_guessing(mock_config: RuntimeConfig) -> None:
    """Assert candidate scorer returns empty list when speech is absent."""
    res = score_candidate_segments([], [], mock_config)
    assert res == []


def test_candidate_scorer_ranks_and_caps_at_max(mock_config: RuntimeConfig) -> None:
    """Assert candidate scorer produces deterministic ranks and enforces candidate cap."""
    t_segs = [
        TranscriptSegment(start_ms=i * 5000, end_ms=(i + 1) * 5000, text=f"Segment {i} why this is important.")
        for i in range(15)
    ]
    vad_segs = [
        SpeechSpan(start_seconds=i * 5.0, end_seconds=(i + 1) * 5.0)
        for i in range(15)
    ]

    res = score_candidate_segments(t_segs, vad_segs, mock_config)
    assert len(res) <= mock_config.max_candidates
    assert len(res) > 0
    # Scores must be in descending order
    scores = [c.score for c in res]
    assert scores == sorted(scores, reverse=True)
    # Ranks must be 1..N
    assert [c.rank for c in res] == list(range(1, len(res) + 1))


# ---------------------------------------------------------------------------
# 7. Confidence Gate Decision Tests
# ---------------------------------------------------------------------------


def test_confidence_gate_decision_cutoff(mock_config: RuntimeConfig) -> None:
    """Assert confidence gate enforces >= cutoff strictly in code."""
    threshold = mock_config.confidence_threshold  # 0.65

    render_dec = confidence_gate_decision("seg_01", threshold, mock_config)
    assert render_dec.decision == "render"
    assert render_dec.tracking_confidence == threshold

    skip_dec = confidence_gate_decision("seg_02", threshold - 0.01, mock_config)
    assert skip_dec.decision == "skip"
    assert "below" in skip_dec.reason


# ---------------------------------------------------------------------------
# 8. Functional Tool Execution Tests Against Simple Case Fixture
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transcribe_audio_execution(mock_config: RuntimeConfig) -> None:
    """Assert transcribe_audio runs in-process with faster-whisper on simple_case."""
    from src.tools.transcribe_audio import transcribe_audio

    inp = TranscribeAudioInput(
        audio_source_path="tests/fixtures/simple_case.mp4",
        model_tier="base.en",
        language="en",
    )
    out = await transcribe_audio(inp, mock_config)
    assert out.success is True
    assert out.segments is not None
    assert out.language_detected == "en"


@pytest.mark.asyncio
async def test_detect_speech_pauses_execution(mock_config: RuntimeConfig) -> None:
    """Assert detect_speech_pauses runs Silero VAD on simple_case."""
    from src.tools.detect_speech_pauses import detect_speech_pauses

    inp = DetectSpeechPausesInput(
        audio_source_path="tests/fixtures/simple_case.mp4",
        sampling_rate=16000,
        threshold=0.5,
        min_speech_duration_ms=250,
        min_silence_duration_ms=300,
        speech_pad_ms=30,
    )
    out = await detect_speech_pauses(inp, mock_config)
    assert out.success is True
    assert out.speech_spans is not None
    assert out.sampling_rate_used == 16000


@pytest.mark.asyncio
async def test_track_speaker_position_execution(mock_config: RuntimeConfig) -> None:
    """Assert track_speaker_position tracks bounding boxes on simple_case."""
    from src.tools.track_speaker_position import track_speaker_position

    inp = TrackSpeakerPositionInput(
        segment_id="seg_01",
        video_path="tests/fixtures/simple_case.mp4",
        segment_start_ms=0,
        segment_end_ms=2000,
        model_asset_path=str(mock_config.models_dir / "blaze_face_short_range.task"),
        frame_sample_stride=2,
        min_detection_confidence=0.5,
    )
    out = await track_speaker_position(inp, mock_config)
    assert out.success is True
    assert out.per_frame_positions is not None
    assert len(out.per_frame_positions) > 0
    assert out.segment_confidence is not None


@pytest.mark.asyncio
async def test_render_vertical_clip_execution(tmp_path: Path, mock_config: RuntimeConfig) -> None:
    """Assert render_vertical_clip executes ffmpeg render of 9:16 vertical clip."""
    from src.tools.render_vertical_clip import render_vertical_clip

    out_file = tmp_path / "clip_seg01.mp4"
    test_config = RuntimeConfig(
        upload_dir=mock_config.upload_dir,
        output_dir=tmp_path,
        models_dir=mock_config.models_dir,
        ffmpeg_path=mock_config.ffmpeg_path,
        ffprobe_path=mock_config.ffprobe_path,
        confidence_threshold=mock_config.confidence_threshold,
        max_candidates=mock_config.max_candidates,
        time_budget_seconds=mock_config.time_budget_seconds,
        trace_log_dir=mock_config.trace_log_dir,
    )

    kf = [
        CropKeyframeModel(timestamp_ms=0, x=300, y=0, width=405, height=720),
        CropKeyframeModel(timestamp_ms=1000, x=300, y=0, width=405, height=720),
    ]

    inp = RenderVerticalClipInput(
        segment_id="seg_01",
        source_video_path="tests/fixtures/simple_case.mp4",
        segment_start_ms=0,
        segment_end_ms=2000,
        crop_keyframes=kf,
        output_width=1080,
        output_height=1920,
        output_path=str(out_file),
        video_codec="libx264",
        crf=20,
        preset="fast",
    )
    out = await render_vertical_clip(inp, test_config)
    assert out.success is True
    assert out.output_file_path is not None
    assert out_file.exists()
    assert out_file.stat().st_size > 0
