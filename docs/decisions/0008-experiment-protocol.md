# 0008 — Experiment protocol: paired seeds, versioned artifacts, >=5 seeds

- **Date:** 2026-11-25
- **Status:** Accepted (2026-11-26, Fabian)
- **Decided with:** Fabian + Hermes

## Context

The Nov-05 sweep produced a results table we correctly labeled "anecdotes,
not measurements": single seed, per-model seed sharing not guaranteed by
protocol, trace headers missing prompt/scenario/timestamp fields. Before
any claim about model behavior (the project's actual product) we need a
protocol that makes runs comparable and claims falsifiable.

## Decision

**The unit of data is (model, scenario, seed).** All models run the **same
shared seed list** (paired comparison — no average-over-different-worlds);
**>=5 seeds per cell** before trusting a ranking; results reported as
medians + spread across seeds, never a lone mean. **Attribution:** trace
header carries `{code_commit, prompt_hash, scenario_hash, model_id,
seed, ts}`, and per-turn timestamps go into the LLM log. **Freeze policy:**
prompt/worldbook text changes require a version bump, and runs from
different versions never appear in the same comparison. **Metrics are
defined from trace fields only, before collecting**: sols survived,
terminal state (ADR-0006), production/consumption ratio at cap,
exploration radius over time, invalid-action rate, parse-retry rate
(ADR-0005), storm-response latency, decision latency.

## Options considered

1. **Paired seeds + >=5 + distribution reporting** — chosen; map/storm
   variance is the dominant noise source, pairing removes it, and the
   Nov-05 known-gap note already set n>=5 as the bar.
2. **Random per-model seeds, mean reporting** — cheapest, but conflates
   "model B is better" with "model B got friendlier storms". Rejected.
3. **Benchmarks re-run per prompt tweak** — silently invalidates every
   prior comparison. Rejected; freeze policy instead.

## Consequences

- Easy: honest model league tables; latency becomes a real metric (the
  missing `ts` field is the one-line enabler); any run can be re-derived
  from header + trace alone.
- Known caveat, accepted: vLLM continuous batching can make identical
  requests non-bitwise-identical at temp 0 — pin model weights paths,
  never trust single-run A/B, let seed spread absorb it.
- Required: experiment runner updates (seed-matrix spec), trace-header
  fields, per-turn timestamps, `metrics` reading only logged fields;
  sweep artifacts location gets its own convention (PROGRESS note's open
  item).
