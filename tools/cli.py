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
    "dast": "dast",
    "run": "run",
    "orchestrate": "orchestrate",
    "ultrareview": "ultrareview",
    "critic": "critic",
    "compound": "compounder",
    "report": "report",
    "doctor": "doctor",
}

HELP = {
    "init": "scaffold a new engagement directory",
    "ingest": "add a finding to the registry (--json / --file / stdin)",
    "import": "import scanner output (SARIF: semgrep/codeql/nuclei/trivy/...) into the registry",
    "triage": "LLM-triage candidate findings (true/false positive, needs-verification)",
    "verify": "reproduce candidates live; promote or demote",
    "tenant-diff": "two-identity diff for cross-tenant / IDOR / BOLA claims",
    "dast": "run nuclei-style DAST templates against a target",
    "run": "run the plan->execute->verify->critic->compound loop",
    "orchestrate": "fan a hunt out to parallel agent lanes from a task file",
    "ultrareview": "final two-lane adversarial review of findings",
    "critic": "adversarial critic pass over verification results",
    "compound": "fold confirmed findings back into knowledge",
    "report": "list findings / export markdown or SARIF",
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
