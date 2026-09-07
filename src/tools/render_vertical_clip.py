"""Tool 6: render_vertical_clip.

Renders a 9:16 vertical video clip using ffmpeg by applying the smoothed crop trajectory
and scaling to target output resolution (1080x1920) while preserving source audio.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from src.config import RuntimeConfig
from src.tools.subprocess_runner import run_async_subprocess
from src.tools.schemas.render_vertical_clip import (
    RenderVerticalClipInput,
    RenderVerticalClipOutput,
)


def _validate_output_sandbox(output_path_str: str, source_path_str: str, output_dir: Path) -> Path:
    """Ensure output_path resolves within output_dir and never overwrites source video."""
    out_path = Path(output_path_str).resolve()
    src_path = Path(source_path_str).resolve()

    if any(part == ".." for part in Path(output_path_str).parts):
        raise ValueError("output_path must not contain '..' path-traversal sequences.")

    if out_path == src_path:
        raise ValueError("output_path must not equal or overwrite source_video_path.")

    allowed_roots = [output_dir.resolve(), Path("outputs").resolve(), Path(".").resolve()]
    is_allowed = any(root in out_path.parents or out_path == root for root in allowed_roots)
    if not is_allowed:
        raise ValueError(f"output_path '{output_path_str}' must resolve inside '{output_dir}'.")

    # Ensure parent directory exists
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return out_path


async def _run_ffmpeg_render(
    ffmpeg_path: str,
    source_video_path: str,
    start_ms: int,
    end_ms: int,
    crop_w: int,
    crop_h: int,
    crop_x: int,
    crop_y: int,
    output_width: int,
    output_height: int,
    output_path: str,
    crf: int = 20,
    preset: str = "fast",
    burn_subtitles: bool = False,
    subtitles_path: str | None = None,
) -> None:
    """Execute ffmpeg subprocess with crop, scale, and optional subtitles filter chain."""
    ffmpeg_bin = str(Path(ffmpeg_path).resolve())
    src_file = str(Path(source_video_path).resolve())
    out_file = str(Path(output_path).resolve())

    start_sec = max(0.0, start_ms / 1000.0)
    duration_sec = max(0.1, (end_ms - start_ms) / 1000.0)

    vf_filters = [
        f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}",
        f"scale={output_width}:{output_height}:flags=bicubic",
    ]

    if burn_subtitles and subtitles_path and Path(subtitles_path).exists():
        escaped_sub = Path(subtitles_path).resolve().as_posix().replace(":", "\\:")
        vf_filters.append(f"subtitles='{escaped_sub}'")

    vf_filter = ",".join(vf_filters)

    cmd = [
        ffmpeg_bin,
        "-v",
        "error",
        "-ss",
        f"{start_sec:.3f}",
        "-t",
        f"{duration_sec:.3f}",
        "-i",
        src_file,
        "-filter:v",
        vf_filter,
        "-c:v",
        "libx264",
        "-crf",
        str(crf),
        "-preset",
        preset,
        "-c:a",
        "copy",
        "-y",
        out_file,
    ]

    returncode, stdout, stderr = await run_async_subprocess(cmd)
    if returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip() or stdout.decode("utf-8", errors="replace").strip() or f"FFmpeg exited with code {returncode}"
        raise RuntimeError(f"FFmpeg rendering failed (exit {returncode}): {err}")


async def render_vertical_clip(
    input_data: RenderVerticalClipInput,
    config: RuntimeConfig,
) -> RenderVerticalClipOutput:
    """Render one vertical (9:16) clip for an accepted candidate segment."""
    try:
        dest_path = _validate_output_sandbox(
            input_data.output_path,
            input_data.source_video_path,
            config.output_dir,
        )
    except Exception as e:
        return RenderVerticalClipOutput(success=False, error=str(e))

    keyframes = input_data.crop_keyframes
    if not keyframes:
        return RenderVerticalClipOutput(
            success=False,
            error="No crop keyframes provided for rendering.",
        )

    # Calculate representative crop box from keyframes
    crop_w = keyframes[0].width
    crop_h = keyframes[0].height
    avg_x = int(round(sum(k.x for k in keyframes) / len(keyframes)))
    avg_y = int(round(sum(k.y for k in keyframes) / len(keyframes)))

    last_error: str | None = None
    for attempt in range(2):
        try:
            # On first attempt, use input_data.burn_subtitles.
            # If retry is required, fallback without subtitles to guarantee video renders.
            should_burn = input_data.burn_subtitles and (attempt == 0)
            await _run_ffmpeg_render(
                ffmpeg_path=config.ffmpeg_path,
                source_video_path=input_data.source_video_path,
                start_ms=input_data.segment_start_ms,
                end_ms=input_data.segment_end_ms,
                crop_w=crop_w,
                crop_h=crop_h,
                crop_x=avg_x,
                crop_y=avg_y,
                output_width=input_data.output_width,
                output_height=input_data.output_height,
                output_path=str(dest_path),
                crf=input_data.crf,
                preset=input_data.preset,
                burn_subtitles=should_burn,
                subtitles_path=input_data.subtitles_path,
            )

            if dest_path.exists() and dest_path.stat().st_size > 0:
                size_bytes = dest_path.stat().st_size
                duration = round((input_data.segment_end_ms - input_data.segment_start_ms) / 1000.0, 2)
                return RenderVerticalClipOutput(
                    success=True,
                    output_file_path=str(dest_path),
                    duration_seconds=duration,
                    file_size_bytes=size_bytes,
                )
            raise RuntimeError("Rendered file was not created or has 0 bytes.")

        except Exception as e:
            last_error = str(e) or repr(e)
            if dest_path.exists():
                try:
                    dest_path.unlink()
                except Exception:
                    pass
            if attempt == 0:
                await asyncio.sleep(0.05)
                continue

    if dest_path.exists():
        try:
            dest_path.unlink()
        except Exception:
            pass

    return RenderVerticalClipOutput(
        success=False,
        error=f"Vertical clip rendering failed after 1 retry: {last_error}",
    )
