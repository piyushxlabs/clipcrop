━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 13 COMPLETION CHECKLIST
# Implement Safety Guardrails
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ BEFORE running the next prompt — do these first:

[ ] Run safety guardrails test suite
    ```powershell
    uv run pytest tests/integration/test_safety_guardrails.py -v
    ```
    Expected: 12 passed in ~5s with 0 failures.

[ ] Run full test suite across all modules
    ```powershell
    uv run pytest tests/ -v
    ```
    Expected: 53 passed with 0 failures.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ AFTER code was generated — do these now:

[ ] Verify source overwrite rejection on RenderVerticalClipInput
    ```powershell
    uv run python -c "from pydantic import ValidationError; from src.tools.schemas.render_vertical_clip import RenderVerticalClipInput, CropKeyframeModel; kf = [CropKeyframeModel(timestamp_ms=0, x=0, y=0, width=400, height=700)];
try:
    RenderVerticalClipInput(segment_id='s1', source_video_path='uploads/test.mp4', segment_start_ms=0, segment_end_ms=1000, crop_keyframes=kf, output_path='uploads/test.mp4')
    assert False, 'Should have failed'
except ValidationError as e:
    print('OVERWRITE_REJECTION_VERIFIED:', e)
"
    ```
    Expected: `OVERWRITE_REJECTION_VERIFIED: 1 validation error ... output_path cannot overwrite source video`
    If wrong: Check `validate_output_not_source` model validator in `src/tools/schemas/render_vertical_clip.py`.

[ ] Verify path traversal protection
    ```powershell
    uv run python -c "from pydantic import ValidationError; from src.tools.schemas.decode_and_validate_source import DecodeAndValidateSourceInput;
try:
    DecodeAndValidateSourceInput(source_path='uploads/../secret.mp4')
    assert False, 'Should have failed'
except ValidationError as e:
    print('TRAVERSAL_REJECTION_VERIFIED:', e)
"
    ```
    Expected: `TRAVERSAL_REJECTION_VERIFIED: 1 validation error ... must not contain '..' path-traversal sequences`
    If wrong: Check `validate_no_traversal` in `src/tools/schemas/decode_and_validate_source.py`.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WHAT GOT BUILT THIS STEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ ] File: `tests/integration/test_safety_guardrails.py` — 12 negative and structural tests covering all Section 8 prohibitions, Section 9.4 criteria, and Section 9.5 failure simulations.
[ ] File: `src/tools/schemas/render_vertical_clip.py` — Dual-layer overwrite defense via `model_validator` rejecting `output_path == source_video_path`.
[ ] File: `src/tools/render_vertical_clip.py` — In-flight partial output unlinking on render failure.
[ ] File: `src/agents/pipeline_controller.py` — Emergency stop with `asyncio.Event` and automatic filesystem rollback cleanup (`_cleanup_in_flight_outputs`).
[ ] Feature: Biometric Privacy Structural Lock — Spatial 2D bounding boxes only; zero identity, landmark, or voiceprint fields in schemas.
[ ] Feature: Ephemeral In-Process State Verification — Zero disk checkpointing or database engines in codebase.
[ ] Feature: Gate-Bypass Impossibility — Strict precondition checks preventing rendering or exporting for skipped segments.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 TESTING & VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test 1 — Files Exist:
```powershell
Test-Path tests/integration/test_safety_guardrails.py
```
✅ Expected: `True`.
❌ If missing: Check file creation in `tests/integration/`.

Test 2 — Environment / Dependencies:
```powershell
uv run python -c "import pytest, pydantic; print('SAFETY_ENV_OK')"
```
✅ Expected: `SAFETY_ENV_OK`
❌ If errors: Run `uv sync --extra dev` to reinstall dependencies.

Test 3 — Safety Guardrails Test Suite:
```powershell
uv run pytest tests/integration/test_safety_guardrails.py -v
```
✅ Expected: 12 passed in ~5s.
❌ If errors: Inspect failing assertion.

Test 4 — Complete Regression Suite:
```powershell
uv run pytest tests/ -v
```
✅ Expected: 53 passed across all unit and integration tests.
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
git commit -m "Step 13: Implement Safety Guardrails — prohibition enforcement, partial output rollback, and negative test suite"
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✋ DO NOT proceed to Step 14 until:
[ ] All tests above show ✅
[ ] Git commit is done
[ ] You have read do_after_completion.md fully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
