"""FastAPI backend application for ClipCrop.

Exposes REST and SSE endpoints for single-shot video reframing:
- GET  /health              -> System health and version check
- POST /runs                -> Multipart video file upload and run session creation
- GET  /runs/{run_id}/stream -> Persistent Server-Sent Events (SSE) progress stream
- POST /runs/{run_id}/cancel -> Emergency stop / mid-run cancellation
- POST /runs/{run_id}/feedback -> Per-clip feedback annotation capture
- GET  /outputs/{filename}  -> Deliverable file download (MP4 / EDL / XML / JSON)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator, Literal

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from src.agents.pipeline_controller import PipelineController, PipelineStage
from src.config import RuntimeConfig, load_config_from_env
from src.exceptions import ClipCropError, PermanentFailureError

logger = logging.getLogger("clipcrop.api")

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}


# ---------------------------------------------------------------------------
# Pydantic Request / Response Schemas
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Health check response."""

    model_config = ConfigDict(strict=True)

    status: str = Field("healthy", description="Service status indicator.")
    version: str = Field("0.1.0", description="ClipCrop application version.")


class CreateRunResponse(BaseModel):
    """Response returned upon successful video upload and session initialization."""

    model_config = ConfigDict(strict=True)

    run_id: str = Field(..., description="Unique run identifier (UUIDv4).")
    status: str = Field("created", description="Initial run state.")
    source_filename: str = Field(..., description="Sanitized uploaded filename.")


class CancelRunResponse(BaseModel):
    """Response returned upon initiating emergency stop."""

    model_config = ConfigDict(strict=True)

    run_id: str = Field(..., description="Target run identifier.")
    status: str = Field("cancelling", description="Cancellation acknowledgement status.")


class FeedbackRequest(BaseModel):
    """Per-clip thumbs up/down and text feedback per INTERFACE_OBSERVABILITY_SYSTEM.md Section 7a."""

    model_config = ConfigDict(strict=True)

    segment_id: str = Field(..., description="Identifier of the evaluated clip segment.")
    rating: Literal["up", "down"] = Field(..., description="Binary user satisfaction rating.")
    note: str | None = Field(
        default=None,
        max_length=500,
        description="Optional one-line developer note describing what was off.",
    )


class FeedbackResponse(BaseModel):
    """Acknowledgement of recorded feedback annotation."""

    model_config = ConfigDict(strict=True)

    run_id: str = Field(..., description="Run identifier.")
    status: str = Field("recorded", description="Feedback receipt status.")
    segment_id: str = Field(..., description="Segment ID feedback was registered against.")


# ---------------------------------------------------------------------------
# Run Session Registry (In-Memory Ephemeral)
# ---------------------------------------------------------------------------

@dataclass
class RunSession:
    """Ephemeral in-process tracking for a single video reframing run."""

    run_id: str
    controller: PipelineController
    source_filename: str
    source_video_path: Path
    created_at: float = field(default_factory=time.time)
    status: str = "created"  # created, running, completed, cancelled, failed
    feedback: dict[str, dict[str, Any]] = field(default_factory=dict)
    task: asyncio.Task[dict[str, Any]] | None = None
    event_queue: asyncio.Queue[str] = field(default_factory=asyncio.Queue)
    result: dict[str, Any] | None = None
    error: str | None = None


RUN_REGISTRY: dict[str, RunSession] = {}


def _sanitize_filename(filename: str) -> str:
    """Extract base filename and remove unsafe path characters."""
    base = Path(filename).name
    # Strip non-alphanumeric characters except safe dots, dashes, underscores
    sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", base)
    if not sanitized or sanitized in {".", ".."}:
        sanitized = "video.mp4"
    return sanitized


# ---------------------------------------------------------------------------
# FastAPI Application Factory
# ---------------------------------------------------------------------------

