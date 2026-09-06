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
