# Methodology

How to run an engagement with SecHound. Target-agnostic; fill in your own scope.

## Two entry points

1. **Triage existing scan output** (fastest value). You already run scanners —
   import their SARIF, let SecHound dedup + LLM-triage + verify:
   ```bash
   python3 tools/import_sarif.py semgrep.sarif trivy.sarif nuclei.sarif
   python3 tools/triage.py              # TP / FP / needs-verification, ranked
   python3 tools/verify_finding.py <engagement>   # confirm the survivors
   ```
2. **Hunt from scratch** — the full loop (below), optionally fanning out the
   [agents](../agents/) as a swarm. Both land in the same registry and share the
   verify → critic → report tail.

Set the active [profile](../profiles/) for your domain so the right FP patterns
and invariants load.

## 0. Scope & authorization

Write down what you are authorized to touch and for how long, in
`config/targets.yaml`. SecHound rejects requests against hosts not listed. This
is not optional — offensive testing without written authorization is illegal.

## 1. Knowledge first

Before grepping, load what you already know about the target:
- a structural map of the services/components,
- the prior findings registry (don't re-find what's tracked),
- the stated invariants (`config/invariants.yaml`).

Grep is the *fallback* when knowledge doesn't answer the question, not the
first move.

## 2. Translate the request

Turn the vague ask into a verifiable plan with gates:

| Vague | Reframed |
|---|---|
| "audit X for SSRF" | enumerate outbound-HTTP sinks → invalidator analysis → ranked candidates w/ file:line + reachability |
| "validate Y" | reproduce on authorized scope, capture req/resp, run critic, return verdict |
| "is this exploitable?" | define what exploitable *requires* (live PoC? leak? RCE?) → run that test |
| "review this PR" | apply FP checklist + invalidator table per change → verdict per file |

## 3. Hunt (multi-pass)

Run 2–3 sweeps with **new vectors each pass**. After each finding ask "would an
attacker stop here?" — usually no, so keep escalating to the deepest
demonstrable end-state. Revalidate prior findings to confirm they aren't
one-offs. Never single-pass.

For multi-class or multi-service work, fan out to parallel sub-agents (see
`agents/`) rather than grepping sequentially in one context.

## 4. File candidates

File as `candidate (code-only)`. Don't pre-retract — apply the FP patterns to
*sharpen* the candidate, then file. Filing is cheap; missing a real bug is not.

## 5. Validate

For anything you intend to confirm:
- reproduce against live authorized scope,
- apply the FP checklist mechanically,
- for cross-tenant/IDOR/BOLA, run the two-identity diff,
- run the critic to challenge your own verdict.

Promote to `confirmed` only with captured evidence and a runnable repro.

## 6. Hunt for variants

A confirmed finding has a root-cause signature (an exact sink + the control that
should have neutralized it). Sweep the rest of the codebase for the same
signature — bugs cluster.

## 7. Chain & escalate

Each chain component must be at least a code-only candidate with its own
invalidator analysis. Three or more components → plan the path explicitly.
Cross-service chains require confirming the inter-service identity model.

## 8. Report

The registry is the artifact. A report is a view over confirmed findings with
evidence and repro steps. No filler, no structure-for-structure's-sake.

## Verdict discipline

Every claim resolves to **exploitable | not exploitable | unknown**. If
unknown, name the single test that resolves it and run it. Don't manufacture
confidence or doubt.
