# MCP FP checklist

Neutralizing controls and retraction traps for Model Context Protocol servers,
clients, and hosts. Check before filing — and before accepting a retraction.

## Controls that make an instance a false positive
- **Per-call authorization on the server** — `tools/call` and `resources/read`
  check the *caller's* grant on the specific tool/resource, not just that a
  session exists. Confirm it's enforced server-side, not client-advisory.
- **Workspace / scope binding** — a session is bound to one workspace/tenant and
  cannot name another's tools or resources. Verify with two workspaces; a filter
  on the *list* is not a check on the *call*.
- **Tool-definition integrity** — definitions are pinned/signed; a change after
  approval forces re-consent (defeats rug-pull). Bypass = silent redefinition
  honored mid-session.
- **Credential isolation** — integration tokens a tool uses are scoped to the
  intended upstream and not exposed to the model or other tools. Trace where the
  token can actually travel.
- **Result-channel discipline** — tool results are treated as untrusted data,
  not instructions; the host does not auto-execute result-borne directives.

## Retraction traps (do NOT accept these as "fixed")
- "The tool list is filtered by workspace" — listing ≠ calling. Test a direct
  `tools/call` / `resources/read` naming the other workspace's object.
- "The description looks safe" — poisoning lives in args/behavior and in results,
  not only the human-readable description.
- "Approved once" — a rug-pull redefines *after* approval; re-check the live
  definition against what was consented to.
- "The model was told to ignore tool instructions" — a prompt instruction is not
  an enforced control.
