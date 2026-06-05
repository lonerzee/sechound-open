# Agents

Specialized sub-agents the orchestrator dispatches in parallel. Each agent owns
one slice of the hunt (a vuln class, a service, a phase) and returns structured
candidate stubs — it does **not** confirm findings on its own.

## The contract

Every sub-agent must:

1. **Stay in scope.** Operate only against hosts in `config/targets.yaml`.
2. **Return code-only candidates**, never `confirmed`. Confirmation is the
   verifier's job, with live evidence.
3. **Cite location.** Every candidate carries `file:line` (and an endpoint when
   applicable) plus a one-line reachability argument.
4. **Include invalidators.** List the controls that would make the candidate a
   false positive, so the verifier knows what to check.
5. **Emit to the registry schema.** Output conforms to `findings/schema.json`
   so the merge step can de-duplicate by root cause.

## Shipped agents

Each is a markdown system prompt with YAML frontmatter (`name`, `domain`,
`tools`). `orchestrate.py` dispatches them as lanes via `agent_file:` — it
strips the frontmatter and honors the declared `tools`. Add your own by dropping
a `.md` here.

| Agent | Slice |
|---|---|
| `recon` | map + rank the in-scope attack surface (seeds hunting) |
| `web-hunter` | web/API classes (injection, XSS, IDOR, auth, SSRF, upload, GraphQL, logic) |
| `code-auditor` | static source→sink; confirm/refute semgrep/CodeQL hits |
| `cloud-auditor` | live cloud + IaC misconfig (Trivy/checkov/prowler) |
| `deps-auditor` | dependency CVEs triaged by reachability (osv/grype/trivy) |
| `secrets-hunter` | hardcoded secrets in code/artifacts/history (gitleaks/trufflehog) |
| `binary-analyst` | native memory-safety (static trace + fuzzing triage) |
| `triage-agent` | true/false-positive triage of candidate piles |
| `validator` | live reproduction → confirmed/demoted (holds the mutation mutex) |
| `chain-builder` | correlate confirmed findings into attack chains |
| `reporter` | render confirmed findings into a report (redacts first) |

## Running a multi-agent swarm

Fan several out at once with `orchestrate.py` and a task file (read-only lanes
run in parallel; `validator` serializes behind the mutation mutex). See
`tasks/swarm.yaml`:

```bash
python3 tools/orchestrate.py engagements/<id> tasks/swarm.yaml
```

## Merge step

After a parallel fan-out, the orchestrator merges every agent's stubs into the
single registry, de-duplicating by root cause (not by symptom — the same bug
found three ways is one record). Conflicts in severity/status are resolved by
the verifier and critic, not at merge time.
