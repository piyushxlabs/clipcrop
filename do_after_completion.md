━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 25 COMPLETION CHECKLIST
# Native Word Timestamps & Audio-Subtitle Desync Elimination
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ BEFORE running the next prompt — do these first:

[ ] Verify the backend server is running and healthy:
    ```powershell
    uv run python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"
    ```
    Expected: {"status":"healthy","version":"0.1.0"}

[ ] Verify the frontend Vite dev server is running:
    ```powershell
    cd frontend && pnpm run dev
    ```
    Expected: Local server running at http://localhost:5173/.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ AFTER code was generated — do these now:

[ ] Run unit tests for native word timestamps and VAD fallback:
    ```powershell
    uv run pytest tests/unit/test_tools.py -k "test_export_subtitles" -v
    ```
    Expected: 4 passed in <5s.

[ ] Run full regression pytest suite:
    ```powershell
    uv run pytest tests/ -v
    ```
    Expected: 94 passed in ~100s with 0 failures.
    If wrong: Check test output to isolate any failing fixture or tool.

[ ] Run live upload pipeline test:
    ```powershell
    uv run python scripts/test_live_upload.py tests/fixtures/simple_case.mp4
    ```
    Expected: Complete 8-stage run finishing with 1 rendered deliverable, word-synchronized subtitles, and complete creator pack ZIP.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WHAT GOT BUILT THIS STEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ ] File: `src/state/schema.py` — Added `TranscriptWord` model (`word`, `start_ms`, `end_ms`, `probability`) and added `words: list[TranscriptWord]` to `TranscriptSegment`.
[ ] File: `src/tools/schemas/transcribe_audio.py` — Added `TranscriptWordModel` and `words: list[TranscriptWordModel]` to `TranscriptSegmentModel`, maintaining 100% parameter parity across Pydantic models and MCP JSON schemas.
[ ] File: `src/tools/transcribe_audio.py` — Passed `word_timestamps=True` to `model.transcribe()` and populated `words` in output segment objects.
[ ] File: `src/agents/pipeline_controller.py` — Mapped transcribed words into `TranscriptSegment` in Stage 2, and passed `speech_spans=self.state.vad_segments` to subtitle exporters in Stage 7.
[ ] File: `src/tools/export_subtitles.py` — Updated `_extract_timed_words` to prioritize native word timestamps, filter boundary words against candidate segment bounds, shift offsets relative to `segment_start_ms`, blank screen during intro silence, and apply Silero VAD speech span fallback clamping when word timestamps are absent.
[ ] File: `tests/unit/test_tools.py` — Added unit tests `test_export_subtitles_native_word_timestamps` and `test_export_subtitles_vad_fallback_guardrail`.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 TESTING & VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test 1 — Files Exist:
```powershell
Get-ChildItem -Path src/state/schema.py, src/tools/schemas/transcribe_audio.py, src/tools/transcribe_audio.py, src/tools/export_subtitles.py, src/agents/pipeline_controller.py, tests/unit/test_tools.py
```
✅ Expected: All 6 files exist and are verified.
❌ If missing: Restore from git.

Test 2 — Word-Level Subtitle Unit Tests:
```powershell
uv run pytest tests/unit/test_tools.py -k "test_export_subtitles" -v
```
✅ Expected: 4 passed.
❌ If errors: Verify `_extract_timed_words` in `src/tools/export_subtitles.py`.

Test 3 — Full Regression Test Suite:
```powershell
uv run pytest tests/ -v
```
✅ Expected: 94 passed in ~100s.
❌ If errors: Run `uv run pytest tests/unit/test_tools.py -v` to isolate.

Test 4 — Functional Verification:
1. Open the ClipCrop web app at `http://localhost:5173/`.
2. Upload a video containing leading silence/music or speech with pauses.
3. Observe the rendered 9:16 clip playback.
4. Verify that subtitles do NOT appear during intro silence/music before speech, appear precisely when words are spoken with yellow word highlighting, and disappear during long speech pauses.
✅ Expected: Subtitle onset matches spoken words 1:1 with zero premature black-screen captions.
❌ If wrong: Inspect `outputs/{run_id}_{segment_id}_subtitles.ass` for initial `Dialogue:` start time.

Test 5 — Security & Sandboxing Check:
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
git commit -m "Step 25: Native Word Timestamps & Audio-Subtitle Desync Elimination — Exact word-accurate captions"
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✋ DO NOT proceed to Step 26 until:
[ ] All tests above show ✅
[ ] Git commit is done
[ ] You have read do_after_completion.md fully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
