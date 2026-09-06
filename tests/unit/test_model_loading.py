"""Unit tests for offline perception model loading and health check.

Enforces zero-network execution by wrapping test execution in a strict
network-call-blocking test harness.
"""

from __future__ import annotations

import socket
from pathlib import Path
import pytest

from src.config import load_config_from_env
from src.tools.model_loader import (
    load_face_detector,
    load_silero_vad_model,
    load_whisper_model,
    run_model_health_check,
)


class NetworkBlockedError(RuntimeError):
    """Raised when an unauthorized outbound network call is attempted."""


class BlockNetworkCalls:
    """Context manager and pytest fixture helper that blocks all outbound socket connections."""

    def __enter__(self) -> BlockNetworkCalls:
        self._orig_connect = socket.socket.connect

        def guarded_connect(sock_self: Any, address: Any) -> Any:
            raise NetworkBlockedError(
                f"Unauthorized network egress attempted during offline execution! Destination: {address}"
            )

        socket.socket.connect = guarded_connect
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        socket.socket.connect = self._orig_connect


@pytest.fixture
def block_network() -> Any:
    """Pytest fixture providing strict network call blocking."""
    with BlockNetworkCalls() as blocker:
        yield blocker


@pytest.fixture
def runtime_config() -> Any:
    """Provide loaded RuntimeConfig for tests."""
    return load_config_from_env()


@pytest.fixture
def simple_case_fixture() -> Path:
    """Provide path to Simple Case video fixture."""
    fixture = Path(__file__).resolve().parent.parent / "fixtures" / "simple_case.mp4"
    assert fixture.is_file(), f"Fixture file not found at {fixture}"
    return fixture


def test_network_blocker_functional(block_network: Any) -> None:
    """Verify that the network blocking harness actively traps socket connect attempts."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(NetworkBlockedError, match="Unauthorized network egress"):
        s.connect(("1.1.1.1", 80))
    s.close()


def test_whisper_model_offline_load(block_network: Any, runtime_config: Any) -> None:
    """Verify Faster-Whisper base.en loads offline with zero network calls."""
    model = load_whisper_model(runtime_config)
    assert model is not None


def test_mediapipe_face_detector_offline_load(block_network: Any, runtime_config: Any) -> None:
    """Verify MediaPipe BlazeFace face detector loads offline with zero network calls."""
    detector = load_face_detector(runtime_config)
    assert detector is not None


def test_silero_vad_offline_load(block_network: Any, runtime_config: Any) -> None:
    """Verify Silero VAD loads offline with zero network calls."""
    model = load_silero_vad_model(runtime_config)
    assert model is not None


def test_run_model_health_check_against_simple_case(
    block_network: Any,
    runtime_config: Any,
    simple_case_fixture: Path,
) -> None:
    """Verify all three models pass the health check against simple_case.mp4 with zero network calls."""
    results = run_model_health_check(runtime_config, simple_case_fixture)

    assert results["all_healthy"] is True
    assert results["faster_whisper"]["status"] == "healthy"
    assert results["mediapipe_face_detector"]["status"] == "healthy"
    assert results["silero_vad"]["status"] == "healthy"
