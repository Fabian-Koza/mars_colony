# 0001 — Engine shape: headless deterministic Python tick engine

- **Date:** 2026-11-05
- **Status:** Accepted
- **Decided with:** Fabian + Hermes

## Context

Mars Colony exists to observe LLM agent behavior under scarcity, stakes and
surprise (see PLAN.md). We need an engine whose runs are reproducible
experiments, not a game loop. First code will land in M2. Performance scale:
turn-based, ≤4 agents, small grid — nowhere near compute-bound.

## Decision

Build a **headless, deterministic, turn-based simulation engine in Python**.
The core is a pure function `state' = f(state, actions)` over plain,
JSON-serializable data. World fidelity is an **abstract resource-colony
sim**: resources are tuned abstract quantities, not physics.

## Options considered

1. **Python, headless tick engine** — best LLM-harness and analysis
   ecosystem; iteration speed on rules is the real bottleneck. Chosen.
2. **Rust core + Python bindings** — 10–100x tick throughput, irrelevant at
   our scale; compile-cycle cost hurts rule iteration. Rejected; the pure
   tick boundary keeps a later port open for free.
3. **TypeScript/Node** — viable SDKs but weak offline data-analysis story.
   Rejected.
4. **Physics-heavy fidelity** — realistic thermodynamics measures physics
   knowledge, not decision behavior under stakes, and slows tuning. Rejected.
5. **Real-time engine** — latency noise contaminates behavioral measurement.
   Rejected.

## Consequences

- Easy: replay/fork/branch runs (serialize state), A/B model comparisons
  with identical seeds, offline metric computation from traces alone.
- Required discipline: one seeded RNG for the whole world; no wall-clock or
  I/O inside the rules layer; integer/fixed-point resource quantities to
  avoid float drift between replays.
- Follow-ups: M2 kernel implemented to this shape; trace/log schema designed
  around target metrics before subsystems are written.
