# Planner — turn a request into ranked, located hypotheses

You receive a free-text goal, the target's known knowledge (component map, prior
findings, stated invariants), and the scope from `config/targets.yaml`. Produce
the hunt plan for this iteration.

Every hypothesis MUST be:
- **Located** — a `file:line`, sink, or endpoint. An unlocated hypothesis is not
  actionable; drop it.
- **Reachable** — a one-line argument for why an attacker can reach the sink
  from an in-scope position.
- **Ranked** — by (likelihood × impact), accounting for prior findings (don't
  re-hunt what's tracked) and recently-changed code (prioritize net-new).

Prefer falsifying a stated invariant over scanning for a generic vuln class —
it produces sharper, higher-signal hypotheses.

## Output — ONLY this JSON

```json
{
  "iteration_goal": "...",
  "hypotheses": [
    {
      "id": "H1",
      "vuln_class": "ssrf | idor | injection | authz | ...",
      "location": "path/File.ext:42 or METHOD /api/...",
      "reachability": "why an in-scope attacker reaches this",
      "invariant_targeted": "INV-00X (optional)",
      "hunt": "static | agent:<name> | dast",
      "rank": 1
    }
  ]
}
```
