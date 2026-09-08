"""Type-safe central state schema and supporting domain models for ClipCrop.

Strictly adheres to:
- docs/AGENT_ORCHESTRATION_BLUEPRINT.md Section 3
- docs/AGENT_LOGIC_SPEC.md Sections 1 & 3-5
- rules/state-invariants-and-tool-preconditions.md
- rules/async-io-and-pydantic-validation-mandate.md
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from src.config import RuntimeConfig
from src.exceptions import StateValidationError


class FileRef(BaseModel):
    """Media file reference with track and technical metadata."""

    model_config = ConfigDict(strict=True)

    path: str = Field(..., description="Local filesystem path to the file.")
    duration_seconds: float | None = Field(default=None, description="Media duration in seconds.")
    file_size_bytes: int | None = Field(default=None, description="File size in bytes.")
    width: int | None = Field(default=None, description="Frame width in pixels.")
    height: int | None = Field(default=None, description="Frame height in pixels.")
    fps: float | None = Field(default=None, description="Frame rate.")
    has_video_track: bool | None = Field(default=None, description="Whether video stream exists.")
    has_audio_track: bool | None = Field(default=None, description="Whether audio stream exists.")
    segment_id: str | None = Field(default=None, description="Associated candidate segment ID, if applicable.")
    keyframe_count: int | None = Field(default=None, description="Number of crop keyframes, if an export file.")
    format: str | None = Field(default=None, description="File format identifier (e.g. mp4, edl, xml, json).")


class TranscriptWord(BaseModel):
    """Word-level timing information."""

    model_config = ConfigDict(strict=True)

    word: str = Field(..., description="Individual word token.")
    start_ms: int = Field(..., ge=0, description="Word start offset in milliseconds.")
    end_ms: int = Field(..., ge=0, description="Word end offset in milliseconds.")
    probability: float | None = Field(default=None, description="Confidence probability of word.")


class TranscriptSegment(BaseModel):
    """Timestamped speech transcript segment."""

    model_config = ConfigDict(strict=True)

    start_ms: int = Field(..., ge=0, description="Segment start offset in milliseconds.")
    end_ms: int = Field(..., ge=0, description="Segment end offset in milliseconds.")
    text: str = Field(..., description="Transcribed text content.")
    words: list[TranscriptWord] = Field(default_factory=list, description="Word-level timestamps.")



class SpeechSpan(BaseModel):
    """Voice activity detection speech span."""

    model_config = ConfigDict(strict=True)

    start_seconds: float = Field(..., ge=0.0, description="Speech span start time in seconds.")
    end_seconds: float = Field(..., ge=0.0, description="Speech span end time in seconds.")


class CandidateSegment(BaseModel):
    """Ranked candidate clip-worthy span scored across audio and text heuristics."""

    model_config = ConfigDict(strict=True)

    segment_id: str = Field(..., description="Deterministic segment identifier (e.g. seg_01).")
    start_ms: int = Field(..., ge=0, description="Start offset in milliseconds.")
    end_ms: int = Field(..., ge=0, description="End offset in milliseconds.")
    score: float = Field(..., ge=0.0, description="Composite clip-worthiness score.")
    pause_pattern_score: float = Field(..., description="VAD pause pattern score component.")
    energy_peak_score: float = Field(..., description="Audio energy peak score component.")
    speaking_rate_variance_score: float = Field(..., description="Speaking rate variance component.")
    keyword_density_score: float = Field(..., description="Transcript keyword/question density component.")
    rank: int = Field(..., ge=1, description="1-indexed rank among returned candidates.")


# Alias CandidateSegmentScore to CandidateSegment for spec alignment
CandidateSegmentScore = CandidateSegment


class BoundingBox(BaseModel):
    """Spatial bounding box in image pixel coordinates."""

    model_config = ConfigDict(strict=True)

    origin_x: int = Field(..., description="Top-left origin x coordinate in pixels.")
    origin_y: int = Field(..., description="Top-left origin y coordinate in pixels.")
    width: int = Field(..., ge=0, description="Box width in pixels.")
    height: int = Field(..., ge=0, description="Box height in pixels.")


class FramePosition(BaseModel):
    """Timestamped face/speaker bounding box detection for a single frame."""

    model_config = ConfigDict(strict=True)

    timestamp_ms: int = Field(..., ge=0, description="Frame offset in milliseconds.")
    bounding_box: BoundingBox = Field(..., description="Detected speaker bounding box.")
    detection_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score for this frame detection.")


class TrackingResult(BaseModel):
    """Per-segment speaker position tracking output."""

    model_config = ConfigDict(strict=True)

    segment_id: str = Field(..., description="Candidate segment ID.")
    success: bool = Field(..., description="Whether tracking completed.")
    per_frame_positions: list[FramePosition] = Field(
        default_factory=list, description="Chronological per-frame detections."
    )
    segment_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Aggregate confidence score for the segment."
    )
    error: str | None = Field(default=None, description="Error message if tracking failed.")


class GateDecision(BaseModel):
    """Confidence gate render-vs-skip decision for a candidate segment."""

    model_config = ConfigDict(strict=True)

    segment_id: str = Field(..., description="Candidate segment ID.")
    tracking_confidence: float = Field(..., ge=0.0, le=1.0, description="Tracking confidence evaluated.")
    threshold_used: float = Field(..., ge=0.0, le=1.0, description="Runtime confidence threshold applied.")
    decision: Literal["render", "skip"] = Field(..., description="Deterministic routing decision.")
    reason: str = Field(..., description="Human-readable explanation of gate outcome.")


# Alias ConfidenceGateDecision to GateDecision for spec alignment
ConfidenceGateDecision = GateDecision


class CropKeyframe(BaseModel):
    """Smoothed 9:16 crop window keyframe."""

    model_config = ConfigDict(strict=True)

    timestamp_ms: int = Field(..., ge=0, description="Keyframe timestamp in milliseconds.")
    x: int = Field(..., description="Crop window top-left x in pixels.")
    y: int = Field(..., description="Crop window top-left y in pixels.")
    width: int = Field(..., ge=0, description="Crop width in pixels.")
    height: int = Field(..., ge=0, description="Crop height in pixels.")


class SmoothedPath(BaseModel):
    """Smoothed camera crop trajectory for a candidate segment."""

    model_config = ConfigDict(strict=True)

    segment_id: str = Field(..., description="Candidate segment ID.")
    success: bool = Field(..., description="Whether smoothing completed successfully.")
    crop_keyframes: list[CropKeyframe] = Field(
        default_factory=list, description="Smoothed crop keyframes."
    )
    error: str | None = Field(default=None, description="Error message if smoothing failed.")


class SkipRecord(BaseModel):
    """Audit record for a candidate segment rejected by the confidence gate."""

    model_config = ConfigDict(strict=True)

    segment_id: str = Field(..., description="Rejected candidate segment ID.")
    tracking_confidence: float = Field(..., ge=0.0, le=1.0, description="Evaluated tracking confidence.")
    threshold_used: float = Field(..., ge=0.0, le=1.0, description="Applied threshold.")
    reason: str = Field(..., description="Documented reason for skipping.")
    timestamp_ms: int | None = Field(default=None, description="Wall clock or pipeline timestamp offset.")


class ErrorRecord(BaseModel):
    """Pipeline error or failure diagnostic record."""

    model_config = ConfigDict(strict=True)

    stage: str = Field(..., description="Pipeline stage where the failure was detected.")
    message: str = Field(..., description="Error message describing the failure.")
    details: dict[str, Any] = Field(default_factory=dict, description="Diagnostic context dictionary.")
    timestamp_ms: int | None = Field(default=None, description="Timestamp offset when failure occurred.")
    recoverable: bool = Field(default=False, description="Whether the error was transient and retried.")


class StateSchema(BaseModel):
    """Central typed in-process state machine schema.

    Contains exactly the 13 locked state fields defined in AGENT_ORCHESTRATION_BLUEPRINT.md Section 3.
    Direct attribute assignment is structurally prohibited; all state mutations must route
    through reducer functions in `src.state.reducers`.
    """

    model_config = ConfigDict(strict=True)

    _initialized: bool = PrivateAttr(default=False)

    # 13 Locked State Fields
    session_id: str = Field(..., description="Unique run identifier (immutable after init).")
    source_video: FileRef | None = Field(default=None, description="Read-only handle to source media.")
    transcript_segments: list[TranscriptSegment] = Field(
        default_factory=list, description="Timestamped transcript segments (append-only)."
    )
    vad_segments: list[SpeechSpan] = Field(
        default_factory=list, description="Acoustic speech/pause spans (append-only)."
    )
    candidate_segments: list[CandidateSegment] = Field(
        default_factory=list, description="Ranked candidate clip spans (last-write-wins, capped at 10)."
    )
    tracking_results: dict[str, TrackingResult] = Field(
        default_factory=dict, description="Per-segment speaker position tracking (merge-by-key)."
    )
    confidence_gate_results: dict[str, GateDecision] = Field(
        default_factory=dict, description="Per-segment confidence gate outcomes (merge-by-key)."
    )
    crop_paths: dict[str, SmoothedPath] = Field(
        default_factory=dict, description="Per-segment smoothed crop paths (merge-by-key)."
    )
    rendered_clips: list[FileRef] = Field(
        default_factory=list, description="Delivered 9:16 vertical clip file references (append-only)."
    )
    crop_path_exports: list[FileRef] = Field(
        default_factory=list, description="Delivered NLE crop-path export files (append-only)."
    )
    skipped_segments: list[SkipRecord] = Field(
        default_factory=list, description="Audit log of low-confidence skipped segments (append-only)."
    )
    error_logs: list[ErrorRecord] = Field(
        default_factory=list, description="Audit log of pipeline errors and warnings (append-only)."
    )
    config: RuntimeConfig = Field(..., description="Locked runtime configuration (immutable after init).")

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._initialized = True

    def __setattr__(self, name: str, value: Any) -> None:
        """Enforce zero direct state mutation on StateSchema.

        Raises StateValidationError on any direct field assignment after initialization.
        State mutations must route strictly through `src.state.reducers.apply_state_update`.
        """
        if getattr(self, "_initialized", False) and not name.startswith("_"):
            raise StateValidationError(
                f"Direct assignment to field '{name}' on StateSchema is prohibited. "
                "All state mutations must route through reducer functions in src.state.reducers."
            )
        super().__setattr__(name, value)

    def _update_from_reducer(self, field_name: str, new_value: Any) -> None:
        """Internal updater used exclusively by reducer functions in src.state.reducers."""
        if field_name not in type(self).model_fields:
            raise StateValidationError(f"Cannot update non-existent state field '{field_name}'.")
        object.__setattr__(self, field_name, new_value)
