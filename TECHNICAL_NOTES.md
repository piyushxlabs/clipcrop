# ClipCrop Technical Notes

---
## Step 1 — Local Model Caching & Asset Resolution Strategy
**Decision:**
- Used standalone standard library Python downloading in `scripts/download_models.py` to pre-cache all perception weights before package installation in Step 2.
- MediaPipe BlazeFace was downloaded as `blaze_face_short_range.tflite` from Google's official MediaPipe CDN and mirrored to `blaze_face_short_range.task` in `CLIPCROP_MODELS_DIR`.
- Silero VAD was cached in dual format: the standalone TorchScript model (`silero_vad.jit`) and the extracted repository (`silero-vad-master` and `snakers4_silero-vad_master`) containing `hubconf.py`, enabling offline `source="local"` loading via `torch.hub`.
- Faster-Whisper `base.en` CTranslate2 INT8 model files (`model.bin`, `config.json`, `tokenizer.json`, `vocabulary.txt`) were downloaded directly into `models/faster-whisper-base.en`.
- Configured explicit absolute binary paths for `CLIPCROP_FFMPEG_PATH` and `CLIPCROP_FFPROBE_PATH` in `.env` pointing to WinGet-installed Gyan FFmpeg 9.0.1 binaries.

**Reason:**
- Satisfies the strict zero-network execution constraint mandated in `AGENT_ORCHESTRATION_BLUEPRINT.md` Section 6 and `AGENT_MASTER_PLAN.md` Section 2.
- Prevents runtime network egress during video processing sessions.
- Using explicit binary paths prevents subprocess failures caused by unsynchronized shell PATH environments on Windows.

**Impact:**
- Step 6 (Configure Local Models) and Step 10 (Register Tools) can load all three models from disk in completely air-gapped / offline test modes.
- Step 10 Tool 1 (`decode_and_validate_source`) and Tool 6 (`render_vertical_clip`) can execute `ffmpeg` and `ffprobe` subprocesses without PATH ambiguity.
---

## Step 2 — PyTorch CPU Wheel Indexing & Protobuf Compatibility Resolution
**Decision:**
- Configured `pyproject.toml` with `[[tool.uv.index]]` explicitly pointing to `https://download.pytorch.org/whl/cpu` and set `[tool.uv.sources]` to map `torch` to this index.
- Intentionally omitted any `opentelemetry-exporter-otlp-*` package from `pyproject.toml` (only `opentelemetry-api` and `opentelemetry-sdk` installed).
- Configured `frontend/package.json` with React 19, Vercel AI SDK v6 (`ai ^6.0.0`), Vite 6, and Tailwind CSS 4, utilizing `pnpm approve-builds --all` for esbuild installation under pnpm v11.

**Reason:**
- The default PyPI index for PyTorch resolves large (>2.5 GB) CUDA-bundled binaries. Mapping the PyTorch CPU index ensures only the ~118 MB CPU wheel (`torch==2.14.0+cpu`) is downloaded and installed, conserving disk space and enforcing CPU-only execution.
- MediaPipe requires protobuf version `<5` or compatible builds, while standard OTLP HTTP/gRPC exporters require `protobuf>=5`. Because `INTERFACE_OBSERVABILITY_SYSTEM.md` Section 6 dictates that telemetry is written strictly to local newline-delimited JSON span files (no network export), omitting the OTLP exporters eliminates the protobuf conflict entirely.
- `ai ^6.0.0` provides low-level SSE stream-parsing utilities for the frontend stage timeline without introducing chat UI surfaces or unwanted generative dependencies.

**Impact:**
- Backend virtual environment is lean and installs in seconds without GPU bloat.
- Step 18 (Integrate Telemetry & Observability) will implement a custom local-file `SpanExporter` using core `opentelemetry-sdk` interfaces without network egress.
- Zero dependency-resolution conflicts between MediaPipe, PyTorch, CTranslate2, and OpenTelemetry.
---

## Step 3 — Coding Assistant Context Codification
**Decision:** Written verbatim from `docs/AGENT_MASTER_PLAN.md` Section 3 into `CLAUDE.md`.
**Reason:** Strict adherence to authoritative specifications without alteration.
**Impact:** Governs coding assistant actions, preventing unauthorized architectural deviations or anti-pattern introduction.

Step 3 — No deviations from spec.
---

## Step 4 — Directory Scaffold & Structural Absence Enforcement
**Decision:**
- Scaffolded backend module directories (`src/agents`, `src/tools/schemas`, `src/state`, `src/telemetry`, `src/ui`), frontend components/sse directories, and test suites (`tests/mocks`, `tests/unit`, `tests/integration`, `tests/fixtures`).
- Formally enforced documented absences: no `src/memory/`, no `checkpointing.py`, no `src/tools/mcp_clients/`, and no `frontend/src/hitl/`.

