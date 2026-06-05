import sechound_lib as sl


def test_skill_index_nonempty_with_metadata():
    idx = sl.skill_index()
    assert len(idx) >= 15            # the shipped library
    ssrf = next((s for s in idx if s["name"] == "hunt-ssrf"), None)
    assert ssrf and ssrf["domain"] == "web" and ssrf["description"]


def test_load_skill_strips_frontmatter():
    body = sl.load_skill("hunt-ssrf")
    assert body and not body.lstrip().startswith("---")   # frontmatter removed
    assert "SSRF" in body


def test_load_skill_missing_returns_empty():
    assert sl.load_skill("hunt-does-not-exist") == ""


def test_skill_context_concatenates_and_caps():
    ctx = sl.skill_context(["hunt-ssrf", "hunt-idor", "hunt-ssrf"], cap=2)
    assert "### Skill: hunt-ssrf" in ctx and "### Skill: hunt-idor" in ctx
    assert ctx.count("### Skill:") == 2     # deduped


def test_profile_loads_skills_list():
    p = sl.load_profile("web-appsec")
    assert p and "hunt-injection" in p["skills"] and "hunt-idor" in p["skills"]
