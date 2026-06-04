# Contributing

Thanks for helping improve SecHound. A few things make review fast.

## Dev setup

```bash
git clone https://github.com/lonerzee/sechound-open.git
cd sechound-open
python -m pip install -e ".[dev]"
python -m pytest -q                  # tests
bash scripts/check_sanitization.sh   # leak gate
```

## The one hard rule: no target data

SecHound's core ships with **zero** information about any specific target. Every
PR runs `scripts/check_sanitization.sh` in CI and must pass. Before you commit:

- No real hostnames, tenant/org/account IDs, credentials, cookies, tokens, or
  API keys — anywhere, including tests, fixtures, and docs.
- No real findings against a real system. Examples must be clearly synthetic.
- No copies of a private codebase or its analysis.

See [`SANITIZATION.md`](SANITIZATION.md) for the full bar. If you need a fixture
that looks like a credential, make it obviously fake (`sk-EXAMPLE...`).

Install the local guard so leaks are caught before they're even committed:

```bash
pip install pre-commit && pre-commit install   # framework, or:
bash scripts/install-hooks.sh                   # no-dependency native hook
```

## Code style

- Standard library first; a new third-party dependency needs a reason.
- Tools are flat modules under `tools/` exposing `main()`. New tools wire into
  `tools/cli.py`.
- New LLM backends touch **only** `tools/llm.py` (see `docs/PROVIDERS.md`).
- Add a test for new logic. The suite must stay network-free and fast.

## Pull requests

- Keep them focused; one concern per PR.
- Describe what you changed and how you verified it.
- Make sure `pytest` and the sanitization check pass locally.
