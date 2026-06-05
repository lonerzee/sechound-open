#!/usr/bin/env python3
"""
triage.py — LLM triage of candidate findings (the answer to "I ran a scanner and
got 4,000 hits").

For each candidate (e.g. imported via import_sarif.py), the LLM applies the
false-positive checklist and returns a verdict: likely_true_positive |
likely_false_positive | needs_verification, with a reason. Results are written
to each finding's `triage` field and ranked. Dedup already happened at import.

    python3 tools/triage.py                       # triage all candidates
    python3 tools/triage.py --source sarif:semgrep --deep
    python3 tools/triage.py --domain web --limit 100

`--deep` gives the model code-reading tools (agentic backends only) so it can
verify cited locations; otherwise it reasons from the finding text (any backend).
This NEVER confirms a finding — it prioritizes. Use verify_finding.py to confirm.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sechound_lib import sechound_model, utcnow, repo_root
import findings_db
import llm

_VERDICTS = {"likely_true_positive", "likely_false_positive", "needs_verification"}

_SYSTEM = """You are a security triage analyst. You receive ONE candidate finding
(often raw scanner output) and decide whether it is worth a human's time. Apply
the false-positive checklist mechanically. You are NOT confirming it — you are
prioritizing.

Return ONLY this JSON:
{
  "verdict": "likely_true_positive | likely_false_positive | needs_verification",
  "reason": "one or two sentences citing the checklist pattern that drove the call",
  "severity": "CRITICAL | HIGH | MEDIUM | LOW | INFO (your calibrated estimate)"
}

Guidance: scanner hits are often unreachable, already-mitigated, test/fixture
code, or duplicates. Demand a plausible reachable path. When the finding lacks
enough context to decide, say needs_verification (don't guess true/false)."""


def _extract_json(text: str) -> dict | None:
    depth = start = 0
    start = -1
    for i, ch in enumerate(text or ""):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    start = -1
    return None


def _fp_checklist() -> str:
    p = repo_root() / "docs" / "FP_CHECKLIST.md"
    return p.read_text(encoding="utf-8") if p.exists() else "(FP checklist not found)"


def _triage_one(finding: dict, checklist: str, model: str, timeout: int, deep: bool) -> dict:
    user = (f"False-positive checklist:\n{checklist}\n\n"
            f"Candidate finding:\n```json\n{json.dumps(finding, indent=2)}\n```")
    res = llm.complete(_SYSTEM, user, model=model, timeout=timeout,
                       tools="Bash,Read" if deep else None)
    if res.error:
        return {"error": res.error}
    return _extract_json(res.text) or {"error": "no_json", "raw": res.text[:300]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", help="only triage findings with this source (e.g. sarif:semgrep)")
    ap.add_argument("--domain", help="only this domain")
    ap.add_argument("--status", default="candidate", help="only this status (default: candidate)")
    ap.add_argument("--limit", type=int, default=0, help="max findings to triage (0 = all)")
    ap.add_argument("--deep", action="store_true", help="let the model read cited code (agentic backends)")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--model", default=sechound_model("default"))
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args()

    usable, reason = llm.available()
    if not usable:
        sys.exit(f"[triage] LLM provider unavailable: {reason} (see docs/PROVIDERS.md)")

    db = findings_db.load_db()
    todo = [f for f in db
            if (f.get("status") or "candidate") == args.status
            and (not args.source or f.get("source") == args.source)
            and (not args.domain or (f.get("domain") or "") == args.domain)
            and not (f.get("triage") or {}).get("verdict")]
    if args.limit:
        todo = todo[:args.limit]
    if not todo:
        print("[triage] nothing to triage (filters matched 0 untriaged candidates)")
        return 0

    print(f"[triage] {len(todo)} candidate(s) | provider={llm.provider()} model={args.model} deep={args.deep}")
    checklist = _fp_checklist()
    counts = {"likely_true_positive": 0, "likely_false_positive": 0, "needs_verification": 0, "error": 0}

    def work(f):
        return f, _triage_one(f, checklist, args.model, args.timeout, args.deep)

    with cf.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for f, verdict in pool.map(work, todo):
            v = verdict.get("verdict")
            if v in _VERDICTS:
                f["triage"] = {"verdict": v, "reason": verdict.get("reason", ""),
                               "triaged_at": utcnow()}
                if verdict.get("severity"):
                    f["triage"]["severity_estimate"] = verdict["severity"]
                findings_db.upsert(f)
                counts[v] += 1
                print(f"  [{v:22}] {f.get('id')}  {f.get('title','')[:60]}")
            else:
                counts["error"] += 1
                print(f"  [error] {f.get('id')}: {verdict.get('error','?')}")

    print(f"\n[triage] done: {counts['likely_true_positive']} likely-TP, "
          f"{counts['likely_false_positive']} likely-FP, "
          f"{counts['needs_verification']} need verification, {counts['error']} errors.")
    print("[triage] review likely-TP first:  python3 tools/report.py --status candidate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
