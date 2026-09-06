"""Safety guardrails and negative test suite for ClipCrop.

Verifies:
- All 8 Section 8 prohibitions from AGENT_BEHAVIOR_PROFILE.md and AGENT_MASTER_PLAN.md.
- Invariants from Section 9.4 ("Agent Is Working" success criteria).
- All 6 failure scenarios from Section 9.5 (corrupt media, model retry, cancellation rollback,
  boundary confidence, time-budget circuit breaker, and malformed tool outputs).
"""

import asyncio
from pathlib import Path
import pytest
from pydantic import ValidationError

from src.config import RuntimeConfig, load_config_from_env
from src.exceptions import ClipCropError, PermanentFailureError, StateValidationError
from src.state.schema import (
    BoundingBox,
    CandidateSegment,
    CropKeyframe,
    FileRef,
    FramePosition,
    GateDecision,
    SmoothedPath,
    StateSchema,
    TrackingResult,
)
from src.state.reducers import (
    apply_state_update,
    verify_export_precondition,
    verify_render_precondition,
)
from src.agents.pipeline_controller import PipelineController, PipelineStage
from src.tools.schemas.decode_and_validate_source import DecodeAndValidateSourceInput
from src.tools.decode_and_validate_source import decode_and_validate_source
from src.tools.schemas.render_vertical_clip import (
    CropKeyframeModel,
    RenderVerticalClipInput,
)
from src.tools.render_vertical_clip import render_vertical_clip
from src.tools.schemas.export_crop_path_data import ExportCropPathDataInput
from src.tools.export_crop_path_data import export_crop_path_data
from src.tools.confidence_gate import confidence_gate_decision
from src.tools.schemas.track_speaker_position import (
    BoundingBoxModel,
    FramePositionModel,
    TrackSpeakerPositionOutput,
)


@pytest.fixture
def test_config(tmp_path: Path) -> RuntimeConfig:
    """Fixture providing sandboxed directories for safety testing."""
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    base_cfg = load_config_from_env()
    return base_cfg.model_copy(
        update={
            "upload_dir": upload_dir,
            "output_dir": output_dir,
            "confidence_threshold": 0.65,
            "max_candidates": 10,
            "time_budget_seconds": 90.0,
        }
    )


# ---------------------------------------------------------------------------
# PROHIBITION 1 & 7: $0 Budget, CPU-only, Zero Publishing/Network Tools
# ---------------------------------------------------------------------------

def test_prohibition_no_network_or_publishing_tools() -> None:
    """Section 8 Prohibition 1 & 7: No social media, publishing, or billed cloud APIs exist."""
    import src.tools as tools_pkg

    # Check exported tool names
    tool_names = dir(tools_pkg)
    prohibited_keywords = ["publish", "upload_social", "youtube", "tiktok", "twitter", "s3", "cloud"]
    for name in tool_names:
        for kw in prohibited_keywords:
            assert kw not in name.lower(), f"Prohibited tool functionality found: {name}"

    # Verify no paid cloud API packages in dependencies
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text(encoding="utf-8").lower()
    for paid_sdk in ["openai", "anthropic", "google-genai", "google-generativeai", "langchain"]:
        assert paid_sdk not in content, f"Prohibited paid/cloud SDK in pyproject.toml: {paid_sdk}"


# ---------------------------------------------------------------------------
# PROHIBITION 2: No Modifying or Deleting Source Video
# ---------------------------------------------------------------------------

def test_prohibition_source_video_immutable_and_cannot_be_overwritten(
    test_config: RuntimeConfig,
    tmp_path: Path,
) -> None:
    """Section 8 Prohibition 2: Source video is immutable and cannot be overwritten."""
    source_file = test_config.upload_dir / "source.mp4"
    source_file.write_bytes(b"dummy source content")

    state = StateSchema(session_id="test_session", config=test_config)
    ref = FileRef(path=str(source_file), format="mp4", width=1280, height=720)

    # 1. State immutability check
    state = apply_state_update(state, "source_video", ref)
    with pytest.raises(StateValidationError) as exc_info:
        # Attempting second mutation must raise StateValidationError
        apply_state_update(state, "source_video", ref)
    assert "immutable after initialization" in str(exc_info.value)

    # 2. Output path cannot equal source path
    kfs = [CropKeyframeModel(timestamp_ms=0, x=100, y=0, width=405, height=720)]
    with pytest.raises(ValidationError) as pydantic_exc:
        RenderVerticalClipInput(
            segment_id="seg_01",
            source_video_path=str(source_file),
            segment_start_ms=0,
            segment_end_ms=1000,
            crop_keyframes=kfs,
            output_path=str(source_file),  # Prohibited!
        )
    assert "cannot overwrite source video" in str(pydantic_exc.value)


# ---------------------------------------------------------------------------
# PROHIBITION 3: Biometric Privacy (Zero Identity Templates / Landmarks)
# ---------------------------------------------------------------------------

