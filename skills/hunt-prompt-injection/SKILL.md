---
name: hunt-prompt-injection
description: LLM/AI hunt playbook — direct & indirect prompt injection, tool/function-call abuse, data exfiltration from LLM apps.
domain: llm
---

# hunt-prompt-injection

Load when testing an application built on an LLM (chatbots, agents, RAG, tool-use).

## When to load
prompt injection, jailbreak, indirect injection, LLM, RAG poisoning, tool abuse,
function calling, system-prompt leak, agent, MCP.

## Where it lives
- Direct: user message overrides system instructions.
- Indirect: untrusted content the model ingests (web pages, docs, emails, RAG
  chunks, tool outputs) carries injected instructions.
- Tool/agent: the model can call tools (HTTP, shell, DB, email) — injection
  steers those calls (the real impact surface).

## Neutralizing controls (check, don't assume)
- Privilege separation: tools enforce their OWN authz, not "the model decided".
- Untrusted content clearly delimited/escaped; output-side guards on actions.
- Allow-listed tool args/destinations; human-in-the-loop on sensitive actions.
- Input/output classifiers (reduce, don't eliminate — test for bypass).

## Probes
Direct override ("ignore previous…"); indirect payload planted in a RAG
doc/web page the agent reads; attempt to make a tool exfiltrate data or call an
attacker destination; system-prompt/secret extraction. Encoding/obfuscation to
bypass guards.

## Validation bar
`confirmed` = injected instructions cause a real effect: an unauthorized tool
action, data exfiltration, or leakage of system prompt/secrets — not just the
model "agreeing" in text.

## Known chains
Indirect injection → tool-driven data exfil / SSRF / state change → account or
system compromise via the agent's privileges.
