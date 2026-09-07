"""Pydantic V2 and strict JSON Schema for render_vertical_clip tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from typing_extensions import Self
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.tools.schemas.smooth_crop_path import CropKeyframeModel


class RenderVerticalClipInput(BaseModel):
    """Render one vertical (9:16) clip for an accepted segment using its smoothed crop path."""

    model_config = ConfigDict(strict=True)

    segment_id: str = Field(..., description="Identifier of the segment being rendered.")
    source_video_path: str = Field(..., description="Path to the validated source video (read-only).")
    segment_start_ms: int = Field(..., ge=0, description="Segment start offset in milliseconds.")
    segment_end_ms: int = Field(..., description="Segment end offset in milliseconds.")
    crop_keyframes: list[CropKeyframeModel] = Field(..., description="Smoothed crop path from smooth_crop_path.")
    output_width: int = Field(1080, description="Target output width in pixels.")
    output_height: int = Field(1920, description="Target output height in pixels.")
    output_path: str = Field(..., description="Destination path inside designated output directory only.")
    video_codec: Literal["libx264"] = Field("libx264", description="Video encoder to use.")
    crf: int = Field(20, ge=0, le=51, description="Constant rate factor for encoding quality.")
    preset: Literal["veryfast", "fast", "medium"] = Field("fast", description="Encoder speed/quality preset.")
    burn_subtitles: bool = Field(default=False, description="Whether to burn in styled subtitles.")
    subtitles_path: str | None = Field(default=None, description="Path to ASS/SRT subtitles file to burn in.")

    @field_validator("source_video_path", "output_path")
    @classmethod
    def validate_no_traversal(cls, v: str) -> str:
        if any(part == ".." for part in Path(v).parts):
            raise ValueError("Paths must not contain '..' path-traversal sequences.")
        return v

    @field_validator("crop_keyframes")
    @classmethod
    def validate_non_empty_keyframes(cls, v: list[CropKeyframeModel]) -> list[CropKeyframeModel]:
        if not v:
            raise ValueError("crop_keyframes must not be empty.")
        return v

    @model_validator(mode="after")
    def validate_output_not_source(self) -> Self:
        from pathlib import Path
        if Path(self.output_path).resolve() == Path(self.source_video_path).resolve():
            raise ValueError("output_path cannot overwrite source video")
        return self


class RenderVerticalClipOutput(BaseModel):
    """Result of rendering the vertical clip."""

    model_config = ConfigDict(strict=True)

    success: bool = Field(..., description="Whether rendering completed successfully.")
    output_file_path: str | None = Field(default=None, description="Path to rendered clip file.")
    duration_seconds: float | None = Field(default=None, description="Duration of rendered clip.")
    file_size_bytes: int | None = Field(default=None, description="Size of rendered clip file.")
    error: str | None = Field(default=None, description="Error message if success is false.")


RENDER_VERTICAL_CLIP_SCHEMA: dict[str, Any] = {
    "name": "render_vertical_clip",
    "description": "Render one vertical (9:16) clip for an accepted segment by applying its smoothed crop path with ffmpeg.",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "segment_id": {"type": "string", "description": "Identifier of the segment being rendered."},
            "source_video_path": {"type": "string", "description": "Path to the validated source video (read-only)."},
            "segment_start_ms": {"type": "integer", "minimum": 0, "description": "Segment start offset in milliseconds."},
            "segment_end_ms": {"type": "integer", "description": "Segment end offset in milliseconds."},
            "crop_keyframes": {
                "type": "array",
                "description": "Smoothed crop path from smooth_crop_path.",
                "items": {
                    "type": "object",
                    "properties": {
                        "timestamp_ms": {"type": "integer"},
                        "x": {"type": "integer"},
                        "y": {"type": "integer"},
                        "width": {"type": "integer"},
                        "height": {"type": "integer"},
                    },
                    "required": ["timestamp_ms", "x", "y", "width", "height"],
                    "additionalProperties": False,
                },
            },
            "output_width": {"type": "integer", "description": "Target output width in pixels."},
            "output_height": {"type": "integer", "description": "Target output height in pixels."},
            "output_path": {"type": "string", "description": "Destination path inside designated output directory only."},
            "video_codec": {"type": "string", "enum": ["libx264"], "description": "Video encoder to use."},
            "crf": {"type": "integer", "minimum": 0, "maximum": 51, "description": "Constant rate factor."},
            "preset": {"type": "string", "enum": ["veryfast", "fast", "medium"], "description": "Encoder preset."},
            "burn_subtitles": {"type": "boolean", "description": "Whether to burn in styled subtitles."},
            "subtitles_path": {"type": ["string", "null"], "description": "Path to ASS/SRT subtitles file to burn in."},
        },
        "required": [
            "segment_id",
            "source_video_path",
            "segment_start_ms",
            "segment_end_ms",
            "crop_keyframes",
            "output_width",
            "output_height",
            "output_path",
            "video_codec",
            "crf",
            "preset",
        ],
        "additionalProperties": False,
    },
}