def test_prohibition_biometric_privacy_bounding_box_only() -> None:
    """Section 8 Prohibition 3: Bounding box tracking only; zero landmarks/identity inference."""
    schema_fields = TrackSpeakerPositionOutput.model_fields
    prohibited_fields = ["landmarks", "face_mesh", "embedding", "identity", "voiceprint", "name"]
    for field in prohibited_fields:
        assert field not in schema_fields, f"Prohibited biometric field in TrackSpeakerPositionOutput: {field}"

    bbox_fields = BoundingBoxModel.model_fields
    assert set(bbox_fields.keys()) == {"origin_x", "origin_y", "width", "height"}


# ---------------------------------------------------------------------------
# PROHIBITION 4: Path Allowlisting & Path Traversal Rejection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prohibition_path_allowlisting_and_traversal(
    test_config: RuntimeConfig,
    tmp_path: Path,
) -> None:
    """Section 8 Prohibition 4: Path traversal and external paths rejected across all tools."""
    outside_path = tmp_path / "outside" / "evil.mp4"
    traversal_path = test_config.upload_dir / ".." / "outside" / "evil.mp4"

    # Decode tool rejects outside / traversal paths
    inp_outside = DecodeAndValidateSourceInput(source_path=str(outside_path))
    res_outside = await decode_and_validate_source(inp_outside, test_config)
    assert not res_outside.success
    assert "resolves outside allowed directories" in (res_outside.error or "")

    with pytest.raises(ValidationError):
        DecodeAndValidateSourceInput(source_path=str(traversal_path))

    # Render tool rejects outside output path
    kfs = [CropKeyframeModel(timestamp_ms=0, x=0, y=0, width=405, height=720)]
    inp_render = RenderVerticalClipInput(
        segment_id="seg_01",
        source_video_path=str(test_config.upload_dir / "valid.mp4"),
        segment_start_ms=0,
        segment_end_ms=1000,
        crop_keyframes=kfs,
        output_path=str(outside_path),
    )
    res_render = await render_vertical_clip(inp_render, test_config)
    assert not res_render.success
    assert "must resolve inside" in (res_render.error or "")

    # Export tool rejects outside output path
    inp_export = ExportCropPathDataInput(
        segment_id="seg_01",
        crop_keyframes=kfs,
        output_path=str(outside_path),
        format="edl",
    )
    res_export = export_crop_path_data(inp_export, test_config)
    assert not res_export.success
    assert "resolves outside" in (res_export.error or "")


# ---------------------------------------------------------------------------
# PROHIBITION 5: No Cross-Session Persistence
# ---------------------------------------------------------------------------

def test_prohibition_ephemeral_state_no_database() -> None:
    """Section 8 Prohibition 5: No persistence layer, SQLite, or cross-session state."""
    src_dir = Path("src")
    prohibited_modules = ["checkpointing.py", "database.py", "db.py", "memory.py"]
    for path in src_dir.rglob("*.py"):
        assert path.name not in prohibited_modules, f"Prohibited persistence module: {path}"

    # Verify no persistent DB engines imported in StateSchema
    import src.state.schema as schema_mod
    content = Path(schema_mod.__file__).read_text(encoding="utf-8")
    for db in ["sqlite3", "psycopg2", "sqlalchemy", "motor"]:
        assert db not in content, f"Database library '{db}' imported in state schema"


# ---------------------------------------------------------------------------
# PROHIBITION 6: Gate-Bypass Impossibility
# ---------------------------------------------------------------------------

def test_prohibition_gate_bypass_impossibility(test_config: RuntimeConfig) -> None:
    """Section 8 Prohibition 6: Skipped segments cannot bypass to render or export."""
    state = StateSchema(session_id="test_session", config=test_config)

    # 1. verify_render_precondition rejects missing or skip decisions
    with pytest.raises(StateValidationError) as exc_missing:
        verify_render_precondition(state, "seg_01")
    assert "Precondition failed" in str(exc_missing.value)

    skip_decision = GateDecision(
        segment_id="seg_01",
        decision="skip",
        tracking_confidence=0.50,
        threshold_used=0.65,
        reason="Below confidence threshold",
    )
    state = apply_state_update(state, "confidence_gate_results", skip_decision, key="seg_01")
    with pytest.raises(StateValidationError) as exc_skip:
        verify_render_precondition(state, "seg_01")
    assert "was gated as 'skip'" in str(exc_skip.value)

    # 2. verify_export_precondition rejects exports without prior render record
    render_decision = GateDecision(
        segment_id="seg_02",
        decision="render",
        tracking_confidence=0.85,
        threshold_used=0.65,
        reason="Tracking confidence above threshold.",
    )
    state = apply_state_update(state, "confidence_gate_results", render_decision, key="seg_02")
    with pytest.raises(StateValidationError) as exc_exp:
        verify_export_precondition(state, "seg_02")
    assert "No rendered clip found" in str(exc_exp.value)


