#!/usr/bin/env python3
"""
orchestrate.py — fan out N specialized agents in parallel (one-shot dispatch).

Used when a single goal benefits from multiple specialized lanes running
concurrently (e.g. recon + web-hunter + api-tester on the same component). Each
lane runs a fresh `claude --print` with its own system prompt and working
directory. Stdout streams live to `<lane>/live.log`. On completion, finding-like
JSON objects in FENCED ```json blocks are auto-ingested into the findings DB.

Outputs under `<engagement>/orchestrator/<run_id>/`:
  <lane>/live.log     streamed stdout (tail -f while running)
  <lane>/stderr.log   stderr
  <lane>.json         structured result with parsed findings
  summary.json        cross-lane summary

Usage:
    python3 tools/orchestrate.py <engagement_dir> <task_yaml>

task_yaml schema:
    run_id: full-audit-2026-01-01
    timeout: 900
    lanes:
      - name: recon
        prompt_file: prompts/lane_recon.md     # or inline `prompt:` / `agent_file:`
        user_input: "Map all controllers in <component> ..."
        model: claude-haiku-4-5-20251001       # optional per-lane override
      - name: web_hunter
        prompt_file: prompts/lane_web_hunter.md
        user_input: "Live test the public API surface ..."
        allowed_tools: "Bash,Read"             # optional; default Bash,Read
        validation: true                       # optional; serialize live-mutation lanes

Lanes run concurrently. Pass --max-parallel N to throttle.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sechound_lib import sechound_model, utcnow, repo_root
import llm

try:
    import findings_db
    _HAS_DB = True
except Exception:
    _HAS_DB = False

try:
    import yaml
except ImportError:
    yaml = None


_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*\n(.*?)```", re.DOTALL)


def _extract_from_fences(text: str) -> tuple[list, str]:
    """Pull JSON from markdown code fences. Returns (parsed, text_without_fences)."""
    results: list = []

    def _replace(m: "re.Match[str]") -> str:
        content = m.group(1).strip()
        if content.startswith(("{", "[")):
            try:
                results.append(json.loads(content))
            except json.JSONDecodeError:
                pass
        return " "

    return results, _FENCE_RE.sub(_replace, text)


def _brace_scan(text: str) -> list:
    results, i, n = [], 0, len(text)
    while i < n:
        if text[i] not in "{[":
            i += 1
            continue
        opener, closer = text[i], ("}" if text[i] == "{" else "]")
        depth, start, in_str, esc, j = 0, i, False, False, i
        while j < n:
            ch = text[j]
            if esc:
                esc = False
            elif ch == "\\" and in_str:
                esc = True
            elif ch == '"':
                in_str = not in_str
            elif not in_str:
                if ch == opener:
                    depth += 1
                elif ch == closer:
                    depth -= 1
                    if depth == 0:
                        try:
                            results.append(json.loads(text[start:j + 1]))
                        except json.JSONDecodeError:
                            pass
                        i = j + 1
                        break
            j += 1
        else:
            break
    return results


def extract_all_json(text: str) -> list:
    fenced, remainder = _extract_from_fences(text)
    brace = _brace_scan(remainder)
    seen = {json.dumps(o, sort_keys=True) for o in fenced}
    return fenced + [o for o in brace if json.dumps(o, sort_keys=True) not in seen]


def _is_finding(obj: object) -> bool:
    if not isinstance(obj, dict):
        return False
    if not obj.get("title"):
        return False
    has_sev = obj.get("severity", "").upper() in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
    return sum([has_sev, bool(obj.get("summary") or obj.get("description")), bool(obj.get("service"))]) >= 2


def _flatten_findings(objects: list) -> list[dict]:
    out = []
    for obj in objects:
        if isinstance(obj, list):
            out += [it for it in obj if _is_finding(it)]
        elif _is_finding(obj):
            out.append(obj)
        elif isinstance(obj, dict):
            for val in obj.values():
                if isinstance(val, list):
                    out += [it for it in val if _is_finding(it)]
    return out


class _SharedState:
    """Thread-safe stub file of findings confirmed mid-run, readable by all lanes
    so a lane can skip what a sibling already confirmed."""
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        path.write_text(json.dumps([]))

    def append(self, finding: dict) -> None:
        stub = {k: finding.get(k) for k in ("title", "severity", "service", "endpoint", "files")}
        with self._lock:
            existing = json.loads(self._path.read_text())
            existing.append(stub)
            self._path.write_text(json.dumps(existing, indent=2))

    def read(self) -> list[dict]:
        with self._lock:
            try:
                return json.loads(self._path.read_text())
            except Exception:
                return []


def _ingest_findings(findings: list[dict], lane: str, shared: "_SharedState | None") -> int:
    """Upsert each finding into the findings DB. Returns count ingested."""
    if not _HAS_DB:
        print(f"  [{lane}] findings_db unavailable — skipping auto-ingest", flush=True)
        return 0
    ingested = 0
    for f in findings:
        f.setdefault("source", f"agent-capture:{lane}")
        f.setdefault("found_at", utcnow()[:10])
        try:
            fid, action = findings_db.upsert(f)
            print(f"  [{lane}] {action} -> {fid}", flush=True)
            if action != "duplicate":
                ingested += 1
                if shared is not None:
                    shared.append(f)
        except Exception as e:
            print(f"  [{lane}] ingest error: {e}", flush=True)
    return ingested


def load_task(task_path: Path) -> dict:
    if task_path.suffix.lower() in (".yaml", ".yml"):
        if yaml is None:
            sys.exit("PyYAML not installed; pip install pyyaml or use a .json task file")
        return yaml.safe_load(task_path.read_text())
    return json.loads(task_path.read_text())


# Only one lane at a time may run live mutation against the shared auth/scope.
# Read-only recon/hunting lanes stay parallel; mutation lanes serialize behind
# this lock to avoid (a) mutual 401s misread as "endpoint secured" and (b)
# shared-state pollution that breaks IDOR/race repro determinism.
_VALIDATION_LOCK = threading.Lock()


def _needs_validation_lock(lane: dict) -> bool:
    return bool(lane.get("validation") or lane.get("serialize"))


def run_lane(lane: dict, eng: Path, default_model: str, timeout: int,
             out_dir: Path, shared: "_SharedState | None") -> dict:
    name = lane["name"]
    root = repo_root()
    agent_tools = ""

    if "agent_file" in lane:
        agent_path = (root / lane["agent_file"]).resolve()
        if not agent_path.exists():
            return {"lane": name, "error": f"agent_file missing: {agent_path}"}
        raw = agent_path.read_text(encoding="utf-8")
        fm = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, flags=re.DOTALL)
        if fm:
            t = re.search(r"^tools:\s*(.+)$", fm.group(1), flags=re.MULTILINE)
            if t:
                agent_tools = ",".join(p.strip() for p in t.group(1).split(",") if p.strip())
        system_prompt = re.sub(r"^---\s*\n.*?\n---\s*\n", "", raw, count=1, flags=re.DOTALL)
    elif "prompt_file" in lane:
        prompt_path = (root / lane["prompt_file"]).resolve()
        if not prompt_path.exists():
            return {"lane": name, "error": f"prompt missing: {prompt_path}"}
        system_prompt = prompt_path.read_text(encoding="utf-8")
    elif "prompt" in lane:
        system_prompt = lane["prompt"]
    else:
        return {"lane": name, "error": "lane must specify agent_file, prompt_file, or prompt"}

    user_input = lane.get("user_input") or "Proceed per system prompt."
    model = lane.get("model") or default_model
    usable, reason = llm.available()
    if not usable:
        return {"lane": name, "error": f"LLM provider unavailable: {reason}"}

    lane_dir = out_dir / name
    lane_dir.mkdir(parents=True, exist_ok=True)

    shared_note = ""
    if shared is not None:
        (lane_dir / "shared_findings.json").write_text(
            json.dumps({"path": str(shared._path),
                        "note": "findings confirmed by sibling lanes this run"}))
        shared_note = (
            f"\n\n## Sibling Lane Coordination\n"
            f"Other lanes run concurrently. Before validating an endpoint or filing a finding, "
            f"run `cat {shared._path}` to see what siblings already confirmed. Re-read it every "
            f"few tool calls — it updates live. If the endpoint+class is listed, skip it."
        )

    log_path = lane_dir / "live.log"
    stderr_path = lane_dir / "stderr.log"
    print(f"  [{name}] starting  model={model}  log={log_path}", flush=True)

    allowed_tools = lane.get("allowed_tools") or agent_tools or "Bash,Read"
    mcp_cfg = root / ".mcp.json"
    full_input = f"Engagement: {eng}\n\n{user_input}{shared_note}"

    # Serialize live-mutation lanes behind the validation mutex; read-only lanes
    # stay parallel.
    needs_lock = _needs_validation_lock(lane)
    if needs_lock:
        if _VALIDATION_LOCK.locked():
            print(f"  [{name}] waiting for validation mutex...", flush=True)
        _VALIDATION_LOCK.acquire()
    try:
        res = llm.complete(
            system_prompt, full_input, model=model, timeout=timeout,
            tools=allowed_tools, cwd=lane_dir, stream_to=log_path, stderr_to=stderr_path,
            mcp_config=mcp_cfg if mcp_cfg.exists() else None,
        )
    finally:
        if needs_lock:
            _VALIDATION_LOCK.release()

    if res.error:
        return {"lane": name, "error": res.error, "log": str(log_path)}

    raw = res.text
    # Auto-ingest ONLY from explicit ```json fenced blocks — never loose braces
    # in prose, which would scrape illustrative/"rejected candidate" examples.
    fenced_json, _ = _extract_from_fences(raw)
    findings = _flatten_findings(fenced_json)
    first_obj = next((o for o in fenced_json if isinstance(o, dict)), None)
    n_ingested = 0
    if findings:
        print(f"  [{name}] {len(findings)} finding(s) detected — ingesting ...", flush=True)
        n_ingested = _ingest_findings(findings, name, shared)

    print(f"  [{name}] done  exit={res.exit_code}  elapsed={res.elapsed_s}s  ingested={n_ingested}", flush=True)
    return {
        "lane": name, "elapsed_s": res.elapsed_s, "exit_code": res.exit_code,
        "log": str(log_path), "stderr_log": str(stderr_path),
        "stderr_tail": res.stderr_tail, "raw_output": raw,
        "parsed": first_obj, "findings_ingested": n_ingested,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("engagement_dir")
    ap.add_argument("task_file")
    ap.add_argument("--model", default=sechound_model("default"))
    ap.add_argument("--max-parallel", type=int, default=4)
    args = ap.parse_args()

    eng = Path(args.engagement_dir).resolve()
    if not eng.is_dir():
        sys.exit(f"engagement dir not found: {eng}")

    task = load_task(Path(args.task_file))
    run_id = task.get("run_id") or utcnow().replace(":", "").replace("-", "")
    lanes = task.get("lanes") or []
    if not lanes:
        sys.exit("task file has no lanes")
    timeout = int(task.get("timeout") or 600)

    out_dir = eng / "orchestrator" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    shared = _SharedState(out_dir / "shared_findings.json")

    print(f"[orchestrate] run_id={run_id}  lanes={len(lanes)}  model={args.model}")
    print(f"[orchestrate] outputs -> {out_dir}\n[orchestrate] tail live logs with:")
    for lane in lanes:
        print(f"    tail -f {out_dir / lane['name'] / 'live.log'}")
    print()

    started = time.time()
    results: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=min(args.max_parallel, len(lanes))) as pool:
        futures = {
            pool.submit(run_lane, lane, eng, args.model, timeout, out_dir, shared): lane["name"]
            for lane in lanes
        }
        for fut in cf.as_completed(futures):
            name = futures[fut]
            try:
                r = fut.result()
            except Exception as e:
                r = {"lane": name, "error": f"exception: {e}"}
            (out_dir / f"{name}.json").write_text(json.dumps(r, indent=2))
            results.append(r)

    total_ingested = sum(r.get("findings_ingested", 0) for r in results)
    (out_dir / "summary.json").write_text(json.dumps({
        "run_id": run_id, "started_at": utcnow(),
        "elapsed_s": round(time.time() - started, 2), "total_ingested": total_ingested,
        "lanes": [{"lane": r["lane"], "exit_code": r.get("exit_code"),
                   "elapsed_s": r.get("elapsed_s"),
                   "findings_ingested": r.get("findings_ingested", 0),
                   "log": r.get("log"), "error": r.get("error")} for r in results],
    }, indent=2))
    print(f"\n[orchestrate] complete  elapsed={round(time.time()-started,2)}s  ingested={total_ingested}")

    # Post-run cross-lane chain analysis.
    all_ingested = shared.read()
    if len(all_ingested) >= 2 and llm.available()[0]:
        print(f"\n[orchestrate] {len(all_ingested)} findings ingested — running chain analysis...")
        chain_prompt = (
            f"You are a security chain analyst. These {len(all_ingested)} findings were discovered "
            f"in the same engagement.\n\nFindings:\n{json.dumps(all_ingested, indent=2)}\n\n"
            "Identify any 2-3 component attack chains where combining findings increases impact. "
            "For each: title, components (finding titles), combined_severity, chain_summary. "
            "Only chain findings from different services or vulnerability classes. "
            "Output a JSON array of chains, or [] if none."
        )
        try:
            cr = llm.complete("You are a security chain analyst.", chain_prompt,
                              model=args.model, timeout=120)
            chains = next((o for o in extract_all_json(cr.text) if isinstance(o, list)), [])
            if chains:
                (out_dir / "chains.json").write_text(json.dumps(chains, indent=2))
                eng_chains = eng / "chains_to_investigate.json"
                existing = json.loads(eng_chains.read_text()) if eng_chains.exists() else []
                titles = {c.get("title") for c in existing}
                eng_chains.write_text(json.dumps(
                    existing + [c for c in chains if c.get("title") not in titles], indent=2))
                print(f"[orchestrate] {len(chains)} chain(s) suggested -> {out_dir / 'chains.json'}")
                for c in chains[:3]:
                    print(f"  [{c.get('combined_severity','?')}] {c.get('title','')}")
            else:
                print("[orchestrate] no cross-lane chains identified")
        except Exception as e:
            print(f"[orchestrate] chain analysis failed: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
