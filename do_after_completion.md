━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 6 COMPLETION CHECKLIST
# Configure Local Models
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ BEFORE running the next prompt — do these first:

[ ] Run the offline model health-check CLI
    ```powershell
    uv run python -m src.tools.model_loader
    ```
    Expected: Reports all three models healthy:
    `Faster-Whisper: HEALTHY`, `MediaPipe: HEALTHY`, `Silero VAD: HEALTHY`.

[ ] Run the model loading unit tests with network-blocking harness
    ```powershell
    uv run pytest tests/unit/test_model_loading.py -v
    ```
    Expected: 5 passed in <10s with zero network calls.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ AFTER code was generated — do these now:

[ ] Verify existence of test fixture video
    ```powershell
    Test-Path tests/fixtures/simple_case.mp4
    ```
    Expected: `True`

[ ] Verify offline model loading directly via python import
    ```powershell
    uv run python -c "from src.tools.model_loader import load_whisper_model, load_face_detector, load_silero_vad_model; from src.config import load_config_from_env; cfg = load_config_from_env(); print('LOADERS_READY')"
    ```
    Expected: `LOADERS_READY`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WHAT GOT BUILT THIS STEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ ] File: `src/tools/model_loader.py` — Centralized offline perception model loader and health-check system.
[ ] File: `tests/fixtures/simple_case.mp4` — Standard 5-second 1280x720 16kHz test fixture video.
[ ] File: `tests/unit/test_model_loading.py` — Pytest test suite with socket-level network-call-blocking verification harness.
[ ] Feature: Offline Model Loaders — `load_whisper_model`, `load_face_detector`, and `load_silero_vad_model` strictly loading from local paths.
[ ] Feature: Zero-Network Guarantee — Socket-level monkeypatching verifying zero outbound network calls during perception inference.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 TESTING & VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test 1 — Files Exist:
```powershell
Test-Path src/tools/model_loader.py, tests/fixtures/simple_case.mp4, tests/unit/test_model_loading.py
```
✅ Expected: `True` for all 3 files.
❌ If missing: Check file generation in `src/tools/`, `tests/fixtures/`, and `tests/unit/`.

Test 2 — Environment / Dependencies:
```powershell
uv run python -c "import faster_whisper, mediapipe, torch; print('PERCEPTION_LIBS_OK')"
```
✅ Expected: `PERCEPTION_LIBS_OK`
❌ If errors: Ensure `.venv` has all dependencies installed.

Test 3 — Model Health Check:
```powershell
uv run python -m src.tools.model_loader
```
✅ Expected: `[SUCCESS] All three local perception models are healthy`
❌ If errors: Check that model files exist in `models/`.

Test 4 — Functional Network-Blocked Test Suite:
```powershell
uv run pytest tests/unit/test_model_loading.py -v
```
✅ Expected: 5 passed.
❌ If wrong: Check `BlockNetworkCalls` fixture and model asset paths.

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
git commit -m "Step 6: Configure Local Models — implemented model loaders, simple_case fixture, and network-blocked test harness"
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✋ DO NOT proceed to Step 7 until:
[ ] All tests above show ✅
[ ] Git commit is done
[ ] You have read do_after_completion.md fully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
