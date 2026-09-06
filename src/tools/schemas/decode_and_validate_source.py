"""Pydantic V2 and strict JSON Schema for decode_and_validate_source tool."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class DecodeAndValidateSourceInput(BaseModel):
    """Open and validate the single user-provided video file, read-only."""

    model_config = ConfigDict(strict=True)

    source_path: str = Field(
        ...,
        description="Absolute local filesystem path to the user-provided video file. Must resolve within the designated upload directory.",
    )

    @field_validator("source_path")
    @classmethod
    def validate_no_traversal(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("source_path must not contain '..' path-traversal sequences.")
        return v


class DecodeAndValidateSourceOutput(BaseModel):
    """Result of validating the source media file."""

    model_config = ConfigDict(strict=True)

    success: bool = Field(..., description="Whether the file decoded successfully with the required tracks.")
    duration_seconds: float | None = Field(default=None, description="Total duration of the source video in seconds, if decoded.")
    has_video_track: bool | None = Field(default=None, description="Whether a video track was found.")
    has_audio_track: bool | None = Field(default=None, description="Whether an audio track was found.")
    width: int | None = Field(default=None, description="Source frame width in pixels.")
    height: int | None = Field(default=None, description="Source frame height in pixels.")
    fps: float | None = Field(default=None, description="Source frame rate.")
    error: str | None = Field(default=None, description="Error message if success is false.")


DECODE_AND_VALIDATE_SOURCE_SCHEMA: dict[str, Any] = {
    "name": "decode_and_validate_source",
    "description": "Open and validate the single user-provided video file, read-only, returning basic media metadata.",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "source_path": {
                "type": "string",
                "description": "Absolute local filesystem path to the user-provided video file. Must resolve within the designated upload directory.",
            }
        },
        "required": ["source_path"],
        "additionalProperties": False,
    },
}
