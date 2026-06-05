---
name: hunt-secrets
description: Secret-exposure hunt playbook — hardcoded credentials/keys/tokens in code, config, history, and artifacts.
domain: secrets
---

# hunt-secrets

Load when looking for credentials embedded in source, config, build artifacts,
container images, or VCS history.

## When to load
hardcoded secret, leaked key, API token, credential in repo, secret in git
history, secret in container image, .env committed.

## Where it lives
Source/config files, `.env`, CI config, Dockerfiles/layers, client bundles,
mobile app packages, and **git history** (a rotated-out file still lives in history).

## Neutralizing controls / false positives (check, don't assume)
- Placeholder/example values (`sk-EXAMPLE`, `changeme`, fake test fixtures).
- Already-rotated/revoked secrets (still report exposure, but note state).
- Public/non-secret values (publishable keys, doc samples).
- High entropy alone ≠ secret — confirm it's a live credential and reachable.

## Probes
Entropy + known key-format regexes (AWS `AKIA…`, `ghp_…`, JWT, PEM, slack `xox…`).
Scan history (`git log -p`, all branches), not just HEAD. For a candidate, test
whether it authenticates (only if in scope/authorized).

## Validation bar
`confirmed` = the secret is real, currently valid, and reachable by an attacker
(committed/published/served). A fixture or revoked key is INFO/LOW.

## Known chains
Leaked cloud key → account access; leaked signing key → token forgery; leaked
CI token → supply-chain compromise.
