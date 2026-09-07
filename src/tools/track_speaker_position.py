"""Tool 4: track_speaker_position.

Per-segment bounding-box tracking using MediaPipe BlazeFace short-range face detector.
Outputs bounding box coordinates and detection confidence only.
Biometric Privacy Guarantee: Strictly zero landmarks, zero face meshes, zero identity tokens.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import mediapipe as mp
import numpy as np

from src.config import RuntimeConfig
from src.tools.model_loader import load_face_detector
from src.tools.subprocess_runner import run_async_subprocess
from src.tools.schemas.track_speaker_position import (
    BoundingBoxModel,
    FramePositionModel,
    TrackSpeakerPositionInput,
    TrackSpeakerPositionOutput,
)


async def _probe_video_dimensions(ffprobe_path: str, video_path: str) -> tuple[int, int]:
    """Quickly probe width and height of video file via ffprobe."""
    ffprobe_bin = str(Path(ffprobe_path).resolve())
    target_file = str(Path(video_path).resolve())
    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "json",
        target_file,
    ]
    try:
        returncode, stdout, _ = await run_async_subprocess(cmd)
        if returncode == 0 and stdout:
            data = json.loads(stdout.decode("utf-8", errors="replace"))
            streams = data.get("streams", [])
            if streams:
                w = int(streams[0].get("width", 0))
                h = int(streams[0].get("height", 0))
                if w > 0 and h > 0:
                    return w, h
    except Exception:
        pass
    return 640, 360


async def _extract_video_frames(
    ffmpeg_path: str,
    video_path: str,
    start_ms: int,
    end_ms: int,
    fps: int = 10,
) -> tuple[list[np.ndarray], list[int], int, int]:
    """Extract sampled video frames as RGB numpy arrays with millisecond timestamps."""
    ffmpeg_bin = str(Path(ffmpeg_path).resolve())
    target_file = str(Path(video_path).resolve())
    start_sec = max(0.0, start_ms / 1000.0)
    duration_sec = max(0.1, max(0.0, end_ms - start_ms) / 1000.0)

    # Extract frames at targeted fps to save CPU
    cmd = [
        ffmpeg_bin,
        "-v",
        "error",
        "-ss",
        f"{start_sec:.3f}",
        "-t",
        f"{duration_sec:.3f}",
        "-i",
        target_file,
        "-vf",
        f"fps={fps},scale=640:360",  # downscale for fast real-time CPU face detection
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-",
    ]

    returncode, stdout, stderr = await run_async_subprocess(cmd)
    if returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip() or stdout.decode("utf-8", errors="replace").strip() or f"FFmpeg exited with code {returncode}"
        raise RuntimeError(f"FFmpeg frame extraction failed (exit {returncode}): {err}")

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
    source_width: int | None = None,
    source_height: int | None = None,
) -> tuple[list[FramePositionModel], float]:
    """Execute MediaPipe BlazeFace detection and tracking across extracted frames.
    
    Bounding boxes are scaled from downscaled extraction space (e.g. 640x360) back
    to full source video coordinate space (e.g. 1280x720).
    """
    if not frames:
        return [], 0.0

    target_w = source_width if (source_width and source_width > 0) else frame_width
    target_h = source_height if (source_height and source_height > 0) else frame_height
    scale_x = float(target_w) / float(frame_width)
    scale_y = float(target_h) / float(frame_height)

    positions: list[FramePositionModel] = []
    sampled_count = 0
    detected_count = 0
    last_box: BoundingBoxModel | None = None
    last_score: float = 0.0

    default_box = BoundingBoxModel(
        origin_x=int(round(target_w * 0.35)),
        origin_y=int(round(target_h * 0.2)),
        width=int(round(target_w * 0.3)),
        height=int(round(target_h * 0.5)),
    )

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
                            origin_x=int(round(bb.origin_x * scale_x)),
                            origin_y=int(round(bb.origin_y * scale_y)),
                            width=int(round(bb.width * scale_x)),
                            height=int(round(bb.height * scale_y)),
                        )

            if best_box is not None and best_score >= min_confidence:
                detected_count += 1
                last_box = best_box
                last_score = round(float(best_score), 3)
                positions.append(
                    FramePositionModel(
                        timestamp_ms=ts,
                        bounding_box=best_box,
                        detection_score=last_score,
                    )
                )
            else:
                # Fallback to last known position or default center box if not detected
                fallback_box = last_box or default_box
                positions.append(
                    FramePositionModel(
                        timestamp_ms=ts,
                        bounding_box=fallback_box,
                        detection_score=0.0,
                    )
                )
        else:
            # Interpolated frame: retain the last valid detection_score instead of emitting 0.0
            fallback_box = last_box or default_box
            positions.append(
                FramePositionModel(
                    timestamp_ms=ts,
                    bounding_box=fallback_box,
                    detection_score=last_score,
                )
            )

    segment_conf = round(detected_count / max(1, sampled_count), 3)
    print(
        f"[Stage 4 Track] Extracted {len(frames)} frames ({frame_width}x{frame_height} -> {target_w}x{target_h}, "
        f"scale={scale_x:.2f}x{scale_y:.2f}), {sampled_count} sampled, {detected_count} face detections (confidence={segment_conf:.3f})"
    )
    return positions, segment_conf


def _track_frames_process_worker(
    config_dict: dict[str, Any],
    frames: list[np.ndarray],
    timestamps: list[int],
    frame_sample_stride: int,
    min_confidence: float,
    frame_width: int,
    frame_height: int,
    source_width: int | None = None,
    source_height: int | None = None,
) -> tuple[list[dict[str, Any]], float]:
    """Worker function executed inside a ProcessPoolExecutor worker process."""
    from src.config import RuntimeConfig
    from src.tools.model_loader import load_face_detector

    cfg = RuntimeConfig.model_validate(config_dict)
    detector = load_face_detector(cfg)
    positions, conf = _track_frames_sync(
        detector,
        frames,
        timestamps,
        frame_sample_stride,
        min_confidence,
        frame_width,
        frame_height,
        source_width,
        source_height,
    )
    return [p.model_dump() for p in positions], conf


async def track_speaker_position(
    input_data: TrackSpeakerPositionInput,
    config: RuntimeConfig,
    executor: Any | None = None,
    source_width: int | None = None,
    source_height: int | None = None,
) -> TrackSpeakerPositionOutput:
    """Detect and track the speaker's bounding-box position across one candidate segment."""
    video_path = Path(input_data.video_path)
    if not video_path.exists():
        return TrackSpeakerPositionOutput(
            success=False,
            error=f"Source video file not found at '{input_data.video_path}'.",
        )

    # Probe source video dimensions if not provided, for coordinate scaling
    if source_width is None or source_height is None:
        probed_w, probed_h = await _probe_video_dimensions(config.ffprobe_path, str(video_path))
        source_width = source_width or probed_w
        source_height = source_height or probed_h

    last_error: str | None = None
    for attempt in range(2):
        try:
            frames, timestamps, fw, fh = await _extract_video_frames(
                config.ffmpeg_path,
                str(video_path),
                input_data.segment_start_ms,
                input_data.segment_end_ms,
            )

            if executor is not None:
                loop = asyncio.get_running_loop()
                raw_positions, conf = await loop.run_in_executor(
                    executor,
                    _track_frames_process_worker,
                    config.model_dump(),
                    frames,
                    timestamps,
                    input_data.frame_sample_stride,
                    input_data.min_detection_confidence,
                    fw,
                    fh,
                    source_width,
                    source_height,
                )
                positions = [FramePositionModel.model_validate(p) for p in raw_positions]
            else:
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
                    source_width,
                    source_height,
                )
            print(
                f"[Stage 4 Track] Segment '{input_data.segment_id}' ({input_data.segment_start_ms}ms-{input_data.segment_end_ms}ms): "
                f"{len(frames)} frames extracted, {len(positions)} positions returned -> segment_confidence={conf:.3f}"
            )

            return TrackSpeakerPositionOutput(
                success=True,
                per_frame_positions=positions,
                segment_confidence=conf,
            )
        except Exception as e:
            last_error = str(e) or repr(e)
            if attempt == 0:
                await asyncio.sleep(0.05)
                continue

    return TrackSpeakerPositionOutput(
        success=False,
        error=f"Speaker tracking failed after 1 retry: {last_error}",
    )
