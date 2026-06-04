# Quickstart

See SecHound confirm a real bug end-to-end in ~10 seconds — **no API key, no LLM
required**. The demo runs the deterministic spine (two-identity diff → file →
verify → SARIF) against a bundled, deliberately vulnerable target.

```bash
git clone https://github.com/lonerzee/sechound-open.git
cd sechound-open
bash examples/demo.sh
```

You'll see:

1. The vulnerable target starts (`examples/vulnerable_target.py` — a stdlib HTTP
   app with a planted IDOR on `GET /api/objects/{id}`).
2. **Two-identity diff** — "bob" requests "alice's" object on the vulnerable
   route → verdict `cross_tenant_leak` (isolation broken).
3. The same attack on the *safe* route → `isolation_holds` (so you can see the
   gate distinguishes a real bug from a non-bug).
4. The finding is filed as a `candidate` with a repro contract.
5. **verify** runs the repro and promotes it `candidate → confirmed`.
6. **report** prints the registry; **SARIF** export is ready for GitHub code
   scanning.

```
VERDICT: cross_tenant_leak
  -> isolation BROKEN: attacker identity read the owner's resource.
...
[verify] SH-API-0001: CONFIRMED — all expected signals present
ID               SEVERITY  STATUS      SERVICE  TITLE
SH-API-0001      HIGH      confirmed   api      IDOR on /api/objects/{id} — no object-level authorization
```

## Adding the LLM loop

The demo shows the spine. The full pipeline layers an LLM planner/executor on
top to *find* candidates (not just verify a known one). Pick a backend
(`docs/PROVIDERS.md`) and run the loop against your own authorized scope:

```bash
export SECHOUND_LLM=claude            # or command / anthropic / openai / gemini
cp config/targets.example.yaml config/targets.yaml   # YOUR authorized scope
python3 tools/init_engagement.py 2026-01-01_initial --target my-staging
sechound run engagements/2026-01-01_initial --goal "audit the public API for IDOR"
```

> The bundled target binds to `127.0.0.1` only and contains no real data. Run
> SecHound against other systems **only** with authorization. See `SECURITY.md`.
