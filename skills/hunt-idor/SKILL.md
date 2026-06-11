---
name: hunt-idor
description: IDOR/BOLA hunt playbook — object-level authorization, cross-tenant reads, the mandatory two-identity diff. A worked example of the hunt-skill format.
domain: web
---

# hunt-idor

Load when testing object-level authorization, cross-tenant data access, or BOLA
in any component. The two-identity diff is mandatory before confirming.

## When to load
IDOR, BOLA, cross-tenant, object reference, `findById`, tenant isolation,
"can user A read user B's resource", direct object id in path/body.

## Where this class lives
Endpoints that take an object identifier (path, query, or body) and return or
mutate that object:
- `GET/PUT/DELETE /.../{id}` handlers,
- list endpoints that accept a `tenant_id` / `org_id` / `owner_id` filter from
  the request body,
- bulk/batch operations over a list of ids.

Trace each one: is the object lookup **scoped to the caller's tenant/owner**, or
does it resolve by id alone and trust the caller?

## Neutralizing controls (invalidators — check, don't assume)
- **Authorization layer below the handler** — an ORM filter, DB row policy, or
  gateway that injects `WHERE tenant_id = :caller` on every query. The control
  may live one layer down from the handler; verify it's on *this* path. Do not
  assume one component's control exists in another.
- **Ownership check in the handler** — explicit `if obj.owner != caller: 403`.
- **Unguessable ids** — UUIDv4 raises difficulty but is not authorization; a
  leaked/enumerated id still wins if there's no scope check.

## Probes
Authenticate as identity A (owner) and identity B (a *different* tenant/user).
Request A's object id while authenticated as B.

## Validation bar — TWO IDENTITIES REQUIRED
A single-identity repro is **not** validation. Run the two-identity diff:

```bash
python3 tools/tenant_diff.py \
    --url https://app.example.test/api/v1/objects/<A_OBJECT_ID> \
    --jar-a ~/.auth/identity_a.cookies \
    --jar-b ~/.auth/identity_b.cookies
```

`confirmed` only on verdict `cross_tenant_leak` (B received A's data). `403/404`
for B → `isolation_holds` (not a finding). Both 2xx with different bodies →
`possible_leak`: do NOT dismiss — the victim's resource may differ from the
attacker's own view or vary per request. Verify manually (compare B's body
against A's resource, not against B's own), then file or drop.

## Known chains
IDOR write (reassign owner / change tenant) → privilege escalation or account
takeover. IDOR read of an invite/reset token → takeover. Each step is its own
candidate until proven.
