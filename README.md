# ClipCrop

**Deterministic, Zero-Cost, Local Video Re-Framing Engine**

ClipCrop converts long-form talking-head video into 9:16 vertical clips with smooth, speaker-following camera motion and exports human-editable NLE timeline data (`.edl` / `.xml` / `.json`).

---

## Key Characteristics

- **100% Offline & $0 Budget:** Runs entirely locally on consumer CPUs using lightweight INT8 perception models. Zero cloud APIs, zero external network egress during video processing.
- **Biometric Privacy Safe:** Performs spatial bounding-box tracking only (via MediaPipe BlazeFace short-range task). Never extracts facial landmarks, face meshes, or identity signatures.
- **Deterministic Motion:** Smooths camera tracking trajectories using causal mathematical filters (EMA/Kalman) instead of generative hallucination.
- **NLE Deliverables:** Generates both rendered 9:16 video clips and standard CMX 3600 Edit Decision Lists (`.edl`), Final Cut Pro XML, and JSON keyframe timelines for instant import into Premiere Pro, DaVinci Resolve, or Final Cut Pro.
- **Real-Time Observability:** Emits structured domain events over Server-Sent Events (SSE) visualized on a task-first stage timeline, backed by local OpenTelemetry span logs.

---

## Architecture Overview

```text
clipcrop/
├── .env.example                       # Environment configuration template
├── pyproject.toml                     # Python dependencies (uv-managed)
├── CLAUDE.md                          # Authoritative assistant context and invariants
├── src/
│   ├── agents/
│   │   ├── pipeline_controller.py     # Deterministic 8-stage pipeline controller
│   │   └── segment_worker.py          # ProcessPoolExecutor segment worker
│   ├── tools/                         # Perception and processing tools
│   │   ├── decode_and_validate_source.py
│   │   ├── transcribe_audio.py
│   │   ├── detect_speech_pauses.py
│   │   ├── track_speaker_position.py
│   │   ├── smooth_crop_path.py
│   │   ├── render_vertical_clip.py
│   │   ├── export_crop_path_data.py
│   │   └── schemas/                   # Pydantic V2 models + matching MCP JSON Schemas
│   ├── state/
│   │   ├── schema.py                  # StateSchema typed state
│   │   └── reducers.py                # 4 state reducers (immutable, append, merge, last-write)
│   ├── telemetry/
│   │   ├── tracing.py                 # OTel SDK + local JSON SpanExporter
│   │   └── feedback_annotations.py    # Local trace feedback annotation writer
│   ├── ui/
│   │   ├── event_types.py             # Typed SSE wire event schemas
│   │   └── stream_handler.py          # FastAPI SSE streaming handler
│   ├── config.py                      # Runtime configuration loader
│   └── main.py                        # FastAPI application entry point
├── frontend/
│   ├── package.json                   # React 19 + Vite + Tailwind CSS (pnpm-managed)
│   └── src/
│       ├── App.tsx                    # Stage timeline & results grid
│       ├── components/                # Generative UI components
│       └── sse/                       # Typed SSE client
└── tests/
    ├── mocks/                         # Mock tool outputs
    ├── unit/                          # Schema and reducer unit tests
    ├── integration/                   # End-to-end deterministic pipeline tests
    └── fixtures/                      # Sample talking-head test fixtures
```

---

## Technology Stack

- **Python Runtime:** Python 3.11 LTS (`>=3.11,<3.12`)
- **Backend Framework:** FastAPI (`>=0.115.0`) + Uvicorn (`>=0.32.0`)
- **State & Validation:** Pydantic V2 (`>=2.9.0,<3.0.0`)
- **Speech Perception:** faster-whisper (`>=1.0.3`) via CTranslate2 INT8 CPU quantization
- **Voice Activity Detection:** Silero VAD (TorchScript local CPU execution)
- **Face & Speaker Tracking:** MediaPipe (`>=0.10.14`) BlazeFace short-range task
- **Media Engine:** FFmpeg & FFprobe 9.0.1 (system binaries via async subprocesses)
- **Frontend SPA:** Node.js LTS, React 19, TypeScript, Vite, Tailwind CSS, Vercel AI SDK v6 SSE utilities

---

## License

Apache-2.0
