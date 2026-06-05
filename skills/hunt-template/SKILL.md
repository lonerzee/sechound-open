---
name: hunt-template
description: Template for a vuln-class hunt playbook. Copy this directory to skills/hunt-<class>/ and fill in. A hunt skill encodes WHERE a class lives in your target, the controls that neutralize it, and the bar for validation.
domain: template
---

# hunt-<class> (template)

> Copy `skills/hunt-template/` to `skills/hunt-<class>/`, rename, and fill in.
> Keep target-specific details (exact class names, hosts) in your private
> config — a published hunt skill should describe the *method*, not your scope.

## When to load

List the keywords/triggers that should pull this skill in (e.g. for an SSRF
hunt: "SSRF", "outbound HTTP", "webhook URL", "URL fetch", "metadata IP").

## Where this class lives

For each component of your target, note where this vuln class tends to surface
(the sink families) and how to enumerate them. Keep this generic in the
published version; the concrete file paths live in your private knowledge.

## Neutralizing controls (invalidators)

The controls that make an instance of this class a false positive. For each:
- what it does,
- how to confirm it's actually on the path (grep target — don't assume),
- what a bypass would look like.

## Payloads / probes

Ready-to-adapt probes for this class. Keep them benign and parameterized; never
hardcode a real target.

## Validation bar

What `confirmed` requires for this class. Be specific (e.g. for cross-tenant: a
two-identity diff; for SSRF: an out-of-band callback or an internal response
that an unauthenticated/cross-tenant caller should not see).

## Known chains

How a confirmed instance of this class typically escalates — what it chains
into. Each chain step is a code-only candidate until proven.
