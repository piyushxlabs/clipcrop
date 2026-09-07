"""Runtime configuration loader for ClipCrop.

Parses and validates all CLIPCROP_* environment variables into a typed
RuntimeConfig Pydantic V2 model.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.exceptions import StateValidationError


class RuntimeConfig(BaseModel):
    """Immutable runtime configuration for a single pipeline execution."""

    model_config = ConfigDict(strict=True, frozen=True)

    upload_dir: Path = Field(
        ...,
        description="Sandboxed root directory for raw uploaded videos.",
    )
    output_dir: Path = Field(
        ...,
        description="Sandboxed root directory for rendered vertical clips and NLE exports.",
    )
    models_dir: Path = Field(
        ...,
        description="Local directory containing pre-downloaded offline perception models.",
    )
    ffmpeg_path: str = Field(
        ...,
        description="System binary path to ffmpeg executable.",
    )
    ffprobe_path: str = Field(
        ...,
        description="System binary path to ffprobe executable.",
    )
    confidence_threshold: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        description="Minimum tracking confidence required to proceed to rendering (default: 0.65).",
    )
    max_candidates: int = Field(
        default=10,
        ge=1,
        le=10,
        description="Maximum number of candidate segments fanned out per run (hard cap: 10).",
    )
    time_budget_seconds: float = Field(
        default=90.0,
        ge=0.0,
        description="Total wall-clock time budget in seconds for the entire pipeline run (default: 90.0).",
    )
    trace_log_dir: Path = Field(
        ...,
        description="Sandboxed directory for local OpenTelemetry newline-delimited JSON span files.",
    )

    @field_validator("confidence_threshold")
    @classmethod
    def validate_confidence_threshold(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise StateValidationError(f"confidence_threshold must be in [0.0, 1.0], got {v}")
        return v

    @field_validator("max_candidates")
    @classmethod
    def validate_max_candidates(cls, v: int) -> int:
        if v < 1 or v > 10:
            raise StateValidationError(f"max_candidates must be between 1 and 10, got {v}")
        return v

    @field_validator("time_budget_seconds")
    @classmethod
    def validate_time_budget(cls, v: float) -> float:
        if v < 0.0:
            raise StateValidationError(f"time_budget_seconds must be >= 0.0, got {v}")
        return v


def _parse_env_file(env_path: Path) -> dict[str, str]:
    """Parse key-value pairs from a .env file."""
    env_vars: dict[str, str] = {}
    if not env_path.is_file():
        return env_vars

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip()
    return env_vars


def load_config_from_env(env_file_path: Path | None = None) -> RuntimeConfig:
    """Load and validate RuntimeConfig from os.environ with fallback to .env file."""
    project_root = Path(__file__).resolve().parent.parent
    if env_file_path is None:
        env_file_path = project_root / ".env"

    file_vars = _parse_env_file(env_file_path)

    def get_var(key: str, default: str | None = None) -> str:
        val = os.environ.get(key, file_vars.get(key, default))
        if val is None:
            raise StateValidationError(f"Missing required environment variable: {key}")
        return val

    try:
        raw_confidence = float(get_var("CLIPCROP_CONFIDENCE_THRESHOLD", "0.65"))
        raw_max_candidates = int(get_var("CLIPCROP_MAX_CANDIDATES", "10"))
        raw_time_budget = float(get_var("CLIPCROP_TIME_BUDGET_SECONDS", "90"))

        return RuntimeConfig(
            upload_dir=Path(get_var("CLIPCROP_UPLOAD_DIR")).resolve(),
            output_dir=Path(get_var("CLIPCROP_OUTPUT_DIR")).resolve(),
            models_dir=Path(get_var("CLIPCROP_MODELS_DIR")).resolve(),
            ffmpeg_path=get_var("CLIPCROP_FFMPEG_PATH", "ffmpeg"),
            ffprobe_path=get_var("CLIPCROP_FFPROBE_PATH", "ffprobe"),
            confidence_threshold=raw_confidence,
            max_candidates=raw_max_candidates,
            time_budget_seconds=raw_time_budget,
            trace_log_dir=Path(get_var("CLIPCROP_TRACE_LOG_DIR")).resolve(),
        )
    except Exception as e:
        if isinstance(e, StateValidationError):
            raise
        raise StateValidationError(f"Failed to load runtime configuration: {e}") from e
