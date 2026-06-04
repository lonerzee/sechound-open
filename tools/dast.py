#!/usr/bin/env python3
"""
dast.py — a small, nuclei-style template runner for live probing.

Templates live in dast/templates/*.yaml and declare requests + matchers. The
runner sends each request against an in-scope base URL (with optional cookie/
header auth), evaluates the matchers, and reports hits. With --file, hits become
candidate findings in the registry (never `confirmed` — that needs the verifier).

    python3 tools/dast.py --base-url https://app.example.test --all
    python3 tools/dast.py --base-url https://app.example.test \
        --jar ~/.auth/id.cookies --template missing-auth --file

Template schema (see dast/templates/ for examples):

    id: missing-auth-on-admin
    info: {name: ..., severity: high, service: api}
    requests:
      - method: GET
        path: /api/admin/users
        headers: {}
        body: null
        matchers:
          status: [200]            # response status must be one of these
          words: ["email"]         # ALL must appear in the body
          negative_status: [401,403]  # response status must NOT be one of these
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sechound_lib import repo_root, utcnow
import findings_db

try:
    import yaml
except ImportError:
    yaml = None


def _templates_dir() -> Path:
    return repo_root() / "dast" / "templates"


def _load_templates(name: str | None) -> list[dict]:
    d = _templates_dir()
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("*.yaml")):
        if name and name not in p.stem:
            continue
        try:
            t = yaml.safe_load(p.read_text())
            t["_file"] = p.name
            out.append(t)
        except Exception as e:
            print(f"[dast] skip {p.name}: {e}", file=sys.stderr)
    return out


def _request(base_url: str, req: dict, jar: str | None, headers: list[str], timeout: int) -> tuple[int, str]:
    url = base_url.rstrip("/") + "/" + req.get("path", "").lstrip("/")
    cmd = ["curl", "-sS", "-o", "-", "-w", "\n__STATUS__:%{http_code}",
           "-X", req.get("method", "GET"), "--max-time", str(timeout)]
    if jar:
        cmd += ["-b", str(Path(jar).expanduser())]
    for h in headers:
        cmd += ["-H", h]
    for k, v in (req.get("headers") or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    if req.get("body"):
        cmd += ["--data", req["body"] if isinstance(req["body"], str) else json.dumps(req["body"])]
    cmd.append(url)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    except subprocess.TimeoutExpired:
        return 0, "<timeout>"
    out = proc.stdout or ""
    status = 0
    if "__STATUS__:" in out:
        out, _, tail = out.rpartition("\n__STATUS__:")
        status = int(tail.strip()) if tail.strip().isdigit() else 0
    return status, out


def _match(status: int, body: str, m: dict) -> bool:
    if m.get("status") and status not in m["status"]:
        return False
    if m.get("negative_status") and status in m["negative_status"]:
        return False
    for w in (m.get("words") or []):
        if w not in body:
            return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True, help="in-scope target base URL")
    ap.add_argument("--template", help="run only templates whose id contains this")
    ap.add_argument("--all", action="store_true", help="run every template")
    ap.add_argument("--jar", help="cookie jar for authenticated probes")
    ap.add_argument("--header", action="append", default=[], help="extra header (repeatable)")
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--file", action="store_true", help="file hits as candidate findings")
    args = ap.parse_args()

    if yaml is None:
        sys.exit("PyYAML required for DAST templates: pip install pyyaml")
    if not (args.all or args.template):
        sys.exit("pass --all or --template <name>")

    templates = _load_templates(None if args.all else args.template)
    if not templates:
        sys.exit(f"no templates in {_templates_dir()}")

    hits = 0
    for t in templates:
        info = t.get("info", {})
        for req in t.get("requests", []):
            status, body = _request(args.base_url, req, args.jar, args.header, args.timeout)
            if _match(status, body, req.get("matchers", {})):
                hits += 1
                path = req.get("path", "")
                print(f"[HIT] {t.get('id')} — {req.get('method','GET')} {path} (status {status})")
                if args.file:
                    fid, action = findings_db.upsert({
                        "title": f"{info.get('name', t.get('id'))} — {req.get('method')} {path}",
                        "severity": (info.get("severity") or "MEDIUM").upper(),
                        "service": info.get("service", ""),
                        "summary": f"DAST template '{t.get('id')}' matched on {path}.",
                        "endpoint": f"{req.get('method','GET')} {path}",
                        "status": "candidate", "source": f"dast:{t.get('id')}",
                        "found_at": utcnow()[:10],
                    })
                    print(f"       -> {action} {fid}")
            else:
                print(f"[ok ] {t.get('id')} — {req.get('method','GET')} {req.get('path','')} (status {status})")

    print(f"\n[dast] {hits} hit(s) across {len(templates)} template(s). "
          "Hits are CANDIDATES — confirm with verify_finding.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
