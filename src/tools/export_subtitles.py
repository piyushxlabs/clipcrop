"""Subtitle Exporter Tool.

Generates standard SubRip (.srt) subtitles and styled Hormozi-style (.ass)
dynamic word-highlighted subtitles for candidate video segments.
Zero external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


def ms_to_srt_timecode(ms: int) -> str:
    """Format millisecond offset into standard SRT timecode: HH:MM:SS,mmm."""
    clamped_ms = max(0, ms)
    total_sec = clamped_ms // 1000
    mmm = clamped_ms % 1000
    ss = total_sec % 60
    mm = (total_sec // 60) % 60
    hh = total_sec // 3600
    return f"{hh:02d}:{mm:02d}:{ss:02d},{mmm:03d}"


def ms_to_ass_timecode(ms: int) -> str:
    """Format millisecond offset into standard ASS timecode: H:MM:SS.cs."""
    clamped_ms = max(0, ms)
    total_sec = clamped_ms // 1000
    cs = (clamped_ms % 1000) // 10
    ss = total_sec % 60
    mm = (total_sec // 60) % 60
    hh = total_sec // 3600
    return f"{hh}:{mm:02d}:{ss:02d}.{cs:02d}"


@dataclass
class TimedWord:
    """Word with relative millisecond timestamps."""
    word: str
    start_ms: int
    end_ms: int


def _extract_timed_words(
    segment_start_ms: int,
    segment_end_ms: int,
    transcript_segments: list[Any],
    speech_spans: list[Any] | None = None,
) -> list[TimedWord]:
    """Extract word-level relative timing from overlapping transcript segments."""
    timed_words: list[TimedWord] = []

    for seg in transcript_segments:
        start_ms = getattr(seg, "start_ms", 0)
        end_ms = getattr(seg, "end_ms", 0)
        text = getattr(seg, "text", "").strip()

        # If speech ends before segment starts or starts after segment ends, skip
        if not text or end_ms <= segment_start_ms or start_ms >= segment_end_ms:
            continue

        raw_words_objs = getattr(seg, "words", None)
        if raw_words_objs:
            # 1. Native word timestamps from Faster-Whisper
            for w in raw_words_objs:
                w_text = (getattr(w, "word", "") if not isinstance(w, dict) else w.get("word", "")).strip().upper()
                if not w_text:
                    continue
                w_abs_start = getattr(w, "start_ms", 0) if not isinstance(w, dict) else w.get("start_ms", 0)
                w_abs_end = getattr(w, "end_ms", 0) if not isinstance(w, dict) else w.get("end_ms", 0)

                # Drop words that finish before the candidate segment starts
                # or start after the candidate segment finishes
                if w_abs_end <= segment_start_ms or w_abs_start >= segment_end_ms:
                    continue

                rel_start = max(0, w_abs_start - segment_start_ms)
                rel_end = max(rel_start + 50, min(segment_end_ms - segment_start_ms, w_abs_end - segment_start_ms))

                if rel_end <= rel_start:
                    continue

                timed_words.append(TimedWord(word=w_text, start_ms=rel_start, end_ms=rel_end))
        else:
            # 2. Fallback when word timestamps are absent, with VAD speech onset clamping
            raw_words = text.split()
            if not raw_words:
                continue

            effective_start_ms = start_ms
            if speech_spans:
                overlapping_vad_starts = [
                    int(round(getattr(span, "start_seconds", 0) * 1000))
                    for span in speech_spans
                    if getattr(span, "end_seconds", 0) * 1000 > start_ms
                    and getattr(span, "start_seconds", 0) * 1000 < end_ms
                ]
                if overlapping_vad_starts:
                    earliest_vad = min(overlapping_vad_starts)
                    if earliest_vad > effective_start_ms:
                        effective_start_ms = earliest_vad

            seg_dur = max(1, end_ms - effective_start_ms)
            n = len(raw_words)

            for i, w in enumerate(raw_words):
                clean_word = w.strip().upper()
                if not clean_word:
                    continue

                # Absolute start and end of this word in source video space
                abs_w_start = effective_start_ms + int(i * seg_dur / n)
                abs_w_end = effective_start_ms + int((i + 1) * seg_dur / n)

                # Drop words that finish before the candidate segment starts
                # or start after the candidate segment finishes
                if abs_w_end <= segment_start_ms or abs_w_start >= segment_end_ms:
                    continue

                # Shift word timestamps by subtracting segment_start_ms
                # Clamp any resulting negative timestamps to 0
                rel_start = max(0, abs_w_start - segment_start_ms)
                rel_end = max(rel_start + 50, min(segment_end_ms - segment_start_ms, abs_w_end - segment_start_ms))

                if rel_end <= rel_start:
                    continue

                timed_words.append(TimedWord(word=clean_word, start_ms=rel_start, end_ms=rel_end))

    return timed_words


def generate_srt_content(
    segment_start_ms: int,
    segment_end_ms: int,
    transcript_segments: list[Any],
    speech_spans: list[Any] | None = None,
) -> str:
    """Convert transcript segments overlapping the candidate window into relative SRT content."""
    lines: list[str] = []
    srt_idx = 1

    for seg in transcript_segments:
        start_ms = getattr(seg, "start_ms", 0)
        end_ms = getattr(seg, "end_ms", 0)
        text = getattr(seg, "text", "").strip()

        if not text or end_ms <= segment_start_ms or start_ms >= segment_end_ms:
            continue

        words = getattr(seg, "words", None)
        if words:
            seg_word_starts = [
                getattr(w, "start_ms", 0) if not isinstance(w, dict) else w.get("start_ms", 0)
                for w in words
            ]
            seg_word_ends = [
                getattr(w, "end_ms", 0) if not isinstance(w, dict) else w.get("end_ms", 0)
                for w in words
            ]
            effective_start_ms = min(seg_word_starts) if seg_word_starts else start_ms
            effective_end_ms = max(seg_word_ends) if seg_word_ends else end_ms
        else:
            effective_start_ms = start_ms
            effective_end_ms = end_ms
            if speech_spans:
                overlapping_vad_starts = [
                    int(round(getattr(span, "start_seconds", 0) * 1000))
                    for span in speech_spans
                    if getattr(span, "end_seconds", 0) * 1000 > start_ms
                    and getattr(span, "start_seconds", 0) * 1000 < end_ms
                ]
                if overlapping_vad_starts:
                    earliest_vad = min(overlapping_vad_starts)
                    if earliest_vad > effective_start_ms:
                        effective_start_ms = earliest_vad

        # Shift timestamps by subtracting segment_start_ms
        # Clamp any resulting negative timestamps to 0
        rel_start = max(0, effective_start_ms - segment_start_ms)
        rel_end = min(segment_end_ms - segment_start_ms, effective_end_ms - segment_start_ms)
        if rel_end <= rel_start:
            continue

        start_tc = ms_to_srt_timecode(rel_start)
        end_tc = ms_to_srt_timecode(rel_end)

        lines.append(f"{srt_idx}")
        lines.append(f"{start_tc} --> {end_tc}")
        lines.append(text)
        lines.append("")
        srt_idx += 1

    return "\n".join(lines)


def generate_ass_content(
    segment_start_ms: int,
    segment_end_ms: int,
    transcript_segments: list[Any],
    words_per_chunk: int = 4,
    speech_spans: list[Any] | None = None,
) -> str:
    """Generate Hormozi-style kinetic ASS subtitles with active-word yellow highlight."""
    timed_words = _extract_timed_words(
        segment_start_ms,
        segment_end_ms,
        transcript_segments,
        speech_spans=speech_spans,
    )

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Arial,54,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,4,2,2,40,40,240,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    if not timed_words:
        return header

    dialogue_lines: list[str] = []
    total_words = len(timed_words)

    for i in range(0, total_words, words_per_chunk):
        chunk = timed_words[i : i + words_per_chunk]
        if not chunk:
            continue

        for active_idx, target_word in enumerate(chunk):
            start_tc = ms_to_ass_timecode(target_word.start_ms)
            end_tc = ms_to_ass_timecode(target_word.end_ms)

            # Build chunk display with active word highlighted in vibrant yellow
            chunk_display: list[str] = []
            for idx, w in enumerate(chunk):
                if idx == active_idx:
                    chunk_display.append(f"{{\\c&H0000FFFF&}}{w.word}{{\\c&H00FFFFFF&}}")
                else:
                    chunk_display.append(w.word)

            text_line = " ".join(chunk_display)
            dialogue_lines.append(
                f"Dialogue: 0,{start_tc},{end_tc},Default,,0,0,0,,{text_line}"
            )

    return header + "\n".join(dialogue_lines) + "\n"


def export_subtitles(
    segment_start_ms: int | list[Any] = 0,
    segment_end_ms: int | str | Path | None = None,
    transcript_segments: list[Any] | None = None,
    output_path: str | Path | None = None,
    speech_spans: list[Any] | None = None,
    **kwargs: Any,
) -> bool:
    """Serialize and write SRT subtitles shifted by segment_start_ms to destination path."""
    try:
        if isinstance(segment_start_ms, list):
            # Caller passed (transcript_segments, output_path, segment_start_ms=...)
            act_transcripts = segment_start_ms
            act_out = segment_end_ms
            act_start = int(kwargs.get("segment_start_ms", 0))
            act_end = int(kwargs.get("segment_end_ms", 999999999))
        else:
            act_start = int(segment_start_ms)
            act_end = int(segment_end_ms) if segment_end_ms is not None else int(kwargs.get("segment_end_ms", 999999999))
            act_transcripts = transcript_segments if transcript_segments is not None else kwargs.get("transcript_segments", [])
            act_out = output_path if output_path is not None else kwargs.get("output_path")

        spans = speech_spans or kwargs.get("speech_spans")

        if act_out is None:
            return False

        p = Path(act_out).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        content = generate_srt_content(act_start, act_end, act_transcripts, speech_spans=spans)
        p.write_text(content, encoding="utf-8")
        return True
    except Exception:
        return False


def export_ass_subtitles(
    segment_start_ms: int | list[Any] = 0,
    segment_end_ms: int | str | Path | None = None,
    transcript_segments: list[Any] | None = None,
    output_path: str | Path | None = None,
    words_per_chunk: int = 4,
    speech_spans: list[Any] | None = None,
    **kwargs: Any,
) -> bool:
    """Serialize and write styled ASS subtitles shifted by segment_start_ms to destination path."""
    try:
        if isinstance(segment_start_ms, list):
            act_transcripts = segment_start_ms
            act_out = segment_end_ms
            act_start = int(kwargs.get("segment_start_ms", 0))
            act_end = int(kwargs.get("segment_end_ms", 999999999))
            chunk_size = int(kwargs.get("words_per_chunk", words_per_chunk))
        else:
            act_start = int(segment_start_ms)
            act_end = int(segment_end_ms) if segment_end_ms is not None else int(kwargs.get("segment_end_ms", 999999999))
            act_transcripts = transcript_segments if transcript_segments is not None else kwargs.get("transcript_segments", [])
            act_out = output_path if output_path is not None else kwargs.get("output_path")
            chunk_size = words_per_chunk

        spans = speech_spans or kwargs.get("speech_spans")

        if act_out is None:
            return False

        p = Path(act_out).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        content = generate_ass_content(
            act_start,
            act_end,
            act_transcripts,
            words_per_chunk=chunk_size,
            speech_spans=spans,
        )
        p.write_text(content, encoding="utf-8")
        return True
    except Exception:
        return False


