---
name: hunt-unbounded-consumption
description: LLM resource hunt playbook — OWASP LLM10 Unbounded Consumption; denial-of-wallet, token/cost exhaustion, resource flooding, unbounded loops.
domain: llm
---

# hunt-unbounded-consumption

Load when testing whether an LLM app lets a caller drive unbounded inference
cost or resource use — denial-of-wallet / denial-of-service. Covers OWASP LLM10
(Unbounded Consumption).

## When to load
unbounded consumption, denial of wallet, token exhaustion, cost blowup, rate
limit bypass, resource flooding, context flooding, unbounded loop, agent
recursion, runaway agent, infinite tool loop, model extraction.

## Where this class lives
Any path where a cheap request triggers expensive or repeated inference:
- endpoints with no per-caller rate/quota/token cap on prompt or completion size,
- user-controlled generation parameters (max_tokens, N, temperature loops,
  requested output length),
- agent/tool loops that can recurse or fan out without a step/depth/time budget
  (one tool call spawning more),
- large-input amplification (huge upload → huge embedding/summarization job),
- expensive model selection a caller can force on a free/low tier.
Enumerate every entry point and ask: what bounds the work per request and per
caller — tokens, steps, wall-clock, concurrency, spend?

## Neutralizing controls (invalidators — check, don't assume)
- **Per-identity rate limit + quota** — requests and tokens capped per
  user/tenant/key over a window. Confirm it counts the right dimension (tokens,
  not just request count) and is enforced server-side. Bypass: rotate keys/IPs,
  or stay under request-count limits while maxing token size.
- **Hard output/context caps** — server clamps max_tokens and input length
  regardless of what the caller asks. Confirm the clamp, don't trust the default.
- **Agent step/depth/time budget** — loop has a ceiling and a timeout. Bypass:
  input that keeps each step "productive" so no stall check trips.
- **Spend alerting/circuit breaker** — cost guard trips and sheds load. Confirm
  it actually halts work, not just alerts.

## Probes
Against `app.example.test`, send a minimal request that requests maximal output
(push max_tokens / "write 50,000 words"), and measure tokens billed vs. bytes
sent — the amplification factor is the signal. Fire N concurrent requests to
test whether rate/concurrency limits hold. For agents, craft input that induces
a self-referential tool loop (tool A triggers tool B triggers tool A) and watch
step count / wall-clock. Keep volume benign and measured — this is a cost probe,
not a live flood; stop at the first clear unbounded signal.

## Validation bar
`confirmed` requires an OBSERVED, measurable resource/cost blowup from a bounded
attacker action: a large amplification ratio (small input → large billed token
count), request/token throughput that exceeds the documented limit (limit
absent or bypassed), or an agent loop that runs past a reasonable step/time
budget without self-terminating. A theoretical "no visible limit in code" is a
candidate, not confirmed — the disproportionate consumption must be measured.

## Known chains
Unbounded consumption → denial-of-wallet (sustained cost drain) or
denial-of-service (capacity exhaustion for other tenants). Amplification +
key rotation → sustained abuse. Runaway agent loop → resource exhaustion plus
unintended repeated side effects from each loop iteration.
