#!/usr/bin/env python3
"""
ClipCrop - Local Model Asset Setup Script
Idempotently downloads and caches all required offline perception models:
1. MediaPipe BlazeFace short-range face detector (.task / .tflite)
2. Faster-Whisper base.en INT8 model (CTranslate2 format)
3. Silero VAD (JIT model and repository for torch.hub offline use)

Zero cloud APIs; runs once at setup time so runtime is 100% offline.
"""

from __future__ import annotations

import io
import os
import sys
import shutil
import urllib.request
import zipfile
from pathlib import Path

# Verified URLs for offline model assets
MEDIAPIPE_BLAZEFACE_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)

SILERO_VAD_JIT_URL = (
    "https://raw.githubusercontent.com/snakers4/silero-vad/master/src/silero_vad/data/silero_vad.jit"
)

SILERO_VAD_REPO_ZIP_URL = (
    "https://github.com/snakers4/silero-vad/archive/refs/heads/master.zip"
)

FASTER_WHISPER_BASE_FILES = {
    "config.json": "https://huggingface.co/Systran/faster-whisper-base.en/resolve/main/config.json",
    "model.bin": "https://huggingface.co/Systran/faster-whisper-base.en/resolve/main/model.bin",
    "tokenizer.json": "https://huggingface.co/Systran/faster-whisper-base.en/resolve/main/tokenizer.json",
    "vocabulary.txt": "https://huggingface.co/Systran/faster-whisper-base.en/resolve/main/vocabulary.txt",
}


def load_env_file(env_path: Path) -> dict[str, str]:
    """Parse key-value pairs from a .env file if present."""
    env_vars: dict[str, str] = {}
    if not env_path.is_file():
        return env_vars

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            env_vars[key.strip()] = val.strip()
    return env_vars


def get_models_dir() -> Path:
    """Resolve destination directory for local models."""
    project_root = Path(__file__).resolve().parent.parent
    env_vars = load_env_file(project_root / ".env")

    models_path_str = os.environ.get(
        "CLIPCROP_MODELS_DIR",
        env_vars.get("CLIPCROP_MODELS_DIR", str(project_root / "models")),
    )
    models_dir = Path(models_path_str).resolve()
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def download_file_with_progress(url: str, dest_path: Path, label: str) -> None:
    """Download a file with progress indication if it does not already exist."""
    if dest_path.is_file() and dest_path.stat().st_size > 0:
        print(f"  [EXISTS] {label} already cached at {dest_path} ({dest_path.stat().st_size:,} bytes)")
        return

    print(f"  [DOWNLOADING] {label} from {url}...")
    temp_path = dest_path.with_suffix(".tmp")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "ClipCrop-Setup/1.0"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp, open(temp_path, "wb") as out_file:
            total_size = int(resp.headers.get("content-length", 0))
            downloaded = 0
            chunk_size = 1024 * 64  # 64 KB
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = downloaded / total_size * 100
                    print(
                        f"\r    Progress: {percent:5.1f}% ({downloaded / 1024 / 1024:6.1f} MB / {total_size / 1024 / 1024:6.1f} MB)",
                        end="",
                        flush=True,
                    )
                else:
                    print(
                        f"\r    Downloaded: {downloaded / 1024 / 1024:6.1f} MB",
                        end="",
                        flush=True,
                    )
            print()
        if temp_path.stat().st_size == 0:
            raise RuntimeError(f"Downloaded file for {label} was empty (0 bytes).")
        temp_path.replace(dest_path)
        print(f"  [SUCCESS] Saved to {dest_path} ({dest_path.stat().st_size:,} bytes)")
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise RuntimeError(f"Failed to download {label}: {e}") from e


def setup_mediapipe_task(models_dir: Path) -> Path:
    """Download MediaPipe BlazeFace short-range task asset."""
    task_file = models_dir / "blaze_face_short_range.task"
    tflite_file = models_dir / "blaze_face_short_range.tflite"

    download_file_with_progress(MEDIAPIPE_BLAZEFACE_URL, task_file, "MediaPipe BlazeFace Task")
    if task_file.is_file() and not tflite_file.is_file():
        shutil.copy2(task_file, tflite_file)
        print(f"  [COPIED] Created duplicate {tflite_file} for tflite compatibility")

    return task_file


