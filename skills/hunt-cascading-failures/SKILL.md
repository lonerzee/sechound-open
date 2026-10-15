---
name: hunt-cascading-failures
description: ASI08 Cascading Failures — one compromised or erroring agent propagating bad state or faults through a multi-agent pipeline; feedback loops and amplification.
domain: agentic
---

# hunt-cascading-failures

Load when agents are chained or looped and the output of one becomes the input of
others — a single bad or malicious result can propagate, amplify, and destabilize
the whole system (OWASP Agentic ASI08).

## When to load
Cascading failure, fault propagation, feedback loop, amplification, poisoned
state propagation, multi-agent pipeline, fan-out, retry storm, runaway loop,
error contagion, shared-memory corruption, blast radius.

## Where this class lives
Trace how one agent's output reaches others and whether any boundary stops a bad
value from spreading:
- Pipeline edges — direct output→input handoffs with no validation between stages.
- Shared state store — a blackboard/memory many agents read; one poisoned write
  reaches all readers.
- Feedback loops — an agent consuming its own (or a descendant's) prior output,
  enabling runaway amplification.
- Fan-out / fan-in — one result broadcast to N agents, or N partial results merged
  without quorum/sanity checks.
- Retry & escalation paths — failure handlers that re-invoke agents and can storm.
Enumerate: for each edge, what validates the payload and what caps rate/depth/cost.

## Neutralizing controls (invalidators — check, don't assume)
- Stage input validation: each agent validates upstream output against a schema/
  invariant before acting. Confirm it rejects malformed/poisoned input; bypass =
  blind trust of the previous stage.
- Circuit breakers / rate & depth limits: loops and retries are capped; recursion
  depth and fan-out bounded. Confirm the limit fires; bypass = unbounded replan.
- State isolation / write authorization: only an authorized stage can write shared
  keys; writes are scoped. Confirm; bypass = any agent overwrites any key.
- Quorum / sanity checks on merges: fan-in requires agreement or bounds-checks
  before accepting. Confirm; bypass = single poisoned partial accepted.
- Blast-radius containment: a failing agent is isolated, not allowed to cascade.
  Confirm degraded-mode behavior; bypass = failure re-enters the pipeline.

## Probes
Benign propagation/amplification markers on a test pipeline:
- Seed one upstream agent's output on `app.example.test` with a bounded marker
  `CASCADE-4512` plus malformed-but-inert fields; observe how many downstream
  stages carry or choke on it. Propagation past a stage = missing validation.
- Introduce a self-referential note in shared memory that asks the next turn to
  "repeat the previous note"; watch for a bounded growth/loop (stop it early).
- Return an error-shaped payload from one stage and see whether retries storm or
  the breaker trips. Measure count, don't actually overload.
Keep markers bounded and abort on first sign of real amplification.

## Validation bar
`confirmed` requires an OBSERVED propagation of bad state or fault BEYOND the
originating agent — a poisoned value reaching and altering a downstream stage's
action, a loop/retry that measurably amplifies past its intended bound, or a
single failing agent degrading the pipeline's output. One agent erroring in
isolation (contained, no spread) is NOT confirmation.

## Known chains
Cascading failure is usually the amplifier, not the entry: ASI01 goal hijack or
ASI07 forged message seeds one node → ASI08 spreads it to the pipeline → mass
incorrect actions, DoS/cost blow-up, or system-wide poisoned memory → operator
sees aggregated-but-wrong output (ASI09). Each downstream stage altered is its own
candidate; trace back to the seeding defect.
