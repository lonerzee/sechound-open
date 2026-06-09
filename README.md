# SecHound

[![ci](https://github.com/lonerzee/sechound-open/actions/workflows/ci.yml/badge.svg)](https://github.com/lonerzee/sechound-open/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

**The triage-and-verification layer for your security scanners. Any model.**

Scanners are good at finding candidates and bad at the part that follows: which
hits are real, which are duplicates of the same root cause, and which survive a
live reproduction. That triage *is* the work. SecHound bakes it in — and nothing
becomes a `confirmed` finding on a model's say-so.

> **See it work in 10s, no API key:** `bash examples/demo.sh` — confirms a real
> IDOR end-to-end against a bundled vulnerable target. Walkthrough in
> [`docs/QUICKSTART.md`](docs/QUICKSTART.md).

Three things make it not just another scanner:

- **A layer, not a scanner.** Pipe your existing tools in as SARIF (semgrep,
  CodeQL, nuclei, Trivy, grype, gitleaks). SecHound de-duplicates by root cause,
  LLM-triages true vs. false positive, live-reproduces the real ones, and exports
  ranked findings back out as SARIF. It complements your toolchain instead of
  competing with it.
- **Model-agnostic.** Every stage talks to an LLM through one seam
  (`tools/llm.py`): Claude Code CLI, a local model via Ollama, or any
  OpenAI-/Anthropic-/Gemini-compatible API — one env var, no stage code changes.
  Run it fully local when source can't leave the building. See
  [`docs/PROVIDERS.md`](docs/PROVIDERS.md).
- **Verification is the product.** Kill gate before anything is filed; mandatory
  invalidator analysis; live-repro required to promote `candidate → confirmed`;
  a two-identity diff (`tenant_diff`) for IDOR/BOLA. The part humans hate, done
  mechanically.

```bash
semgrep --sarif -o out.sarif .
python3 tools/import_sarif.py out.sarif --domain web   # dedup on the way in
python3 tools/triage.py                                # LLM sorts TP/FP, ranks
python3 tools/report.py --status candidate --format md
```

**Domain-neutral.** Not just web/API — the pipeline and registry work for
cloud/IaC, dependencies, secrets, native/binary, and LLM apps. Domain specifics
live in optional [profiles](profiles/) and a library of [hunt
skills](skills/); the [vulnerability taxonomy](docs/VULN_TAXONOMY.md) lists
what's covered. Specialist [agents](agents/) can be fanned out as a swarm.
See [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md) for how it plugs into your
toolchain.

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

## What's in the box

- **Registry** (`tools/findings_db.py`, `ingest`) — root-cause de-duplication, SARIF export.
- **Scanner interop** — `tools/import_sarif.py` (semgrep/CodeQL/nuclei/Trivy/grype/gitleaks) + `tools/triage.py` (LLM true/false-positive triage).
- **Model-agnostic seam** (`tools/llm.py`) — Claude CLI / Ollama / Anthropic / OpenAI-compatible / Gemini.
- **Pipeline** — `run` (plan→execute→verify→critic→compound), `verify_finding`, `critic`, `ultrareview`, `compounder`, `orchestrate`.
- **Domain packs** — [`profiles/`](profiles/) (web-appsec, secrets, cloud-iac, deps, binary, llm) + a [hunt-skill library](skills/) spanning [many vuln classes](docs/VULN_TAXONOMY.md).
- **Agents** — [`agents/`](agents/) specialist roles (recon, web/code/cloud/deps/secrets/binary hunters, triage, validator, chain-builder, reporter) dispatchable as a swarm.
- **Validators** — `tenant_diff` (two-identity proof), `verify_finding` (re-runnable repro contracts; refuses to exec untrusted-source repros without `--allow-exec`).
- **DAST** — `tools/dast.py` + nuclei-style templates.
- **Ops** — `sechound doctor` (preflight: backend/deps/tools/config), `Dockerfile`, CI + sanitization gate.

Ships with **no target data** — see [`SANITIZATION.md`](SANITIZATION.md) for the
bar every file clears (no hosts, IDs, credentials, or findings), enforced in CI.

## Authorized use only

SecHound is offensive security tooling. Use it **only** against systems you own
or are explicitly authorized to test. You are responsible for staying within
your scope and the law. See `LICENSE`.

## References

Two things were useful to look at while building: Anthropic's **defender's loop**
(security as a repeatable model → hunt → validate → hunt-for-variants cycle) and
**Claude BugHunter** (a library of focused, reusable hunt skills an agent is
pointed through). SecHound's own contribution is the verification gates and the
persistent, compounding knowledge.

## License

MIT — see `LICENSE`.
