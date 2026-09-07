"""Unit tests for ClipCrop OpenTelemetry local tracing and feedback annotations.

Adheres strictly to:
- docs/AGENT_MASTER_PLAN.md Section 10 Step 18
- docs/INTERFACE_OBSERVABILITY_SYSTEM.md Section 6 & 7a
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opentelemetry.trace import Status, StatusCode

from src.config import RuntimeConfig
from src.telemetry.feedback_annotations import (
    append_feedback_annotation,
    append_interruption_annotation,
)
from src.telemetry.tracing import (
    JsonFileSpanExporter,
    PipelineTracer,
    format_span_id,
    format_trace_id,
)


def test_format_ids() -> None:
    """Verify trace_id and span_id hex formatters."""
    trace_id_int = 0x1234567890ABCDEF1234567890ABCDEF
    span_id_int = 0x1234567890ABCDEF
    assert format_trace_id(trace_id_int) == "1234567890abcdef1234567890abcdef"
    assert format_span_id(span_id_int) == "1234567890abcdef"


def test_json_file_span_exporter_and_tracer_hierarchy(tmp_path: Path) -> None:
    """Verify PipelineTracer records root, stage, segment, and tool spans into a local JSONL file."""
    trace_file = tmp_path / "test_session_trace.jsonl"
    tracer = PipelineTracer(session_id="test_sess_001", trace_file_path=trace_file)

    # 1. Start Root Run Span
    root_span = tracer.start_root_span(source_path="/uploads/test_video.mp4")
    assert root_span is not None

    # 2. Stage 1: Ingest & Validate
    tracer.start_stage_span("ingest_and_validate")
    tracer.record_tool_span(
        "decode_and_validate_source",
        stage_name="ingest_and_validate",
        success=True,
        attributes={"clipcrop.duration_seconds": 15.0, "clipcrop.width": 1920, "clipcrop.height": 1080},
    )
    tracer.end_stage_span("ingest_and_validate", success=True)

    # 3. Stage 4: Fan-out Segment Tracking
    tracer.start_stage_span("track_speaker_position")
    tracer.start_segment_span("seg_01", parent_stage_name="track_speaker_position")
    tracer.record_tool_span(
        "track_speaker_position",
        stage_name="track_speaker_position",
        segment_id="seg_01",
        success=True,
        attributes={"clipcrop.segment.confidence": 0.94, "clipcrop.frames_tracked": 45},
    )
    tracer.end_segment_span(
        "seg_01",
        success=True,
        confidence=0.94,
        gate_decision="render",
        gate_threshold=0.65,
    )
    tracer.end_stage_span("track_speaker_position", success=True)

    # 4. End Root Run Span
    tracer.end_root_span(outcome="success")

    # Verify file exists on disk
    assert trace_file.is_file()

    # Read and parse JSON lines
    lines = [json.loads(line) for line in trace_file.read_text(encoding="utf-8").strip().splitlines()]
    assert len(lines) >= 4

    # Extract spans by name
    span_names = [line["name"] for line in lines]
    assert "stage:ingest_and_validate" in span_names
    assert "tool:decode_and_validate_source" in span_names
    assert "stage:track_speaker_position" in span_names
    assert "segment:seg_01" in span_names
    assert "run" in span_names

    # Verify root span record
    run_record = next(line for line in lines if line["name"] == "run")
    assert run_record["attributes"]["clipcrop.session_id"] == "test_sess_001"
    assert run_record["attributes"]["clipcrop.source.filename"] == "test_video.mp4"
    assert run_record["attributes"]["clipcrop.run.outcome"] == "success"
    assert run_record["status"]["code"] == "OK"

    # Verify parent-child relationship: stage span parent is run span
    root_span_id = run_record["span_id"]
    stage_record = next(line for line in lines if line["name"] == "stage:ingest_and_validate")
    assert stage_record["parent_id"] == root_span_id

    # Verify tool span parent is stage span
    tool_record = next(line for line in lines if line["name"] == "tool:decode_and_validate_source")
    assert tool_record["parent_id"] == stage_record["span_id"]
    assert tool_record["attributes"]["clipcrop.tool.name"] == "decode_and_validate_source"
    assert tool_record["attributes"]["clipcrop.duration_seconds"] == 15.0


def test_append_feedback_annotation(tmp_path: Path) -> None:
    """Verify appending per-clip feedback annotations per Section 7a."""
    trace_file = tmp_path / "run123_trace.jsonl"
    trace_file.write_text('{"name": "run", "span_id": "root01"}\n', encoding="utf-8")

    success = append_feedback_annotation(
        trace_file=trace_file,
        run_id="run123",
        segment_id="seg_01",
        rating="up",
        note="Great camera motion!",
    )
    assert success is True

    # Read back and verify annotation structure
    lines = [json.loads(line) for line in trace_file.read_text(encoding="utf-8").strip().splitlines()]
    assert len(lines) == 2

    annotation = lines[1]
    assert annotation["type"] == "annotation"
    assert annotation["annotation_type"] == "user_feedback"
    assert annotation["run_id"] == "run123"
    assert annotation["segment_id"] == "seg_01"
    assert annotation["attributes"]["clipcrop.feedback.rating"] == "up"
    assert annotation["attributes"]["clipcrop.feedback.note"] == "Great camera motion!"


def test_append_interruption_annotation(tmp_path: Path) -> None:
    """Verify appending interruption annotation upon run cancellation."""
    trace_file = tmp_path / "run456_trace.jsonl"
    trace_file.write_text('{"name": "run", "span_id": "root02"}\n', encoding="utf-8")

    success = append_interruption_annotation(
        trace_file=trace_file,
        run_id="run456",
        reason="user_cancellation",
    )
    assert success is True

    lines = [json.loads(line) for line in trace_file.read_text(encoding="utf-8").strip().splitlines()]
    assert len(lines) == 2

    annotation = lines[1]
    assert annotation["type"] == "annotation"
    assert annotation["annotation_type"] == "run_interrupted"
    assert annotation["run_id"] == "run456"
    assert annotation["attributes"]["clipcrop.run.outcome"] == "interrupted"
    assert annotation["attributes"]["clipcrop.interruption.reason"] == "user_cancellation"


@pytest.mark.asyncio
async def test_pipeline_controller_creates_trace_file(tmp_path: Path) -> None:
    """Verify pipeline controller execution creates a valid trace file in trace_log_dir."""
    from src.agents.pipeline_controller import PipelineController
    from src.config import load_config_from_env

    fixture_path = Path("tests/fixtures/simple_case.mp4").resolve()
    assert fixture_path.is_file()

    session_id = "test_trace_sess_099"
    base_config = load_config_from_env()
    config = base_config.model_copy(
        update={
            "upload_dir": tmp_path / "uploads",
            "output_dir": tmp_path / "outputs",
            "trace_log_dir": tmp_path / "traces",
            "confidence_threshold": 0.65,
            "max_candidates": 2,
            "time_budget_seconds": 90,
        }
    )
    config.upload_dir.mkdir(parents=True, exist_ok=True)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.trace_log_dir.mkdir(parents=True, exist_ok=True)

    controller = PipelineController(
        config=config,
        source_video_path=fixture_path,
        session_id=session_id,
    )

    result = await controller.execute()
    assert result["status"] == "completed"

    expected_trace_file = config.trace_log_dir / f"{session_id}_trace.jsonl"
    assert expected_trace_file.is_file()

    content = expected_trace_file.read_text(encoding="utf-8").strip()
    assert len(content) > 0

    lines = [json.loads(line) for line in content.splitlines()]
    span_names = [line.get("name") for line in lines]

    # Verify root run span and several stages were logged
    assert "run" in span_names
    assert "stage:ingest_and_validate" in span_names
    assert "stage:transcribe_and_segment" in span_names
    assert "stage:aggregate_and_terminate" in span_names
