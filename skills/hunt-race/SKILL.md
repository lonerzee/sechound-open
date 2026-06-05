---
name: hunt-race
description: Race condition / TOCTOU hunt playbook — concurrent requests breaking a limit, balance, or state check.
domain: web
---

# hunt-race

Load when a check and an action aren't atomic and concurrency could break an
invariant (limits, balances, one-time tokens, state transitions).

## When to load
race condition, TOCTOU, double-spend, limit bypass, concurrent requests,
idempotency, single-use token reuse.

## Where it lives
read-modify-write without a lock/transaction: coupon/credit redemption, balance
debits, seat/quota limits, "use once" tokens, approval state machines.

## Neutralizing controls (check, don't assume)
- DB transaction + row lock / atomic decrement / unique constraint.
- Idempotency keys; optimistic concurrency (version check) on the write.
- Single-use enforced atomically (consume + check in one operation).

## Probes
Fire N concurrent identical requests (HTTP/2 single-packet, or parallel
clients) at the window between check and commit; measure whether the invariant
breaks (e.g. balance goes negative, token used twice).

## Validation bar
`confirmed` = repeated concurrent trials demonstrably break the invariant
(over-redeem, over-spend, double-use). One trial is not proof — show it across runs.

## Known chains
Limit bypass → financial loss, quota abuse, privilege/seat escalation.
