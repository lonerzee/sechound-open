# Sanitization checklist

SecHound must never contain data about any specific target. Every file passes
this checklist **before** it lands.

## The bar (every file must clear all of these)

- [ ] **No hostnames / domains** of any real target. Use `config/targets.yaml`
      (gitignored) and placeholders like `<TARGET_HOST>` in code and docs.
- [ ] **No tenant / org / account IDs.** No numeric or named tenant identifiers.
- [ ] **No credentials of any kind** — cookies, JWE/JWT, API keys, passwords,
      session jars, `Authorization` headers, magic links.
- [ ] **No findings** — no confirmed or candidate vulnerabilities against any
      real system, no CVE write-ups tied to a target, no evidence/PoC output.
- [ ] **No internal repo contents** or analysis of a specific company's source.
- [ ] **No personal data** — names, emails, employee handles, internal URLs.
- [ ] **No paths that leak environment** — `~/.auth/...`, internal wiki links,
      Grafana/Loki/MCP endpoints, dashboard URLs.

## What is intentionally NOT in this repo

These directories are **excluded by design** — they are target-specific by
nature and must never be committed:

- `findings_registry/`, `findings/*.json` (real records) — target findings
- `engagements/<dated>/` — real engagement artifacts
- `evidence/`, `exploits/` — PoCs, screenshots, captured traffic
- `repos/`, `repo_knowledge/` — clones/analysis of a target's source
- `global_knowledge/<target>/` — target topology, auth model, endpoint maps
- `reports/` — generated assessment reports
- `config/targets.yaml`, `config/*.cookies`, `.auth/` — scope + secrets
- `CLAUDE.local.md` and any `*.local.*` — operator-specific config

All of the above are in `.gitignore`. The example/templated versions
(`*.example.yaml`, `findings/schema.json`, `findings/example-finding.json`) are
synthetic and safe.

## Before you commit

1. Grep your change for target markers:
   ```bash
   rg -i '<target-domain>|<tenant-id>|cookie|bearer|jwe' path/to/file
   ```
2. Replace anything real with a placeholder + a `config/` lookup.
3. Tick the boxes above. Commit.

## Reporting a leak

If you find target-specific data in a published commit, treat it as a secret
leak: rotate any exposed credential, rewrite history if needed, and open an
issue. Deleting the file in a later commit is **not** sufficient — git history
retains it.
