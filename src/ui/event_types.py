"""Typed Server-Sent Events (SSE) models for ClipCrop.

Conforms to Vercel AI SDK v6 Data Stream wire format specifications
per INTERFACE_OBSERVABILITY_SYSTEM.md Section 2a and AGENT_MASTER_PLAN.md Section 7.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

STAGE_LABELS: dict[str, str] = {
    "ingest_and_validate": "Validating video",
    "transcribe_and_segment": "Listening for speech",
    "score_candidates": "Ranking candidate segments",
    "track_speaker_position": "Finding the speaker",
    "confidence_gate": "Evaluating tracking confidence",
    "smooth_crop_path": "Smoothing the camera path",
    "render_and_export": "Rendering clips and exporting timeline data",
    "aggregate_and_terminate": "Finalizing summary and deliverables",
}


class DataStageStartEvent(BaseModel):
    """Emitted when a pipeline stage begins execution."""

    model_config = ConfigDict(strict=True)

    type: Literal["data-stage-start"] = "data-stage-start"
    stage: str
    label: str


class DataStageProgressEvent(BaseModel):
    """Emitted periodically during long-running tool execution (elapsed time only)."""

    model_config = ConfigDict(strict=True)

    type: Literal["data-stage-progress"] = "data-stage-progress"
    stage: str
    detail: Union[dict[str, Any], str]


class ToolInputAvailableEvent(BaseModel):
    """Emitted immediately before a tool call is dispatched with validated input."""

    model_config = ConfigDict(strict=True)

    type: Literal["tool-input-available"] = "tool-input-available"
    toolCallId: str
    toolName: str
    input: dict[str, Any]


class ToolOutputAvailableEvent(BaseModel):
    """Emitted immediately after a tool call completes with validated output."""

    model_config = ConfigDict(strict=True)

    type: Literal["tool-output-available"] = "tool-output-available"
    toolCallId: str
    toolName: str
    output: dict[str, Any]


class DataStateUpdateEvent(BaseModel):
    """Emitted when a typed state field is written via its declared reducer."""

    model_config = ConfigDict(strict=True)

    type: Literal["data-state-update"] = "data-state-update"
    field: str
    reducer: Literal[
        "append-only",
        "merge-by-key",
        "last-write-wins",
        "immutable-after-init",
        "append_only",
        "merge_by_key",
        "last_write_wins",
        "immutable_after_init",
    ]
    key: str | None = None
    value: Any


class ErrorEvent(BaseModel):
    """Emitted on permanent failure."""

    model_config = ConfigDict(strict=True)

    type: Literal["error"] = "error"
    code: str
    message: str
    recoverable: bool = False


class DataRunEndEvent(BaseModel):
    """Emitted when the pipeline finishes all stages (success, interrupted, or error)."""

    model_config = ConfigDict(strict=True)

    type: Literal["data-run-end"] = "data-run-end"
    reason: Literal["success", "interrupted", "error", "no_deliverables"]
    deliverables_count: int | None = None
    skipped_count: int | None = None


StreamEvent = Annotated[
    Union[
        DataStageStartEvent,
        DataStageProgressEvent,
        ToolInputAvailableEvent,
        ToolOutputAvailableEvent,
        DataStateUpdateEvent,
        ErrorEvent,
        DataRunEndEvent,
    ],
    Field(discriminator="type"),
]

_stream_event_adapter = TypeAdapter(StreamEvent)


def format_sse_event(event: BaseModel | dict[str, Any] | str) -> str:
    """Format an event model or dictionary into Vercel AI SDK v6 Data Stream wire line ('data: <json>\\n\\n')."""
    if isinstance(event, BaseModel):
        payload = event.model_dump(exclude_none=True)
    elif isinstance(event, dict):
        payload = {k: v for k, v in event.items() if v is not None}
    elif isinstance(event, str):
        if event.startswith("data: "):
            return event if event.endswith("\n\n") else f"{event}\n\n"
        return f"data: {event}\n\n"
    else:
        raise ValueError(f"Unsupported event type for SSE formatting: {type(event)}")

    json_str = json.dumps(payload, default=str)
    return f"data: {json_str}\n\n"


def parse_sse_line(line: str) -> StreamEvent | None:
    """Parse a single SSE wire line ('data: <json>\\n\\n' or 'data: <json>') into a validated StreamEvent."""
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.startswith("data: "):
        json_part = stripped[6:]
    else:
        json_part = stripped

    data = json.loads(json_part)
    return _stream_event_adapter.validate_python(data)
