# 0003 — Spatial model: one tile = one room; no-gotchas tile rules

- **Date:** 2026-11-25
- **Status:** Proposed
- **Decided with:** Fabian + Hermes

## Context

Open design questions going into the next build phase: is a "room" one tile
or a multi-tile footprint, and what micro-rules govern tiles (agent sharing,
structure blocking, build placement, move costs)? These are currently
implicit in M2 (`world.py` has one structure per tile, terrain as a single
char) and are about to be baked into bots, prompts and scenario files.

## Decision

**One tile holds at most one structure (room); no multi-tile footprints.**
Adopt the no-gotchas rule set: agents may share a tile freely; structures do
not block movement; building is allowed on any passable tile (never
stacking, no terrain restrictions beyond passability); move cost is uniform
(craters are the only geometry). Spatial decisions come from *distance to
deposits* and (optionally) adjacency bonuses, not from collision bookkeeping.

## Options considered

1. **One tile = one room** — footprint validation, connectivity ("attached
   to airlock?"), and partial-destruction semantics never need to exist.
   Chosen.
2. **Multi-tile rooms** — spatially realistic, but the added rulebook
   (placement, overlap, connectivity) is learned-at-a-cost noise before any
   real decision is made; behavioral signal does not live in geometry.
   Rejected.
3. **Adjacency rules for spatial play** — not an alternative but an
   add-on we keep open: same-type neighbors produce a small bonus, or
   build range limited from base ("pressurized corridor"). ~10 lines in the
   production step, expressible as a scenario param. Deferred until a
   scenario needs it.

## Consequences

- Easy: placement decisions are measurable (cluster vs scatter) without
  geometry machinery; prompts and bots never hit collision surprises.
- Terrain-move-costs and structure blocking become deliberate, ADR'd
  additions later — not drift.
- If a future game-like mode ever wants footprints, it supersedes this ADR;
  the state schema (`structures` list with x/y) tolerates it.
- Micro-rules must be written into the worldbook (ADR-0005) so agents are
  told them, per our baseline-knowledge stance.
