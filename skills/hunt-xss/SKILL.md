---
name: hunt-xss
description: XSS hunt playbook — reflected, stored, and DOM cross-site scripting; sink-context aware.
domain: web
---

# hunt-xss

Load when untrusted input may reach an HTML/JS/attribute/URL sink in a page.

## When to load
XSS, cross-site scripting, reflected/stored/DOM XSS, HTML injection,
`innerHTML`, `dangerouslySetInnerHTML`, unescaped template output.

## Where it lives
- Reflected: request input echoed into a response without context-correct encoding.
- Stored: user content (comments, names, KB articles) rendered later.
- DOM: client reads `location`/`postMessage`/storage into a sink
  (`innerHTML`, `document.write`, `eval`, `setAttribute('href', ...)`).

## Neutralizing controls (check, don't assume)
- Context-correct output encoding (HTML body vs attribute vs JS vs URL — they differ).
- Framework auto-escaping actually in effect on this path (not bypassed by raw/`|safe`).
- A strict CSP that blocks inline/eval (reduces impact; not a fix on its own).
- Sanitizer (DOMPurify) applied to the *rendered* sink, not just on input.

## Probes
A context-appropriate non-alerting marker (e.g. inject an attribute breakout or
a benign tag and observe it parsed as markup, not text). Prefer a unique token
you can see un-encoded in the DOM/source.

## Validation bar
`confirmed` = your markup/script executes or is parsed as active content in the
victim context — reflection of an *encoded* value is not XSS.

## Known chains
XSS → session/token theft, CSRF-token exfil, account actions as the victim,
admin-panel takeover (stored XSS hitting an admin view).