# ---------------------------------------------------------------------------
# SECTION 9.5 FAILURE SCENARIOS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failure_scenario_1_corrupt_undecodable_media(
    test_config: RuntimeConfig,
) -> None:
    """Section 9.5 Scenario 1: Corrupt media triggers permanent failure in Stage 1."""
    corrupt_file = test_config.upload_dir / "corrupt.mp4"
    corrupt_file.write_bytes(b"NOT_A_REAL_MEDIA_FILE_HEADER_GARBAGE_DATA_1234567890")

    controller = PipelineController(
        config=test_config,
        source_video_path=corrupt_file,
    )

    with pytest.raises(PermanentFailureError) as exc_info:
        await controller.execute()

    assert "Stage 1 Ingest failed" in str(exc_info.value)
    assert len(controller.state.error_logs) >= 1
    assert controller.state.error_logs[0].stage == PipelineStage.STAGE_1_INGEST_AND_VALIDATE.value


@pytest.mark.asyncio
async def test_failure_scenario_2_whisper_retry_and_fallback(
    test_config: RuntimeConfig,
) -> None:
    """Section 9.5 Scenario 2: transcribe_audio attempts retry and fallback tier on error."""
    from src.tools.transcribe_audio import transcribe_audio
    from src.tools.schemas.transcribe_audio import TranscribeAudioInput

    # Existing but invalid/corrupt audio file to trigger transcription failure and fallback retry
    invalid_audio = test_config.upload_dir / "corrupt_audio.wav"
    invalid_audio.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00corrupt")
    inp = TranscribeAudioInput(
        audio_source_path=str(invalid_audio),
        model_tier="base.en",
    )
    out = await transcribe_audio(inp, test_config)
    assert not out.success
    assert "failed after retry" in (out.error or "")


def test_failure_scenario_4_confidence_threshold_exact_boundary(
    test_config: RuntimeConfig,
) -> None:
    """Section 9.5 Scenario 4: Confidence at exact boundary resolves to render (>=), below is skip."""
    # Exactly at boundary: 0.65 == 0.65 -> render
    exact = confidence_gate_decision("seg_01", 0.65, test_config)
    assert exact.decision == "render"
    assert exact.tracking_confidence == 0.65

    # Just below boundary: 0.649999 < 0.65 -> skip
    below = confidence_gate_decision("seg_02", 0.649999, test_config)
    assert below.decision == "skip"
    assert "below threshold" in below.reason


@pytest.mark.asyncio
async def test_failure_scenario_5_circuit_breaker_micro_time_budget(
    test_config: RuntimeConfig,
) -> None:
    """Section 9.5 Scenario 5: Micro time budget trips circuit breaker gracefully."""
    fixture_video = Path("tests/fixtures/simple_case.mp4").resolve()
    tiny_cfg = test_config.model_copy(update={"time_budget_seconds": 0.0001})

    controller = PipelineController(config=tiny_cfg, source_video_path=fixture_video)
    res = await controller.execute()

    assert res["status"] in ("no_deliverables", "completed")
    # Verify error log recorded circuit breaker trip
    assert any("exhausted" in err.message.lower() for err in controller.state.error_logs)


def test_failure_scenario_6_malformed_tool_output_validation() -> None:
    """Section 9.5 Scenario 6: Malformed tool outputs rejected by strict Pydantic models."""
    # Out of range confidence score (> 1.0)
    with pytest.raises(ValidationError):
        TrackSpeakerPositionOutput(
            success=True,
            per_frame_positions=[],
            segment_confidence=1.5,  # Exceeds le=1.0
        )

    # Negative detection score (< 0.0)
    with pytest.raises(ValidationError):
        FramePositionModel(
            timestamp_ms=100,
            bounding_box=BoundingBoxModel(origin_x=10, origin_y=10, width=50, height=50),
            detection_score=-0.2,  # Below ge=0.0
        )


@pytest.mark.asyncio
async def test_failure_scenario_3_cancellation_and_partial_file_rollback(
    test_config: RuntimeConfig,
    tmp_path: Path,
) -> None:
    """Section 9.5 Scenario 3: Mid-run cancellation deletes partial files and halts without deliverables."""
    fixture_video = Path("tests/fixtures/simple_case.mp4").resolve()
    controller = PipelineController(config=test_config, source_video_path=fixture_video)

    # Simulate in-flight partial output file
    partial_file = test_config.output_dir / f"{controller.session_id}_seg_01_vertical.mp4"
    partial_file.write_bytes(b"incomplete partial render bytes")
    assert partial_file.exists()

    # Trigger cancellation
    controller.cancel()
    assert controller.cancelled

    with pytest.raises(PermanentFailureError) as exc_info:
        await controller.execute()

    assert "cancelled by user" in str(exc_info.value)
    # Rollback assertion: in-flight partial file must have been deleted!
    assert not partial_file.exists(), "In-flight partial file must be deleted on cancellation"
    assert len(controller.state.rendered_clips) == 0
    assert len(controller.state.crop_path_exports) == 0
