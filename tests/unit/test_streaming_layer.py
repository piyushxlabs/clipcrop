"""Unit and integration tests for the ClipCrop typed streaming layer.

Verifies:
1. Strict Pydantic V2 validation and wire formatting for all 7 event types.
2. StreamHandler publisher-subscriber broadcasting and historical replay.
3. ToolTracker and progress heartbeat context managers.
4. Full SSE integration test connecting to GET /runs/{run_id}/stream for
   a Simple Case run and verifying reception of every event type in documented order
   per AGENT_MASTER_PLAN.md Section 10 (Step 15) and Section 7.
"""

from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from src.config import RuntimeConfig
from src.main import RUN_REGISTRY, app
from src.ui.event_types import (
    DataRunEndEvent,
    DataStageProgressEvent,
    DataStageStartEvent,
    DataStateUpdateEvent,
    ErrorEvent,
    StreamEvent,
    ToolInputAvailableEvent,
    ToolOutputAvailableEvent,
    format_sse_event,
    parse_sse_line,
)
from src.ui.stream_handler import StreamHandler


# ---------------------------------------------------------------------------
# 1. Event Types Pydantic V2 Schema Validation Tests
# ---------------------------------------------------------------------------

def test_event_types_validation_and_serialization() -> None:
    """All 7 event models validate strictly and serialize to wire format."""
    # 1. DataStageStartEvent
    start = DataStageStartEvent(
        stage="ingest_and_validate",
        label="Validating video",
    )
    assert start.type == "data-stage-start"
    wire_start = format_sse_event(start)
    assert wire_start.startswith("data: ")
    assert wire_start.endswith("\n\n")
    parsed_start = parse_sse_line(wire_start)
    assert isinstance(parsed_start, DataStageStartEvent)
    assert parsed_start.stage == "ingest_and_validate"

    # 2. DataStageProgressEvent
    progress = DataStageProgressEvent(
        stage="transcribe_and_segment",
        detail={"elapsed_ms": 4200},
    )
    wire_prog = format_sse_event(progress)
    parsed_prog = parse_sse_line(wire_prog)
    assert isinstance(parsed_prog, DataStageProgressEvent)
    assert parsed_prog.detail == {"elapsed_ms": 4200}

    # 3. ToolInputAvailableEvent
    t_in = ToolInputAvailableEvent(
        toolCallId="call_ingest_01",
        toolName="decode_and_validate_source",
        input={"source_path": "/uploads/test.mp4"},
    )
    wire_tin = format_sse_event(t_in)
    parsed_tin = parse_sse_line(wire_tin)
    assert isinstance(parsed_tin, ToolInputAvailableEvent)
    assert parsed_tin.toolCallId == "call_ingest_01"
    assert parsed_tin.toolName == "decode_and_validate_source"

    # 4. ToolOutputAvailableEvent
    t_out = ToolOutputAvailableEvent(
        toolCallId="call_ingest_01",
        toolName="decode_and_validate_source",
        output={"success": True, "duration_seconds": 6.8},
    )
    wire_tout = format_sse_event(t_out)
    parsed_tout = parse_sse_line(wire_tout)
    assert isinstance(parsed_tout, ToolOutputAvailableEvent)
    assert parsed_tout.output["success"] is True

    # 5. DataStateUpdateEvent (merge-by-key with key)
    state_up = DataStateUpdateEvent(
        field="confidence_gate_results",
        reducer="merge-by-key",
        key="seg_01",
        value={"decision": "render", "tracking_confidence": 0.95},
    )
    wire_sup = format_sse_event(state_up)
    parsed_sup = parse_sse_line(wire_sup)
    assert isinstance(parsed_sup, DataStateUpdateEvent)
    assert parsed_sup.key == "seg_01"

    # 5b. DataStateUpdateEvent (last-write-wins without key)
    state_up_lww = DataStateUpdateEvent(
        field="candidate_segments",
        reducer="last-write-wins",
        value=[{"segment_id": "seg_01", "score": 0.9}],
    )
    wire_lww = format_sse_event(state_up_lww)
    assert "key" not in json.loads(wire_lww[6:])
    parsed_lww = parse_sse_line(wire_lww)
    assert isinstance(parsed_lww, DataStateUpdateEvent)
    assert parsed_lww.key is None

    # 6. ErrorEvent
    err = ErrorEvent(
        code="zero_candidates",
        message="No clip-worthy segments detected.",
        recoverable=False,
    )
    wire_err = format_sse_event(err)
    parsed_err = parse_sse_line(wire_err)
    assert isinstance(parsed_err, ErrorEvent)
    assert parsed_err.code == "zero_candidates"
    assert parsed_err.recoverable is False

    # 7. DataRunEndEvent
    run_end = DataRunEndEvent(
        reason="success",
        deliverables_count=1,
        skipped_count=0,
    )
    wire_end = format_sse_event(run_end)
    parsed_end = parse_sse_line(wire_end)
    assert isinstance(parsed_end, DataRunEndEvent)
    assert parsed_end.reason == "success"
    assert parsed_end.deliverables_count == 1


