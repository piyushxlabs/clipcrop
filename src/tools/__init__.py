"""ClipCrop processing and perception tools package."""

from src.tools.candidate_scorer import score_candidate_segments
from src.tools.confidence_gate import confidence_gate_decision
from src.tools.decode_and_validate_source import decode_and_validate_source
from src.tools.transcribe_audio import transcribe_audio
from src.tools.detect_speech_pauses import detect_speech_pauses
from src.tools.export_crop_path_data import export_crop_path_data
from src.tools.model_loader import (
    load_face_detector,
    load_silero_vad_model,
    load_whisper_model,
    run_model_health_check,
)
from src.tools.render_vertical_clip import render_vertical_clip
from src.tools.smooth_crop_path import smooth_crop_path
from src.tools.track_speaker_position import track_speaker_position

__all__ = [
    "decode_and_validate_source",
    "transcribe_audio",
    "detect_speech_pauses",
    "score_candidate_segments",
    "track_speaker_position",
    "confidence_gate_decision",
    "smooth_crop_path",
    "render_vertical_clip",
    "export_crop_path_data",
    "load_whisper_model",
    "load_face_detector",
    "load_silero_vad_model",
    "run_model_health_check",
]
