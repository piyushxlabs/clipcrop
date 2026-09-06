"""Unit tests for ClipCrop typed StateSchema and reducers.

Tests all verification criteria defined in:
- docs/AGENT_MASTER_PLAN.md Section 4 Step 3 & Section 9.2
- rules/state-invariants-and-tool-preconditions.md
- rules/async-io-and-pydantic-validation-mandate.md
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import RuntimeConfig
from src.exceptions import StateValidationError
from src.state import (
    BoundingBox,
    CandidateSegment,
    CropKeyframe,
    ErrorRecord,
    FileRef,
    FramePosition,
    GateDecision,
    SkipRecord,
    SmoothedPath,
    SpeechSpan,
    StateSchema,
    TrackingResult,
    TranscriptSegment,
    append_only,
    apply_state_update,
    immutable_after_init,
    last_write_wins,
    merge_by_key,
    verify_export_precondition,
    verify_render_precondition,
)


@pytest.fixture
def mock_config() -> RuntimeConfig:
    """Fixture providing a valid RuntimeConfig instance."""
    return RuntimeConfig(
        upload_dir=Path("A:/Projects/clipcrop/uploads"),
        output_dir=Path("A:/Projects/clipcrop/outputs"),
        models_dir=Path("A:/Projects/clipcrop/models"),
        ffmpeg_path="C:/path/to/ffmpeg.exe",
        ffprobe_path="C:/path/to/ffprobe.exe",
        confidence_threshold=0.65,
        max_candidates=10,
        time_budget_seconds=90,
        trace_log_dir=Path("A:/Projects/clipcrop/outputs/traces"),
    )


@pytest.fixture
def initial_state(mock_config: RuntimeConfig) -> StateSchema:
    """Fixture providing an initialized StateSchema instance."""
    return StateSchema(
        session_id="session_test_001",
        config=mock_config,
    )


# ---------------------------------------------------------------------------
# Reducer: append_only Tests
# ---------------------------------------------------------------------------


def test_append_only_preserves_existing_entries_under_repeated_calls() -> None:
    """Assert append_only never drops existing items and appends new ones."""
    seg1 = TranscriptSegment(start_ms=0, end_ms=1000, text="Hello world")
    seg2 = TranscriptSegment(start_ms=1000, end_ms=2500, text="This is clipcrop")
    seg3 = TranscriptSegment(start_ms=2500, end_ms=4000, text="Testing append only")

    # Initial empty list
    items: list[TranscriptSegment] = []
    res1 = append_only(items, seg1)
    assert len(res1) == 1
    assert res1[0] == seg1

    # Second append
    res2 = append_only(res1, seg2)
    assert len(res2) == 2
    assert res2[0] == seg1
    assert res2[1] == seg2

    # Third append with a list of items
    res3 = append_only(res2, [seg3])
    assert len(res3) == 3
    assert res3 == [seg1, seg2, seg3]

    # Original lists should not be mutated (immutability of inputs)
    assert len(items) == 0
    assert len(res1) == 1
    assert len(res2) == 2


# ---------------------------------------------------------------------------
# Reducer: merge_by_key Tests
# ---------------------------------------------------------------------------


def test_merge_by_key_never_clobbers_unrelated_segment_entries() -> None:
    """Assert writing segment B never alters or clobbers segment A."""
    box_a = BoundingBox(origin_x=100, origin_y=100, width=200, height=200)
    pos_a = FramePosition(timestamp_ms=0, bounding_box=box_a, detection_score=0.95)
    track_a = TrackingResult(
        segment_id="seg_01",
        success=True,
        per_frame_positions=[pos_a],
        segment_confidence=0.92,
    )

    box_b = BoundingBox(origin_x=300, origin_y=150, width=250, height=250)
    pos_b = FramePosition(timestamp_ms=0, bounding_box=box_b, detection_score=0.88)
    track_b = TrackingResult(
        segment_id="seg_02",
        success=True,
        per_frame_positions=[pos_b],
        segment_confidence=0.85,
    )

    results: dict[str, TrackingResult] = {}

    # Merge segment A
    results_after_a = merge_by_key(results, ("seg_01", track_a))
    assert len(results_after_a) == 1
    assert results_after_a["seg_01"] == track_a

    # Merge segment B
    results_after_b = merge_by_key(results_after_a, ("seg_02", track_b))
    assert len(results_after_b) == 2
    assert results_after_b["seg_01"] == track_a  # Segment A remains unchanged
    assert results_after_b["seg_02"] == track_b

    # Update segment A with new data
    track_a_updated = TrackingResult(
        segment_id="seg_01",
        success=True,
        per_frame_positions=[pos_a],
        segment_confidence=0.99,
    )
    results_updated = merge_by_key(results_after_b, {"seg_01": track_a_updated})
    assert len(results_updated) == 2
    assert results_updated["seg_01"].segment_confidence == 0.99
    assert results_updated["seg_02"].segment_confidence == 0.85  # Segment B still untouched


# ---------------------------------------------------------------------------
# Reducer: last_write_wins Tests
# ---------------------------------------------------------------------------


def test_last_write_wins_atomically_replaces_and_enforces_cap() -> None:
    """Assert last_write_wins replaces candidate_segments list and caps at 10."""
    cand1 = CandidateSegment(
        segment_id="seg_01",
        start_ms=0,
        end_ms=5000,
        score=0.85,
        pause_pattern_score=0.9,
        energy_peak_score=0.8,
        speaking_rate_variance_score=0.7,
        keyword_density_score=0.85,
        rank=1,
    )
    cand2 = CandidateSegment(
        segment_id="seg_02",
        start_ms=5000,
        end_ms=10000,
        score=0.75,
        pause_pattern_score=0.8,
        energy_peak_score=0.7,
        speaking_rate_variance_score=0.6,
        keyword_density_score=0.75,
        rank=2,
    )

    initial_list = [cand1]
    new_list = [cand2]

    replaced = last_write_wins(initial_list, new_list, max_candidates=10)
    assert replaced == [cand2]
    assert replaced is not new_list  # Fresh copy

    # Test candidate cap enforcement (> 10 items)
    too_many_candidates = [
        CandidateSegment(
            segment_id=f"seg_{i:02d}",
            start_ms=i * 1000,
            end_ms=(i + 1) * 1000,
            score=0.5,
            pause_pattern_score=0.5,
            energy_peak_score=0.5,
            speaking_rate_variance_score=0.5,
            keyword_density_score=0.5,
            rank=i + 1,
        )
        for i in range(11)
    ]
    with pytest.raises(StateValidationError, match="exceeds maximum allowed"):
        last_write_wins([], too_many_candidates, max_candidates=10)


# ---------------------------------------------------------------------------
# Reducer: immutable_after_init Tests
# ---------------------------------------------------------------------------


def test_immutable_after_init_raises_on_second_write() -> None:
    """Assert immutable_after_init allows initial write and raises on subsequent writes."""
    val1 = "initial_session_id"
    val2 = "attempted_new_session_id"

    # Initial write to empty field succeeds
    first_write = immutable_after_init(None, val1, field_name="session_id")
    assert first_write == val1

    # Second write raises StateValidationError
    with pytest.raises(StateValidationError, match="immutable after initialization"):
        immutable_after_init(first_write, val2, field_name="session_id")


# ---------------------------------------------------------------------------
# Direct Assignment Protection Tests
# ---------------------------------------------------------------------------


def test_direct_assignment_on_stateschema_raises_state_validation_error(
    initial_state: StateSchema,
) -> None:
    """Assert direct assignment to StateSchema fields raises StateValidationError."""
    with pytest.raises(StateValidationError, match="Direct assignment to field 'session_id' on StateSchema is prohibited"):
        initial_state.session_id = "new_session"

    with pytest.raises(StateValidationError, match="Direct assignment to field 'candidate_segments' on StateSchema is prohibited"):
        initial_state.candidate_segments = []

    with pytest.raises(StateValidationError, match="Direct assignment to field 'source_video' on StateSchema is prohibited"):
        initial_state.source_video = FileRef(path="A:/some/path.mp4")


# ---------------------------------------------------------------------------
# apply_state_update Dispatcher Tests
# ---------------------------------------------------------------------------


def test_apply_state_update_routes_correctly(
    initial_state: StateSchema,
    mock_config: RuntimeConfig,
) -> None:
    """Assert apply_state_update updates fields through correct reducers."""
    # 1. immutable_after_init on source_video
    video_ref = FileRef(
        path="A:/Projects/clipcrop/uploads/video.mp4",
        duration_seconds=60.0,
        has_video_track=True,
        has_audio_track=True,
    )
    apply_state_update(initial_state, "source_video", video_ref)
    assert initial_state.source_video == video_ref

    # Second write to source_video must raise
    with pytest.raises(StateValidationError, match="immutable after initialization"):
        apply_state_update(
            initial_state, "source_video", FileRef(path="A:/Projects/clipcrop/uploads/another.mp4")
        )

    # 2. append_only on transcript_segments
    t_seg = TranscriptSegment(start_ms=0, end_ms=1500, text="Testing dispatcher")
    apply_state_update(initial_state, "transcript_segments", t_seg)
    assert len(initial_state.transcript_segments) == 1
    assert initial_state.transcript_segments[0] == t_seg

    # 3. merge_by_key on confidence_gate_results
    gate_decision = GateDecision(
        segment_id="seg_01",
        tracking_confidence=0.88,
        threshold_used=0.65,
        decision="render",
        reason="tracking confidence 0.88 >= 0.65",
    )
    apply_state_update(
        initial_state, "confidence_gate_results", gate_decision, key="seg_01"
    )
    assert "seg_01" in initial_state.confidence_gate_results
    assert initial_state.confidence_gate_results["seg_01"] == gate_decision

    # 4. last_write_wins on candidate_segments
    cand = CandidateSegment(
        segment_id="seg_01",
        start_ms=0,
        end_ms=5000,
        score=0.9,
        pause_pattern_score=0.9,
        energy_peak_score=0.9,
        speaking_rate_variance_score=0.9,
        keyword_density_score=0.9,
        rank=1,
    )
    apply_state_update(initial_state, "candidate_segments", [cand])
    assert len(initial_state.candidate_segments) == 1
    assert initial_state.candidate_segments[0].segment_id == "seg_01"


# ---------------------------------------------------------------------------
# Precondition Verification Tests
# ---------------------------------------------------------------------------


def test_verify_render_and_export_preconditions(initial_state: StateSchema) -> None:
    """Assert render and export preconditions enforce confidence gating and deliverable pairing."""
    # Precondition fails when no gate decision exists
    with pytest.raises(StateValidationError, match="No confidence gate decision found"):
        verify_render_precondition(initial_state, "seg_01")

    # Set gate decision to "skip"
    skip_decision = GateDecision(
        segment_id="seg_01",
        tracking_confidence=0.40,
        threshold_used=0.65,
        decision="skip",
        reason="confidence 0.40 < 0.65",
    )
    apply_state_update(initial_state, "confidence_gate_results", skip_decision, key="seg_01")

    with pytest.raises(StateValidationError, match="gated as 'skip'"):
        verify_render_precondition(initial_state, "seg_01")

    # Export precondition also fails
    with pytest.raises(StateValidationError, match="gated as 'skip'"):
        verify_export_precondition(initial_state, "seg_01")

    # Set gate decision to "render" for seg_02
    render_decision = GateDecision(
        segment_id="seg_02",
        tracking_confidence=0.85,
        threshold_used=0.65,
        decision="render",
        reason="confidence 0.85 >= 0.65",
    )
    apply_state_update(initial_state, "confidence_gate_results", render_decision, key="seg_02")

    # Render precondition passes
    verify_render_precondition(initial_state, "seg_02")

    # Export precondition fails before render_vertical_clip produces a clip
    with pytest.raises(StateValidationError, match="No rendered clip found"):
        verify_export_precondition(initial_state, "seg_02")

    # Add rendered clip for seg_02
    clip_ref = FileRef(
        path="A:/Projects/clipcrop/outputs/clip_seg_02.mp4",
        segment_id="seg_02",
        duration_seconds=15.0,
    )
    apply_state_update(initial_state, "rendered_clips", clip_ref)

    # Now export precondition passes!
    verify_export_precondition(initial_state, "seg_02")


# ---------------------------------------------------------------------------
# Strict Pydantic V2 Validation Tests
# ---------------------------------------------------------------------------


def test_strict_pydantic_validation_rejects_malformed_types() -> None:
    """Assert strict type validation rejects loose type coercions."""
    # Strict int validation fails on string float
    with pytest.raises(ValidationError):
        TranscriptSegment(start_ms="invalid", end_ms=1000, text="hello")  # type: ignore[arg-type]

    # Negative rank fails
    with pytest.raises(ValidationError):
        CandidateSegment(
            segment_id="seg_01",
            start_ms=0,
            end_ms=1000,
            score=0.5,
            pause_pattern_score=0.5,
            energy_peak_score=0.5,
            speaking_rate_variance_score=0.5,
            keyword_density_score=0.5,
            rank=0,  # ge=1 violated
        )
