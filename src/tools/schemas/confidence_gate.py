"""Pydantic V2 and strict JSON Schema for confidence_gate_decision structured output."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ConfidenceGateDecision(BaseModel):
    """Render-vs-skip decision for one segment based on tracking confidence."""

    model_config = ConfigDict(strict=True)

    segment_id: str = Field(..., description="Identifier of the segment being gated.")
    tracking_confidence: float = Field(..., ge=0.0, le=1.0, description="segment_confidence from track_speaker_position.")
    threshold_used: float = Field(..., ge=0.0, le=1.0, description="config.confidence_threshold value applied.")
    decision: Literal["render", "skip"] = Field(..., description="render if tracking_confidence >= threshold_used, else skip.")
    reason: str = Field(..., description="Human-readable justification.")


CONFIDENCE_GATE_DECISION_SCHEMA: dict[str, Any] = {
    "name": "confidence_gate_decision",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "segment_id": {"type": "string"},
            "tracking_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "threshold_used": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "decision": {"type": "string", "enum": ["render", "skip"]},
            "reason": {"type": "string"},
        },
        "required": [
            "segment_id",
            "tracking_confidence",
            "threshold_used",
            "decision",
            "reason",
        ],
        "additionalProperties": False,
    },
}
