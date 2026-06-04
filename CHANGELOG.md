# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this project uses [SemVer](https://semver.org/).

## [Unreleased]

## [0.1.0] — 2026-06-04

Initial open-source release: the generic, model-agnostic core extracted from a
private engine, with no target data.

### Added
- Pipeline: `plan → execute → verify → critic → compound` with prompts in
  `prompts/` and drivers in `tools/` (`run.py`, `critic.py`, `verify_finding.py`,
  `compounder.py`, `ultrareview.py`, `orchestrate.py`).
- Findings registry (`tools/findings_db.py`) with root-cause de-duplication;
  `ingest`/`report` CLIs; SARIF export for GitHub code scanning.
- Two-identity diff (`tools/tenant_diff.py`) — the cross-tenant/IDOR/BOLA gate.
- Model-agnostic LLM seam (`tools/llm.py`): `claude` CLI, generic `command`,
  Anthropic, and OpenAI-compatible backends, selected by `$SECHOUND_LLM`.
- `sechound` CLI + `pyproject.toml`; engagement scaffolding (`init`).
- Docs: ARCHITECTURE, METHODOLOGY, FP_CHECKLIST, PROVIDERS; hunt-skill and
  agent templates.
- Tests (pytest, network-free) and CI, including a sanitization leak-gate
  (`scripts/check_sanitization.sh`) that runs on every PR.
