#!/usr/bin/env python3
"""
tenant_diff.py — the falsifier for cross-tenant / IDOR / BOLA claims.

Runs the SAME request as two distinct identities and diffs the responses. A
single-identity repro is NOT validation; this is the tool the FP checklist and
the verifier require before any cross-tenant finding can be confirmed.

Identity is supplied as a cookie jar (curl -b) and/or extra headers:

    python3 tools/tenant_diff.py \
        --url https://app.example.test/api/v1/objects/4242 \
        --jar-a ~/.auth/identity_a.cookies \
        --jar-b ~/.auth/identity_b.cookies

    # or with header-based auth:
    python3 tools/tenant_diff.py --url ... \
        --header-a "Authorization: Bearer AAA" \
        --header-b "Authorization: Bearer BBB"

Identity A is the OWNER (expected to see the resource); identity B is the
ATTACKER (a different tenant/user that should NOT). Verdicts:

  cross_tenant_leak    B got 2xx with the same body A did → isolation BROKEN
  isolation_holds      B was denied (401/403/404) while A succeeded → good
  possible_leak        both 2xx, B got content on A's resource URL but a
                       different body → ambiguous (legit per-identity scoping,
                       or a leak with per-request variation). Flagged for review,
                       NOT auto-confirmed.
  scoped_per_identity  both 2xx but B's body is empty → B saw its own empty view
  responses_match      both identical AND not clearly A's resource → inconclusive
  diverged             statuses/sizes don't fit a clean pattern → inspect manually

Only `cross_tenant_leak` is a confirm-grade signal (non-zero exit). `possible_leak`
is deliberately review-grade: it stops the false negative where an IDOR returns
the victim's resource with a body that isn't byte-identical to the attacker's own.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _curl(url: str, method: str, data: str | None, jar: str | None,
          headers: list[str], timeout: int) -> tuple[int, str]:
    cmd = ["curl", "-sS", "-o", "-", "-w", "\n__HTTP_STATUS__:%{http_code}",
           "-X", method, "--max-time", str(timeout)]
    if jar:
        cmd += ["-b", str(Path(jar).expanduser())]
    for h in headers:
        cmd += ["-H", h]
    if data:
        cmd += ["--data", data]
    cmd.append(url)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    except subprocess.TimeoutExpired:
        return 0, "<timeout>"
    out = proc.stdout or ""
    status = 0
    if "__HTTP_STATUS__:" in out:
        out, _, tail = out.rpartition("\n__HTTP_STATUS__:")
        try:
            status = int(tail.strip())
        except ValueError:
            status = 0
    return status, out


def classify(status_a: int, body_a: str, status_b: int, body_b: str) -> str:
    a_ok = 200 <= status_a < 300
    b_ok = 200 <= status_b < 300
    if a_ok and b_ok:
        if body_a == body_b and body_a.strip():
            return "cross_tenant_leak"   # B sees exactly what owner A sees
        if body_b.strip():
            # B got 2xx with content on A's resource URL but a different body.
            # Could be legit per-identity scoping, or a real leak whose body
            # varies per request (timestamps/nonces). Ambiguous → review, don't
            # silently treat as safe.
            return "possible_leak"
        return "scoped_per_identity"     # B's response empty → its own empty view
    if a_ok and status_b in (401, 403, 404):
        return "isolation_holds"
    if body_a == body_b:
        return "responses_match"
    return "diverged"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--method", default="GET")
    ap.add_argument("--data", default=None, help="request body (sent to both identities)")
    ap.add_argument("--jar-a", default=None, help="owner cookie jar")
    ap.add_argument("--jar-b", default=None, help="attacker (other tenant) cookie jar")
    ap.add_argument("--header-a", action="append", default=[], help="extra header for A (repeatable)")
    ap.add_argument("--header-b", action="append", default=[], help="extra header for B (repeatable)")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--json", action="store_true", help="emit JSON only")
    args = ap.parse_args()

    if not (args.jar_a or args.header_a) or not (args.jar_b or args.header_b):
        sys.exit("supply identity A (--jar-a/--header-a) AND identity B (--jar-b/--header-b)")

    sa, ba = _curl(args.url, args.method, args.data, args.jar_a, args.header_a, args.timeout)
    sb, bb = _curl(args.url, args.method, args.data, args.jar_b, args.header_b, args.timeout)
    verdict = classify(sa, ba, sb, bb)

    result = {
        "url": args.url, "method": args.method, "verdict": verdict,
        "identity_a": {"status": sa, "body_len": len(ba)},
        "identity_b": {"status": sb, "body_len": len(bb)},
        "bodies_identical": ba == bb,
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"A (owner):    status={sa} body_len={len(ba)}")
        print(f"B (attacker): status={sb} body_len={len(bb)}")
        print(f"bodies identical: {ba == bb}")
        print(f"\nVERDICT: {verdict}")
        if verdict == "cross_tenant_leak":
            print("  -> isolation BROKEN: attacker identity read the owner's resource.")
        elif verdict == "possible_leak":
            print("  -> REVIEW: attacker got 2xx on the owner's resource with a different "
                  "body. Could be per-identity scoping or a leak — verify manually.")

    # Exit non-zero on a confirmed leak so it's usable as a repro signal in
    # verify_finding.py expected_signals (grep for 'cross_tenant_leak').
    return 2 if verdict == "cross_tenant_leak" else 0


if __name__ == "__main__":
    sys.exit(main())
