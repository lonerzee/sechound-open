---
name: hunt-agent-code-exec
description: ASI05 Unexpected Code Execution — agent-driven code/command execution escaping its sandbox via tool-invoked shell/eval, container escape, or write-then-execute.
domain: agentic
---

# hunt-agent-code-exec

Load when an agent can cause code or commands to run — a code-interpreter tool, a
shell, an `eval`, a file it writes and then executes, or a sandboxed runtime it
might escape (OWASP Agentic ASI05).

## When to load
Unexpected code execution, agent code exec, tool-invoked shell, eval sink,
sandbox escape, container escape, code interpreter abuse, write-then-execute,
arbitrary command, RCE via agent, runtime breakout, interpreter tool.

## Where this class lives
Trace every path by which agent-chosen text becomes executed code:
- Code-execution tools — interpreter/shell/`eval`/`exec` tools the agent can call;
  check what bounds the code and the runtime.
- Write-then-execute — the agent writes a file (code, config, cron, startup hook)
  that a later step or external process runs.
- Sandbox boundary — the container/VM/isolate the code runs in; check seccomp,
  capabilities, mounts, network egress, and shared kernel.
- Indirect sinks — tool arguments that reach a downstream interpreter (template,
  deserializer, DB driver) — the agent is the injector.
- Dependency/tool loading — the agent installing or importing code that then runs.
For the underlying injection/deserialization sink mechanics, cross-reference
`skills/hunt-injection` and `skills/hunt-deserialization`; this skill is the
agent-driven *delivery* of those sinks and the sandbox-escape layer on top.

## Neutralizing controls (invalidators — check, don't assume)
- Sandbox isolation: code runs in a locked-down VM/container — non-root, dropped
  caps, seccomp, read-only FS, no host mounts. Confirm the profile is applied to
  the actual runtime; bypass = a writable mount, a capability, or shared namespace.
- No shell / argv-vector exec: tools use fixed argv, never a shell string.
  Confirm; bypass = concatenated command strings.
- Egress control: the sandbox cannot reach internal networks or exfil out. Confirm
  the deny applies on the code path; bypass = open outbound.
- Allow-listed interpreters / no dynamic code: `eval`-class sinks are absent or
  gated. Confirm; bypass = any `eval`/`exec` reachable from tool input.
- Resource & write limits: FS writes are ephemeral and can't reach executed-code
  locations. Confirm write-then-execute is impossible; bypass = write into a run
  path.

## Probes
Benign, observable execution markers — never destructive, never real exfil:
- Have the agent run (via its interpreter tool) a command that echoes a unique
  token and the runtime identity, e.g. print `AGENTEXEC-5503` plus `id`/hostname
  on `app.example.test`. Token + identity = code actually executed.
- Probe the boundary read-only: attempt to list a host-only path or resolve an
  internal name `metadata.example.test`; a response = escape/egress gap (stop at
  proof, don't pivot).
- Write a file then see if a later step executes it (drop a marker, not a payload).
Keep every command inert and self-identifying; take no destructive action.

## Validation bar
`confirmed` requires OBSERVED code execution attributable to agent-chosen input —
the marker token returned from real execution plus evidence of the runtime it ran
in. A sandbox escape requires proof the code reached OUTSIDE the intended boundary
(host path, internal network, another tenant), not just that it ran inside the
sandbox. The agent *generating* code, or an interpreter that echoes input without
executing it, is NOT confirmation.

## Known chains
Agent code exec is a terminal primitive: ASI01 goal hijack or ASI07 forged message
→ attacker-chosen code via the interpreter tool → in-sandbox RCE → escape to host/
internal network → credential theft and privilege use (ASI03) → persistence as a
rogue agent (ASI10). The in-sandbox execution and the escape are SEPARATE
candidates; confirm each. Trace the delivered sink back to `hunt-injection` /
`hunt-deserialization` for root cause.
