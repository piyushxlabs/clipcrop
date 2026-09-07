━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 20 COMPLETION CHECKLIST
# End-to-End Verification
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ BEFORE running the next prompt — do these first:

[ ] Run the automated live end-to-end verification script:
    ```
    uv run python scripts/verify_e2e_live.py
    ```
    Expected: "ALL STEP 20 END-TO-END VERIFICATION CHECKS PASSED SUCCESSFULLY!"

[ ] Run the full test suite across the entire project:
    ```
    uv run pytest tests/ -v
    ```
    Expected: All 84 tests pass with 0 failures.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ AFTER code was generated — do these now:

[ ] Verify delivered vertical clip with ffprobe:
    ```powershell
    uv run python -c "import subprocess, json; out = subprocess.check_output(['tools/ffmpeg/ffprobe.exe' if Path('tools/ffmpeg/ffprobe.exe').exists() else 'ffprobe', '-v', 'error', '-show_entries', 'stream=width,height', '-of', 'json', str(list(Path('outputs').glob('*_vertical.mp4'))[-1])]); print(json.loads(out))"
    ```
    Expected: width=1080, height=1920.

[ ] Inspect trace log annotation in outputs/traces:
    ```powershell
    powershell -Command "Get-ChildItem outputs\traces\*_trace.jsonl | Select-Object -Last 1 | ForEach-Object { Get-Content $_.FullName | Select-Object -Last 2 }"
    ```
    Expected: User feedback annotation record with rating 'up'.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WHAT GOT BUILT THIS STEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ ] File: `scripts/verify_e2e_live.py` — Automated live end-to-end verification script
[ ] Feature: Live Multipart Upload & Ingest — Validated 201 response and sandboxed upload persistence
[ ] Feature: Live SSE Event Stream — Verified wire-line events for all 8 stages and terminal run end
[ ] Feature: Deliverable Verification — Probed 1080x1920 MP4 vertical clip and CMX 3600 EDL timecodes
[ ] Feature: User Feedback Pipeline — Confirmed POST /runs/{run_id}/feedback writes to local trace log
[ ] Feature: Security Sandboxing — Verified path traversal defense and source video immutability

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 TESTING & VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test 1 — Files Exist:
```powershell
powershell -Command "Get-Item scripts/verify_e2e_live.py | Select-Object Name, Length"
```
✅ Expected: `verify_e2e_live.py` exists and is non-empty.
❌ If missing: Check git status or restore the file.

Test 2 — Environment / Dependencies:
```powershell
uv run python -c "import httpx, fastapi, src.main; print('Live verification environment OK')"
```
✅ Expected: `Live verification environment OK`
❌ If errors: Verify virtual environment with `uv sync`.

Test 3 — Live End-to-End Verification:
```powershell
uv run python scripts/verify_e2e_live.py
```
✅ Expected: 7 checks pass; exits with code 0.
❌ If errors: Inspect traceback log for endpoint failure.

Test 4 — Full Regression Suite:
```powershell
uv run pytest tests/ -v
```
✅ Expected: 84 passed with 0 failures.
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
git add . ; git commit -m "Step 20: End-to-End Verification — Live non-mocked flow, deliverables, trace log annotations, and sandbox validation"
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✋ DO NOT proceed to Step 21 until:
[ ] All tests above show ✅
[ ] Git commit is done
[ ] You have read do_after_completion.md fully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