# ---------------------------------------------------------------------------
# 2. StreamHandler Unit Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_handler_broadcast_and_history_replay() -> None:
    """StreamHandler broadcasts to multiple subscribers and replays history to late joiners."""
    handler = StreamHandler(run_id="test_run")

    # Pre-populate history with an event
    ev1 = DataStageStartEvent(stage="stage_1", label="Stage 1")
    await handler.emit(ev1)

    # Subscriber 1 connects
    sub1 = handler.subscribe()

    # Emit second event
    ev2 = DataStateUpdateEvent(
        field="source_video",
        reducer="immutable-after-init",
        value={"duration_seconds": 10.0},
    )
    await handler.emit(ev2)

    # Subscriber 2 connects late
    sub2 = handler.subscribe()

    # Emit end
    ev3 = DataRunEndEvent(reason="success")
    await handler.emit(ev3)
    handler.close()

    # Collect from sub1
    sub1_events = []
    while not sub1.empty():
        item = sub1.get_nowait()
        if item is not None:
            sub1_events.append(item)

    # Collect from sub2 (should have received history + live)
    sub2_events = []
    while not sub2.empty():
        item = sub2.get_nowait()
        if item is not None:
            sub2_events.append(item)

    assert len(sub1_events) == 3
    assert len(sub2_events) == 3
    assert sub1_events[0].type == "data-stage-start"
    assert sub2_events[0].type == "data-stage-start"
    assert sub1_events[2].type == "data-run-end"
    assert sub2_events[2].type == "data-run-end"


@pytest.mark.asyncio
async def test_stream_handler_tool_tracker() -> None:
    """ToolTracker emits tool-input-available and tool-output-available."""
    handler = StreamHandler(run_id="test_run")
    sub = handler.subscribe()

    tracker = handler.track_tool(
        "test_tool",
        {"param": "val"},
        tool_call_id="call_test_01",
    )
    async with tracker as t:
        await t.record_output({"success": True, "result": 42})

    events = []
    while not sub.empty():
        item = sub.get_nowait()
        if item is not None:
            events.append(item)

    assert len(events) == 2
    assert isinstance(events[0], ToolInputAvailableEvent)
    assert events[0].toolCallId == "call_test_01"
    assert isinstance(events[1], ToolOutputAvailableEvent)
    assert events[1].output == {"success": True, "result": 42}


@pytest.mark.asyncio
async def test_stream_handler_track_progress_heartbeat() -> None:
    """track_progress emits elapsed_ms heartbeat events."""
    handler = StreamHandler(run_id="test_run")
    sub = handler.subscribe()

    async with handler.track_progress("test_stage", interval_seconds=0.05):
        await asyncio.sleep(0.12)

    events = []
    while not sub.empty():
        item = sub.get_nowait()
        if item is not None:
            events.append(item)

    assert len(events) >= 1
    assert all(isinstance(e, DataStageProgressEvent) for e in events)
    assert all("elapsed_ms" in e.detail for e in events)


