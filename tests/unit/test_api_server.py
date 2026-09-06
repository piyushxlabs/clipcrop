"""Unit and integration test suite for ClipCrop FastAPI backend in src/main.py.

Verifies:
- GET /health responds 200 with expected schema.
- POST /runs receives file uploads, enforces extensions/sizes, and initialises sessions.
- GET /runs/{run_id}/stream streams SSE events with valid headers.
- POST /runs/{run_id}/cancel triggers controller emergency stop.
- POST /runs/{run_id}/feedback records user ratings and updates trace logs.
- GET /outputs/{filename} securely downloads deliverables and rejects path traversal.
"""

from __future__ import annotations

import io
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from src.config import RuntimeConfig, load_config_from_env
from src.main import RUN_REGISTRY, create_app


@pytest.fixture
def test_config(tmp_path: Path) -> RuntimeConfig:
    """Fixture providing isolated sandboxed test directories."""
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    trace_dir = tmp_path / "traces"
    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    trace_dir.mkdir(parents=True, exist_ok=True)

    base_cfg = load_config_from_env()
    return base_cfg.model_copy(
        update={
            "upload_dir": upload_dir,
            "output_dir": output_dir,
            "trace_log_dir": trace_dir,
            "confidence_threshold": 0.65,
            "max_candidates": 10,
            "time_budget_seconds": 90,
        }
    )


@pytest.fixture
def app_instance(test_config: RuntimeConfig):
    """FastAPI test application instance with isolated config."""
    RUN_REGISTRY.clear()
    return create_app(config=test_config)


@pytest.fixture
def client(app_instance) -> TestClient:
    """Synchronous test client."""
    return TestClient(app_instance)


# ---------------------------------------------------------------------------
# 1. Health Check Endpoint
# ---------------------------------------------------------------------------

