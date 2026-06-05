---
name: hunt-cloud-misconfig
description: Cloud misconfiguration hunt playbook — public storage, over-permissive IAM, exposed services in a live cloud account.
domain: cloud
---

# hunt-cloud-misconfig

Load when assessing a live cloud account (AWS/GCP/Azure) for misconfiguration.
(For pre-deploy infra-as-code, use `hunt-iac`.)

## When to load
cloud misconfig, public bucket, S3 ACL, IAM privesc, over-permissive role,
exposed service, security group 0.0.0.0, public snapshot, metadata SSRF target.

## Where it lives
- Storage: buckets/objects with public/`AllUsers`/`AuthenticatedUsers` access.
- IAM: wildcard `Action`/`Resource`, `iam:PassRole` + privesc paths, unused-but-powerful roles.
- Network: security groups/firewalls allowing 0.0.0.0/0 to mgmt ports.
- Data: unencrypted volumes/snapshots, public AMIs/images, disabled audit logs.

## Neutralizing controls (check, don't assume)
- Org SCP / deny guardrails, public-access-block, conditions on IAM statements.
- The principal you're assessing actually has the permission (test, don't infer from policy text alone).

## Probes
Read-only enumeration with least privilege (e.g. `aws s3 ls`, IAM policy
simulator, `scoutsuite`/`prowler`-style checks). Confirm reachability from the
attacker principal, not just policy presence.

## Validation bar
`confirmed` = you actually access the resource / exercise the permission as the
attacker principal — not just "the policy looks broad." Note blast radius for severity.

## Known chains
Public bucket → secret/data exfil; `PassRole` + service → IAM privesc → account takeover.