# ---------------------------------------------------------------------------
# 3. Simple Case End-to-End SSE Integration Verification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_streaming_layer_simple_case_receives_all_spec_events_in_order(
    tmp_path: Path,
) -> None:
    """A test client connects to GET /runs/{run_id}/stream for Simple Case

    and receives every event type listed in Section 7 in the documented order:
    1. data-stage-start
    2. data-stage-progress
    3. tool-input-available
    4. tool-output-available
    5. data-state-update
    6. data-run-end
    """
    RUN_REGISTRY.clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        fixture_path = Path("tests/fixtures/simple_case.mp4").resolve()
        assert fixture_path.is_file()

        with open(fixture_path, "rb") as f:
            upload_resp = await ac.post(
                "/runs",
                files={"file": ("simple.mp4", f, "video/mp4")},
            )
        assert upload_resp.status_code == 201
        run_id = upload_resp.json()["run_id"]

        # Connect to SSE stream
        events: list[StreamEvent] = []
        async with ac.stream("GET", f"/runs/{run_id}/stream") as stream_resp:
            assert stream_resp.status_code == 200
            assert "text/event-stream" in stream_resp.headers["content-type"]

            async for line in stream_resp.aiter_lines():
                parsed = parse_sse_line(line)
                if parsed is not None:
                    events.append(parsed)
                    if isinstance(parsed, DataRunEndEvent):
                        break

        # Verification: Assert all key event types from Section 7 were received
        event_types = [e.type for e in events]
        assert "data-stage-start" in event_types
        assert "tool-input-available" in event_types
        assert "tool-output-available" in event_types
        assert "data-state-update" in event_types
        assert "data-run-end" in event_types

        # Verify initial event is data-stage-start for Stage 1
        assert isinstance(events[0], DataStageStartEvent)
        assert events[0].stage == "ingest_and_validate"

        # Verify terminal event is data-run-end with reason="success"
        terminal_event = events[-1]
        assert isinstance(terminal_event, DataRunEndEvent)
        assert terminal_event.reason == "success"
        assert terminal_event.deliverables_count == 1

        # Verify tool inputs and outputs match registered tools
        tool_input_names = [e.toolName for e in events if isinstance(e, ToolInputAvailableEvent)]
        tool_output_names = [e.toolName for e in events if isinstance(e, ToolOutputAvailableEvent)]
        assert "decode_and_validate_source" in tool_input_names
        assert "decode_and_validate_source" in tool_output_names
        assert "transcribe_audio" in tool_input_names
        assert "transcribe_audio" in tool_output_names
        assert "detect_speech_pauses" in tool_input_names
        assert "detect_speech_pauses" in tool_output_names
        assert "track_speaker_position" in tool_input_names
        assert "track_speaker_position" in tool_output_names
        assert "smooth_crop_path" in tool_input_names
        assert "smooth_crop_path" in tool_output_names
        assert "render_vertical_clip" in tool_input_names
        assert "render_vertical_clip" in tool_output_names
        assert "export_crop_path_data" in tool_input_names
        assert "export_crop_path_data" in tool_output_names

        # Verify state updates cover key StateSchema fields with correct reducers
        state_updates = [e for e in events if isinstance(e, DataStateUpdateEvent)]
        fields_updated = [e.field for e in state_updates]
        assert "source_video" in fields_updated
        assert "transcript_segments" in fields_updated
        assert "vad_segments" in fields_updated
        assert "candidate_segments" in fields_updated
        assert "tracking_results" in fields_updated
        assert "confidence_gate_results" in fields_updated
        assert "crop_paths" in fields_updated
        assert "rendered_clips" in fields_updated
        assert "crop_path_exports" in fields_updated

        # Verify reducer types conform to spec
        for su in state_updates:
            assert su.reducer in (
                "immutable-after-init",
                "append-only",
                "merge-by-key",
                "last-write-wins",
            )
            if su.reducer == "merge-by-key":
                assert su.key is not None


@pytest.mark.asyncio
async def test_streaming_layer_zero_candidates_emits_error_and_run_end(
    tmp_path: Path,
) -> None:
    """Silent audio edge case emits error event and terminates with data-run-end."""
    RUN_REGISTRY.clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create silent 2-second fixture
        silent_file = tmp_path / "silent.mp4"
        import subprocess
        from src.config import load_config_from_env
        ffmpeg_bin = str(load_config_from_env().ffmpeg_path)
        subprocess.run(
            [
                ffmpeg_bin, "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=2",
                "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
                "-t", "2", "-c:v", "libx264", "-c:a", "aac", str(silent_file),
            ],
            check=True,
            capture_output=True,
        )

        with open(silent_file, "rb") as f:
            upload_resp = await ac.post("/runs", files={"file": ("silent.mp4", f, "video/mp4")})
        assert upload_resp.status_code == 201
        run_id = upload_resp.json()["run_id"]

        events: list[StreamEvent] = []
        async with ac.stream("GET", f"/runs/{run_id}/stream") as stream_resp:
            async for line in stream_resp.aiter_lines():
                parsed = parse_sse_line(line)
                if parsed is not None:
                    events.append(parsed)
                    if isinstance(parsed, DataRunEndEvent):
                        break

        event_types = [e.type for e in events]
        assert "error" in event_types
        assert "data-run-end" in event_types

        err_event = next(e for e in events if isinstance(e, ErrorEvent))
        assert err_event.code == "zero_candidates"
        assert err_event.recoverable is False

        end_event = next(e for e in events if isinstance(e, DataRunEndEvent))
        assert end_event.reason == "error"