**Reason:**
- Preserves the strict architectural boundaries mandated in `docs/AGENT_MASTER_PLAN.md` Section 2, `docs/AGENT_ORCHESTRATION_BLUEPRINT.md` Sections 5–7, and `docs/INTERFACE_OBSERVABILITY_SYSTEM.md` Section 5.
- The state machine is explicitly ephemeral and single-shot in-process (no vector database, no long-term memory, no SQLite/PostgreSQL checkpointing, no approval modal).

**Impact:**
- Future steps can immediately import and author cleanly separated modules without structural refactoring.
- Eliminates any ambiguity about where components belong.

Step 4 — No deviations from spec.
---

## Step 5 — Pipeline Controller Skeleton & Deterministic Failure Semantics
**Decision:**
- Structured `PipelineController` in `src/agents/pipeline_controller.py` as a forward-only async controller strictly implementing the 8 stages defined in `AGENT_LOGIC_SPEC.md` Section 2.
- Created `ClipCropError` hierarchy (`ToolExecutionError`, `StateValidationError`, `PermanentFailureError`) in `src/exceptions.py`.
- Built `RuntimeConfig` in `src/config.py` using strict, frozen Pydantic V2 models (`model_config = ConfigDict(strict=True, frozen=True)`) with field validators enforcing threshold and candidate bounds.
- Enforced input verification: missing source path triggers a clean `ClipCropError` rather than crashing during `--dry-run` or execution.

**Reason:**
- Fulfills the verification requirement of Step 5 from `AGENT_MASTER_PLAN.md` Section 4/10.
- Implements the non-generative, deterministic state machine architecture mandated across all five foundational specification documents.

**Impact:**
- Modules in subsequent steps (model configuration in Step 6, state schema in Step 7, and tool integrations in Step 10) have an explicit runtime configuration, error handling hierarchy, and stage execution pipeline to plug into.

Step 5 — No deviations from spec.
---

## Step 6 — Standalone TorchScript JIT VAD Loading & Socket-Level Network Blocker
**Decision:**
- Loaded Silero VAD standalone TorchScript JIT model directly via `torch.jit.load(map_location="cpu")` rather than executing `torch.hub.load` through `snakers4_silero-vad_master`.
- Created a custom `BlockNetworkCalls` test fixture monkeypatching `socket.socket.connect` to systematically prohibit and catch any outbound TCP/UDP network access during model loading and inference tests.
- Bound Faster-Whisper to `local_files_only=True` and MediaPipe FaceDetector to local `.task` asset path.

**Reason:**
- The Silero `hubconf.py` script attempts to import `torchaudio`. Loading `silero_vad.jit` directly eliminates unapproved dependencies and preserves the locked manifest in `pyproject.toml`.
- Provides 100% mechanical verification that no telemetry, license checks, or model weights are fetched from the internet during pipeline execution, strictly satisfying the airgap runtime directives in `AGENT_ORCHESTRATION_BLUEPRINT.md` Section 6 and workspace rules.

**Impact:**
- Tools implemented in Step 10 (`transcribe_audio`, `detect_speech_pauses`, `track_speaker_position`) can directly consume `load_whisper_model`, `load_silero_vad_model`, and `load_face_detector` from `src.tools.model_loader` with zero risk of runtime egress.
---

## Step 7 — Direct-Mutation Protection on StateSchema & Reducer Container Immutability
**Decision:**
- Enforced direct attribute assignment prohibition on `StateSchema` after initialization by intercepting `__setattr__` to raise `StateValidationError`, requiring all mutations to route through `apply_state_update()`.
- Built `append_only` and `merge_by_key` reducers to return fresh/shallow-copied containers rather than in-place mutations, guaranteeing that external callers cannot mutate internal state collections via references.
- Bound `last_write_wins` on `candidate_segments` to strictly enforce the `CLIPCROP_MAX_CANDIDATES = 10` hard cap.
- Implemented precondition verification helpers (`verify_render_precondition`, `verify_export_precondition`) enforcing that low-confidence segments cannot proceed to smoothing/rendering/exporting and that crop path exports require pre-existing rendered clips.

**Reason:**
- Fulfills rule `state-invariants-and-tool-preconditions.md` ("zero direct field assignments on `StateSchema`") and `AGENT_ORCHESTRATION_BLUEPRINT.md` Section 3.
- Prevents subtle race conditions or state corruption when per-segment operations fan out across concurrent workers.
- Guarantees the Deliverable Contract (rendered 9:16 vertical clips strictly paired 1:1 with timeline crop-path exports) cannot be violated.

