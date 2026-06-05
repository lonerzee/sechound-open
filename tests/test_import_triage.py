import importlib
import json


def _fresh(monkeypatch, tmp_path):
    monkeypatch.setenv("SECHOUND_DB", str(tmp_path / "db.json"))
    import findings_db
    importlib.reload(findings_db)
    return findings_db


SARIF = {
    "version": "2.1.0",
    "runs": [{
        "tool": {"driver": {"name": "Semgrep", "rules": [
            {"id": "sqli", "properties": {"security-severity": "9.1", "tags": ["CWE-89"]}}
        ]}},
        "results": [
            {"ruleId": "sqli", "level": "error",
             "message": {"text": "SQL injection in query builder"},
             "locations": [{"physicalLocation": {
                 "artifactLocation": {"uri": "src/db.py"}, "region": {"startLine": 12}}}]},
            # duplicate root cause (same rule+location) -> should collapse
            {"ruleId": "sqli", "level": "error",
             "message": {"text": "SQL injection in query builder"},
             "locations": [{"physicalLocation": {
                 "artifactLocation": {"uri": "src/db.py"}, "region": {"startLine": 12}}}]},
        ],
    }],
}


def test_sarif_maps_fields(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    import import_sarif
    importlib.reload(import_sarif)
    found = import_sarif.results_from_sarif(SARIF, None, "web")
    f = found[0]
    assert f["severity"] == "CRITICAL"       # 9.1 security-severity
    assert f["cwe"] == "CWE-89"
    assert f["source"] == "sarif:semgrep"
    assert f["files"] == ["src/db.py:12"]
    assert f["domain"] == "web"


def test_sarif_import_dedups(monkeypatch, tmp_path):
    db = _fresh(monkeypatch, tmp_path)
    import import_sarif
    importlib.reload(import_sarif)
    for f in import_sarif.results_from_sarif(SARIF, None, "web"):
        db.upsert(f)
    # two identical results collapse to one finding
    assert len(db.load_db()) == 1


def test_triage_extract_json():
    import triage
    importlib.reload(triage)
    out = triage._extract_json('noise {"verdict": "likely_false_positive", "reason": "x"} tail')
    assert out["verdict"] == "likely_false_positive"


def test_triage_extract_array():
    import triage
    importlib.reload(triage)
    arr = triage._extract_array('prose ```json\n[{"id":"A","verdict":"likely_true_positive"},'
                                '{"id":"B","verdict":"needs_verification"}]\n``` tail')
    assert [x["id"] for x in arr] == ["A", "B"]


def test_triage_batch_maps_by_id(monkeypatch):
    import triage
    importlib.reload(triage)
    monkeypatch.setattr(triage.llm, "complete", lambda *a, **k: type(
        "R", (), {"error": "", "text": '[{"id":"X","verdict":"likely_false_positive","reason":"fixture"}]'})())
    out = triage._triage_batch([{"id": "X", "title": "t"}], "checklist", "m", 5, False)
    assert out["X"]["verdict"] == "likely_false_positive"
