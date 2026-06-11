import orchestrate
import tenant_diff


# ---- orchestrate JSON extraction -----------------------------------------

def test_extract_fenced_and_brace():
    text = (
        "preamble\n```json\n{\"a\": 1}\n```\n"
        "loose {\"b\": 2} and an array [1,2,3]"
    )
    objs = orchestrate.extract_all_json(text)
    assert {"a": 1} in objs
    assert {"b": 2} in objs
    assert [1, 2, 3] in objs


def test_is_finding_requires_title_plus_two():
    assert orchestrate._is_finding(
        {"title": "x", "severity": "HIGH", "service": "api"}) is True
    assert orchestrate._is_finding({"title": "x"}) is False           # title only
    assert orchestrate._is_finding({"severity": "HIGH"}) is False      # no title


def test_flatten_handles_wrapper_and_arrays():
    objs = [{"findings": [
        {"title": "a", "severity": "HIGH", "summary": "s"},
        {"not": "a finding"},
    ]}]
    out = orchestrate._flatten_findings(objs)
    assert len(out) == 1 and out[0]["title"] == "a"


# ---- tenant_diff verdict logic --------------------------------------------

def test_diff_cross_tenant_leak():
    assert tenant_diff.classify(200, "secret", 200, "secret") == "cross_tenant_leak"


def test_diff_isolation_holds():
    assert tenant_diff.classify(200, "secret", 403, "denied") == "isolation_holds"
    assert tenant_diff.classify(200, "secret", 404, "") == "isolation_holds"


def test_diff_possible_leak():
    # Both 2xx on the same resource URL, attacker got different non-empty content:
    # ambiguous → review-grade, not silently "safe".
    assert tenant_diff.classify(200, "A-data", 200, "B-data") == "possible_leak"


def test_diff_scoped_per_identity_empty_attacker_body():
    # Attacker got 2xx but no content → its own empty view, not a leak.
    assert tenant_diff.classify(200, "A-data", 200, "") == "scoped_per_identity"


def test_possible_leak_is_not_confirm_grade():
    # Only cross_tenant_leak auto-confirms; possible_leak must stay review-only.
    assert tenant_diff.classify(200, "A-data", 200, "B-data") != "cross_tenant_leak"


def test_diff_diverged():
    assert tenant_diff.classify(500, "err", 200, "ok") == "diverged"