**Impact:**
- In Step 10 (Register Tools) and Step 11 (Wire the Fixed Stage Sequence), tools and the pipeline controller cannot bypass reducers or corrupt state invariants.

---
## Step 10 — Dual-Format Schema Parity, Biometric Privacy, and Zero-Dependency CMX 3600 Serialization
**Decision:**
- Implemented dual-format schemas across all 7 tools and internal helpers: strict Pydantic V2 input/output models (`model_config = ConfigDict(strict=True)`) paired with authoritative MCP JSON Schema dict constants, verified by an automated reflection test enforcing 100% parameter equivalence.
- MediaPipe BlazeFace speaker tracking (`src/tools/track_speaker_position.py`) extracts strictly 2D bounding boxes (`center_x`, `center_y`, `width`, `height`) and detection confidence. Completely omitted any facial mesh, landmark extraction, voiceprint, or identity profiling to maintain strict biometric privacy compliance.
- Serialized CMX 3600 Edit Decision Lists (`.edl`) using standard library Python formatting converting keyframe millisecond offsets to SMPTE non-drop timecodes (`HH:MM:SS:FF`) at the source video frame rate, eliminating unapproved third-party EDL dependencies.
- Enforced sandboxed path resolution across all tools: validating paths resolve strictly within configured roots (`CLIPCROP_UPLOAD_DIR`, `CLIPCROP_OUTPUT_DIR`, `CLIPCROP_MODELS_DIR`), rejecting `..` path traversal, and guaranteeing `output_path != source_video_path`.

**Reason:**
- Satisfies `AGENT_LOGIC_SPEC.md` Section 3 and `async-io-and-pydantic-validation-mandate.md` requiring strict schema-first tool interfaces compatible with local deterministic pipelines and MCP servers.
- Satisfies `identity-persona-and-compliance-directives.md` and BIPA/CUBI safe harbor requirements prohibiting biometric identity templates.
- Guarantees NLE timeline import compatibility (Premiere Pro, DaVinci Resolve, Final Cut Pro) at zero financial cost ($0.00) without brittle external C-libraries.
- Satisfies security gate 1 & 5 in `scope-screening-and-safety-gate-order.md`.

**Impact:**
- In Step 11 (Wire the Fixed Stage Sequence), the `PipelineController` can invoke these 7 tools directly with complete type safety, sandboxed path validation, and deterministic output schemas.
---

## Step 11 — ProcessPoolExecutor Worker Function Isolation & Forward-Only Sequencing
**Decision:**
- Implemented `_track_frames_process_worker` in `src/tools/track_speaker_position.py` passing strictly picklable primitive types (`str`, `list[np.ndarray]`, `list[int]`, `int`, `float`) and instantiating MediaPipe inside the worker process, enabling safe multiprocessing under Windows without SWIG wrapper serialization crashes.
- Wired the 8-stage sequence in `PipelineController` using `apply_state_update()` to enforce all 4 state reducers and prevent direct field assignment.
- Bound Stage 3 candidate ranking to hard-cap candidates at `CLIPCROP_MAX_CANDIDATES = 10` and enforced silence-over-guessing policy raising `PermanentFailureError("zero_candidates")`.
- Enforced paired deliverables contract in Stage 7: invoking `export_crop_path_data` immediately following successful `render_vertical_clip` for the same segment.
- Built circuit breakers for mid-session cancellation (`controller.cancel()`) and run-wide time budget exhaustion (`time_budget_seconds`).

**Reason:**
- MediaPipe C++ SWIG wrappers cannot be pickled across process boundaries on Windows. Isolating model loading into the worker process allows `ProcessPoolExecutor` to utilize multi-core CPU resources without blocking the `asyncio` event loop, fulfilling `async-io-and-pydantic-validation-mandate.md`.
- Conforms to `graph-topology-loop-caps-and-circuit-breakers.md`, `node-tool-access-matrix-restrictions.md`, and `state-invariants-and-tool-preconditions.md`.

**Impact:**
- In Step 12 (Implement the Deterministic Reasoning Loop), the pipeline controller can execute end-to-end against real fixtures, evaluating confidence gating and termination criteria.
---

