"""Proves mcp_probe against the live vulnerable MCP lab over real transports:
HTTP (two bearer-token workspaces) and stdio (subprocess, MCP_WORKSPACE env)."""
import importlib.util
import socket
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("vuln_mcp", ROOT / "examples" / "vulnerable_mcp.py")
vm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vm)

import mcp_probe
from mcp_probe import (MCPClient, check_result_injection, check_workspace_idor,
                      http_transport, stdio_transport)

SCRIPT = str(ROOT / "examples" / "vulnerable_mcp.py")


@pytest.fixture(scope="module")
def http_url():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), vm.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    host, port = srv.server_address
    yield f"http://{host}:{port}/mcp"
    srv.shutdown()


# ---- HTTP transport: workspace IDOR leak vs secure contrast --------------

def test_http_workspace_idor_leak(http_url):
    ca = MCPClient(http_transport(http_url, ["Authorization: Bearer tokA"], 10))  # W1 owner
    cb = MCPClient(http_transport(http_url, ["Authorization: Bearer tokB"], 10))  # W2 attacker
    ca.initialize(); cb.initialize()
    res = check_workspace_idor(ca, cb, tool="get_resource",
                               args={"resource_id": "r1"}, resource_uri=None)
    assert res["verdict"] == "cross_workspace_leak"     # W2 read W1's resource


def test_http_secure_tool_holds(http_url):
    ca = MCPClient(http_transport(http_url, ["Authorization: Bearer tokA"], 10))
    cb = MCPClient(http_transport(http_url, ["Authorization: Bearer tokB"], 10))
    ca.initialize(); cb.initialize()
    res = check_workspace_idor(ca, cb, tool="get_resource_secure",
                               args={"resource_id": "r1"}, resource_uri=None)
    assert res["verdict"] == "isolation_holds"


def test_http_result_injection_exposure(http_url):
    c = MCPClient(http_transport(http_url, ["Authorization: Bearer tokA"], 10))
    c.initialize()
    res = check_result_injection(c, "fetch_note", {"note_id": "n1"})
    assert res["verdict"] == "result_injection_exposure"   # note carried instructions


# ---- stdio transport: real subprocess MCP server -------------------------

def _stdio(ws: str):
    return stdio_transport(f"env MCP_WORKSPACE={ws} {sys.executable} {SCRIPT} --stdio", 10)


def test_stdio_transport_calls_tool():
    c = MCPClient(_stdio("W1"))
    assert "protocolVersion" in (c.initialize().get("result") or {})
    ok, text = mcp_probe.call_outcome(c.tools_call("get_resource", {"resource_id": "r1"}))
    assert ok and "SECRET_W1" in text


def test_stdio_workspace_idor_leak():
    ca = MCPClient(_stdio("W1")); cb = MCPClient(_stdio("W2"))
    ca.initialize(); cb.initialize()
    leak = check_workspace_idor(ca, cb, tool="get_resource",
                                args={"resource_id": "r1"}, resource_uri=None)
    hold = check_workspace_idor(MCPClient(_stdio("W1")), MCPClient(_stdio("W2")),
                                tool="get_resource_secure",
                                args={"resource_id": "r1"}, resource_uri=None)
    assert leak["verdict"] == "cross_workspace_leak"
    assert hold["verdict"] == "isolation_holds"
