"""Local-file OpenTelemetry tracing system for ClipCrop.

Adheres strictly to:
- docs/INTERFACE_OBSERVABILITY_SYSTEM.md Section 6
- docs/AGENT_MASTER_PLAN.md Section 6 & 10 (Step 18)
- Zero outbound network telemetry export (writes strictly to local newline-delimited JSON span logs).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Sequence

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExportResult, SpanExporter
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger("clipcrop.telemetry")


def format_trace_id(trace_id: int) -> str:
    """Format 128-bit trace ID integer as 32-character hexadecimal string."""
    return f"{trace_id:032x}"


def format_span_id(span_id: int) -> str:
    """Format 64-bit span ID integer as 16-character hexadecimal string."""
    return f"{span_id:016x}"


class JsonFileSpanExporter(SpanExporter):
    """Custom OpenTelemetry SpanExporter writing newline-delimited JSON spans to a local file.

    Guarantees 100% offline, zero-network trace persistence.
    """

    def __init__(self, file_path: Path | str) -> None:
        self.file_path = Path(file_path).resolve()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Serialize and append spans as newline-delimited JSON to disk."""
        try:
            with open(self.file_path, "a", encoding="utf-8") as f:
                for span in spans:
                    duration_sec = None
                    if span.start_time and span.end_time and span.end_time >= span.start_time:
                        duration_sec = (span.end_time - span.start_time) / 1_000_000_000.0

                    parent_id = (
                        format_span_id(span.parent.span_id)
                        if span.parent and span.parent.span_id
                        else None
                    )

                    record: dict[str, Any] = {
                        "name": span.name,
                        "trace_id": format_trace_id(span.context.trace_id),
                        "span_id": format_span_id(span.context.span_id),
                        "parent_id": parent_id,
                        "start_time_unix_nano": span.start_time,
                        "end_time_unix_nano": span.end_time,
                        "duration_seconds": duration_sec,
                        "status": {
                            "code": span.status.status_code.name,
                            "description": span.status.description,
                        },
                        "attributes": dict(span.attributes or {}),
                        "events": [
                            {
                                "name": event.name,
                                "timestamp_unix_nano": event.timestamp,
                                "attributes": dict(event.attributes or {}),
                            }
                            for event in (span.events or [])
                        ],
                    }
                    f.write(json.dumps(record, default=str) + "\n")
            return SpanExportResult.SUCCESS
        except Exception as e:
            logger.error("Failed to export OTel spans to %s: %s", self.file_path, e)
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        """Cleanly shutdown exporter."""
        pass


