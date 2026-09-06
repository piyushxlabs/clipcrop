"""ClipCrop typed state and reducers package.

Exports the authoritative StateSchema, domain sub-models, and reducer functions.
"""

from src.state.reducers import (
    FIELD_REDUCERS,
    append_only,
    apply_state_update,
    immutable_after_init,
    last_write_wins,
    merge_by_key,
    verify_export_precondition,
    verify_render_precondition,
)
from src.state.schema import (
    BoundingBox,
    CandidateSegment,
    CandidateSegmentScore,
    ConfidenceGateDecision,
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

__all__ = [
    "StateSchema",
    "FileRef",
    "TranscriptSegment",
    "SpeechSpan",
    "CandidateSegment",
    "CandidateSegmentScore",
    "BoundingBox",
    "FramePosition",
    "TrackingResult",
    "GateDecision",
    "ConfidenceGateDecision",
    "CropKeyframe",
    "SmoothedPath",
    "SkipRecord",
    "ErrorRecord",
    "immutable_after_init",
    "append_only",
    "merge_by_key",
    "last_write_wins",
    "apply_state_update",
    "verify_render_precondition",
    "verify_export_precondition",
    "FIELD_REDUCERS",
]
