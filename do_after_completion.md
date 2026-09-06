━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 7 COMPLETION CHECKLIST
# Implement Typed State Schema & Reducers
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ BEFORE running the next prompt — do these first:

[ ] Run unit tests for StateSchema and reducers
    ```powershell
    uv run pytest tests/unit/test_reducers.py -v
    ```
    Expected: 8 passed in <1s with 0 warnings.

[ ] Run full unit test suite
    ```powershell
    uv run pytest tests/unit/ -v
    ```
    Expected: 13 passed in <8s.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ AFTER code was generated — do these now:

[ ] Verify direct mutation protection raises StateValidationError
    ```powershell
    uv run python -c "from src.state import StateSchema; from src.config import load_config_from_env; from src.exceptions import StateValidationError; s = StateSchema(session_id='test', config=load_config_from_env());
try:
    s.session_id = 'mutated'
    print('FAIL: Mutation allowed')
except StateValidationError as e:
    print('PASS: Mutation blocked:', e)
"
    ```
    Expected: `PASS: Mutation blocked: Direct assignment to field 'session_id' on StateSchema is prohibited. All state mutations must route through reducer functions in src.state.reducers.`

[ ] Verify state update routing via apply_state_update
    ```powershell
    uv run python -c "from src.state import StateSchema, FileRef, apply_state_update; from src.config import load_config_from_env; s = StateSchema(session_id='test', config=load_config_from_env()); s = apply_state_update(s, 'source_video', FileRef(path='A:/test.mp4')); print('UPDATED_SOURCE:', s.source_video.path)"
    ```
    Expected: `UPDATED_SOURCE: A:/test.mp4`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WHAT GOT BUILT THIS STEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ ] File: `src/state/schema.py` — Central StateSchema with 13 locked fields and 12 supporting Pydantic V2 domain models.
[ ] File: `src/state/reducers.py` — 4 locked state reducers (`immutable_after_init`, `append_only`, `merge_by_key`, `last_write_wins`), `apply_state_update` dispatcher, and precondition verifiers.
[ ] File: `src/state/__init__.py` — Package export interface for state models, reducers, and precondition checkers.
[ ] File: `tests/unit/test_reducers.py` — Unit test suite verifying reducer invariants, candidate capping, and direct mutation protection.
[ ] Feature: Immutability Protection — Prohibits direct attribute assignment on StateSchema, enforcing mutation strictly through reducers.
[ ] Feature: Gating Preconditions — `verify_render_precondition` and `verify_export_precondition` enforcing render gates and paired deliverables.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 TESTING & VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test 1 — Files Exist:
```powershell
Test-Path src/state/schema.py, src/state/reducers.py, tests/unit/test_reducers.py
```
✅ Expected: `True` for all 3 files.
❌ If missing: Check file creation in `src/state/` and `tests/unit/`.

Test 2 — Reducers Unit Test Suite:
```powershell
uv run pytest tests/unit/test_reducers.py -v
```
✅ Expected: 8 passed in <1s.
❌ If errors: Inspect reducer function signatures and Pydantic model configurations.

Test 3 — Full Unit Test Suite:
```powershell
uv run pytest tests/unit/ -v
```
✅ Expected: 13 passed in <8s.
❌ If errors: Verify no regressions in `test_model_loading.py`.

Test 4 — State Schema Field Count Verification:
```powershell
uv run python -c "from src.state import StateSchema; fields = list(StateSchema.model_fields.keys()); assert len(fields) == 13; print('13_FIELDS_OK:', fields)"
```
✅ Expected: `13_FIELDS_OK: ['session_id', 'source_video', 'transcript_segments', 'vad_segments', 'candidate_segments', 'tracking_results', 'confidence_gate_results', 'crop_paths', 'rendered_clips', 'crop_path_exports', 'skipped_segments', 'error_logs', 'config']`
❌ If wrong: Compare fields with AGENT_ORCHESTRATION_BLUEPRINT.md Section 3.

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
git commit -m "Step 7: Implement Typed State Schema & Reducers — implemented 13-field StateSchema, 4 reducers, and unit test suite"
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✋ DO NOT proceed to Step 10 until:
[ ] All tests above show ✅
[ ] Git commit is done
[ ] You have read do_after_completion.md fully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
