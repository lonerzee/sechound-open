"""Proves the grounding gate blocks vibe-confirmed findings: a confirmed finding
whose claimed signal/quote is not in captured evidence or cited source is
flagged ungrounded; a properly-backed one passes; candidates are not blocked."""
from pathlib import Path

import grounding_gate as gg


def _confirmed(**ev):
    return {"id": "X", "classification": "confirmed", "evidence": ev}


# ---- runtime grounding ----------------------------------------------------

def test_signal_present_in_live_evidence_is_grounded():
    f = _confirmed(repro={"expected_signals": ["cross_tenant_leak"]},
                   live_evidence="... VERDICT: cross_tenant_leak ...")
    assert gg.classify_grounding(f)[0] == "grounded"


def test_signal_absent_from_evidence_is_ungrounded():
    f = _confirmed(repro={"expected_signals": ["cross_tenant_leak"]},
                   live_evidence="VERDICT: isolation_holds")
    verdict, ungrounded = gg.classify_grounding(f)
    assert verdict == "ungrounded" and ungrounded[0]["text"] == "cross_tenant_leak"


def test_confirmed_with_no_evidence_is_ungrounded():
    f = {"id": "X", "classification": "confirmed", "evidence": {}}
    assert gg.classify_grounding(f)[0] == "ungrounded"       # vibe-confirmed


# ---- static (citation) grounding -----------------------------------------

def test_citation_quote_in_real_source_is_grounded(tmp_path):
    (tmp_path / "app.py").write_text("def f():\n    return OBJECTS.get(id)  # no owner check\n")
    f = _confirmed(citations=[{"quote": "OBJECTS.get(id)", "source": "app.py"}])
    assert gg.classify_grounding(f, root=tmp_path)[0] == "grounded"


def test_hallucinated_citation_is_ungrounded(tmp_path):
    (tmp_path / "app.py").write_text("def f():\n    return safe_lookup(id)\n")
    f = _confirmed(citations=[{"quote": "OBJECTS.get(id)  # no owner check",
                               "source": "app.py"}])     # quote not in file
    assert gg.classify_grounding(f, root=tmp_path)[0] == "ungrounded"


# ---- scope of enforcement -------------------------------------------------

def test_candidate_not_blocked():
    f = {"id": "X", "status": "candidate", "evidence": {}}
    assert gg.classify_grounding(f)[0] == "not_confirmed"


def test_mixed_backing_requires_all_claims_grounded(tmp_path):
    (tmp_path / "a.py").write_text("OBJECTS.get(id)\n")
    f = _confirmed(
        repro={"expected_signals": ["cross_tenant_leak"]},
        live_evidence="VERDICT: cross_tenant_leak",
        citations=[{"quote": "NONEXISTENT", "source": "a.py"}])   # one bad claim
    assert gg.classify_grounding(f, root=tmp_path)[0] == "ungrounded"
