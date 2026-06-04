# Agents

Specialized sub-agents the orchestrator dispatches in parallel. Each agent owns
one slice of the hunt (a vuln class, a service, a phase) and returns structured
candidate stubs — it does **not** confirm findings on its own.

## The contract

Every sub-agent must:

1. **Stay in scope.** Operate only against hosts in `config/targets.yaml`.
2. **Return code-only candidates**, never `confirmed`. Confirmation is the
   verifier's job, with live evidence.
3. **Cite location.** Every candidate carries `file:line` (and an endpoint when
   applicable) plus a one-line reachability argument.
4. **Include invalidators.** List the controls that would make the candidate a
   false positive, so the verifier knows what to check.
5. **Emit to the registry schema.** Output conforms to `findings/schema.json`
   so the merge step can de-duplicate by root cause.

## Suggested roles

These map cleanly onto the pipeline; add your own:

| Agent | Slice |
|---|---|
| recon | enumerate attack surface, routes, exposed components |
| static-hunter | per-vuln-class code search using a `hunt-<class>` skill |
| api-tester | live API behavior probing within scope |
| poc-validator | reproduce a candidate; produce evidence or demote |
| chain-planner | correlate confirmed findings into attack paths |
| reporter | render confirmed findings + evidence into a report |

## Merge step

After a parallel fan-out, the orchestrator merges every agent's stubs into the
single registry, de-duplicating by root cause (not by symptom — the same bug
found three ways is one record). Conflicts in severity/status are resolved by
the verifier and critic, not at merge time.
