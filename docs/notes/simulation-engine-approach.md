# Simulation Engine — Approach (note)

> What this is: engineering approach for the Mars Colony simulation engine.
> Status: proposal / discussion — NOT yet accepted decisions. Decisions that
> settle here get promoted to ADRs.

## Core principle

We are studying LLM agent behavior, not making a game. That dictates the
architecture:

1. **Headless first.** The engine runs without any rendering. A visualizer
   (if built) is a *read-only consumer* of recorded state traces, never part
   of the simulation loop.
2. **Deterministic.** Same seed + same action sequence ⇒ identical run.
   Required for reproducible behavioral experiments and A/B comparisons of
   models. Single seeded RNG for the whole world; no wall-clock reads in the
   rules layer.
3. **Agents see the world through a narrow interface.** Observations in,
   actions out — a JSON/text API. This is also the *scientific instrument*:
   what we choose to make observable/partial is itself an experimental
   variable.
4. **Log everything from day one.** Every tick: full state snapshot (or
   diff), each agent's observation, chosen action, and resolution result.
   Instrumentation is designed first, not bolted on.

## Layered architecture

```
┌─────────────────────────────────────────────┐
│ Experiment harness (runner)                 │  obs → LLM → action → step loop,
├─────────────────────────────────────────────┤  model config, scenario config
│ Agent interface layer                       │  observation builder (partial
├─────────────────────────────────────────────┤  observability), action validator
│ Rules / tick engine  (PURE: state' = f(state, actions))
│   ├─ life-support system   (O2, water, food)│
│   ├─ energy system         (solar, storage) │
│   ├─ production/construction chains         │
│   ├─ environment/events    (dust storm,     │
│   │                        radiation, cold) │
│   └─ agent/crew status                      │
├─────────────────────────────────────────────┤
│ World state (plain data: grid/zones,        │
│ resources, structures, agents, sol counter) │
├─────────────────────────────────────────────┤
│ Instrumentation: event log, action log,     │
│ metrics, replayable traces                  │
└─────────────────────────────────────────────┘
        (optional, later)  Visualizer ← reads traces only
```

Key property: the rules layer is a **pure function** over plain data.
Serialise state to JSON/MessagePack → replay, fork scenarios, branch runs.

## Turn model (recommended)

Turn-based, not real-time: the unit of time is a "tick" (e.g. 1/10 sol or
1 sol). Each tick: build observations → collect all agent actions →
validate → resolve systems in fixed order → commit state → log. Real-time
adds latency noise that contaminates behavioral measurements.

## Minimal kernel (first milestone)

- 2D grid world (say 32×32 tiles: regolith, ice, basalt, crater) — grid over
  free-form geometry keeps rules simple and debuggable.
- 1 agent, 3–4 resources (power, water, O2, food), 5–8 action types
  (move, mine, build, operate, rest, communicate).
- Death/failure conditions (O2 = 0 → episode ends) — gives agents real
  stakes and gives us a survival-time metric.
- Random events from a seeded table (dust storm reduces solar output N
  ticks) — stress is what makes behavior interesting to observe.
- CLI: run a scripted policy for 50 sols, dump trace, replay trace.
  No LLM needed yet — a scripted bot validates the engine.

Only after the kernel passes scripted-bot validation do we wire the LLM
harness (obs text → model → JSON action → validator → step).

## Metric hooks (why the engine exists)

Design the log schema around the questions we want to ask:
- survival time, resource efficiency, exploration vs exploitation ratio
- planning horizon (how far ahead actions look), response to surprise events
- (multi-agent later) cooperation, negotiation, norm formation
Every metric must be computable offline from the trace alone.

## Open decisions (need ADRs once settled)

1. Language: Python recommended (LLM harness ecosystem, fast iteration;
   speed is not a constraint at turn-based scale).
2. Agent interface: pure text/JSON tool API vs rendered/visual env
   (pixels would imply a totally different stack — recommend text/JSON).
3. Single agent first, or multi-agent from day one.
4. Fidelity level: abstract resource-colony sim vs physics-heavy simulation
   (recommend abstract — we measure decisions, not thermodynamics).
5. Turn granularity: 1 tick = 1 sol vs fraction of a sol.
