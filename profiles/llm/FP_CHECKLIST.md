# LLM FP checklist (OWASP LLM Top 10, 2025)

Neutralizing controls and retraction traps for LLM apps. Check before filing —
and before accepting a retraction.

## Controls that make an instance a false positive
- **Privilege separation** — tools/plugins enforce their own authz on the
  requesting principal; the model's output cannot by itself perform a privileged
  action. The single most important control; confirm it's on *this* action.
- **Output treated as untrusted** — model output is encoded/validated before it
  reaches an HTML sink, a shell, a DB, or an outbound request (defeats LLM05).
- **System-prompt / secret separation** — secrets are not in the prompt; the
  system prompt carries no capability on its own (so leaking it is low impact).
- **Retrieval trust boundary** — RAG/KB content is scoped and provenance-checked;
  a document one tenant/user plants is not served to another (defeats LLM08/04).
- **Consumption limits** — per-principal rate/token/cost caps and loop budgets
  bound unbounded consumption (LLM10).

## Retraction traps (do NOT accept these as "fixed")
- **Hallucinated "leak"** — a model emitting plausible-looking "system prompt" or
  "secret" text is not disclosure unless it matches the REAL value. Verify, don't
  assume. (Also the inverse: don't dismiss a real match as "it just made it up".)
- **"The classifier caught it"** — classifiers are probabilistic; an
  encoded/obfuscated/multilingual variant may pass. Not an invalidator alone.
- **"The model refused once"** — non-deterministic; re-run and report the rate.
- **"It only agreed, didn't act"** — correct for a tool-abuse claim: that's a
  candidate, not confirmed. Hold the line both directions.
