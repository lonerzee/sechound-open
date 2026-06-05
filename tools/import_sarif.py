#!/usr/bin/env python3
"""
import_sarif.py — pull existing scanner output into the registry.

SARIF is the lingua franca: semgrep, CodeQL, nuclei, Trivy, grype, gitleaks,
checkov, and many others emit it. Import normalizes each result into a finding
(de-duplicated by root cause on the way in), so a 4,000-hit scan collapses and
becomes triage-able by the LLM (`tools/triage.py`).

    python3 tools/import_sarif.py semgrep.sarif
    python3 tools/import_sarif.py *.sarif --domain web --tool semgrep
    nuclei -u https://t -json | ...                 # (nuclei also has -sarif)

Imported findings land as `candidate`, `source=sarif:<tool>`. Nothing is marked
confirmed — that needs the verifier.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import findings_db

# SARIF result.level -> our severity (fallback; many tools also set a rank/score)
_LEVEL_SEV = {"error": "HIGH", "warning": "MEDIUM", "note": "LOW", "none": "INFO"}
# security-severity (SARIF property, 0-10) -> severity
def _sev_from_score(score: float) -> str:
    return ("CRITICAL" if score >= 9 else "HIGH" if score >= 7
            else "MEDIUM" if score >= 4 else "LOW" if score > 0 else "INFO")


def _tool_name(run: dict) -> str:
    return (((run.get("tool") or {}).get("driver") or {}).get("name") or "scanner").lower()


def _rule_index(run: dict) -> dict:
    rules = ((run.get("tool") or {}).get("driver") or {}).get("rules") or []
    idx = {}
    for r in rules:
        idx[r.get("id")] = r
    return idx


def _location(result: dict) -> tuple[str, list[str]]:
    locs = result.get("locations") or []
    files = []
    primary = ""
    for loc in locs:
        phys = loc.get("physicalLocation") or {}
        uri = ((phys.get("artifactLocation") or {}).get("uri")) or ""
        line = (phys.get("region") or {}).get("startLine")
        if uri:
            cite = f"{uri}:{line}" if line else uri
            files.append(cite)
            if not primary:
                primary = cite
    return primary, files


def _severity(result: dict, rule: dict) -> str:
    # Prefer the numeric security-severity if present (semgrep/CodeQL set it).
    for src in (result.get("properties") or {}, (rule.get("properties") or {})):
        score = src.get("security-severity")
        if score is not None:
            try:
                return _sev_from_score(float(score))
            except (TypeError, ValueError):
                pass
    return _LEVEL_SEV.get((result.get("level") or rule.get("defaultConfiguration", {}).get("level") or "warning"), "MEDIUM")


def _cwe(rule: dict) -> str:
    for tag in ((rule.get("properties") or {}).get("tags") or []):
        if isinstance(tag, str) and tag.upper().startswith("CWE-"):
            return tag.upper()
    return ""


def results_from_sarif(doc: dict, tool_override: str | None, domain: str | None) -> list[dict]:
    out = []
    for run in doc.get("runs", []):
        tool = tool_override or _tool_name(run)
        rules = _rule_index(run)
        for res in run.get("results", []):
            rule_id = res.get("ruleId") or (res.get("rule") or {}).get("id") or "finding"
            rule = rules.get(rule_id, {})
            msg = (res.get("message") or {}).get("text") or rule_id
            primary, files = _location(res)
            title = f"{rule_id}: {msg.strip()[:120]}"
            out.append({
                "title": title,
                "severity": _severity(res, rule),
                "domain": domain or "",
                "category": rule_id,
                "cwe": _cwe(rule),
                "summary": msg.strip()[:500],
                "status": "candidate",
                "location": primary,
                "files": files,
                "source": f"sarif:{tool}",
            })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="one or more SARIF files")
    ap.add_argument("--tool", help="override tool name (else read from SARIF)")
    ap.add_argument("--domain", help="tag all imported findings with this domain")
    args = ap.parse_args()

    total = inserted = dup = 0
    for fp in args.files:
        try:
            doc = json.loads(Path(fp).read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[import] skip {fp}: {e}", file=sys.stderr)
            continue
        findings = results_from_sarif(doc, args.tool, args.domain)
        for f in findings:
            total += 1
            _, action = findings_db.upsert(f)
            if action == "duplicate":
                dup += 1
            else:
                inserted += 1
    print(f"[import] {total} result(s): {inserted} new, {dup} collapsed as duplicates "
          f"(root-cause dedup). Next: python3 tools/triage.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
