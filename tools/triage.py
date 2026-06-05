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
from sechound_lib import sechound_model, utcnow, repo_root, load_profile
import findings_db
import llm

_VERDICTS = {"likely_true_positive", "likely_false_positive", "needs_verification"}

_SYSTEM = """You are a security triage analyst. You receive a BATCH of candidate
findings (often raw scanner output) and decide which are worth a human's time.
Apply the false-positive checklist mechanically. You are NOT confirming them —
you are prioritizing.

Return ONLY a JSON array, one object per finding, echoing its id:
[
  {
    "id": "<finding id>",
    "verdict": "likely_true_positive | likely_false_positive | needs_verification",
    "reason": "one or two sentences citing the checklist pattern that drove the call",
    "severity": "CRITICAL | HIGH | MEDIUM | LOW | INFO (calibrated estimate)"
  }
]

Guidance: scanner hits are often unreachable, already-mitigated, test/fixture/
vendor code, or duplicates — weight those toward likely_false_positive. Demand a
plausible reachable path. When a finding lacks context to decide, say
needs_verification (don't guess). Return an entry for EVERY id you were given."""


def _extract_array(text: str) -> list:
    """Pull the first top-level JSON array out of the model output."""
    depth, start, in_str, esc = 0, -1, False, False
    for i, ch in enumerate(text or ""):
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
        elif ch == '"':
            in_str = not in_str
        elif not in_str:
            if ch == "[":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0 and start != -1:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        start = -1
    return []


def _extract_json(text: str) -> dict | None:  # kept for the test/back-compat
    depth, start = 0, -1
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


def _fp_checklist(profile: str | None = None) -> str:
    p = repo_root() / "docs" / "FP_CHECKLIST.md"
    core = p.read_text(encoding="utf-8") if p.exists() else "(FP checklist not found)"
    prof = load_profile(profile)
    if prof and prof.get("fp"):
        core += f"\n\n## Profile FP patterns ({prof['name']})\n{prof['fp']}"
    return core


def _slim(f: dict) -> dict:
    """Only the fields triage needs — keeps the batch prompt small."""
    return {k: f.get(k) for k in ("id", "title", "severity", "domain", "category",
                                  "cwe", "component", "location", "files", "summary",
                                  "source") if f.get(k)}


def _triage_batch(findings: list[dict], checklist: str, model: str, timeout: int,
                  deep: bool) -> dict:
    """Triage a batch in one call. Returns {id: {verdict, reason, severity}}."""
    user = (f"False-positive checklist:\n{checklist}\n\n"
            f"Candidate findings ({len(findings)}):\n```json\n"
            f"{json.dumps([_slim(f) for f in findings], indent=2)}\n```")
    res = llm.complete(_SYSTEM, user, model=model, timeout=timeout,
                       tools="Bash,Read" if deep else None)
    if res.error:
        return {"__error__": res.error}
    by_id = {}
    for item in _extract_array(res.text):
        if isinstance(item, dict) and item.get("id"):
            by_id[item["id"]] = item
    return by_id


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", help="only triage findings with this source (e.g. sarif:semgrep)")
    ap.add_argument("--domain", help="only this domain")
    ap.add_argument("--status", default="candidate", help="only this status (default: candidate)")
    ap.add_argument("--limit", type=int, default=0, help="max findings to triage (0 = all)")
    ap.add_argument("--deep", action="store_true", help="let the model read cited code (agentic backends)")
    ap.add_argument("--profile", default=None, help="domain profile (default: config/targets.yaml 'profile:')")
    ap.add_argument("--batch-size", type=int, default=10, help="findings per LLM call (default 10)")
    ap.add_argument("--max-batches", type=int, default=0, help="cost cap: stop after N LLM calls (0 = no cap)")
    ap.add_argument("--skip-info", action="store_true", help="don't spend LLM calls on INFO-severity findings")
    ap.add_argument("--concurrency", type=int, default=4, help="batches in flight at once")
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
    if args.skip_info:
        todo = [f for f in todo if (f.get("severity") or "").upper() != "INFO"]
    if args.limit:
        todo = todo[:args.limit]
    if not todo:
        print("[triage] nothing to triage (filters matched 0 untriaged candidates)")
        return 0

    # Batch to keep calls (and cost) bounded: N findings per LLM call.
    batches = [todo[i:i + args.batch_size] for i in range(0, len(todo), args.batch_size)]
    if args.max_batches:
        batches = batches[:args.max_batches]
    triaged_n = sum(len(b) for b in batches)
    print(f"[triage] {triaged_n} candidate(s) in {len(batches)} call(s) "
          f"(batch={args.batch_size}) | provider={llm.provider()} model={args.model} deep={args.deep}")
    if triaged_n < len(todo):
        print(f"[triage] cost cap: {len(todo) - triaged_n} left untriaged (raise --max-batches to continue)")
    checklist = _fp_checklist(args.profile)
    counts = {"likely_true_positive": 0, "likely_false_positive": 0, "needs_verification": 0, "error": 0}

    def work(batch):
        return batch, _triage_batch(batch, checklist, args.model, args.timeout, args.deep)

    with cf.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for batch, verdicts in pool.map(work, batches):
            if "__error__" in verdicts:
                counts["error"] += len(batch)
                print(f"  [error] batch failed: {verdicts['__error__']}")
                continue
            for f in batch:
                v = (verdicts.get(f["id"]) or {}).get("verdict")
                if v in _VERDICTS:
                    item = verdicts[f["id"]]
                    f["triage"] = {"verdict": v, "reason": item.get("reason", ""),
                                   "triaged_at": utcnow()}
                    if item.get("severity"):
                        f["triage"]["severity_estimate"] = item["severity"]
                    findings_db.upsert(f)
                    counts[v] += 1
                    print(f"  [{v:22}] {f.get('id')}  {f.get('title','')[:56]}")
                else:
                    counts["error"] += 1
                    print(f"  [no-verdict] {f.get('id')} (model omitted it)")

    print(f"\n[triage] done: {counts['likely_true_positive']} likely-TP, "
          f"{counts['likely_false_positive']} likely-FP, "
          f"{counts['needs_verification']} need verification, {counts['error']} errors.")
    print("[triage] review likely-TP first:  python3 tools/report.py --status candidate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
