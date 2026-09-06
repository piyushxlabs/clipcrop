"""Internal Structured Output: confidence_gate_decision.

Deterministically gates candidate segments based on speaker tracking confidence.
Strict binary comparison (render vs skip) — zero heuristic or LLM guessing.
"""

from __future__ import annotations

from src.config import RuntimeConfig
from src.state.schema import GateDecision


def confidence_gate_decision(
    segment_id: str,
    tracking_confidence: float,
    config: RuntimeConfig,
) -> GateDecision:
    """Evaluate tracking confidence against runtime threshold to make render-vs-skip decision."""
    threshold = config.confidence_threshold
    decision = "render" if tracking_confidence >= threshold else "skip"

    if decision == "render":
        reason = (
            f"Tracking confidence {tracking_confidence:.2f} meets or exceeds "
            f"threshold {threshold:.2f}."
        )
    else:
        reason = (
            f"Tracking confidence {tracking_confidence:.2f} below "
            f"threshold {threshold:.2f}."
        )

    return GateDecision(
        segment_id=segment_id,
        tracking_confidence=round(tracking_confidence, 3),
        threshold_used=threshold,
        decision=decision,
        reason=reason,
    )
