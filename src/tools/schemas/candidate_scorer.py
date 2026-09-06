"""Pydantic V2 and strict JSON Schema for candidate segment scoring."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class CandidateSegmentScore(BaseModel):
    """One ranked candidate clip-worthy span scored deterministically."""

    model_config = ConfigDict(strict=True)

    segment_id: str = Field(..., description="Generated identifier for this candidate segment.")
    start_ms: int = Field(..., ge=0, description="Candidate segment start offset in milliseconds.")
    end_ms: int = Field(..., ge=0, description="Candidate segment end offset in milliseconds.")
    score: float = Field(..., ge=0.0, description="Composite clip-worthiness score.")
    pause_pattern_score: float = Field(..., description="Component score from VAD pause-pattern analysis.")
    energy_peak_score: float = Field(..., description="Component score from audio-energy peak analysis.")
    speaking_rate_variance_score: float = Field(..., description="Component score from speaking-rate variance.")
    keyword_density_score: float = Field(..., description="Component score from transcript keyword/question-marker density.")
    rank: int = Field(..., ge=1, description="1-indexed rank among all returned candidates.")


CANDIDATE_SEGMENT_SCORE_SCHEMA: dict[str, Any] = {
    "name": "candidate_segment_score",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "segment_id": {"type": "string"},
            "start_ms": {"type": "integer", "minimum": 0},
            "end_ms": {"type": "integer", "minimum": 0},
            "score": {"type": "number", "minimum": 0.0},
            "pause_pattern_score": {"type": "number"},
            "energy_peak_score": {"type": "number"},
            "speaking_rate_variance_score": {"type": "number"},
            "keyword_density_score": {"type": "number"},
            "rank": {"type": "integer", "minimum": 1},
        },
        "required": [
            "segment_id",
            "start_ms",
            "end_ms",
            "score",
            "pause_pattern_score",
            "energy_peak_score",
            "speaking_rate_variance_score",
            "keyword_density_score",
            "rank",
        ],
        "additionalProperties": False,
    },
}
