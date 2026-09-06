━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 4 COMPLETION CHECKLIST
# Scaffold Directory Structure
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ BEFORE running the next prompt — do these first:

[ ] Verify full scaffolded directory hierarchy exists
    ```powershell
    Get-ChildItem -Path src, frontend/src, tests
    ```
    Expected: `agents`, `tools`, `state`, `telemetry`, `ui`, `components`, `sse`, `mocks`, `unit`, `integration`, `fixtures` listed.

[ ] Confirm documented structural absences are enforced
    ```powershell
    -not (Test-Path src/memory, src/checkpointing.py, src/tools/mcp_clients, frontend/src/hitl)
    ```
    Expected: `True`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ AFTER code was generated — do these now:

[ ] Verify package imports across backend hierarchy
    ```powershell
    uv run python -c "import src.state, src.tools.schemas, src.agents, src.telemetry, src.ui; print('PACKAGE_TREE_IMPORT_OK')"
    ```
    Expected: `PACKAGE_TREE_IMPORT_OK`

[ ] Check root README.md documentation
    ```powershell
    Get-Content README.md -Head 10
    ```
    Expected: ClipCrop title, description, and key characteristics visible.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WHAT GOT BUILT THIS STEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ ] Directory: `src/agents/` — Pipeline controller and segment worker module location.
[ ] Directory: `src/tools/schemas/` — Tool implementations and Pydantic V2 / JSON Schemas.
[ ] Directory: `src/state/` — StateSchema and 4 reducer functions.
[ ] Directory: `src/telemetry/` — Local-file OpenTelemetry tracing and feedback annotations.
[ ] Directory: `src/ui/` — Streaming domain event types and FastAPI SSE handler.
[ ] Directory: `frontend/src/components/` — Generative UI components.
[ ] Directory: `frontend/src/sse/` — Minimal AI SDK v6 SSE client.
[ ] Directory: `tests/mocks/` — JSON mock tool outputs.
[ ] Directory: `tests/unit/` — Reducer and schema unit tests.
[ ] Directory: `tests/integration/` — Full pipeline integration tests.
[ ] Directory: `tests/fixtures/` — Sample video fixtures.
[ ] File: `README.md` — Project architecture, offline execution model, and directory overview.
[ ] Markers: Standard `__init__.py` files across all backend and test packages.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 TESTING & VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test 1 — Files Exist:
```powershell
Test-Path src/agents, src/tools/schemas, src/state, src/telemetry, src/ui, frontend/src/components, frontend/src/sse, tests/mocks, tests/unit, tests/integration, tests/fixtures, README.md
```
✅ Expected: `True` for all 12 items.
❌ If missing: Check directory scaffolding commands.

Test 2 — Environment / Dependencies:
```powershell
uv run python -c "import sys; assert sys.version_info >= (3, 11) and sys.version_info < (3, 12); print('PYTHON_3_11_LTS_OK')"
```
✅ Expected: `PYTHON_3_11_LTS_OK`
❌ If errors: Ensure Python 3.11 virtual environment is active.

Test 3 — Server or Process Start:
```powershell
uv run python -c "import uvicorn; print('UVICORN_READY')"
```
✅ Expected: `UVICORN_READY`
❌ If errors: Check uvicorn installation in `.venv`.

Test 4 — Functional Check:
```powershell
uv run python -c "
from pathlib import Path
for d in ['src/agents', 'src/tools/schemas', 'src/state', 'src/telemetry', 'src/ui']:
    assert Path(d).is_dir(), f'Missing dir {d}'
for f in ['src/memory', 'src/checkpointing.py', 'src/tools/mcp_clients', 'frontend/src/hitl']:
    assert not Path(f).exists(), f'Forbidden path exists: {f}'
import src.agents, src.tools.schemas, src.state, src.telemetry, src.ui
print('SCAFFOLD_STRUCTURAL_INTEGRITY_VERIFIED')
"
```
✅ Expected: `SCAFFOLD_STRUCTURAL_INTEGRITY_VERIFIED`
❌ If wrong: Remove any forbidden components and re-add missing packages.

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
git commit -m "Step 4: Scaffold Directory Structure — established package hierarchy and verified structural absences"
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✋ DO NOT proceed to Step 5 until:
[ ] All tests above show ✅
[ ] Git commit is done
[ ] You have read do_after_completion.md fully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
