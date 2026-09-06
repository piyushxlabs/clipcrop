"""Pydantic V2 and strict JSON Schema for detect_speech_pauses tool."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SpeechSpanModel(BaseModel):
    """Detected speech span with start and end offsets in seconds."""

    model_config = ConfigDict(strict=True)

    start_seconds: float = Field(..., ge=0.0, description="Speech span start time in seconds.")
    end_seconds: float = Field(..., ge=0.0, description="Speech span end time in seconds.")


class DetectSpeechPausesInput(BaseModel):
    """Segment the source audio into speech/pause spans using a local Silero-VAD-class model."""

    model_config = ConfigDict(strict=True)

    audio_source_path: str = Field(..., description="Path to the validated source video/audio (same file as source_video).")
    sampling_rate: Literal[8000, 16000] = Field(16000, description="Audio sampling rate in Hz; Silero VAD supports 8000 or 16000.")
    threshold: float = Field(0.5, ge=0.0, le=1.0, description="Speech probability threshold above which a frame is considered speech.")
    min_speech_duration_ms: int = Field(250, ge=0, description="Minimum duration for a detected speech span to be kept.")
    min_silence_duration_ms: int = Field(300, ge=0, description="Minimum silence duration required to split two speech spans.")
    speech_pad_ms: int = Field(30, ge=0, description="Padding added to each side of a detected speech span.")

    @field_validator("audio_source_path")
    @classmethod
    def validate_no_traversal(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("audio_source_path must not contain '..' path-traversal sequences.")
        return v


class DetectSpeechPausesOutput(BaseModel):
    """Result of local voice-activity detection."""

    model_config = ConfigDict(strict=True)

    success: bool = Field(..., description="Whether VAD completed successfully.")
    speech_spans: list[SpeechSpanModel] | None = Field(default=None, description="Detected speech spans.")
    sampling_rate_used: int | None = Field(default=None, description="Sampling rate actually used for inference.")
    error: str | None = Field(default=None, description="Error message if success is false.")


DETECT_SPEECH_PAUSES_SCHEMA: dict[str, Any] = {
    "name": "detect_speech_pauses",
    "description": "Segment the source audio into speech/pause spans using a local Silero-VAD-class model.",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "audio_source_path": {
                "type": "string",
                "description": "Path to the validated source video/audio (same file as source_video).",
            },
            "sampling_rate": {
                "type": "integer",
                "enum": [8000, 16000],
                "description": "Audio sampling rate in Hz.",
            },
            "threshold": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Speech probability threshold.",
            },
            "min_speech_duration_ms": {
                "type": "integer",
                "minimum": 0,
                "description": "Minimum kept speech-span duration.",
            },
            "min_silence_duration_ms": {
                "type": "integer",
                "minimum": 0,
                "description": "Minimum silence duration to split spans.",
            },
            "speech_pad_ms": {
                "type": "integer",
                "minimum": 0,
                "description": "Padding added to each side of a speech span.",
            },
        },
        "required": [
            "audio_source_path",
            "sampling_rate",
            "threshold",
            "min_speech_duration_ms",
            "min_silence_duration_ms",
            "speech_pad_ms",
        ],
        "additionalProperties": False,
    },
}
