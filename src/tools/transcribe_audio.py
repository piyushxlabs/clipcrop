"""Tool 2: transcribe_audio.

Performs local speech-to-text with word/segment timestamps using in-process faster-whisper
(CTranslate2 INT8 CPU quantization) dispatched via asyncio.to_thread.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from src.config import RuntimeConfig
from src.tools.model_loader import load_whisper_model
from src.tools.schemas.transcribe_audio import (
    TranscribeAudioInput,
    TranscribeAudioOutput,
    TranscriptSegmentModel,
)


def _transcribe_sync(
    model: Any,
    audio_path: str,
    language: str,
) -> tuple[list[TranscriptSegmentModel], str]:
    """Synchronous CPU transcription helper run inside asyncio.to_thread."""
    segments_gen, info = model.transcribe(
        audio_path,
        language=language,
        vad_filter=False,  # VAD is handled independently by Silero VAD (Tool 3)
    )
    result_segments: list[TranscriptSegmentModel] = []
    for s in segments_gen:
        start_ms = max(0, int(round(s.start * 1000)))
        end_ms = max(start_ms, int(round(s.end * 1000)))
        text = s.text.strip()
        if text:
            result_segments.append(
                TranscriptSegmentModel(start_ms=start_ms, end_ms=end_ms, text=text)
            )
    detected_lang = getattr(info, "language", language) or language
    return result_segments, detected_lang


async def transcribe_audio(
    input_data: TranscribeAudioInput,
    config: RuntimeConfig,
) -> TranscribeAudioOutput:
    """Produce a timestamped transcript of the source audio using in-process faster-whisper."""
    audio_path = Path(input_data.audio_source_path)
    if not audio_path.exists():
        return TranscribeAudioOutput(
            success=False,
            error=f"Source audio/video file not found at '{input_data.audio_source_path}'.",
        )

    last_error: str | None = None
    tiers_to_try = [input_data.model_tier]
    if input_data.model_tier == "base.en":
        tiers_to_try.append("tiny.en")  # fallback tier for retry

    for tier in tiers_to_try:
        try:
            model = load_whisper_model(config)
            segments, lang = await asyncio.to_thread(
                _transcribe_sync,
                model,
                str(audio_path),
                input_data.language,
            )
            return TranscribeAudioOutput(
                success=True,
                segments=segments,
                language_detected=lang,
            )
        except Exception as e:
            last_error = str(e)
            continue

    return TranscribeAudioOutput(
        success=False,
        error=f"Transcription failed after retry: {last_error}",
    )
