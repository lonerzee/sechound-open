#!/usr/bin/env python3
"""
skill_lint.py — the depth lint for hunt skills.

The check that would have caught shipping 16 prose-only skills: it asserts every
hunt skill is structurally complete AND that the mechanism it claims actually
exists. Specifically:

  ERROR (fails the lint):
    * missing frontmatter name/description/domain
    * missing a "When to load", a controls/invalidators, or a "Validation bar"
      section (heading matched by substring, so wording can vary)
    * a profile `validators:` entry with no tools/<name>.py
    * a skill body that references a tools/<name>.py which does not exist

  WARN (reported, does not fail):
    * a hunt skill not listed in any profile
    * a "doc-only" skill: its Validation bar names no tools/*.py probe and no
      dast template — fine for methodology-only classes, flagged so coverage is
      visible instead of silently shallow.

    python3 tools/skill_lint.py            # lint skills/ + profiles/
    python3 tools/skill_lint.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED_FM = ["name", "description", "domain"]
# (label, list of acceptable heading substrings) — ERROR if none present
REQUIRED_SECTIONS = [
    ("when-to-load", ["when to load"]),
    ("controls", ["control", "invalidator", "what to check"]),
    ("validation-bar", ["validation bar"]),
]
TOOL_REF = re.compile(r"tools/([a-z_][a-z0-9_]*)\.py")


def _frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip()
    return fm


def _headings(text: str) -> list[str]:
    return [h.lower() for h in re.findall(r"^##\s+(.*)$", text, re.M)]


def lint_skill(name: str, text: str, tools_dir: Path) -> list[dict]:
    issues: list[dict] = []
    fm = _frontmatter(text)
    for key in REQUIRED_FM:
        if not fm.get(key):
            issues.append({"severity": "ERROR", "skill": name,
                           "msg": f"missing frontmatter '{key}'"})
    headings = _headings(text)
    for label, needles in REQUIRED_SECTIONS:
        if not any(any(n in h for n in needles) for h in headings):
            issues.append({"severity": "ERROR", "skill": name,
                           "msg": f"missing required section ({label})"})
    for ref in set(TOOL_REF.findall(text)):
        if not (tools_dir / f"{ref}.py").is_file():
            issues.append({"severity": "ERROR", "skill": name,
                           "msg": f"references tools/{ref}.py which does not exist"})
    return issues


def is_doc_only(text: str) -> bool:
    """True if the Validation bar references no concrete probe tool."""
    m = re.search(r"##\s+Validation bar.*?(?=\n##\s|\Z)", text, re.S | re.I)
    section = m.group(0) if m else ""
    return "tools/" not in section


def lint_profiles(profiles_dir: Path, tools_dir: Path) -> list[dict]:
    issues = []
    for pf in sorted(profiles_dir.glob("*/profile.yaml")):
        text = pf.read_text()
        vblock = re.search(r"validators:\s*\n((?:\s*-\s*\S+.*\n?)*)", text)
        if vblock:
            # match the validator name only at list-item start (not hyphenated
            # words inside trailing # comments, e.g. rug-pull / two-identity)
            for v in re.findall(r"^\s*-\s*([a-z_][a-z0-9_]*)", vblock.group(1), re.M):
                if not (tools_dir / f"{v}.py").is_file():
                    issues.append({"severity": "ERROR", "skill": pf.parent.name,
                                   "msg": f"profile validator '{v}' has no tools/{v}.py"})
    return issues


def _profiled_skills(profiles_dir: Path) -> set[str]:
    out = set()
    for pf in profiles_dir.glob("*/profile.yaml"):
        out.update(re.findall(r"-\s*(hunt-[a-z0-9-]+)", pf.read_text()))
    return out


def lint_repo(root: Path) -> list[dict]:
    skills_dir, tools_dir, profiles_dir = root / "skills", root / "tools", root / "profiles"
    issues: list[dict] = []
    profiled = _profiled_skills(profiles_dir)
    for sk in sorted(skills_dir.glob("hunt-*/SKILL.md")):
        name = sk.parent.name
        if name == "hunt-template":
            continue
        text = sk.read_text()
        issues += lint_skill(name, text, tools_dir)
        if name not in profiled:
            issues.append({"severity": "WARN", "skill": name,
                           "msg": "not listed in any profile"})
        if is_doc_only(text):
            issues.append({"severity": "WARN", "skill": name,
                           "msg": "doc-only (Validation bar names no tools/*.py probe)"})
    issues += lint_profiles(profiles_dir, tools_dir)
    return issues


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="hunt-skill depth lint")
    ap.add_argument("--root", default=".", help="repo root")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="fail on WARN too")
    args = ap.parse_args(argv)

    issues = lint_repo(Path(args.root))
    errors = [i for i in issues if i["severity"] == "ERROR"]
    warns = [i for i in issues if i["severity"] == "WARN"]

    if args.json:
        print(json.dumps(issues, indent=2))
    else:
        for i in issues:
            print(f"  [{i['severity']}] {i['skill']}: {i['msg']}")
        print(f"\n[skill-lint] {len(errors)} error(s), {len(warns)} warning(s)")
    return 1 if (errors or (args.strict and warns)) else 0


if __name__ == "__main__":
    sys.exit(main())