class PipelineTracer:
    """Manages hierarchical span lifecycle and domain attribute capture for a run session.

    Hierarchy:
    run (root span)
      └── stage spans (ingest_and_validate, transcribe_and_segment, ...)
            └── segment spans (per candidate segment)
                  └── tool call spans / attributes
    """

    def __init__(self, session_id: str, trace_file_path: Path | str) -> None:
        self.session_id = session_id
        self.trace_file_path = Path(trace_file_path).resolve()

        # Dedicated TracerProvider per run to avoid cross-session contamination
        self.provider = TracerProvider()
        self.exporter = JsonFileSpanExporter(self.trace_file_path)
        self.processor = SimpleSpanProcessor(self.exporter)
        self.provider.add_span_processor(self.processor)
        self.tracer = self.provider.get_tracer("clipcrop.pipeline", "0.1.0")

        self.root_span: trace.Span | None = None
        self._active_spans: dict[str, trace.Span] = {}

    def start_root_span(self, source_path: str | None = None) -> trace.Span:
        """Start root 'run' span representing the single-shot session."""
        span = self.tracer.start_span("run")
        span.set_attribute("clipcrop.session_id", self.session_id)
        if source_path:
            # File metadata only, never content, per Section 6
            filename = Path(source_path).name
            span.set_attribute("clipcrop.source.filename", filename)

        self.root_span = span
        self._active_spans["root"] = span
        return span

    def end_root_span(self, outcome: str = "success") -> None:
        """Close root span and flush all spans to disk."""
        if self.root_span:
            self.root_span.set_attribute("clipcrop.run.outcome", outcome)
            if outcome != "success":
                self.root_span.set_status(Status(StatusCode.ERROR, description=outcome))
            else:
                self.root_span.set_status(Status(StatusCode.OK))
            self.root_span.end()
            self.root_span = None

        self.provider.shutdown()

    def start_stage_span(self, stage_name: str) -> trace.Span:
        """Start a child span for a pipeline stage nested under the root run span."""
        parent_context = (
            trace.set_span_in_context(self.root_span) if self.root_span else None
        )
        span = self.tracer.start_span(
            f"stage:{stage_name}",
            context=parent_context,
        )
        span.set_attribute("clipcrop.stage.name", stage_name)
        span.set_attribute("clipcrop.session_id", self.session_id)
        self._active_spans[f"stage:{stage_name}"] = span
        return span

    def end_stage_span(
        self,
        stage_name: str,
        success: bool = True,
        error_message: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """End an active stage span, attaching final attributes and status."""
        key = f"stage:{stage_name}"
        span = self._active_spans.pop(key, None)
        if span:
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, v)
            if not success:
                span.set_status(Status(StatusCode.ERROR, description=error_message or "Stage failed"))
                if error_message:
                    span.set_attribute("error.type", error_message)
            else:
                span.set_status(Status(StatusCode.OK))
            span.end()

    def start_segment_span(self, segment_id: str, parent_stage_name: str | None = None) -> trace.Span:
        """Start a child span for a candidate segment fan-out execution."""
        parent_span = (
            self._active_spans.get(f"stage:{parent_stage_name}")
            if parent_stage_name
            else self.root_span
        )
        parent_context = (
            trace.set_span_in_context(parent_span) if parent_span else None
        )
        span = self.tracer.start_span(
            f"segment:{segment_id}",
            context=parent_context,
        )
        span.set_attribute("clipcrop.segment.id", segment_id)
        span.set_attribute("clipcrop.session_id", self.session_id)
        self._active_spans[f"segment:{segment_id}"] = span
        return span

    def end_segment_span(
        self,
        segment_id: str,
        success: bool = True,
        confidence: float | None = None,
        gate_decision: str | None = None,
        gate_threshold: float | None = None,
        error_message: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """End a candidate segment span with gate outcomes and metrics."""
        key = f"segment:{segment_id}"
        span = self._active_spans.pop(key, None)
        if span:
            if confidence is not None:
                span.set_attribute("clipcrop.segment.confidence", confidence)
            if gate_decision is not None:
                span.set_attribute("clipcrop.gate.decision", gate_decision)
            if gate_threshold is not None:
                span.set_attribute("clipcrop.gate.threshold", gate_threshold)
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, v)

            if not success:
                span.set_status(Status(StatusCode.ERROR, description=error_message or "Segment failed"))
                if error_message:
                    span.set_attribute("error.type", error_message)
            else:
                span.set_status(Status(StatusCode.OK))
            span.end()

    def record_tool_span(
        self,
        tool_name: str,
        stage_name: str,
        segment_id: str | None = None,
        success: bool = True,
        attributes: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        """Record an individual completed tool invocation span."""
        parent_key = f"segment:{segment_id}" if segment_id else f"stage:{stage_name}"
        parent_span = self._active_spans.get(parent_key) or self.root_span
        parent_context = (
            trace.set_span_in_context(parent_span) if parent_span else None
        )

        span = self.tracer.start_span(f"tool:{tool_name}", context=parent_context)
        span.set_attribute("clipcrop.tool.name", tool_name)
        span.set_attribute("clipcrop.stage.name", stage_name)
        if segment_id:
            span.set_attribute("clipcrop.segment.id", segment_id)
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, v)

        if not success:
            span.set_status(Status(StatusCode.ERROR, description=error_message or "Tool execution failed"))
            if error_message:
                span.set_attribute("error.type", error_message)
        else:
            span.set_status(Status(StatusCode.OK))

        span.end()
