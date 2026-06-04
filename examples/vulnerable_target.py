#!/usr/bin/env python3
"""
vulnerable_target.py — a deliberately vulnerable HTTP service for the demo.

Stdlib only, loopback only. It plants ONE textbook bug — an IDOR/BOLA on an
object-read endpoint — plus a correctly-scoped endpoint to contrast against, so
the two-identity diff produces both verdicts.

    /api/objects/{id}         VULNERABLE: requires a valid token but does NOT
                              check that the object belongs to the caller.
    /api/secure/objects/{id}  SAFE: 403s when the object isn't the caller's.

Identity is the `X-Token` header. Run:  python3 examples/vulnerable_target.py
Authorized for local testing of this app only.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = "127.0.0.1", 8731

TOKENS = {"tokA": "alice", "tokB": "bob"}          # token -> user
OBJECTS = {                                          # id -> object
    "1": {"owner": "alice", "data": "SECRET_ALICE_SSN_123-45-6789"},
    "2": {"owner": "bob", "data": "SECRET_BOB_SSN_987-65-4321"},
}


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

    def do_GET(self) -> None:
        user = TOKENS.get(self.headers.get("X-Token", ""))
        if user is None:
            return self._send(401, {"error": "missing or invalid X-Token"})

        parts = self.path.strip("/").split("/")
        # /api/objects/{id}  — VULNERABLE: no ownership check
        if parts[:2] == ["api", "objects"] and len(parts) == 3:
            obj = OBJECTS.get(parts[2])
            if not obj:
                return self._send(404, {"error": "not found"})
            return self._send(200, obj)   # BUG: returns regardless of obj["owner"]

        # /api/secure/objects/{id} — SAFE: object-level authorization
        if parts[:3] == ["api", "secure", "objects"] and len(parts) == 4:
            obj = OBJECTS.get(parts[3])
            if not obj:
                return self._send(404, {"error": "not found"})
            if obj["owner"] != user:
                return self._send(403, {"error": "forbidden"})
            return self._send(200, obj)

        return self._send(404, {"error": "no such route"})


if __name__ == "__main__":
    print(f"[target] vulnerable demo app on http://{HOST}:{PORT} (Ctrl-C to stop)")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
