# Mars Colony — Plan

> Living document. Update when scope, goals, or priorities change
> (major changes should also get an ADR). Session log lives in PROGRESS.md.

## Vision

A Mars-colony-inspired simulation environment in which LLM agents live and
act, built to **observe and study LLM behavior** under scarcity, stakes, and
surprise. The simulation is the instrument; behavioral data is the product.

## Goals

- [x] Build a headless, deterministic simulation engine (world state + tick
      rules + full trace logging).  # M2, 2026-11-05
- [x] Agent interface layer: observations in, validated JSON actions out.  # M2, 2026-11-05
- [x] LLM harness: run one or more models as colony agents in scenarios.  # M3, 2026-11-05
- [ ] Metrics computed offline from traces (survival, efficiency, planning
      horizon, response to stress events).

## Non-goals

Things we explicitly will NOT do (keeps scope honest).

- Game-quality graphics or real-time play.
- Physical/thermodynamic realism — resources are abstract quantities we
  tune for interesting decisions, not simulated exactly.
- Rendering inside the simulation loop (visualizer, if ever, reads traces).

## Architecture / approach

Headless deterministic Python tick engine: `state' = f(state, actions)` as a
pure function over plain data; modular subsystems (life support, energy,
production, events); agents interact only through a text/JSON
observation/action API, ≤4 agents per run. Decided in
[ADR-0001](decisions/0001-engine-shape-headless-python-tick-engine.md) and
[ADR-0002](decisions/0002-agent-interface-text-json-api.md); rationale and
layer diagram: [notes/simulation-engine-approach.md](notes/simulation-engine-approach.md).

## Roadmap

| Milestone | Scope | Status |
|-----------|-------|--------|
| M0 — Foundation | Repo scaffolding, agent config, docs system | In progress |
| M1 — Planning | Vision, goals, architecture decided and documented | Done (ADR-0001/0002) |
| M2 — Engine kernel | Grid world, tick loop, 1 scripted bot, resources, death conditions, trace log + replay | Done (2026-11-05) |
| M3 — LLM harness | Observation builder, action validator, run a real model in the sim | Done (2026-11-05) |
| M4 — Scenarios & events | Seeded random events (dust storms etc.), scenario configs, multi-agent if decided | Not started |
| M5 — Analysis | Offline metrics from traces, experiment runner, optional trace visualizer | Partial (visualizer + sweep runner done, 2026-11-05) |

> **Engine branch (2026-11-25):** `engine` branch carries `0.3.0-engine` —
> the first build implementing the draft ADRs 0004–0008 (deposit layering,
> terminal outcomes, declarative scenarios, trace attribution). Merges back
> to `fabian` once the ADRs are accepted.

## Open questions

- M2 kernel design details — RESOLVED (see `notes/m2-kernel-design.md`).
- Foundational design for the next build phase (spatial rules, deposit
  layers, worldbook/memory protocol, episode semantics, scenario format,
  experiment protocol, comms/ownership deferral) — DRAFTED as
  ADR-0003…0009 (Proposed, 2026-11-25); **awaiting Fabian's acceptance**.
- Add OpenCode to the agent roster — when, and what changes in AGENTS.md?
