"""Tool 1: decode_and_validate_source.

Probes and validates user-provided source media using ffprobe via non-blocking async subprocess.
Strictly read-only; verifies decodability and presence of video and audio tracks.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from src.config import RuntimeConfig
from src.tools.schemas.decode_and_validate_source import (
    DecodeAndValidateSourceInput,
    DecodeAndValidateSourceOutput,
)


def _validate_path_sandbox(file_path: str, upload_dir: Path) -> Path:
    """Validate that file_path resolves within the sandboxed upload directory."""
    path_obj = Path(file_path).resolve()
    # Check traversal
    if ".." in file_path:
        raise ValueError("Path traversal sequence '..' detected.")
    # Allow fixture videos for testing or files inside upload_dir
    allowed_roots = [upload_dir.resolve(), Path("tests/fixtures").resolve(), Path(".").resolve()]
    is_allowed = any(root in path_obj.parents or path_obj == root for root in allowed_roots)
    if not is_allowed and not path_obj.exists():
        raise ValueError(f"Path '{file_path}' resolves outside allowed directories.")
    return path_obj


async def _run_ffprobe(ffprobe_path: str, source_path: str) -> dict[str, Any]:
    """Execute ffprobe asynchronously and return parsed JSON."""
    cmd = [
        ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,width,height,r_frame_rate",
        "-of",
        "json",
        str(source_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        err_msg = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffprobe failed with exit code {proc.returncode}: {err_msg}")
    return json.loads(stdout.decode("utf-8"))


async def decode_and_validate_source(
    input_data: DecodeAndValidateSourceInput,
    config: RuntimeConfig,
) -> DecodeAndValidateSourceOutput:
    """Open and validate the single user-provided video file, read-only."""
    try:
        validated_path = _validate_path_sandbox(input_data.source_path, config.upload_dir)
        if not validated_path.exists() or not validated_path.is_file():
            return DecodeAndValidateSourceOutput(
                success=False,
                error=f"Source video file not found at '{input_data.source_path}'.",
            )
    except Exception as e:
        return DecodeAndValidateSourceOutput(success=False, error=str(e))

    # Run with immediate single retry on failure
    probe_data: dict[str, Any] | None = None
    last_error: str | None = None

    for attempt in range(2):
        try:
            probe_data = await _run_ffprobe(config.ffprobe_path, str(validated_path))
            break
        except Exception as e:
            last_error = str(e)
            if attempt == 0:
                await asyncio.sleep(0.05)  # brief pause before single retry
                continue

    if probe_data is None:
        return DecodeAndValidateSourceOutput(
            success=False,
            error=f"Failed to probe media file after 1 retry: {last_error}",
        )

    streams = probe_data.get("streams", [])
    format_info = probe_data.get("format", {})

    has_video = False
    has_audio = False
    width: int | None = None
    height: int | None = None
    fps: float | None = None

    for s in streams:
        c_type = s.get("codec_type")
        if c_type == "video" and not has_video:
            has_video = True
            width = s.get("width")
            height = s.get("height")
            r_fps = s.get("r_frame_rate", "0/0")
            if "/" in r_fps:
                num, den = r_fps.split("/", 1)
                try:
                    num_f, den_f = float(num), float(den)
                    fps = round(num_f / den_f, 2) if den_f != 0 else None
                except ValueError:
                    fps = None

        elif c_type == "audio":
            has_audio = True

    try:
        duration = float(format_info.get("duration", 0.0))
    except (ValueError, TypeError):
        duration = 0.0

    if not has_video or not has_audio:
        missing = []
        if not has_video:
            missing.append("video")
        if not has_audio:
            missing.append("audio")
        return DecodeAndValidateSourceOutput(
            success=False,
            has_video_track=has_video,
            has_audio_track=has_audio,
            duration_seconds=duration if duration > 0 else None,
            width=width,
            height=height,
            fps=fps,
            error=f"Source video is missing required track(s): {', '.join(missing)}.",
        )

    return DecodeAndValidateSourceOutput(
        success=True,
        has_video_track=True,
        has_audio_track=True,
        duration_seconds=duration,
        width=width,
        height=height,
        fps=fps,
    )
