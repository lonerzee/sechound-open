# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this project uses [SemVer](https://semver.org/).

## [Unreleased]

### Added
- **Domain-neutral core.** Finding schema, FP checklist, prompts, and invariants
  generalized beyond web/multi-tenant; web specifics moved to a profile.
- **Profiles** (`profiles/`) — domain packs (web-appsec, secrets, cloud-iac,
  deps, binary, llm) carrying FP patterns, invariants, skills, and validators.
- **Scanner interop** — `tools/import_sarif.py` (semgrep/CodeQL/nuclei/Trivy/
  grype/gitleaks → registry, root-cause deduped) + `tools/triage.py` (LLM
  true/false-positive triage). Positions SecHound as a triage/verification layer.
- **Hunt-skill library** expanded across domains: injection, xss, auth,
  path-traversal, deserialization, race, misc, file-upload, graphql,
  http-smuggling, business-logic, secrets, crypto, memory-safety,
  cloud-misconfig, iac, deps, prompt-injection, recon (+ existing ssrf/idor).
- **Agents** (`agents/`) — 11 specialist roles dispatchable as a swarm via
  `orchestrate.py`; `tasks/swarm.yaml` example.
- Docs: `VULN_TAXONOMY.md`, `INTEGRATIONS.md`, `EVIDENCE_HYGIENE.md`; README
  repositioned as a layer-over-scanners; new `import`/`triage`/`dast` CLI verbs.

### Fixed
- `claude --allowedTools` is variadic and swallowed a trailing positional
  prompt; the prompt now goes on stdin (every tool-using stage was exiting 1).

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
