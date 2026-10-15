"""Proves the miner aggregates disclosure records by class with per-pattern
citations and renders a well-formed, cited hunt skill."""
import json
from pathlib import Path

import skill_miner as sm

ROOT = Path(__file__).resolve().parent.parent
CORPUS = json.loads((ROOT / "profiles" / "disclosures" / "sample_disclosures.json").read_text())


def test_mine_groups_by_class_with_citations():
    mined = sm.mine(CORPUS)
    assert set(mined) == {"ssrf", "idor", "prompt-injection"}
    # a sink pattern carries the report ids that cite it
    ssrf_sinks = mined["ssrf"]["sink"]
    assert all(isinstance(ids, list) and ids for ids in ssrf_sinks.values())
    # every ssrf report id shows up somewhere in the aggregation
    report_ids = {r["id"] for r in mined["ssrf"]["_reports"]}
    assert report_ids == {"RPT-0001", "RPT-0002"}


def test_render_skill_has_sections_and_citations():
    mined = sm.mine(CORPUS)
    md = sm.render_skill("idor", mined["idor"])
    for section in ["## When to load", "## Where this class lives",
                    "## Neutralizing controls", "## Probes", "## Validation bar",
                    "## Known chains", "## Cited reports"]:
        assert section in md
    assert "[RPT-0003]" in md and "[RPT-0004]" in md          # patterns are cited
    assert md.startswith("---\nname: hunt-idor")


def test_cli_writes_and_refuses_overwrite(tmp_path, capsys):
    corpus = ROOT / "profiles" / "disclosures" / "sample_disclosures.json"
    assert sm.main(["--corpus", str(corpus), "--out", str(tmp_path), "--class", "ssrf"]) == 0
    skill = tmp_path / "hunt-ssrf" / "SKILL.md"
    assert skill.is_file() and "[RPT-0001]" in skill.read_text()
    # second run without --force must not clobber
    sm.main(["--corpus", str(corpus), "--out", str(tmp_path), "--class", "ssrf"])
    assert "skip" in capsys.readouterr().out
