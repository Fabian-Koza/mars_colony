# 0006 — Episode semantics: three terminal states, permanent death

- **Date:** 2026-11-25
- **Status:** Proposed
- **Decided with:** Fabian + Hermes

## Context

M2's only episode end is "all agents dead". That yields a survival-time
metric but no success state, and cannot distinguish "died at 40" from
"alive but stalled at the cap" from "actually built a sustainable colony".
Scenarios (M4) need a declared notion of going well.

## Decision

**Every episode ends in exactly one of three logged states:**
`colony_dead` (all agents dead — deaths are permanent, no respawn, no
knowledge transfer to survivors), `success` (scenario-declared; default:
all four resources net-positive for 30 consecutive sols with >=1 agent
alive), or `sol_cap` (hard ceiling, default 120 sols, reported distinctly
— alive-at-cap is neither success nor death). The terminal state and its
triggering sol go into the final trace record and the header summary.

## Options considered

1. **Survival-only (status quo)** — one ordinal metric, blind to colony
   quality; two very different trajectories collapse to the same number.
   Rejected.
2. **Three terminal states + permanent death** — chosen; stakes require
   irreversibility, and "went well" must be defined per scenario at design
   time, not judged post-hoc.
3. **Respawn / knowledge carry-over on death** — removes the cost of
   mistakes and turns death into a scouting move; would dominate every
   incentive structure. Rejected.

## Consequences

- Easy: survival curves become three-outcome comparisons across models;
  success defines an efficiency axis (how fast did they close the loop?).
- Follow-up: `rules.py` needs a per-sol net-production check (cheap) and
  scenarios (ADR-0007) gain `win` and `sol_cap` fields; existing metrics
  code updated to read the terminal state.
- "30 consecutive sols net-positive" is a tuning knob — it lives in
  scenario data, not code.
