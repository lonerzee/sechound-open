---
name: hunt-ssrf
description: SSRF hunt playbook — outbound-HTTP sinks, egress allow-list bypass, metadata-endpoint reach. A worked example of the hunt-skill format.
---

# hunt-ssrf

Load when testing URL-fetch sinks, webhook validators, attachment downloads, or
any outbound HTTP. Keep target-specific sink locations in your private knowledge;
this skill is the method.

## When to load
SSRF, server-side request, outbound HTTP, webhook URL, URL fetch, metadata,
IMDS, link preview, PDF/screenshot render, avatar/logo import.

## Where this class lives
Enumerate code that takes a URL (or host/port) from a request and fetches it:
- webhook registration / "test webhook" endpoints,
- import-from-URL features (logo, avatar, document, feed),
- link unfurl / preview / oEmbed,
- server-side render (HTML→PDF, screenshot),
- any HTTP client call whose URL traces back to user input.

Grep the outbound HTTP client(s) your stack uses and trace each call site's URL
argument back to its source.

## Neutralizing controls (invalidators — check, don't assume)
- **Egress allow-list / proxy** — outbound traffic restricted to known hosts.
  Confirm it's enforced on *this* call path, not just configured somewhere.
- **URL validator** — scheme allow-list (https only), DNS-resolves-to-public
  check, blocks `169.254.169.254` / link-local / RFC1918. Check for
  TOCTOU (validate then re-resolve) and parser-confusion bypasses.
- **No-redirect-follow** — does the client follow 30x to an internal host?

## Probes
- Point the URL at a collaborator/OOB host you control → confirm callback.
- Internal targets: cloud metadata (`169.254.169.254`), `localhost`, RFC1918,
  link-local; alternate encodings (decimal/octal IP, `[::]`, trailing dot,
  `@`-userinfo, redirect chains).

## Validation bar
`confirmed` = an out-of-band callback you control fires, OR the response
contains data only reachable from the server's network position (e.g. a
metadata/credentials response) that the attacker could not otherwise obtain.

## Known chains
SSRF → cloud metadata → temporary credentials → cloud API access. SSRF → reach
an internal admin/management endpoint. Each downstream step is its own
code-only candidate until proven.
