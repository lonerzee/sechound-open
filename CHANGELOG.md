# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this project uses [SemVer](https://semver.org/).

## [Unreleased]

### Added
- **Benchmark with condition tracking.** `tools/benchmark.py` + `bench/suite.yaml`
  run the real probes against the bundled labs and score detection per class,
  recording the conditions (box level, hints) alongside the score — the one
  thing the 2026 agent-pentest surveys say every result omits. `--autostart`
  stands the labs up; positive cases must be detected and negative (safe-route)
  cases must not be flagged (false-positive control). Bundled suite scores 1.0
  with 0 false positives; `--min-rate` makes it a regression gate.
- **Disclosed-report → skill miner.** `tools/skill_miner.py` ingests a corpus of
  disclosed reports and emits a hunt-skill playbook per class where every pattern
  (sink / control / bypass / chain) is attributed to the report(s) it came from —
  auditable instead of asserted. Ships a generic `profiles/disclosures/` sample
  so it runs offline; refuses to clobber a hand-written skill without `--force`.
- **Grounding gate (anti-hallucination).** `tools/grounding_gate.py` enforces
  that every claim a `confirmed` finding makes traces to a logged observation —
  a signal in captured repro output, or a quote that actually appears in the
  cited source file. Confirmed-with-no-evidence or hallucinated file:line is
  flagged `ungrounded` and the gate exits non-zero (CI/pipeline-usable).
- **DAST templates + a vulnerable lab for the new classes.** The bundled
  `examples/vulnerable_target.py` now plants mass-assignment (API3), BFLA (API5)
  and unbounded-consumption bugs, each with a safe-route contrast; three new
  `dast/templates/` fire against them. A second lab, `examples/vulnerable_mcp.py`
  (HTTP + stdio), plants an MCP workspace-IDOR that `mcp_probe` proves live.
  `mcp_probe` gained a **stdio transport** (most real MCP servers run that way).
- **Executable AI validators (proof, not prose).** `tools/mcp_probe.py` — an MCP
  JSON-RPC falsifier (two-principal workspace-IDOR diff, rug-pull tool-definition
  detection, tool-result-injection exposure, credential-passthrough), and
  `tools/rag_probe.py` — a plant→retrieve-later→diff harness for RAG/embedding/
  memory poisoning (cross-context + persistence), corpus-agnostic via shell
  adapters. Both follow the `tenant_diff` contract: a pure, unit-tested verdict
  core and a non-zero exit only on a confirm-grade signal, so they drive a
  `verify_finding` repro. The `mcp`/`agentic`/`llm` profiles now point at these
  real validators instead of the HTTP-only `tenant_diff`; `hunt-mcp` and
  `hunt-rag-poisoning` carry the exact invocations. +13 tests (now 61).
- **Full OWASP AI coverage.** Expanded the `llm` profile to the complete OWASP
  Top 10 for LLM Apps (2025) and added two new profiles: `agentic` (OWASP Top 10
  for Agentic Applications, ASI01–ASI10) and `mcp` (Model Context Protocol
  attack surface). 16 new hunt skills — `hunt-excessive-agency`,
  `hunt-system-prompt-leak`, `hunt-rag-poisoning`, `hunt-insecure-output`,
  `hunt-unbounded-consumption`, `hunt-ai-supply-chain`, `hunt-agent-goal-hijack`,
  `hunt-agent-identity-privilege`, `hunt-inter-agent-comms`,
  `hunt-cascading-failures`, `hunt-human-agent-trust`, `hunt-rogue-agents`,
  `hunt-agent-code-exec`, `hunt-mcp`, plus web `hunt-mass-assignment` (API3/BOPLA)
  and `hunt-function-authz` (API5/BFLA). Each skill maps to its OWASP ID and
  keeps the observed-effect validation bar (no `confirmed` on the model merely
  "agreeing"). `VULN_TAXONOMY.md` now carries the OWASP LLM/ASI/API mappings.

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

- **Skills are now machinery, not just docs:** `sechound_lib` loads skill
  bodies + a catalog and injects them into the planner (catalog) and executor
  (the skills the plan/profile call for). Profiles' `skills:` lists are parsed.
- **Triage scales + is safer:** `triage.py` batches findings per LLM call
  (`--batch-size`, `--max-batches` cost cap, `--skip-info`) instead of one call
  each. `verify_finding` refuses to run repro scripts from imported/untrusted
  sources (`sarif:*`, etc.) without `--allow-exec` — closes an operator-RCE path.
- **Packaging:** `sechound doctor` preflight, a `Dockerfile`, and a real-scan
  interop quickstart.

### Fixed
- `claude --allowedTools` is variadic and swallowed a trailing positional
  prompt; the prompt now goes on stdin (every tool-using stage was exiting 1).
- Schema↔tools drift: `findings_db`/`report` now read `component`/`location`/
  `domain` (not just `service`/`endpoint`); dedup collapses cross-scanner hits on
  the same location; profiles' FP patterns + invariants are actually injected.

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
