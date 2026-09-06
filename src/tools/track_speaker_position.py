"""Tool 4: track_speaker_position.

Per-segment bounding-box tracking using MediaPipe BlazeFace short-range face detector.
Outputs bounding box coordinates and detection confidence only.
Biometric Privacy Guarantee: Strictly zero landmarks, zero face meshes, zero identity tokens.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
import mediapipe as mp
import numpy as np

from src.config import RuntimeConfig
from src.tools.model_loader import load_face_detector
from src.tools.schemas.track_speaker_position import (
    BoundingBoxModel,
    FramePositionModel,
    TrackSpeakerPositionInput,
    TrackSpeakerPositionOutput,
)


async def _extract_video_frames(
    ffmpeg_path: str,
    video_path: str,
    start_ms: int,
    end_ms: int,
    fps: int = 10,
) -> tuple[list[np.ndarray], list[int], int, int]:
    """Extract sampled video frames as RGB numpy arrays with millisecond timestamps."""
    start_sec = start_ms / 1000.0
    duration_sec = max(0.1, (end_ms - start_ms) / 1000.0)

    # First probe resolution quickly using ffprobe or standard resolution
    # Extract frames at targeted fps to save CPU
    cmd = [
        ffmpeg_path,
        "-v",
        "error",
        "-ss",
        f"{start_sec:.3f}",
        "-t",
        f"{duration_sec:.3f}",
        "-i",
        video_path,
        "-vf",
        f"fps={fps},scale=640:360",  # downscale slightly for fast real-time CPU face detection
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-",
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"FFmpeg frame extraction failed: {err}")

    frame_width = 640
    frame_height = 360
    frame_size = frame_width * frame_height * 3

    if len(stdout) == 0:
        return [], [], frame_width, frame_height

    num_frames = len(stdout) // frame_size
    frames: list[np.ndarray] = []
    timestamps: list[int] = []
    frame_step_ms = int(1000 / fps)

    for i in range(num_frames):
        raw = stdout[i * frame_size : (i + 1) * frame_size]
        arr = np.frombuffer(raw, dtype=np.uint8).reshape((frame_height, frame_width, 3))
        frames.append(arr)
        timestamps.append(start_ms + i * frame_step_ms)

    return frames, timestamps, frame_width, frame_height


def _track_frames_sync(
    detector: Any,
    frames: list[np.ndarray],
    timestamps: list[int],
    frame_sample_stride: int,
    min_confidence: float,
    frame_width: int,
    frame_height: int,
) -> tuple[list[FramePositionModel], float]:
    """Execute MediaPipe BlazeFace detection and tracking across extracted frames."""
    if not frames:
        return [], 0.0

    positions: list[FramePositionModel] = []
    sampled_count = 0
    detected_count = 0
    last_box: BoundingBoxModel | None = None

    for idx, (frame, ts) in enumerate(zip(frames, timestamps)):
        is_sampled = (idx % frame_sample_stride == 0) or (idx == len(frames) - 1)

        if is_sampled:
            sampled_count += 1
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
            detection_result = detector.detect(mp_image)

            best_box: BoundingBoxModel | None = None
            best_score = 0.0

            if detection_result.detections:
                for det in detection_result.detections:
                    score = det.categories[0].score if det.categories else 0.0
                    if score > best_score:
                        best_score = score
                        bb = det.bounding_box
                        best_box = BoundingBoxModel(
                            origin_x=int(bb.origin_x),
                            origin_y=int(bb.origin_y),
                            width=int(bb.width),
                            height=int(bb.height),
                        )

            if best_box is not None and best_score >= min_confidence:
                detected_count += 1
                last_box = best_box
                positions.append(
                    FramePositionModel(
                        timestamp_ms=ts,
                        bounding_box=best_box,
                        detection_score=round(float(best_score), 3),
                    )
                )
            else:
                # Fallback to last known position or default center box if not detected
                fallback_box = last_box or BoundingBoxModel(
                    origin_x=int(frame_width * 0.35),
                    origin_y=int(frame_height * 0.2),
                    width=int(frame_width * 0.3),
                    height=int(frame_height * 0.5),
                )
                positions.append(
                    FramePositionModel(
                        timestamp_ms=ts,
                        bounding_box=fallback_box,
                        detection_score=0.0,
                    )
                )
        else:
            # Interpolated frame (score 0.0)
            fallback_box = last_box or BoundingBoxModel(
                origin_x=int(frame_width * 0.35),
                origin_y=int(frame_height * 0.2),
                width=int(frame_width * 0.3),
                height=int(frame_height * 0.5),
            )
            positions.append(
                FramePositionModel(
                    timestamp_ms=ts,
                    bounding_box=fallback_box,
                    detection_score=0.0,
                )
            )

    segment_conf = round(detected_count / max(1, sampled_count), 3)
    return positions, segment_conf


async def track_speaker_position(
    input_data: TrackSpeakerPositionInput,
    config: RuntimeConfig,
) -> TrackSpeakerPositionOutput:
    """Detect and track the speaker's bounding-box position across one candidate segment."""
    video_path = Path(input_data.video_path)
    if not video_path.exists():
        return TrackSpeakerPositionOutput(
            success=False,
            error=f"Source video file not found at '{input_data.video_path}'.",
        )

    last_error: str | None = None
    for attempt in range(2):
        try:
            frames, timestamps, fw, fh = await _extract_video_frames(
                config.ffmpeg_path,
                str(video_path),
                input_data.segment_start_ms,
                input_data.segment_end_ms,
            )
            detector = load_face_detector(config)
            positions, conf = await asyncio.to_thread(
                _track_frames_sync,
                detector,
                frames,
                timestamps,
                input_data.frame_sample_stride,
                input_data.min_detection_confidence,
                fw,
                fh,
            )
            return TrackSpeakerPositionOutput(
                success=True,
                per_frame_positions=positions,
                segment_confidence=conf,
            )
        except Exception as e:
            last_error = str(e)
            if attempt == 0:
                await asyncio.sleep(0.05)
                continue

    return TrackSpeakerPositionOutput(
        success=False,
        error=f"Speaker tracking failed after 1 retry: {last_error}",
    )
