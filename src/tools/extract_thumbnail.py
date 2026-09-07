"""Cover Thumbnail Extractor Tool.

Extracts a single high-quality frame from the rendered vertical MP4 at the point
of peak speaker detection confidence during active speech.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from src.tools.subprocess_runner import run_async_subprocess


async def extract_thumbnail(
    vertical_mp4_path: str | Path,
    output_thumbnail_path: str | Path,
    per_frame_positions: Sequence[Any] | None,
    vad_spans: Sequence[Any] | None,
    segment_start_ms: int,
    segment_end_ms: int,
) -> str | None:
    """Extract optimal peak frame thumbnail from rendered vertical video.

    Returns:
        String path to output thumbnail if successful, or None.
    """
    try:
        mp4_path = Path(vertical_mp4_path).resolve()
        if not mp4_path.exists():
            return None

        out_path = Path(output_thumbnail_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        dur_ms = segment_end_ms - segment_start_ms
        best_rel_sec = (dur_ms / 2000.0) if dur_ms > 0 else 0.0

        # Build list of active speech intervals in segment-relative ms
        speech_intervals: list[tuple[int, int]] = []
        if vad_spans:
            for s in vad_spans:
                s_start_ms = int(getattr(s, "start_seconds", 0.0) * 1000)
                s_end_ms = int(getattr(s, "end_seconds", 0.0) * 1000)
                if s_end_ms > segment_start_ms and s_start_ms < segment_end_ms:
                    r_start = max(0, s_start_ms - segment_start_ms)
                    r_end = min(dur_ms, s_end_ms - segment_start_ms)
                    if r_end > r_start:
                        speech_intervals.append((r_start, r_end))

        scored_candidates: list[tuple[float, int]] = []
        half_dur = dur_ms / 2.0

        if per_frame_positions:
            for p in per_frame_positions:
                pos_ts = getattr(p, "timestamp_ms", 0)
                rel_ms = pos_ts - segment_start_ms
                if 0 <= rel_ms <= dur_ms:
                    score = float(getattr(p, "detection_score", 0.5))

                    # Boost frames occurring during active speech
                    in_speech = any(st <= rel_ms <= en for st, en in speech_intervals)
                    speech_boost = 1.3 if in_speech else 0.8

                    # Slight center proximity bias
                    center_factor = 1.0 - 0.3 * (abs(rel_ms - half_dur) / max(1.0, half_dur))
                    final_score = score * speech_boost * center_factor
                    scored_candidates.append((final_score, rel_ms))

        if scored_candidates:
            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            best_rel_ms = scored_candidates[0][1]
            best_rel_sec = max(0.0, min(best_rel_ms / 1000.0, max(0.0, (dur_ms - 50) / 1000.0)))

        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{best_rel_sec:.3f}",
            "-i",
            str(mp4_path),
            "-vframes",
            "1",
            "-q:v",
            "2",
            str(out_path),
        ]

        returncode, _, _ = await run_async_subprocess(cmd)
        if returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
            return str(out_path)

        return None
    except Exception:
        return None
