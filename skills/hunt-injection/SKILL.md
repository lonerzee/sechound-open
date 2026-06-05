---
name: hunt-injection
description: Injection hunt playbook — SQL/NoSQL, command, template/expression (SSTI), and XML (XXE). Untrusted input reaching an interpreter.
domain: web
---

# hunt-injection

Load when untrusted input might reach an interpreter: a database driver, a
shell, a template/expression engine, or an XML parser.

## When to load
SQLi, NoSQL injection, command injection, RCE, SSTI, template injection,
expression injection, XXE, ORM injection, LDAP injection.

## Where it lives
Trace each call into an interpreter back to its argument's source:
- DB: string-built queries, ORM `.raw()`/`exec`, dynamic `IN`/`ORDER BY`.
- Shell: `system`/`exec`/`popen`/`ProcessBuilder` with concatenated input.
- Templates: user data rendered as a template, not as data (`render_template_string`, `Velocity`, `Freemarker`, `eval`).
- XML: parsers with external entity resolution enabled.

## Neutralizing controls (check, don't assume)
- Parameterized queries / prepared statements / bound ORM params.
- Argument-vector exec (no shell) with a fixed argv.
- Auto-escaping template context; data passed as variables, not template source.
- XML parser hardened: external entities + DTDs disabled.

## Probes
Benign markers that prove interpretation vs. inertness: arithmetic in SSTI
(`{{7*7}}`→`49`), boolean/time SQL deltas, a unique echo for command exec, an
OOB entity fetch for XXE. Keep payloads non-destructive.

## Validation bar
`confirmed` = the marker is demonstrably *interpreted* (computed result, timing
delta, OOB callback) — not merely reflected. Show the source is attacker-controlled.

## Known chains
Injection → data exfiltration, auth bypass, RCE, lateral movement. Each
downstream step is its own candidate until proven.
