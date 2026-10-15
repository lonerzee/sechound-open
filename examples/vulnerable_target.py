#!/usr/bin/env python3
"""
vulnerable_target.py — a deliberately vulnerable HTTP service for the demo and
the benchmark.

Stdlib only, loopback only. Each class is planted in a VULNERABLE route with a
correctly-scoped SAFE route beside it, so a validator/template produces both a
positive and a negative verdict against the same app.

  IDOR / BOLA (API1)
    GET  /api/objects/{id}          VULN: no ownership check
    GET  /api/secure/objects/{id}   SAFE: 403 when not the caller's

  Mass assignment / BOPLA (API3)
    POST /api/profile               VULN: copies ALL body fields (role, is_admin)
    POST /api/secure/profile        SAFE: allow-lists name/email only

  Broken function-level authz / BFLA (API5)
    GET  /api/admin/stats           VULN: any valid token reaches admin data
    GET  /api/secure/admin/stats    SAFE: requires the admin role

  Unbounded consumption (LLM10-style denial-of-wallet)
    GET  /api/expand?n=             VULN: returns n units, uncapped (amplify)
    GET  /api/secure/expand?n=      SAFE: caps n at MAX_EXPAND

Identity is the `X-Token` header. Run:  python3 examples/vulnerable_target.py
Authorized for local testing of this app only.
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

HOST, PORT = "127.0.0.1", 8731

TOKENS = {"tokA": "alice", "tokB": "bob"}          # token -> user
ROLES = {"alice": "admin", "bob": "member"}        # user -> role
OBJECTS = {                                          # id -> object
    "1": {"owner": "alice", "data": "SECRET_ALICE_SSN_123-45-6789"},
    "2": {"owner": "bob", "data": "SECRET_BOB_SSN_987-65-4321"},
}
MAX_EXPAND = 100                                     # the SAFE cap

# Fields a client is allowed to set on its own profile. role/is_admin are NOT.
PROFILE_ALLOWED = {"name", "email", "bio"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _auth(self):
        return TOKENS.get(self.headers.get("X-Token", ""))

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0) or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode() or "{}")
        except (ValueError, UnicodeDecodeError):
            return {}

    # ---- GET ----------------------------------------------------------
    def do_GET(self) -> None:
        user = self._auth()
        if user is None:
            return self._send(401, {"error": "missing or invalid X-Token"})
        split = urlsplit(self.path)
        parts = split.path.strip("/").split("/")
        qs = parse_qs(split.query)

        # IDOR — VULNERABLE: no ownership check
        if parts[:2] == ["api", "objects"] and len(parts) == 3:
            obj = OBJECTS.get(parts[2])
            if not obj:
                return self._send(404, {"error": "not found"})
            return self._send(200, obj)   # BUG: returns regardless of obj["owner"]

        # IDOR — SAFE: object-level authorization
        if parts[:3] == ["api", "secure", "objects"] and len(parts) == 4:
            obj = OBJECTS.get(parts[3])
            if not obj:
                return self._send(404, {"error": "not found"})
            if obj["owner"] != user:
                return self._send(403, {"error": "forbidden"})
            return self._send(200, obj)

        # BFLA — VULNERABLE: any valid token reaches admin data
        if parts == ["api", "admin", "stats"]:
            return self._send(200, {"admin": True, "total_users": len(TOKENS),
                                    "revenue": "SECRET_MRR_428000"})

        # BFLA — SAFE: requires the admin role
        if parts == ["api", "secure", "admin", "stats"]:
            if ROLES.get(user) != "admin":
                return self._send(403, {"error": "forbidden: admin only"})
            return self._send(200, {"admin": True, "total_users": len(TOKENS),
                                    "revenue": "SECRET_MRR_428000"})

        # Unbounded consumption — VULNERABLE: uncapped amplification
        if parts == ["api", "expand"]:
            n = int((qs.get("n", ["1"])[0]) or 1)
            return self._send(200, {"units": ["x"] * n, "count": n})

        # Unbounded consumption — SAFE: capped
        if parts == ["api", "secure", "expand"]:
            n = min(int((qs.get("n", ["1"])[0]) or 1), MAX_EXPAND)
            return self._send(200, {"units": ["x"] * n, "count": n, "capped_at": MAX_EXPAND})

        return self._send(404, {"error": "no such route"})

    # ---- POST ---------------------------------------------------------
    def do_POST(self) -> None:
        user = self._auth()
        if user is None:
            return self._send(401, {"error": "missing or invalid X-Token"})
        parts = self.path.strip("/").split("/")
        body = self._body()

        # Mass assignment — VULNERABLE: copies EVERY field, including privileged ones
        if parts == ["api", "profile"]:
            profile = {"user": user}
            profile.update(body)          # BUG: role/is_admin/verified all land here
            return self._send(200, {"profile": profile})

        # Mass assignment — SAFE: allow-list
        if parts == ["api", "secure", "profile"]:
            profile = {"user": user, "role": ROLES.get(user, "member")}
            for k, v in body.items():
                if k in PROFILE_ALLOWED:
                    profile[k] = v
            return self._send(200, {"profile": profile})

        return self._send(404, {"error": "no such route"})


if __name__ == "__main__":
    try:
        srv = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        sys.stderr.write(f"[target] cannot bind {HOST}:{PORT} ({e}). A stale lab may "
                         f"be running there — probes would hit the WRONG server. "
                         f"Stop it: lsof -ti tcp:{PORT} | xargs kill\n")
        sys.exit(1)
    print(f"[target] vulnerable demo app on http://{HOST}:{PORT} (Ctrl-C to stop)")
    srv.serve_forever()
