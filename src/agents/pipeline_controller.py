"""ClipCrop Deterministic 8-Stage Pipeline Controller.

Implements the forward-only, confidence-gated pipeline state machine defined in
AGENT_ORCHESTRATION_BLUEPRINT.md Section 4 and AGENT_LOGIC_SPEC.md Section 2.
"""

from __future__ import annotations

import argparse
import asyncio
import enum
import sys
from pathlib import Path
from typing import Any

from src.config import RuntimeConfig, load_config_from_env
from src.exceptions import ClipCropError, PermanentFailureError, StateValidationError


class PipelineStage(str, enum.Enum):
    """The eight sequential stages of the ClipCrop forward-only pipeline."""

    STAGE_1_INGEST_AND_VALIDATE = "ingest_and_validate"
    STAGE_2_TRANSCRIBE_AND_SEGMENT = "transcribe_and_segment"
    STAGE_3_SCORE_CANDIDATES = "score_candidates"
    STAGE_4_TRACK_SPEAKER_POSITION = "track_speaker_position"
    STAGE_5_CONFIDENCE_GATE = "confidence_gate"
    STAGE_6_SMOOTH_CROP_PATH = "smooth_crop_path"
    STAGE_7_RENDER_AND_EXPORT = "render_and_export"
    STAGE_8_AGGREGATE_AND_TERMINATE = "aggregate_and_terminate"


PIPELINE_STAGES_ORDER: tuple[PipelineStage, ...] = (
    PipelineStage.STAGE_1_INGEST_AND_VALIDATE,
    PipelineStage.STAGE_2_TRANSCRIBE_AND_SEGMENT,
    PipelineStage.STAGE_3_SCORE_CANDIDATES,
    PipelineStage.STAGE_4_TRACK_SPEAKER_POSITION,
    PipelineStage.STAGE_5_CONFIDENCE_GATE,
    PipelineStage.STAGE_6_SMOOTH_CROP_PATH,
    PipelineStage.STAGE_7_RENDER_AND_EXPORT,
    PipelineStage.STAGE_8_AGGREGATE_AND_TERMINATE,
)


class PipelineController:
    """Deterministic, forward-only pipeline controller for ClipCrop.

    Orchestrates the 8-stage execution flow with per-segment parallel fan-out
    and binary confidence gating. Ephemeral, in-process, single-shot execution.
    """

    def __init__(
        self,
        config: RuntimeConfig | None = None,
        source_video_path: Path | str | None = None,
        dry_run: bool = False,
    ) -> None:
        self.config = config or load_config_from_env()
        self.source_video_path = Path(source_video_path).resolve() if source_video_path else None
        self.dry_run = dry_run
        self.current_stage: PipelineStage | None = None

    async def execute(self) -> dict[str, Any]:
        """Execute the pipeline from Stage 1 through Stage 8.

        Raises:
            ClipCropError: If input validation fails or a fatal condition is encountered.
        """
        # Strict input gate
        if self.source_video_path is None:
            raise ClipCropError(
                "No source video input provided for pipeline execution. "
                "A valid source_path is required."
            )

        if not self.source_video_path.is_file():
            raise ClipCropError(
                f"Source video file does not exist: {self.source_video_path}"
            )

        # Path sandboxing verification
        try:
            self.source_video_path.relative_to(self.config.upload_dir)
        except ValueError:
            # Allow dry-run or test paths if explicitly provided, else enforce sandboxing
            if not self.dry_run:
                raise ClipCropError(
                    f"Path security violation: {self.source_video_path} is outside {self.config.upload_dir}"
                )

        if self.dry_run:
            return {
                "status": "dry_run_success",
                "source_video_path": str(self.source_video_path),
                "stages": [s.value for s in PIPELINE_STAGES_ORDER],
                "config": self.config.model_dump(),
            }

        # Stage sequencing skeleton (wired to concrete tools in subsequent steps)
        for stage in PIPELINE_STAGES_ORDER:
            self.current_stage = stage
            await self._execute_stage(stage)

        return {
            "status": "completed",
            "source_video_path": str(self.source_video_path),
        }

    async def _execute_stage(self, stage: PipelineStage) -> None:
        """Execute a single pipeline stage. Implementation wired in Steps 10-12."""
        # Stub for subsequent tool wiring in Steps 10-12
        await asyncio.sleep(0)


async def run_pipeline(
    source_video_path: Path | str | None = None,
    config: RuntimeConfig | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Helper entry point to execute the pipeline controller asynchronously."""
    controller = PipelineController(
        config=config,
        source_video_path=source_video_path,
        dry_run=dry_run,
    )
    return await controller.execute()


def main() -> None:
    """CLI entry point for pipeline controller invocation and dry-run validation."""
    parser = argparse.ArgumentParser(
        description="ClipCrop Deterministic Video Reframing Pipeline Controller",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default=None,
        help="Path to source video file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Execute dry-run validation of configuration and stages without rendering.",
    )

    args = parser.parse_args()

    try:
        result = asyncio.run(
            run_pipeline(
                source_video_path=args.input,
                dry_run=args.dry_run,
            )
        )
        print(f"Pipeline finished successfully: {result}")
    except ClipCropError as e:
        print(f"ClipCropError: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected fatal error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
