"""Proves the depth lint: structural gaps and broken validator/tool wiring are
ERRORs; the real repo lints clean (dogfood). doc-only is a WARN, not a failure."""
from pathlib import Path

import skill_lint as sl

ROOT = Path(__file__).resolve().parent.parent

GOOD = """---
name: hunt-x
description: d
domain: web
---
# hunt-x
## When to load
k
## Neutralizing controls (invalidators — check, don't assume)
c — run python3 tools/tenant_diff.py ...
## Validation bar
prove it with tools/tenant_diff.py
## Known chains
z
"""


def test_good_skill_no_errors():
    errs = [i for i in sl.lint_skill("hunt-x", GOOD, ROOT / "tools")
            if i["severity"] == "ERROR"]
    assert errs == []


def test_missing_sections_and_frontmatter_error():
    bad = "---\nname: hunt-y\n---\n# hunt-y\n## Probes\nonly this\n"
    msgs = [i["msg"] for i in sl.lint_skill("hunt-y", bad, ROOT / "tools")]
    assert any("description" in m for m in msgs)
    assert any("when-to-load" in m for m in msgs)
    assert any("validation-bar" in m for m in msgs)


def test_nonexistent_tool_reference_errors(tmp_path):
    txt = GOOD.replace("tools/tenant_diff.py", "tools/does_not_exist.py")
    errs = sl.lint_skill("hunt-x", txt, tmp_path)   # empty tools dir
    assert any("does_not_exist" in e["msg"] for e in errs)


def test_is_doc_only():
    assert sl.is_doc_only("## Validation bar\njust prose, no probe\n## Known chains\n")
    assert not sl.is_doc_only("## Validation bar\nrun tools/mcp_probe.py\n")


def test_profile_bogus_validator_errors(tmp_path):
    pdir = tmp_path / "profiles" / "p"
    pdir.mkdir(parents=True)
    (pdir / "profile.yaml").write_text("name: p\nvalidators:\n  - no_such_tool\n")
    (tmp_path / "tools").mkdir()
    errs = sl.lint_profiles(tmp_path / "profiles", tmp_path / "tools")
    assert any("no_such_tool" in e["msg"] for e in errs)


def test_real_repo_lints_clean():
    errors = [i for i in sl.lint_repo(ROOT) if i["severity"] == "ERROR"]
    assert errors == [], f"repo has lint errors: {errors}"
