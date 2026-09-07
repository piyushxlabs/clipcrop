"""Feedback and interruption annotations for ClipCrop trace logs.

Adheres strictly to docs/INTERFACE_OBSERVABILITY_SYSTEM.md Section 7a:
- Captures per-clip thumbs up/down and notes as structured local annotations
- Appends annotations post-hoc to completed local trace logs in CLIPCROP_TRACE_LOG_DIR
- Zero external network calls or cloud services.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Literal

logger = logging.getLogger("clipcrop.telemetry")


def append_feedback_annotation(
    trace_file: Path | str,
    run_id: str,
    segment_id: str,
    rating: Literal["up", "down"],
    note: str | None = None,
) -> bool:
    """Append a structured feedback annotation line to the local run trace log.

    Args:
        trace_file: Filesystem path to the run's JSONL trace file.
        run_id: Unique run session identifier.
        segment_id: Candidate segment identifier (e.g. seg_01).
        rating: Binary satisfaction rating ('up' or 'down').
        note: Optional developer note describing what was off.

    Returns:
        True if successfully written, False otherwise.
    """
    path = Path(trace_file).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    annotation_record = {
        "type": "annotation",
        "annotation_type": "user_feedback",
        "timestamp_unix": time.time(),
        "run_id": run_id,
        "segment_id": segment_id,
        "attributes": {
            "clipcrop.feedback.rating": rating,
            "clipcrop.feedback.note": note,
        },
    }

    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(annotation_record, default=str) + "\n")
        logger.info(
            "Recorded user feedback for run %s segment %s: %s",
            run_id,
            segment_id,
            rating,
        )
        return True
    except Exception as e:
        logger.error("Failed to append feedback annotation to %s: %s", path, e)
        return False


def append_interruption_annotation(
    trace_file: Path | str,
    run_id: str,
    reason: str = "user_cancellation",
) -> bool:
    """Append an emergency stop / interruption marker to the local trace log."""
    path = Path(trace_file).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    interruption_record = {
        "type": "annotation",
        "annotation_type": "run_interrupted",
        "timestamp_unix": time.time(),
        "run_id": run_id,
        "attributes": {
            "clipcrop.run.outcome": "interrupted",
            "clipcrop.interruption.reason": reason,
        },
    }

    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(interruption_record, default=str) + "\n")
        return True
    except Exception as e:
        logger.error("Failed to append interruption annotation to %s: %s", path, e)
        return False
