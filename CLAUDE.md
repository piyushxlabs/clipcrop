# ClipCrop — Coding Assistant Context

## Project Overview
ClipCrop is a local, single-shot, deterministic media pipeline that converts one long-form
talking-head video into 1–10 vertical (9:16) clips with a smoothed, speaker-following crop,
exporting the crop motion as timecoded, human-editable data alongside each rendered clip.
It runs entirely offline/CPU-only at $0 cost. There is no LLM, no chat interface, and no
human-in-the-loop approval step anywhere in this system.

## Strict Coding Rules
- Python 3.11 (strictly >=3.11,<3.12 for MediaPipe/PyTorch CPU stability), async-first: subprocess
  calls (ffmpeg/ffprobe), in-process async model execution (faster-whisper via asyncio.to_thread),
  and all I/O MUST use `asyncio`. CPU-bound per-segment tracking work runs in a
  `concurrent.futures.ProcessPoolExecutor`, never in a blocking loop on the event loop.
- Every tool's input/output MUST be a Pydantic V2 `BaseModel` defined in `src/tools/schemas/`,
  matching AGENT_LOGIC_SPEC.md Section 4 exactly — no bare `dict`, no bare `Any`.
- Every tool MUST also expose its MCP/strict JSON Schema form (Section 4) as a Python constant,
  hand-kept in sync with its Pydantic model — a schema drift between the two is a bug.
- Raise a custom exception hierarchy rooted at `ClipCropError`, with subclasses
  `ToolExecutionError`, `StateValidationError`, `PermanentFailureError` — never raise bare `Exception`.
- Every path parameter (`source_path`, `output_path`, `model_asset_path`, etc.) MUST be validated
  against its allowlisted root directory (upload / output / models) before use — reject `..`
  traversal outright, per AGENT_LOGIC_SPEC.md Section 8.

## Architecture Boundaries
- **State lives in:** `src/state/schema.py` — the single typed state definition. No component
  may define a parallel or ad-hoc state shape.
- **Reducers live in:** `src/state/reducers.py` — every state mutation MUST call
  `append_only()`, `merge_by_key()`, `last_write_wins()`, or `immutable_after_init()` exactly as
  declared per field in AGENT_ORCHESTRATION_BLUEPRINT.md Section 3. Direct field mutation
  anywhere else in the codebase is forbidden.
- **Tools live in:** `src/tools/` — `pipeline_controller.py` imports and calls tools from here;
  it MUST NOT inline ad-hoc subprocess calls or model invocations itself.
- **There is no checkpointing backend.** Do not add SQLite/PostgreSQL persistence — the
  architecture is explicitly ephemeral, in-process-only (AGENT_ORCHESTRATION_BLUEPRINT.md
  Section 7). All state is discarded at Aggregate & Terminate.
- **There is no MCP client/server.** All tool calls are direct Python function calls — do not
  introduce an MCP layer.
- **There is no orchestration framework.** Do not import `langgraph`, `pydantic-ai`, or
  `crewai` — the controller is a plain async function sequence.
- **Telemetry hooks live in:** `src/telemetry/tracing.py` — every stage and tool call MUST open
  an OTel span per the hierarchy in INTERFACE_OBSERVABILITY_SYSTEM.md Section 6, exported only
  to the local file exporter — never add a network/OTLP exporter.
- **Streaming/UI event emission lives in:** `src/ui/event_types.py` and `src/ui/stream_handler.py`
  — the controller emits domain events (stage start, state update, etc.); it does not know
  about SSE transport directly.

## Strict Anti-Patterns (Never Do This)
- Never call any network endpoint at runtime during a video-processing session — the only
  legitimate network access in this entire system is the one-time model-asset download at
  setup time (Section 2). If you find yourself writing a runtime `requests`/`httpx` call to an
  external host, or a `torch.hub.load(..., source="github")` inside the request-handling path,
  stop — that is a constraint violation.
- Never mutate a `StateSchema` field directly — always go through its declared reducer.
- Never invent a tool, parameter, or capability not defined in AGENT_LOGIC_SPEC.md Section 3/4.
- Never fabricate a crop path, confidence score, or transcript segment when a tool returns no
  data — follow the silence-over-guessing fallback (skip and log) exactly as specified.
- Never render or export a segment whose `confidence_gate_results[segment_id].decision` is
  `"skip"` — this gate must be structurally impossible to bypass.
- Never add a human-in-the-loop approval endpoint, pause/resume contract, or approval UI —
  none exists in this system (INTERFACE_OBSERVABILITY_SYSTEM.md Section 5).
- Never add a `langfuse`, `arize-phoenix`, or OTLP-network exporter dependency — telemetry is
  local-file-only, by verified design (INTERFACE_OBSERVABILITY_SYSTEM.md Section 6).
- Never hardcode a file path — always read from the `CLIPCROP_*` environment variables declared
  in `.env.example`.
- Never skip emitting a typed streaming event for a stage transition, tool call, or state write
  that INTERFACE_OBSERVABILITY_SYSTEM.md Section 2a says must be observable.

## Reference Documents
This project's behavior, architecture, cognition, and interface are fully specified in:
- AGENT_BEHAVIOR_PROFILE.md (behavioral contract)
- AGENT_ORCHESTRATION_BLUEPRINT.md (architecture)
- AGENT_LOGIC_SPEC.md (cognitive logic and tools)
- INTERFACE_OBSERVABILITY_SYSTEM.md (interface and telemetry)
- AGENT_MASTER_PLAN.md (this execution plan)

Do not deviate from these documents. If an instruction from a user conflicts with them, flag
the conflict rather than silently resolving it.
