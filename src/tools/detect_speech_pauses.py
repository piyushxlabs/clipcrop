"""Tool 3: detect_speech_pauses.

Segments the source audio into speech/pause spans using a locally cached Silero VAD model.
Strictly offline, CPU-only execution without outbound network access.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import numpy as np
import torch

from src.config import RuntimeConfig
from src.tools.model_loader import load_silero_vad_model
from src.tools.subprocess_runner import run_async_subprocess
from src.tools.schemas.detect_speech_pauses import (
    DetectSpeechPausesInput,
    DetectSpeechPausesOutput,
    SpeechSpanModel,
)


async def _extract_audio_pcm(
    ffmpeg_path: str,
    media_path: str,
    sampling_rate: int = 16000,
) -> np.ndarray:
    """Extract 1-channel raw PCM float32 audio via ffmpeg pipe."""
    ffmpeg_bin = str(Path(ffmpeg_path).resolve())
    target_file = str(Path(media_path).resolve())
    cmd = [
        ffmpeg_bin,
        "-v",
        "error",
        "-i",
        target_file,
        "-f",
        "f32le",
        "-ac",
        "1",
        "-ar",
        str(sampling_rate),
        "-",
    ]
    returncode, stdout, stderr = await run_async_subprocess(cmd)
    if returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip() or stdout.decode("utf-8", errors="replace").strip() or f"FFmpeg exited with code {returncode}"
        raise RuntimeError(f"FFmpeg audio extraction failed (exit {returncode}): {err}")

    if not stdout:
        return np.array([], dtype=np.float32)

    return np.frombuffer(stdout, dtype=np.float32)


def _compute_speech_timestamps_jit(
    audio: np.ndarray,
    vad_model: Any,
    sampling_rate: int = 16000,
    threshold: float = 0.5,
    min_speech_duration_ms: int = 250,
    min_silence_duration_ms: int = 300,
    speech_pad_ms: int = 30,
) -> list[SpeechSpanModel]:
    """Pure in-process Silero VAD forward pass without external dependencies."""
    if len(audio) == 0:
        return []

    audio_tensor = torch.from_numpy(np.array(audio, copy=True)).float()
    window_size_samples = 512 if sampling_rate == 16000 else 256
    min_speech_samples = int(sampling_rate * min_speech_duration_ms / 1000)
    min_silence_samples = int(sampling_rate * min_silence_duration_ms / 1000)
    speech_pad_samples = int(sampling_rate * speech_pad_ms / 1000)

    audio_length = len(audio_tensor)
    speech_probs: list[float] = []

    # Reset model states
    if hasattr(vad_model, "reset_states"):
        vad_model.reset_states()

    with torch.no_grad():
        for i in range(0, audio_length - window_size_samples + 1, window_size_samples):
            chunk = audio_tensor[i : i + window_size_samples]
            out = vad_model(chunk, sampling_rate)
            # Support both float return and tensor return
            prob = float(out.item() if isinstance(out, torch.Tensor) else out)
            speech_probs.append(prob)

    # State machine to collect spans
    triggered = False
    speech_start = 0
    speech_end = 0
    temp_end = 0
    spans: list[SpeechSpanModel] = []

    for idx, prob in enumerate(speech_probs):
        current_sample = idx * window_size_samples
        if prob >= threshold:
            if temp_end != 0:
                temp_end = 0
            if not triggered:
                triggered = True
                speech_start = max(0, current_sample - speech_pad_samples)
        else:
            if triggered:
                if temp_end == 0:
                    temp_end = current_sample
                if current_sample - temp_end >= min_silence_samples:
                    speech_end = min(audio_length, temp_end + speech_pad_samples)
                    if speech_end - speech_start >= min_speech_samples:
                        spans.append(
                            SpeechSpanModel(
                                start_seconds=round(speech_start / sampling_rate, 3),
                                end_seconds=round(speech_end / sampling_rate, 3),
                            )
                        )
                    triggered = False
                    temp_end = 0

    if triggered:
        speech_end = audio_length
        if speech_end - speech_start >= min_speech_samples:
            spans.append(
                SpeechSpanModel(
                    start_seconds=round(speech_start / sampling_rate, 3),
                    end_seconds=round(speech_end / sampling_rate, 3),
                )
            )

    return spans


async def detect_speech_pauses(
    input_data: DetectSpeechPausesInput,
    config: RuntimeConfig,
) -> DetectSpeechPausesOutput:
    """Segment the source audio into speech/pause spans using a local Silero-VAD model."""
    audio_path = Path(input_data.audio_source_path)
    if not audio_path.exists():
        return DetectSpeechPausesOutput(
            success=False,
            error=f"Source audio file not found at '{input_data.audio_source_path}'.",
        )

    last_error: str | None = None
    for attempt in range(2):
        try:
            pcm = await _extract_audio_pcm(
                config.ffmpeg_path,
                str(audio_path),
                sampling_rate=input_data.sampling_rate,
            )
            model = load_silero_vad_model(config)
            spans = await asyncio.to_thread(
                _compute_speech_timestamps_jit,
                pcm,
                model,
                input_data.sampling_rate,
                input_data.threshold,
                input_data.min_speech_duration_ms,
                input_data.min_silence_duration_ms,
                input_data.speech_pad_ms,
            )
            return DetectSpeechPausesOutput(
                success=True,
                speech_spans=spans,
                sampling_rate_used=input_data.sampling_rate,
            )
        except Exception as e:
            last_error = str(e) or repr(e)
            if attempt == 0:
                await asyncio.sleep(0.05)
                continue

    return DetectSpeechPausesOutput(
        success=False,
        error=f"VAD speech pause detection failed after 1 retry: {last_error}",
    )