def setup_silero_vad(models_dir: Path) -> tuple[Path, Path]:
    """Download Silero VAD JIT model and offline repository."""
    vad_jit_file = models_dir / "silero_vad.jit"
    download_file_with_progress(SILERO_VAD_JIT_URL, vad_jit_file, "Silero VAD JIT Model")

    # Also download and unpack snakers4/silero-vad repo for torch.hub source="local"
    repo_dir = models_dir / "silero-vad-master"
    hubconf_file = repo_dir / "hubconf.py"
    if hubconf_file.is_file():
        print(f"  [EXISTS] Silero VAD torch.hub repository already unpacked at {repo_dir}")
    else:
        print(f"  [DOWNLOADING] Silero VAD repository archive for torch.hub offline mode...")
        req = urllib.request.Request(
            SILERO_VAD_REPO_ZIP_URL,
            headers={"User-Agent": "ClipCrop-Setup/1.0"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            zip_content = resp.read()
        with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
            z.extractall(models_dir)
        print(f"  [SUCCESS] Unpacked Silero VAD repository to {repo_dir}")

    # Also create snakers4_silero-vad_master alias for torch.hub naming conventions
    alias_dir = models_dir / "snakers4_silero-vad_master"
    if not alias_dir.exists() and repo_dir.exists():
        shutil.copytree(repo_dir, alias_dir)
        print(f"  [COPIED] Created alias directory at {alias_dir}")

    return vad_jit_file, repo_dir


def setup_faster_whisper(models_dir: Path) -> Path:
    """Download and cache faster-whisper base.en CTranslate2 model."""
    whisper_dir = models_dir / "faster-whisper-base.en"
    whisper_dir.mkdir(parents=True, exist_ok=True)

    # First check if faster_whisper is available to use native download_model
    try:
        from faster_whisper import download_model
        print("  [FASTER-WHISPER] Using faster_whisper.download_model...")
        download_model("base.en", output_dir=str(whisper_dir))
        print(f"  [SUCCESS] faster-whisper base.en cached at {whisper_dir}")
        return whisper_dir
    except ImportError:
        print("  [INFO] faster_whisper not yet installed in host env; downloading direct CTranslate2 files...")

    # Fallback to direct HTTP download of CTranslate2 INT8 model files
    for filename, file_url in FASTER_WHISPER_BASE_FILES.items():
        target_path = whisper_dir / filename
        download_file_with_progress(file_url, target_path, f"Faster-Whisper {filename}")

    return whisper_dir


def main() -> None:
    print("=" * 70)
    print("ClipCrop: Standalone Offline Model Asset Setup")
    print("=" * 70)

    models_dir = get_models_dir()
    print(f"Target Models Directory: {models_dir}\n")

    print("[1/3] Setting up MediaPipe BlazeFace detector asset...")
    task_path = setup_mediapipe_task(models_dir)
    print(f"-> BlazeFace Task: {task_path} (exists: {task_path.is_file()})\n")

    print("[2/3] Setting up Silero VAD assets...")
    vad_path, repo_path = setup_silero_vad(models_dir)
    print(f"-> Silero VAD JIT: {vad_path} (exists: {vad_path.is_file()})")
    print(f"-> Silero VAD Repo: {repo_path} (exists: {repo_path.is_dir()})\n")

    print("[3/3] Setting up Faster-Whisper base.en model...")
    whisper_dir = setup_faster_whisper(models_dir)
    print(f"-> Faster-Whisper Dir: {whisper_dir} (exists: {whisper_dir.is_dir()})\n")

    all_whisper_present = all((whisper_dir / f).is_file() for f in FASTER_WHISPER_BASE_FILES)

    print("=" * 70)
    print("Verification Summary:")
    print(f"  1. MediaPipe task asset: {'PASS' if task_path.is_file() else 'FAIL'}")
    print(f"  2. Silero VAD JIT asset: {'PASS' if vad_path.is_file() else 'FAIL'}")
    print(f"  3. Silero VAD offline repo: {'PASS' if repo_path.is_dir() else 'FAIL'}")
    print(f"  4. Faster-Whisper base.en: {'PASS' if all_whisper_present else 'FAIL'}")
    print("=" * 70)

    if not (task_path.is_file() and vad_path.is_file() and repo_path.is_dir() and all_whisper_present):
        print("ERROR: Model setup failed to download all required offline assets.")
        sys.exit(1)

    print("Model asset setup successfully completed.")


if __name__ == "__main__":
    main()
