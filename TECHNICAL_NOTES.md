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
