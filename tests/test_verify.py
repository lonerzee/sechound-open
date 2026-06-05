import importlib
import json


def _setup(monkeypatch, tmp_path, repro):
    monkeypatch.setenv("SECHOUND_DB", str(tmp_path / "db.json"))
    eng = tmp_path / "eng"
    (eng / "findings").mkdir(parents=True)
    finding = {"id": "SH-API-0001", "title": "test", "service": "api",
               "severity": "HIGH", "status": "candidate",
               "evidence": {"repro": repro}}
    (eng / "findings" / "SH-API-0001.json").write_text(json.dumps(finding))
    import verify_finding
    importlib.reload(verify_finding)
    monkeypatch.setattr("sys.argv", ["verify", str(eng), "all", "--skip-precheck"])
    verify_finding.main()
    return json.loads((eng / "findings" / "SH-API-0001.json").read_text()), eng


def test_repro_pass_confirms(monkeypatch, tmp_path):
    finding, eng = _setup(monkeypatch, tmp_path, {
        "script": "echo 'LEAKED 200'", "expected_signals": ["LEAKED", "200"]})
    assert finding["status"] == "confirmed"
    vr = json.loads((eng / "verification_result.json").read_text())
    assert len(vr["findings_new"]) == 1


def test_missing_signal_demotes(monkeypatch, tmp_path):
    finding, _ = _setup(monkeypatch, tmp_path, {
        "script": "echo 'nothing here'", "expected_signals": ["LEAKED"]})
    assert finding["status"] == "unverifiable"
    assert "LEAKED" in finding["verify_failure"]["missing_signals"]


def test_forbidden_signal_demotes(monkeypatch, tmp_path):
    finding, _ = _setup(monkeypatch, tmp_path, {
        "script": "echo 'LEAKED 403'", "expected_signals": ["LEAKED"],
        "forbidden_signals": ["403"]})
    assert finding["status"] == "unverifiable"


def test_imported_finding_repro_refused_without_allow_exec(monkeypatch, tmp_path):
    # An imported (untrusted-source) finding's bash repro must NOT auto-run.
    import importlib
    import json as _json
    monkeypatch.setenv("SECHOUND_DB", str(tmp_path / "db.json"))
    eng = tmp_path / "eng"
    (eng / "findings").mkdir(parents=True)
    finding = {"id": "SH-API-0001", "title": "t", "domain": "web", "status": "candidate",
               "source": "sarif:semgrep",
               "evidence": {"repro": {"script": "echo PWNED", "expected_signals": ["PWNED"]}}}
    (eng / "findings" / "SH-API-0001.json").write_text(_json.dumps(finding))
    import verify_finding
    importlib.reload(verify_finding)
    monkeypatch.setattr("sys.argv", ["verify", str(eng), "all", "--skip-precheck"])
    verify_finding.main()
    after = _json.loads((eng / "findings" / "SH-API-0001.json").read_text())
    assert after["status"] == "candidate"          # not run, not confirmed


def test_exec_allowed_logic():
    import verify_finding, importlib
    importlib.reload(verify_finding)
    assert verify_finding._exec_allowed({"source": "manual"}, False)[0] is True
    assert verify_finding._exec_allowed({"source": "sarif:nuclei"}, False)[0] is False
    assert verify_finding._exec_allowed({"source": "sarif:nuclei"}, True)[0] is True


def test_verdict_syncs_to_registry(monkeypatch, tmp_path):
    # After verify confirms a finding, the central registry must reflect it so
    # report/browse don't show a stale 'candidate'.
    import importlib
    _setup(monkeypatch, tmp_path, {"script": "echo 'LEAKED 200'",
                                   "expected_signals": ["LEAKED"]})
    import findings_db
    importlib.reload(findings_db)
    row = [f for f in findings_db.load_db() if f["id"] == "SH-API-0001"][0]
    assert row["status"] == "confirmed"
