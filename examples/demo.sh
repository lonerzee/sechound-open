#!/usr/bin/env bash
#
# demo.sh — end-to-end proof against the bundled vulnerable target.
#
# Exercises the deterministic spine offline (NO API key, NO LLM needed):
#   start target -> two-identity diff -> file candidate -> verify (confirm) -> SARIF
#
# The LLM-driven loop (tools/run.py) layers planner/executor on top of this same
# spine; set $SECHOUND_LLM and run `sechound run` to see that part.

set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

export SECHOUND_DB="$(mktemp -t sechound_demo_db.XXXXXX.json)"
ENG="engagements/demo"
TARGET="http://127.0.0.1:8731"

cleanup() {
  if [ -n "${TARGET_PID:-}" ]; then kill "$TARGET_PID" 2>/dev/null; wait "$TARGET_PID" 2>/dev/null; fi
  rm -f "$SECHOUND_DB"
}
trap cleanup EXIT

echo "== 1. start the vulnerable target =="
python3 examples/vulnerable_target.py & TARGET_PID=$!
for _ in $(seq 1 20); do curl -s "$TARGET/api/objects/1" -H "X-Token: tokA" >/dev/null 2>&1 && break; sleep 0.2; done

echo; echo "== 2. two-identity diff: bob requests alice's object on the VULNERABLE route =="
python3 tools/tenant_diff.py --url "$TARGET/api/objects/1" \
  --header-a "X-Token: tokA" --header-b "X-Token: tokB"

echo; echo "== 3. contrast: same attack on the SAFE route (expect isolation_holds) =="
python3 tools/tenant_diff.py --url "$TARGET/api/secure/objects/1" \
  --header-a "X-Token: tokA" --header-b "X-Token: tokB"

echo; echo "== 4. scaffold an engagement + file the candidate with a repro contract =="
rm -rf "$ENG"
python3 tools/init_engagement.py demo --target local-demo --scope 127.0.0.1 >/dev/null

# The repro re-runs the two-identity diff; verify_finding confirms on the signal.
cat > "$ENG/repro.sh" <<EOF
python3 "$REPO/tools/tenant_diff.py" --url "$TARGET/api/objects/1" \
  --header-a "X-Token: tokA" --header-b "X-Token: tokB"
EOF

python3 tools/ingest.py --json '{
  "id": "SH-API-0001",
  "title": "IDOR on /api/objects/{id} — no object-level authorization",
  "severity": "HIGH", "service": "api", "status": "candidate",
  "summary": "A valid token for any user can read any object by id; ownership is not enforced.",
  "endpoint": "GET /api/objects/{id}",
  "files": ["examples/vulnerable_target.py:55"],
  "evidence": {"repro": {"script": "repro.sh", "expected_signals": ["cross_tenant_leak"]}}
}' >/dev/null
python3 -c "import json,os;d=json.load(open(os.environ['SECHOUND_DB']));f=[x for x in d if x['id']=='SH-API-0001'][0];open('$ENG/findings/SH-API-0001.json','w').write(json.dumps(f,indent=2))"

echo; echo "== 5. verify: run the repro, promote candidate -> confirmed =="
python3 tools/verify_finding.py "$ENG" SH-API-0001 --skip-precheck

echo; echo "== 6. report (table) =="
python3 tools/report.py

echo; echo "== 7. SARIF export (head) =="
python3 tools/report.py --format sarif | head -n 20

echo; echo "demo complete. confirmed an IDOR end-to-end with no LLM needed."
