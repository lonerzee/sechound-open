---
name: hunt-http-smuggling
description: HTTP request smuggling / desync hunt playbook — CL.TE / TE.CL / H2 desync across a front-end/back-end pair.
domain: web
---

# hunt-http-smuggling

Load when traffic passes through a chain (CDN/proxy/LB → origin) that may parse
request boundaries differently.

## When to load
request smuggling, HTTP desync, CL.TE, TE.CL, TE.TE, H2.CL, H2.TE, cache
poisoning via smuggling, front-end/back-end disagreement.

## Where it lives
Any multi-hop HTTP path: CDN/WAF/reverse-proxy/load-balancer in front of an
origin, especially HTTP/1.1 downgrade or HTTP/2 → HTTP/1.1 rewriting.

## Neutralizing controls (check, don't assume)
- Front-end and back-end agree on length semantics; ambiguous `Content-Length` +
  `Transfer-Encoding` rejected (not silently picked).
- HTTP/2 end-to-end (no downgrade); strict header validation at the edge.

## Probes
Time-based differential probes (a crafted request that stalls only if smuggled);
`smuggler.py`/Burp's HTTP Request Smuggler. CL.TE / TE.CL / H2.CL / H2.TE
variants. Use benign, reversible probes — smuggling can affect other users, so
test carefully and within scope.

## Validation bar
`confirmed` = a reproducible desync: your smuggled prefix affects a *subsequent*
request/response (capture another response, or a controlled cache poison). One
timing blip isn't proof — show the boundary confusion deterministically.

## Known chains
Desync → request hijack / credential capture, cache poisoning, WAF/auth bypass.
