"""Offline model loader and health-check system for ClipCrop.

Loads all perception models strictly from local paths with zero network egress:
1. Faster-Whisper INT8 model (via faster_whisper.WhisperModel)
2. MediaPipe BlazeFace Detector (via mediapipe.tasks.python.vision.FaceDetector)
3. Silero VAD (via torch.jit.load on standalone TorchScript bundle)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import torch

from src.config import RuntimeConfig, load_config_from_env
from src.exceptions import ToolExecutionError


def load_whisper_model(config: RuntimeConfig, tier: str = "base.en") -> Any:
    """Load Faster-Whisper model (base.en or tiny.en) from local models directory.

    Guarantees zero network calls by enforcing local_files_only=True.
    """
    from faster_whisper import WhisperModel

    folder_name = f"faster-whisper-{tier}" if not tier.startswith("faster-whisper-") else tier
    whisper_dir = config.models_dir / folder_name
    if not whisper_dir.is_dir():
        raise ToolExecutionError(
            f"Faster-Whisper model directory not found at {whisper_dir}"
        )

    required_files = ["model.bin", "config.json", "tokenizer.json", "vocabulary.txt"]
    for f in required_files:
        if not (whisper_dir / f).is_file():
            raise ToolExecutionError(
                f"Faster-Whisper model asset missing: {whisper_dir / f}"
            )

    try:
        model = WhisperModel(
            model_size_or_path=str(whisper_dir),
            device="cpu",
            compute_type="int8",
            local_files_only=True,
        )
        return model
    except Exception as e:
        raise ToolExecutionError(f"Failed to load Faster-Whisper model: {e}") from e


def load_face_detector(
    config: RuntimeConfig,
    running_mode: Any = None,
) -> Any:
    """Load MediaPipe BlazeFace short-range face detector task from local path.

    Guarantees offline execution by pointing to pre-downloaded .task asset.
    """
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    if running_mode is None:
        running_mode = vision.RunningMode.IMAGE

    task_path = config.models_dir / "blaze_face_short_range.task"
    if not task_path.is_file():
        # Fallback check for .tflite if .task wasn't created
        tflite_path = config.models_dir / "blaze_face_short_range.tflite"
        if tflite_path.is_file():
            task_path = tflite_path
        else:
            raise ToolExecutionError(
                f"MediaPipe BlazeFace task file not found at {task_path}"
            )

    try:
        base_options = mp_python.BaseOptions(model_asset_path=str(task_path))
        options = vision.FaceDetectorOptions(
            base_options=base_options,
            running_mode=running_mode,
        )
        detector = vision.FaceDetector.create_from_options(options)
        return detector
    except Exception as e:
        raise ToolExecutionError(f"Failed to load MediaPipe FaceDetector: {e}") from e


def load_silero_vad_model(config: RuntimeConfig) -> torch.jit.ScriptModule:
    """Load Silero VAD TorchScript model from local models directory.

    Directly loads silero_vad.jit via torch.jit.load, completely offline with
    zero external dependencies and zero network requests.
    """
    jit_path = config.models_dir / "silero_vad.jit"
    if not jit_path.is_file():
        raise ToolExecutionError(f"Silero VAD JIT model file not found at {jit_path}")

    try:
        model = torch.jit.load(str(jit_path), map_location="cpu")
        model.eval()
        return model
    except Exception as e:
        raise ToolExecutionError(f"Failed to load Silero VAD model: {e}") from e


def run_model_health_check(
    config: RuntimeConfig,
    fixture_path: Path | None = None,
) -> dict[str, Any]:
    """Execute end-to-end local health check for all three perception models.

    Tests loading and test inference against fixture data with zero network calls.
    """
    import cv2
    import mediapipe as mp

    results: dict[str, Any] = {
        "faster_whisper": {"status": "untested"},
        "mediapipe_face_detector": {"status": "untested"},
        "silero_vad": {"status": "untested"},
    }

    # 1. Faster-Whisper Health Check
    try:
        whisper_model = load_whisper_model(config)
        # Run test inference on 1-second 16kHz silent audio array
        test_audio = np.zeros(16000, dtype=np.float32)
        segments, info = whisper_model.transcribe(test_audio, language="en")
        seg_list = list(segments)
        results["faster_whisper"] = {
            "status": "healthy",
            "model_path": str(config.models_dir / "faster-whisper-base.en"),
            "language_detected": info.language,
            "segments_produced": len(seg_list),
        }
    except Exception as e:
        results["faster_whisper"] = {"status": "unhealthy", "error": str(e)}

    # 2. MediaPipe Face Detector Health Check
    try:
        face_detector = load_face_detector(config)
        # Extract a real frame if fixture provided, else use synthetic frame
        if fixture_path and fixture_path.is_file():
            cap = cv2.VideoCapture(str(fixture_path))
            ret, frame = cap.read()
            cap.release()
            if not ret:
                frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        else:
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        detection_result = face_detector.detect(mp_image)
        results["mediapipe_face_detector"] = {
            "status": "healthy",
            "model_path": str(config.models_dir / "blaze_face_short_range.task"),
            "detections_count": len(detection_result.detections),
            "frame_shape": list(frame.shape),
        }
    except Exception as e:
        results["mediapipe_face_detector"] = {"status": "unhealthy", "error": str(e)}

    # 3. Silero VAD Health Check
    try:
        vad_model = load_silero_vad_model(config)
        # Run test inference on 512-sample chunk at 16000 Hz
        test_chunk = torch.zeros(1, 512, dtype=torch.float32)
        vad_model.reset_states()
        speech_prob = vad_model(test_chunk, 16000).item()
        results["silero_vad"] = {
            "status": "healthy",
            "model_path": str(config.models_dir / "silero_vad.jit"),
            "test_chunk_speech_prob": float(speech_prob),
        }
    except Exception as e:
        results["silero_vad"] = {"status": "unhealthy", "error": str(e)}

    # Overall health evaluation
    all_healthy = all(
        res.get("status") == "healthy" for res in results.values()
    )
    results["all_healthy"] = all_healthy

    if not all_healthy:
        raise ToolExecutionError(
            f"One or more local models failed health check: {results}"
        )

    return results


def main() -> None:
    """CLI utility to execute the offline model health check."""
    config = load_config_from_env()
    fixture = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "simple_case.mp4"

    print("=" * 70)
    print("ClipCrop: Offline Model Health Check")
    print("=" * 70)
    print(f"Models directory: {config.models_dir}")
    print(f"Fixture video:    {fixture} (exists: {fixture.is_file()})\n")

    try:
        health_results = run_model_health_check(config, fixture if fixture.is_file() else None)
        print("[SUCCESS] All three local perception models are healthy:")
        print(f"  1. Faster-Whisper: {health_results['faster_whisper']['status'].upper()}")
        print(f"  2. MediaPipe:      {health_results['mediapipe_face_detector']['status'].upper()}")
        print(f"  3. Silero VAD:     {health_results['silero_vad']['status'].upper()}")
        print("=" * 70)
    except Exception as e:
        print(f"[FAIL] Model health check failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()
