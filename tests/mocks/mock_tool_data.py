"""Authoritative mock responses for unit testing downstream pipeline stages.

Copied verbatim from AGENT_MASTER_PLAN.md Section 9.1 and AGENT_LOGIC_SPEC.md Section 4.
"""

from __future__ import annotations

from typing import Any

MOCK_DECODE_AND_VALIDATE_OUTPUT: dict[str, Any] = {
    "success": True,
    "duration_seconds": 612.4,
    "has_video_track": True,
    "has_audio_track": True,
    "width": 1920,
    "height": 1080,
    "fps": 29.97,
    "error": None,
}

MOCK_TRANSCRIBE_OUTPUT: dict[str, Any] = {
    "success": True,
    "segments": [
        {"start_ms": 0, "end_ms": 850, "text": "And so my"},
        {"start_ms": 900, "end_ms": 2500, "text": "journey began in video editing."},
    ],
    "language_detected": "en",
    "error": None,
}

MOCK_DETECT_PAUSES_OUTPUT: dict[str, Any] = {
    "success": True,
    "speech_spans": [
        {"start_seconds": 0.0, "end_seconds": 11.0},
        {"start_seconds": 12.5, "end_seconds": 25.0},
    ],
    "sampling_rate_used": 16000,
    "error": None,
}

MOCK_TRACK_SPEAKER_OUTPUT: dict[str, Any] = {
    "success": True,
    "per_frame_positions": [
        {
            "timestamp_ms": 0,
            "bounding_box": {"origin_x": 126, "origin_y": 100, "width": 463, "height": 463},
            "detection_score": 0.97,
        },
        {
            "timestamp_ms": 100,
            "bounding_box": {"origin_x": 130, "origin_y": 102, "width": 460, "height": 460},
            "detection_score": 0.95,
        },
    ],
    "segment_confidence": 0.91,
    "error": None,
}

MOCK_SMOOTH_CROP_OUTPUT: dict[str, Any] = {
    "success": True,
    "crop_keyframes": [
        {"timestamp_ms": 0, "x": 210, "y": 40, "width": 608, "height": 1080},
        {"timestamp_ms": 100, "x": 212, "y": 40, "width": 608, "height": 1080},
    ],
    "error": None,
}

MOCK_RENDER_CLIP_OUTPUT: dict[str, Any] = {
    "success": True,
    "output_file_path": "outputs/clip_seg01.mp4",
    "duration_seconds": 17.7,
    "file_size_bytes": 4823110,
    "error": None,
}

MOCK_EXPORT_CROP_OUTPUT: dict[str, Any] = {
    "success": True,
    "output_file_path": "outputs/clip_seg01.edl",
    "keyframe_count": 42,
    "error": None,
}