def test_get_health_responds_200(client: TestClient) -> None:
    """GET /health responds 200 with status='healthy' and version='0.1.0'."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"


# ---------------------------------------------------------------------------
# 2. Run Creation & Upload Handling
# ---------------------------------------------------------------------------

def test_post_runs_successful_upload(
    client: TestClient,
    test_config: RuntimeConfig,
) -> None:
    """POST /runs successfully uploads a valid video file and creates a session."""
    dummy_video_bytes = b"FAKE_MP4_CONTENT_1234567890"
    files = {"file": ("test_speaker.mp4", io.BytesIO(dummy_video_bytes), "video/mp4")}

    response = client.post("/runs", files=files)
    assert response.status_code == 201
    data = response.json()
    assert "run_id" in data
    assert data["status"] == "created"
    assert data["source_filename"] == "test_speaker.mp4"

    run_id = data["run_id"]
    assert run_id in RUN_REGISTRY
    saved_file = test_config.upload_dir / f"{run_id}_test_speaker.mp4"
    assert saved_file.is_file()
    assert saved_file.read_bytes() == dummy_video_bytes


def test_post_runs_rejects_unsupported_file_extension(client: TestClient) -> None:
    """POST /runs rejects disallowed file formats (e.g., .txt, .exe)."""
    files = {"file": ("malicious.exe", io.BytesIO(b"MZ..."), "application/x-msdownload")}
    response = client.post("/runs", files=files)
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_post_runs_rejects_empty_file(client: TestClient) -> None:
    """POST /runs rejects 0-byte uploaded files."""
    files = {"file": ("empty.mp4", io.BytesIO(b""), "video/mp4")}
    response = client.post("/runs", files=files)
    assert response.status_code == 400
    assert "empty (0 bytes)" in response.json()["detail"]


def test_post_runs_sanitizes_path_traversal_filename(
    client: TestClient,
    test_config: RuntimeConfig,
) -> None:
    """POST /runs sanitizes filename containing directory traversal sequences."""
    files = {"file": ("../../etc/evil.mp4", io.BytesIO(b"DUMMY"), "video/mp4")}
    response = client.post("/runs", files=files)
    assert response.status_code == 201
    data = response.json()
    run_id = data["run_id"]

    # Traversal parts must be stripped; file must be strictly inside upload_dir
    saved_path = test_config.upload_dir / f"{run_id}_evil.mp4"
    assert saved_path.is_file()


# ---------------------------------------------------------------------------
# 3. Emergency Stop / Cancellation Endpoint
# ---------------------------------------------------------------------------

def test_post_cancel_run_success(client: TestClient) -> None:
    """POST /runs/{run_id}/cancel cancels an active run session."""
    # Create run first
    files = {"file": ("video.mp4", io.BytesIO(b"VALID_CONTENT"), "video/mp4")}
    create_resp = client.post("/runs", files=files)
    run_id = create_resp.json()["run_id"]

    cancel_resp = client.post(f"/runs/{run_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelling"
    assert RUN_REGISTRY[run_id].controller.cancelled is True


def test_post_cancel_run_not_found(client: TestClient) -> None:
    """POST /runs/{run_id}/cancel returns 404 for unknown run_id."""
    response = client.post("/runs/unknown-uuid-12345/cancel")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 4. Feedback Endpoint
# ---------------------------------------------------------------------------

def test_post_feedback_success(
    client: TestClient,
    test_config: RuntimeConfig,
) -> None:
    """POST /runs/{run_id}/feedback records satisfaction rating and note."""
    files = {"file": ("video.mp4", io.BytesIO(b"VALID_CONTENT"), "video/mp4")}
    create_resp = client.post("/runs", files=files)
    run_id = create_resp.json()["run_id"]

    payload = {
        "segment_id": "seg_01",
        "rating": "up",
        "note": "Camera motion is perfectly centered.",
    }
    feedback_resp = client.post(f"/runs/{run_id}/feedback", json=payload)
    assert feedback_resp.status_code == 200
    data = feedback_resp.json()
    assert data["status"] == "recorded"
    assert data["segment_id"] == "seg_01"

    # Verify stored in session memory
    session = RUN_REGISTRY[run_id]
    assert session.feedback["seg_01"]["rating"] == "up"

    # Verify annotation appended to trace log file
    trace_file = test_config.trace_log_dir / f"{run_id}_trace.jsonl"
    assert trace_file.is_file()
    content = trace_file.read_text(encoding="utf-8")
    assert "Camera motion is perfectly centered." in content


def test_post_feedback_validation_error(client: TestClient) -> None:
    """POST /runs/{run_id}/feedback rejects invalid ratings."""
    files = {"file": ("video.mp4", io.BytesIO(b"VALID_CONTENT"), "video/mp4")}
    create_resp = client.post("/runs", files=files)
    run_id = create_resp.json()["run_id"]

    # Rating must be strictly "up" or "down"
    payload = {"segment_id": "seg_01", "rating": "neutral"}
    resp = client.post(f"/runs/{run_id}/feedback", json=payload)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 5. Deliverable Download Endpoint
# ---------------------------------------------------------------------------

def test_get_deliverable_download(
    client: TestClient,
    test_config: RuntimeConfig,
) -> None:
    """GET /outputs/{filename} serves files from output_dir and rejects traversal."""
    deliverable = test_config.output_dir / "seg_01_vertical.mp4"
    deliverable.write_bytes(b"DELIVERABLE_MP4_BYTES")

    resp = client.get("/outputs/seg_01_vertical.mp4")
    assert resp.status_code == 200
    assert resp.content == b"DELIVERABLE_MP4_BYTES"
    assert "video/mp4" in resp.headers.get("content-type", "")

    # Non-existent file
    assert client.get("/outputs/non_existent.mp4").status_code == 404

    # Traversal rejection
    assert client.get("/outputs/..secret.txt").status_code == 400


# ---------------------------------------------------------------------------
# 6. SSE Streaming Endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_stream_not_found(app_instance) -> None:
    """GET /runs/{run_id}/stream returns 404 for unknown run."""
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/runs/unknown-id/stream")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_stream_sse_headers_and_events(
    app_instance,
    test_config: RuntimeConfig,
) -> None:
    """GET /runs/{run_id}/stream provides text/event-stream with valid SSE messages."""
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a run first using simple_case fixture
        fixture_path = Path("tests/fixtures/simple_case.mp4").resolve()
        with open(fixture_path, "rb") as f:
            upload_resp = await ac.post("/runs", files={"file": ("simple.mp4", f, "video/mp4")})
        assert upload_resp.status_code == 201
        run_id = upload_resp.json()["run_id"]

        # Connect to SSE stream
        async with ac.stream("GET", f"/runs/{run_id}/stream") as stream_resp:
            assert stream_resp.status_code == 200
            assert "text/event-stream" in stream_resp.headers["content-type"]
            assert stream_resp.headers.get("cache-control") == "no-cache"

            events_collected = []
            async for line in stream_resp.aiter_lines():
                if line.startswith("data: "):
                    events_collected.append(line)
                    # We can read until data-run-end or collect first few events
                    if "data-run-end" in line:
                        break

            assert len(events_collected) >= 2
            assert any("data-stage-start" in e for e in events_collected)
            assert any("data-run-end" in e for e in events_collected)
