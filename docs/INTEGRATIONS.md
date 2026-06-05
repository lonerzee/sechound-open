# Integrations

SecHound is a **triage & verification layer**, not a scanner. It's designed to
sit on top of the tools you already run: bring your scanner output in, get
ranked, de-duplicated, false-positive-filtered, verified findings out. It does
not reimplement nmap, semgrep, or nuclei — it orchestrates around them.

## The pattern

```
your tools (find)              SecHound (make it trustworthy)
─────────────────              ──────────────────────────────
recon  →  scan/SAST/SCA  →  SARIF/JSON  →  import → triage → verify → critic → dedup → report/SARIF
```

## Bring scanner output in (SARIF)

SARIF is the common format. These all emit it, and `tools/import_sarif.py`
normalizes any of them into the registry (de-duping by root cause on the way in):

| Tool | Kind | Emit SARIF |
|---|---|---|
| **semgrep** | SAST | `semgrep --sarif -o out.sarif` |
| **CodeQL** | SAST | `codeql database analyze --format=sarif-latest` |
| **nuclei** | DAST | `nuclei -u <t> -se out.sarif` |
| **Trivy** | container/IaC/SCA | `trivy fs --format sarif -o out.sarif .` |
| **grype / osv-scanner** | SCA | both support SARIF output |
| **gitleaks / trufflehog** | secrets | `gitleaks detect --report-format sarif` |
| **checkov / tfsec** | IaC | `checkov -o sarif` |

```bash
python3 tools/import_sarif.py semgrep.sarif trivy.sarif --domain web
python3 tools/triage.py            # LLM sorts true/false positive, ranks
python3 tools/report.py --status candidate --format md
```

That's the day-one value: pipe a noisy 4,000-hit scan in, get a ranked,
de-duplicated, triaged shortlist out — then verify the real ones.

## Recon toolchain (SCOPE / RECON phase)

SecHound orchestrates around the standard open-source recon stack rather than
shipping its own (see the `recon` skill + `agents/recon.md`):

- **ProjectDiscovery**: `subfinder`, `dnsx`, `httpx`, `katana`, `nuclei`
- **Content/params**: `ffuf`, `feroxbuster` + SecLists
- **Source**: `gitleaks`/`trufflehog`, `semgrep`/CodeQL

Run them yourself (or via the `recon` agent), feed live targets to the planner
and scanner output to `import_sarif.py`.

## Out (export)

- **SARIF** — `tools/report.py --format sarif` → GitHub code scanning / any SARIF viewer.
- **Markdown** — `tools/report.py --format md` → a human report (run it through the `reporter` agent for audience-shaping).

## LLM backends

Model-agnostic via `$SECHOUND_LLM` (Claude CLI / local via Ollama / Anthropic /
OpenAI-compatible / Gemini). See [`PROVIDERS.md`](PROVIDERS.md).

## Related projects

SecHound is a Claude-skill-style framework in the same family as bundles like
Claude-BugHunter (web/bug-bounty skills) and pentest-agent collections — its
distinguishing bet is the **domain-neutral triage/verification layer over
existing scanners**, plus a model-agnostic core.
