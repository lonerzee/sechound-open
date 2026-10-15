#!/usr/bin/env python3
"""
mcp_probe.py — the falsifier for MCP (Model Context Protocol) findings.

A hunt-mcp playbook tells you WHERE to look; this proves it. It speaks MCP
JSON-RPC and runs the checks a `confirmed` MCP finding requires — the same role
`tenant_diff.py` plays for web IDOR. Reachability or an accepted call is never
the finding; an OBSERVED cross-principal effect is.

Checks (each has a pure classifier, unit-tested network-free):

  workspace-idor   Call a tool/resource naming principal A's object while
                   authenticated as principal B. Verdict cross_workspace_leak
                   only when B actually receives A's data.
  rug-pull         Snapshot tool definitions, re-list, diff. A tool whose
                   description/schema changed after approval is a rug_pull.
  result-injection Inspect a tool RESULT for instruction-like / role-marker
                   content that would be concatenated into model context
                   unlabeled. Exposure is review-grade: full exploitation needs
                   a model-in-the-loop, which this tool does not fake.
  cred-passthrough Call a tool with a host/URL arg pointing at an unintended
                   host; with --oob-host (a collector you control) confirm
                   whether the server's injected credential actually egressed.

Transport is pluggable (HTTP streamable JSON-RPC by default, or an injected
callable for stdio/tests). Only cross_workspace_leak and rug_pull are
confirm-grade (non-zero exit), so they can drive a verify_finding repro
contract's `expected_signals`.

    python3 tools/mcp_probe.py workspace-idor \
        --url https://mcp.example.test/mcp \
        --header-a "Authorization: Bearer A" --header-b "Authorization: Bearer B" \
        --tool get_resource --args '{"workspace_id":"W1","resource_id":"R1"}'

    python3 tools/mcp_probe.py rug-pull --url https://mcp.example.test/mcp \
        --header-a "Authorization: Bearer A" --snapshot before.json   # then, later:
    python3 tools/mcp_probe.py rug-pull --url ... --compare before.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
import urllib.request
from typing import Callable

# A transport takes a JSON-RPC request dict and returns the response dict.
Transport = Callable[[dict], dict]

CONFIRM_GRADE = {"cross_workspace_leak", "rug_pull"}


# --------------------------------------------------------------------------
# Pure classifiers — no I/O, unit-tested.
# --------------------------------------------------------------------------

def call_outcome(resp: dict) -> tuple[bool, str]:
    """Normalize a JSON-RPC/MCP tools/call response to (ok, text).

    ok is False on a JSON-RPC error OR an MCP result flagged isError. text is
    the serialized result content (what the model would actually see).
    """
    if not isinstance(resp, dict):
        return False, ""
    if "error" in resp and resp["error"] is not None:
        return False, json.dumps(resp["error"], sort_keys=True)
    result = resp.get("result")
    if isinstance(result, dict):
        if result.get("isError"):
            return False, _content_text(result)
        return True, _content_text(result)
    if result is None:
        return False, ""
    return True, json.dumps(result, sort_keys=True)


def _content_text(result: dict) -> str:
    """Flatten MCP content blocks (or a raw resource) to comparable text."""
    content = result.get("content")
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text") or block.get("uri") or
                             json.dumps(block, sort_keys=True))
            else:
                parts.append(str(block))
        return "\n".join(parts)
    # resources/read shape, or anything else: serialize deterministically.
    for key in ("contents", "text"):
        if key in result:
            return json.dumps(result[key], sort_keys=True)
    return json.dumps(result, sort_keys=True)


def classify_workspace_idor(ok_a: bool, text_a: str, ok_b: bool, text_b: str) -> str:
    """A = owner (baseline, must succeed). B = attacker in another workspace."""
    if not ok_a:
        return "inconclusive"          # baseline failed — can't judge isolation
    if ok_b:
        if text_b.strip() and text_b == text_a:
            return "cross_workspace_leak"   # B got exactly A's object
        if text_b.strip():
            return "possible_leak"          # B got 2xx-equiv, different body → review
        return "scoped_empty"               # B succeeded but saw nothing of A's
    return "isolation_holds"           # B was denied while A succeeded → good


def tool_def_fingerprint(tools: list[dict]) -> dict[str, str]:
    """Map tool name -> stable hash of its model-facing surface (desc+schema)."""
    out: dict[str, str] = {}
    for t in tools or []:
        if not isinstance(t, dict) or "name" not in t:
            continue
        surface = json.dumps(
            {"description": t.get("description", ""),
             "inputSchema": t.get("inputSchema", {})},
            sort_keys=True,
        )
        out[t["name"]] = hashlib.sha256(surface.encode()).hexdigest()
    return out


def classify_rug_pull(before: dict[str, str], after: dict[str, str]) -> str:
    """Compare two tool-definition fingerprints taken around an approval."""
    for name, h in after.items():
        if name in before and before[name] != h:
            return "rug_pull"          # an approved tool silently redefined
    if set(after) - set(before):
        return "new_tool_added"        # new tool appeared post-approval (review)
    return "stable"


# Instruction-like patterns that should never ride *unlabeled* inside a tool
# result the host concatenates into the model's context.
_INJECTION_MARKERS = [
    re.compile(r"ignore (all )?(previous|prior|above) (instructions|context)", re.I),
    re.compile(r"\b(system|assistant|developer)\s*:", re.I),
    re.compile(r"<\s*/?\s*(system|instructions?)\s*>", re.I),
    re.compile(r"you (are|must|should) now\b", re.I),
    re.compile(r"\[\[.*?\]\]"),                      # bracketed directive markers
    re.compile(r"\bappend\b.*\bto (the|your) (answer|result|response)\b", re.I),
]


def classify_tool_result_injection(text: str) -> str:
    """Flag instruction-like content in a tool result. Review-grade only."""
    if text and any(p.search(text) for p in _INJECTION_MARKERS):
        return "result_injection_exposure"
    return "clean"


# --------------------------------------------------------------------------
# I/O layer — the MCP JSON-RPC client.
# --------------------------------------------------------------------------

def http_transport(url: str, headers: list[str], timeout: int) -> Transport:
    hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
    for h in headers:
        if ":" in h:
            k, _, v = h.partition(":")
            hdrs[k.strip()] = v.strip()

    def _send(req: dict) -> dict:
        data = json.dumps(req).encode()
        request = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as r:
                body = r.read().decode(errors="replace")
        except urllib.error.HTTPError as e:                      # noqa: F821
            body = e.read().decode(errors="replace")
        except Exception as e:  # network/transport error → JSON-RPC-shaped error
            return {"error": {"code": -32000, "message": f"transport: {e}"}}
        # Streamable HTTP may return SSE framing ("data: {...}"); take last JSON.
        for line in reversed(body.splitlines()):
            line = line.strip()
            if line.startswith("data:"):
                line = line[5:].strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"error": {"code": -32700, "message": "non-JSON response"}}
    return _send


def stdio_transport(command: str, timeout: int = 30) -> Transport:
    """Transport for a stdio MCP server: spawn it and exchange newline-delimited
    JSON-RPC. Many real MCP servers run this way (e.g. `npx some-mcp-server`)."""
    proc = subprocess.Popen(
        shlex.split(command), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, bufsize=1)

    def _send(req: dict) -> dict:
        if proc.poll() is not None:
            return {"error": {"code": -32000, "message": "server exited"}}
        try:
            proc.stdin.write(json.dumps(req) + "\n")
            proc.stdin.flush()
        except BrokenPipeError:
            return {"error": {"code": -32000, "message": "broken pipe"}}
        # read until a line parses as this request's JSON-RPC response
        for _ in range(100):
            line = proc.stdout.readline()
            if not line:
                return {"error": {"code": -32000, "message": "no response"}}
            line = line.strip()
            if line.startswith("{"):
                try:
                    resp = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if resp.get("id") == req.get("id") or "result" in resp or "error" in resp:
                    return resp
        return {"error": {"code": -32000, "message": "no matching response"}}
    return _send


class MCPClient:
    """Minimal MCP JSON-RPC client over a pluggable transport."""

    def __init__(self, transport: Transport):
        self._t = transport
        self._id = 0

    def _rpc(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        return self._t({"jsonrpc": "2.0", "id": self._id,
                        "method": method, "params": params or {}})

    def initialize(self) -> dict:
        return self._rpc("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "sechound-mcp-probe", "version": "0"},
        })

    def tools_list(self) -> list[dict]:
        return (self._rpc("tools/list").get("result") or {}).get("tools", [])

    def tools_call(self, name: str, arguments: dict) -> dict:
        return self._rpc("tools/call", {"name": name, "arguments": arguments})

    def resources_read(self, uri: str) -> dict:
        return self._rpc("resources/read", {"uri": uri})


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def check_workspace_idor(client_a: MCPClient, client_b: MCPClient, *,
                         tool: str | None, args: dict | None,
                         resource_uri: str | None) -> dict:
    def _invoke(c: MCPClient) -> tuple[bool, str]:
        if resource_uri:
            return call_outcome(c.resources_read(resource_uri))
        return call_outcome(c.tools_call(tool, args or {}))

    ok_a, text_a = _invoke(client_a)
    ok_b, text_b = _invoke(client_b)
    verdict = classify_workspace_idor(ok_a, text_a, ok_b, text_b)
    return {"check": "workspace-idor", "verdict": verdict,
            "target": resource_uri or f"tool:{tool}",
            "owner_ok": ok_a, "attacker_ok": ok_b,
            "bodies_identical": text_a == text_b and bool(text_a.strip())}


def check_rug_pull(before: dict[str, str], after: dict[str, str]) -> dict:
    verdict = classify_rug_pull(before, after)
    changed = [n for n in after if n in before and before[n] != after[n]]
    return {"check": "rug-pull", "verdict": verdict, "changed_tools": changed,
            "added_tools": sorted(set(after) - set(before))}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _emit(result: dict, as_json: bool) -> int:
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"CHECK:   {result.get('check')}")
        print(f"VERDICT: {result['verdict']}")
        for k, v in result.items():
            if k not in ("check", "verdict"):
                print(f"  {k}: {v}")
    return 2 if result["verdict"] in CONFIRM_GRADE else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MCP finding falsifier")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def _common(p):
        p.add_argument("--url", help="MCP streamable-HTTP endpoint")
        p.add_argument("--timeout", type=int, default=30)
        p.add_argument("--json", action="store_true")

    pi = sub.add_parser("workspace-idor", help="two-principal cross-workspace diff")
    _common(pi)
    pi.add_argument("--header-a", action="append", default=[], help="owner header (repeatable)")
    pi.add_argument("--header-b", action="append", default=[], help="attacker header (repeatable)")
    pi.add_argument("--stdio-a", help="owner stdio MCP command (instead of --url)")
    pi.add_argument("--stdio-b", help="attacker stdio MCP command (instead of --url)")
    pi.add_argument("--tool", help="tool name to call")
    pi.add_argument("--args", default="{}", help="JSON arguments naming A's object")
    pi.add_argument("--resource", help="resource URI to read (instead of a tool)")

    pr = sub.add_parser("rug-pull", help="snapshot/compare tool definitions")
    _common(pr)
    pr.add_argument("--header-a", action="append", default=[])
    pr.add_argument("--stdio", help="stdio MCP command (instead of --url)")
    pr.add_argument("--snapshot", help="write current tool fingerprints here")
    pr.add_argument("--compare", help="compare current fingerprints against this file")

    args = ap.parse_args(argv)

    if args.cmd == "workspace-idor":
        if args.stdio_a and args.stdio_b:
            ta = stdio_transport(args.stdio_a, args.timeout)
            tb = stdio_transport(args.stdio_b, args.timeout)
        elif args.url:
            ta = http_transport(args.url, args.header_a, args.timeout)
            tb = http_transport(args.url, args.header_b, args.timeout)
        else:
            sys.exit("supply --url (+ --header-a/--header-b) or --stdio-a/--stdio-b")
        ca, cb = MCPClient(ta), MCPClient(tb)
        ca.initialize(); cb.initialize()
        res = check_workspace_idor(
            ca, cb, tool=args.tool,
            args=json.loads(args.args), resource_uri=args.resource)
        return _emit(res, args.json)

    if args.cmd == "rug-pull":
        if args.stdio:
            c = MCPClient(stdio_transport(args.stdio, args.timeout))
        elif args.url:
            c = MCPClient(http_transport(args.url, args.header_a, args.timeout))
        else:
            sys.exit("supply --url or --stdio")
        c.initialize()
        current = tool_def_fingerprint(c.tools_list())
        if args.snapshot:
            with open(args.snapshot, "w") as fh:
                json.dump(current, fh, indent=2)
            print(f"snapshot written: {args.snapshot} ({len(current)} tools)")
            return 0
        if args.compare:
            with open(args.compare) as fh:
                before = json.load(fh)
            return _emit(check_rug_pull(before, current), args.json)
        sys.exit("rug-pull needs --snapshot (first run) or --compare <file>")

    return 0


if __name__ == "__main__":
    sys.exit(main())
