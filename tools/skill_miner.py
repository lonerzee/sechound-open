#!/usr/bin/env python3
"""
skill_miner.py — turn a corpus of disclosed reports into CITED hunt skills.

Hand-written hunt skills encode one author's knowledge. This mines a corpus of
public disclosures and emits a hunt-skill playbook per vulnerability class where
every pattern — each sink, control, bypass, and chain — is attributed to the
report(s) it came from, so the skill is auditable instead of asserted. That
auditability (patterns traceable to real reports) is the point.

Corpus is a JSON list of records (see profiles/disclosures/sample_disclosures.json):

    {"id","url","vuln_class","severity","title","sink","control","bypass","chain"}

    python3 tools/skill_miner.py --corpus profiles/disclosures/sample_disclosures.json \
        --out /tmp/mined                       # write skills/hunt-<class>/SKILL.md
    python3 tools/skill_miner.py --corpus ... --class ssrf --dry-run   # print one

By default it refuses to overwrite an existing skill (so it never clobbers a
hand-written one); pass --force to replace.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

FIELDS = ["sink", "control", "bypass", "chain"]
KEYWORDS = {  # seed triggers per class; the class name itself is always included
    "ssrf": "SSRF, outbound HTTP, webhook URL, URL fetch, metadata IP, callback",
    "idor": "IDOR, BOLA, cross-tenant, object id, ownership, findById",
    "prompt-injection": "prompt injection, indirect injection, jailbreak, tool abuse, system prompt",
}


# --------------------------------------------------------------------------
# Pure core
# --------------------------------------------------------------------------

def mine(records: list[dict]) -> dict[str, dict]:
    """Group records by vuln_class; for each field, collect distinct patterns
    with the list of report ids that cite them."""
    by_class: dict[str, dict] = {}
    for rec in records:
        cls = rec.get("vuln_class")
        if not cls:
            continue
        agg = by_class.setdefault(cls, {f: defaultdict(list) for f in FIELDS})
        agg.setdefault("_reports", [])
        rid = rec.get("id", "?")
        agg["_reports"].append({"id": rid, "url": rec.get("url", ""),
                                "title": rec.get("title", ""),
                                "severity": rec.get("severity", "")})
        for f in FIELDS:
            val = (rec.get(f) or "").strip()
            if val:
                agg[f][val].append(rid)
    return by_class


def _bullets(field_map: dict[str, list[str]]) -> str:
    lines = []
    for pattern, rids in field_map.items():
        cites = " ".join(f"[{r}]" for r in rids)
        lines.append(f"- {pattern}  {cites}")
    return "\n".join(lines) if lines else "- (none in corpus)"


def render_skill(cls: str, agg: dict) -> str:
    kw = KEYWORDS.get(cls, cls.replace("-", " "))
    reports = agg.get("_reports", [])
    refs = "\n".join(f"- [{r['id']}] {r['title']} ({r['severity']}) — {r['url']}"
                     for r in reports)
    return f"""---
name: hunt-{cls}
description: Mined hunt playbook for {cls} — patterns attributed to disclosed reports.
domain: web
---

# hunt-{cls}

Mined from {len(reports)} disclosed report(s). Every pattern below is attributed
to the report(s) it came from — verify against the citation before relying on it.

## When to load
{cls}, {kw}

## Where this class lives
Sink families seen across the cited reports:
{_bullets(agg["sink"])}

## Neutralizing controls (invalidators — check, don't assume)
Controls that neutralized (or should have neutralized) the cited instances:
{_bullets(agg["control"])}

## Probes
Bypasses that defeated the control in the cited reports — adapt, keep benign:
{_bullets(agg["bypass"])}

## Validation bar
`confirmed` requires an OBSERVED effect for this class — not a reflected payload
or the target merely accepting input. Prove the sink actually fired (out-of-band
callback, cross-identity read, or the chain's next step), then file.

## Known chains
{_bullets(agg["chain"])}

## Cited reports
{refs}
"""


# --------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="mine disclosed reports into cited hunt skills")
    ap.add_argument("--corpus", required=True, help="JSON list of disclosure records")
    ap.add_argument("--out", default="skills", help="output skills dir (default: skills)")
    ap.add_argument("--class", dest="cls", help="only this vuln_class")
    ap.add_argument("--dry-run", action="store_true", help="print, don't write")
    ap.add_argument("--force", action="store_true", help="overwrite existing SKILL.md")
    args = ap.parse_args(argv)

    records = json.loads(Path(args.corpus).read_text())
    mined = mine(records)
    if args.cls:
        mined = {k: v for k, v in mined.items() if k == args.cls}
    if not mined:
        sys.exit("no matching classes in corpus")

    written = 0
    for cls, agg in sorted(mined.items()):
        md = render_skill(cls, agg)
        if args.dry_run:
            print(md)
            continue
        dest = Path(args.out) / f"hunt-{cls}" / "SKILL.md"
        if dest.exists() and not args.force:
            print(f"[miner] skip {dest} (exists; --force to overwrite)")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(md)
        written += 1
        print(f"[miner] wrote {dest} ({len(agg.get('_reports', []))} reports cited)")
    if not args.dry_run:
        print(f"\n[miner] {written} skill(s) written to {args.out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
