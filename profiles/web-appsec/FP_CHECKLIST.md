# Web-appsec FP patterns (profile addendum)

Applied on top of the core `docs/FP_CHECKLIST.md`. These are the web/multi-tenant
specifics that caused real false positives and false retractions.

1. **Authorization enforced below the handler.** A query missing a tenant/owner
   filter in handler code is NOT a cross-tenant bug if a lower layer (ORM
   filter, DB row policy, request interceptor, gateway) injects the scope.
   **Verify that layer runs on this path** — and that it isn't a control you
   assumed exists. Don't generalize one service's interceptor to another.

2. **Cross-tenant / IDOR / BOLA needs the two-identity diff.** Confirmation
   requires the same request run as two distinct principals (owner vs. a
   different tenant) showing the attacker reads/writes the owner's data. A
   single-identity repro is NOT validation. Use `tools/tenant_diff.py`; confirm
   only on verdict `cross_tenant_leak`.

3. **Reflected value is output-encoded.** Echoed input isn't XSS if the sink
   encodes for its context (HTML body vs attribute vs JS vs URL differ). Check
   the template/serializer for the *specific* sink.

4. **Header/Origin spoofing blocked at the edge.** If a gateway strips or
   validates `X-Forwarded-*`/`Host`/identity headers, header-spoofing findings
   aren't reachable externally — verify the edge config.

5. **The endpoint isn't actually exposed.** Internal-only, unrouted, or behind
   auth you don't hold. Confirm reachability from the attacker position before
   confirming.

6. **Webhook/callback source is trusted & verified.** A "SSRF/injection via
   webhook" where the source is a signature-verified third party (and the
   signature is actually checked) is lower/again — trace who controls the input.
