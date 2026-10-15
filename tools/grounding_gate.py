#!/usr/bin/env python3
"""
grounding_gate.py — the anti-hallucination gate.

SecHound's rule is that nothing is `confirmed` on a model's say-so. This gate
enforces the mechanical version of that: every claim a confirmed finding makes
must be traceable to a LOGGED observation — captured repro output, or a quote
that actually appears in the source it cites. A finding that was promoted to
`confirmed` with no logged evidence, or that cites a signal/quote/file:line that
does not exist, is flagged `ungrounded` (the vibe-confirmed case) and the gate
exits non-zero.

Two backings count as grounding:
  * runtime  — the claimed signal appears in `evidence.live_evidence` (the repro
               output verify_finding captured).
  * static   — a citation {quote, source} whose quote actually appears in the
               cited source file (catches hallucinated file:line / invented code).

A confirmed finding is `grounded` only if it carries at least one claim AND every
claim it makes is backed. Candidates are reported but not blocked.

    python3 tools/grounding_gate.py engagements/<id>        # scan an engagement
    python3 tools/grounding_gate.py --db findings_db.json   # scan the registry
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CONFIRMED = {"confirmed"}
BLOCK_VERDICT = "ungrounded"


# --------------------------------------------------------------------------
# Pure core
# --------------------------------------------------------------------------

def extract_claims(finding: dict) -> list[dict]:
    """Every checkable assertion the finding makes, as {kind, text, source}."""
    claims: list[dict] = []
    ev = finding.get("evidence") or {}
    for sig in ((ev.get("repro") or {}).get("expected_signals") or []):
        claims.append({"kind": "signal", "text": str(sig), "source": None})
    for cite in (ev.get("citations") or []):
        if isinstance(cite, dict) and cite.get("quote"):
            claims.append({"kind": "citation", "text": str(cite["quote"]),
                           "source": cite.get("source")})
    return claims


def _source_text(source: str | None, root: Path | None) -> str | None:
    if not source or root is None:
        return None
    path = source.split(":", 1)[0]            # drop :line suffix
    p = (root / path)
    try:
        return p.read_text(errors="replace") if p.is_file() else None
    except OSError:
        return None


def claim_grounded(claim: dict, transcript: str, root: Path | None) -> bool:
    text = claim["text"]
    if text and text in (transcript or ""):
        return True                            # runtime grounding
    src = _source_text(claim.get("source"), root)
    if src is not None and text in src:
        return True                            # static grounding
    return False


def classify_grounding(finding: dict, root: Path | None = None) -> tuple[str, list[dict]]:
    """Return (verdict, ungrounded_claims). verdict ∈ {grounded, ungrounded,
    not_confirmed}. Only confirmed findings can be `ungrounded` (blocking)."""
    status = finding.get("classification") or finding.get("status") or "candidate"
    transcript = (finding.get("evidence") or {}).get("live_evidence") or ""
    claims = extract_claims(finding)
    ungrounded = [c for c in claims if not claim_grounded(c, transcript, root)]

    if status not in CONFIRMED:
        return "not_confirmed", ungrounded
    if not claims:
        # confirmed but asserts nothing checkable — cannot be grounded
        return "ungrounded", [{"kind": "none", "text": "<no claims on a confirmed finding>",
                               "source": None}]
    return ("ungrounded" if ungrounded else "grounded"), ungrounded


# --------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------

def _load_findings(args) -> tuple[list[dict], Path | None]:
    if args.engagement:
        eng = Path(args.engagement)
        root = eng.resolve().parent.parent      # repo root-ish for citation reads
        fdir = eng / "findings"
        files = sorted(fdir.glob("*.json")) if fdir.is_dir() else []
        return [json.loads(f.read_text()) for f in files], Path.cwd()
    if args.db:
        data = json.loads(Path(args.db).read_text())
        rows = data if isinstance(data, list) else data.get("findings", [])
        return rows, Path.cwd()
    return [], None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="anti-hallucination grounding gate")
    ap.add_argument("engagement", nargs="?", help="engagement dir (scans findings/)")
    ap.add_argument("--db", help="scan a findings_db.json instead")
    ap.add_argument("--root", help="repo root for resolving citation sources (default: cwd)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    findings, default_root = _load_findings(args)
    root = Path(args.root) if args.root else default_root
    if not findings:
        print("[grounding] no findings to check", file=sys.stderr)
        return 0

    report, blocked = [], 0
    for f in findings:
        verdict, ungrounded = classify_grounding(f, root)
        row = {"id": f.get("id"), "status": f.get("classification") or f.get("status"),
               "verdict": verdict, "ungrounded_claims": ungrounded}
        report.append(row)
        if verdict == BLOCK_VERDICT:
            blocked += 1

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for r in report:
            mark = "✗" if r["verdict"] == BLOCK_VERDICT else ("·" if r["verdict"] == "not_confirmed" else "✓")
            print(f"{mark} {r['id']}: {r['verdict']}")
            for c in r["ungrounded_claims"]:
                print(f"    ungrounded {c['kind']}: {c['text'][:80]!r}")
        print(f"\n[grounding] {blocked} confirmed finding(s) ungrounded.")
    # Non-zero when a confirmed finding is ungrounded — usable as a CI/pipeline gate.
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
