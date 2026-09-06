"""Asynchronous event queue and SSE stream handler for ClipCrop.

Provides publisher-subscriber broadcasting of typed StreamEvents,
in-order SSE line generation, and tool/stage lifecycle tracking helpers
per INTERFACE_OBSERVABILITY_SYSTEM.md Section 2a and AGENT_MASTER_PLAN.md Section 7.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Literal

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
)


class ToolTracker:
    """Context manager for tracking a tool execution with input and output events."""

    def __init__(
        self,
        handler: StreamHandler,
        tool_name: str,
        input_data: dict[str, Any],
        tool_call_id: str | None = None,
    ) -> None:
        self.handler = handler
        self.tool_name = tool_name
        self.input_data = input_data
        self.tool_call_id = tool_call_id or f"call_{tool_name}_{uuid.uuid4().hex[:8]}"
        self._output_recorded = False

    async def __aenter__(self) -> ToolTracker:
        await self.handler.emit_tool_input(
            self.tool_call_id, self.tool_name, self.input_data
        )
        return self

    async def record_output(self, output_data: dict[str, Any]) -> None:
        """Record successful or explicitly handled tool output."""
        if not self._output_recorded:
            self._output_recorded = True
            await self.handler.emit_tool_output(
                self.tool_call_id, self.tool_name, output_data
            )

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Emit failure output event if an unhandled exception occurred."""
        if exc_val is not None and not self._output_recorded:
            self._output_recorded = True
            await self.handler.emit_tool_output(
                self.tool_call_id,
                self.tool_name,
                {"success": False, "error": str(exc_val)},
            )


class StreamHandler:
    """Manages asynchronous broadcasting of typed StreamEvents for a single run session.

    Supports multiple subscriber queues, history preservation for late-joining
    clients, and high-level emission helpers for stages, tools, and state updates.
    """

    def __init__(self, run_id: str | None = None) -> None:
        self.run_id = run_id or str(uuid.uuid4())
        self.history: list[StreamEvent] = []
        self._subscribers: set[asyncio.Queue[StreamEvent | None]] = set()
        self._is_closed = False

    def subscribe(self) -> asyncio.Queue[StreamEvent | None]:
        """Subscribe to the stream, replaying all past events and receiving live events."""
        q: asyncio.Queue[StreamEvent | None] = asyncio.Queue()
        for ev in self.history:
            q.put_nowait(ev)
        if self._is_closed:
            q.put_nowait(None)
        else:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[StreamEvent | None]) -> None:
        """Remove a subscriber queue."""
        self._subscribers.discard(q)

    async def emit(self, event: StreamEvent) -> None:
        """Append event to history and fan out to all active subscribers."""
        self.history.append(event)
        for q in list(self._subscribers):
            await q.put(event)

    def close(self) -> None:
        """Close the stream broadcaster and signal EOF to all subscriber queues."""
        if not self._is_closed:
            self._is_closed = True
            for q in list(self._subscribers):
                q.put_nowait(None)
            self._subscribers.clear()

    async def emit_stage_start(self, stage: str, label: str) -> None:
        """Emit a data-stage-start event."""
        await self.emit(DataStageStartEvent(stage=stage, label=label))

    async def emit_stage_progress(
        self, stage: str, detail: dict[str, Any] | str
    ) -> None:
        """Emit a periodic data-stage-progress event."""
        await self.emit(DataStageProgressEvent(stage=stage, detail=detail))

    async def emit_tool_input(
        self, tool_call_id: str, tool_name: str, input_data: dict[str, Any]
    ) -> None:
        """Emit a tool-input-available event."""
        await self.emit(
            ToolInputAvailableEvent(
                toolCallId=tool_call_id, toolName=tool_name, input=input_data
            )
        )

    async def emit_tool_output(
        self, tool_call_id: str, tool_name: str, output_data: dict[str, Any]
    ) -> None:
        """Emit a tool-output-available event."""
        await self.emit(
            ToolOutputAvailableEvent(
                toolCallId=tool_call_id, toolName=tool_name, output=output_data
            )
        )

    async def emit_state_update(
        self,
        field: str,
        reducer: Literal[
            "append-only",
            "merge-by-key",
            "last-write-wins",
            "immutable-after-init",
            "append_only",
            "merge_by_key",
            "last_write_wins",
            "immutable_after_init",
        ],
        value: Any,
        key: str | None = None,
    ) -> None:
        """Emit a data-state-update event matching reducer semantics."""
        # Normalize reducer string to hyphenated form per spec
        norm_reducer = reducer.replace("_", "-")
        await self.emit(
            DataStateUpdateEvent(
                field=field,
                reducer=norm_reducer,  # type: ignore[arg-type]
                key=key,
                value=value,
            )
        )

    async def emit_error(
        self, code: str, message: str, recoverable: bool = False
    ) -> None:
        """Emit an error event."""
        await self.emit(
            ErrorEvent(code=code, message=message, recoverable=recoverable)
        )

    async def emit_run_end(
        self,
        reason: Literal["success", "interrupted", "error", "no_deliverables"],
        deliverables_count: int | None = None,
        skipped_count: int | None = None,
    ) -> None:
        """Emit a data-run-end event and signal stream closure."""
        await self.emit(
            DataRunEndEvent(
                reason=reason,
                deliverables_count=deliverables_count,
                skipped_count=skipped_count,
            )
        )
        self.close()

    def track_tool(
        self,
        tool_name: str,
        input_data: dict[str, Any],
        tool_call_id: str | None = None,
    ) -> ToolTracker:
        """Create a ToolTracker context manager for wrapping tool execution."""
        return ToolTracker(self, tool_name, input_data, tool_call_id=tool_call_id)

    @asynccontextmanager
    async def track_progress(
        self,
        stage: str,
        interval_seconds: float = 2.0,
    ) -> AsyncGenerator[None, None]:
        """Periodically emit elapsed_ms progress events while the block executes."""
        start_time = time.monotonic()
        stop_event = asyncio.Event()

        async def _ticker() -> None:
            while not stop_event.is_set():
                try:
                    await asyncio.sleep(interval_seconds)
                except asyncio.CancelledError:
                    break
                if stop_event.is_set():
                    break
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                await self.emit_stage_progress(stage, {"elapsed_ms": elapsed_ms})

        ticker_task = asyncio.create_task(_ticker())
        try:
            yield
        finally:
            stop_event.set()
            ticker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await ticker_task

    async def event_generator(self) -> AsyncGenerator[str, None]:
        """Yield formatted SSE strings ('data: <json>\\n\\n') from subscriber queue."""
        q = self.subscribe()
        try:
            while True:
                event = await q.get()
                if event is None:
                    break
                yield format_sse_event(event)
                if isinstance(event, DataRunEndEvent):
                    break
        finally:
            self.unsubscribe(q)
