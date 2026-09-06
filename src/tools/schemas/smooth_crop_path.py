"""Pydantic V2 and strict JSON Schema for smooth_crop_path tool."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from src.tools.schemas.track_speaker_position import FramePositionModel


class CropKeyframeModel(BaseModel):
    """Smoothed crop window keyframe."""

    model_config = ConfigDict(strict=True)

    timestamp_ms: int = Field(..., ge=0, description="Keyframe timestamp within the segment, in milliseconds.")
    x: int = Field(..., description="Smoothed crop top-left x coordinate in pixels.")
    y: int = Field(..., description="Smoothed crop top-left y coordinate in pixels.")
    width: int = Field(..., ge=0, description="Crop width in pixels.")
    height: int = Field(..., ge=0, description="Crop height in pixels.")


class SmoothCropPathInput(BaseModel):
    """Apply a deterministic smoothing filter to a segment's raw position track."""

    model_config = ConfigDict(strict=True)

    segment_id: str = Field(..., description="Identifier of the segment being smoothed.")
    raw_positions: list[FramePositionModel] = Field(..., description="The raw per-frame bounding-box track from track_speaker_position.")
    smoothing_method: Literal["ema", "fixed_window_average"] = Field("ema", description="Deterministic smoothing method to apply.")
    smoothing_strength: float = Field(0.3, ge=0.0, le=1.0, description="Smoothing coefficient.")
    source_width: int = Field(1280, ge=1, description="Source video frame width in pixels.")
    source_height: int = Field(720, ge=1, description="Source video frame height in pixels.")


class SmoothCropPathOutput(BaseModel):
    """Result of crop-path smoothing."""

    model_config = ConfigDict(strict=True)

    success: bool = Field(..., description="Whether smoothing completed successfully.")
    crop_keyframes: list[CropKeyframeModel] | None = Field(default=None, description="Smoothed, jitter-free crop path as timecoded keyframes.")
    error: str | None = Field(default=None, description="Error message if success is false.")


SMOOTH_CROP_PATH_SCHEMA: dict[str, Any] = {
    "name": "smooth_crop_path",
    "description": "Apply a deterministic smoothing filter to a segment's raw bounding-box track to produce a jitter-free crop path.",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "segment_id": {"type": "string", "description": "Identifier of the segment being smoothed."},
            "raw_positions": {
                "type": "array",
                "description": "The raw per-frame bounding-box track from track_speaker_position.",
                "items": {
                    "type": "object",
                    "properties": {
                        "timestamp_ms": {"type": "integer"},
                        "bounding_box": {
                            "type": "object",
                            "properties": {
                                "origin_x": {"type": "integer"},
                                "origin_y": {"type": "integer"},
                                "width": {"type": "integer"},
                                "height": {"type": "integer"},
                            },
                            "required": ["origin_x", "origin_y", "width", "height"],
                            "additionalProperties": False,
                        },
                        "detection_score": {"type": "number"},
                    },
                    "required": ["timestamp_ms", "bounding_box", "detection_score"],
                    "additionalProperties": False,
                },
            },
            "smoothing_method": {
                "type": "string",
                "enum": ["ema", "fixed_window_average"],
                "description": "Deterministic smoothing method.",
            },
            "smoothing_strength": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Smoothing coefficient.",
            },
            "source_width": {"type": "integer", "description": "Source video frame width in pixels."},
            "source_height": {"type": "integer", "description": "Source video frame height in pixels."},
        },
        "required": [
            "segment_id",
            "raw_positions",
            "smoothing_method",
            "smoothing_strength",
            "source_width",
            "source_height",
        ],
        "additionalProperties": False,
    },
}