def create_app(config: RuntimeConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI backend instance."""
    runtime_config = config or load_config_from_env()

    app = FastAPI(
        title="ClipCrop API",
        version="0.1.0",
        description="Deterministic local video re-framing engine converting talking-head video into 9:16 vertical clips.",
    )

    # Enable CORS for local frontend dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Ensure local directory sandboxes exist
    runtime_config.upload_dir.mkdir(parents=True, exist_ok=True)
    runtime_config.output_dir.mkdir(parents=True, exist_ok=True)
    runtime_config.trace_log_dir.mkdir(parents=True, exist_ok=True)

    @app.get("/health", response_model=HealthResponse, tags=["System"])
    async def get_health() -> HealthResponse:
        """Health check endpoint responding 200 with service version."""
        return HealthResponse(status="healthy", version="0.1.0")

    @app.post(
        "/runs",
        response_model=CreateRunResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["Pipeline"],
    )
    async def create_run(
        file: UploadFile = File(..., description="Source video file to re-frame."),
        confidence_threshold: float | None = Form(
            default=None,
            ge=0.0,
            le=1.0,
            description="Optional confidence threshold override.",
        ),
        time_budget_seconds: float | None = Form(
            default=None,
            ge=1.0,
            le=600.0,
            description="Optional time budget circuit breaker override.",
        ),
    ) -> CreateRunResponse:
        """Receive video upload, validate sandbox path, and initialize a new run session."""
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file must have a valid filename.",
            )

        safe_name = _sanitize_filename(file.filename)
        ext = Path(safe_name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'. Allowed formats: {sorted(ALLOWED_EXTENSIONS)}",
            )

        run_id = str(uuid.uuid4())
        dest_filename = f"{run_id}_{safe_name}"
        dest_path = (runtime_config.upload_dir / dest_filename).resolve()

        # Enforce sandbox: ensure destination resolves strictly inside upload_dir
        if not dest_path.is_relative_to(runtime_config.upload_dir.resolve()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path security violation: Upload destination is outside upload directory.",
            )

        # Write uploaded file in chunks
        bytes_written = 0
        try:
            with open(dest_path, "wb") as out_file:
                while chunk := await file.read(1024 * 1024):  # 1MB chunks
                    out_file.write(chunk)
                    bytes_written += len(chunk)
        except Exception as e:
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to write uploaded file to disk: {e}",
            ) from e

        if bytes_written == 0:
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes).",
            )

        # Build custom config if overrides provided
        run_config = runtime_config
        updates: dict[str, Any] = {}
        if confidence_threshold is not None:
            updates["confidence_threshold"] = confidence_threshold
        if time_budget_seconds is not None:
            updates["time_budget_seconds"] = time_budget_seconds
        if updates:
            run_config = runtime_config.model_copy(update=updates)

        controller = PipelineController(
            config=run_config,
            source_video_path=dest_path,
            session_id=run_id,
        )

        session = RunSession(
            run_id=run_id,
            controller=controller,
            source_filename=safe_name,
            source_video_path=dest_path,
        )
        RUN_REGISTRY[run_id] = session

        return CreateRunResponse(
            run_id=run_id,
            status="created",
            source_filename=safe_name,
        )

    @app.get(
        "/runs/{run_id}/stream",
        response_class=StreamingResponse,
        tags=["Pipeline"],
    )
    async def stream_run(run_id: str) -> StreamingResponse:
        """Stream real-time Server-Sent Events (SSE) for the pipeline run."""
        session = RUN_REGISTRY.get(run_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run session '{run_id}' not found.",
            )

        async def sse_event_generator() -> AsyncGenerator[str, None]:
            """Yield SSE wire format events from pipeline execution."""
            controller = session.controller

            # Helper to format SSE message
            def _format_sse(event_data: dict[str, Any]) -> str:
                return f"data: {json.dumps(event_data)}\n\n"

            # If the session is already completed or failed, emit current state and run-end
            if session.status in ("completed", "cancelled", "failed"):
                state_dump = {
                    "rendered_clips": [c.model_dump() for c in controller.state.rendered_clips],
                    "crop_path_exports": [e.model_dump() for e in controller.state.crop_path_exports],
                    "skipped_segments": [s.model_dump() for s in controller.state.skipped_segments],
                }
                yield _format_sse({
                    "type": "data-state-update",
                    "field": "rendered_clips",
                    "reducer": "append-only",
                    "value": state_dump,
                })
                reason = "interrupted" if session.status == "cancelled" else ("error" if session.status == "failed" else "success")
                yield _format_sse({"type": "data-run-end", "reason": reason})
                return

            session.status = "running"

            # Emit initial stage-start
            yield _format_sse({
                "type": "data-stage-start",
                "stage": PipelineStage.STAGE_1_INGEST_AND_VALIDATE.value,
                "label": "Ingesting and validating source video",
            })

            try:
                result = await controller.execute()
                session.result = result
                session.status = "completed"

                # Emit final state updates for deliverables
                for clip in controller.state.rendered_clips:
                    yield _format_sse({
                        "type": "data-state-update",
                        "field": "rendered_clips",
                        "reducer": "append-only",
                        "value": clip.model_dump(),
                    })
                for export in controller.state.crop_path_exports:
                    yield _format_sse({
                        "type": "data-state-update",
                        "field": "crop_path_exports",
                        "reducer": "append-only",
                        "value": export.model_dump(),
                    })
                for skip in controller.state.skipped_segments:
                    yield _format_sse({
                        "type": "data-state-update",
                        "field": "skipped_segments",
                        "reducer": "append-only",
                        "value": skip.model_dump(),
                    })

                yield _format_sse({
                    "type": "data-run-end",
                    "reason": "success" if result.get("rendered_count", 0) > 0 else "no_deliverables",
                    "deliverables_count": len(controller.state.rendered_clips),
                    "skipped_count": len(controller.state.skipped_segments),
                })

            except PermanentFailureError as pfe:
                session.status = "cancelled" if "cancelled" in str(pfe).lower() else "failed"
                session.error = str(pfe)
                if "cancelled" in str(pfe).lower():
                    yield _format_sse({"type": "data-run-end", "reason": "interrupted"})
                else:
                    code = "zero_candidates" if "zero_candidates" in str(pfe).lower() else "permanent_failure"
                    yield _format_sse({
                        "type": "error",
                        "code": code,
                        "message": str(pfe),
                        "recoverable": False,
                    })
                    yield _format_sse({"type": "data-run-end", "reason": "error"})

            except Exception as e:
                session.status = "failed"
                session.error = str(e)
                yield _format_sse({
                    "type": "error",
                    "code": "unexpected_error",
                    "message": str(e),
                    "recoverable": False,
                })
                yield _format_sse({"type": "data-run-end", "reason": "error"})

        return StreamingResponse(
            sse_event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post(
        "/runs/{run_id}/cancel",
        response_model=CancelRunResponse,
        tags=["Pipeline"],
    )
    async def cancel_run(run_id: str) -> CancelRunResponse:
        """Trigger emergency stop / cancellation for an in-flight run session."""
        session = RUN_REGISTRY.get(run_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run session '{run_id}' not found.",
            )

        session.controller.cancel()
        session.status = "cancelled"
        return CancelRunResponse(run_id=run_id, status="cancelling")

    @app.post(
        "/runs/{run_id}/feedback",
        response_model=FeedbackResponse,
        tags=["Telemetry"],
    )
    async def submit_feedback(
        run_id: str,
        feedback_input: FeedbackRequest,
    ) -> FeedbackResponse:
        """Capture user satisfaction feedback and append annotation to local trace log."""
        session = RUN_REGISTRY.get(run_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run session '{run_id}' not found.",
            )

        # Record feedback in session memory
        session.feedback[feedback_input.segment_id] = feedback_input.model_dump()

        # Append annotation to local trace log if file exists
        trace_file = runtime_config.trace_log_dir / f"{run_id}_trace.jsonl"
        annotation = {
            "timestamp": time.time(),
            "run_id": run_id,
            "segment_id": feedback_input.segment_id,
            "rating": feedback_input.rating,
            "note": feedback_input.note,
        }
        try:
            with open(trace_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(annotation) + "\n")
        except Exception as e:
            logger.warning("Could not write feedback annotation to %s: %s", trace_file, e)

        return FeedbackResponse(
            run_id=run_id,
            status="recorded",
            segment_id=feedback_input.segment_id,
        )

    @app.get(
        "/outputs/{filename}",
        response_class=FileResponse,
        tags=["Deliverables"],
    )
    async def get_deliverable(filename: str) -> FileResponse:
        """Download delivered vertical clip (.mp4) or crop-path timeline file (.edl/.xml/.json)."""
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename contains illegal path traversal characters.",
            )

        file_path = (runtime_config.output_dir / filename).resolve()
        if not file_path.is_relative_to(runtime_config.output_dir.resolve()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: requested path resolves outside allowed output directory.",
            )

        if not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Deliverable file '{filename}' does not exist.",
            )

        media_type = "video/mp4" if file_path.suffix.lower() == ".mp4" else "text/plain"
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=media_type,
        )

    return app


# Default application instance
app = create_app()


def main() -> None:
    """Entry point for running the ClipCrop API server via Uvicorn."""
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
