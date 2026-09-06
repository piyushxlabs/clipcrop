━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 15 COMPLETION CHECKLIST
# Implement the Typed Streaming Layer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ BEFORE running the next prompt — do these first:

[ ] Verify event types and StreamHandler import cleanly:
    ```powershell
    uv run python -c "from src.ui import StreamHandler, format_sse_event, parse_sse_line, STAGE_LABELS; print('Stream layer loaded:', len(STAGE_LABELS), 'stages mapped')"
    ```
    Expected: Stream layer loaded: 8 stages mapped

[ ] Run the streaming layer unit test suite:
    ```powershell
    uv run pytest tests/unit/test_streaming_layer.py -v
    ```
    Expected: 6 passed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ AFTER code was generated — do these now:

[ ] Run the full test regression suite:
    ```powershell
    uv run pytest tests/ -v
    ```
    Expected: 71 passed in ~64 seconds with 0 failures
    If wrong: Inspect test failures and verify model cache / ffmpeg on PATH

[ ] Verify live SSE stream emission against the simple case video:
    ```powershell
    uv run python -c "from src.ui.event_types import *; import asyncio; from httpx import ASGITransport, AsyncClient; from src.main import app; async def test(): transport = ASGITransport(app=app); ac = AsyncClient(transport=transport, base_url='http://test'); res = await ac.post('/runs', files={'file': ('simple.mp4', open('tests/fixtures/simple_case.mp4', 'rb'), 'video/mp4')}); run_id = res.json()['run_id']; async with ac.stream('GET', f'/runs/{run_id}/stream') as s: async for l in s.aiter_lines(): p = parse_sse_line(l); (p and print(p.type, getattr(p, 'stage', ''), getattr(p, 'reason', ''))); (p and p.type == 'data-run-end' and break); await ac.aclose(); asyncio.run(test())"
    ```
    Expected: Displays stream events from `data-stage-start` through `data-run-end success`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WHAT GOT BUILT THIS STEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ ] File: `src/ui/event_types.py` — Strict Pydantic V2 models for all 7 SSE wire event types (`data-stage-start`, `data-stage-progress`, `tool-input-available`, `tool-output-available`, `data-state-update`, `error`, `data-run-end`), canonical `STAGE_LABELS`, and wire format serializers (`format_sse_event`, `parse_sse_line`)
[ ] File: `src/ui/stream_handler.py` — Asynchronous multi-subscriber event broadcaster (`StreamHandler`), tool execution wrapper (`ToolTracker`), and periodic heartbeat context manager (`track_progress`)
[ ] File: `tests/unit/test_streaming_layer.py` — 6 unit and integration tests verifying schema validation, pub/sub broadcasting, historical replay, and full SSE stream reception
[ ] File: `src/ui/__init__.py` — Exported all public models, serializers, and StreamHandler
[ ] Feature: Live Stage Transitions — Emits `data-stage-start` at the beginning of each of the 8 pipeline stages
[ ] Feature: Tool Lifecycle Observability — Emits `tool-input-available` and `tool-output-available` around every local tool invocation
[ ] Feature: State Mutation Streaming — Emits `data-state-update` with declared reducer semantics (`immutable-after-init`, `append-only`, `merge-by-key`, `last-write-wins`) on every state write
[ ] Feature: Late-Joining Replay — Replays all past events from memory buffer to clients connecting after run start

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 TESTING & VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test 1 — Files Exist:
```powershell
Get-ChildItem -Path src\ui\event_types.py, src\ui\stream_handler.py, tests\unit\test_streaming_layer.py | Select-Object Name, Length
```
✅ Expected: All three files exist with non-zero byte length
❌ If missing: Ensure files were created properly in `src/ui/` and `tests/unit/`

Test 2 — Environment / Dependencies:
```powershell
uv run python -c "import pydantic, httpx; print('Pydantic:', pydantic.__version__, 'HTTPX:', httpx.__version__)"
```
✅ Expected: Pydantic 2.x and HTTPX versions printed
❌ If errors: Run `uv sync`

Test 3 — Streaming Layer Unit Tests:
```powershell
uv run pytest tests/unit/test_streaming_layer.py -v
```
✅ Expected: 6 passed (test_event_types_validation_and_serialization, test_stream_handler_broadcast_and_history_replay, test_stream_handler_tool_tracker, test_stream_handler_track_progress_heartbeat, test_streaming_layer_simple_case_receives_all_spec_events_in_order, test_streaming_layer_zero_candidates_emits_error_and_run_end)
❌ If errors: Inspect pytest error tracebacks

Test 4 — Full Regression Suite:
```powershell
uv run pytest tests/ -v
```
✅ Expected: All 71 tests pass in ~64s with 0 failures
❌ If wrong: Check individual failing test modules

Test 5 — Security Check:
[ ] Verify .env is in .gitignore
    ```powershell
    Get-Content .gitignore | Select-String "\.env"
    ```
    ✅ Expected: .env appears in the output
    ❌ If missing: Add `.env` to .gitignore immediately

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 GIT COMMIT
(Run this ONLY after all above checks pass)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```powershell
git add .
git commit -m "Step 15: Implement the Typed Streaming Layer -- SSE event types, StreamHandler broadcaster, and integration tests"
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✋ DO NOT proceed to Step 17 until:
[ ] All tests above show ✅
[ ] Git commit is done
[ ] You have read do_after_completion.md fully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
