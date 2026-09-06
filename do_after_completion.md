━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 12 COMPLETION CHECKLIST
# Implement the Deterministic Reasoning Loop
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ BEFORE running the next prompt — do these first:

[ ] Run integration test suite
    ```powershell
    uv run pytest tests/integration/test_pipeline_e2e.py -v
    ```
    Expected: 5 passed in ~40s with 0 failures.

[ ] Run full test suite across unit and integration suites
    ```powershell
    uv run pytest tests/ -v
    ```
    Expected: 41 passed with 0 failures.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ AFTER code was generated — do these now:

[ ] Verify end-to-end execution deliverables on Simple Case fixture
    ```powershell
    uv run python -c "import asyncio, pprint; from pathlib import Path; from src.config import load_config_from_env; from src.agents.pipeline_controller import PipelineController; cfg = load_config_from_env(); ctrl = PipelineController(config=cfg, source_video_path=Path('tests/fixtures/simple_case.mp4')); res = asyncio.run(ctrl.execute()); pprint.pprint(res); assert res['status'] == 'success'; assert res['rendered_count'] == 1"
    ```
    Expected: `{'deliverables': [{'crop_path_export': '...', 'rendered_clip': '...', 'segment_id': 'seg_01'}], 'rendered_count': 1, 'skipped_count': 0, 'status': 'success'}`
    If wrong: Verify model checkpoints in `models/` and ffprobe stream decoding in `src/tools/decode_and_validate_source.py`.

[ ] Inspect rendered 9:16 vertical clip dimensions and audio stream
    ```powershell
    uv run python -c "import subprocess, json; res = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', 'outputs/seg_01_vertical.mp4'], capture_output=True, text=True); data = json.loads(res.stdout); v = next(s for s in data['streams'] if s['codec_type'] == 'video'); a = next(s for s in data['streams'] if s['codec_type'] == 'audio'); print(f'VIDEO: {v[\"width\"]}x{v[\"height\"]}, AUDIO: {a[\"codec_name\"]}'); assert v['width'] == 1080 and v['height'] == 1920"
    ```
    Expected: `VIDEO: 1080x1920, AUDIO: aac`

[ ] Inspect generated CMX 3600 EDL file
    ```powershell
    Get-Content outputs/seg_01_crop_path.edl -TotalCount 10
    ```
    Expected: Valid CMX 3600 header, event record with SMPTE timecodes (`HH:MM:SS:FF`), and crop keyframe comments (`* CROP_KEYFRAME`).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WHAT GOT BUILT THIS STEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ ] File: `tests/integration/test_pipeline_e2e.py` — 5 comprehensive end-to-end integration tests verifying determinism, silence-over-guessing, confidence gating, time budgeting, and paired deliverables.
[ ] File: `tests/fixtures/simple_case.mp4` — Real audiovisual test fixture with centered face and clear spoken 16kHz audio track (~6.8s).
[ ] Feature: Determinism Regression Verification — Proved that two independent pipeline runs on identical media produce value-identical candidates, gate decisions, and crop keyframes.
[ ] Feature: Windows Multiprocessing Deserialization — Updated `_track_frames_process_worker` to safely pass and reconstruct `RuntimeConfig` dict across process boundaries.
[ ] Feature: Paired Deliverables Delivery — 1:1 pairing of rendered vertical clip (1080x1920 MP4) with editable NLE timeline file (`.edl`).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 TESTING & VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test 1 — Files Exist:
```powershell
Test-Path tests/integration/test_pipeline_e2e.py, tests/fixtures/simple_case.mp4
```
✅ Expected: `True` for both files.
❌ If missing: Check file creation in `tests/integration/` and `tests/fixtures/`.

Test 2 — Environment / Dependencies:
```powershell
uv run python -c "import pytest, torch, mediapipe, faster_whisper; print('INTEGRATION_ENV_OK')"
```
✅ Expected: `INTEGRATION_ENV_OK`
❌ If errors: Run `uv sync --extra dev` to reinstall dependencies.

Test 3 — End-to-End Integration Suite:
```powershell
uv run pytest tests/integration/test_pipeline_e2e.py -v
```
✅ Expected: 5 passed in ~40s.
❌ If errors: Check test traceback and verify test video fixtures.

Test 4 — Complete Regression Suite:
```powershell
uv run pytest tests/ -v
```
✅ Expected: 41 passed across unit and integration tests.
❌ If errors: Check failing tests for regressions.

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
git commit -m "Step 12: Implement the Deterministic Reasoning Loop — end-to-end execution, determinism regression, and integration tests"
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✋ DO NOT proceed to Step 13 until:
[ ] All tests above show ✅
[ ] Git commit is done
[ ] You have read do_after_completion.md fully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
