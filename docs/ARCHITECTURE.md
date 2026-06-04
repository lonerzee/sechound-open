# Architecture

SecHound is a pipeline, not a scanner. The unit of value is a **confirmed,
de-duplicated finding with a reproduction**, and every stage exists to move
candidates toward that bar or drop them.

## Data flow

```
request
  │
  ▼
┌──────────┐   ranked hypotheses (vuln class + file:line + reachability)
│ planner  │────────────────────────────────────────────────┐
└──────────┘                                                 │
                                                             ▼
                                                      ┌──────────┐
                                                      │ executor │  runs the hunt
                                                      └────┬─────┘
                                          candidate (code-only) stubs
                                                           │
                                                           ▼
                                                    ┌─────────────┐
                                                    │ kill gate   │  drop or keep
                                                    └──────┬──────┘
                                                           │ kept
                                                           ▼
                                                  ┌──────────────────┐
                                                  │ verify_finding   │  live repro
                                                  │  + FP checklist  │  + invalidators
                                                  └────────┬─────────┘
                                       confirmed │         │ demote
                                                 ▼         ▼
                                          ┌──────────┐  back to candidate
                                          │  critic  │  adversarial re-test
                                          └────┬─────┘
                                               │ verdict holds
                                               ▼
                                       ┌──────────────┐
                                       │  compounder  │  fold into knowledge
                                       └──────┬───────┘
                                              ▼
                                       ┌──────────────┐
                                       │ ultrareview  │  static + counter lanes
                                       └──────┬───────┘
                                              ▼
                                       findings registry  ──▶ report
```

## Components

### Planner (`tools/planner.py`)
Takes a free-text request and the target's knowledge (service map, prior
findings, invariants) and emits ranked hypotheses. Each hypothesis is
*located* (file:line or endpoint) and *reachable* (an argument for why an
attacker can reach the sink). Unlocated hypotheses are not actionable.

### Executor (`tools/executor.py`)
Runs the hunt for each hypothesis: static grep/AST queries, a dispatched
sub-agent (`agents/`), or a DAST template. Output is always a
`candidate (code-only)` stub — never a confirmed finding. The executor does not
judge; it produces.

### Kill gate
A cheap filter between code discovery and expensive live verification. A
candidate that obviously cannot be reached, or that a known control fully
neutralizes, is dropped here so verification time goes to real leads.

### Verifier (`tools/verify_finding.py`)
The promotion gate. Reproduces the candidate against live, authorized scope and
applies the false-positive checklist (`docs/FP_CHECKLIST.md`) mechanically.
Cross-tenant / IDOR / BOLA claims require **two authenticated identities** — a
single-identity repro is not validation. Promotes to `confirmed` only with
captured evidence; otherwise demotes.

### Critic (`tools/critic.py`)
Adversarial pass over each verdict. Its job is to be wrong-proving: challenge
the confirmation, look for the invalidator the verifier missed, and auto-demote
on mismatch. False retractions are treated as exactly as costly as false
positives.

### Compounder (`tools/compounder.py`)
Folds confirmed findings back into target knowledge so later hunts start
smarter — new sinks, new invariants, new bypass patterns.

### Ultrareview (`tools/ultrareview.py`)
Final two-lane review at engagement completion: a **static** lane re-reads the
code path, a **counter** lane argues the finding is a false positive. A finding
that survives both ships.

## Orchestration

For multi-class or multi-service work, the orchestrator fans hypotheses out to
parallel sub-agents (one dispatch, many workers), then merges their stubs into
the single registry. See `prompts/` for the agent role prompts and
`agents/README.md` for the contract a sub-agent must satisfy.

## Model layer (`tools/llm.py`)

Every stage that needs an LLM calls one function, `llm.complete()`, and never
references a model or vendor directly. The backend is chosen by `$SECHOUND_LLM`
(Claude CLI, a generic command, or an Anthropic/OpenAI-compatible API). This is
the modular seam: adding a model means editing one file; swapping models means
setting one env var. Stages that must read the codebase (critic, static review
lane) request tool access via `tools=`; completion-only backends degrade
gracefully with a warning. Full matrix in [`PROVIDERS.md`](PROVIDERS.md).

## State & storage

- **Findings registry** — JSON records (`findings/schema.json`),
  de-duplicated by root cause. Real records are gitignored.
- **Engagements** — per-engagement working dirs under `engagements/`
  (gitignored except the keep file). One engagement = one scope + window.
- **Config** — `config/targets.yaml` (scope + auth) and
  `config/invariants.yaml` (invariant-breaker input), both gitignored.

## Design principles

1. **Translate vague → verifiable.** "Audit X" becomes "enumerate sinks →
   invalidator analysis → ranked candidates with file:line."
2. **File candidates cheaply; promote expensively.** Filing a candidate is
   cheap; missing a real bug is expensive. Apply FP patterns *before*
   retracting, not before filing.
3. **Prove, don't assume.** If it's unknowable from code alone, scaffold the
   test and run it. `confirmed` requires evidence.
4. **No hedging in verdicts.** exploitable | not exploitable | unknown — and if
   unknown, name what resolves it.
