# Profiles

A **profile** is a domain pack. The SecHound core (pipeline, registry, model
seam, generic FP checklist) is domain-neutral; a profile layers on the
domain-specific knowledge:

- **FP patterns** — the controls that neutralize this domain's bugs, and the
  retraction traps specific to it (`FP_CHECKLIST.md`).
- **Invariants** — domain properties to falsify (`invariants.yaml`).
- **Skills** — which `skills/hunt-*` apply.
- **Validators** — the right "proof" tool for the domain's classes.

Set the active profile per engagement (in `config/targets.yaml` or a tool flag);
the planner/hunters/critic load its FP patterns and invariants on top of the
core. A target can use more than one.

## Shipped profiles

| Profile | Domain | What it adds |
|---|---|---|
| `web-appsec` | web / API | the multi-tenant + injection + authz patterns, two-identity diff validator |
| `secrets` | secrets / crypto | entropy/fixture FP discipline, key-format detection |
| `cloud-iac` | cloud / IaC | effective-config resolution, permission-actually-held checks |
| `deps` | dependencies | reachability triage over raw CVE lists |
| `binary` | native | reachable+triggerable bar, sanitizer/fuzz triage |
| `llm` | AI / LLM apps | privilege-separation + tool-abuse focus |

## profile.yaml

```yaml
name: web-appsec
domain: [web, api]
description: Multi-tenant web/API application security.
skills: [hunt-injection, hunt-xss, hunt-idor, hunt-auth, hunt-ssrf, ...]
fp_checklist: FP_CHECKLIST.md      # added on top of docs/FP_CHECKLIST.md
invariants: invariants.yaml
validators: [tenant_diff]          # tools/<name>.py
```

## Writing your own

Make `profiles/<domain>/` with a `profile.yaml`, an `FP_CHECKLIST.md` of the
domain's neutralizing controls + retraction traps, and an `invariants.yaml`.
List the `skills/hunt-*` that apply (add new skills if needed). Nothing in the
core changes — `category`/`domain` on findings are free-form.
