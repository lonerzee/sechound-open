# Agentic FP checklist (ASI01–ASI10)

Neutralizing controls and retraction traps specific to agentic systems. Check
each before filing — and before accepting a retraction.

## Controls that make an instance a false positive
- **Runtime-enforced tool authz** — the tool checks the *requesting principal's*
  permission on every call, independent of what the model asked. Confirm it's on
  *this* tool's path; a guard on one tool is not a guard on another.
- **Principal/identity binding** — the agent acts as the requesting user, not a
  shared service identity; delegated tokens are scoped and short-lived. Verify
  the downstream call carries the *caller's* identity, not a broader one.
- **Signed / authenticated inter-agent messages** — A2A messages are
  authenticated and integrity-checked; a message from an unknown or spoofed
  sender is rejected. Bypass = unauthenticated bus, or trust-by-topic.
- **Sandbox / egress containment** — tool execution is isolated (no host fs,
  allow-listed egress); escape requires crossing a real boundary. Prove the
  boundary is actually enforced, not just configured.
- **Policy on agent lifecycle** — sub-agent spawn, tool grants, and persistence
  are policy-gated and TTL-bound; an agent cannot widen its own mandate.
- **Human-approval integrity** — what the human approves is what executes; the
  summary shown is derived from the actual action, not a model-authored gloss.

## Retraction traps (do NOT accept these as "fixed")
- "The classifier blocks that prompt" — classifiers are probabilistic; an
  obfuscated/encoded variant is still in scope. Not an invalidator on its own.
- "The model is instructed not to" — a system-prompt instruction is not an
  enforced control. Only a runtime check counts.
- "It only worked in one run" — non-determinism is not safety; a flaky exploit
  is still an exploit. Re-run; report the success rate.
- "No tool actually fired" for goal-hijack — correct: that one IS a candidate,
  not confirmed. Keep the discipline both ways.
