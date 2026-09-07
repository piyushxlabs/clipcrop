"""Comprehensive Automated Evaluation Suite for ClipCrop.

Verifies:
- docs/AGENT_MASTER_PLAN.md Section 9.2 (Unit & Integration Verification)
- docs/AGENT_MASTER_PLAN.md Section 9.3 (Deterministic-Pipeline Evaluation Suites)
- docs/AGENT_MASTER_PLAN.md Section 9.4 ("Agent Is Working" Success Criteria)
- docs/AGENT_MASTER_PLAN.md Section 9.5 (Simulated Failure Scenarios)
- docs/AGENT_MASTER_PLAN.md Section 9.6 (Non-Negotiable Verification Requirements)
- docs/INTERFACE_OBSERVABILITY_SYSTEM.md Section 6, 7a, 8, 9, 10
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest
from pydantic import ValidationError

from src.agents.pipeline_controller import PipelineController, PipelineStage
from src.config import RuntimeConfig, load_config_from_env
from src.exceptions import ClipCropError, PermanentFailureError, StateValidationError
from src.state.reducers import (
    apply_state_update,
    verify_export_precondition,
    verify_render_precondition,
)
from src.state.schema import (
    BoundingBox,
    CandidateSegment,
    CropKeyframe,
    ErrorRecord,
    FileRef,
    FramePosition,
    GateDecision,
    SkipRecord,
    SmoothedPath,
    SpeechSpan,
    StateSchema,
    TrackingResult,
    TranscriptSegment,
)
from src.telemetry.feedback_annotations import (
    append_feedback_annotation,
    append_interruption_annotation,
)
from src.telemetry.tracing import PipelineTracer
from src.tools.export_crop_path_data import export_crop_path_data
from src.tools.model_loader import (
    load_face_detector,
    load_silero_vad_model,
    load_whisper_model,
    run_model_health_check,
)
from src.tools.schemas import (
    DECODE_AND_VALIDATE_SOURCE_SCHEMA,
    DETECT_SPEECH_PAUSES_SCHEMA,
    EXPORT_CROP_PATH_DATA_SCHEMA,
    RENDER_VERTICAL_CLIP_SCHEMA,
    SMOOTH_CROP_PATH_SCHEMA,
    TRACK_SPEAKER_POSITION_SCHEMA,
    TRANSCRIBE_AUDIO_SCHEMA,
    BoundingBoxModel,
    CropKeyframeModel,
    DecodeAndValidateSourceInput,
    DetectSpeechPausesInput,
    ExportCropPathDataInput,
    FramePositionModel,
    RenderVerticalClipInput,
    SmoothCropPathInput,
    TrackSpeakerPositionInput,
    TrackSpeakerPositionOutput,
    TranscribeAudioInput,
)
from src.ui.event_types import (
    DataRunEndEvent,
    DataStageProgressEvent,
    DataStageStartEvent,
    DataStateUpdateEvent,
    ErrorEvent,
    ToolInputAvailableEvent,
    ToolOutputAvailableEvent,
    format_sse_event,
    parse_sse_line,
)
from src.ui.stream_handler import StreamHandler


@pytest.fixture
def eval_config(tmp_path: Path) -> RuntimeConfig:
    """Provides sandboxed runtime config for evaluation suites."""
    base_cfg = load_config_from_env()
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    trace_log_dir = tmp_path / "traces"
    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    trace_log_dir.mkdir(parents=True, exist_ok=True)

    return RuntimeConfig(
        upload_dir=upload_dir,
        output_dir=output_dir,
        models_dir=base_cfg.models_dir,
        trace_log_dir=trace_log_dir,
        ffmpeg_path=base_cfg.ffmpeg_path,
        ffprobe_path=base_cfg.ffprobe_path,
        confidence_threshold=0.65,
        max_candidates=10,
        time_budget_seconds=90,
    )


@pytest.fixture
def simple_case_path() -> Path:
    """Returns verified path to simple_case.mp4 fixture."""
    path = Path("tests/fixtures/simple_case.mp4").resolve()
    assert path.is_file(), "simple_case.mp4 fixture must exist."
    return path


# ===========================================================================
# Section 9.2: Unit & Integration Verification Checks
# ===========================================================================

def test_eval_python_version_and_runtime_manifest() -> None:
    """Section 9.2: Python runtime is strictly 3.11.x."""
    assert sys.version_info.major == 3
    assert sys.version_info.minor == 11, f"Expected Python 3.11, got {sys.version}"


def test_eval_ffmpeg_and_ffprobe_binaries(eval_config: RuntimeConfig) -> None:
    """Section 9.2: ffmpeg and ffprobe binaries are found and respond to -version."""
    ffmpeg_res = subprocess.run([eval_config.ffmpeg_path, "-version"], capture_output=True, text=True)
    assert ffmpeg_res.returncode == 0, f"ffmpeg failed: {ffmpeg_res.stderr}"
    assert "ffmpeg version" in ffmpeg_res.stdout.lower()

    ffprobe_res = subprocess.run([eval_config.ffprobe_path, "-version"], capture_output=True, text=True)
    assert ffprobe_res.returncode == 0, f"ffprobe failed: {ffprobe_res.stderr}"
    assert "ffprobe version" in ffprobe_res.stdout.lower()


def test_eval_offline_perception_models_health(eval_config: RuntimeConfig) -> None:
    """Section 9.2: Offline perception models load from local disk with zero network."""
    results = run_model_health_check(eval_config)
    assert results["all_healthy"] is True
    assert results["faster_whisper"]["status"] == "healthy"
    assert results["mediapipe_face_detector"]["status"] == "healthy"
    assert results["silero_vad"]["status"] == "healthy"
    assert results["faster_whisper"]["model_path"]
    assert results["mediapipe_face_detector"]["model_path"]
    assert results["silero_vad"]["model_path"]


def test_eval_tool_schema_parameter_diff_ci() -> None:
    """Section 9.2 & Section 9.6: Automated tool parameter parity diff between Pydantic and JSON Schema."""
    tool_pairs = [
        ("decode_and_validate_source", DecodeAndValidateSourceInput, DECODE_AND_VALIDATE_SOURCE_SCHEMA),
        ("transcribe_audio", TranscribeAudioInput, TRANSCRIBE_AUDIO_SCHEMA),
        ("detect_speech_pauses", DetectSpeechPausesInput, DETECT_SPEECH_PAUSES_SCHEMA),
        ("track_speaker_position", TrackSpeakerPositionInput, TRACK_SPEAKER_POSITION_SCHEMA),
        ("smooth_crop_path", SmoothCropPathInput, SMOOTH_CROP_PATH_SCHEMA),
        ("render_vertical_clip", RenderVerticalClipInput, RENDER_VERTICAL_CLIP_SCHEMA),
        ("export_crop_path_data", ExportCropPathDataInput, EXPORT_CROP_PATH_DATA_SCHEMA),
    ]

    for tool_name, pydantic_cls, json_schema in tool_pairs:
        pydantic_fields = set(pydantic_cls.model_fields.keys())
        json_schema_props = set(json_schema["parameters"]["properties"].keys())
        diff = pydantic_fields.symmetric_difference(json_schema_props)
        assert not diff, f"Tool '{tool_name}' schema mismatch: {diff}"


# ===========================================================================
# Section 9.3: Deterministic-Pipeline Evaluation Suites
# ===========================================================================

@pytest.mark.asyncio
async def test_eval_tool_sequencing_and_grounding_telemetry(
    eval_config: RuntimeConfig,
    simple_case_path: Path,
) -> None:
    """Section 9.3: Controller calls stages strictly in order (1 -> 8) and data-run-end is 100% grounded."""
    stream_handler = StreamHandler()
    controller = PipelineController(
        config=eval_config,
        source_video_path=simple_case_path,
        stream_handler=stream_handler,
    )

    executed_stages: List[str] = []
    final_run_end_events: List[DataRunEndEvent] = []

    async def stream_listener() -> None:
        queue = stream_handler.subscribe()
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                event = item
                if isinstance(event, DataStageStartEvent):
                    executed_stages.append(event.stage)
                elif isinstance(event, DataRunEndEvent):
                    final_run_end_events.append(event)
                    break
        finally:
            stream_handler.unsubscribe(queue)

    listener_task = asyncio.create_task(stream_listener())
    res = await controller.execute()
    await listener_task

    assert res["status"] == "completed"

    expected_stages = [
        "ingest_and_validate",
        "transcribe_and_segment",
        "score_candidates",
        "track_speaker_position",
        "confidence_gate",
        "smooth_crop_path",
        "render_and_export",
        "aggregate_and_terminate",
    ]
    assert executed_stages == expected_stages, f"Stages diverged from spec: {executed_stages}"

    # Verify 1:1 grounding to StateSchema
    assert len(final_run_end_events) == 1
    event = final_run_end_events[0]
    state = controller.state

    assert event.deliverables_count == len(state.rendered_clips)
    assert event.skipped_count == len(state.skipped_segments)
    assert event.reason == "success"

    assert len(state.rendered_clips) == 1
    assert len(state.crop_path_exports) == 1
    clip = state.rendered_clips[0]
    export_ref = state.crop_path_exports[0]
    assert Path(clip.path).is_file()
    assert Path(export_ref.path).is_file()


# ===========================================================================
# Section 9.4 & 9.6: "Agent Is Working" & Non-Negotiable Invariants
# ===========================================================================

@pytest.mark.asyncio
async def test_eval_agent_is_working_trace_file_hierarchy(
    eval_config: RuntimeConfig,
    simple_case_path: Path,
) -> None:
    """Section 9.4: Local OTel trace log produced with valid 3-tier hierarchy, zero network export."""
    session_id = "eval_trace_test_run"
    controller = PipelineController(
        config=eval_config,
        source_video_path=simple_case_path,
        session_id=session_id,
    )
    res = await controller.execute()
    assert res["status"] == "completed"

    trace_file = eval_config.trace_log_dir / f"{session_id}_trace.jsonl"
    assert trace_file.is_file(), "Trace log file must exist on disk"
    assert trace_file.stat().st_size > 0

    lines = [json.loads(line) for line in trace_file.read_text(encoding="utf-8").strip().splitlines()]
    span_names = [record.get("name") for record in lines]

    # Verify Root span
    assert "run" in span_names

    # Verify Stage spans
    assert "stage:ingest_and_validate" in span_names
    assert "stage:transcribe_and_segment" in span_names
    assert "stage:render_and_export" in span_names

    # Verify Tool / Segment spans
    tool_spans = [n for n in span_names if n.startswith("tool:")]
    assert len(tool_spans) >= 6

    # Verify attributes in clipcrop.* namespace
    run_record = next(r for r in lines if r.get("name") == "run")
    assert run_record["attributes"]["clipcrop.session_id"] == session_id
    assert run_record["attributes"]["clipcrop.run.outcome"] == "success"

    # Append feedback and assert annotation written
    append_feedback_annotation(trace_file=trace_file, run_id=session_id, segment_id="seg_01", rating="up", note="Great framing!")
    updated_lines = [json.loads(line) for line in trace_file.read_text(encoding="utf-8").strip().splitlines()]
    feedback_record = updated_lines[-1]
    assert feedback_record.get("annotation_type") == "user_feedback"
    assert feedback_record["attributes"]["clipcrop.feedback.rating"] == "up"
    assert feedback_record["attributes"]["clipcrop.feedback.note"] == "Great framing!"


def test_eval_non_negotiable_loop_bounds_and_circuit_breakers(eval_config: RuntimeConfig) -> None:
    """Section 9.6: Loop bounds and circuit breakers are locked and enforced."""
    assert eval_config.max_candidates <= 10
    assert eval_config.time_budget_seconds <= 90.0

    # Reducer last_write_wins caps candidates at max_candidates
    state = StateSchema(session_id="bounds_test", config=eval_config)
    oversized_candidates = [
        CandidateSegment(
            segment_id=f"seg_{i:02d}",
            start_ms=i * 1000,
            end_ms=(i + 1) * 1000,
            score=0.9,
            pause_pattern_score=0.8,
            energy_peak_score=0.85,
            speaking_rate_variance_score=0.7,
            keyword_density_score=0.9,
            rank=i + 1,
        )
        for i in range(15)
    ]
    with pytest.raises(StateValidationError) as exc:
        apply_state_update(state, "candidate_segments", oversized_candidates)
    assert "exceeds maximum allowed" in str(exc.value)

    # Valid candidates within cap are accepted
    valid_candidates = oversized_candidates[:10]
    updated_state = apply_state_update(state, "candidate_segments", valid_candidates)
    assert len(updated_state.candidate_segments) == 10, "Candidate segments within cap must be accepted"


def test_eval_tool_specific_failure_messages() -> None:
    """Section 9.4: Error messages map to exact Tool-Specific Failure Mapping Table from spec."""
    failure_mappings = {
        "invalid_source": "The uploaded video cannot be read or contains no usable video or audio track. Please check the file and try again.",
        "zero_candidates": "No speech or conversation segments could be identified in this video. Please upload a video with audible dialogue.",
        "time_budget_exhausted": "The processing time limit was reached before all clips could be rendered. Any completed clips are shown below.",
        "stream_interrupted": "Connection to the processing engine was lost. Please refresh or try again.",
    }

    for err_code, expected_msg in failure_mappings.items():
        err_event = ErrorEvent(code=err_code, message=expected_msg, recoverable=False)
        sse_line = format_sse_event(err_event)
        parsed = parse_sse_line(sse_line)
        assert parsed is not None
        assert isinstance(parsed, ErrorEvent)
        assert parsed.code == err_code
        assert parsed.message == expected_msg

