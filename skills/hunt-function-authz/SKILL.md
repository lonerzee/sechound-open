---
name: hunt-function-authz
description: OWASP API5:2023 Broken Function Level Authorization (BFLA) — a lower-privilege principal reaching a privileged/admin function or endpoint, via missing per-action role checks, method-based bypass, or guessable admin routes.
domain: web
---

# hunt-function-authz

Load when testing whether a lower-privilege principal can invoke a privileged
FUNCTION (an admin/management action or endpoint) — distinct from reaching a
specific OBJECT (that's BOLA/API1). This is OWASP API5:2023. Confirmation
requires the privileged call to actually SUCCEED for the low-priv principal.

## When to load
API5, BFLA, function-level authorization, broken function level, privilege
escalation, admin endpoint, admin route, privileged action, role not enforced,
method bypass, GET vs POST, verb tampering, forced browsing, guessable admin
path, `/admin`, management API.

## Where this class lives
- **Administrative / management functions** — user management, role assignment,
  tenant config, feature flags, billing, data export, impersonation, bulk ops,
  "danger zone" actions. Enumerate from the admin UI's XHR calls, API docs/spec,
  route tables, and JS bundles (admin routes often referenced but hidden).
- **Action endpoints without per-call role checks** — handlers where auth checks
  *authentication* but not *the action's required role*; or where the role check
  sits in the UI/gateway, not the handler.
- **Method-sensitive handlers** — routes that enforce a role on one verb but not
  another (`GET` list gated, `POST`/`PUT`/`DELETE` not), or frameworks mapping
  multiple verbs to one unguarded method.
- **Guessable siblings** — `/api/v1/admin/...`, `/internal/...`,
  `.../{id}/promote`, `.../export`, numbered/patterned admin routes.

Enumerate: build the full privileged-function list from a privileged account,
then replay each as a lower-privilege (or unauthenticated) principal.

## Neutralizing controls (invalidators — check, don't assume)
- **Per-action role enforcement in the handler** — the function checks the
  caller's role/permission for *this action* server-side. Confirm it fires for a
  low-priv principal (not just the UI hiding the button). Bypass: check in a
  filter that misses an alternate route/verb.
- **Centralized policy / middleware** — a gateway or decorator maps route→required
  role. Confirm the privileged route is actually in the policy map and the map
  is consulted on this path. Bypass: a route not registered in the policy, or a
  path-normalization gap (`//`, `;`, case, trailing slash, encoded segment).
- **Method allow-listing** — handler restricts verbs and rejects the rest.
  Bypass: `X-HTTP-Method-Override`, `_method`, or a verb the gate ignores.
- **Deny-by-default** — unknown/unmatched routes 403 rather than fall through.
  Bypass: a route that matches a permissive pattern and escapes the default.

A hidden button, a 404 on a guessed path, or client-side role gating is NOT a
control — confirm the server authorizes the action.

## Probes
Benign, parameterized. Authenticate as a low-privilege principal (and separately
as unauthenticated). Prefer read-only or reversible privileged actions.

- **Forced function access:** replay a privileged call captured from an admin:
  `GET https://app.example.test/api/v1/admin/users` as the low-priv jar.
- **Method bypass:** if `POST .../admin/flags` is gated, try
  `GET`/`PUT`/`PATCH .../admin/flags`, and `POST` with
  `X-HTTP-Method-Override: GET`.
- **Guessable route:** enumerate `/api/v1/admin/*`, `/internal/*`,
  `.../{id}/promote`, `.../export` referenced in the JS bundle / spec.
- **Role escalation function:** low-priv principal calls the self-promote action
  `POST https://app.example.test/api/v1/users/<SELF>/role {"role":"admin"}` and
  checks the resulting effective role.

## Validation bar
`confirmed` requires an OBSERVED effect: the lower-privilege principal's request
to the privileged function actually **SUCCEEDED** — the action ran (state
changed, or privileged data was returned), not merely that the route was
reachable or returned 200 with an empty/benign body. A 2xx that performed no
privileged action, or returned the low-priv principal's own view, is
`not_confirmed`. Re-read state (or exercise the new privilege) to prove effect.

Where the finding is "low-priv could do what only admin should", prove it with
the two-identity diff — low-priv principal vs. the privileged baseline:

```bash
python3 tools/tenant_diff.py \
    --url https://app.example.test/api/v1/admin/users \
    --jar-a ~/.auth/lowpriv.cookies \
    --jar-b ~/.auth/admin.cookies
```

Low-priv receiving the same privileged response as admin → `bfla`. A 403/404 for
low-priv → `authz_holds`.

## Known chains
Reaching a user-management function (role assign / invite / impersonate) → direct
vertical privilege escalation to admin. Reaching a bulk-export or data function →
mass data disclosure. Method-bypass on a config/flag endpoint → enable a
privileged feature or disable a security control. BFLA on a cross-tenant admin
route combines with API1/BOLA to turn function access into tenant-wide
compromise. Each escalation step is its own candidate until proven.
