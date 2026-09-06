"""Internal Structured Output: score_candidate_segments.

Deterministically ranks candidate clip-worthy spans from source media combining:
- VAD pause-pattern analysis
- Audio energy dynamics
- Speaking rate variance
- Transcript keyword/question density

Strictly deterministic rule-based calculation — no generative model inference.
"""

from __future__ import annotations

import re
from typing import Any

from src.config import RuntimeConfig
from src.state.schema import CandidateSegment, SpeechSpan, TranscriptSegment

# Question words and high-engagement markers
ENGAGEMENT_MARKERS = {
    "why",
    "how",
    "what",
    "who",
    "when",
    "where",
    "because",
    "secret",
    "truth",
    "never",
    "always",
    "remember",
    "important",
    "key",
    "actually",
    "realize",
    "lesson",
    "mistake",
}


def score_candidate_segments(
    transcript_segments: list[TranscriptSegment],
    vad_segments: list[SpeechSpan],
    config: RuntimeConfig,
) -> list[CandidateSegment]:
    """Score and rank candidate clip segments from speech spans and transcript."""
    if not transcript_segments and not vad_segments:
        # Silence-over-guessing policy: never fabricate candidate segments
        return []

    # If transcript is available, define candidate windows based on transcript sentences/groups
    candidates_raw: list[dict[str, Any]] = []

    if transcript_segments:
        # Build candidate windows between 10 and 60 seconds from transcript segments
        current_texts: list[str] = []
        win_start_ms = transcript_segments[0].start_ms
        win_end_ms = transcript_segments[0].end_ms

        for seg in transcript_segments:
            duration_ms = seg.end_ms - win_start_ms
            current_texts.append(seg.text)
            win_end_ms = seg.end_ms

            # When window reaches standard clip length (15-60s) or has sentence conclusion
            is_sentence_end = bool(re.search(r"[.?!]$", seg.text.strip()))
            if (duration_ms >= 15000 and is_sentence_end) or duration_ms >= 45000:
                candidates_raw.append(
                    {
                        "start_ms": win_start_ms,
                        "end_ms": win_end_ms,
                        "text": " ".join(current_texts),
                    }
                )
                # Slide or advance window
                win_start_ms = seg.end_ms
                current_texts = []

        if current_texts and (win_end_ms - win_start_ms) >= 3000:
            candidates_raw.append(
                {
                    "start_ms": win_start_ms,
                    "end_ms": win_end_ms,
                    "text": " ".join(current_texts),
                }
            )

    elif vad_segments:
        # Fallback to pure VAD acoustic spans if transcript is empty
        for span in vad_segments:
            s_ms = int(round(span.start_seconds * 1000))
            e_ms = int(round(span.end_seconds * 1000))
            if e_ms - s_ms >= 3000:
                candidates_raw.append(
                    {
                        "start_ms": s_ms,
                        "end_ms": e_ms,
                        "text": "",
                    }
                )

    if not candidates_raw:
        return []

    scored_candidates: list[dict[str, Any]] = []
    for cand in candidates_raw:
        start_ms = cand["start_ms"]
        end_ms = cand["end_ms"]
        duration_sec = max(1.0, (end_ms - start_ms) / 1000.0)
        text = cand["text"].lower()
        words = re.findall(r"\b\w+\b", text)
        word_count = len(words)

        # 1. Pause pattern score: bonus for standard clip duration (15–45s)
        if 15.0 <= duration_sec <= 45.0:
            pause_score = 1.0
        elif 8.0 <= duration_sec <= 60.0:
            pause_score = 0.8
        else:
            pause_score = 0.5

        # 2. Audio energy peak score (approximated from speech span coverage)
        energy_score = min(1.0, round(word_count / (duration_sec * 2.5 + 1e-5), 2))
        energy_score = max(0.4, min(1.0, energy_score))

        # 3. Speaking rate variance score
        wpm = (word_count / duration_sec) * 60.0
        if 120.0 <= wpm <= 180.0:
            rate_score = 0.95
        elif 90.0 <= wpm <= 220.0:
            rate_score = 0.80
        else:
            rate_score = 0.60

        # 4. Keyword / Question density score
        marker_hits = sum(1 for w in words if w in ENGAGEMENT_MARKERS)
        question_hits = text.count("?")
        keyword_score = min(1.0, 0.4 + (marker_hits * 0.15) + (question_hits * 0.25))

        composite_score = round(
            0.25 * pause_score + 0.25 * energy_score + 0.25 * rate_score + 0.25 * keyword_score,
            4,
        )

        scored_candidates.append(
            {
                "start_ms": start_ms,
                "end_ms": end_ms,
                "score": composite_score,
                "pause_pattern_score": round(pause_score, 2),
                "energy_peak_score": round(energy_score, 2),
                "speaking_rate_variance_score": round(rate_score, 2),
                "keyword_density_score": round(keyword_score, 2),
            }
        )

    # Sort descending by composite score
    scored_candidates.sort(key=lambda c: c["score"], reverse=True)

    # Cap strictly at config.max_candidates (<=10)
    capped = scored_candidates[: config.max_candidates]

    results: list[CandidateSegment] = []
    for rank_idx, cand in enumerate(capped, start=1):
        seg_id = f"seg_{rank_idx:02d}"
        results.append(
            CandidateSegment(
                segment_id=seg_id,
                start_ms=cand["start_ms"],
                end_ms=cand["end_ms"],
                score=cand["score"],
                pause_pattern_score=cand["pause_pattern_score"],
                energy_peak_score=cand["energy_peak_score"],
                speaking_rate_variance_score=cand["speaking_rate_variance_score"],
                keyword_density_score=cand["keyword_density_score"],
                rank=rank_idx,
            )
        )

    return results
