---
name: recon
description: Attack-surface mapping playbook — enumerate the target with the standard open-source toolchain, then feed results into the pipeline.
domain: recon
---

# recon

Load at the start of an engagement to map the attack surface before hunting.
This is the SCOPE/RECON phase. Stay within authorized scope at all times.

## When to load
recon, enumeration, attack surface, subdomains, endpoints, asset discovery,
content discovery.

## The standard toolchain (bring your own; SecHound orchestrates around it)
- **Subdomains/DNS:** `subfinder`, `amass`, `dnsx`.
- **Live hosts/fingerprint:** `httpx` (status, tech, titles).
- **Crawl/endpoints:** `katana`, `gau`, `waybackurls`.
- **Content/params:** `ffuf`, `feroxbuster` + SecLists wordlists.
- **Templated checks:** `nuclei` (emits findings — import via `tools/import_sarif.py` or JSON).
- **Source/repos:** `gitleaks`/`trufflehog` (secrets), `semgrep`/CodeQL (code).

## Workflow
1. Confirm scope (`config/targets.yaml`) — never enumerate out-of-scope assets.
2. Enumerate → live hosts → crawl → rank surface by attacker value (writes,
   auth-adjacent, internal-looking, recently changed).
3. Feed the ranked surface to the planner as hunt targets; pipe any scanner
   output (nuclei/semgrep/trivy → SARIF) into the registry for LLM triage.

## Output
A ranked list of assets/endpoints with: what it is, auth tier (guessed),
why it's interesting. Recon does NOT file findings — it seeds hunting.

## Note
SecHound doesn't reimplement these tools — it sits on top, ranking their output
and driving verification. See `docs/INTEGRATIONS.md`.
