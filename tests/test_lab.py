"""Proves the bundled vulnerable lab actually plants each class (vuln route) with
a working safe contrast — the live substrate the DAST templates and benchmark
depend on. Starts the stdlib server in a background thread on an ephemeral port."""
import http.client
import importlib.util
import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("vuln_target", ROOT / "examples" / "vulnerable_target.py")
vt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vt)

import dast  # from tools/ (conftest puts it on path)


@pytest.fixture(scope="module")
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), vt.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address
    srv.shutdown()


def _req(addr, method, path, token, body=None):
    conn = http.client.HTTPConnection(*addr, timeout=5)
    headers = {"X-Token": token}
    data = None
    if body is not None:
        data = json.dumps(body)
        headers["Content-Type"] = "application/json"
    conn.request(method, path, body=data, headers=headers)
    r = conn.getresponse()
    out = r.read().decode()
    conn.close()
    return r.status, out


# ---- IDOR ----------------------------------------------------------------

def test_idor_vuln_vs_safe(server):
    # bob reads alice's object: vuln route leaks, safe route 403s
    assert _req(server, "GET", "/api/objects/1", "tokB")[0] == 200
    assert "SECRET_ALICE" in _req(server, "GET", "/api/objects/1", "tokB")[1]
    assert _req(server, "GET", "/api/secure/objects/1", "tokB")[0] == 403


# ---- mass assignment (API3) ---------------------------------------------

def test_mass_assignment_vuln_binds_privileged_field(server):
    s, b = _req(server, "POST", "/api/profile", "tokB", {"name": "x", "role": "admin"})
    assert s == 200 and '"role": "admin"' in b          # over-bound

def test_mass_assignment_safe_strips_privileged_field(server):
    s, b = _req(server, "POST", "/api/secure/profile", "tokB", {"name": "x", "role": "admin"})
    assert s == 200 and json.loads(b)["profile"]["role"] == "member"   # not admin


# ---- BFLA (API5) ---------------------------------------------------------

def test_bfla_vuln_lets_member_hit_admin(server):
    s, b = _req(server, "GET", "/api/admin/stats", "tokB")   # bob = member
    assert s == 200 and "revenue" in b

def test_bfla_safe_denies_member(server):
    assert _req(server, "GET", "/api/secure/admin/stats", "tokB")[0] == 403
    assert _req(server, "GET", "/api/secure/admin/stats", "tokA")[0] == 200   # admin ok


# ---- unbounded consumption ----------------------------------------------

def test_unbounded_vuln_vs_capped(server):
    assert json.loads(_req(server, "GET", "/api/expand?n=5000", "tokB")[1])["count"] == 5000
    assert json.loads(_req(server, "GET", "/api/secure/expand?n=5000", "tokB")[1])["count"] == vt.MAX_EXPAND


# ---- dast matcher over a real body --------------------------------------

def test_dast_match_logic():
    assert dast._match(200, '{"role": "admin"}', {"status": [200], "words": ['"role": "admin"']})
    assert not dast._match(403, "forbidden", {"status": [200]})
    assert not dast._match(200, "ok", {"negative_status": [200]})
