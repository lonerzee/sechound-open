# Evidence hygiene

Before any finding, repro, or report leaves your machine, sanitize it. Findings
carry the most sensitive byproducts of testing — credentials you captured, PII,
internal hostnames. Leaking them in a report is its own incident.

This is the CAPTURE step of the loop. The `reporter` and `secrets-hunter` agents
are required to apply it; do the same for anything you hand off.

## Redact before capture

- **Credentials & tokens** — cookies, `Authorization` headers, API keys, JWTs,
  session ids, PATs. Replace with `<redacted>`. Never paste a *live* secret into
  a finding or report, even when the finding *is* "this secret leaked" — cite
  its location and a masked prefix, not the value.
- **PII** — names, emails, phone numbers, addresses, account ids of real users.
  Black-bar or synthesize.
- **Internal infrastructure** — internal hostnames, IPs, paths, dashboard URLs
  that aren't needed to understand the finding.

## Trim and make reproducible

- **Trim noise** — include the request/response lines that matter, not 40KB of
  headers. A reviewer should see the signal immediately.
- **Repro must be self-contained** — `repro.sh` should read secrets from the
  environment or a gitignored jar, never hard-code them. It must run without
  your shell history or local aliases. (This is what `verify_finding` re-runs.)
- **Screenshots** — crop to the relevant pane; redact tokens in URLs and headers
  visible in the shot.

## Storage

- Real findings, evidence, engagements, and cookie jars are **gitignored** (see
  `.gitignore` / `SANITIZATION.md`) — they never enter the open-source tree.
- The sanitization gate (`scripts/check_sanitization.sh`) blocks common secret
  patterns at commit/CI time as a backstop — not a substitute for redacting.

## Quick self-check before sharing
- [ ] No live credential/token/cookie/key in the text or screenshots.
- [ ] No real PII.
- [ ] Repro runs clean from a fresh shell with no hard-coded secrets.
- [ ] Output trimmed to the relevant lines.
