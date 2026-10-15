---
name: hunt-excessive-agency
description: LLM/agent hunt playbook — OWASP LLM06 Excessive Agency + Agentic ASI02 Tool Misuse; the tool-authorization boundary and confused-deputy chaining.
domain: llm
---

# hunt-excessive-agency

Load when an LLM or agent can invoke tools/functions and you need to prove the
TOOL enforces its own authorization, not the model's "judgement." Covers OWASP
LLM06 (Excessive Agency) and Agentic ASI02 (Tool Misuse).

## When to load
excessive agency, tool abuse, function calling, over-broad permissions, tool
authz, confused deputy, agent privilege, MCP tool scope, autonomous action,
"the model decided to call X", tool chaining.

## Where this class lives
Any sink where the model's output selects and parameterizes a real action:
- function/tool definitions exposed to the model (HTTP, shell, DB, filesystem,
  email, ticketing, admin APIs),
- tool-dispatch/router code that maps a model-chosen tool name + args to a call,
- agent frameworks where one tool's output feeds the next tool's input.
Enumerate the full tool manifest and, for each tool, trace whether the call is
gated by the CALLER's identity/scope or merely by the model having chosen it.
Excessive agency = excessive functionality (tools broader than the task needs),
excessive permissions (tool runs with more rights than the invoking user), or
excessive autonomy (high-impact action with no confirmation).

## Neutralizing controls (invalidators — check, don't assume)
- **Per-tool authz enforced below the model** — the tool handler re-checks the
  caller's permission/tenant on every invocation, independent of the prompt.
  Confirm it's on THIS tool's path; one tool's gate does not imply another's.
- **Allow-listed args/destinations** — the tool only accepts a fixed set of
  targets. Bypass: an arg shape the allow-list doesn't canonicalize (encoding,
  alias, path trick) that still reaches the sink.
- **Human-in-the-loop** on sensitive actions — confirm it fires for the exact
  tool and cannot be satisfied by model-generated "approval" text.
- **Least-privilege tool credentials** — the tool's own token is scoped tighter
  than the agent. Verify the scope, don't trust the tool name.

## Probes
Against `app.example.test` with a low-privilege identity, steer the agent to
call a tool whose action exceeds that identity's rights (e.g. read another
tenant's record, or invoke an admin-only function). Chain two tools so tool A's
output supplies a privileged arg to tool B (confused deputy). Try an arg that a
naive allow-list misses: `target=127.0.0.1` via alias, a path with `..`, or a
destination host that canonicalizes differently.

## Validation bar
`confirmed` requires an OBSERVED privileged side effect from the tool call: the
tool actually returned data the invoking identity could not otherwise read,
mutated state it was not authorized to change, or reached a destination outside
policy — captured in the tool response or downstream logs. The model *saying* it
will call the tool, or emitting the action in text, is NOT confirmation.

## Known chains
Over-broad tool + weak per-tool authz → cross-tenant read/write (BOLA via the
agent). Tool-chaining confused deputy → privilege escalation using the agent's
higher-privileged tool credential. Tool with network egress → SSRF / data exfil
→ metadata-service or internal-service pivot.
