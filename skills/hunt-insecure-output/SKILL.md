---
name: hunt-insecure-output
description: LLM output-handling hunt playbook — OWASP LLM05 Improper Output Handling + LLM09 Misinformation/Overreliance; model output into a downstream sink.
domain: llm
---

# hunt-insecure-output

Load when LLM output flows into code, a browser, a shell, a query, or an HTTP
client without validation. Treat model output as untrusted input to the sink.
Covers OWASP LLM05 (Improper Output Handling) and LLM09 (Overreliance).

## When to load
insecure output handling, model output to sink, LLM XSS, LLM SQLi, LLM SSRF,
output-driven command exec, markdown rendering of model output, overreliance,
unvalidated decision, agent acts on model answer.

## Where this class lives
Every place the app consumes model output as more than display text:
- model text rendered in a browser without encoding (stored/reflected XSS via
  markdown/HTML the model emits),
- model output interpolated into SQL/NoSQL, a shell command, a file path, an
  eval/template, or an HTTP request URL (SSRF),
- model-produced structured output (JSON/args) deserialized or routed into an
  action without schema validation,
- model factual/decision output consumed by code as ground truth (LLM09:
  auto-approvals, routing, eligibility calls).
Enumerate each consumer of model output and ask: is the output encoded/validated
for THAT sink's context before it is used?

## Neutralizing controls (invalidators — check, don't assume)
- **Context-correct output encoding** — HTML-encode before DOM, parameterize
  before SQL, no shell string-concat. Confirm it wraps the model output on this
  path, not just user input elsewhere.
- **Strict schema validation** on structured output — reject/clamp before use.
  Bypass: a field the schema allows through unchecked.
- **Allow-listed destinations/commands** for output-driven actions. Bypass:
  canonicalization gap (encoding, alias, `..`).
- **Human review before act** for LLM09 decisions — confirm it actually gates
  the consequential step.

## Probes
Steer the model (directly, or via injected content it summarizes) to emit a
payload that is inert as text but active in the sink, against `app.example.test`:
for HTML sinks, `<img src=x onerror=...>` or a markdown link with a
`javascript:` scheme; for a URL sink, a model answer containing
`http://169.254.169.254/...` or `http://internal.example.test/`; for a query
sink, output containing `' OR '1'='1`; for a command sink, `$(id)` style
content. Then observe the sink, not the chat.

## Validation bar
`confirmed` requires the downstream sink to actually FIRE from model output:
script execution in the victim's browser (XSS), an out-of-band callback or
internal fetch (SSRF), an altered query result (SQLi), command output returned
(exec), or — for LLM09 — code taking a consequential action (approve/route/grant)
driven solely by unvalidated model output. The model emitting the payload string
in its reply is NOT confirmation; the sink effect is.

## Known chains
Model-output XSS → session/token theft → account takeover. Output SSRF →
metadata-service / internal pivot. Output command/SQL exec → RCE / data
disclosure. Overreliance on model decision → business-logic bypass
(auto-approval of an action the policy would reject).
