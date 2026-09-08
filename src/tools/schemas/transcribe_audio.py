"""Pydantic V2 and strict JSON Schema for transcribe_audio tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TranscriptWordModel(BaseModel):
    """Word-level timing model."""

    model_config = ConfigDict(strict=True)

    word: str = Field(..., description="Individual word token.")
    start_ms: int = Field(..., ge=0, description="Word start offset in milliseconds.")
    end_ms: int = Field(..., ge=0, description="Word end offset in milliseconds.")
    probability: float | None = Field(default=None, description="Confidence probability of word.")


class TranscriptSegmentModel(BaseModel):
    """Timestamped transcript segment model."""

    model_config = ConfigDict(strict=True)

    start_ms: int = Field(..., ge=0, description="Segment start offset in milliseconds.")
    end_ms: int = Field(..., ge=0, description="Segment end offset in milliseconds.")
    text: str = Field(..., description="Transcribed text for this segment.")
    words: list[TranscriptWordModel] = Field(default_factory=list, description="Word-level timestamps.")



class TranscribeAudioInput(BaseModel):
    """Produce a timestamped transcript of the source audio using in-process faster-whisper (CTranslate2 INT8 CPU quantization)."""

    model_config = ConfigDict(strict=True)

    audio_source_path: str = Field(..., description="Path to the validated source video/audio (same file as source_video).")
    model_tier: Literal["tiny.en", "base.en"] = Field("base.en", description="Local faster-whisper CPU model tier to use; base.en is default, tiny.en is retry fallback.")
    language: str = Field("en", description="Expected spoken language code passed to faster-whisper.")
    max_segment_length_tokens: int | None = Field(default=None, description="Optional parameter to bound segment length for finer timestamp granularity.")

    @field_validator("audio_source_path")
    @classmethod
    def validate_no_traversal(cls, v: str) -> str:
        if any(part == ".." for part in Path(v).parts):
            raise ValueError("audio_source_path must not contain '..' path-traversal sequences.")
        return v

    @field_validator("max_segment_length_tokens")
    @classmethod
    def validate_tokens_positive(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("max_segment_length_tokens must be greater than 0 if provided.")
        return v


class TranscribeAudioOutput(BaseModel):
    """Result of local transcription."""

    model_config = ConfigDict(strict=True)

    success: bool = Field(..., description="Whether transcription completed successfully.")
    segments: list[TranscriptSegmentModel] | None = Field(default=None, description="Timestamped transcript segments.")
    language_detected: str | None = Field(default=None, description="Language reported by faster-whisper.")
    error: str | None = Field(default=None, description="Error message if success is false.")


TRANSCRIBE_AUDIO_SCHEMA: dict[str, Any] = {
    "name": "transcribe_audio",
    "description": "Produce a timestamped transcript of the source audio using in-process faster-whisper (CTranslate2 INT8 CPU quantization).",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "audio_source_path": {
                "type": "string",
                "description": "Path to the validated source video/audio (same file as source_video).",
            },
            "model_tier": {
                "type": "string",
                "enum": ["tiny.en", "base.en"],
                "description": "Local faster-whisper CPU model tier to use.",
            },
            "language": {
                "type": "string",
                "description": "Expected spoken language code passed to faster-whisper.",
            },
            "max_segment_length_tokens": {
                "type": ["integer", "null"],
                "description": "Optional parameter to bound segment length for finer timestamp granularity.",
            },
        },
        "required": ["audio_source_path", "model_tier", "language"],
        "additionalProperties": False,
    },
}
