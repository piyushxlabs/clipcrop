━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 18 COMPLETION CHECKLIST
# Integrate Telemetry & Observability
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ BEFORE running the next prompt — do these first:

[ ] Run the telemetry unit test suite to verify span hierarchy and log outputs:
    ```
    uv run pytest tests/unit/test_telemetry.py -v
    ```
    Expected: 5 tests pass with 0 failures.

[ ] Run the entire backend regression test suite:
    ```
    uv run pytest tests/ -v
    ```
    Expected: All 76 tests pass with 0 failures.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ AFTER code was generated — do these now:

[ ] Verify trace files are produced in the configured directory:
    ```
    dir outputs\traces
    ```
    Expected: JSONL trace files matching `*_trace.jsonl` are present.

[ ] Inspect the contents of a generated trace file to verify hierarchical structure and attributes:
    ```
    powershell -Command "Get-Content (Get-ChildItem outputs\traces\*_trace.jsonl | Select-Object -Last 1).FullName | Select-Object -First 5"
    ```
    Expected: Valid JSON records with `name`, `trace_id`, `span_id`, and attributes in the `clipcrop.*` namespace.
    If wrong: Ensure `JsonFileSpanExporter` correctly opens the file and flushes before controller completion.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WHAT GOT BUILT THIS STEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ ] File: `src/telemetry/tracing.py` — OpenTelemetry local `JsonFileSpanExporter` and hierarchical `PipelineTracer`
[ ] File: `src/telemetry/feedback_annotations.py` — Structured JSON post-hoc feedback ratings (`up`/`down`) and interruption annotations
[ ] File: `src/telemetry/__init__.py` — Telemetry module exports
[ ] File: `src/agents/pipeline_controller.py` — Root run span, stage spans, and per-segment/tool span lifecycle tracking
[ ] File: `src/main.py` — Connected feedback and cancellation endpoints to trace log annotations
[ ] File: `tests/unit/test_telemetry.py` — Unit test suite verifying span hierarchy, formatting, and trace file persistence
[ ] Feature: Local OpenTelemetry JSON File Tracing — Newline-delimited JSON span exporter without network daemon overhead
[ ] Feature: Post-Hoc User Feedback Pipeline — Appends user ratings and notes to completed run traces

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 TESTING & VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test 1 — Files Exist:
```powershell
powershell -Command "Get-Item src/telemetry/tracing.py, src/telemetry/feedback_annotations.py, tests/unit/test_telemetry.py | Select-Object Name, Length"
```
✅ Expected: `tracing.py`, `feedback_annotations.py`, and `test_telemetry.py` all exist and are non-empty.
❌ If missing: Check git status or re-create missing module files.

Test 2 — Environment / Dependencies:
```powershell
uv run python -c "import opentelemetry.sdk.trace as trace; from src.telemetry.tracing import PipelineTracer, JsonFileSpanExporter; print('Telemetry imports OK')"
```
✅ Expected: `Telemetry imports OK`
❌ If errors: Verify virtual environment with `uv sync`.

Test 3 — Server or Process Start:
```powershell
uv run python -c "from src.main import app; print('FastAPI app imports with telemetry OK')"
```
✅ Expected: `FastAPI app imports with telemetry OK`
❌ If errors: Verify imports in `src/main.py` and `src/telemetry/`.

Test 4 — Functional Check:
Run the telemetry unit tests:
```powershell
uv run pytest tests/unit/test_telemetry.py -v
```
✅ Expected: 5 passed in < 15s.
❌ If wrong: Check test output log for assertion failures or permission issues on `outputs/traces/`.

Test 5 — Security Check:
[ ] Verify .env is in .gitignore:
    ```powershell
    powershell -Command "Select-String -Path .gitignore -Pattern '\.env'"
    ```
    ✅ Expected: `.env` appears in the output.
    ❌ If missing: Add `.env` to `.gitignore` immediately.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 GIT COMMIT
(Run this ONLY after all above checks pass)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```powershell
git add .
git commit -m "Step 18: Integrate Telemetry & Observability — Local OpenTelemetry JSON file tracing, span hierarchy, and post-hoc feedback pipeline"
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✋ DO NOT proceed to Step 19 until:
[ ] All tests above show ✅
[ ] Git commit is done
[ ] You have read do_after_completion.md fully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
