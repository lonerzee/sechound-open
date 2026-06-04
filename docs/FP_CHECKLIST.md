# False-positive checklist

Apply mechanically before filing a finding **and** before accepting any
retraction. Each pattern represents a class of mistake that produces either a
false positive (filing a non-bug) or a false retraction (dropping a real bug).
Both are failures.

This list is target-agnostic. Maintain a *private* companion list of
target-specific controls (the exact interceptor/filter classes that neutralize
a given class in *your* codebase) — that list does not belong in this repo.

## The patterns

1. **Sink without a reachable source.** A dangerous sink is not a finding
   unless attacker-controlled input reaches it. Trace the source → sink path;
   if input is internal/constant, drop it.

2. **Framework default already mitigates.** Many frameworks escape, parameterize,
   or scope by default. Confirm the default is actually in effect on this path
   before claiming the bug.

3. **Tenant/authorization scoping happens at a lower layer.** A query missing a
   tenant filter in application code is not a cross-tenant bug if a lower layer
   (ORM interceptor, DB policy, gateway) enforces scoping. **Verify that layer
   exists on this path** — do not assume it.

4. **Validation/auth is enforced by an interceptor, not the handler.** Absence
   of a check in the handler ≠ absence of the check. Look for filters,
   middleware, decorators, and interceptors upstream.

5. **The "vulnerable" config is overridden elsewhere.** A risky setting in one
   file may be superseded by another. Resolve the effective config.

6. **Reflected value is encoded on output.** Echoed input is not XSS if the
   sink encodes for its context. Check the template/serializer.

7. **The endpoint isn't actually exposed.** Internal-only, behind auth you
   don't have, or unrouted. Confirm reachability from the attacker position.

8. **Chain component is unproven.** In a multi-step chain, every component must
   be at least a code-only candidate with its own invalidator analysis. A chain
   built on an assumed step is an assumed chain.

9. **Expression/template path discriminated wrong.** Distinguish a sink that
   evaluates attacker input from one that merely passes it as data. The same
   API can be safe or unsafe depending on which overload/context is used.

10. **Cited mitigation does not exist.** Before accepting a retraction that
    leans on a control ("this is safe because class/filter X handles it"),
    **grep for X.** AI-generated validation reports fabricate plausible-sounding
    controls that aren't in the codebase. If the cited class/file/line is
    absent, the retraction is invalid.

11. **Cross-tenant claim validated with one identity.** A cross-tenant / IDOR /
    BOLA confirmation **requires two authenticated identities** and a diff
    showing one can read the other's data. A single-identity repro is not
    validation — demote to candidate until the two-identity diff exists.

## How to use it

- **Before filing:** run patterns 1–9 against the candidate. They sharpen the
  finding; they don't block filing a genuine candidate. File code-only
  candidates cheaply.
- **Before confirming:** patterns 7, 10, 11 are promotion gates.
- **Before accepting a retraction:** pattern 10 is mandatory — verify the
  mitigation is real.
