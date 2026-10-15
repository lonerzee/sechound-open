---
name: hunt-mass-assignment
description: OWASP API3:2023 Broken Object Property Level Authorization — mass assignment (client sets properties it shouldn't) and excessive data exposure (response over-returns sensitive fields).
domain: web
---

# hunt-mass-assignment

Load when testing whether a client can set object properties it shouldn't
(mass assignment) or read fields it shouldn't (excessive data exposure) via
create/update endpoints. This is OWASP API3:2023. The privileged property must
be shown to actually take effect, with a two-identity check where privilege
differs.

## When to load
API3, mass assignment, auto-binding, over-posting, excessive data exposure,
property-level authorization, `role`, `is_admin`, `tenant_id`, `owner_id`,
`verified`, `status`, internal field, create/update body, PATCH/PUT body,
object serializer, model binding.

## Where this class lives
- **Create/update handlers** that bind a request body straight onto a model /
  entity (`new User(body)`, `obj.update(body)`, ORM auto-bind, `BodyParser` →
  struct). Any field present in the body may be writable.
- **Sensitive properties** on those objects: `role`, `is_admin`,
  `permissions`, `tenant_id`/`org_id`, `owner_id`, `verified`, `email_verified`,
  `status`, `approved`, `balance`, `price`, `plan`, timestamps, internal ids.
- **Response serializers** that return the full object: look for sensitive
  fields leaking in the response (`password_hash`, tokens, other users' PII,
  internal flags) — excessive data exposure.

Enumerate: for each writable object, list its properties, and for each property
ask "should *this* principal set/read it?" Diff the create/update body schema
against the full persisted model.

## Neutralizing controls (invalidators — check, don't assume)
- **Allow-list binding (DTO / explicit field map)** — the handler binds only a
  named set of fields and drops the rest. Confirm the privileged field is *not*
  in the allow-list on this path. Bypass: nested objects, array/JSON sub-fields,
  or an alternate alias for the same column that escapes the list.
- **Read-only / server-set attributes** — ORM marks `role`, `tenant_id` etc.
  non-insertable/updatable, or they're set server-side from session. Confirm the
  attribute is actually ignored when supplied. Bypass: a secondary endpoint
  (admin API, import, bulk) that does bind it.
- **Property-level authorization** — a policy gates *which* principal may set a
  field (owner can set `status`, only admin can set `role`). Confirm the gate
  fires for a lower-priv principal. Bypass: method/route variant that skips it.
- **Response projection** — serializer returns a reduced view per caller role.
  Confirm the sensitive field is absent for the low-priv view; bypass is an
  include/expand param or a sibling endpoint returning the full object.

## Probes
Benign, parameterized. Authenticate as a principal that should NOT control the
field.

- **Mass assignment (create):** `POST https://app.example.test/api/v1/users`
  body `{"email":"probe@example.test","name":"probe","role":"admin",
  "is_admin":true,"tenant_id":"<OTHER_TENANT>","verified":true}` — then re-read
  the object and check which privileged fields stuck.
- **Mass assignment (update):** `PATCH https://app.example.test/api/v1/users/<SELF>`
  body `{"role":"admin","verified":true,"owner_id":"<SELF>"}`.
- **Nested/alias variant:** `{"profile":{"role":"admin"}}` or `{"roleId":1}` when
  the direct field is blocked.
- **Excessive exposure:** `GET https://app.example.test/api/v1/users/<SELF>` and
  list every returned field; flag any sensitive/internal field present.

## Validation bar
`confirmed` requires an OBSERVED effect, not just a 2xx on the write:
- **Mass assignment:** the privileged property actually **persisted and took
  effect** for a principal that shouldn't set it — re-read the object (or
  exercise the privilege, e.g. the `role:admin` now grants an admin action).
  A 200 that silently dropped the field is `not_confirmed`.
- **Excessive data exposure:** a sensitive field actually **returned** in a
  response to a principal not entitled to it.

Where privilege differs between principals, prove it with the two-identity diff —
low-priv principal sets/reads the field, compare against what the privileged
principal legitimately sees:

```bash
python3 tools/tenant_diff.py \
    --url https://app.example.test/api/v1/users/<OBJECT_ID> \
    --jar-a ~/.auth/lowpriv.cookies \
    --jar-b ~/.auth/privileged.cookies
```

## Known chains
Mass-assign `role`/`is_admin`/`permissions` on self → vertical privilege
escalation. Mass-assign `tenant_id`/`org_id` → cross-tenant object planting or
takeover (chains into BOLA/API1). Mass-assign `verified`/`approved`/`status` →
bypass of an approval or email-verification gate. Excessive exposure of a
`password_reset_token` / session token / other users' PII → account takeover or
further enumeration.
