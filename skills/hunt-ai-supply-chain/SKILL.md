---
name: hunt-ai-supply-chain
description: AI supply-chain hunt playbook — OWASP LLM03 Supply Chain + Agentic ASI04 Agentic Supply Chain; poisoned weights/adapters, malicious plugins/tools, broken provenance.
domain: llm
---

# hunt-ai-supply-chain

Load when assessing the provenance and integrity of the models, adapters,
plugins, and tools an LLM/agent system depends on. Covers OWASP LLM03 (Supply
Chain) and Agentic ASI04 (Agentic Supply Chain).

## When to load
AI supply chain, model provenance, poisoned weights, malicious adapter, LoRA
poisoning, model integrity, plugin/tool provenance, MCP server trust, untrusted
model source, model registry, unsigned model, dependency poisoning for AI.

## Where this class lives
Every untrusted artifact pulled into the AI runtime:
- model weights / base models / fine-tunes / adapters (LoRA) fetched from a hub
  or registry without pinned digest or signature verification,
- plugins / tools / MCP servers installed from a marketplace or custom URL,
  loaded with the agent's privileges,
- the serving/inference stack and its dependencies (same classic SCA surface),
- datasets used for fine-tune/RAG that carry their own poisoning risk.
Enumerate the manifest: for each model, adapter, plugin, and MCP server, record
source, pinned version/digest, and whether integrity is verified at load. The
question: can an upstream (or a name-squat / registry compromise) substitute a
malicious artifact that the runtime loads unverified?

## Neutralizing controls (invalidators — check, don't assume)
- **Pinned digest + signature verification** on model/adapter load — the runtime
  refuses an artifact whose hash/signature doesn't match. Confirm verification
  actually runs at load, not just that a digest is recorded. Bypass: a path that
  fetches "latest" or an unpinned tag.
- **Vetted/allow-listed plugin & MCP registry** — only reviewed sources install,
  and a custom MCP URL is gated. Bypass: a custom-server install path that skips
  review, or a tool whose scope exceeds its vetting.
- **Isolation of the inference/plugin runtime** — a loaded artifact can't reach
  secrets/network beyond its need. Confirm the sandbox boundary.
- **SBOM + provenance (SLSA-style) for the serving stack** — attestation back to
  source. Confirm it covers the model artifacts, not just the Python deps.

## Probes
This class is validated largely by provenance tracing, not live payloads.
Inventory each artifact and check: is the source pinned by digest? Is the
signature verified at load? Against `app.example.test`'s model/plugin config,
test whether an unpinned/`latest` reference or an unverified custom plugin/MCP
URL is accepted. In a lab (never a real registry), stage a benign adapter with a
distinctive, inert behavioral marker and confirm whether the runtime loads it
without an integrity check — the marker surfacing proves the unverified load.

## Validation bar
`confirmed` requires an OBSERVED integrity/provenance failure with impact: the
runtime actually loaded an artifact (model, adapter, plugin, or MCP server) that
was unsigned, unpinned, or substituted — demonstrated by a distinctive marker in
behavior or output from a lab-staged benign artifact, or by the install/load
path accepting an attacker-controllable source with no verification step. A
missing-attestation finding alone is a candidate; `confirmed` needs the
unverified artifact to have actually been loaded and exercised.

## Known chains
Poisoned weights/adapter → backdoored behavior triggered by a hidden phrase →
targeted misclassification or injected action. Malicious plugin/MCP server →
tool-level RCE / data exfil with the agent's privileges (chains into
hunt-excessive-agency). Compromised dependency in the serving stack → classic
RCE / credential theft at the host.
