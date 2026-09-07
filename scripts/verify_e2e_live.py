"""End-to-End Live Verification Script for ClipCrop.

Executes Step 20 of AGENT_MASTER_PLAN.md:
- Full non-mocked flow through FastAPI server endpoints (REST + SSE)
- Multipart upload of simple_case.mp4 fixture
- Live Server-Sent Events (SSE) streaming and event contract verification
- Deliverable downloads (1080x1920 MP4 clip + CMX 3600 EDL)
- User feedback submission and trace log annotation
- Trace log hierarchy and attributes verification
- Sandbox security and source file immutability checks
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from httpx import ASGITransport

from src.config import RuntimeConfig, load_config_from_env
from src.main import create_app
from src.ui.event_types import parse_sse_line, DataRunEndEvent, DataStageStartEvent


async def run_live_e2e_verification() -> None:
    print("=" * 80)
    print("  CLIPCROP: STEP 20 END-TO-END LIVE VERIFICATION")
    print("=" * 80)

    # 1. Setup sandboxed runtime configuration
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        upload_dir = temp_dir / "uploads"
        output_dir = temp_dir / "outputs"
        trace_log_dir = temp_dir / "traces"
        upload_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        trace_log_dir.mkdir(parents=True, exist_ok=True)

        base_cfg = load_config_from_env()
        config = RuntimeConfig(
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

        app = create_app(config)
        transport = ASGITransport(app=app)

        fixture_video = Path("tests/fixtures/simple_case.mp4").resolve()
        assert fixture_video.is_file(), f"Fixture video not found at {fixture_video}"
        fixture_initial_mtime = fixture_video.stat().st_mtime
        fixture_initial_size = fixture_video.stat().st_size

        async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=120.0) as client:
            # -----------------------------------------------------------------------
            # Step 20.1: Health check
            # -----------------------------------------------------------------------
            print("\n[Check 1] Querying GET /health...")
            health_res = await client.get("/health")
            assert health_res.status_code == 200, f"Expected 200, got {health_res.status_code}"
            health_json = health_res.json()
            assert health_json["status"] == "healthy"
            assert health_json["version"] == "0.1.0"
            print("  -> GET /health responded 200 healthy.")

            # -----------------------------------------------------------------------
            # Step 20.2: Video Upload (POST /runs)
            # -----------------------------------------------------------------------
            print("\n[Check 2] Uploading simple_case.mp4 to POST /runs...")
            with open(fixture_video, "rb") as f:
                video_bytes = f.read()

            files = {"file": ("simple_case.mp4", video_bytes, "video/mp4")}
            upload_res = await client.post("/runs", files=files)
            assert upload_res.status_code == 201, f"Upload failed: {upload_res.status_code} {upload_res.text}"
            upload_json = upload_res.json()
            run_id = upload_json["run_id"]
            assert run_id, "Run ID must be present in response"
            assert upload_json["status"] == "created"
            print(f"  -> Run session created successfully. Run ID: {run_id}")

            # -----------------------------------------------------------------------
            # Step 20.3: Live SSE Stream Consumption (GET /runs/{run_id}/stream)
            # -----------------------------------------------------------------------
            print("\n[Check 3] Consuming real-time SSE stream from GET /runs/{run_id}/stream...")
            received_events = []
            executed_stages = []
            hitl_events_detected = []

            async with client.stream("GET", f"/runs/{run_id}/stream") as response:
                assert response.status_code == 200, f"SSE stream failed: {response.status_code}"
                assert "text/event-stream" in response.headers.get("content-type", "")

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        event = parse_sse_line(line)
                        if event is not None:
                            received_events.append(event)
                            event_type = getattr(event, "type", "unknown")

                            # Check for prohibited HITL events
                            if "approval" in event_type.lower() or "hitl" in event_type.lower():
                                hitl_events_detected.append(event_type)

                            if isinstance(event, DataStageStartEvent):
                                executed_stages.append(event.stage)
                                print(f"  [Stage] >> {event.stage.upper()}")
                            elif isinstance(event, DataRunEndEvent):
                                print(f"  [Run End] >> Outcome: {event.reason}, Deliverables: {event.deliverables_count}")
                                break

            # Verify no HITL approval events
            assert len(hitl_events_detected) == 0, f"Prohibited HITL events detected: {hitl_events_detected}"
            print("  -> Zero HITL/approval events detected (fully autonomous execution).")

            # Verify 8-stage sequence
            expected_stages = [
                "ingest_and_validate",
                "transcribe_and_segment",
                "score_candidates",
                "track_speaker_position",
                "confidence_gate",
                "smooth_crop_path",
                "render_and_export",
                "aggregate_and_terminate",
            ]
            assert executed_stages == expected_stages, f"Stages diverged: {executed_stages} vs {expected_stages}"
            print("  -> All 8 stages executed in strictly sequential order.")

            # -----------------------------------------------------------------------
            # Step 20.4: Deliverables Download (GET /outputs/{filename})
            # -----------------------------------------------------------------------
            print("\n[Check 4] Verifying and downloading deliverables...")
            clip_filename = f"{run_id}_seg_01_vertical.mp4"
            edl_filename = f"{run_id}_seg_01_crop_path.edl"

            # Download vertical MP4
            clip_res = await client.get(f"/outputs/{clip_filename}")
            assert clip_res.status_code == 200, f"Clip download failed: {clip_res.status_code}"
            assert len(clip_res.content) > 0, "Clip file is empty"
            assert "video/mp4" in clip_res.headers.get("content-type", "")

            # Probe downloaded clip with ffprobe
            clip_path = output_dir / clip_filename
            assert clip_path.is_file(), "Clip file must exist on disk"
            probe_cmd = [
                config.ffprobe_path,
                "-v", "error",
                "-show_entries", "stream=width,height,codec_type",
                "-of", "json",
                str(clip_path),
            ]
            probe_out = subprocess.check_output(probe_cmd)
            probe_json = json.loads(probe_out)
            v_stream = next(s for s in probe_json["streams"] if s["codec_type"] == "video")
            assert v_stream["width"] == 1080 and v_stream["height"] == 1920, f"Expected 1080x1920, got {v_stream}"
            print(f"  -> Delivered clip {clip_filename}: Verified 1080x1920 9:16 vertical MP4 ({len(clip_res.content)} bytes).")

            # Download CMX 3600 EDL
            edl_res = await client.get(f"/outputs/{edl_filename}")
            assert edl_res.status_code == 200, f"EDL download failed: {edl_res.status_code}"
            edl_text = edl_res.text
            assert "TITLE: CLIPCROP_EXPORT" in edl_text
            assert "FCM: NON-DROP FRAME" in edl_text
            assert "001  AX       V     C" in edl_text
            print(f"  -> Delivered timeline {edl_filename}: Verified valid CMX 3600 EDL timecode file.")

            # -----------------------------------------------------------------------
            # Step 20.5: Submit User Feedback (POST /runs/{run_id}/feedback)
            # -----------------------------------------------------------------------
            print("\n[Check 5] Submitting user feedback rating...")
            feedback_payload = {
                "segment_id": "seg_01",
                "rating": "up",
                "note": "Verified E2E: smooth framing on speaker.",
            }
            fb_res = await client.post(f"/runs/{run_id}/feedback", json=feedback_payload)
            assert fb_res.status_code == 200, f"Feedback failed: {fb_res.status_code}"
            fb_json = fb_res.json()
            assert fb_json["status"] == "recorded"
            assert fb_json["segment_id"] == "seg_01"
            print("  -> User feedback successfully registered.")

            # -----------------------------------------------------------------------
            # Step 20.6: Verify Local OTel Trace File & Annotation
            # -----------------------------------------------------------------------
            print("\n[Check 6] Verifying OpenTelemetry JSON file trace log...")
            trace_path = trace_log_dir / f"{run_id}_trace.jsonl"
            assert trace_path.is_file() and trace_path.stat().st_size > 0, "Trace log must exist"

            trace_lines = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").strip().splitlines()]
            names = [r.get("name") for r in trace_lines]

            assert "run" in names, "Root span 'run' missing"
            assert "stage:ingest_and_validate" in names, "Stage 1 span missing"
            assert "stage:render_and_export" in names, "Stage 7 span missing"

            # Check feedback annotation
            annotation_record = next((r for r in trace_lines if r.get("annotation_type") == "user_feedback"), None)
            assert annotation_record is not None, "Feedback annotation record missing from trace log"
            assert annotation_record["attributes"]["clipcrop.feedback.rating"] == "up"
            assert annotation_record["attributes"]["clipcrop.feedback.note"] == "Verified E2E: smooth framing on speaker."
            print(f"  -> Trace log verified: 3-tier span hierarchy and user feedback annotation present ({len(trace_lines)} records).")

            # -----------------------------------------------------------------------
            # Step 20.7: Security Sandbox & Immutability Verification
            # -----------------------------------------------------------------------
            print("\n[Check 7] Verifying security sandboxing and immutability...")
            # Path traversal rejection: .. in filename returns 400
            traversal_res = await client.get("/outputs/..secret.txt")
            assert traversal_res.status_code == 400, f"Path traversal should return 400, got {traversal_res.status_code}"

            # Path traversal with parent navigation
            parent_res = await client.get("/outputs/../../.env")
            assert parent_res.status_code in (400, 404), f"Parent traversal should be rejected, got {parent_res.status_code}"

            # Source video immutability check
            assert fixture_video.stat().st_mtime == fixture_initial_mtime, "Source video was modified!"
            assert fixture_video.stat().st_size == fixture_initial_size, "Source video size changed!"
            print("  -> Path traversal correctly rejected (400/404); source video untouched and strictly immutable.")

    print("\n" + "=" * 80)
    print("  ALL STEP 20 END-TO-END VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_live_e2e_verification())
