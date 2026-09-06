"""Integration test suite for the deterministic reasoning loop and end-to-end execution.

Verifies:
- docs/AGENT_MASTER_PLAN.md Section 6 & Section 10 (Step 12)
- docs/AGENT_MASTER_PLAN.md Section 9.3 & 9.4 ("Agent Is Working" Success Criteria)
- Full end-to-end execution on simple_case.mp4 fixture with real models and FFmpeg
- Paired deliverable contract (1:1 vertical clip paired with CMX 3600 EDL)
- Determinism repeatability regression across successive runs
- Silence-over-guessing policy on silent media
- Confidence gate skip branch under high threshold
- Time budget circuit breaker enforcement
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from src.agents.pipeline_controller import PipelineController
from src.config import RuntimeConfig, load_config_from_env
from src.exceptions import PermanentFailureError


@pytest.fixture
def test_config(tmp_path: Path) -> RuntimeConfig:
    """Fixture providing isolated environment config with real models and ffmpeg."""
    base_cfg = load_config_from_env()
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    trace_log_dir = tmp_path / "traces"
    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    trace_log_dir.mkdir(parents=True, exist_ok=True)

    return RuntimeConfig(
        upload_dir=upload_dir,
        output_dir=output_dir,
        models_dir=base_cfg.models_dir,
        trace_log_dir=trace_log_dir,
        ffmpeg_path=base_cfg.ffmpeg_path,
        ffprobe_path=base_cfg.ffprobe_path,
        confidence_threshold=0.65,
        max_candidates=10,
        time_budget_seconds=90,
    )


@pytest.fixture
def simple_case_path() -> Path:
    """Fixture returning the verified path to simple_case.mp4."""
    path = Path("tests/fixtures/simple_case.mp4").resolve()
    assert path.is_file(), "simple_case.mp4 fixture must exist."
    return path


@pytest.mark.asyncio
async def test_simple_case_end_to_end_real_pipeline(
    test_config: RuntimeConfig,
    simple_case_path: Path,
) -> None:
    """Section 9.4 Success Criteria Test: Complete end-to-end execution on Simple Case fixture."""
    controller = PipelineController(
        config=test_config,
        source_video_path=simple_case_path,
    )

    result = await controller.execute()

    # 1. Pipeline terminates with completed status
    assert result["status"] == "completed"
    assert result["rendered_count"] == 1
    assert result["skipped_count"] == 0
    assert len(result["deliverables"]) == 1

    deliverable = result["deliverables"][0]
    segment_id = deliverable["segment_id"]
    clip_path = Path(deliverable["clip_path"])
    export_path = Path(deliverable["export_path"])

    # 2. Both deliverables exist and are non-empty
    assert clip_path.is_file() and clip_path.stat().st_size > 0
    assert export_path.is_file() and export_path.stat().st_size > 0

    # 3. Probe rendered video with ffprobe to verify 1080x1920 9:16 vertical resolution
    probe_cmd = [
        test_config.ffprobe_path,
        "-v", "error",
        "-show_entries", "stream=width,height,codec_type",
        "-of", "json",
        str(clip_path),
    ]
    probe_out = subprocess.check_output(probe_cmd)
    probe_json = json.loads(probe_out)

    video_stream = next((s for s in probe_json["streams"] if s["codec_type"] == "video"), None)
    audio_stream = next((s for s in probe_json["streams"] if s["codec_type"] == "audio"), None)

    assert video_stream is not None, "Rendered vertical clip must contain a video track."
    assert video_stream["width"] == 1080
    assert video_stream["height"] == 1920
    assert audio_stream is not None, "Rendered vertical clip must preserve source audio track."

    # 4. Read CMX 3600 EDL export file to verify format and non-drop timecodes
    edl_content = export_path.read_text(encoding="utf-8")
    assert "TITLE: CLIPCROP_EXPORT" in edl_content
    assert "FCM: NON-DROP FRAME" in edl_content
    assert f"* FROM CLIP NAME: {segment_id}" in edl_content
    assert "001  AX       V     C" in edl_content
    assert "* KEYFRAME" in edl_content

    # 5. Verify central StateSchema invariants
    state = controller.state
    assert state.source_video is not None
    assert len(state.transcript_segments) >= 1
    assert len(state.vad_segments) >= 1
    assert len(state.candidate_segments) == 1
    assert segment_id in state.tracking_results
    assert state.tracking_results[segment_id].success is True
    assert state.confidence_gate_results[segment_id].decision == "render"
    assert segment_id in state.crop_paths
    assert len(state.rendered_clips) == 1
    assert len(state.crop_path_exports) == 1
    assert len(state.skipped_segments) == 0


@pytest.mark.asyncio
async def test_pipeline_determinism_regression(
    test_config: RuntimeConfig,
    simple_case_path: Path,
) -> None:
    """Section 9.3 Determinism Regression Test: Assert identical results across successive runs."""
    controller_1 = PipelineController(
        config=test_config,
        source_video_path=simple_case_path,
        session_id="det_run_1",
    )
    result_1 = await controller_1.execute()

    controller_2 = PipelineController(
        config=test_config,
        source_video_path=simple_case_path,
        session_id="det_run_2",
    )
    result_2 = await controller_2.execute()

    # Verify identical candidate segments
    cand_1 = [c.model_dump(exclude={"segment_id"}) for c in controller_1.state.candidate_segments]
    cand_2 = [c.model_dump(exclude={"segment_id"}) for c in controller_2.state.candidate_segments]
    assert cand_1 == cand_2, "Candidate segments must be strictly deterministic."

    # Verify identical confidence gate outcomes
    gate_1 = controller_1.state.confidence_gate_results["seg_01"]
    gate_2 = controller_2.state.confidence_gate_results["seg_01"]
    assert gate_1.decision == gate_2.decision
    assert gate_1.tracking_confidence == gate_2.tracking_confidence

    # Verify identical crop keyframes
    kfs_1 = [k.model_dump() for k in controller_1.state.crop_paths["seg_01"].crop_keyframes]
    kfs_2 = [k.model_dump() for k in controller_2.state.crop_paths["seg_01"].crop_keyframes]
    assert kfs_1 == kfs_2, "Smoothed crop keyframes must be strictly deterministic."


@pytest.mark.asyncio
async def test_silent_audio_edge_case_zero_candidates(
    test_config: RuntimeConfig,
    tmp_path: Path,
) -> None:
    """Section 9.3 Silence-Over-Guessing Test: Silent media terminates with zero_candidates failure."""
    # Generate a purely silent video with no speech inside upload_dir
    silent_video = test_config.upload_dir / "silent_case.mp4"
    cmd = [
        test_config.ffmpeg_path, "-y",
        "-f", "lavfi", "-i", "color=c=black:s=640x360:r=25:d=3",
        "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
        "-c:v", "libx264", "-c:a", "aac",
        "-t", "3",
        str(silent_video),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    controller = PipelineController(
        config=test_config,
        source_video_path=silent_video,
    )

    with pytest.raises(PermanentFailureError) as exc_info:
        await controller.execute()

    assert "zero_candidates" in str(exc_info.value)
    assert len(controller.state.rendered_clips) == 0
    assert len(controller.state.crop_path_exports) == 0


@pytest.mark.asyncio
async def test_low_confidence_skip_branch(
    test_config: RuntimeConfig,
    simple_case_path: Path,
) -> None:
    """Section 9.3 Low-Confidence Skip Test: Segment below threshold is skipped and never rendered."""
    # Create out-of-frame fixture: real speech audio over a black screen (no detectable face)
    out_of_frame_video = test_config.upload_dir / "out_of_frame.mp4"
    cmd = [
        test_config.ffmpeg_path, "-y",
        "-f", "lavfi", "-i", "color=c=black:s=640x360:r=25",
        "-i", str(simple_case_path),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-c:a", "copy",
        "-shortest",
        str(out_of_frame_video),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    controller = PipelineController(
        config=test_config,
        source_video_path=out_of_frame_video,
    )

    result = await controller.execute()

    assert result["rendered_count"] == 0
    assert result["skipped_count"] == 1
    assert len(result["deliverables"]) == 0

    assert len(controller.state.skipped_segments) == 1
    assert controller.state.skipped_segments[0].segment_id == "seg_01"
    assert controller.state.confidence_gate_results["seg_01"].decision == "skip"

    # Invariant: No clips or exports delivered
    assert len(controller.state.rendered_clips) == 0
    assert len(controller.state.crop_path_exports) == 0


@pytest.mark.asyncio
async def test_circuit_breaker_time_budget(
    test_config: RuntimeConfig,
    simple_case_path: Path,
) -> None:
    """Section 6 Circuit Breaker Test: Exceeded time budget halts gracefully without hang."""
    tiny_budget_config = test_config.model_copy(update={"time_budget_seconds": 0.001})

    controller = PipelineController(
        config=tiny_budget_config,
        source_video_path=simple_case_path,
    )

    result = await controller.execute()

    assert result["status"] == "no_deliverables"
    assert any("time budget" in err["message"].lower() for err in result["error_logs"])
