#!/usr/bin/env python3
"""
doctor.py — preflight check. Is SecHound ready to run, and with what?

    python3 tools/doctor.py      (or: sechound doctor)

Reports the active LLM backend + whether it's usable, optional deps, external
tools, and config/content presence. Exit 0 if an LLM backend is usable, else 1.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sechound_lib import repo_root, skill_index
import llm


def _ok(b: bool) -> str:
    return "OK  " if b else "MISS"


def main() -> int:
    root = repo_root()
    print("SecHound doctor\n" + "=" * 40)

    # Python
    v = sys.version_info
    py_ok = (v.major, v.minor) >= (3, 10)
    print(f"[{_ok(py_ok)}] Python {v.major}.{v.minor} (need >= 3.10)")

    # LLM backend
    prov = llm.provider()
    usable, reason = llm.available()
    print(f"[{_ok(usable)}] LLM backend: SECHOUND_LLM={prov} "
          f"(model={llm.default_model()}, agentic={llm.is_agentic()})"
          + ("" if usable else f"  -> {reason}"))

    # Optional Python deps
    for mod, why in [("yaml", "YAML task/profile files"),
                     ("anthropic", "SECHOUND_LLM=anthropic"),
                     ("openai", "SECHOUND_LLM=openai"),
                     ("google.generativeai", "SECHOUND_LLM=gemini")]:
        try:
            __import__(mod)
            present = True
        except Exception:
            present = False
        print(f"[{_ok(present)}] python: {mod}  ({why})")

    # External tools (optional — used by recon/validators/scanners)
    for tool in ["claude", "curl", "git", "semgrep", "nuclei", "trivy", "gitleaks"]:
        print(f"[{_ok(bool(shutil.which(tool)))}] tool: {tool}")

    # Config + content
    targets = (root / "config" / "targets.yaml").exists()
    print(f"[{_ok(targets)}] config/targets.yaml "
          + ("present" if targets else "missing (cp config/targets.example.yaml config/targets.yaml)"))
    print(f"[OK  ] skills: {len(skill_index())} | profiles: "
          f"{len([p for p in (root / 'profiles').glob('*/profile.yaml')])} | "
          f"agents: {len(list((root / 'agents').glob('*.md'))) - 1}")  # minus README

    print("=" * 40)
    if usable:
        print("Ready. Try:  sechound import <scan.sarif> && sechound triage")
        return 0
    print(f"Not ready: no usable LLM backend ({reason}). See docs/PROVIDERS.md.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
