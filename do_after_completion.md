━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 26 COMPLETION CHECKLIST
# Local Ollama (Qwen 2.5) Intelligent Viral Hooks & Metadata
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ BEFORE running the next prompt — do these first:

[ ] Verify Ollama server is running and models are accessible:
    ```powershell
    uv run python -c "import urllib.request, json; res = urllib.request.urlopen('http://127.0.0.1:11434/api/tags'); print(json.loads(res.read().decode()))"
    ```
    Expected: List of models including `qwen2.5:3b` and `qwen2.5:7b`.

[ ] Verify backend server is running and healthy:
    ```powershell
    uv run python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"
    ```
    Expected: `{"status":"healthy","version":"0.1.0"}`

[ ] Verify frontend Vite dev server is running:
    ```powershell
    cd frontend && pnpm run dev
    ```
    Expected: Local server running at http://localhost:5173/.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ AFTER code was generated — do these now:

[ ] Run unit tests for viral metadata and Ollama mock:
    ```powershell
    uv run pytest tests/unit/test_tools.py -k "test_generate_clip_metadata" -v
    ```
    Expected: 2 passed in <3s.

[ ] Run full regression pytest suite:
    ```powershell
    uv run pytest tests/ -v
    ```
    Expected: 95 passed in ~150s with 0 failures.
    If wrong: Check test output to isolate any failing fixture or tool.

[ ] Run live upload pipeline test:
    ```powershell
    uv run python scripts/test_live_upload.py tests/fixtures/simple_case.mp4
    ```
    Expected: Complete 8-stage run finishing with 1 rendered deliverable, intelligent viral hook, and complete creator pack ZIP.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WHAT GOT BUILT THIS STEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ ] File: `src/tools/generate_clip_metadata.py` — Integrated local Ollama chat API (`http://127.0.0.1:11434/api/chat`) with `qwen2.5:3b` / `qwen2.5:7b` using standard library `urllib.request` and `json`.
[ ] File: `src/tools/generate_clip_metadata.py` — Enforced 4.0-second timeout with `keep_alive: -1` in request payload for GPU residency and sub-2-second inference.
[ ] File: `src/tools/generate_clip_metadata.py` — Implemented defensive heuristic fallback (strict invariant): errors, timeouts, or malformed JSON silently fall back to offline keyword heuristic.
[ ] File: `tests/unit/test_tools.py` — Added unit test `test_generate_clip_metadata_ollama_mock` verifying mock JSON parsing and fallback error tolerance.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 TESTING & VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test 1 — Files Exist:
```powershell
Get-ChildItem -Path src/tools/generate_clip_metadata.py, tests/unit/test_tools.py
```
✅ Expected: Both files exist and are verified.
❌ If missing: Restore from git.

Test 2 — Metadata Generation Unit Tests:
```powershell
uv run pytest tests/unit/test_tools.py -k "test_generate_clip_metadata" -v
```
✅ Expected: 2 passed.
❌ If errors: Verify `_query_ollama_metadata` in `src/tools/generate_clip_metadata.py`.

Test 3 — Full Regression Test Suite:
```powershell
uv run pytest tests/ -v
```
✅ Expected: 95 passed.
❌ If errors: Run `uv run pytest tests/unit/test_tools.py -v` to isolate.

Test 4 — Functional Verification:
1. Open the ClipCrop web app at `http://localhost:5173/`.
2. Upload a talking-head video.
3. Observe the rendered clip card in the dashboard.
4. Verify the viral hook banner displays an engaging, creative hook (e.g. "Unlock the art of video editing today!").
5. Click "Copy Title & Tags" and paste into a text editor to verify 3 high-CTR titles and 5 hashtags.
✅ Expected: Human-level creative titles and punchy hook instead of verbatim transcript text.
❌ If wrong: Inspect `outputs/{run_id}_{segment_id}_metadata.json` directly.

Test 5 — Security & Output Sandboxing Check:
[ ] Verify .env is in .gitignore:
    ```powershell
    Select-String -Path .gitignore -Pattern "\.env"
    ```
    ✅ Expected: `.env` appears in the output.
    ❌ If missing: Add `.env` to `.gitignore` immediately.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 GIT COMMIT
(Run this ONLY after all above checks pass)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```powershell
git add .
git commit -m "Step 26: Local Ollama (Qwen 2.5) Intelligent Viral Hooks & Metadata — AI viral hooks with safe fallback"
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✋ DO NOT proceed to Step 27 until:
[ ] All tests above show ✅
[ ] Git commit is done
[ ] You have read do_after_completion.md fully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
