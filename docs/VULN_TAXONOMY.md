# Vulnerability taxonomy

SecHound is **not** limited to web/API bugs. The pipeline (find → verify →
critic → dedup) and the registry are domain-neutral; the classes below are what
the shipped profiles and hunt skills cover, and you can add your own. Each class
maps to a `category` on findings and (where useful) a CWE.

Skills live in `skills/hunt-<class>/`; domain bundles live in `profiles/<domain>/`.

## Web / API  (profile: `web-appsec`)
| Class | CWE | Skill |
|---|---|---|
| SQL / NoSQL injection | CWE-89/943 | `hunt-injection` |
| Command injection | CWE-78 | `hunt-injection` |
| Template / expression injection (SSTI) | CWE-1336/94 | `hunt-injection` |
| Cross-site scripting (XSS) | CWE-79 | `hunt-xss` |
| IDOR / BOLA / broken object auth (API1) | CWE-639/284 | `hunt-idor` |
| Mass assignment / BOPLA / excessive data exposure (API3) | CWE-915/213 | `hunt-mass-assignment` |
| Broken function-level authz / BFLA (API5) | CWE-285/862 | `hunt-function-authz` |
| Broken auth / session / JWT | CWE-287/384 | `hunt-auth` |
| SSRF | CWE-918 | `hunt-ssrf` |
| Path traversal / LFI | CWE-22/98 | `hunt-path-traversal` |
| Insecure deserialization | CWE-502 | `hunt-deserialization` |
| XXE | CWE-611 | `hunt-injection` |
| CSRF / request forgery | CWE-352 | `hunt-auth` |
| Open redirect | CWE-601 | `hunt-misc` |
| Race conditions / TOCTOU | CWE-362 | `hunt-race` |

## Secrets  (profile: `secrets`)
| Class | CWE | Skill |
|---|---|---|
| Hardcoded credential / key / token | CWE-798 | `hunt-secrets` |
| Secret in VCS history / artifact | CWE-540 | `hunt-secrets` |
| Weak / missing cryptography | CWE-326/327 | `hunt-crypto` |

## Cloud / IaC  (profile: `cloud-iac`)
| Class | Skill |
|---|---|
| Public storage / overbroad bucket/object ACL | `hunt-cloud-misconfig` |
| Over-permissive IAM (wildcards, privesc paths) | `hunt-cloud-misconfig` |
| Exposed management ports / 0.0.0.0 ingress | `hunt-iac` |
| Unencrypted data store / disabled logging | `hunt-iac` |
| Hardcoded secret in Terraform/CloudFormation | `hunt-iac` + `hunt-secrets` |

## Dependencies / supply chain  (profile: `deps`)
| Class | CWE | Skill |
|---|---|---|
| Known-vulnerable dependency (CVE) | — | `hunt-deps` |
| Reachable vs. non-reachable CVE triage | — | `hunt-deps` |
| Typosquat / dependency confusion | CWE-427 | `hunt-deps` |

## Binary / native  (profile: `binary`)
| Class | CWE | Skill |
|---|---|---|
| Buffer/heap overflow | CWE-120/122 | `hunt-memory-safety` |
| Use-after-free / double-free | CWE-416/415 | `hunt-memory-safety` |
| Integer overflow → bounds error | CWE-190 | `hunt-memory-safety` |
| Format string | CWE-134 | `hunt-memory-safety` |

## LLM / AI  (profile: `llm`) — OWASP Top 10 for LLM Apps (2025)
| OWASP | Class | Skill |
|---|---|---|
| LLM01 | Direct / indirect prompt injection | `hunt-prompt-injection` |
| LLM02 | Sensitive information disclosure | `hunt-system-prompt-leak` |
| LLM03 | Supply chain (model / adapter / plugin) | `hunt-ai-supply-chain` |
| LLM04 | Data & model poisoning | `hunt-rag-poisoning` |
| LLM05 | Improper output handling (output→sink) | `hunt-insecure-output` |
| LLM06 | Excessive agency (tool / function abuse) | `hunt-excessive-agency` |
| LLM07 | System-prompt leakage | `hunt-system-prompt-leak` |
| LLM08 | Vector & embedding weaknesses (RAG) | `hunt-rag-poisoning` |
| LLM09 | Misinformation / overreliance | `hunt-insecure-output` |
| LLM10 | Unbounded consumption (denial-of-wallet) | `hunt-unbounded-consumption` |

## Agentic  (profile: `agentic`) — OWASP Top 10 for Agentic Applications (ASI, 2026)
| OWASP | Class | Skill |
|---|---|---|
| ASI01 | Agent goal hijack | `hunt-agent-goal-hijack` |
| ASI02 | Tool misuse & exploitation | `hunt-excessive-agency` |
| ASI03 | Identity & privilege abuse | `hunt-agent-identity-privilege` |
| ASI04 | Agentic supply chain | `hunt-ai-supply-chain` |
| ASI05 | Unexpected code execution (sandbox escape) | `hunt-agent-code-exec` |
| ASI06 | Memory & context poisoning | `hunt-rag-poisoning` |
| ASI07 | Insecure inter-agent communication | `hunt-inter-agent-comms` |
| ASI08 | Cascading failures | `hunt-cascading-failures` |
| ASI09 | Human-agent trust exploitation | `hunt-human-agent-trust` |
| ASI10 | Rogue agents | `hunt-rogue-agents` |

## MCP  (profile: `mcp`) — Model Context Protocol attack surface
| Class | Skill |
|---|---|
| Tool poisoning / rug-pull redefinition | `hunt-mcp` |
| Server scope / workspace IDOR | `hunt-mcp` |
| Confused-deputy tool chaining | `hunt-mcp` |
| Credential / token passthrough abuse | `hunt-mcp` |
| Prompt injection via tool results | `hunt-mcp` + `hunt-prompt-injection` |

## Adding a class
Drop a `skills/hunt-<class>/SKILL.md` (copy `skills/hunt-template/`), give it a
`domain:` in frontmatter, and list it in the relevant `profiles/<domain>/profile.yaml`.
Nothing in the core needs to change — `category` is free-form.
