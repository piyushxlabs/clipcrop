"""Tool 7: export_crop_path_data.

Serializes the smoothed crop path used for rendering into human-editable
NLE timeline data (industry-standard CMX 3600 .edl, FCPXML/Premiere .xml, or JSON).
Zero-dependency Python implementation — no legacy PyPI EDL packages.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.config import RuntimeConfig
from src.tools.schemas.export_crop_path_data import (
    ExportCropPathDataInput,
    ExportCropPathDataOutput,
)
from src.tools.schemas.smooth_crop_path import CropKeyframeModel


def _ms_to_timecode(ms: int, fps: int = 30) -> str:
    """Format millisecond timestamp into standard CMX 3600 timecode HH:MM:SS:FF."""
    total_frames = int(round((ms / 1000.0) * fps))
    ff = total_frames % fps
    total_sec = total_frames // fps
    ss = total_sec % 60
    mm = (total_sec // 60) % 60
    hh = total_sec // 3600
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def _serialize_to_edl(
    segment_id: str,
    keyframes: list[CropKeyframeModel],
    fps: int = 30,
) -> str:
    """Serialize keyframes to CMX 3600 EDL string with tracking marker metadata."""
    if not keyframes:
        return "TITLE: CLIPCROP_EXPORT\nFCM: NON-DROP FRAME\n"

    lines = [
        "TITLE: CLIPCROP_EXPORT",
        "FCM: NON-DROP FRAME",
        "",
    ]

    start_tc = _ms_to_timecode(keyframes[0].timestamp_ms, fps)
    end_tc = _ms_to_timecode(keyframes[-1].timestamp_ms, fps)

    # Event 001: Main source edit event
    lines.append(f"001  AX       V     C        {start_tc} {end_tc} 01:00:00:00 01:00:{end_tc[6:]}")
    lines.append(f"* FROM CLIP NAME: {segment_id}")

    # Append keyframe pan/zoom tracking markers as standard CMX comments
    for idx, kf in enumerate(keyframes, start=1):
        kf_tc = _ms_to_timecode(kf.timestamp_ms, fps)
        lines.append(
            f"* KEYFRAME {idx:03d} AT {kf_tc} CROP_X={kf.x} CROP_Y={kf.y} WIDTH={kf.width} HEIGHT={kf.height}"
        )

    lines.append("")
    return "\n".join(lines)


def _serialize_to_xml(
    segment_id: str,
    keyframes: list[CropKeyframeModel],
    fps: int = 30,
) -> str:
    """Serialize keyframes to FCPXML/Premiere XML timeline structure."""
    duration_frames = len(keyframes)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE xmeml>',
        '<xmeml version="4">',
        '  <sequence>',
        f'    <name>{segment_id}</name>',
        f'    <duration>{duration_frames}</duration>',
        '    <rate>',
        f'      <timebase>{fps}</timebase>',
        '      <ntsc>FALSE</ntsc>',
        '    </rate>',
        '    <media>',
        '      <video>',
        '        <track>',
        f'          <clipitem id="{segment_id}_clip">',
        f'            <name>{segment_id}</name>',
        '            <filter>',
        '              <effect>',
        '                <name>ClipCrop Motion</name>',
        '                <keyframes>',
    ]

    for kf in keyframes:
        lines.append(
            f'                  <keyframe timestamp_ms="{kf.timestamp_ms}" x="{kf.x}" y="{kf.y}" width="{kf.width}" height="{kf.height}"/>'
        )

    lines.extend(
        [
            '                </keyframes>',
            '              </effect>',
            '            </filter>',
            '          </clipitem>',
            '        </track>',
            '      </video>',
            '    </media>',
            '  </sequence>',
            '</xmeml>',
        ]
    )
    return "\n".join(lines)


def _serialize_to_json(
    segment_id: str,
    keyframes: list[CropKeyframeModel],
) -> str:
    """Serialize keyframes to coordinate telemetry JSON."""
    data = {
        "segment_id": segment_id,
        "keyframe_count": len(keyframes),
        "keyframes": [
            {
                "timestamp_ms": kf.timestamp_ms,
                "x": kf.x,
                "y": kf.y,
                "width": kf.width,
                "height": kf.height,
            }
            for kf in keyframes
        ],
    }
    return json.dumps(data, indent=2)


def export_crop_path_data(
    input_data: ExportCropPathDataInput,
    config: RuntimeConfig | None = None,
) -> ExportCropPathDataOutput:
    """Write a segment's smoothed crop path out as CMX 3600 .edl, .xml, or .json."""
    out_path = Path(input_data.output_path).resolve()

    if ".." in input_data.output_path:
        return ExportCropPathDataOutput(
            success=False,
            error="output_path must not contain '..' path-traversal sequences.",
        )

    # Validate output directory if config is provided
    if config is not None:
        allowed_roots = [config.output_dir.resolve(), Path("outputs").resolve(), Path(".").resolve()]
        is_allowed = any(root in out_path.parents or out_path == root for root in allowed_roots)
        if not is_allowed:
            return ExportCropPathDataOutput(
                success=False,
                error=f"output_path '{input_data.output_path}' resolves outside allowed output directory.",
            )

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if input_data.format == "edl":
            content = _serialize_to_edl(input_data.segment_id, input_data.crop_keyframes)
        elif input_data.format == "xml":
            content = _serialize_to_xml(input_data.segment_id, input_data.crop_keyframes)
        elif input_data.format == "json":
            content = _serialize_to_json(input_data.segment_id, input_data.crop_keyframes)
        else:
            return ExportCropPathDataOutput(
                success=False,
                error=f"Unsupported export format '{input_data.format}'.",
            )

        out_path.write_text(content, encoding="utf-8")

        return ExportCropPathDataOutput(
            success=True,
            output_file_path=str(out_path),
            keyframe_count=len(input_data.crop_keyframes),
        )

    except Exception as e:
        return ExportCropPathDataOutput(
            success=False,
            error=f"Failed to write crop path export: {e}",
        )
