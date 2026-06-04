#!/usr/bin/env python3
"""
init_engagement.py — scaffold a new engagement directory.

Creates engagements/<id>/ with the layout the pipeline tools expect.

Usage:
    python3 tools/init_engagement.py <id> [--target NAME] [--scope HOST ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sechound_lib import repo_root, utcnow


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("id", help="engagement id, e.g. 2026-01-01_initial")
    ap.add_argument("--target", default="", help="target name (from config/targets.yaml)")
    ap.add_argument("--scope", nargs="*", default=[], help="in-scope hosts")
    args = ap.parse_args()

    eng = repo_root() / "engagements" / args.id
    if eng.exists():
        sys.exit(f"engagement already exists: {eng}")

    for sub in ("findings", "attempts", "reports", "knowledge", "logs", "auth"):
        (eng / sub).mkdir(parents=True, exist_ok=True)

    (eng / "engagement.json").write_text(json.dumps({
        "id": args.id, "created_at": utcnow(),
        "target": args.target, "scope": args.scope,
        "authorization": "REQUIRED: record written authorization / RoE before testing",
    }, indent=2))
    (eng / "progress.json").write_text(json.dumps({"objectives": [], "completed": []}, indent=2))
    (eng / "methodology_tree.json").write_text(json.dumps({}, indent=2))
    (eng / ".gitignore").write_text("auth/\n*.cookies\n")  # never commit creds

    print(f"[init] engagement scaffolded at {eng}")
    print(f"[init] put cookie jars in {eng}/auth/ (gitignored), findings land in {eng}/findings/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
