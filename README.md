# SecHound

[![ci](https://github.com/lonerzee/sechound-open/actions/workflows/ci.yml/badge.svg)](https://github.com/lonerzee/sechound-open/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

**An LLM-orchestrated security audit framework.**

> **See it work in 10s, no API key:** `bash examples/demo.sh` — confirms a real
> IDOR end-to-end against a bundled vulnerable target. Walkthrough in
> [`docs/QUICKSTART.md`](docs/QUICKSTART.md).

SecHound turns a vague request ("audit this service for SSRF") into a verifiable,
reproducible pipeline: code-level candidate discovery → live reproduction →
adversarial critique → de-duplicated, false-positive-filtered findings. The
orchestration, scoring, and finding-management logic are plain Python and
target-agnostic.

It is also **model-agnostic and modular**: every stage talks to an LLM through a
single seam (`tools/llm.py`), so you can drive it with the Claude Code CLI, a
local model via Ollama, or any OpenAI-/Anthropic-compatible API by setting one
environment variable. See [`docs/PROVIDERS.md`](docs/PROVIDERS.md).

> This is the open-source core. It ships with **no target data** — no hosts, no
> credentials, no findings. You point it at *your own* authorized scope via
> `config/targets.yaml` (see `config/targets.example.yaml`).

---

## Why it exists

Most automated security tooling produces a pile of unranked, unverified
candidates that a human then triages by hand. SecHound's thesis is that the
triage *is* the work, so the framework bakes it in:

- **Every candidate must survive a kill gate** before it becomes a finding.
- **Every finding carries an invalidator analysis** — the controls that would
  make it a false positive, checked explicitly rather than assumed away.
- **Live reproduction is required for `confirmed`** — a code-only candidate
  never gets promoted on vibes.
- **A registry de-duplicates by root cause**, so the same bug found three ways
  collapses into one tracked item.

## The loop

```
                 ┌─────────────────────────────────────────────┐
                 │                                             │
   plan ──▶ execute ──▶ verify ──▶ critic ──▶ compound ──▶ (report)
   │          │           │          │           │
   │          │           │          │           └─ fold confirmed findings
   │          │           │          │              back into knowledge
   │          │           │          └─ adversarial re-test; auto-demote
   │          │           │             on mismatch
   │          │           └─ live repro + FP checklist; candidate→confirmed
   │          └─ run the hunt (grep / agent / DAST template)
   └─ translate vague request → ranked, file:line hypotheses
```

| Stage | Module | Responsibility |
|---|---|---|
| Plan | `prompts/planner.md` | Turn a request into ranked, located hypotheses |
| Execute | `prompts/executor.md` | Run the hunt; emit `candidate (code-only)` stubs |
| Verify | `prompts/verifier.md` | Reproduce live; apply FP checklist; promote/demote |
| Critic | `tools/critic.py` | Adversarially challenge each verdict |
| Compound | `tools/compounder.py` | Fold confirmed findings back into knowledge |
| Review | `tools/ultrareview.py` | Final two-lane (static + counter) pass |
| Dispatch | `tools/orchestrate.py` | Fan stages out to parallel lanes |

Every stage's prompt lives in `prompts/`; the orchestration logic is in
`tools/`. The LLM seam is `tools/llm.py` — swapping models never touches a stage.

## Core concepts

- **Findings registry** — one JSON record per vulnerability, keyed by a stable
  ID, de-duplicated by root cause. Schema in `findings/schema.json`.
- **Kill gate** — a candidate that can't clear the gate is dropped, not filed.
- **False-positive checklist** — a mechanical list of patterns that have
  historically produced FPs; applied before filing and before accepting any
  retraction. Template in `docs/FP_CHECKLIST.md`.
- **Invariant-breaker** — off-taxonomy hunting: state the invariants the system
  *claims* to hold, then try to falsify them. Template in
  `config/invariants.example.yaml`.
- **Skills & agents** — reusable hunt playbooks (`skills/`) and specialized
  sub-agents (`agents/`) the orchestrator can dispatch in parallel.

## Quick start

```bash
git clone https://github.com/lonerzee/sechound-open.git
cd sechound-open
cp config/targets.example.yaml config/targets.yaml   # fill in YOUR authorized scope
cp config/invariants.example.yaml config/invariants.yaml
python -m pip install -r requirements.txt

# Pick a model backend (default is the Claude Code CLI). See docs/PROVIDERS.md.
export SECHOUND_LLM=claude

# File a candidate, fan a hunt out to parallel lanes, review at the end:
python tools/ingest.py --json '{"title":"...","severity":"HIGH","service":"api","summary":"..."}'
python tools/orchestrate.py engagements/<id> tasks/<run>.yaml
python tools/ultrareview.py engagements/<id>
```

The orchestration entry points are documented in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md); the methodology in
[`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## Status

Ships a runnable core: the registry (`tools/findings_db.py`, `tools/ingest.py`),
the model-agnostic seam (`tools/llm.py`), and the pipeline stages
(`tools/critic.py`, `tools/compounder.py`, `tools/ultrareview.py`,
`tools/orchestrate.py`) with their prompts in `prompts/`. It ships with **no
target data** — see `SANITIZATION.md` for the bar every file clears (no target
hosts, IDs, credentials, or findings).

## Authorized use only

SecHound is offensive security tooling. Use it **only** against systems you own
or are explicitly authorized to test. You are responsible for staying within
your scope and the law. See `LICENSE`.

## License

MIT — see `LICENSE`.
