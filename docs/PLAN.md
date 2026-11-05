# Mars Colony — Plan

> Living document. Update when scope, goals, or priorities change
> (major changes should also get an ADR). Session log lives in PROGRESS.md.

## Vision

A Mars-colony-inspired simulation environment in which LLM agents live and
act, built to **observe and study LLM behavior** under scarcity, stakes, and
surprise. The simulation is the instrument; behavioral data is the product.

## Goals

- [ ] Build a headless, deterministic simulation engine (world state + tick
      rules + full trace logging).
- [ ] Agent interface layer: observations in, validated JSON actions out.
- [ ] LLM harness: run one or more models as colony agents in scenarios.
- [ ] Metrics computed offline from traces (survival, efficiency, planning
      horizon, response to stress events).

## Non-goals

Things we explicitly will NOT do (keeps scope honest).

- Game-quality graphics or real-time play.
- Physical/thermodynamic realism — resources are abstract quantities we
  tune for interesting decisions, not simulated exactly.
- Rendering inside the simulation loop (visualizer, if ever, reads traces).

## Architecture / approach

Headless tick engine: `state' = f(state, actions)` as a pure function over
plain data; modular subsystems (life support, energy, production, events);
agents interact only through the observation/action API. Full rationale and
layer diagram: [notes/simulation-engine-approach.md](notes/simulation-engine-approach.md).

## Roadmap

| Milestone | Scope | Status |
|-----------|-------|--------|
| M0 — Foundation | Repo scaffolding, agent config, docs system | In progress |
| M1 — Planning | Vision, goals, architecture decided and documented | In progress |
| M2 — Engine kernel | Grid world, tick loop, 1 scripted bot, resources, death conditions, trace log + replay | Not started |
| M3 — LLM harness | Observation builder, action validator, run a real model in the sim | Not started |
| M4 — Scenarios & events | Seeded random events (dust storms etc.), scenario configs, multi-agent if decided | Not started |
| M5 — Analysis | Offline metrics from traces, experiment runner, optional trace visualizer | Not started |

## Open questions

- ADR-pending engine decisions (see notes/simulation-engine-approach.md):
  language choice, agent interface format, single- vs multi-agent first,
  fidelity level, tick granularity.
- Add OpenCode to the agent roster — when, and what changes in AGENTS.md?
