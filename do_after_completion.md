━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 2 COMPLETION CHECKLIST
# Initialize Project Manifest & Install Dependencies
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ BEFORE running the next prompt — do these first:

[ ] Verify Python backend virtual environment and packages
    ```powershell
    uv run python -c "import fastapi, pydantic, mediapipe, faster_whisper, torch, scipy, numpy, opentelemetry; print('ALL_BACKEND_PACKAGES_LOADED')"
    ```
    Expected: `ALL_BACKEND_PACKAGES_LOADED` without any import errors or protobuf conflicts.

[ ] Verify frontend packages in pnpm store
    ```powershell
    cd frontend; pnpm list; cd ..
    ```
    Expected: `ai@6.0.277`, `react@19.2.8`, `react-dom@19.2.8`, `vite@6.4.3`, etc. listed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ AFTER code was generated — do these now:

[ ] Confirm PyTorch CPU-only configuration
    ```powershell
    uv run python -c "import torch; assert not torch.cuda.is_available(); print(f'Torch {torch.__version__} CPU verified')"
    ```
    Expected: `Torch 2.14.0+cpu CPU verified`

[ ] Confirm pytest test runner executes cleanly
    ```powershell
    uv run pytest --version
    ```
    Expected: `pytest 9.1.1`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WHAT GOT BUILT THIS STEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ ] File: `pyproject.toml` — Backend manifest with Python 3.11 lock and PyTorch CPU index.
[ ] File: `uv.lock` — Deterministic lockfile for all 68 backend Python dependencies.
[ ] File: `frontend/package.json` — Frontend manifest with React 19, AI SDK v6, and Vite.
[ ] File: `frontend/pnpm-lock.yaml` — Deterministic lockfile for all frontend dependencies.
[ ] File: `frontend/pnpm-workspace.yaml` — pnpm workspace configuration.
[ ] Feature: CPU-Only Torch Mapping — uv source mapping to PyTorch CPU wheel index.
[ ] Feature: Conflict-Free Telemetry — OpenTelemetry SDK configured without network OTLP packages.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 TESTING & VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test 1 — Files Exist:
```powershell
Test-Path pyproject.toml, uv.lock, frontend/package.json, frontend/pnpm-lock.yaml, .venv, frontend/node_modules
```
✅ Expected: True for all 6 paths.
❌ If missing: Re-run `uv sync --extra dev --python 3.11` or `cd frontend; pnpm install; cd ..`.

Test 2 — Environment / Dependencies:
```powershell
uv run python -c "import sys; assert sys.version_info >= (3, 11) and sys.version_info < (3, 12); print('PYTHON_3_11_LTS_OK')"
```
✅ Expected: `PYTHON_3_11_LTS_OK`
❌ If errors: Ensure uv uses Python 3.11.x via `--python 3.11`.

Test 3 — Server or Process Start:
```powershell
uv run python -c "import uvicorn; print('UVICORN_READY')"
```
✅ Expected: `UVICORN_READY`
❌ If errors: Check uvicorn installation in `.venv`.

Test 4 — Functional Check:
```powershell
uv run python -c "
import importlib.metadata, opentelemetry.sdk.trace
tracer = opentelemetry.sdk.trace.TracerProvider().get_tracer('test')
with tracer.start_as_current_span('step2-verify') as span:
    span.set_attribute('step', 2)
print('OPENTELEMETRY_CORE_FUNCTIONAL')
"
```
✅ Expected: `OPENTELEMETRY_CORE_FUNCTIONAL`
❌ If wrong: Check opentelemetry-sdk installation.

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
git commit -m "Step 2: Initialize Project Manifest & Install Dependencies — configured pyproject.toml, package.json, and resolved all packages"
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✋ DO NOT proceed to Step 3 until:
[ ] All tests above show ✅
[ ] Git commit is done
[ ] You have read do_after_completion.md fully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
