━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 23 COMPLETION CHECKLIST
# Hormozi-Style Highlighted Captions, Offline Viral Metadata, Peak Cover Art & 1-Click ZIP Creator Bundle
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ BEFORE running the next prompt — do these first:

[ ] Verify the backend and frontend dev servers are running:
    ```powershell
    uv run uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
    ```
    Expected: Application startup complete, Uvicorn running on http://127.0.0.1:8000.

[ ] In another terminal, ensure the Vite dev server is running:
    ```powershell
    cd frontend && pnpm run dev
    ```
    Expected: Local server running at http://localhost:5173/.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ AFTER code was generated — do these now:

[ ] Run the full automated pytest suite:
    ```powershell
    uv run pytest tests/ -v
    ```
    Expected: 91 passed in ~85s with 0 failures.
    If wrong: Check test failure output and verify local perception assets in `models/`.

[ ] Run live upload test to generate a full Creator Pack bundle:
    ```powershell
    uv run python scripts/test_live_upload.py tests/fixtures/simple_case.mp4
    ```
    Expected: All 8 stages complete, yielding vertical MP4, EDL, XML, JSON, SRT, ASS, JPG, metadata JSON, and master ZIP.

[ ] Verify master ZIP Creator Pack contents and metadata:
    ```powershell
    uv run python -c "import zipfile, glob; zips = glob.glob('outputs/*_complete_pack.zip'); z = zipfile.ZipFile(zips[-1]); print(z.namelist())"
    ```
    Expected: List containing `.mp4`, `.edl`, `.xml`, `.json`, `.srt`, `.jpg`, and `README_METADATA.txt`.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WHAT GOT BUILT THIS STEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ ] File: `src/tools/export_subtitles.py` — Added kinetic ASS subtitle generator with Hormozi-style vibrant yellow active-word highlight (`{\c&H0000FFFF&}`), bold text, black outline, and configurable word chunks.
[ ] File: `src/tools/schemas/render_vertical_clip.py` — Updated schema with `burn_subtitles` and `subtitles_path` parameters maintaining 100% Pydantic V2 and JSON schema parity.
[ ] File: `src/tools/render_vertical_clip.py` — Injected FFmpeg `subtitles` filter with Windows path colon escaping and defensive fallback to clean video.
[ ] File: `src/tools/extract_thumbnail.py` — Standalone peak detection score cover thumbnail extraction during active speech intervals.
[ ] File: `src/tools/generate_clip_metadata.py` — 100% offline heuristic viral hook, 3 title variants, and 5 hashtags engine saved to `_metadata.json`.
[ ] File: `src/tools/bundle_deliverables.py` — 1-click master ZIP archive builder packaging all clip deliverables and README.
[ ] File: `src/agents/pipeline_controller.py` — Wired subtitle generation, burned subtitles, thumbnail, viral metadata, and ZIP bundling into Stage 7 with comprehensive cancellation cleanup.
[ ] File: `src/main.py` — Added MIME mappings for `application/zip` (`.zip`) and `text/x-ssa` (`.ass`).
[ ] File: `frontend/src/components/ClipResultsGrid.tsx` — Added poster thumbnail display, viral hook banner, copy title & tags button, and master `[📦 Download Complete Creator Pack (.ZIP)]` button.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 TESTING & VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test 1 — Files Exist:
```powershell
Get-ChildItem -Path src/tools/export_subtitles.py, src/tools/extract_thumbnail.py, src/tools/generate_clip_metadata.py, src/tools/bundle_deliverables.py
```
✅ Expected: All 4 tool files exist and are non-empty.
❌ If missing: Restore or recreate the tool implementations from git.

Test 2 — Environment / Dependencies:
```powershell
uv run pytest tests/unit/test_tools.py -k "test_export_ass_subtitles_formatting or test_generate_clip_metadata or test_create_deliverables_bundle" -v
```
✅ Expected: 3 passed in <5s.
❌ If errors: Verify `src/tools/export_subtitles.py` and `generate_clip_metadata.py`.

Test 3 — Full Regression Test Suite:
```powershell
uv run pytest tests/ -v
```
✅ Expected: 91 passed in ~85s.
❌ If errors: Run `uv run pytest tests/unit/test_tools.py -v` to isolate failing component.

Test 4 — Functional UI Check:
1. Open http://localhost:5173/ in the browser.
2. Upload a test video or inspect rendered clip results.
3. Observe the cover poster thumbnail, the yellow "VIRAL HOOK" badge, the "📋 Copy Title & Tags" button, and the green "📦 Download Complete Creator Pack (.ZIP)" button.
✅ Expected: Video plays with crisp, centered framing; clicking the ZIP button downloads the complete creator bundle.
❌ If wrong: Check browser console (F12) for network errors or unbuilt assets.

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
git commit -m "Step 23: Hormozi-Style Captions & Creator Pack Bundle — Dynamic highlighted subtitles, viral metadata, and 1-click ZIP pack"
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✋ DO NOT proceed to Step 24 until:
[ ] All tests above show ✅
[ ] Git commit is done
[ ] You have read do_after_completion.md fully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
