━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 11 COMPLETION CHECKLIST
# Wire the Fixed Stage Sequence
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ BEFORE running the next prompt — do these first:

[ ] Run pipeline controller unit and structural tests
    ```powershell
    uv run pytest tests/unit/test_pipeline_controller.py -v
    ```
    Expected: 8 passed in <5s with 0 warnings.

[ ] Run full unit test suite across all modules
    ```powershell
    uv run pytest tests/unit/ -v
    ```
    Expected: 36 passed in <15s with 0 warnings.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ AFTER code was generated — do these now:

[ ] Verify dry-run execution on simple_case fixture
    ```powershell
    uv run python -m src.agents.pipeline_controller --input tests/fixtures/simple_case.mp4 --dry-run
    ```
    Expected: `Pipeline finished successfully: {'session_id': '...', 'status': 'dry_run_success', ...}`
    If wrong: Check `--input` argument parsing and path sandbox validation in `src/agents/pipeline_controller.py`.

[ ] Verify stage count and sequence order
    ```powershell
    uv run python -c "from src.agents.pipeline_controller import PIPELINE_STAGES_ORDER; print('STAGES:', [s.value for s in PIPELINE_STAGES_ORDER]); assert len(PIPELINE_STAGES_ORDER) == 8"
    ```
    Expected: `STAGES: ['ingest_and_validate', 'transcribe_and_segment', 'score_candidates', 'track_speaker_position', 'confidence_gate', 'smooth_crop_path', 'render_and_export', 'aggregate_and_terminate']`
    If wrong: Compare `PIPELINE_STAGES_ORDER` with `AGENT_ORCHESTRATION_BLUEPRINT.md` Section 4.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WHAT GOT BUILT THIS STEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ ] File: `src/agents/pipeline_controller.py` — Complete 8-stage forward-only pipeline controller with ProcessPoolExecutor parallel fan-out and reducer-governed state updates.
[ ] File: `src/tools/track_speaker_position.py` — Process worker function `_track_frames_process_worker` and optional `executor` parameter for multiprocessing.
[ ] File: `tests/unit/test_pipeline_controller.py` — 8 comprehensive unit and structural tests verifying sequence, fan-out cap, access matrix, gating, cancellation, and circuit breaker.
[ ] Feature: Forward-Only 8-Stage Execution — Deterministic sequencing with zero loops, zero cycles, and no dynamic graph delegation.
[ ] Feature: Bounded Parallel Fan-Out — `track_speaker_position` fanned out via ProcessPoolExecutor capped strictly at `CLIPCROP_MAX_CANDIDATES = 10`.
[ ] Feature: Silence-Over-Guessing — Short-circuit termination via `zero_candidates` permanent failure when speech is absent.
[ ] Feature: Paired Deliverables Contract — Render vertical clip immediately followed by crop path export.
[ ] Feature: Circuit Breakers — Mid-session cancellation and 90-second run-wide time budget protection.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 TESTING & VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test 1 — Files Exist:
```powershell
Test-Path src/agents/pipeline_controller.py, tests/unit/test_pipeline_controller.py
```
✅ Expected: `True` for both files.
❌ If missing: Check file creation in `src/agents/` and `tests/unit/`.

Test 2 — Environment / Dependencies:
```powershell
uv run python -c "import src.agents.pipeline_controller; print('PIPELINE_CONTROLLER_IMPORT_OK')"
```
✅ Expected: `PIPELINE_CONTROLLER_IMPORT_OK`
❌ If errors: Run `uv sync --extra dev` to verify environment dependencies.

Test 3 — Pipeline Controller Unit Tests:
```powershell
uv run pytest tests/unit/test_pipeline_controller.py -v
```
✅ Expected: 8 passed in <5s.
❌ If errors: Inspect failing test case and traceback.

Test 4 — Full Unit Test Suite:
```powershell
uv run pytest tests/unit/ -v
```
✅ Expected: 36 passed in <15s.
❌ If errors: Verify no regressions across all unit test suites.

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
git commit -m "Step 11: Wire the Fixed Stage Sequence — implemented 8-stage pipeline controller with parallel fan-out and structural tests"
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✋ DO NOT proceed to Step 12 until:
[ ] All tests above show ✅
[ ] Git commit is done
[ ] You have read do_after_completion.md fully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
