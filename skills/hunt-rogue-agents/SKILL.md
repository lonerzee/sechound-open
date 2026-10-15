---
name: hunt-rogue-agents
description: ASI10 Rogue Agents — unauthorized/shadow agents, agent persistence/backdoors, and agents exceeding their mandate or spawning sub-agents outside policy.
domain: agentic
---

# hunt-rogue-agents

Load when the platform can register, spawn, or persist agents — the risk is a
shadow/unauthorized agent, an agent that outlives or exceeds its mandate, or
sub-agents spawned outside policy (OWASP Agentic ASI10).

## When to load
Rogue agent, shadow agent, unauthorized agent, agent persistence, agent backdoor,
sub-agent spawn, agent sprawl, over-mandate, unregistered worker, orphaned agent,
self-replication, scope exceedance, agent lifecycle.

## Where this class lives
Trace the full lifecycle: who can create an agent, what it's allowed to do, and
when it dies:
- Agent registry / spawn point — the API or code path that instantiates an agent
  or sub-agent; check authz and whether it's the only way in.
- Sub-agent delegation — a parent spawning children; check depth limits, scope
  inheritance, and policy enforcement on the child.
- Persistence surfaces — scheduled/cron agents, long-lived daemons, memory or
  config that re-launches an agent across restarts.
- Mandate definition — the policy/role bounding an agent's tools and scope; check
  whether it's enforced at runtime vs. documented.
- Deregistration / TTL — how agents are retired; orphaned or TTL-less agents are
  rogue candidates.
Enumerate: inventory every running agent and reconcile against the authorized set.

## Neutralizing controls (invalidators — check, don't assume)
- Spawn authorization: creating an agent/sub-agent requires an authz check against
  the requesting principal. Confirm the check is server-side on the spawn path;
  bypass = any agent can spawn freely.
- Registry / allow-list: only registered agents can run; unknown agents are
  rejected. Confirm enforcement, not just inventory; bypass = run-anything.
- Mandate enforcement: an agent's tools/scope are bounded at runtime by policy a
  child cannot widen. Confirm inheritance is restrictive; bypass = child escalates.
- Lifecycle / TTL: agents have a bounded lifetime and are reaped; persistence
  requires explicit authorization. Confirm reaping works; bypass = orphan survives.
- Egress / action monitoring: anomalous agent behavior is detected and killable.
  Confirm an off-switch exists and fires.

## Probes
Benign shadow/persistence checks in a test workspace:
- As a low-priv principal on `app.example.test`, attempt to register/spawn an
  agent named `ROGUE-9284`; success = missing spawn authz.
- Have an agent spawn a sub-agent requesting a tool outside the parent's mandate;
  the child receiving it = scope-inheritance bypass.
- Create a short-lived agent, then check whether it (or a scheduled hook it wrote)
  survives past its intended TTL / a restart; survival = persistence gap.
- Reconcile the live agent inventory against the registry; any unlisted runner is
  a rogue candidate.
Use inert agents that take no real action; clean up after.

## Validation bar
`confirmed` requires an OBSERVED unauthorized agent existing or acting: a
spawned/registered agent the requesting principal was not authorized to create, a
sub-agent running with tools/scope beyond its parent's mandate, or an agent
persisting past its authorized lifetime (surviving a restart / re-launching
itself). An agent merely being *definable* in config, with spawn blocked at
runtime, is NOT confirmation.

## Known chains
A rogue agent is a foothold: spawned outside policy → acts with borrowed or
over-broad identity (ASI03) → persists as a backdoor across sessions → issues
forged messages to legitimate agents (ASI07) → hides its actions from operators
(ASI09). Over-privileged spawn can also seed cascades (ASI08). Each rogue runner
and each action it takes is its own candidate.
