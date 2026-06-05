---
name: hunt-iac
description: Infrastructure-as-code hunt playbook — Terraform/CloudFormation/K8s/Helm misconfig caught before deploy.
domain: cloud
---

# hunt-iac

Load when reviewing infrastructure definitions (Terraform, CloudFormation, ARM,
Kubernetes manifests, Helm, Dockerfiles) — pre-deploy, static.

## When to load
IaC, Terraform, CloudFormation, Kubernetes, Helm, Dockerfile, misconfig as code,
tfsec/checkov-style issues.

## Where it lives & what to check
- Public exposure: `0.0.0.0/0` ingress, public IPs, public buckets in HCL/YAML.
- Encryption/logging: storage/DB without encryption-at-rest; audit/flow logs off.
- Secrets: hardcoded credentials/keys in variables/defaults (see `hunt-secrets`).
- K8s: privileged containers, `hostPath`, no resource limits, `:latest`, no securityContext.
- IAM-as-code: wildcard policies defined in the template.

## Neutralizing controls (check, don't assume)
- Values overridden by tfvars/parameters/overlays at deploy — resolve effective config.
- Module wrappers that inject the missing control; org policy enforced at apply.

## Probes
Static parse of the IaC; trace a flagged resource's *effective* setting through
variables/overrides. Confirm it isn't superseded before filing.

## Validation bar
This is static — findings are candidates by nature. `confirmed` needs the
deployed resource to actually exhibit the misconfig (then it's a `hunt-cloud-misconfig` check).

## Known chains
Insecure default shipped repeatedly → fleet-wide exposure on apply.
