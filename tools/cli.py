#!/usr/bin/env python3
"""
cli.py — the `sechound` umbrella command.

Dispatches to the individual tools so you can run `sechound <subcommand> ...`
instead of `python3 tools/<x>.py ...`. Works straight from a clone (via the
`./sechound` shim) or after `pip install -e .`.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# subcommand -> module providing main()
SUBCOMMANDS = {
    "init": "init_engagement",
    "ingest": "ingest",
    "import": "import_sarif",
    "triage": "triage",
    "verify": "verify_finding",
    "tenant-diff": "tenant_diff",
    "mcp-probe": "mcp_probe",
    "rag-probe": "rag_probe",
    "dast": "dast",
    "run": "run",
    "orchestrate": "orchestrate",
    "ultrareview": "ultrareview",
    "critic": "critic",
    "compound": "compounder",
    "grounding-gate": "grounding_gate",
    "report": "report",
    "benchmark": "benchmark",
    "skill-miner": "skill_miner",
    "skill-lint": "skill_lint",
    "doctor": "doctor",
}

HELP = {
    "init": "scaffold a new engagement directory",
    "ingest": "add a finding to the registry (--json / --file / stdin)",
    "import": "import scanner output (SARIF: semgrep/codeql/nuclei/trivy/...) into the registry",
    "triage": "LLM-triage candidate findings (true/false positive, needs-verification)",
    "verify": "reproduce candidates live; promote or demote",
    "tenant-diff": "two-identity diff for cross-tenant / IDOR / BOLA claims",
    "mcp-probe": "MCP falsifier: workspace-IDOR / rug-pull / result-injection (HTTP + stdio)",
    "rag-probe": "RAG/embedding/memory poisoning falsifier: cross-context + persistence",
    "dast": "run nuclei-style DAST templates against a target",
    "run": "run the plan->execute->verify->critic->compound loop",
    "orchestrate": "fan a hunt out to parallel agent lanes from a task file",
    "ultrareview": "final two-lane adversarial review of findings",
    "critic": "adversarial critic pass over verification results",
    "compound": "fold confirmed findings back into knowledge",
    "grounding-gate": "anti-hallucination gate: confirmed findings must be evidence-backed",
    "report": "list findings / export markdown or SARIF",
    "benchmark": "score the falsifiers against bundled labs, with condition tracking",
    "skill-miner": "mine disclosed reports into cited hunt skills",
    "skill-lint": "lint hunt skills for structure + backing validators",
    "doctor": "preflight check: backend, deps, tools, config readiness",
}


def _usage() -> None:
    print("usage: sechound <command> [args]\n\ncommands:")
    width = max(len(c) for c in SUBCOMMANDS)
    for cmd in SUBCOMMANDS:
        print(f"  {cmd:<{width}}  {HELP.get(cmd, '')}")
    print("\nLLM backend: set $SECHOUND_LLM (claude | command | anthropic | openai). "
          "See docs/PROVIDERS.md.")


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        _usage()
        return 0
    sub = sys.argv[1]
    if sub not in SUBCOMMANDS:
        print(f"unknown command: {sub}\n")
        _usage()
        return 2
    mod = importlib.import_module(SUBCOMMANDS[sub])
    # Hand the rest of argv to the tool's own argparse.
    sys.argv = [f"sechound {sub}"] + sys.argv[2:]
    return int(mod.main() or 0)


if __name__ == "__main__":
    sys.exit(main())
