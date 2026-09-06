"""Pydantic V2 and strict JSON Schema for export_crop_path_data tool."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.tools.schemas.smooth_crop_path import CropKeyframeModel


class ExportCropPathDataInput(BaseModel):
    """Write a segment's smoothed crop path out as an industry-standard NLE timeline (.edl / .xml) or JSON data file."""

    model_config = ConfigDict(strict=True)

    segment_id: str = Field(..., description="Identifier of the segment whose crop path is being exported.")
    crop_keyframes: list[CropKeyframeModel] = Field(..., description="Smoothed crop path from smooth_crop_path.")
    output_path: str = Field(..., description="Destination path inside designated output directory only.")
    format: Literal["edl", "xml", "json"] = Field(
        "edl",
        description="Timeline export format: 'edl' (CMX 3600 standard), 'xml' (FCPXML/Premiere), or 'json' (coordinate telemetry).",
    )

    @field_validator("output_path")
    @classmethod
    def validate_no_traversal(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("output_path must not contain '..' path-traversal sequences.")
        return v


class ExportCropPathDataOutput(BaseModel):
    """Result of exporting crop-path data."""

    model_config = ConfigDict(strict=True)

    success: bool = Field(..., description="Whether export completed successfully.")
    output_file_path: str | None = Field(default=None, description="Path to exported crop-path data file.")
    keyframe_count: int | None = Field(default=None, description="Number of keyframes written.")
    error: str | None = Field(default=None, description="Error message if success is false.")


EXPORT_CROP_PATH_DATA_SCHEMA: dict[str, Any] = {
    "name": "export_crop_path_data",
    "description": "Write a segment's smoothed crop path out as an industry-standard NLE timeline (.edl / .xml) or JSON data file, paired with its rendered clip.",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "segment_id": {"type": "string", "description": "Identifier of the segment whose crop path is being exported."},
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
            "output_path": {"type": "string", "description": "Destination path inside the designated output directory only."},
            "format": {
                "type": "string",
                "enum": ["edl", "xml", "json"],
                "description": "Timeline export format: 'edl' (CMX 3600 standard with position/pan/zoom tracking markers), 'xml' (FCPXML/Premiere timeline), or 'json' (raw coordinate telemetry).",
            },
        },
        "required": ["segment_id", "crop_keyframes", "output_path", "format"],
        "additionalProperties": False,
    },
}
