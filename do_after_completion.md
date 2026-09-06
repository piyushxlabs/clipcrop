━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 1 COMPLETION CHECKLIST
# Environment Setup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ BEFORE running the next prompt — do these first:

[ ] Verify FFmpeg is accessible in your current shell session
    ```powershell
    & "C:\Users\DELL\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe" -version
    ```
    Expected: ffmpeg version 9.0.1 output with full build configuration.

[ ] Confirm `.env` points to valid local workspace paths
    ```powershell
    Get-Content .env
    ```
    Expected: All 9 `CLIPCROP_*` keys present without placeholder values.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ AFTER code was generated — do these now:

[ ] Re-run model asset verification check
    ```powershell
    & "C:\Users\DELL\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\python.exe" scripts/download_models.py
    ```
    Expected: All 4 verification items display `PASS`.
    If wrong: Ensure network access is active and re-run the script.

[ ] Verify sandboxed directory hierarchy
    ```powershell
    Test-Path uploads, outputs, outputs/traces, models
    ```
    Expected: True for all 4 paths.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WHAT GOT BUILT THIS STEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ ] File: `.env.example` — Template defining all 9 required `CLIPCROP_*` environment keys with defaults.
[ ] File: `.env` — Active configuration instance with sandboxed workspace paths.
[ ] File: `scripts/download_models.py` — Idempotent offline model downloader and verification tool.
[ ] File: `models/blaze_face_short_range.task` — MediaPipe BlazeFace face detector model.
[ ] File: `models/silero_vad.jit` — Standalone Silero VAD TorchScript model.
[ ] File: `models/silero-vad-master/hubconf.py` — Silero VAD repository for offline `torch.hub` loading.
[ ] File: `models/faster-whisper-base.en/` — INT8 CTranslate2 speech recognition weights and vocab.
[ ] Config: `.gitignore` — Strictly excludes `.env`, `models/`, `uploads/`, `outputs/`, and build artifacts.
[ ] Package: Gyan.FFmpeg@9.0.1 — Installed system binaries for audio/video decoding and rendering.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 TESTING & VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test 1 — Files Exist:
```powershell
Get-ChildItem -Path .env, .env.example, scripts/download_models.py, models/*
```
✅ Expected: `.env`, `.env.example`, `scripts/download_models.py`, `blaze_face_short_range.task`, `silero_vad.jit`, `silero-vad-master`, and `faster-whisper-base.en`.
❌ If missing: Re-run `& "C:\Users\DELL\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\python.exe" scripts/download_models.py`.

Test 2 — Environment / Dependencies:
```powershell
& "C:\Users\DELL\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\python.exe" --version
uv --version
```
✅ Expected: Python 3.11.x and uv CLI tool present.
❌ If errors: Verify uv installation at `C:\Users\DELL\.local\bin\uv.exe`.

Test 3 — Server or Process Start:
```powershell
& "C:\Users\DELL\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\python.exe" -c "from pathlib import Path; assert Path('.env').is_file(); print('ENV_OK')"
```
✅ Expected: `ENV_OK`
❌ If errors: Ensure `.env` is created in repository root.

Test 4 — Functional Check:
```powershell
& "C:\Users\DELL\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\python.exe" -c "from pathlib import Path; m = Path('models'); assert (m / 'blaze_face_short_range.task').stat().st_size > 0; assert (m / 'silero_vad.jit').stat().st_size > 0; assert (m / 'faster-whisper-base.en/model.bin').stat().st_size > 100_000_000; print('ALL_ASSETS_VERIFIED')"
```
✅ Expected: `ALL_ASSETS_VERIFIED`
❌ If wrong: Re-run `python scripts/download_models.py` to complete asset downloads.

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
git commit -m "Step 1: Environment Setup — configured sandboxed env and cached offline perception models"
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✋ DO NOT proceed to Step 2 until:
[ ] All tests above show ✅
[ ] Git commit is done
[ ] You have read do_after_completion.md fully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
