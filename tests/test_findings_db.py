import importlib


def _fresh_db(monkeypatch, tmp_path):
    monkeypatch.setenv("SECHOUND_DB", str(tmp_path / "db.json"))
    import findings_db
    importlib.reload(findings_db)
    return findings_db


def test_insert_assigns_id(monkeypatch, tmp_path):
    db = _fresh_db(monkeypatch, tmp_path)
    fid, action = db.upsert({"title": "SSRF in webhook", "service": "api", "severity": "HIGH"})
    assert action == "inserted"
    assert fid == "SH-API-0001"
    assert len(db.load_db()) == 1


def test_ids_increment_per_service(monkeypatch, tmp_path):
    db = _fresh_db(monkeypatch, tmp_path)
    db.upsert({"title": "bug one", "service": "api", "severity": "LOW"})
    fid2, _ = db.upsert({"title": "completely different two", "service": "api", "severity": "LOW"})
    assert fid2 == "SH-API-0002"


def test_root_cause_dedup_same_endpoint(monkeypatch, tmp_path):
    db = _fresh_db(monkeypatch, tmp_path)
    a, _ = db.upsert({"title": "IDOR here", "service": "api",
                      "endpoint": "GET /api/objects/{id}", "severity": "HIGH"})
    b, action = db.upsert({"title": "totally different wording", "service": "api",
                           "endpoint": "GET /api/objects/{id}", "severity": "HIGH"})
    assert action == "duplicate"
    assert a == b
    assert len(db.load_db()) == 1


def test_update_in_place_by_id(monkeypatch, tmp_path):
    db = _fresh_db(monkeypatch, tmp_path)
    fid, _ = db.upsert({"title": "x", "service": "api", "severity": "LOW"})
    _, action = db.upsert({"id": fid, "title": "x", "service": "api", "severity": "CRITICAL"})
    assert action == "updated"
    assert db.load_db()[0]["severity"] == "CRITICAL"


def test_cross_scanner_dedup_by_location(monkeypatch, tmp_path):
    # Two scanners flag the same file:line with different wording -> one finding.
    db = _fresh_db(monkeypatch, tmp_path)
    a, _ = db.upsert({"title": "semgrep: tainted query", "domain": "web",
                      "location": "src/db.py:12", "severity": "HIGH", "source": "sarif:semgrep"})
    b, action = db.upsert({"title": "codeql: SQL built from user input", "domain": "web",
                           "location": "src/db.py:12", "severity": "HIGH", "source": "sarif:codeql"})
    assert action == "duplicate" and a == b
    assert len(db.load_db()) == 1


def test_component_alias_and_id_prefix(monkeypatch, tmp_path):
    db = _fresh_db(monkeypatch, tmp_path)
    fid, _ = db.upsert({"title": "x", "component": "auth-svc", "severity": "LOW"})
    assert fid == "SH-AUTHSVC-0001"               # component drives the prefix
    assert db.component_of({"service": "legacy"}) == "legacy"   # legacy alias still read


def test_finding_does_not_dedup_against_itself(monkeypatch, tmp_path):
    db = _fresh_db(monkeypatch, tmp_path)
    fid, _ = db.upsert({"title": "IDOR x", "service": "api",
                        "endpoint": "GET /api/objects/{id}", "severity": "HIGH"})
    # Re-checking the SAME finding (by id) must not report it as its own duplicate.
    rows = db.load_db()
    same = next(f for f in rows if f["id"] == fid)
    assert db.check_duplicate(rows, same) is None


def test_deterministic_sort(monkeypatch, tmp_path):
    db = _fresh_db(monkeypatch, tmp_path)
    out = db.sorted_findings([{"id": "SH-B-1"}, {"id": "SH-A-1"}])
    assert [f["id"] for f in out] == ["SH-A-1", "SH-B-1"]
