---
name: hunt-agent-identity-privilege
description: ASI03 Identity & Privilege Abuse — agent identity spoofing, delegated-credential misuse, and the agent acting above the requesting principal.
domain: agentic
---

# hunt-agent-identity-privilege

Load when an agent holds its own identity or a delegated credential and acts on
behalf of a principal — the risk is the agent using more privilege than the
requester, or an attacker assuming the agent's identity (OWASP Agentic ASI03).

## When to load
Agent identity spoofing, delegated credentials, token misuse, confused deputy,
privilege escalation via agent, impersonation across sessions, service-account
over-grant, on-behalf-of token, agent principal, ambient authority, scope
widening.

## Where this class lives
Trace the identity the agent *presents* to each tool/API vs. the identity of the
*requester* that triggered the action:
- Tool-dispatch authz — does the tool authorize against the end-user principal,
  or against the agent's own (usually broader) service identity?
- Delegated-token mint/exchange — where an on-behalf-of or impersonation token is
  issued; check audience, scope, and lifetime.
- Session/principal binding — whether the agent's identity is re-bound per request
  or carried statically across users and sessions.
- Credential store the agent reads — shared keys/tokens that let any invoking
  user borrow the agent's privilege.
- Cross-session memory of identity — a prior user's token or context reachable in
  a later session.
Enumerate by mapping, for each tool, {who asked} vs. {whose credential ran it}.

## Neutralizing controls (invalidators — check, don't assume)
- Privilege separation: tools enforce their OWN authz against the end principal,
  not "the model decided". Confirm the check is server-side on the requester's
  identity; bypass = authz keyed only on the agent's service account.
- Scoped delegation: on-behalf-of tokens carry the requester's scopes, a narrow
  audience, and a short TTL. Confirm the downstream validates audience+scope;
  bypass = a broad or reusable token.
- Per-request identity binding: the principal is re-established each turn, never
  cached across users. Confirm no static principal; bypass = session reuse.
- Least privilege: the agent's own identity grants only what every user may do.
  Confirm the grant set; bypass = agent can reach admin-only actions.
- Token binding / sender-constraint (DPoP/mTLS): stolen tokens are unusable
  off-channel. Confirm it's enforced, not advertised.

## Probes
Benign cross-principal checks — never escalate a real account:
- Two low-priv test principals A and B on `app.example.test`. Have the agent,
  acting for A, request an object owned by B via a tool; a success proves the
  tool authorized on the agent identity, not on A.
- Ask the agent (as a least-priv user) to perform an admin-only read; a non-403
  proves it runs with the agent's broader identity.
- In session 2 as user B, ask "what was the last account you acted for?" — a leak
  of A's identity/token proves cross-session principal bleed.
Keep to read-only objects you own in the test tenant.

## Validation bar
`confirmed` requires an OBSERVED cross-principal privilege use: the agent takes
an action or returns data that the *requesting* principal is not authorized for,
executed under the agent's (or another user's) identity. A forged/accepted
delegated token used downstream also qualifies. The agent *claiming* it could do
it, or echoing a credential without a successful privileged call, is NOT
confirmation.

## Known chains
Over-privileged agent identity → BOLA/IDOR across tenants (confused deputy),
→ reads a secret store → ASI05 code exec, → mints a broader token reused by a
rogue agent (ASI10), → the elevated action is laundered through a benign summary
to the operator (ASI09). Treat each escalated action as a separate candidate.
