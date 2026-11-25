# 0009 — Defer inter-agent communication and private ownership

- **Date:** 2026-11-25
- **Status:** Proposed
- **Decided with:** Fabian + Hermes

## Context

ADR-0002 assumed multi-agent social behavior (communication as an action
type; cooperation/negotiation interest) and PLAN.md lists M4 multi-agent as
"if decided". Left implicit, comms and per-agent inventories would get
built by accident — and both re-teach the entire action space (`give` stops
being moot, storage attribution changes, deception measurement enters)
before the single-agent scarcity instrument is producing clean data.

## Decision

**M4 multi-agent means world-shared, parallel-independent agents: shared
storage, no message channel.** Inter-agent communication (`say` action —
proximity-limited, ~100-token cap, energy cost, truthfulness measured not
enforced) and private inventories/trade are **future scenario families,
each gated behind its own ADR triggered by a concrete hypothesis**. The
`ownership` scenario flag (ADR-0007) records the door without opening it.

## Options considered

1. **Build comms now in M4** — social dynamics is a real research
   interest, but its confound stack (format skill x lying x memory x
   theory-of-mind) can't be attributed until the solo instrument is clean.
   Deferred, not rejected.
2. **World-shared only, door reserved in schema** — chosen; keeps M4 to
   scenario loader + events + worldbook; makes the deferral explicit so it
   can't be undone by drift.
3. **Drop the social-research angle entirely** — premature; several
   interesting questions (norm formation, division of labor) need it.
   Rejected.

## Consequences

- Easy: M4 stays small and its results interpretable; when comms arrives it
  gets a clean baseline to diff against.
- Refines (does not supersede) ADR-0002: its interface decisions stand;
  only its "communication needs design during M4" follow-up is resolved as
  "not in M4". A future comms ADR supersedes this one when it fires.
- Trace/metrics: parallel-agent runs log the shared-world interference
  (tile collisions, storage contention) since Nov-05 showed symmetric
  deaths — that interference itself is data now.
