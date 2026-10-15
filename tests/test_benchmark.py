"""Proves the benchmark scoring math and that a full autostart run detects every
planted bug with no false positives (detection_rate 1.0)."""
import importlib.util
import socket
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import benchmark

_ROOT = Path(__file__).resolve().parent.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _ROOT / "examples" / f"{name}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def _serve(handler):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


# ---- port + identity guards (dry-run MED) --------------------------------

def test_port_in_use_detects_listener():
    srv = _serve(_load("vulnerable_mcp").Handler)
    try:
        assert benchmark._port_in_use(srv.server_address[1]) is True
        assert benchmark._port_in_use(1) is False      # nothing on port 1
    finally:
        srv.shutdown()


def test_lab_identity_checks_reject_wrong_server():
    mcp = _serve(_load("vulnerable_mcp").Handler)
    web = _serve(_load("vulnerable_target").Handler)
    try:
        mcp_url = f"http://127.0.0.1:{mcp.server_address[1]}/mcp"
        web_url = f"http://127.0.0.1:{web.server_address[1]}"
        assert benchmark._verify_mcp_lab(mcp_url) is True
        assert benchmark._verify_web_lab(web_url) is True
        # cross-checks must FAIL (the dry-run's wrong-server scenario)
        assert benchmark._verify_mcp_lab(web_url) is False
        assert benchmark._verify_web_lab(mcp_url + "/nope") is False
    finally:
        mcp.shutdown(); web.shutdown()


# ---- pure scoring ---------------------------------------------------------

def test_score_counts_tp_fn_fp_tn():
    results = [
        {"class": "idor", "kind": "positive", "passed": True},
        {"class": "idor", "kind": "positive", "passed": False},   # missed bug
        {"class": "idor", "kind": "negative", "passed": True},    # correctly clean
        {"class": "mcp", "kind": "negative", "passed": False},    # false positive
    ]
    sc = benchmark.score(results)
    assert sc["true_positives"] == 1 and sc["false_negatives"] == 1
    assert sc["true_negatives"] == 1 and sc["false_positives"] == 1
    assert sc["detection_rate"] == 0.5
    assert sc["per_class"]["idor"] == {"passed": 2, "total": 3}


# ---- live autostart integration ------------------------------------------

def test_autostart_full_detection():
    # starts both bundled labs, runs every probe, requires a perfect score
    rc = benchmark.main(["--autostart", "--min-rate", "1.0"])
    assert rc == 0        # non-zero would mean a planted bug went undetected
