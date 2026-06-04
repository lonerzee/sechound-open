## What & why

<!-- What does this change and why? -->

## How verified

<!-- Commands run, tests added/passing. -->

## Checklist

- [ ] `python -m pytest -q` passes
- [ ] `bash scripts/check_sanitization.sh` passes
- [ ] No target-specific data added (hosts, IDs, creds, real findings) — see SANITIZATION.md
- [ ] New logic has a test; new tool wired into `tools/cli.py`; new LLM backend only touches `tools/llm.py`
