"""Master ZIP Deliverable Bundle Tool.

Packages all paired deliverables, timeline files, captions, cover art,
and metadata into a single 1-click creator archive.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
import zipfile


def create_deliverables_bundle(
    zip_output_path: str | Path,
    segment_id: str,
    files_to_bundle: Mapping[str, Path | str | None],
    metadata: dict[str, Any] | None = None,
) -> str | None:
    """Pack all generated files for a clip segment into a single ZIP archive.

    Returns:
        String path to created ZIP if successful, or None.
    """
    try:
        dest_zip = Path(zip_output_path).resolve()
        dest_zip.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # 1. Add all existing file assets
            for arcname, fpath in files_to_bundle.items():
                if fpath:
                    p = Path(fpath).resolve()
                    if p.is_file():
                        zf.write(p, arcname=arcname)

            # 2. Add README_METADATA.txt
            if metadata:
                readme_lines = [
                    "============================================================",
                    f"CLIPCROP CREATOR PACK — SEGMENT {segment_id}",
                    "============================================================",
                    "",
                    "VIRAL OPENING HOOK:",
                    f'"{metadata.get("hook", "")}"',
                    "",
                    "RECOMMENDED TITLES:",
                ]
                for idx, t in enumerate(metadata.get("titles", []), start=1):
                    readme_lines.append(f"  {idx}. {t}")

                readme_lines.extend([
                    "",
                    "RECOMMENDED HASHTAGS:",
                    " ".join(metadata.get("hashtags", [])),
                    "",
                    "FULL TRANSCRIPT:",
                    metadata.get("transcript", ""),
                    "",
                    "------------------------------------------------------------",
                    "NLE EDIT TIMELINES INCLUDED:",
                    "- CMX 3600 Edit Decision List (.edl) for Premiere Pro / DaVinci Resolve",
                    "- Final Cut Pro XML (.xml) for FCP / DaVinci Resolve",
                    "- JSON Keyframe coordinates (.json) for custom motion graphics",
                    "============================================================",
                ])
                zf.writestr("README_METADATA.txt", "\n".join(readme_lines))

        if dest_zip.exists() and dest_zip.stat().st_size > 0:
            return str(dest_zip)
        return None
    except Exception:
        return None
