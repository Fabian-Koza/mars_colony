# M2 — Engine kernel design (note)

> What this is: the concrete design of the M2 simulation kernel: state
> schema, action space, tick order, trace format. Implements ADR-0001/0002.

## Settled here (were open questions in PLAN.md)

- **Tick granularity:** 1 tick = 1 sol. Simplest mapping to the fiction;
  action energy costs are what gate behavior, not time slices.
- **Minimal resource set:** `power`, `water`, `o2`, `food` — integers,
  colony-shared storage (no per-agent inventories in the kernel).
- **Action space (v0):** `move`, `mine`, `build`, `rest`, `wait`.
  `give`/`communicate` deferred to M4 (colony-shared storage makes `give`
  moot for now).
- **Trace/log schema:** JSONL — header line (seed, scenario, code version),
  then one line per tick:
  `{tick, actions:[{agent, action, status(ok|invalid), reason, produced}],
    events:[...], deaths:[...], state_hash, state}` (full snapshot per tick
  — cheap at this scale, makes replay diffs trivial).

## World

- 32×32 grid, terrain codes: `.` regolith, `b` basalt (both passable),
  `i` ice (passable, mineable), `c` crater (impassable).
  Generated deterministically from the run seed. Base at center tile.
- Structures: `base` (starts), `panel` (+2 power/sol, halved in storm),
  `extractor` (2 water + 1 power → 2 o2), `greenhouse` (1 water + 1 power →
  2 food). One structure per tile; build at the agent's own tile.
- Build costs (from colony water storage): panel 10, extractor 15,
  greenhouse 20 water. Mine: +8 water to storage (cap 200). Yield 5 was
  tuned to 8 after M2 balance check: with mine costing 5 energy the bot
  rests ~1/3 of sols, and 5/sol income could not cover the 5/sol steady
  drain (crew + extractor + greenhouse) — a built colony must be
  sustainable, extinction should come from bad decisions, not arithmetic.
- Storage start: power 20, water 40, o2 60, food 60. Caps: power 100.

## Agents

`{id, x, y, energy(0..100), health(0..100), alive}`.
- Action energy costs: move 2, mine 5, build 8. `rest`: +10 energy.
  Invalid (logged, not crashed) if energy < cost or preconditions unmet.
- Per-sol consumption per alive agent: 1 o2, 1 water, 1 food from storage.

## Death conditions (episode = until all agents dead)

- o2 shortfall at consumption → instant death (`asphyxiation`).
- water/food shortfall → health −10/sol (recover +1 up to 100 while fed);
  health ≤ 0 → death (`starvation`/`dehydration`).

## Environment (minimal seeded stress)

- Dust storm: each tick 2% chance (seeded) of a 3–6 sol storm; panel output
  halved. This is the stub for the M4 event system and the determinism
  exercise for the RNG.
- RNG: custom splitmix64 with integer state stored IN the state dict →
  `f(state, actions)` is pure and replayable; no Python `random` object.

## Tick order (fixed)

1. validate + resolve agent actions (agent id order)
2. production systems (structures, in id order)
3. consumption + health/deaths (agent id order)
4. environment/events (sole RNG consumer)
5. sol counter++, snapshot + log

## Interfaces (already the M3 contract)

- `observation(state, agent_id) -> dict` — agent-local view: self status,
  storage, structures, terrain+agents within radius 3, storm flag. Partial
  by design.
- Scripted bots consume only the observation — same door the LLM uses in M3.
