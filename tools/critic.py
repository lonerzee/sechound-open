#!/usr/bin/env python3
"""
critic.py — adversarial critic phase, runs between verify and compound.

Reads `<engagement>/verification_result.json`, invokes the Claude CLI with the
critic system prompt (prompts/critic.md) once per new finding, parses the
verdict, and APPLIES demotions directly to the finding files. The critic is
non-advisory and biased toward demotion: a false retraction is treated as
exactly as costly as a false positive, so a calibration alarm fires if it
demotes too large a fraction.

Usage:
    python3 tools/critic.py <engagement_dir> [--model MODEL]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sechound_lib import resolve_engagement_arg, sechound_model, utcnow
import llm


def _upsert_escalation_queue(eng: Path, entry: dict) -> None:
    queue_path = eng / "escalation_queue.json"
    try:
        existing = json.loads(queue_path.read_text()) if queue_path.exists() else []
    except Exception:
        existing = []
    if entry["finding_id"] not in {e.get("finding_id") for e in existing}:
        existing.append(entry)
        queue_path.write_text(json.dumps(existing, indent=2))
        print(f"[critic] ESCALATION REQUIRED: {entry['finding_id']} ({entry['severity']}) queued")


def _remove_from_escalation_queue(eng: Path, finding_id: str) -> None:
    queue_path = eng / "escalation_queue.json"
    if not queue_path.exists():
        return
    try:
        existing = json.loads(queue_path.read_text())
        updated = [e for e in existing if e.get("finding_id") != finding_id]
        if len(updated) != len(existing):
            queue_path.write_text(json.dumps(updated, indent=2))
    except Exception:
        pass


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("engagement_dir", nargs="?", default=None)
    ap.add_argument("--model", default=sechound_model("expensive_tasks"))
    ap.add_argument("--timeout", type=int, default=420)
    args = ap.parse_args()

    eng = resolve_engagement_arg(args.engagement_dir)
    verify_path = eng / "verification_result.json"
    if not verify_path.exists():
        print(f"[critic] no verification_result.json at {verify_path} — skipping")
        return 0

    try:
        verification_result = json.loads(verify_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[critic] failed to parse verification_result.json: {e}")
        return 0

    findings_new = verification_result.get("findings_new") or []
    if not findings_new:
        print("[critic] no findings_new — skipping")
        return 0

    usable, reason = llm.available()
    if not usable:
        print(f"[critic] LLM provider unavailable ({reason}) — skipping")
        return 0
    if not llm.is_agentic():
        print(f"[critic] WARNING: provider '{llm.provider()}' is completion-only; the critic "
              "cannot grep the codebase to verify citations. Verdicts will be weaker. "
              "Use SECHOUND_LLM=claude or an agentic command backend for full fidelity.")

    prompt = (Path(__file__).resolve().parent.parent / "prompts" / "critic.md").read_text(encoding="utf-8")
    service_tested = verification_result.get("service_tested", "")

    per_finding_results: list[dict] = []
    first_demotion_written = False

    for finding_dict in findings_new:
        finding_id = finding_dict.get("id") or finding_dict.get("finding_id")

        # Merge reasoning_trace stamped on disk by the verifier (absent from
        # verification_result.json).
        if finding_id:
            fpath_disk = eng / "findings" / f"{finding_id}.json"
            if fpath_disk.exists():
                try:
                    disk_data = json.loads(fpath_disk.read_text())
                    if disk_data.get("reasoning_trace") and not finding_dict.get("reasoning_trace"):
                        finding_dict["reasoning_trace"] = disk_data["reasoning_trace"]
                except Exception:
                    pass

        reasoning_trace = finding_dict.get("reasoning_trace") or []
        trace_section = ""
        if reasoning_trace:
            trace_section = (
                f"\n\nReasoning trace from verifier (challenge each step):\n"
                f"```json\n{json.dumps(reasoning_trace, indent=2)}\n```"
            )

        user_input = (
            f"Engagement: {eng}\nService: {service_tested}\n"
            f"Apply the FP checklist and verifier-specific probes to the following "
            f"finding. Output ONLY the JSON specified.\n\n"
            f"```json\n{json.dumps(finding_dict, indent=2)}\n```{trace_section}"
        )

        res = llm.complete(prompt, user_input, model=args.model,
                           timeout=args.timeout, tools="Bash,Read")
        if res.error:
            print(f"[critic] LLM error for {finding_id}: {res.error}")
            per_finding_results.append({"finding_id": finding_id, "error": res.error, "ran_at": utcnow()})
            continue

        parsed = extract_json(res.text)
        per_finding_results.append({
            "finding_id": finding_id, "ran_at": utcnow(), "elapsed_s": res.elapsed_s,
            "exit_code": res.exit_code, "stderr_tail": res.stderr_tail,
            "raw_output": res.text, "parsed": parsed,
        })

        if not parsed:
            print(f"[critic] WARNING: could not parse critic output for {finding_id}")
            continue

        verdict = parsed.get("critic_verdict") or "unknown"
        final = parsed.get("final_classification") or "unknown"
        resolved_id = parsed.get("finding_id") or finding_id

        # Step-level challenge: any failed reasoning-trace step is blocking,
        # regardless of the top-level verdict.
        trace_challenges = parsed.get("reasoning_trace_challenges") or []
        failed_steps = [c for c in trace_challenges if c.get("verdict") == "fail"]
        if failed_steps and verdict == "uphold":
            verdict = "demote_to_candidate"
            if not final or final == "confirmed":
                final = "candidate (code-only)"
            print(f"[critic] reasoning_trace step failure(s) on {resolved_id} — overriding to demote")
        print(f"[critic] finding={resolved_id} verdict={verdict} final={final}")

        # Upheld HIGH/CRITICAL findings must be escalated before COMPLETE.
        if verdict == "uphold" and resolved_id:
            fpath_check = eng / "findings" / f"{resolved_id}.json"
            if fpath_check.exists():
                try:
                    f_data = json.loads(fpath_check.read_text())
                    if (f_data.get("severity") or "").upper() in ("HIGH", "CRITICAL"):
                        _upsert_escalation_queue(eng, {
                            "finding_id": resolved_id, "title": f_data.get("title", ""),
                            "severity": (f_data.get("severity") or "").upper(),
                            "service": f_data.get("service", ""),
                            "endpoint": f_data.get("endpoint", ""), "added_at": utcnow(),
                        })
                    for parent_id in (f_data.get("chains_on") or []):
                        _remove_from_escalation_queue(eng, parent_id)
                        print(f"[critic] escalation satisfied: {parent_id} chained by {resolved_id}")
                except Exception:
                    pass

        if verdict and verdict != "uphold":
            if not first_demotion_written:
                (eng / "critic_demotion.flag").write_text(json.dumps(
                    {"verdict": verdict, "final": final, "finding_id": resolved_id, "ran_at": utcnow()},
                    indent=2))
                first_demotion_written = True

            if resolved_id:
                fpath = eng / "findings" / f"{resolved_id}.json"
                if fpath.exists():
                    try:
                        finding = json.loads(fpath.read_text())
                        prior = finding.get("classification")
                        was_confirmed = "confirmed" in (prior or "").lower()
                        finding["classification"] = final
                        finding["status"] = final
                        if was_confirmed:
                            finding["critic_challenged_confirmed"] = True
                            finding["critic_challenged_confirmed_at"] = utcnow()
                            print(f"[critic] CONFIRMED finding challenged: {resolved_id} — flagged for review")
                        entry: dict = {
                            "ran_at": utcnow(), "prior_classification": prior,
                            "new_classification": final, "critic_verdict": verdict,
                            "blocking_concerns": parsed.get("blocking_concerns", []),
                            "fp_checklist": parsed.get("fp_checklist", {}),
                            "actions_required": parsed.get("actions_required", []),
                        }
                        if failed_steps:
                            entry["blocking_concerns"] = entry["blocking_concerns"] + [
                                f"reasoning_trace step '{c.get('step')}' failed: {c.get('challenge', '')}"
                                for c in failed_steps
                            ]
                            entry["reasoning_trace_challenges"] = trace_challenges
                        finding.setdefault("critic_demotion_history", []).append(entry)
                        fpath.write_text(json.dumps(finding, indent=2))
                        print(f"[critic] APPLIED demotion to {resolved_id}: {prior!r} -> {final!r}")
                        _remove_from_escalation_queue(eng, resolved_id)
                    except Exception as e:
                        print(f"[critic] failed to apply demotion to {fpath}: {e}")
                else:
                    print(f"[critic] finding file not found, demotion deferred: {fpath}")

    (eng / "critic_result.json").write_text(json.dumps(per_finding_results, indent=2))

    # Calibration alarm: >40% demotion rate may mean the critic prompt is
    # miscalibrated — a single bad rule can silently wipe real findings.
    demoted_ids = [
        r["finding_id"] for r in per_finding_results
        if (r.get("parsed") or {}).get("critic_verdict") not in (None, "uphold", "unknown")
        and r.get("parsed") is not None
    ]
    total = len([r for r in per_finding_results if r.get("parsed") is not None])
    if total >= 3 and len(demoted_ids) / total > 0.40:
        rate = len(demoted_ids) / total
        (eng / "critic_calibration_warning.json").write_text(json.dumps({
            "generated_at": utcnow(), "demotion_rate": round(rate, 3),
            "demoted_count": len(demoted_ids), "total_processed": total,
            "demoted_ids": demoted_ids,
            "message": (f"Critic demoted {len(demoted_ids)}/{total} findings "
                        f"({round(rate*100)}%) — exceeds 40% threshold. Review critic.md "
                        "before accepting these demotions."),
        }, indent=2))
        print(f"\n[critic] CALIBRATION WARNING: {len(demoted_ids)}/{total} demoted "
              f"({round(rate*100)}% > 40%) — see critic_calibration_warning.json")

    # Cascade: demote any finding that chains_on a demoted finding so a chain
    # report never ships with a broken leg. Loops to handle A->B->C.
    if demoted_ids:
        findings_dir = eng / "findings"
        if findings_dir.exists():
            newly_demoted = set(demoted_ids)
            while newly_demoted:
                next_round: set[str] = set()
                for fpath in sorted(findings_dir.glob("*.json")):
                    try:
                        f = json.loads(fpath.read_text())
                    except Exception:
                        continue
                    overlap = [d for d in (f.get("chains_on") or []) if d in newly_demoted]
                    if not overlap:
                        continue
                    prior = f.get("classification", "")
                    if "candidate" in prior or "retract" in prior:
                        continue
                    f["classification"] = f["status"] = "candidate (code-only)"
                    f.setdefault("critic_demotion_history", []).append({
                        "ran_at": utcnow(), "prior_classification": prior,
                        "new_classification": "candidate (code-only)",
                        "critic_verdict": "cascade_demotion",
                        "blocking_concerns": [f"Chain dependency {d!r} was demoted" for d in overlap],
                        "actions_required": [f"Re-validate chain component(s) {overlap} before re-confirming."],
                    })
                    fpath.write_text(json.dumps(f, indent=2))
                    print(f"[critic] CASCADE: demoted {fpath.stem} (chains on {overlap})")
                    next_round.add(fpath.stem)
                newly_demoted = next_round

    return 0


if __name__ == "__main__":
    sys.exit(main())
