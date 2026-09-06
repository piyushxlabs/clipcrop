"""Pydantic V2 and strict JSON Schema for track_speaker_position tool."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class BoundingBoxModel(BaseModel):
    """Bounding box in image pixel coordinates."""

    model_config = ConfigDict(strict=True)

    origin_x: int = Field(..., description="Bounding box top-left x coordinate in pixels.")
    origin_y: int = Field(..., description="Bounding box top-left y coordinate in pixels.")
    width: int = Field(..., ge=0, description="Bounding box width in pixels.")
    height: int = Field(..., ge=0, description="Bounding box height in pixels.")


class FramePositionModel(BaseModel):
    """Position detection for a single frame."""

    model_config = ConfigDict(strict=True)

    timestamp_ms: int = Field(..., ge=0, description="Frame timestamp within the segment, in milliseconds.")
    bounding_box: BoundingBoxModel = Field(..., description="Detected or interpolated speaker bounding box for this frame.")
    detection_score: float = Field(..., ge=0.0, le=1.0, description="Detector confidence for this frame's bounding box.")


class TrackSpeakerPositionInput(BaseModel):
    """Detect and track the speaker's bounding-box position across one candidate segment."""

    model_config = ConfigDict(strict=True)

    segment_id: str = Field(..., description="Identifier of the candidate segment, matching an entry in candidate_segments.")
    video_path: str = Field(..., description="Path to the validated source video (same file as source_video).")
    segment_start_ms: int = Field(..., ge=0, description="Segment start offset in milliseconds within the source video.")
    segment_end_ms: int = Field(..., description="Segment end offset in milliseconds within the source video.")
    model_asset_path: str = Field(..., description="Local path to the MediaPipe BlazeFace-class .task model file.")
    frame_sample_stride: int = Field(3, ge=1, description="Run detection every Nth frame and interpolate between detections.")
    min_detection_confidence: float = Field(0.5, ge=0.0, le=1.0, description="Minimum per-frame detection score to accept a bounding box.")

    @field_validator("video_path", "model_asset_path")
    @classmethod
    def validate_no_traversal(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("Paths must not contain '..' path-traversal sequences.")
        return v

    @field_validator("segment_end_ms")
    @classmethod
    def validate_end_after_start(cls, v: int, info: Any) -> int:
        start = info.data.get("segment_start_ms")
        if start is not None and v <= start:
            raise ValueError("segment_end_ms must be strictly greater than segment_start_ms.")
        return v


class TrackSpeakerPositionOutput(BaseModel):
    """Result of per-segment positional tracking."""

    model_config = ConfigDict(strict=True)

    success: bool = Field(..., description="Whether tracking completed.")
    per_frame_positions: list[FramePositionModel] | None = Field(default=None, description="Per-frame bounding-box track for this segment.")
    segment_confidence: float | None = Field(default=None, ge=0.0, le=1.0, description="Aggregate confidence for this segment's track.")
    error: str | None = Field(default=None, description="Error message if success is false.")


TRACK_SPEAKER_POSITION_SCHEMA: dict[str, Any] = {
    "name": "track_speaker_position",
    "description": "Detect and track the speaker's bounding-box position across one candidate segment using a local BlazeFace-class detector. Returns position only — no identity data.",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "segment_id": {"type": "string", "description": "Identifier of the candidate segment."},
            "video_path": {"type": "string", "description": "Path to the validated source video."},
            "segment_start_ms": {"type": "integer", "minimum": 0, "description": "Segment start offset in milliseconds."},
            "segment_end_ms": {"type": "integer", "description": "Segment end offset in milliseconds."},
            "model_asset_path": {"type": "string", "description": "Local path to the BlazeFace-class .task model file."},
            "frame_sample_stride": {"type": "integer", "minimum": 1, "description": "Run detection every Nth frame."},
            "min_detection_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0, "description": "Minimum per-frame detection score to accept a box."},
        },
        "required": [
            "segment_id",
            "video_path",
            "segment_start_ms",
            "segment_end_ms",
            "model_asset_path",
            "frame_sample_stride",
            "min_detection_confidence",
        ],
        "additionalProperties": False,
    },
}
