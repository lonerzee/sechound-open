#!/usr/bin/env python3
"""
compounder.py — extract and store reusable knowledge after each iteration.

Reads iteration_plan.json + the latest attempt JSON (+ verification_result.json
if present), invokes the Claude CLI with prompts/compounder.md as the system
prompt, then applies knowledge_added entries to the relevant knowledge files and
methodology_updates to methodology_tree.json.

Usage:
    python3 tools/compounder.py <engagement_dir> [--model MODEL] [--iteration N]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sechound_lib import resolve_engagement_arg, sechound_model, utcnow, repo_root
import llm


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


def load_json_safe(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


def append_to_knowledge(path: Path, entry: str) -> None:
    """Append entry to a knowledge file, skipping near-duplicates.

    Dedup heuristic: if any existing line shares >= 70% of the entry's words,
    the observation is already captured and we skip it silently. Prevents the
    same dead end accumulating across iterations.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""

    entry_words = set(entry.lower().split())
    if len(entry_words) >= 6:
        for line in existing.splitlines():
            line_words = set(line.lower().split())
            if not line_words:
                continue
            if len(entry_words & line_words) / len(entry_words) >= 0.70:
                return  # already captured

    sep = "\n\n" if existing.strip() else ""
    path.write_text(existing + sep + f"<!-- {utcnow()} -->\n{entry.strip()}\n", encoding="utf-8")


def apply_knowledge(eng: Path, knowledge_added: list[dict]) -> None:
    root = repo_root()
    for item in knowledge_added:
        file_rel = item.get("file", "")
        entry = item.get("entry", "")
        if not file_rel or not entry:
            continue
        # Knowledge files live under the repo (shared) or the engagement (local).
        if file_rel.startswith(("knowledge/", "engagements/")):
            target = root / file_rel
        else:
            target = eng / file_rel
        try:
            append_to_knowledge(target, entry)
            print(f"[compounder] updated {target}")
        except Exception as e:
            print(f"[compounder] failed to write {file_rel}: {e}")


def apply_methodology_updates(eng: Path, updates: dict) -> None:
    tree_path = eng / "methodology_tree.json"
    if not tree_path.exists() or not updates:
        return
    try:
        tree = json.loads(tree_path.read_text(encoding="utf-8"))
        branch = updates.get("branch_marked_explored", "")
        result = updates.get("branch_result", "")
        next_target = updates.get("next_recommended_target", "")
        if branch and result:
            node = tree
            for part in branch.replace(" > ", ".").split("."):
                part = part.strip().replace(" ", "_").replace("-", "_")
                if isinstance(node, dict) and part in node:
                    node = node[part]
                elif isinstance(node, dict):
                    break
            if isinstance(node, dict):
                node["status"] = (
                    "tested_positive" if result == "tested_positive"
                    else "tested_negative" if result == "tested_negative"
                    else "partially_explored"
                )
                node["last_tested"] = utcnow()
        if next_target:
            tree.setdefault("_compounder_hints", []).append(
                {"next_target": next_target, "added_at": utcnow()}
            )
        tree_path.write_text(json.dumps(tree, indent=2), encoding="utf-8")
        print(f"[compounder] methodology_tree updated — branch={branch} result={result}")
    except Exception as e:
        print(f"[compounder] failed to update methodology_tree: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("engagement_dir", nargs="?", default=None)
    ap.add_argument("--model", default=sechound_model("default"))
    ap.add_argument("--iteration", type=int, default=None)
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    eng = resolve_engagement_arg(args.engagement_dir)

    usable, reason = llm.available()
    if not usable:
        print(f"[compounder] LLM provider unavailable ({reason}) — skipping")
        return 0

    prompt_path = repo_root() / "prompts" / "compounder.md"
    if not prompt_path.exists():
        print(f"[compounder] {prompt_path} not found — skipping")
        return 0

    plan = load_json_safe(eng / "iteration_plan.json")
    verification = load_json_safe(eng / "verification_result.json")

    attempt_data: dict = {}
    if args.iteration:
        attempt_data = load_json_safe(eng / "attempts" / f"iteration_{args.iteration:03d}.json")
    else:
        attempts_dir = eng / "attempts"
        if attempts_dir.exists():
            files = sorted(attempts_dir.glob("iteration_*.json"))
            if files:
                attempt_data = load_json_safe(files[-1])

    if not plan and not attempt_data:
        print("[compounder] no iteration_plan.json or attempt data — skipping")
        return 0

    user_input = (
        f"Engagement: {eng}\n\n"
        f"## Iteration Plan\n```json\n{json.dumps(plan, indent=2)}\n```\n\n"
        f"## Iteration Execution\n```json\n{json.dumps(attempt_data, indent=2)}\n```\n\n"
    )
    if verification:
        user_input += f"## Verification Result\n```json\n{json.dumps(verification, indent=2)}\n```\n\n"
    user_input += "Extract reusable knowledge and output ONLY the JSON specified in the prompt."

    res = llm.complete(
        prompt_path.read_text(encoding="utf-8"), user_input,
        model=args.model, timeout=args.timeout,
    )
    elapsed = res.elapsed_s
    if res.error:
        print(f"[compounder] LLM error ({res.error}) — skipping")
        return 0

    parsed = extract_json(res.text)
    if not parsed:
        print(f"[compounder] no structured output (elapsed={elapsed}s) — skipping")
        if res.stderr_tail:
            print(f"[compounder] stderr: {res.stderr_tail[-500:]}")
        return 0

    (eng / "compounder_result.json").write_text(
        json.dumps({"ran_at": utcnow(), "elapsed_s": elapsed, "parsed": parsed}, indent=2),
        encoding="utf-8",
    )

    knowledge_added = parsed.get("knowledge_added", [])
    if knowledge_added:
        apply_knowledge(eng, knowledge_added)
    if parsed.get("methodology_updates"):
        apply_methodology_updates(eng, parsed["methodology_updates"])

    print(f"[compounder] done — {len(knowledge_added)} knowledge entries (elapsed={elapsed}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
