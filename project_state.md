# ClipCrop Project State

- **Last Completed Step:** Step 3: Generate Coding Assistant Context File (CLAUDE.md)
- **Implemented Features:**
  - Sandboxed filesystem architecture (`uploads/`, `outputs/`, `outputs/traces/`, `models/`)
  - Environment variable schema and active `.env` configuration file
  - Security exclusion rules in `.gitignore`
  - Offline perception asset pre-caching mechanism (`scripts/download_models.py`)
  - MediaPipe BlazeFace short-range face detection model (`blaze_face_short_range.task` & `.tflite`)
  - Silero VAD offline JIT model (`silero_vad.jit`) and local torch.hub source repository (`silero-vad-master`)
  - Faster-Whisper `base.en` CTranslate2 INT8 model weights and vocabulary
  - System FFmpeg 9.0.1 and FFprobe binary path discovery and verification
  - Python 3.11 backend manifest (`pyproject.toml`) and locked dependencies (`uv.lock`)
  - CPU-only PyTorch configuration (`torch==2.14.0+cpu`) via uv index mapping
  - OpenTelemetry SDK without conflicting network exporters (`protobuf<5` compatibility preserved)
  - Frontend SPA manifest (`frontend/package.json`) and locked dependencies (`frontend/pnpm-lock.yaml`)
  - Vercel AI SDK v6 (`ai ^6.0.0`), React 19, TypeScript, and Vite dependencies
  - Coding Assistant Context document (`CLAUDE.md`) codifying invariants, boundaries, and anti-patterns
- **Pending Next Step:** Step 4: Scaffold Directory Structure
- **Known Issues / Blockers:** None
