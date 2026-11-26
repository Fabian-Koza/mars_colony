# 0007 — Scenarios are declarative data files

- **Date:** 2026-11-25
- **Status:** Accepted (2026-11-26, Fabian)
- **Decided with:** Fabian + Hermes

## Context

M4 introduces events, map variants and win conditions (ADR-0006). Without
a decided shape, "scenario" would get implemented as Python branches —
unreviewable, unhashable, and impossible for non-engineers to author.

## Decision

**One scenario = one declarative JSON file; the engine never edits code to
add one.** Fields: `name`, `worldbook_ref` (version), `map`
(`{mode: procedural, seed}` or `{mode: fixed, file}`), `start_overrides`,
`deposits` budget (per ADR-0004), `events` (`scripted: [{sol, type,
params}]` + `stochastic: [{type, p, params}]`), `win` (condition +
consecutive-sols), `sol_cap`, `agents` (count/ids), `ownership` (flag; only
`shared` implemented, `private` reserved — see ADR-0009). The scenario
file's hash is recorded in every run's trace header. **Map policy:
hand-authored fixed maps for A/B model comparisons; procedural seeded maps
only for robustness runs** (same config, N seeds).

## Options considered

1. **Declarative JSON scenarios** — chosen; stdlib-parseable, hashable,
   diff-reviewable, and ADR-0008's attribution model requires a scenario
   hash per run.
2. **Scenarios as Python modules** — max flexibility, but a scenario could
   change behavior invisibly between runs; attribution and review both
   break. Rejected.
3. **Hard-coded presets in `runner.py`** — fine for M2/M3 throwaway,
   actively hostile to M4's scenario family ambitions. Rejected.

## Consequences

- Easy: scenario libraries are data PRs; fixed maps make model A/B paired
  comparisons honest; event mix (fixed schedule vs seeded RNG, e.g. the
  storm that never fired on seed 42) becomes authorable per scenario.
- Required: a scenario loader + validator (stdlib `json`), 2-3 starter
  scenarios (baseline fixed-map A/B map, storm-heavy stress map,
  depletion map exercising ADR-0004), trace-header wiring for the hash.
- `ownership: private` and event types beyond storm stay unimplemented —
  the schema reserves names, code lands when a scenario needs them.
