# 0002 — Agent interface: text/JSON observation–action API, ≤4 agents

- **Date:** 2026-11-05
- **Status:** Accepted
- **Decided with:** Fabian + Hermes

## Context

Agents (LLMs) must perceive and act in the sim. The interface defines which
behaviors are observable at all — it is the scientific instrument, not just
plumbing. Multi-agent interaction (cooperation, negotiation, norm formation)
is in scope from day one, capped at 4 agents per run.

## Decision

Agents interact **only through a text/JSON observation–action API**: the
engine builds a structured observation per agent per tick (with deliberate
partial observability), and accepts a small, schema-validated JSON action
space (e.g. move, mine, build, operate, rest, communicate). Up to **4 agents
per run**; inter-agent communication is an action type, delivered through
observations. No pixels, no direct state access, ever.

## Options considered

1. **Text/JSON API** — model-agnostic, cheap, fully loggable; observability
   becomes an explicit experimental variable. Chosen.
2. **Rendered 2D environment (agent sees images)** — needs a vision stack
   per model, expensive, conflates perception failures with decision
   failures. Rejected (could return later only as an experiment variant).
3. **Single agent first** — simpler, but the user's interest is social
   dynamics; with ≤4 agents the tick resolution stays trivial. Rejected.

## Consequences

- Easy: comparing models on identical scenarios; injecting events as text;
  auditing every agent's exact information state at every tick.
- Required discipline: pydantic action schemas; invalid/illegal actions are
  logged as first-class events (refusal, hallucinated target, schema
  violation) — agent failure modes are data, not errors.
- Follow-ups: M2 kernel builds a scripted bot behind the same interface;
  communication-channel rules (broadcast vs targeted, range limits) need
  design during M4 scenario work.
