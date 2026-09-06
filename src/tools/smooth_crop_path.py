"""Tool 5: smooth_crop_path.

Applies a deterministic smoothing filter (EMA or fixed-window moving average)
to a candidate segment's raw bounding-box detections to produce a jitter-free
9:16 vertical camera pan/zoom crop trajectory.
"""

from __future__ import annotations

import numpy as np

from src.config import RuntimeConfig
from src.tools.schemas.smooth_crop_path import (
    CropKeyframeModel,
    SmoothCropPathInput,
    SmoothCropPathOutput,
)


def smooth_crop_path(
    input_data: SmoothCropPathInput,
    config: RuntimeConfig | None = None,
) -> SmoothCropPathOutput:
    """Apply a deterministic smoothing filter to raw bounding-box positions."""
    if not input_data.raw_positions:
        return SmoothCropPathOutput(
            success=False,
            error="No raw positions provided for crop path smoothing.",
        )

    sw = input_data.source_width
    sh = input_data.source_height

    # Calculate 9:16 target dimensions for vertical framing
    crop_h = sh
    crop_w = int(round(crop_h * 9.0 / 16.0))
    if crop_w > sw:
        crop_w = sw
        crop_h = int(round(crop_w * 16.0 / 9.0))

    # Calculate target center x for each frame
    target_xs: list[float] = []
    timestamps: list[int] = []

    for pos in input_data.raw_positions:
        timestamps.append(pos.timestamp_ms)
        bb = pos.bounding_box
        face_center_x = bb.origin_x + (bb.width / 2.0)
        ideal_x = face_center_x - (crop_w / 2.0)
        clamped_x = max(0.0, min(float(sw - crop_w), ideal_x))
        target_xs.append(clamped_x)

    # Apply deterministic smoothing filter
    strength = input_data.smoothing_strength
    smoothed_xs = np.array(target_xs, dtype=np.float64)

    if input_data.smoothing_method == "ema":
        # Exponential Moving Average
        # Higher smoothing_strength means smoother (lower alpha)
        alpha = max(0.05, min(0.95, 1.0 - (strength * 0.85)))
        curr = smoothed_xs[0]
        ema_result = []
        for val in smoothed_xs:
            curr = alpha * val + (1.0 - alpha) * curr
            ema_result.append(curr)
        smoothed_xs = np.array(ema_result, dtype=np.float64)

    elif input_data.smoothing_method == "fixed_window_average":
        # Moving window average
        window_size = max(3, int(round(strength * 20)))
        if len(smoothed_xs) >= window_size:
            pad_size = window_size // 2
            padded = np.pad(smoothed_xs, pad_size, mode="edge")
            window = np.ones(window_size) / window_size
            smoothed_xs = np.convolve(padded, window, mode="valid")[: len(smoothed_xs)]

    # Assemble smoothed keyframes
    keyframes: list[CropKeyframeModel] = []
    for ts, sx in zip(timestamps, smoothed_xs):
        final_x = int(round(max(0.0, min(float(sw - crop_w), float(sx)))))
        keyframes.append(
            CropKeyframeModel(
                timestamp_ms=ts,
                x=final_x,
                y=0,
                width=crop_w,
                height=crop_h,
            )
        )

    return SmoothCropPathOutput(
        success=True,
        crop_keyframes=keyframes,
    )
