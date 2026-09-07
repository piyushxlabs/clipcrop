"""ClipCrop Deterministic 8-Stage Pipeline Controller.

Implements the forward-only, confidence-gated pipeline state machine defined in:
- docs/AGENT_ORCHESTRATION_BLUEPRINT.md Section 4 & 10
- docs/AGENT_LOGIC_SPEC.md Section 2 & 6
- docs/AGENT_MASTER_PLAN.md Section 4 (Step 6) & Section 10 (Step 11)
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import contextlib
import enum
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from src.config import RuntimeConfig, load_config_from_env
from src.exceptions import ClipCropError, PermanentFailureError, StateValidationError
from src.telemetry.tracing import PipelineTracer
from src.ui.event_types import STAGE_LABELS
from src.ui.stream_handler import StreamHandler
from src.state.reducers import apply_state_update
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
from src.tools.candidate_scorer import score_candidate_segments
from src.tools.confidence_gate import confidence_gate_decision
from src.tools.decode_and_validate_source import decode_and_validate_source
from src.tools.detect_speech_pauses import detect_speech_pauses
from src.tools.export_crop_path_data import export_crop_path_data
from src.tools.render_vertical_clip import render_vertical_clip
from src.tools.schemas.decode_and_validate_source import DecodeAndValidateSourceInput
from src.tools.schemas.detect_speech_pauses import DetectSpeechPausesInput
from src.tools.schemas.export_crop_path_data import ExportCropPathDataInput
from src.tools.schemas.render_vertical_clip import RenderVerticalClipInput
from src.tools.schemas.smooth_crop_path import (
    CropKeyframeModel,
    SmoothCropPathInput,
)
from src.tools.schemas.track_speaker_position import (
    BoundingBoxModel,
    FramePositionModel,
    TrackSpeakerPositionInput,
)
from src.tools.schemas.transcribe_audio import TranscribeAudioInput
from src.tools.smooth_crop_path import smooth_crop_path
from src.tools.track_speaker_position import track_speaker_position
from src.tools.transcribe_audio import transcribe_audio


class PipelineStage(str, enum.Enum):
    """The eight sequential stages of the ClipCrop forward-only pipeline."""

    STAGE_1_INGEST_AND_VALIDATE = "ingest_and_validate"
    STAGE_2_TRANSCRIBE_AND_SEGMENT = "transcribe_and_segment"
    STAGE_3_SCORE_CANDIDATES = "score_candidates"
    STAGE_4_TRACK_SPEAKER_POSITION = "track_speaker_position"
    STAGE_5_CONFIDENCE_GATE = "confidence_gate"
    STAGE_6_SMOOTH_CROP_PATH = "smooth_crop_path"
    STAGE_7_RENDER_AND_EXPORT = "render_and_export"
    STAGE_8_AGGREGATE_AND_TERMINATE = "aggregate_and_terminate"


PIPELINE_STAGES_ORDER: tuple[PipelineStage, ...] = (
    PipelineStage.STAGE_1_INGEST_AND_VALIDATE,
    PipelineStage.STAGE_2_TRANSCRIBE_AND_SEGMENT,
    PipelineStage.STAGE_3_SCORE_CANDIDATES,
    PipelineStage.STAGE_4_TRACK_SPEAKER_POSITION,
    PipelineStage.STAGE_5_CONFIDENCE_GATE,
    PipelineStage.STAGE_6_SMOOTH_CROP_PATH,
    PipelineStage.STAGE_7_RENDER_AND_EXPORT,
    PipelineStage.STAGE_8_AGGREGATE_AND_TERMINATE,
)


class PipelineController:
    """Deterministic, forward-only pipeline controller for ClipCrop.

    Orchestrates the 8-stage execution flow with per-segment parallel fan-out
    and binary confidence gating. Ephemeral, in-process, single-shot execution.
    """

    def __init__(
        self,
        config: RuntimeConfig | None = None,
        source_video_path: Path | str | None = None,
        dry_run: bool = False,
        executor: concurrent.futures.Executor | None = None,
        session_id: str | None = None,
        stream_handler: StreamHandler | None = None,
    ) -> None:
        self.config = config or load_config_from_env()
        self.source_video_path = Path(source_video_path).resolve() if source_video_path else None
        self.dry_run = dry_run
        self.session_id = session_id or str(uuid.uuid4())
        self.state = StateSchema(session_id=self.session_id, config=self.config)
        self.start_time: float = 0.0
        self.cancelled: bool = False
        self._cancel_event = asyncio.Event()
        self.current_stage: PipelineStage | None = None
        self.executor = executor
        self._owns_executor = False
        self._final_result: dict[str, Any] | None = None
        self.stream_handler = stream_handler
        self.trace_file = self.config.trace_log_dir / f"{self.session_id}_trace.jsonl"
        self.tracer = PipelineTracer(self.session_id, self.trace_file)

    def cancel(self) -> None:
        """Signal the pipeline controller to cancel between stages or segments."""
        self.cancelled = True
        self._cancel_event.set()

    def _cleanup_in_flight_outputs(self) -> None:
        """Roll back and delete partially written output files on cancellation or failure."""
        if not self.config.output_dir.is_dir():
            return
        prefix = f"{self.session_id}_"
        for item in self.config.output_dir.iterdir():
            if item.is_file() and item.name.startswith(prefix):
                try:
                    item.unlink(missing_ok=True)
                except Exception:
                    pass

    def _check_cancellation(self) -> None:
        """Check if a cancellation signal has been received and clean up in-flight outputs."""
        if self.cancelled or self._cancel_event.is_set():
            self._cleanup_in_flight_outputs()
            raise PermanentFailureError("Pipeline execution was cancelled by user.")

    def _check_time_budget(self) -> bool:
        """Return True if elapsed time has reached or exceeded run-wide time budget."""
        if self.start_time > 0 and (time.monotonic() - self.start_time) >= self.config.time_budget_seconds:
            return True
        return False

    def _record_error(
        self,
        stage: str,
        message: str,
        details: dict[str, Any] | None = None,
        recoverable: bool = False,
    ) -> None:
        """Record an error or diagnostic record into StateSchema via append_only reducer."""
        rec = ErrorRecord(
            stage=stage,
            message=message,
            details=details or {},
            timestamp_ms=int((time.monotonic() - self.start_time) * 1000) if self.start_time > 0 else 0,
            recoverable=recoverable,
        )
        self.state = apply_state_update(self.state, "error_logs", rec)

    async def execute(self) -> dict[str, Any]:
        """Execute the pipeline from Stage 1 through Stage 8.

        Raises:
            ClipCropError: If input validation fails or a fatal condition is encountered.
        """
        # Strict input gate
        if self.source_video_path is None:
            raise ClipCropError(
                "No source video input provided for pipeline execution. "
                "A valid source_path is required."
            )

        if not self.source_video_path.is_file():
            raise ClipCropError(
                f"Source video file does not exist: {self.source_video_path}"
            )

        # Path sandboxing verification
        try:
            self.source_video_path.relative_to(self.config.upload_dir)
        except ValueError:
            # Allow dry-run or test paths if explicitly provided, else enforce sandboxing
            if not self.dry_run:
                # Check if path is in workspace/tests or explicitly allowed
                is_workspace = (
                    Path("tests").resolve() in self.source_video_path.parents
                    or Path(".").resolve() in self.source_video_path.parents
                )
                if not is_workspace:
                    raise ClipCropError(
                        f"Path security violation: {self.source_video_path} is outside {self.config.upload_dir}"
                    )

        if self.dry_run:
            return {
                "session_id": self.session_id,
                "status": "dry_run_success",
                "source_video_path": str(self.source_video_path),
                "stages": [s.value for s in PIPELINE_STAGES_ORDER],
                "config": self.config.model_dump(),
            }

        self.start_time = time.monotonic()

        # Initialize ProcessPoolExecutor for CPU-bound tracking if not provided
        if self.executor is None:
            try:
                max_w = min(4, os.cpu_count() or 1)
                self.executor = concurrent.futures.ProcessPoolExecutor(max_workers=max_w)
                self._owns_executor = True
            except Exception:
                self.executor = None
                self._owns_executor = False

        self.tracer.start_root_span(source_path=str(self.source_video_path))

        try:
            for stage in PIPELINE_STAGES_ORDER:
                self._check_cancellation()
                self.current_stage = stage
                if self.stream_handler is not None:
                    label = STAGE_LABELS.get(stage.value, stage.value)
                    await self.stream_handler.emit_stage_start(stage.value, label)

                self.tracer.start_stage_span(stage.value)
                try:
                    await self._execute_stage(stage)
                    self.tracer.end_stage_span(stage.value, success=True)
                except Exception as stage_exc:
                    self.tracer.end_stage_span(stage.value, success=False, error_message=str(stage_exc))
                    raise

                # Time budget circuit breaker check between stages
                if stage != PipelineStage.STAGE_8_AGGREGATE_AND_TERMINATE and self._check_time_budget():
                    msg = f"Time budget of {self.config.time_budget_seconds}s exhausted after stage '{stage.value}'."
                    self._record_error(stage.value, msg)
                    if self.stream_handler is not None:
                        await self.stream_handler.emit_error("time_budget_exhausted", msg, recoverable=False)
                    break

            if self.current_stage != PipelineStage.STAGE_8_AGGREGATE_AND_TERMINATE:
                if self.stream_handler is not None:
                    label = STAGE_LABELS.get(
                        PipelineStage.STAGE_8_AGGREGATE_AND_TERMINATE.value,
                        "Finalizing summary and deliverables",
                    )
                    await self.stream_handler.emit_stage_start(
                        PipelineStage.STAGE_8_AGGREGATE_AND_TERMINATE.value, label
                    )
                self.tracer.start_stage_span(PipelineStage.STAGE_8_AGGREGATE_AND_TERMINATE.value)
                try:
                    await self._execute_stage_8_aggregate_and_terminate()
                    self.tracer.end_stage_span(PipelineStage.STAGE_8_AGGREGATE_AND_TERMINATE.value, success=True)
                except Exception as s8_exc:
                    self.tracer.end_stage_span(PipelineStage.STAGE_8_AGGREGATE_AND_TERMINATE.value, success=False, error_message=str(s8_exc))
                    raise

            result = self._final_result or {"status": "completed"}
            rendered_count = len(self.state.rendered_clips)
            skipped_count = len(self.state.skipped_segments)
            reason = "success" if rendered_count > 0 else "no_deliverables"
            self.tracer.end_root_span(outcome=reason)

            if self.stream_handler is not None:
                await self.stream_handler.emit_run_end(
                    reason=reason,
                    deliverables_count=rendered_count,
                    skipped_count=skipped_count,
                )
            return result
        except PermanentFailureError as pfe:
            pfe_str = str(pfe).lower()
            outcome = "interrupted" if "cancelled" in pfe_str else "error"
            self.tracer.end_root_span(outcome=outcome)

            if self.stream_handler is not None:
                if "cancelled" in pfe_str:
                    code = "cancelled"
                    reason = "interrupted"
                elif "zero_candidates" in pfe_str:
                    code = "zero_candidates"
                    reason = "error"
                elif "ingest failed" in pfe_str or "invalid" in pfe_str or "missing required" in pfe_str:
                    code = "invalid_source"
                    reason = "error"
                else:
                    code = "pipeline_error"
                    reason = "error"
                await self.stream_handler.emit_error(code, str(pfe), recoverable=False)
                await self.stream_handler.emit_run_end(reason=reason)
            raise
        except Exception as exc:
            self.tracer.end_root_span(outcome="error")
            if self.stream_handler is not None:
                await self.stream_handler.emit_error("pipeline_error", str(exc), recoverable=False)
                await self.stream_handler.emit_run_end(reason="error")
            raise
        finally:
            if self._owns_executor and self.executor is not None:
                self.executor.shutdown(wait=False)
                self.executor = None
                self._owns_executor = False

    async def _execute_stage(self, stage: PipelineStage) -> None:
        """Dispatch stage execution in strict forward order."""
        if stage == PipelineStage.STAGE_1_INGEST_AND_VALIDATE:
            await self._execute_stage_1_ingest_and_validate()
        elif stage == PipelineStage.STAGE_2_TRANSCRIBE_AND_SEGMENT:
            await self._execute_stage_2_transcribe_and_segment()
        elif stage == PipelineStage.STAGE_3_SCORE_CANDIDATES:
            await self._execute_stage_3_score_candidates()
        elif stage == PipelineStage.STAGE_4_TRACK_SPEAKER_POSITION:
            await self._execute_stage_4_track_speaker_position()
        elif stage == PipelineStage.STAGE_5_CONFIDENCE_GATE:
            await self._execute_stage_5_confidence_gate()
        elif stage == PipelineStage.STAGE_6_SMOOTH_CROP_PATH:
            await self._execute_stage_6_smooth_crop_path()
        elif stage == PipelineStage.STAGE_7_RENDER_AND_EXPORT:
            await self._execute_stage_7_render_and_export()
        elif stage == PipelineStage.STAGE_8_AGGREGATE_AND_TERMINATE:
            await self._execute_stage_8_aggregate_and_terminate()

    async def _execute_stage_1_ingest_and_validate(self) -> None:
        """Stage 1: Ingest & Validate via decode_and_validate_source tool."""
        assert self.source_video_path is not None
        inp = DecodeAndValidateSourceInput(source_path=str(self.source_video_path))
        tool_call_id = f"call_ingest_{self.session_id[:8]}"

        if self.stream_handler is not None:
            await self.stream_handler.emit_tool_input(
                tool_call_id, "decode_and_validate_source", inp.model_dump()
            )

        out = await decode_and_validate_source(inp, self.config)

        self.tracer.record_tool_span(
            "decode_and_validate_source",
            stage_name=PipelineStage.STAGE_1_INGEST_AND_VALIDATE.value,
            success=out.success,
            attributes={
                "clipcrop.duration_seconds": out.duration_seconds,
                "clipcrop.width": out.width,
                "clipcrop.height": out.height,
                "clipcrop.fps": out.fps,
            },
            error_message=out.error,
        )

        if self.stream_handler is not None:
            await self.stream_handler.emit_tool_output(
                tool_call_id, "decode_and_validate_source", out.model_dump()
            )

        if not out.success:
            self._record_error(
                PipelineStage.STAGE_1_INGEST_AND_VALIDATE.value,
                out.error or "Media decode failed.",
            )
            raise PermanentFailureError(f"Stage 1 Ingest failed: {out.error}")

        if not out.has_video_track:
            msg = "Source video missing required video track."
            self._record_error(PipelineStage.STAGE_1_INGEST_AND_VALIDATE.value, msg)
            raise PermanentFailureError(msg)

        if not out.has_audio_track:
            msg = "Source video missing required audio track."
            self._record_error(PipelineStage.STAGE_1_INGEST_AND_VALIDATE.value, msg)
            raise PermanentFailureError(msg)

        file_size = (
            self.source_video_path.stat().st_size
            if self.source_video_path and self.source_video_path.exists()
            else None
        )
        file_ref = FileRef(
            path=str(self.source_video_path),
            duration_seconds=out.duration_seconds,
            width=out.width,
            height=out.height,
            fps=out.fps,
            has_video_track=out.has_video_track,
            has_audio_track=out.has_audio_track,
            file_size_bytes=file_size,
        )
        self.state = apply_state_update(self.state, "source_video", file_ref)
        if self.stream_handler is not None:
            await self.stream_handler.emit_state_update(
                "source_video", "immutable-after-init", file_ref.model_dump()
            )

    async def _execute_stage_2_transcribe_and_segment(self) -> None:
        """Stage 2: Transcribe & Segment concurrently via transcribe_audio and detect_speech_pauses."""
        assert self.state.source_video is not None
        src_path = self.state.source_video.path

        t_inp = TranscribeAudioInput(audio_source_path=src_path)
        v_inp = DetectSpeechPausesInput(audio_source_path=src_path)
        call_id_t = f"call_transcribe_{self.session_id[:8]}"
        call_id_v = f"call_vad_{self.session_id[:8]}"

        if self.stream_handler is not None:
            await self.stream_handler.emit_tool_input(call_id_t, "transcribe_audio", t_inp.model_dump())
            await self.stream_handler.emit_tool_input(call_id_v, "detect_speech_pauses", v_inp.model_dump())

        progress_cm = (
            self.stream_handler.track_progress(PipelineStage.STAGE_2_TRANSCRIBE_AND_SEGMENT.value, interval_seconds=1.0)
            if self.stream_handler is not None
            else contextlib.nullcontext()
        )
        async with progress_cm:
            t_res, v_res = await asyncio.gather(
                transcribe_audio(t_inp, self.config),
                detect_speech_pauses(v_inp, self.config),
            )

        if self.stream_handler is not None:
            await self.stream_handler.emit_tool_output(call_id_t, "transcribe_audio", t_res.model_dump())
            await self.stream_handler.emit_tool_output(call_id_v, "detect_speech_pauses", v_res.model_dump())

        self.tracer.record_tool_span(
            "transcribe_audio",
            stage_name=PipelineStage.STAGE_2_TRANSCRIBE_AND_SEGMENT.value,
            success=t_res.success,
            attributes={"clipcrop.transcript_segments_count": len(t_res.segments or [])},
            error_message=t_res.error,
        )
        self.tracer.record_tool_span(
            "detect_speech_pauses",
            stage_name=PipelineStage.STAGE_2_TRANSCRIBE_AND_SEGMENT.value,
            success=v_res.success,
            attributes={"clipcrop.speech_spans_count": len(v_res.speech_spans or [])},
            error_message=v_res.error,
        )

        t_segments = [
            TranscriptSegment(start_ms=s.start_ms, end_ms=s.end_ms, text=s.text)
            for s in (t_res.segments or [])
        ]
        v_spans = [
            SpeechSpan(start_seconds=s.start_seconds, end_seconds=s.end_seconds)
            for s in (v_res.speech_spans or [])
        ]

        self.state = apply_state_update(self.state, "transcript_segments", t_segments)
        self.state = apply_state_update(self.state, "vad_segments", v_spans)
        if self.stream_handler is not None:
            await self.stream_handler.emit_state_update(
                "transcript_segments", "append-only", [s.model_dump() for s in t_segments]
            )
            await self.stream_handler.emit_state_update(
                "vad_segments", "append-only", [s.model_dump() for s in v_spans]
            )

    async def _execute_stage_3_score_candidates(self) -> None:
        """Stage 3: Score Candidates via deterministic heuristic candidate_scorer."""
        candidates = score_candidate_segments(
            self.state.transcript_segments,
            self.state.vad_segments,
            self.config,
        )

        if not candidates:
            msg = "zero_candidates: No viable speech segments detected in source media."
            self._record_error(PipelineStage.STAGE_3_SCORE_CANDIDATES.value, msg)
            raise PermanentFailureError(msg)

        # Enforce hard cap CLIPCROP_MAX_CANDIDATES
        capped = candidates[: self.config.max_candidates]
        self.tracer.record_tool_span(
            "score_candidate_segments",
            stage_name=PipelineStage.STAGE_3_SCORE_CANDIDATES.value,
            success=True,
            attributes={"clipcrop.candidates_count": len(capped)},
        )
        self.state = apply_state_update(self.state, "candidate_segments", capped)
        if self.stream_handler is not None:
            await self.stream_handler.emit_state_update(
                "candidate_segments", "last-write-wins", [c.model_dump() for c in capped]
            )

    async def _execute_stage_4_track_speaker_position(self) -> None:
        model_asset = self.config.models_dir / "blaze_face_short_range.task"
        if not model_asset.exists():
            model_asset = self.config.models_dir / "blaze_face_short_range.tflite"

        if self.stream_handler is not None:
            for cand in self.state.candidate_segments:
                await self.stream_handler.emit_tool_input(
                    f"call_track_{cand.segment_id}",
                    "track_speaker_position",
                    {
                        "segment_id": cand.segment_id,
                        "segment_start_ms": cand.start_ms,
                        "segment_end_ms": cand.end_ms,
                    },
                )

        tasks = [
            track_speaker_position(
                TrackSpeakerPositionInput(
                    video_path=self.state.source_video.path,
                    segment_id=cand.segment_id,
                    segment_start_ms=cand.start_ms,
                    segment_end_ms=cand.end_ms,
                    model_asset_path=str(model_asset),
                ),
                self.config,
                executor=self.executor,
            )
            for cand in self.state.candidate_segments
        ]

        progress_cm = (
            self.stream_handler.track_progress(PipelineStage.STAGE_4_TRACK_SPEAKER_POSITION.value, interval_seconds=1.0)
            if self.stream_handler is not None
            else contextlib.nullcontext()
        )
        async with progress_cm:
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for cand, res in zip(self.state.candidate_segments, results):
            call_id = f"call_track_{cand.segment_id}"
            if isinstance(res, Exception) or not getattr(res, "success", False):
                err_msg = str(res) if isinstance(res, Exception) else (res.error or "Tracking failed.")
                tr = TrackingResult(
                    segment_id=cand.segment_id,
                    success=False,
                    error=err_msg,
                    segment_confidence=0.0,
                )
                self._record_error(
                    PipelineStage.STAGE_4_TRACK_SPEAKER_POSITION.value,
                    f"Tracking failed for {cand.segment_id}: {err_msg}",
                )
                if self.stream_handler is not None:
                    await self.stream_handler.emit_tool_output(
                        call_id, "track_speaker_position", {"success": False, "error": err_msg}
                    )
            else:
                positions = [
                    FramePosition(
                        timestamp_ms=p.timestamp_ms,
                        bounding_box=BoundingBox(
                            origin_x=p.bounding_box.origin_x,
                            origin_y=p.bounding_box.origin_y,
                            width=p.bounding_box.width,
                            height=p.bounding_box.height,
                        ),
                        detection_score=p.detection_score,
                    )
                    for p in res.per_frame_positions
                ]
                tr = TrackingResult(
                    segment_id=cand.segment_id,
                    success=True,
                    per_frame_positions=positions,
                    segment_confidence=res.segment_confidence,
                )
                if self.stream_handler is not None:
                    await self.stream_handler.emit_tool_output(
                        call_id, "track_speaker_position", res.model_dump()
                    )

            self.state = apply_state_update(self.state, "tracking_results", tr, key=cand.segment_id)
            self.tracer.record_tool_span(
                "track_speaker_position",
                stage_name=PipelineStage.STAGE_4_TRACK_SPEAKER_POSITION.value,
                segment_id=cand.segment_id,
                success=tr.success,
                attributes={
                    "clipcrop.segment.id": cand.segment_id,
                    "clipcrop.segment.confidence": tr.segment_confidence,
                    "clipcrop.frames_tracked": len(tr.per_frame_positions),
                },
                error_message=tr.error,
            )
            if self.stream_handler is not None:
                await self.stream_handler.emit_state_update(
                    "tracking_results", "merge-by-key", tr.model_dump(), key=cand.segment_id
                )

    async def _execute_stage_5_confidence_gate(self) -> None:
        """Stage 5: Confidence Gate evaluating render-vs-skip for each candidate segment."""
        for cand in self.state.candidate_segments:
            tr = self.state.tracking_results.get(cand.segment_id)
            conf = tr.segment_confidence if (tr and tr.success) else 0.0

            decision = confidence_gate_decision(cand.segment_id, conf, self.config)
            self.state = apply_state_update(
                self.state,
                "confidence_gate_results",
                decision,
                key=cand.segment_id,
            )
            self.tracer.record_tool_span(
                "confidence_gate_decision",
                stage_name=PipelineStage.STAGE_5_CONFIDENCE_GATE.value,
                segment_id=cand.segment_id,
                success=True,
                attributes={
                    "clipcrop.segment.id": cand.segment_id,
                    "clipcrop.segment.confidence": decision.tracking_confidence,
                    "clipcrop.gate.decision": decision.decision,
                    "clipcrop.gate.threshold": decision.threshold_used,
                },
            )
            if self.stream_handler is not None:
                await self.stream_handler.emit_state_update(
                    "confidence_gate_results", "merge-by-key", decision.model_dump(), key=cand.segment_id
                )

            if decision.decision == "skip":
                skip_rec = SkipRecord(
                    segment_id=cand.segment_id,
                    tracking_confidence=decision.tracking_confidence,
                    threshold_used=decision.threshold_used,
                    reason=decision.reason,
                    timestamp_ms=int((time.monotonic() - self.start_time) * 1000) if self.start_time > 0 else 0,
                )
                self.state = apply_state_update(self.state, "skipped_segments", skip_rec)
                if self.stream_handler is not None:
                    await self.stream_handler.emit_state_update(
                        "skipped_segments", "append-only", skip_rec.model_dump()
                    )

    async def _execute_stage_6_smooth_crop_path(self) -> None:
        """Stage 6: Smooth Crop Path generating 9:16 crop keyframes for render-approved segments."""
        assert self.state.source_video is not None

        for cand in self.state.candidate_segments:
            gate = self.state.confidence_gate_results.get(cand.segment_id)
            if not gate or gate.decision != "render":
                continue

            if self._check_time_budget():
                skip_rec = SkipRecord(
                    segment_id=cand.segment_id,
                    tracking_confidence=gate.tracking_confidence,
                    threshold_used=gate.threshold_used,
                    reason="time_budget_exhausted",
                    timestamp_ms=int((time.monotonic() - self.start_time) * 1000),
                )
                self.state = apply_state_update(self.state, "skipped_segments", skip_rec)
                continue

            tr = self.state.tracking_results[cand.segment_id]
            raw_pos = [
                FramePositionModel(
                    timestamp_ms=p.timestamp_ms,
                    bounding_box=BoundingBoxModel(
                        origin_x=p.bounding_box.origin_x,
                        origin_y=p.bounding_box.origin_y,
                        width=p.bounding_box.width,
                        height=p.bounding_box.height,
                    ),
                    detection_score=p.detection_score,
                )
                for p in tr.per_frame_positions
            ]

            smooth_in = SmoothCropPathInput(
                segment_id=cand.segment_id,
                raw_positions=raw_pos,
                source_width=self.state.source_video.width or 1280,
                source_height=self.state.source_video.height or 720,
            )
            res = smooth_crop_path(smooth_in, self.config)

            if self.stream_handler is not None:
                await self.stream_handler.emit_tool_input(
                    f"call_smooth_{cand.segment_id}",
                    "smooth_crop_path",
                    smooth_in.model_dump(),
                )
                await self.stream_handler.emit_tool_output(
                    f"call_smooth_{cand.segment_id}",
                    "smooth_crop_path",
                    res.model_dump(),
                )

            if res.success:
                kfs = [
                    CropKeyframe(
                        timestamp_ms=k.timestamp_ms,
                        x=k.x,
                        y=k.y,
                        width=k.width,
                        height=k.height,
                    )
                    for k in res.crop_keyframes
                ]
                sp = SmoothedPath(segment_id=cand.segment_id, success=True, crop_keyframes=kfs)
            else:
                sp = SmoothedPath(segment_id=cand.segment_id, success=False, error=res.error)

            self.state = apply_state_update(self.state, "crop_paths", sp, key=cand.segment_id)
            self.tracer.record_tool_span(
                "smooth_crop_path",
                stage_name=PipelineStage.STAGE_6_SMOOTH_CROP_PATH.value,
                segment_id=cand.segment_id,
                success=res.success,
                attributes={
                    "clipcrop.segment.id": cand.segment_id,
                    "clipcrop.keyframes_count": len(res.crop_keyframes or []),
                },
                error_message=res.error,
            )
            if self.stream_handler is not None:
                await self.stream_handler.emit_state_update(
                    "crop_paths", "merge-by-key", sp.model_dump(), key=cand.segment_id
                )

    async def _execute_stage_7_render_and_export(self) -> None:
        """Stage 7: Render 9:16 vertical clip and immediately export paired crop path data."""
        assert self.state.source_video is not None

        for cand in self.state.candidate_segments:
            self._check_cancellation()
            gate = self.state.confidence_gate_results.get(cand.segment_id)
            if not gate or gate.decision != "render":
                continue

            crop_path = self.state.crop_paths.get(cand.segment_id)
            if not crop_path or not crop_path.success:
                continue

            if self._check_time_budget():
                skip_rec = SkipRecord(
                    segment_id=cand.segment_id,
                    tracking_confidence=gate.tracking_confidence,
                    threshold_used=gate.threshold_used,
                    reason="time_budget_exhausted",
                    timestamp_ms=int((time.monotonic() - self.start_time) * 1000),
                )
                self.state = apply_state_update(self.state, "skipped_segments", skip_rec)
                if self.stream_handler is not None:
                    await self.stream_handler.emit_state_update(
                        "skipped_segments", "append-only", skip_rec.model_dump()
                    )
                continue

            out_clip_path = self.config.output_dir / f"{self.session_id}_{cand.segment_id}_vertical.mp4"
            kfs_model = [
                CropKeyframeModel(
                    timestamp_ms=k.timestamp_ms,
                    x=k.x,
                    y=k.y,
                    width=k.width,
                    height=k.height,
                )
                for k in crop_path.crop_keyframes
            ]

            render_in = RenderVerticalClipInput(
                segment_id=cand.segment_id,
                source_video_path=self.state.source_video.path,
                segment_start_ms=cand.start_ms,
                segment_end_ms=cand.end_ms,
                crop_keyframes=kfs_model,
                output_path=str(out_clip_path),
                crf=20,
                preset="fast",
            )

            call_id_render = f"call_render_{cand.segment_id}"
            if self.stream_handler is not None:
                await self.stream_handler.emit_tool_input(
                    call_id_render, "render_vertical_clip", render_in.model_dump()
                )

            render_out = await render_vertical_clip(render_in, self.config)

            self.tracer.record_tool_span(
                "render_vertical_clip",
                stage_name=PipelineStage.STAGE_7_RENDER_AND_EXPORT.value,
                segment_id=cand.segment_id,
                success=render_out.success,
                attributes={
                    "clipcrop.segment.id": cand.segment_id,
                    "clipcrop.output_file": Path(render_out.output_file_path).name if render_out.output_file_path else None,
                    "clipcrop.duration_seconds": render_out.duration_seconds,
                },
                error_message=render_out.error,
            )

            if self.stream_handler is not None:
                await self.stream_handler.emit_tool_output(
                    call_id_render, "render_vertical_clip", render_out.model_dump()
                )

            # Cancellation check after in-flight render call returns
            if self.cancelled or self._cancel_event.is_set():
                if out_clip_path.exists():
                    out_clip_path.unlink(missing_ok=True)
                self._check_cancellation()

            if render_out.success and render_out.output_file_path:
                clip_ref = FileRef(
                    path=render_out.output_file_path,
                    segment_id=cand.segment_id,
                    format="mp4",
                    duration_seconds=render_out.duration_seconds,
                    width=1080,
                    height=1920,
                    file_size_bytes=render_out.file_size_bytes,
                )
                self.state = apply_state_update(self.state, "rendered_clips", clip_ref)
                if self.stream_handler is not None:
                    await self.stream_handler.emit_state_update(
                        "rendered_clips", "append-only", clip_ref.model_dump()
                    )

                # Deliverable Contract: Immediately serialize crop path data for this segment
                out_edl_path = self.config.output_dir / f"{self.session_id}_{cand.segment_id}_crop_path.edl"
                export_in = ExportCropPathDataInput(
                    segment_id=cand.segment_id,
                    crop_keyframes=kfs_model,
                    output_path=str(out_edl_path),
                    format="edl",
                )

                call_id_export = f"call_export_{cand.segment_id}"
                if self.stream_handler is not None:
                    await self.stream_handler.emit_tool_input(
                        call_id_export, "export_crop_path_data", export_in.model_dump()
                    )

                export_out = export_crop_path_data(export_in, self.config)
                if asyncio.iscoroutine(export_out):
                    export_out = await export_out

                self.tracer.record_tool_span(
                    "export_crop_path_data",
                    stage_name=PipelineStage.STAGE_7_RENDER_AND_EXPORT.value,
                    segment_id=cand.segment_id,
                    success=export_out.success,
                    attributes={
                        "clipcrop.segment.id": cand.segment_id,
                        "clipcrop.output_file": Path(export_out.output_file_path).name if export_out.output_file_path else None,
                        "clipcrop.keyframe_count": export_out.keyframe_count,
                    },
                    error_message=export_out.error,
                )

                if self.stream_handler is not None:
                    await self.stream_handler.emit_tool_output(
                        call_id_export, "export_crop_path_data", export_out.model_dump()
                    )

                # Cancellation check after in-flight export call returns
                if self.cancelled or self._cancel_event.is_set():
                    if out_clip_path.exists():
                        out_clip_path.unlink(missing_ok=True)
                    if out_edl_path.exists():
                        out_edl_path.unlink(missing_ok=True)
                    self._check_cancellation()

                if export_out.success and export_out.output_file_path:
                    exp_ref = FileRef(
                        path=export_out.output_file_path,
                        segment_id=cand.segment_id,
                        format="edl",
                        keyframe_count=export_out.keyframe_count,
                    )
                    self.state = apply_state_update(self.state, "crop_path_exports", exp_ref)
                    if self.stream_handler is not None:
                        await self.stream_handler.emit_state_update(
                            "crop_path_exports", "append-only", exp_ref.model_dump()
                        )
                else:
                    if out_edl_path.exists():
                        out_edl_path.unlink(missing_ok=True)
                    self._record_error(
                        PipelineStage.STAGE_7_RENDER_AND_EXPORT.value,
                        f"Export failed for {cand.segment_id}: {export_out.error}",
                    )
            else:
                if out_clip_path.exists():
                    out_clip_path.unlink(missing_ok=True)
                self._record_error(
                    PipelineStage.STAGE_7_RENDER_AND_EXPORT.value,
                    f"Render failed for {cand.segment_id}: {render_out.error}",
                )

    async def _execute_stage_8_aggregate_and_terminate(self) -> dict[str, Any]:
        """Stage 8: Aggregate deliverables, skipped segments, and error records."""
        deliverables: list[dict[str, Any]] = []

        for clip in self.state.rendered_clips:
            matching_export = next(
                (e for e in self.state.crop_path_exports if e.segment_id == clip.segment_id),
                None,
            )
            deliverables.append({
                "segment_id": clip.segment_id,
                "clip_path": clip.path,
                "export_path": matching_export.path if matching_export else None,
                "duration_seconds": clip.duration_seconds,
            })

        self._final_result = {
            "session_id": self.session_id,
            "status": "completed" if deliverables else "no_deliverables",
            "rendered_count": len(self.state.rendered_clips),
            "skipped_count": len(self.state.skipped_segments),
            "deliverables": deliverables,
            "skipped_segments": [s.model_dump() for s in self.state.skipped_segments],
            "error_logs": [e.model_dump() for e in self.state.error_logs],
            "elapsed_seconds": round(time.monotonic() - self.start_time, 2) if self.start_time > 0 else 0.0,
        }
        return self._final_result


async def run_pipeline(
    source_video_path: Path | str | None = None,
    config: RuntimeConfig | None = None,
    dry_run: bool = False,
    executor: concurrent.futures.Executor | None = None,
) -> dict[str, Any]:
    """Helper entry point to execute the pipeline controller asynchronously."""
    controller = PipelineController(
        config=config,
        source_video_path=source_video_path,
        dry_run=dry_run,
        executor=executor,
    )
    return await controller.execute()


def main() -> None:
    """CLI entry point for pipeline controller invocation and dry-run validation."""
    parser = argparse.ArgumentParser(
        description="ClipCrop Deterministic Video Reframing Pipeline Controller",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default=None,
        help="Path to source video file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Execute dry-run validation of configuration and stages without rendering.",
    )

    args = parser.parse_args()

    try:
        result = asyncio.run(
            run_pipeline(
                source_video_path=args.input,
                dry_run=args.dry_run,
            )
        )
        print(f"Pipeline finished successfully: {result}")
    except ClipCropError as e:
        print(f"ClipCropError: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected fatal error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
