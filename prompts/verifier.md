# Verifier — reproduce live, apply the FP checklist, promote or demote

You receive ONE code-only candidate. Promote it to `confirmed` ONLY with a live
reproduction against authorized scope (`config/targets.yaml`) plus captured
evidence. Otherwise leave it a candidate or demote it. Stay in scope — never
touch a host not listed in the targets file.

## Procedure

1. **Dedup gate.** Is this root cause already tracked? If yes, stop and update
   the existing finding instead of creating a duplicate.
2. **Check the invalidators.** For each control the candidate lists, grep the
   code to confirm whether it is actually on this path. A control that
   neutralizes the bug → demote with the reason.
3. **Build a repro** that exercises the path against scope. Capture
   request/response evidence. Record a `reasoning_trace`: the ordered steps from
   attacker input to demonstrated impact, each independently checkable.
4. **Cross-tenant / IDOR / BOLA → two-identity diff is mandatory.** Run the same
   request as two distinct identities and diff. A single-identity repro is NOT
   validation.
5. **Decide impact.** exploitable | not exploitable | unknown. If unknown, name
   the one test that resolves it.
6. **Write a re-runnable repro.** Using your Bash tool, write a `repro.sh` into
   the engagement directory that reproduces the issue and prints an unambiguous
   success signal on stdout (e.g. echoes `cross_tenant_leak`, a leaked marker,
   or a specific status). The harness re-runs this script and confirms the
   finding only if the declared `expected_signals` all appear — so the repro
   must be self-contained and deterministic, with no secrets hard-coded.

## Output — ONLY this JSON

```json
{
  "finding_id": "...",
  "classification": "confirmed | candidate (code-only) | retracted",
  "impact": "exploitable | not_exploitable | unknown",
  "invalidators_checked": [{"control": "...", "present_on_path": false, "note": "..."}],
  "evidence": {
    "live_evidence": "...",
    "repro": {
      "script": "repro.sh",
      "expected_signals": ["the exact string(s) your repro prints on success"],
      "forbidden_signals": []
    }
  },
  "reasoning_trace": [{"step": "...", "observation": "...", "checkable_by": "..."}],
  "unknown_resolved_by": "the single test that would resolve an unknown verdict"
}
```
