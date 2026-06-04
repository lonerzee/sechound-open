#!/usr/bin/env python3
"""
ingest.py — add a finding to the registry (root-cause de-duplicated).

Usage:
    python3 tools/ingest.py --json '{"title":"...","severity":"HIGH","service":"api","summary":"..."}'
    python3 tools/ingest.py --file finding.json
    cat finding.json | python3 tools/ingest.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import findings_db


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="finding as a JSON string")
    ap.add_argument("--file", help="path to a JSON file (one finding or an array)")
    args = ap.parse_args()

    if args.json:
        raw = args.json
    elif args.file:
        raw = Path(args.file).read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()

    if not raw.strip():
        sys.exit("no finding provided (pass --json, --file, or pipe JSON on stdin)")

    data = json.loads(raw)
    findings = data if isinstance(data, list) else [data]

    for f in findings:
        if not f.get("title"):
            print(f"[ingest] skip — finding has no title: {f}", file=sys.stderr)
            continue
        fid, action = findings_db.upsert(f)
        print(f"[ingest] {action}: {fid}  ({f.get('severity','?')} / {f.get('service','?')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
