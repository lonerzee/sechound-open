#!/usr/bin/env python3
"""
ultrareview.py — multi-agent adversarial review of findings at engagement end.

Spawns two parallel `claude --print` reviewers per finding:
  - prompts/ultrareview_static.md  — citation existence + accuracy
  - prompts/ultrareview_counter.md — argues why a real-deployment exploit fails

(The invalidator lane is intentionally absent: critic.py already applies the FP
checklist adversarially before findings reach this phase.)

Merges the per-lane verdicts into a per-finding consensus. Demotion rule: the
final verdict is the MOST CONSERVATIVE across lanes — any single lane
recommending retraction flags the finding for retraction.

Usage:
    python3 tools/ultrareview.py <engagement_dir> [finding_id|all] [--model MODEL]
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sechound_lib import sechound_model, utcnow, repo_root
import llm

LANES = ("static", "counter")
PROMPT_FILES = {
    "static": "prompts/ultrareview_static.md",
    "counter": "prompts/ultrareview_counter.md",
}
DEMOTION_RANK = {
    "none": 0,
    "demote_severity": 1,
    "demote_to_candidate": 2,
    "demote_to_informational": 3,
    "by_design": 4,
    "retract": 5,
    "retract_due_to_fabricated_citation": 5,
}


def extract_json(text: str) -> dict | None:
    if not text:
        return None
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    start = -1
    return None


def load_finding(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return {"finding_id": path.stem, "raw_markdown": text}


def list_findings(eng: Path, target: str) -> list[Path]:
    findings_dir = eng / "findings"
    if not findings_dir.exists():
        return []
    all_findings = sorted(p for p in findings_dir.iterdir() if p.suffix.lower() in (".json", ".md"))
    if target == "all":
        return all_findings
    matches = [p for p in all_findings if target in p.stem]
    if not matches:
        sys.exit(f"No finding matching '{target}' under {findings_dir}")
    return matches


def run_lane(lane: str, finding: dict, eng: Path, model: str, timeout: int) -> dict:
    prompt_path = repo_root() / PROMPT_FILES[lane]
    if not prompt_path.exists():
        return {"lane": lane, "error": f"prompt missing: {prompt_path}"}

    user_input = (
        f"Engagement directory: {eng}\nLane: {lane}\n"
        f"Finding payload (review this; output ONLY the JSON specified in your "
        f"system prompt):\n\n```json\n{json.dumps(finding, indent=2)}\n```\n"
    )
    # The static lane reads cited files; give it tools when the provider supports them.
    tools = "Bash,Read" if lane == "static" else None
    res = llm.complete(prompt_path.read_text(encoding="utf-8"), user_input,
                       model=model, timeout=timeout, tools=tools)
    if res.error:
        return {"lane": lane, "error": res.error}
    return {
        "lane": lane, "elapsed_s": res.elapsed_s, "exit_code": res.exit_code,
        "stderr": res.stderr_tail, "raw_output": res.text, "parsed": extract_json(res.text),
    }


def merge_lanes(finding_id: str, lane_results: list[dict]) -> dict:
    recs, blockers = [], []
    for r in lane_results:
        parsed = r.get("parsed") or {}
        recs.append((r["lane"], parsed.get("downgrade_recommendation") or "none"))
        for key in ("missing_or_wrong", "blocking_concerns", "fp_pattern_failures",
                    "blockers_to_prod_exploitation"):
            if parsed.get(key):
                blockers.append({"lane": r["lane"], "category": key, "items": parsed[key]})

    worst_rank = max((DEMOTION_RANK.get(r, 0) for _, r in recs), default=0)
    worst = next((r for r in DEMOTION_RANK if DEMOTION_RANK[r] == worst_rank), "none")
    consensus = (
        "retract" if worst_rank >= 5 else
        "demote_to_informational" if worst_rank >= 3 else
        "demote_to_candidate" if worst_rank == 2 else
        "demote_severity" if worst_rank == 1 else "uphold"
    )
    return {
        "finding_id": finding_id, "merged_at": utcnow(),
        "lane_recommendations": [{"lane": l, "recommendation": r} for l, r in recs],
        "worst_recommendation": worst, "consensus": consensus, "blockers": blockers,
    }


def review_finding(finding_path: Path, eng: Path, model: str, timeout: int) -> dict:
    finding = load_finding(finding_path)
    finding_id = finding.get("finding_id") or finding_path.stem
    out_dir = eng / "ultrareview" / finding_id
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"  [ultrareview] {finding_id} — spawning {len(LANES)} lanes", flush=True)
    results = []
    with cf.ThreadPoolExecutor(max_workers=len(LANES)) as pool:
        futures = {pool.submit(run_lane, lane, finding, eng, model, timeout): lane for lane in LANES}
        try:
            for fut in cf.as_completed(futures, timeout=timeout + 60):
                lane = futures[fut]
                try:
                    r = fut.result()
                except Exception as e:
                    r = {"lane": lane, "error": f"exception: {e}"}
                (out_dir / f"{lane}.json").write_text(json.dumps(r, indent=2))
                results.append(r)
                print(f"    [{finding_id}] {lane}: {'ok' if r.get('parsed') else 'no_json'} {r.get('error') or ''}", flush=True)
        except cf.TimeoutError:
            for fut, lane in futures.items():
                if not fut.done():
                    r = {"lane": lane, "error": f"lane wedged > {timeout + 60}s"}
                    (out_dir / f"{lane}.json").write_text(json.dumps(r, indent=2))
                    results.append(r)

    merged = merge_lanes(finding_id, results)
    (out_dir / "merged.json").write_text(json.dumps(merged, indent=2))
    return merged


def write_summary(eng: Path, merges: list[dict]) -> Path:
    reports_dir = eng / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out = reports_dir / f"ultrareview_{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H%M%SZ')}.md"

    lines = [
        f"# UltraReview — {eng.name}", f"_Generated {utcnow()}_", "",
        f"Findings reviewed: **{len(merges)}**", "",
        "| Finding | Consensus | Worst Lane Rec | Lanes |", "|---|---|---|---|",
    ]
    for m in merges:
        lane_rec = ", ".join(f"{lr['lane']}={lr['recommendation']}" for lr in m["lane_recommendations"])
        lines.append(f"| {m['finding_id']} | **{m['consensus']}** | {m['worst_recommendation']} | {lane_rec} |")

    lines.append("\n## Blocking Concerns by Finding\n")
    for m in merges:
        if not m["blockers"]:
            continue
        lines.append(f"### {m['finding_id']}")
        for b in m["blockers"]:
            lines.append(f"- `{b['lane']}` / `{b['category']}`:")
            items = b["items"]
            for it in (items if isinstance(items, list) else [items]):
                lines.append(f"  - {it}")
        lines.append("")

    out.write_text("\n".join(lines))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("engagement_dir")
    ap.add_argument("target", nargs="?", default="all", help="finding id substring or 'all'")
    ap.add_argument("--model", default=sechound_model("expensive_tasks"))
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--concurrency", type=int, default=4,
                    help="findings reviewed in parallel (each runs 2 lanes)")
    args = ap.parse_args()

    eng = Path(args.engagement_dir).resolve()
    if not eng.is_dir():
        sys.exit(f"engagement dir not found: {eng}")

    findings = list_findings(eng, args.target)
    if not findings:
        print(f"[ultrareview] no findings under {eng}/findings/ — skipping")
        return 0

    workers = max(1, min(args.concurrency, len(findings)))
    print(f"[ultrareview] engagement={eng.name} findings={len(findings)} "
          f"model={args.model} concurrency={workers}", flush=True)

    merges: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(review_finding, f, eng, args.model, args.timeout): f for f in findings}
        for fut in cf.as_completed(futures):
            try:
                merges.append(fut.result())
            except Exception as e:
                print(f"  [ultrareview] {futures[fut].stem}: failed — {e}", flush=True)

    print(f"[ultrareview] summary written: {write_summary(eng, merges)}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[ultrareview] interrupted — partial results saved per finding", file=sys.stderr)
        sys.exit(130)
