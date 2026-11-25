# 0004 — Split terrain and deposits; finite multi-resource deposits

- **Date:** 2026-11-25
- **Status:** Proposed
- **Decided with:** Fabian + Hermes

## Context

M2 encodes three orthogonal things in one terrain char (`.` `b` `i` `c`):
walkability, extractability, and flavor. Ice being both passable and
mineable already forced the awkward `PASSABLE = ".ib"` string. Open
question: one resource per tile or many?

## Decision

**Terrain becomes passability only; a sparse `deposits` layer carries
extractables.** A tile may hold up to **two** deposit types, each with a
**finite amount** (e.g. `{"x,y": {"ice": 40, "salt": 10}}`). Mining
withdraws from the deposit; depleted deposits remain as revealed-but-empty
memory for agents. Structure stays one-per-tile (ADR-0003).

## Options considered

1. **Single resource per tile (status quo char)** — simplest, but mutual
   exclusivity (ice never co-occurring with anything) is artificial and
   confounds exploration-path results; and infinite tiles cannot express
   depletion, our best planning-horizon pressure ("nearby ice runs dry by
   sol 40 — push out or die?"). Rejected.
2. **Deposits layer, multiple per tile, finite** — chosen. Backward
   compatible: terrain rows ride alongside old traces; deposits are additive
   state.
3. **Unlimited deposit types per tile** — dense multi-resource tiles make
   radius-3 scouting trivially informative; the map is meant to be hard to
   read. Cap of 2 keeps partial information meaningful. Rejected in favor
   of the capped variant.

## Consequences

- Easy: depletion scenarios (nearby patch exhaustion forcing exploration
  risk), new resource types without new terrain codes, controlled resource
  budgets per map (sum of deposits = scenario-level scarcity tuning).
- Requires: `rules.py` mine action reads/writes deposits; `world.py`
  generator places them; observation exposes deposits in radius (revealed
  only); `viz.py` renders deposit layer; code-version bump in trace headers
  marks the schema change (old traces stay readable, replay must branch on
  version).
- `i` terrain code is retired to a renderer alias during transition.
