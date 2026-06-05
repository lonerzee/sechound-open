# False-positive checklist (core)

Apply mechanically before filing a finding **and** before accepting any
retraction. Each pattern is a class of mistake that produces either a false
positive (filing a non-bug) or a false retraction (dropping a real bug). Both
are failures.

These principles are **domain-neutral** — they hold whether you're auditing a
web API, a binary, cloud config, dependencies, or secrets. Domain-specific FP
patterns (e.g. the exact controls that neutralize an injection in *your* stack)
live in a profile under `profiles/<domain>/FP_CHECKLIST.md`.

## The patterns

1. **Reachability.** A dangerous sink/condition is only a finding if it is
   actually reachable and triggerable from the attacker's position. Trace the
   path from attacker-controlled input (or attacker capability) to the effect.
   No reachable path → not a finding (yet).

2. **The control is actually on *this* path.** A mitigation that exists
   *somewhere* doesn't help if it isn't applied to the path in question.
   Confirm the control runs on this code path / request / resource — don't
   assume a global default covers the specific case.

3. **The cited control/location actually exists.** Before accepting a
   retraction that leans on "X handles this," **grep for X.** Scanners and
   AI-written reports routinely cite plausible files, rules, or controls that
   don't exist. If the cited file/symbol/line is absent, the claim is invalid.

4. **A platform/framework default may already neutralize it.** Many runtimes
   escape, parameterize, sandbox, or scope by default. Confirm the default is
   in effect on this path before claiming the bug.

5. **Effective configuration wins.** A risky setting in one place may be
   overridden elsewhere. Resolve the *effective* config/state, not the first
   value you find.

6. **Sink-context handling.** A value that looks dangerous may be encoded,
   escaped, sanitized, parameterized, or bounds-checked for the specific sink it
   reaches. Check what the sink actually does with it.

7. **Every chain component is proven.** In a multi-step finding, each step must
   independently hold (at least as a code-level candidate with its own
   analysis). A chain built on an assumed step is an assumed finding.

8. **Environment parity.** A repro on a dev/test/sample environment may not
   generalize: seeded data, disabled controls, a feature flag, missing rate
   limits, or internal-only reachability can make it not fire in production.
   State what would have to hold for it to generalize.

9. **One observation isn't proof.** A single run can mislead. Prove the claim
   with the *right* comparison for the class: an authorization/isolation claim
   needs the negative case (a principal that should be denied); a race needs
   repeated trials; a timing/heuristic needs a baseline.

10. **De-duplicate by root cause.** The same root cause found three ways (three
    scanners, three endpoints) is **one** finding. Don't inflate counts by
    symptom.

11. **Severity reflects demonstrated impact.** Rate by what you actually showed,
    not the category's worst-case default. "SQLi class" ≠ CRITICAL if you only
    demonstrated an error-based boolean on a non-sensitive table.

## How to use it

- **Before filing:** run 1–7 to sharpen the candidate. They don't block filing
  a genuine candidate — file code-level candidates cheaply.
- **Before confirming:** 1, 3, 8, 9 are promotion gates.
- **Before accepting a retraction:** 3 is mandatory — verify the mitigation is
  real.
- **When triaging scanner output:** 1, 6, 10, 11 catch most scanner false
  positives and inflation.
