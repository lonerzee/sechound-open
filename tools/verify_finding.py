#!/usr/bin/env python3
"""
verify_finding.py — the promotion gate: reproduce a candidate live, then
promote (confirmed) or demote based on whether the repro produces the evidence
it claims.

A finding declares a repro contract under `evidence.repro`:

    "evidence": {
      "repro": {
        "script": "repro.sh",                 # path (rel to engagement) or inline command
        "expected_signals": ["leaked", "200"],# ALL must appear in stdout to confirm
        "forbidden_signals": ["403"],         # NONE may appear (optional)
        "timeout": 60
      }
    }

The harness runs the script, asserts the signals, and writes
`verification_result.json` (consumed by critic.py). Cross-tenant / IDOR / BOLA
findings should drive a two-identity diff inside their script (see
tenant_diff.py) — a single-identity repro is not validation.

Usage:
    python3 tools/verify_finding.py <engagement_dir> [finding_id|all] [--skip-precheck]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sechound_lib import resolve_engagement_arg, utcnow
import findings_db


def _list_findings(eng: Path, target: str) -> list[Path]:
    fdir = eng / "findings"
    if not fdir.exists():
        return []
    js = sorted(fdir.glob("*.json"))
    if target == "all":
        return js
    matches = [p for p in js if target in p.stem]
    if not matches:
        sys.exit(f"no finding matching '{target}' under {fdir}")
    return matches


def _run_repro(eng: Path, repro: dict) -> tuple[bool, str, list[str]]:
    """Run the repro script. Returns (passed, output, missing_signals)."""
    script = repro.get("script", "")
    timeout = int(repro.get("timeout", 60))
    if not script:
        return False, "no repro.script declared", ["<no script>"]

    script_path = eng / script
    if script_path.exists():
        cmd = ["bash", str(script_path)]
    else:
        cmd = ["bash", "-c", script]  # treat as inline command

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(eng))
        output = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return False, f"repro timed out after {timeout}s", ["<timeout>"]
    except Exception as e:
        return False, f"repro failed to run: {e}", ["<error>"]

    expected = repro.get("expected_signals") or []
    forbidden = repro.get("forbidden_signals") or []
    missing = [s for s in expected if s not in output]
    present_forbidden = [s for s in forbidden if s in output]
    passed = not missing and not present_forbidden and bool(expected)
    if present_forbidden:
        missing += [f"forbidden:{s}" for s in present_forbidden]
    return passed, output, missing


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("engagement_dir", nargs="?", default=None)
    ap.add_argument("target", nargs="?", default="all", help="finding id substring or 'all'")
    ap.add_argument("--skip-precheck", action="store_true",
                    help="skip the duplicate-root-cause gate")
    args = ap.parse_args()

    eng = resolve_engagement_arg(args.engagement_dir)
    findings = _list_findings(eng, args.target)
    if not findings:
        print(f"[verify] no findings under {eng}/findings/ — nothing to do")
        return 0

    db = findings_db.load_db()
    findings_new: list[dict] = []

    for fpath in findings:
        try:
            finding = json.loads(fpath.read_text())
        except Exception as e:
            print(f"[verify] skip {fpath.name}: unreadable ({e})")
            continue

        fid = finding.get("id") or fpath.stem

        # Pre-test dedup gate: don't re-validate a root cause already tracked.
        if not args.skip_precheck:
            dup = findings_db.check_duplicate(db, finding)
            if dup and dup != fid:
                print(f"[verify] {fid}: root cause already tracked as {dup} — skipping "
                      "(use --skip-precheck to override)")
                continue

        repro = ((finding.get("evidence") or {}).get("repro")) or {}
        if not repro:
            print(f"[verify] {fid}: no evidence.repro contract — leaving as "
                  f"{finding.get('status', 'candidate')!r}")
            continue

        passed, output, missing = _run_repro(eng, repro)
        evidence_tail = output[-4000:]

        if passed:
            finding["classification"] = finding["status"] = "confirmed"
            finding.setdefault("evidence", {})["live_evidence"] = evidence_tail
            finding["verified_at"] = utcnow()
            print(f"[verify] {fid}: CONFIRMED — all expected signals present")
            findings_new.append(finding)
        else:
            finding["classification"] = finding["status"] = "unverifiable"
            finding["verify_failure"] = {
                "ran_at": utcnow(), "missing_signals": missing,
                "output_tail": evidence_tail[-1000:],
            }
            print(f"[verify] {fid}: UNVERIFIABLE — missing {missing} — demoted to 'unverifiable'")

        fpath.write_text(json.dumps(finding, indent=2))
        # Sync the verdict back to the registry so report/browse stay consistent
        # with the engagement finding file.
        if finding.get("id"):
            findings_db.upsert(finding)

    (eng / "verification_result.json").write_text(json.dumps({
        "ran_at": utcnow(), "engagement": str(eng),
        "findings_new": findings_new,
    }, indent=2))
    print(f"[verify] done — {len(findings_new)} confirmed → verification_result.json "
          "(run critic next)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