## Step 12 — Audiovisual Fixture Standardization, Determinism Verification, and Windows Multi-Processing
**Decision:**
- Standardized the real talking-head audiovisual fixture (`tests/fixtures/simple_case.mp4`) with an identifiable centered facial subject and clear spoken speech audio track (16kHz PCM), establishing a permanent ground-truth fixture for offline integration and determinism testing.
- Implemented multi-run determinism regression testing (`test_pipeline_determinism_regression` in `tests/integration/test_pipeline_e2e.py`) verifying that running the pipeline multiple times over identical media produces strictly identical candidate segments, confidence gate decisions, and smoothed crop keyframes.
- Updated `_track_frames_process_worker` in `src/tools/track_speaker_position.py` to accept serialized `config_dict` (via `config.model_dump()`) and re-validate inside the worker process, ensuring seamless cross-process boundary serialization under Windows.

**Reason:**
- Satisfies `docs/AGENT_MASTER_PLAN.md` Section 9.4 and `docs/AGENT_LOGIC_SPEC.md` Section 1 requiring zero-hallucination, 100% deterministic camera motion and reproducible segment scoring on CPU-only local execution.
- Ensures integration tests catch any nondeterministic drift or race conditions in perception model execution and multiprocessing on Windows.

**Impact:**
- Step 13 (Implement Safety Guardrails) and subsequent backend API/streaming integration (Steps 14–15) have fully validated, deterministic end-to-end pipeline execution and robust regression test coverage.
---

## Step 13 — Dual-Layer Overwrite Defense, In-Flight Rollback, and Structural Negative Evals
**Decision:**
- Enforced dual-layer output collision defense: added a strict Pydantic `model_validator` in `RenderVerticalClipInput` asserting `Path(output_path).resolve() != Path(source_video_path).resolve()`, supplemented by runtime verification in `_validate_output_sandbox` inside `src/tools/render_vertical_clip.py`.
- Implemented in-flight partial output rollback cleanup in `src/agents/pipeline_controller.py` (`_cleanup_in_flight_outputs`) and `src/tools/render_vertical_clip.py`. On mid-session user cancellation or render failure, any partially written `.mp4` or `.edl` files are immediately deleted from disk, guaranteeing zero corrupt or incomplete files remain in the output directory.
- Upgraded the emergency stop mechanism in `PipelineController` to maintain an `asyncio.Event` (`self._cancel_event`), checking cancellation before every stage transition and before dispatching each candidate segment in Stage 4, 6, and 7.
- Authored a comprehensive negative and structural verification suite in `tests/integration/test_safety_guardrails.py` (12 tests) verifying all 8 Section 8 prohibitions, Section 9.4 invariants, and Section 9.5 failure scenarios.

**Reason:**
- Satisfies `docs/AGENT_MASTER_PLAN.md` Section 8, Section 9.4/9.5, and rules `scope-screening-and-safety-gate-order.md` and `code-level-verification-over-model-discretion.md`.
- Prevents data loss or source video destruction under erroneous configurations.
- Guarantees the deliverable contract: only verified, complete, 100% paired deliverables (clip + EDL) are delivered to the user.

**Impact:**
- In Step 14 (Build Backend API/Server) and Step 15 (Implement Typed Streaming Layer), HTTP/SSE cancel endpoints can invoke `controller.cancel()` knowing execution halts cleanly with automatic filesystem rollback.
---

## Step 14 — FastAPI Application Architecture, SSE Wire Streaming, and Deliverable Sandboxing
**Decision:**
- Implemented `src/main.py` providing `GET /health`, `POST /runs`, `GET /runs/{run_id}/stream`, `POST /runs/{run_id}/cancel`, `POST /runs/{run_id}/feedback`, and `GET /outputs/{filename}` with FastAPI CORS middleware.
- In `POST /runs`, enforced strict file validation: filename path traversal sanitization, extension allowlist (`.mp4`, `.mov`, `.mkv`, `.webm`, `.avi`), zero-byte check, and chunked streaming to sandboxed `upload_dir`.
- Bound `GET /runs/{run_id}/stream` to the pipeline controller, emitting text/event-stream messages (`data-stage-start`, `data-state-update`, `data-run-end`, `error`) formatted for Vercel AI SDK v6 Data Stream consumers.
- Mounted deliverable serving on `GET /outputs/{filename}` with strict path traversal validation against `CLIPCROP_OUTPUT_DIR`.
- Implemented `POST /runs/{run_id}/feedback` appending user thumbs-up/down ratings and notes to newline-delimited JSON trace logs in `outputs/traces/`.
- Created comprehensive unit test suite in `tests/unit/test_api_server.py` with 12 tests covering all endpoints and security safeguards.

