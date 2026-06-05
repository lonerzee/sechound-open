---
name: hunt-deps
description: Dependency / supply-chain hunt playbook — known-vulnerable packages, reachability triage, typosquat / dependency confusion.
domain: deps
---

# hunt-deps

Load when assessing third-party dependencies for known vulnerabilities and
supply-chain risk. Pairs well with SARIF import from `osv-scanner`/`grype`/`trivy`
(`tools/import_sarif.py`) — then triage reachability here.

## When to load
vulnerable dependency, CVE, SCA, SBOM, outdated package, typosquat, dependency
confusion, transitive CVE.

## Where it lives
Lockfiles/manifests (`package-lock.json`, `poetry.lock`, `go.sum`, `pom.xml`),
vendored deps, container base images.

## The real work: reachability triage
A CVE in the dependency graph is not automatically exploitable. For each:
- Is the vulnerable **function/path actually called** by the app? (reachability)
- Is the attacker able to reach that call with the triggering input?
- Is it transitive and pulled into the runtime artifact, or dev-only?

## Neutralizing controls / FP guards (check, don't assume)
- Version constraint already patched in the *resolved* (locked) version.
- Vulnerable code path not imported / behind a disabled feature.
- Mitigated by config (e.g. the risky option is off).

## Validation bar
`confirmed` = the vulnerable code is reachable AND triggerable in this app's
usage (ideally a working trigger). Otherwise: `dependency-vulnerable; exploitability TBD`.

## Known chains
Reachable RCE-class CVE → code execution; build-time dep → supply-chain compromise.
