#!/usr/bin/env python3
"""
benchmark.py — a detection benchmark with CONDITION TRACKING.

The 2026 survey lesson every agent-pentest result ignores: a score is
meaningless without the conditions it was measured under (white/grey/black box,
hints provided or blind). This runs the real probes against the bundled labs,
scores detection per class, and records the conditions alongside the score, so
regressions are measurable and comparisons are honest.

A case passes when its `expect` string appears in the probe's output. positive
cases are planted bugs that must be detected; negative cases are safe routes
that must NOT be flagged (false-positive control).

    python3 tools/benchmark.py --autostart            # start labs, run, score
    python3 tools/benchmark.py --target http://... --mcp http://.../mcp
    python3 tools/benchmark.py --autostart --min-rate 1.0   # non-zero if below
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sechound_lib import repo_root

try:
    import yaml
except ImportError:
    yaml = None


def run_case(case: dict, target: str, mcp: str, timeout: int = 30) -> dict:
    # explicit replace (not str.format) — cmds contain literal {...} JSON args.
    # {py} binds probes to the interpreter running the benchmark (same deps).
    cmd = (case["cmd"].replace("{py}", sys.executable)
           .replace("{target}", target.rstrip("/")).replace("{mcp}", mcp))
    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=timeout, cwd=repo_root())
        out = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        out = "<timeout>"
    detected = case["expect"] in out
    kind = case.get("kind", "positive")
    # positive: pass == detected. negative: pass == expected-safe-signal present.
    passed = detected
    return {"id": case["id"], "class": case["class"], "box": case.get("box"),
            "kind": kind, "expect": case["expect"], "passed": passed}


def score(results: list[dict]) -> dict:
    per_class: dict[str, dict] = defaultdict(lambda: {"passed": 0, "total": 0})
    tp = fp = fn = tn = 0
    for r in results:
        pc = per_class[r["class"]]
        pc["total"] += 1
        pc["passed"] += int(r["passed"])
        if r["kind"] == "positive":
            tp += int(r["passed"]); fn += int(not r["passed"])
        else:
            tn += int(r["passed"]); fp += int(not r["passed"])
    total = len(results)
    passed = sum(r["passed"] for r in results)
    return {
        "detection_rate": round(passed / total, 4) if total else 0.0,
        "passed": passed, "total": total,
        "true_positives": tp, "false_negatives": fn,
        "true_negatives": tn, "false_positives": fp,
        "per_class": {k: v for k, v in per_class.items()},
    }


def _wait(url: str, tries: int = 40) -> bool:
    for _ in range(tries):
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except urllib.error.HTTPError:          # noqa: F821 — reachable, just an error code
            return True
        except Exception:
            time.sleep(0.2)
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="detection benchmark with condition tracking")
    ap.add_argument("--suite", default=str(repo_root() / "bench" / "suite.yaml"))
    ap.add_argument("--target", help="running web lab base URL")
    ap.add_argument("--mcp", help="running MCP lab URL")
    ap.add_argument("--autostart", action="store_true", help="start the bundled labs")
    ap.add_argument("--min-rate", type=float, help="exit non-zero if detection_rate below this")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if yaml is None:
        sys.exit("PyYAML required: pip install pyyaml")
    suite = yaml.safe_load(Path(args.suite).read_text())
    procs = []
    target, mcp = args.target, args.mcp

    if args.autostart:
        ex = repo_root() / "examples"
        procs.append(subprocess.Popen([sys.executable, str(ex / "vulnerable_target.py")],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        procs.append(subprocess.Popen([sys.executable, str(ex / "vulnerable_mcp.py")],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        target = target or "http://127.0.0.1:8731"
        mcp = mcp or "http://127.0.0.1:8732/mcp"
        _wait(target + "/api/objects/1")
        _wait(mcp)
    if not target or not mcp:
        sys.exit("supply --target and --mcp, or --autostart")

    try:
        results = [run_case(c, target, mcp) for c in suite.get("cases", [])]
    finally:
        for p in procs:
            p.terminate()

    sc = score(results)
    conditions = {"hints": (suite.get("meta") or {}).get("hints", "unknown"),
                  "boxes": sorted({r["box"] for r in results if r["box"]}),
                  "target": target, "mcp": mcp,
                  "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    scorecard = {"conditions": conditions, "score": sc, "cases": results}

    if args.json:
        print(json.dumps(scorecard, indent=2))
    else:
        print(f"== SecHound benchmark ==  (conditions: box={conditions['boxes']}, "
              f"hints={conditions['hints']})")
        for r in results:
            mark = "PASS" if r["passed"] else "FAIL"
            print(f"  [{mark}] {r['id']:24} {r['class']:20} ({r['kind']}, {r['box']})")
        print(f"\ndetection_rate={sc['detection_rate']}  "
              f"TP={sc['true_positives']} FN={sc['false_negatives']} "
              f"FP={sc['false_positives']} TN={sc['true_negatives']}")
        print("conditions:", json.dumps(conditions))

    if args.min_rate is not None and sc["detection_rate"] < args.min_rate:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
