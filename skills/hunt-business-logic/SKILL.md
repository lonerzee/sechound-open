---
name: hunt-business-logic
description: Business-logic hunt playbook — workflow/state abuse, price/quantity tampering, negative amounts, step-skipping that scanners miss.
domain: web
---

# hunt-business-logic

Load for flaws in *intended* functionality that no signature catches — the
application works "correctly" but the rules can be abused.

## When to load
business logic, workflow bypass, price manipulation, negative quantity, coupon
abuse, step skipping, approval bypass, parameter tampering, quota/limit abuse.

## Where it lives
Multi-step flows and money/quota/state: checkout, refunds, discounts, transfers,
approvals, onboarding, plan/seat limits, anything with a state machine.

## What to check (no payloads — it's about rules)
- **Tampering:** client-supplied price/quantity/total/currency trusted by server.
- **Sign/precision:** negative quantities, integer rounding, currency confusion.
- **State machine:** skip/reorder steps (pay→ship without pay; approve own request).
- **Replay/over-use:** reuse one-time coupons/tokens; exceed plan limits.
- **Trust boundary:** server recomputes vs. trusts client-asserted facts.

## Neutralizing controls (check, don't assume)
- Server authoritatively recomputes prices/totals/permissions; client values ignored.
- State transitions validated server-side against the current state.
- Idempotency / single-use enforced atomically (overlaps `hunt-race`).

## Validation bar
`confirmed` = you achieve a state the rules forbid (pay less, get more, skip a
required gate, exceed a limit) with concrete evidence. Reason about *intended*
behavior — the model/operator's judgment carries this, not a payload list.

## Known chains
Logic flaw → financial loss, privilege/seat escalation, free service.
