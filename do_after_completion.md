━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 10 COMPLETION CHECKLIST
# Register Tools
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ BEFORE running the next prompt — do these first:

[ ] Run tool unit test suite
    ```powershell
    uv run pytest tests/unit/test_tools.py -v
    ```
    Expected: 15 passed in <8s with 0 warnings.

[ ] Run entire test suite across all modules
    ```powershell
    uv run pytest tests/unit/ -v
    ```
    Expected: 28 passed in <15s with 0 warnings.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ AFTER code was generated — do these now:

[ ] Verify dual-format schema parameter parity across all 7 tools
    ```powershell
    uv run python -c "from tests.unit.test_tools import test_schema_parameter_parity_for_all_tools; test_schema_parameter_parity_for_all_tools(); print('ALL_7_SCHEMAS_MATCH_100_PERCENT')"
    ```
    Expected: `ALL_7_SCHEMAS_MATCH_100_PERCENT`
    If wrong: Check field names between Pydantic input models and JSON Schema property dictionaries in `src/tools/schemas/`.

[ ] Verify CMX 3600 timecode generation
    ```powershell
    uv run python -c "from src.tools.export_crop_path_data import _ms_to_timecode; print('TIMECODE_CHECK:', _ms_to_timecode(1000, 25.0), _ms_to_timecode(5000, 30.0))"
    ```
    Expected: `TIMECODE_CHECK: 00:00:01:00 00:00:05:00`
    If wrong: Check millisecond-to-frame conversion logic in `src/tools/export_crop_path_data.py`.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WHAT GOT BUILT THIS STEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ ] File: `src/tools/schemas/decode_and_validate_source.py` — Pydantic V2 + strict MCP JSON Schema for Tool 1.
[ ] File: `src/tools/schemas/transcribe_audio.py` — Pydantic V2 + strict MCP JSON Schema for Tool 2.
[ ] File: `src/tools/schemas/detect_speech_pauses.py` — Pydantic V2 + strict MCP JSON Schema for Tool 3.
[ ] File: `src/tools/schemas/candidate_scorer.py` — Pydantic V2 + strict MCP JSON Schema for Candidate Scorer.
[ ] File: `src/tools/schemas/track_speaker_position.py` — Pydantic V2 + strict MCP JSON Schema for Tool 4.
[ ] File: `src/tools/schemas/confidence_gate.py` — Pydantic V2 + strict MCP JSON Schema for Confidence Gate.
[ ] File: `src/tools/schemas/smooth_crop_path.py` — Pydantic V2 + strict MCP JSON Schema for Tool 5.
[ ] File: `src/tools/schemas/render_vertical_clip.py` — Pydantic V2 + strict MCP JSON Schema for Tool 6.
[ ] File: `src/tools/schemas/export_crop_path_data.py` — Pydantic V2 + strict MCP JSON Schema for Tool 7.
[ ] File: `src/tools/decode_and_validate_source.py` — Async ffprobe media validation and stream extraction.
[ ] File: `src/tools/transcribe_audio.py` — In-process Faster-Whisper transcription with single-retry fallback.
[ ] File: `src/tools/detect_speech_pauses.py` — Silero VAD speech span and pause detection.
[ ] File: `src/tools/candidate_scorer.py` — Deterministic candidate segment scoring capped at 10.
[ ] File: `src/tools/track_speaker_position.py` — MediaPipe BlazeFace tracking (bounding box + confidence only).
[ ] File: `src/tools/confidence_gate.py` — Deterministic binary threshold gating (`tracking_confidence >= threshold`).
[ ] File: `src/tools/smooth_crop_path.py` — Deterministic EMA/window smoothing generating 9:16 crop keyframes.
[ ] File: `src/tools/render_vertical_clip.py` — Async ffmpeg vertical video renderer (1080x1920, source copy audio).
[ ] File: `src/tools/export_crop_path_data.py` — Zero-dependency CMX 3600 EDL, XML, and JSON exporter.
[ ] File: `src/tools/__init__.py` — Package export interface for tools and helpers.
[ ] File: `src/tools/schemas/__init__.py` — Package export interface for schemas and JSON Schema constants.
[ ] File: `tests/mocks/mock_tool_data.py` — Authoritative mock datasets for all 7 tools and pipeline controller.
[ ] File: `tests/unit/test_tools.py` — Comprehensive unit test suite (15 tests) verifying tools, schemas, and formats.
[ ] Feature: Dual-Format Schemas — Complete parameter parity between Pydantic models and MCP JSON Schemas.
[ ] Feature: Biometric Compliance — Speaker tracking strictly restricted to 2D bounding boxes, zero facial mesh or identity extraction.
[ ] Feature: Sandboxed Path Security — Strict enforcement of allowed roots and prohibition of overwriting source files.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 TESTING & VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test 1 — Files Exist:
```powershell
Test-Path src/tools/decode_and_validate_source.py, src/tools/transcribe_audio.py, src/tools/detect_speech_pauses.py, src/tools/candidate_scorer.py, src/tools/track_speaker_position.py, src/tools/confidence_gate.py, src/tools/smooth_crop_path.py, src/tools/render_vertical_clip.py, src/tools/export_crop_path_data.py, tests/unit/test_tools.py
```
✅ Expected: `True` for all 10 files.
❌ If missing: Verify tool implementations in `src/tools/` and `tests/unit/`.

Test 2 — Environment / Dependencies:
```powershell
uv run python -c "import faster_whisper, mediapipe, torch, scipy; print('ALL_PACKAGES_AVAILABLE')"
```
✅ Expected: `ALL_PACKAGES_AVAILABLE`
❌ If errors: Run `uv sync --extra dev` to reinstall dependencies.

Test 3 — Tool Unit Test Suite:
```powershell
uv run pytest tests/unit/test_tools.py -v
```
✅ Expected: 15 passed in <8s.
❌ If errors: Inspect failing test case and stack trace.

Test 4 — Full Unit Test Suite:
```powershell
uv run pytest tests/unit/ -v
```
✅ Expected: 28 passed in <15s.
❌ If errors: Verify no regressions across `test_model_loading.py`, `test_reducers.py`, and `test_tools.py`.

Test 5 — Security Check:
[ ] Verify .env is in .gitignore
    ```powershell
    Get-Content .gitignore | Select-String "\.env"
    ```
    ✅ Expected: `.env` appears in the output.
    ❌ If missing: Add `.env` to `.gitignore` immediately.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 GIT COMMIT
(Run this ONLY after all above checks pass)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```powershell
git add .
git commit -m "Step 10: Register Tools — implemented 7 tools, dual-format schemas, and unit test suite"
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✋ DO NOT proceed to Step 11 until:
[ ] All tests above show ✅
[ ] Git commit is done
[ ] You have read do_after_completion.md fully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
