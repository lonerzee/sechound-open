---
name: hunt-misc
description: Catch-all web playbook — open redirect, CORS misconfig, header injection, clickjacking, mass assignment, rate-limit gaps.
domain: web
---

# hunt-misc

Load for common web issues without a dedicated skill.

## When to load
open redirect, CORS misconfiguration, host-header injection, response splitting,
clickjacking, mass assignment / autobinding, missing rate limit, info disclosure.

## Where it lives & what to check
- **Open redirect:** redirect target taken from input without an allow-list.
- **CORS:** reflected `Origin` + `Access-Control-Allow-Credentials: true`, or `*` with creds.
- **Host-header injection:** `Host`/`X-Forwarded-Host` used to build links/resets.
- **Mass assignment:** request body binds to privileged fields (`isAdmin`, `role`).
- **Rate limit:** sensitive actions (login, OTP, reset) with no throttling.

## Neutralizing controls (check, don't assume)
- Redirect/CORS allow-lists; credentials never combined with reflected/`*` origin.
- Canonical/configured host for link generation, not the request header.
- Explicit field allow-lists on binding; server sets privileged fields.

## Validation bar
`confirmed` = the misconfig produces a concrete effect: redirect to attacker
host, cross-origin credentialed read, privilege field set via mass assignment,
unthrottled brute force. Note the demonstrated impact for severity.

## Known chains
Open redirect → OAuth token theft; CORS → cross-origin data theft; mass
assignment → privilege escalation.
