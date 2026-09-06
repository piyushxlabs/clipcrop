"""Pydantic V2 and JSON schemas for all ClipCrop tools and structured outputs."""

from src.tools.schemas.candidate_scorer import (
    CANDIDATE_SEGMENT_SCORE_SCHEMA,
    CandidateSegmentScore,
)
from src.tools.schemas.confidence_gate import (
    CONFIDENCE_GATE_DECISION_SCHEMA,
    ConfidenceGateDecision,
)
from src.tools.schemas.decode_and_validate_source import (
    DECODE_AND_VALIDATE_SOURCE_SCHEMA,
    DecodeAndValidateSourceInput,
    DecodeAndValidateSourceOutput,
)
from src.tools.schemas.detect_speech_pauses import (
    DETECT_SPEECH_PAUSES_SCHEMA,
    DetectSpeechPausesInput,
    DetectSpeechPausesOutput,
    SpeechSpanModel,
)
from src.tools.schemas.export_crop_path_data import (
    EXPORT_CROP_PATH_DATA_SCHEMA,
    ExportCropPathDataInput,
    ExportCropPathDataOutput,
)
from src.tools.schemas.render_vertical_clip import (
    RENDER_VERTICAL_CLIP_SCHEMA,
    RenderVerticalClipInput,
    RenderVerticalClipOutput,
)
from src.tools.schemas.smooth_crop_path import (
    SMOOTH_CROP_PATH_SCHEMA,
    CropKeyframeModel,
    SmoothCropPathInput,
    SmoothCropPathOutput,
)
from src.tools.schemas.track_speaker_position import (
    TRACK_SPEAKER_POSITION_SCHEMA,
    BoundingBoxModel,
    FramePositionModel,
    TrackSpeakerPositionInput,
    TrackSpeakerPositionOutput,
)
from src.tools.schemas.transcribe_audio import (
    TRANSCRIBE_AUDIO_SCHEMA,
    TranscribeAudioInput,
    TranscribeAudioOutput,
    TranscriptSegmentModel,
)

__all__ = [
    "DecodeAndValidateSourceInput",
    "DecodeAndValidateSourceOutput",
    "DECODE_AND_VALIDATE_SOURCE_SCHEMA",
    "TranscribeAudioInput",
    "TranscriptSegmentModel",
    "TranscribeAudioOutput",
    "TRANSCRIBE_AUDIO_SCHEMA",
    "DetectSpeechPausesInput",
    "SpeechSpanModel",
    "DetectSpeechPausesOutput",
    "DETECT_SPEECH_PAUSES_SCHEMA",
    "CandidateSegmentScore",
    "CANDIDATE_SEGMENT_SCORE_SCHEMA",
    "TrackSpeakerPositionInput",
    "BoundingBoxModel",
    "FramePositionModel",
    "TrackSpeakerPositionOutput",
    "TRACK_SPEAKER_POSITION_SCHEMA",
    "ConfidenceGateDecision",
    "CONFIDENCE_GATE_DECISION_SCHEMA",
    "SmoothCropPathInput",
    "CropKeyframeModel",
    "SmoothCropPathOutput",
    "SMOOTH_CROP_PATH_SCHEMA",
    "RenderVerticalClipInput",
    "RenderVerticalClipOutput",
    "RENDER_VERTICAL_CLIP_SCHEMA",
    "ExportCropPathDataInput",
    "ExportCropPathDataOutput",
    "EXPORT_CROP_PATH_DATA_SCHEMA",
]