**Reason:**
- Satisfies `docs/AGENT_MASTER_PLAN.md` Section 10 Step 14 and `docs/INTERFACE_OBSERVABILITY_SYSTEM.md` Section 2, 2a, and 7a.
- Connects the async pipeline controller to the HTTP/SSE transport layer while preserving the zero-cloud, sandboxed local architecture.

**Impact:**
- Ready for Step 15 (Implement the Typed Streaming Layer) where `src/ui/event_types.py` and `src/ui/stream_handler.py` will formalize the typed SSE wire contracts.
---

## Step 15 — Typed Server-Sent Events Wire Protocol, Multi-Subscriber Broadcasting, and Lifecycle Tracking
**Decision:**
- Implemented `src/ui/event_types.py` defining strict Pydantic V2 models (`model_config = ConfigDict(strict=True)`) for all 7 SSE wire events (`data-stage-start`, `data-stage-progress`, `tool-input-available`, `tool-output-available`, `data-state-update`, `error`, `data-run-end`).
- Formatted all SSE emissions strictly matching Vercel AI SDK v6 Data Stream wire lines (`data: <json>\n\n`) via `format_sse_event()`, and verified symmetric deserialization via `parse_sse_line()`.
- Built `StreamHandler` (`src/ui/stream_handler.py`) as an asynchronous event queue broadcaster supporting multiple concurrent subscribers, automatic queue cleanup upon disconnect, and historical replay from an in-memory event buffer so late-joining clients receive the entire sequence of events from run start.
- Created `ToolTracker` and `track_progress` context managers for declarative emission of `tool-input-available`, `tool-output-available`, and periodic `data-stage-progress` heartbeat events.
- Wired `StreamHandler` into `PipelineController` and `src/main.py`, emitting live stage transitions, tool executions, and reducer-governed state updates in real time.

**Reason:**
- Satisfies `docs/AGENT_MASTER_PLAN.md` Section 10 Step 15, Section 7, and `docs/INTERFACE_OBSERVABILITY_SYSTEM.md` Section 2a and 3b.
- Guarantees strict ordering and 1:1 synchronization between backend state mutations and frontend UI stream consumers.

**Impact:**
- The frontend in Step 17 (`frontend/src/App.tsx` and components) can directly bind to typed SSE events from `GET /runs/{run_id}/stream` using AI SDK v6 or standard EventSource without any custom protocol translation.
---

## Step 17 — Generative UI Architecture, Reducer Synchronization, and UI Non-Goals Enforcement
**Decision:**
- Implemented frontend data streaming in `frontend/src/sse/usePipelineStream.ts` using `fetch` with `ReadableStream` reader parsing chunked `data: <json>\n\n` blocks directly, updating client state through matching reducer functions (`append-only`, `merge-by-key`, `last-write-wins`, `immutable-after-init`).
- Built all 7 Generative UI components from `docs/INTERFACE_OBSERVABILITY_SYSTEM.md` Section 4a (`SourceVideoCard`, `TranscriptView`, `VadTimeline`, `CandidateRankingTable`, `ConfidenceBadge`, `CropPathChart`, `ClipResultsGrid`) with strict payload binding directly to tool outputs and state updates.
- Enforced paired deliverables contract in `ClipResultsGrid`: clips are only rendered in the deliverables grid if both a valid vertical MP4 clip and a corresponding crop-path export file (`.edl`, `.xml`, or `.json`) exist for that `segment_id`.
- Enforced all Section 10 UI Non-Goals in code and verified via automated scanning:
  1. No conversational chat thread.
  2. No native model thinking panels.
  3. No approval/HITL modal.
  4. No individual clip regenerate/retry button.
  5. No continuous quality score meter (confidence gating is presented strictly as a binary threshold cutoff).
  6. No raw filesystem paths or internal process PIDs displayed.
- Built an offline mock fixture replayer (`frontend/src/sse/mockEvents.ts`) mirroring `tests/mocks/mock_tool_data.py` allowing instant end-to-end frontend verification without running external video workloads.

**Reason:**
- Satisfies `docs/AGENT_MASTER_PLAN.md` Section 10 Step 17, `docs/INTERFACE_OBSERVABILITY_SYSTEM.md` Section 4a and Section 10, and rules `ui-non-goals-interface-boundaries.md` and `code-level-verification-over-model-discretion.md`.
- Guarantees complete visual observability of the deterministic pipeline while strictly adhering to non-generative, local-only architectural reality.

**Impact:**
- In Step 18 (Integrate Telemetry & Observability), telemetry spans and feedback annotations recorded from `ClipResultsGrid`'s rating buttons will bind directly to the local trace logs in `CLIPCROP_TRACE_LOG_DIR`.
---



