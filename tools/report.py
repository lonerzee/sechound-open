#!/usr/bin/env python3
"""
report.py — list findings and export reports from the registry.

    python3 tools/report.py                       # table of all findings
    python3 tools/report.py --status confirmed    # filter
    python3 tools/report.py --format md  > report.md
    python3 tools/report.py --format sarif > findings.sarif   # GitHub code scanning

SARIF lets confirmed findings drop straight into GitHub's Security tab.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import findings_db

_SARIF_LEVEL = {"CRITICAL": "error", "HIGH": "error", "MEDIUM": "warning",
                "LOW": "note", "INFO": "note"}


def _component(f: dict) -> str:
    return findings_db.component_of(f) or (f.get("domain") or "")


def _filter(db: list[dict], status: str | None, severity: str | None,
            component: str | None, domain: str | None) -> list[dict]:
    out = db
    if status:
        out = [f for f in out if (f.get("status") or "").lower() == status.lower()]
    if severity:
        out = [f for f in out if (f.get("severity") or "").upper() == severity.upper()]
    if component:
        out = [f for f in out if findings_db.component_of(f) == component.lower()]
    if domain:
        out = [f for f in out if (f.get("domain") or "").lower() == domain.lower()]
    return out


def _table(findings: list[dict]) -> str:
    if not findings:
        return "(no findings match)"
    rows = [f"{f.get('id',''):<16} {f.get('severity',''):<9} {f.get('status',''):<14} "
            f"{_component(f)[:14]:<14} {(f.get('title') or '')[:56]}"
            for f in findings]
    header = f"{'ID':<16} {'SEVERITY':<9} {'STATUS':<14} {'COMPONENT':<14} TITLE"
    return header + "\n" + "-" * len(header) + "\n" + "\n".join(rows)


def _markdown(findings: list[dict]) -> str:
    lines = ["# Findings report", "",
             f"Total: **{len(findings)}**", "",
             "| ID | Severity | Status | Service | Title |",
             "|---|---|---|---|---|"]
    for f in findings:
        lines.append(f"| {f.get('id','')} | {f.get('severity','')} | {f.get('status','')} "
                     f"| {f.get('service','')} | {f.get('title','')} |")
    for f in findings:
        lines += ["", f"## {f.get('id','')} — {f.get('title','')}", "",
                  f"- **Severity:** {f.get('severity','')}",
                  f"- **Status:** {f.get('status','')}",
                  f"- **Domain:** {f.get('domain','—')}",
                  f"- **Category:** {f.get('category','—')}{(' (' + f['cwe'] + ')') if f.get('cwe') else ''}",
                  f"- **Component:** {_component(f) or '—'}",
                  f"- **Location:** {findings_db.location_of(f) or '—'}",
                  f"- **Files:** {', '.join(f.get('files', [])) or '—'}", "",
                  f.get("summary", "")]
        ev = (f.get("evidence") or {}).get("live_evidence")
        if ev:
            lines += ["", "<details><summary>Evidence</summary>", "",
                      "```", str(ev)[:2000], "```", "</details>"]
    return "\n".join(lines)


def _sarif(findings: list[dict]) -> str:
    rules, results = {}, []
    for f in findings:
        rule_id = f.get("category") or findings_db.component_of(f) or "finding"
        rules.setdefault(rule_id, {"id": rule_id, "name": rule_id,
                                   "shortDescription": {"text": f"SecHound: {rule_id}"}})
        loc = []
        cites = f.get("files") or ([f["location"]] if f.get("location") else [])
        for cite in cites:
            path, _, line = cite.partition(":")
            region = {"startLine": int(line)} if line.isdigit() else {}
            loc.append({"physicalLocation": {
                "artifactLocation": {"uri": path},
                **({"region": region} if region else {})}})
        results.append({
            "ruleId": rule_id,
            "level": _SARIF_LEVEL.get((f.get("severity") or "").upper(), "warning"),
            "message": {"text": f"[{f.get('id','')}] {f.get('title','')} — {f.get('summary','')}"},
            "locations": loc or [{"physicalLocation": {"artifactLocation": {"uri": "unknown"}}}],
            "properties": {"severity": f.get("severity"), "status": f.get("status"),
                           "id": f.get("id")},
        })
    return json.dumps({
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "SecHound", "informationUri":
                  "https://github.com/lonerzee/sechound-open",
                  "rules": list(rules.values())}}, "results": results}],
    }, indent=2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("engagement_dir", nargs="?", default=None, help="(unused; registry is global)")
    ap.add_argument("--status")
    ap.add_argument("--severity")
    ap.add_argument("--component", help="filter by component (or legacy 'service')")
    ap.add_argument("--service", help="alias for --component")
    ap.add_argument("--domain", help="filter by domain (web/cloud/binary/...)")
    ap.add_argument("--format", choices=["table", "md", "sarif"], default="table")
    args = ap.parse_args()

    findings = _filter(findings_db.load_db(), args.status, args.severity,
                       args.component or args.service, args.domain)
    findings.sort(key=lambda f: ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"].index(
        (f.get("severity") or "INFO").upper()) if (f.get("severity") or "INFO").upper()
        in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO") else 99)

    if args.format == "md":
        print(_markdown(findings))
    elif args.format == "sarif":
        print(_sarif(findings))
    else:
        print(_table(findings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
