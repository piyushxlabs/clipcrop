━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3 COMPLETION CHECKLIST
# Generate Coding Assistant Context File
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ BEFORE running the next prompt — do these first:

[ ] Verify `CLAUDE.md` exists and contains the required content
    ```powershell
    Get-Content CLAUDE.md -Head 15
    ```
    Expected: Header `# ClipCrop — Coding Assistant Context` and Project Overview visible.

[ ] Confirm character and line counts match spec
    ```powershell
    (Get-Content CLAUDE.md).Count
    ```
    Expected: 78 lines.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ AFTER code was generated — do these now:

[ ] Verify all five core sections exist in `CLAUDE.md`
    ```powershell
    Select-String -Path CLAUDE.md -Pattern "^## "
    ```
    Expected:
    - `## Project Overview`
    - `## Strict Coding Rules`
    - `## Architecture Boundaries`
    - `## Strict Anti-Patterns (Never Do This)`
    - `## Reference Documents`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ WHAT GOT BUILT THIS STEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ ] File: `CLAUDE.md` — Authoritative context document establishing constraints, boundaries, and anti-patterns for assistant execution.
[ ] Feature: Architectural Governance — Rules locked for Python 3.11 LTS, async-first I/O, Pydantic V2 validation, ProcessPoolExecutor tracking, and local-file OTel export.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 TESTING & VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test 1 — Files Exist:
```powershell
Test-Path CLAUDE.md
```
✅ Expected: `True`
❌ If missing: Generate `CLAUDE.md` from `docs/AGENT_MASTER_PLAN.md` Section 3.

Test 2 — Environment / Dependencies:
```powershell
uv run python -c "import sys; assert sys.version_info >= (3, 11) and sys.version_info < (3, 12); print('PYTHON_3_11_LTS_OK')"
```
✅ Expected: `PYTHON_3_11_LTS_OK`
❌ If errors: Ensure Python 3.11 virtual environment is active.

Test 3 — Server or Process Start:
```powershell
uv run python -c "import uvicorn; print('UVICORN_READY')"
```
✅ Expected: `UVICORN_READY`
❌ If errors: Check uvicorn in `.venv`.

Test 4 — Functional Check:
```powershell
uv run python -c "
with open('CLAUDE.md', 'r', encoding='utf-8') as f:
    text = f.read()
required = [
    'ClipCrop is a local, single-shot, deterministic media pipeline',
    'strictly >=3.11,<3.12',
    'ProcessPoolExecutor',
    'Pydantic V2',
    'append_only()',
    'merge_by_key()',
    'last_write_wins()',
    'immutable_after_init()',
    'There is no checkpointing backend',
    'There is no orchestration framework',
    'Never call any network endpoint at runtime',
]
for r in required:
    assert r in text, f'Missing rule: {r}'
print('ALL_CLAUDE_RULES_VERIFIED')
"
```
✅ Expected: `ALL_CLAUDE_RULES_VERIFIED`
❌ If wrong: Re-copy Section 3 from `docs/AGENT_MASTER_PLAN.md` into `CLAUDE.md`.

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
git commit -m "Step 3: Generate Coding Assistant Context File — codified boundaries and rules in CLAUDE.md"
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✋ DO NOT proceed to Step 4 until:
[ ] All tests above show ✅
[ ] Git commit is done
[ ] You have read do_after_completion.md fully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
