━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 14 COMPLETION CHECKLIST
# Build Backend API/Server
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ BEFORE running the next prompt — do these first:

[ ] Verify the FastAPI application imports cleanly and root endpoints respond:
    ```powershell
    uv run python -c "from src.main import app; print(app.title)"
    ```
    Expected: ClipCrop API

[ ] Run the API server test suite:
    ```powershell
    uv run pytest tests/unit/test_api_server.py -v
    ```
    Expected: 12 passed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ AFTER code was generated — do these now:

[ ] Run the full test regression suite:
    ```powershell
    uv run pytest tests/ -v
    ```
    Expected: 65 passed in ~55 seconds with 0 failures
    If wrong: Check error output in test failures and ensure FFmpeg is available on PATH

[ ] Verify server starts up without errors:
    ```powershell
    uv run uvicorn src.main:app --host 127.0.0.1 --port 8000
    ```
    Expected: Application startup complete. Uvicorn running on http://127.0.0.1:8000
    If wrong: Check if port 8000 is occupied or kill conflicting process

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WHAT GOT BUILT THIS STEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ ] File: `src/main.py` — FastAPI application implementing REST and SSE endpoints (`/health`, `/runs`, `/runs/{id}/stream`, `/runs/{id}/cancel`, `/runs/{id}/feedback`, `/outputs/{filename}`)
[ ] File: `tests/unit/test_api_server.py` — 12 unit tests covering all endpoints, status codes, upload validation, SSE streaming, cancellation, feedback, and deliverable serving
[ ] Feature: Multipart upload validation — Enforces file extension allowlist, path traversal protection, zero-byte rejection, and chunked streaming to sandboxed `uploads/`
[ ] Feature: In-process run registry — Ephemeral dictionary tracking active controllers and source video metadata without persistent databases
[ ] Feature: Server-Sent Events (SSE) streaming — StreamingResponse emitting real-time stage progress and state transitions formatted for Vercel AI SDK v6 Data Stream consumers
[ ] Feature: Emergency stop endpoint — `POST /runs/{run_id}/cancel` cleanly triggering controller cancellation and partial deliverable rollback
[ ] Feature: User feedback trace logging — `POST /runs/{run_id}/feedback` recording ratings and notes to newline-delimited JSON trace files in `outputs/traces/`
[ ] Feature: Sandboxed deliverable download — `GET /outputs/{filename}` serving rendered clips and EDL files with directory traversal defense

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 TESTING & VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test 1 — Files Exist:
```powershell
Get-ChildItem -Path src\main.py, tests\unit\test_api_server.py | Select-Object Name, Length
```
✅ Expected: Both `main.py` and `test_api_server.py` are listed with non-zero byte size
❌ If missing: Ensure files were saved properly in `src/` and `tests/unit/`

Test 2 — Environment / Dependencies:
```powershell
uv run python -c "import fastapi, uvicorn, pydantic; print('FastAPI:', fastapi.__version__, 'Pydantic:', pydantic.__version__)"
```
✅ Expected: FastAPI 0.115.x and Pydantic 2.x versions printed
❌ If errors: Run `uv sync` to ensure dependencies match `uv.lock`

Test 3 — Server or Process Start:
```powershell
uv run python -c "from fastapi.testclient import TestClient; from src.main import app; client = TestClient(app); print(client.get('/health').json())"
```
✅ Expected: {'status': 'healthy', 'version': '0.1.0'}
❌ If errors: Inspect `src/main.py` syntax and route registration

Test 4 — Functional Check:
```powershell
uv run pytest tests/unit/test_api_server.py -v
```
✅ Expected: All 12 tests pass (test_health, test_post_runs_*, test_stream_run, test_cancel_run, test_feedback, test_get_output_*)
❌ If wrong: Check test output logs and tracebacks

Test 5 — Security Check:
[ ] Verify .env is in .gitignore
    ```powershell
    Get-Content .gitignore | Select-String "\.env"
    ```
    ✅ Expected: .env appears in the output
    ❌ If missing: Add `.env` to .gitignore immediately

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 GIT COMMIT
(Run this ONLY after all above checks pass)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```powershell
git add .
git commit -m "Step 14: Build Backend API/Server -- FastAPI endpoints, upload sanitization, SSE streaming, and test suite"
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✋ DO NOT proceed to Step 15 until:
[ ] All tests above show ✅
[ ] Git commit is done
[ ] You have read do_after_completion.md fully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
