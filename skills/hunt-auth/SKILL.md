---
name: hunt-auth
description: Authentication & authorization hunt playbook — authn bypass, broken session/JWT, missing function-level authz, CSRF.
domain: web
---

# hunt-auth

Load when testing login, sessions, tokens, role/permission enforcement, or
state-changing requests.

## When to load
auth bypass, authn, authz, broken access control, JWT, session fixation,
privilege escalation, missing function-level authorization, CSRF, OAuth/OIDC, SSO.

## Where it lives
- Authn: login, password reset, MFA, magic links, token issuance.
- Session/JWT: token signing/verification, expiry, `alg` handling, cookie flags.
- Authz: per-route/per-action role checks; admin-only functions; vertical privesc.
- CSRF: state-changing requests lacking anti-CSRF + safe-method discipline.

## Neutralizing controls (check, don't assume)
- Server-side authz enforced per action (not just hidden UI / client checks).
- JWT verified with the expected alg + key; `none`/alg-confusion rejected; expiry enforced.
- Session tokens rotated on privilege change; cookies `HttpOnly`/`Secure`/`SameSite`.
- Anti-CSRF token or `SameSite` on state-changing endpoints.

## Probes
Replay a lower-privilege session against a higher-privilege function; tamper JWT
alg/claims; remove/alter the CSRF token; reuse a reset token. Two principals
(low vs privileged) for vertical/horizontal checks.

## Validation bar
`confirmed` = an action runs without the authorization it requires — proven with
the negative case (a principal that *should* be denied succeeding). For
multi-tenant horizontal access, see the web-appsec profile's two-identity diff.

## Known chains
Authz gap → IDOR/BOLA, account takeover, admin compromise.
