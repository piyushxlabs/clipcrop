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
) -> list[TimedWord]:
    """Extract word-level relative timing from overlapping transcript segments."""
    timed_words: list[TimedWord] = []

    for seg in transcript_segments:
        start_ms = getattr(seg, "start_ms", 0)
        end_ms = getattr(seg, "end_ms", 0)
        text = getattr(seg, "text", "").strip()

        if not text or end_ms <= segment_start_ms or start_ms >= segment_end_ms:
            continue

        rel_start = max(0, start_ms - segment_start_ms)
        rel_end = min(segment_end_ms - segment_start_ms, end_ms - segment_start_ms)
        if rel_end <= rel_start:
            continue

        raw_words = text.split()
        if not raw_words:
            continue

        dur = rel_end - rel_start
        n = len(raw_words)
        for i, w in enumerate(raw_words):
            clean_word = w.strip().upper()
            if not clean_word:
                continue
            w_start = rel_start + int(i * dur / n)
            w_end = rel_start + int((i + 1) * dur / n)
            timed_words.append(TimedWord(word=clean_word, start_ms=w_start, end_ms=max(w_start + 50, w_end)))

    return timed_words


def generate_srt_content(
    segment_start_ms: int,
    segment_end_ms: int,
    transcript_segments: list[Any],
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

        rel_start = max(0, start_ms - segment_start_ms)
        rel_end = min(segment_end_ms - segment_start_ms, end_ms - segment_start_ms)
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
) -> str:
    """Generate Hormozi-style kinetic ASS subtitles with active-word yellow highlight."""
    timed_words = _extract_timed_words(segment_start_ms, segment_end_ms, transcript_segments)

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
    segment_start_ms: int,
    segment_end_ms: int,
    transcript_segments: list[Any],
    output_path: str | Path,
) -> bool:
    """Serialize and write SRT subtitles to the specified destination path."""
    try:
        p = Path(output_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        content = generate_srt_content(segment_start_ms, segment_end_ms, transcript_segments)
        p.write_text(content, encoding="utf-8")
        return True
    except Exception:
        return False


def export_ass_subtitles(
    segment_start_ms: int,
    segment_end_ms: int,
    transcript_segments: list[Any],
    output_path: str | Path,
    words_per_chunk: int = 4,
) -> bool:
    """Serialize and write styled ASS subtitles to the specified destination path."""
    try:
        p = Path(output_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        content = generate_ass_content(
            segment_start_ms,
            segment_end_ms,
            transcript_segments,
            words_per_chunk=words_per_chunk,
        )
        p.write_text(content, encoding="utf-8")
        return True
    except Exception:
        return False

