---
name: hunt-graphql
description: GraphQL hunt playbook — introspection, authz gaps per resolver, batching/alias abuse, injection through resolvers.
domain: web
---

# hunt-graphql

Load when the target exposes a GraphQL API.

## When to load
GraphQL, introspection, resolver, query batching, alias overloading, DoS via
nested queries, GraphQL injection.

## Where it lives & what to check
- **Introspection** enabled in prod → full schema map (recon win, not a bug alone).
- **Per-resolver authz:** auth often enforced at the HTTP layer but missing on
  individual resolvers/fields → object/field-level access control gaps (BOLA).
- **Batching/aliases:** many operations per request bypass per-request rate
  limits (brute force) or amplify cost (DoS).
- **Injection:** resolver args reaching SQL/NoSQL/OS (see `hunt-injection`).
- **Mutations:** state-changing mutations missing CSRF/authz.

## Neutralizing controls (check, don't assume)
- Authz enforced in each resolver / via a schema directive, not only at the gateway.
- Introspection disabled in prod; query depth/complexity/cost limits; rate limits per-operation.

## Probes
Introspect the schema; call sensitive queries/mutations as a low-priv principal;
alias-batch a login mutation to bypass rate limits; deeply nest a query for cost DoS.

## Validation bar
`confirmed` = a resolver returns/mutates data the principal isn't authorized for,
or batching/depth produces real impact (rate-limit bypass, DoS). Introspection alone = INFO.

## Known chains
Resolver authz gap → BOLA → cross-account data; batch → credential brute force → ATO.
