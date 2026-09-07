━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 19 COMPLETION CHECKLIST
# Run Automated Evaluation Suites
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ BEFORE running the next prompt — do these first:

[ ] Run the new evaluation test suite:
    ```
    uv run pytest tests/integration/test_eval_suites.py -v
    ```
    Expected: All 8 evaluation tests pass with 0 failures.

[ ] Run the full regression test suite across the entire project:
    ```
    uv run pytest tests/ -v
    ```
    Expected: All 84 tests pass with 0 failures.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ AFTER code was generated — do these now:

[ ] Run frontend verification script and build:
    ```powershell
    cd frontend; node test_verification.mjs; pnpm exec tsc --noEmit; pnpm run build
    ```
    Expected: 21 checks pass, 0 type errors, production bundle built cleanly in < 2 seconds.

[ ] Verify trace logs exist and contain valid evaluation spans:
    ```powershell
    powershell -Command "Get-ChildItem outputs\traces\*_trace.jsonl | Select-Object -Last 1 | ForEach-Object { Get-Content $_.FullName | Select-Object -First 3 }"
    ```
    Expected: JSON records with trace_id, span_id, and clipcrop.* attributes.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WHAT GOT BUILT THIS STEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ ] File: `tests/integration/test_eval_suites.py` — Formal automated evaluation suite (8 tests)
[ ] Feature: CI Tool Parameter Parity Diff — Automated reflection check diffing Pydantic V2 models vs JSON schema properties
[ ] Feature: Tool-Sequencing Correctness Verification — Strict sequential 8-stage execution validation
[ ] Feature: Telemetry Grounding Verification — 1:1 state-to-event summary grounding check
[ ] Feature: Non-Negotiable Requirements Enforcement — Loop bounds (10 candidate cap), 90s time budget, failure mappings
[ ] Test Suite: 84 of 84 automated tests passing across unit, integration, safety guardrails, and evaluation suites

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 TESTING & VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test 1 — Files Exist:
```powershell
powershell -Command "Get-Item tests/integration/test_eval_suites.py | Select-Object Name, Length"
```
✅ Expected: `test_eval_suites.py` exists and is non-empty.
❌ If missing: Check git status or restore the file.

Test 2 — Environment / Dependencies:
```powershell
uv run python -c "import pytest, torch, mediapipe, faster_whisper; print('Evaluation test environment OK')"
```
✅ Expected: `Evaluation test environment OK`
❌ If errors: Verify virtual environment with `uv sync`.

Test 3 — Evaluation Suite Execution:
```powershell
uv run pytest tests/integration/test_eval_suites.py -v
```
✅ Expected: 8 passed in ~25s.
❌ If errors: Inspect pytest failure log.

Test 4 — Full Regression Suite:
```powershell
uv run pytest tests/ -v
```
✅ Expected: 84 passed in ~105s with 0 failures.
❌ If errors: Check test output log for assertion failures.

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
git add . ; git commit -m "Step 19: Run Automated Evaluation Suites — Formal evaluation matrix, determinism regression, and non-negotiable verification"
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✋ DO NOT proceed to Step 20 until:
[ ] All tests above show ✅
[ ] Git commit is done
[ ] You have read do_after_completion.md fully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
