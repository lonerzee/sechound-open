#!/usr/bin/env python3
"""
run.py — the loop driver: plan -> execute -> verify -> critic -> compound.

Runs one or more iterations against an engagement. Each iteration:
  1. plan      — planner prompt -> iteration_plan.json (ranked hypotheses)
  2. execute   — executor prompt -> candidate findings (fenced JSON) -> finding files
  3a. verifier — verifier prompt reproduces each candidate live and writes a
                 repro contract (so the harness below can confirm it)
  3b. verify   — verify_finding.py runs each candidate's repro contract
  4. critic    — critic.py adversarially reviews confirmations
  5. compound  — compounder.py folds learnings back into knowledge/

Scope/knowledge context is read from config/targets.yaml and the current
findings registry, so the planner doesn't re-hunt what's already tracked.

Usage:
    python3 tools/run.py <engagement_dir> --goal "audit the public API for IDOR" [--iterations N]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sechound_lib import resolve_engagement_arg, sechound_model, utcnow, repo_root, profile_context
import findings_db
import llm

try:
    import yaml
except ImportError:
    yaml = None


def _load_scope() -> dict:
    cfg = repo_root() / "config" / "targets.yaml"
    if cfg.exists() and yaml is not None:
        try:
            return yaml.safe_load(cfg.read_text()) or {}
        except Exception:
            return {}
    return {}


def _prompt(name: str) -> str:
    return (repo_root() / "prompts" / f"{name}.md").read_text(encoding="utf-8")


def _extract_fenced(text: str) -> list:
    import re
    out = []
    for m in re.finditer(r"```(?:json|JSON)?\s*\n(.*?)```", text, re.DOTALL):
        c = m.group(1).strip()
        if c.startswith(("{", "[")):
            try:
                out.append(json.loads(c))
            except json.JSONDecodeError:
                pass
    return out


def _knowledge_context(eng: Path) -> str:
    db = findings_db.load_db()
    tracked = [{"id": f.get("id"), "title": f.get("title"),
                "status": f.get("status"), "service": f.get("service")}
               for f in db][:50]
    invariants = repo_root() / "config" / "invariants.yaml"
    inv_text = invariants.read_text() if invariants.exists() else "(none configured)"
    return (f"## Already-tracked findings (do NOT re-hunt)\n```json\n"
            f"{json.dumps(tracked, indent=2)}\n```\n\n## Invariants to falsify\n{inv_text}\n")


def _run_tool(script: str, *tool_args: str) -> int:
    cmd = [sys.executable, str(repo_root() / "tools" / script), *tool_args]
    return subprocess.run(cmd).returncode


def iterate(eng: Path, goal: str, n: int, model: str, timeout: int, profile: str | None = None) -> None:
    scope = _load_scope()
    knowledge = _knowledge_context(eng)
    prof_ctx = profile_context(profile)
    iter_no = len(list((eng / "attempts").glob("iteration_*.json"))) + 1 if (eng / "attempts").exists() else 1

    common = (f"Engagement: {eng}\nGoal: {goal}\n"
              f"In-scope (config/targets.yaml):\n```json\n{json.dumps(scope.get('targets', []), indent=2)}\n```\n\n"
              f"{knowledge}{prof_ctx}")

    # 1. PLAN
    print(f"\n=== iteration {iter_no}: plan ===")
    plan_res = llm.complete(_prompt("planner"), common + "\nProduce the plan.",
                            model=model, timeout=timeout)
    plan = next((o for o in _extract_fenced(plan_res.text) if isinstance(o, dict)), {})
    (eng / "iteration_plan.json").write_text(json.dumps(plan or {"raw": plan_res.text}, indent=2))
    hyps = plan.get("hypotheses", [])
    print(f"[run] {len(hyps)} hypotheses planned")

    # 2. EXECUTE
    print(f"=== iteration {iter_no}: execute ===")
    exec_input = (common + "\n## Plan\n```json\n" + json.dumps(plan, indent=2) +
                  "\n```\nRun the hunt and emit candidate findings as fenced ```json blocks.")
    exec_res = llm.complete(_prompt("executor"), exec_input, model=model,
                            timeout=timeout, tools="Bash,Read")
    candidates = [o for o in _extract_fenced(exec_res.text)
                  if isinstance(o, dict) and o.get("title")]
    (eng / "attempts").mkdir(exist_ok=True)
    (eng / "attempts" / f"iteration_{iter_no:03d}.json").write_text(json.dumps({
        "iteration": iter_no, "ran_at": utcnow(), "goal": goal,
        "candidates": candidates, "raw_output": exec_res.text[-8000:],
    }, indent=2))
    print(f"[run] {len(candidates)} candidate(s) emitted")

    # Persist candidates: registry (dedup) + engagement finding files.
    for c in candidates:
        c.setdefault("status", "candidate")
        c.setdefault("source", "executor")
        c.setdefault("found_at", utcnow()[:10])
        fid, action = findings_db.upsert(c)
        c["id"] = fid
        (eng / "findings" / f"{fid}.json").write_text(json.dumps(c, indent=2))
        print(f"  [{action}] {fid}: {c.get('title','')[:60]}")

    # 3a. VERIFIER (LLM) — reproduce each candidate live and write a repro
    # contract, so the mechanical harness in 3b can confirm it. Without this the
    # loop only ever produces candidates (executor emits no repro).
    if candidates:
        print(f"=== iteration {iter_no}: verifier (write repro contracts) ===")
        for c in candidates:
            fid = c["id"]
            fpath = eng / "findings" / f"{fid}.json"
            vres = llm.complete(
                _prompt("verifier"),
                f"Engagement: {eng}\nReproduce this candidate. Write the repro to the file "
                f"`repro_{fid}.sh` in the engagement directory, and in your JSON set "
                f"`evidence.repro.script` to exactly \"repro_{fid}.sh\" so the harness finds it.\n"
                f"```json\n{json.dumps(c, indent=2)}\n```",
                model=model, timeout=timeout, tools="Bash,Read", cwd=eng,
            )
            parsed = next((o for o in _extract_fenced(vres.text) if isinstance(o, dict)), None)
            if not parsed:
                print(f"  [{fid}] verifier produced no contract — stays candidate")
                continue
            try:
                finding = json.loads(fpath.read_text())
                ev = parsed.get("evidence") or {}
                if ev.get("repro"):
                    finding.setdefault("evidence", {})["repro"] = ev["repro"]
                if parsed.get("reasoning_trace"):
                    finding["reasoning_trace"] = parsed["reasoning_trace"]
                fpath.write_text(json.dumps(finding, indent=2))
                print(f"  [{fid}] repro contract written: {ev.get('repro', {}).get('script', '?')}")
            except Exception as e:
                print(f"  [{fid}] failed to merge verifier output: {e}")

    # 3b. VERIFY (harness) -> 4. CRITIC -> 5. COMPOUND
    print(f"=== iteration {iter_no}: verify ===")
    _run_tool("verify_finding.py", str(eng))
    print(f"=== iteration {iter_no}: critic ===")
    _run_tool("critic.py", str(eng))
    print(f"=== iteration {iter_no}: compound ===")
    _run_tool("compounder.py", str(eng))

    if n > 1:
        iterate(eng, goal, n - 1, model, timeout, profile)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("engagement_dir", nargs="?", default=None)
    ap.add_argument("--goal", required=True, help="what to hunt this run")
    ap.add_argument("--iterations", type=int, default=1)
    ap.add_argument("--profile", default=None, help="domain profile (default: config/targets.yaml 'profile:')")
    ap.add_argument("--model", default=sechound_model("default"))
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    eng = resolve_engagement_arg(args.engagement_dir)
    usable, reason = llm.available()
    if not usable:
        sys.exit(f"[run] LLM provider unavailable: {reason} (see docs/PROVIDERS.md)")

    print(f"[run] engagement={eng.name} goal={args.goal!r} iterations={args.iterations} "
          f"provider={llm.provider()} model={args.model}")
    iterate(eng, args.goal, args.iterations, args.model, args.timeout, args.profile)
    print("\n[run] loop complete. Review with: python3 tools/ultrareview.py "
          f"{eng}  /  python3 tools/report.py {eng}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
