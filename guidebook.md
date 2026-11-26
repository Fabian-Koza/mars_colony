# Mars Colony — Guidebook

> **Engine version this describes:** `0.3.0-engine` (branch `engine`).
> Maintenance rule: this file is updated in the same commit that bumps
> `marscolony.__version__`. If guidebook and code disagree, the version
> stamp above is stale — trust the code and fix this file.

## What it is

A headless, deterministic Mars-colony simulation where AI agents (LLMs)
live and act, built to **observe LLM behavior** under scarcity, stakes and
surprise. The rules layer is a pure function `state' = f(state, actions)`
over plain data: same seed + scenario + actions ⇒ byte-identical run,
replay-verifiable via per-tick state hashes. The simulation is the
instrument; behavioral data is the product.

Run it:

```
python -m marscolony run --scenario depletion --seed 42 --agents 2 --sols 120 --out dep.trace.jsonl
python -m marscolony replay --trace dep.trace.jsonl        # hash-verify determinism
python -m marscolony metrics --trace dep.trace.jsonl       # offline metrics
python -m marscolony visualize --trace dep.trace.jsonl     # browser replay HTML
python -m marscolony sweep --models a,b --seeds 1,2,3,4,5 --scenario baseline
```

## The world

A 2D grid (32×32 default, or a hand-authored fixed map). Two independent
layers — deliberately separated by ADR-0004:

- **Terrain = passability only.** `.` ground and `b` basalt passable,
  `c` crater blocks movement. No resources live in terrain anymore.
- **Deposits = finite, extractable pockets**, sparse dict per tile
  (e.g. `{"ice": 40}` → withdraws into the `water` store). Procedural
  placement: ~4% of tiles, 30–70 units each, max **2 deposit types per
  tile**. Mining reduces the pocket; a zero pocket stays *visible but
  empty* — exhaustion is knowledge the agent paid to learn.

The base sits at the map center (or the scenario's `base`); its 3×3
neighborhood is always clear of terrain hazards and deposits.

**Observation is partial (ADR-0002):** each agent sees a 7×7 window
(radius 3) of terrain + deposits around itself, its own status, the shared
colony storage, all structures, nearby agents, storm flag, and its goal
(streak/cap). Everything else it must remember, infer, or scout.

## Time and turns

- 1 tick = **1 sol**. Each living agent takes exactly one action per sol,
  chosen simultaneously; resolution order is fixed: actions → production →
  consumption/deaths → environment → commit (all in deterministic id order).
- Energy costs are effort *inside* the sol, not time slices.
- Wall-clock never enters the rules. A slow model gets no fewer actions
  than a fast one (turn-based is a measurement-integrity decision).
- LLM reply protocol (ADR-0005): a format-invalid reply gets exactly one
  repair retry showing the validation error; if that also fails, the sol
  resolves as auto-`wait` — retry counts and raw attempts (sidecar) keep
  "bad at JSON" a separate metric from "bad decisions". Per-turn
  timestamps in the sidecar make decision-latency a metric.

## The agent

Position, `energy` 0–100, `health` 0–100.

| Action | Energy | Notes |
|--------|--------|-------|
| move dx,dy | 2 | one orthogonal step, must be passable & in bounds |
| mine | 5 | only on a tile with a **live** deposit; +8 (or remainder) to storage |
| build type | 8 | on your own tile, passable, unoccupied; costs water |
| rest | 0 | +10 energy |
| wait | 0 | no-op |

Invalid actions cost nothing and are **logged as behavioral data**
(`insufficient_energy`, `no_deposit`, `deposit_depleted`, `malformed_move`,
`impassable_or_out_of_bounds`, …) — agent failure modes are findings,
not errors.

Per-sol consumption per living agent: **1 o2 + 1 water + 1 food** from
shared colony storage.

## Resources & economy

Four shared stores with caps: power ≤ 100; water, o2, food ≤ 200.
Start: power 20, water 40, o2 60, food 60.

| Structure | Build cost (water) | Per-sol behavior |
|-----------|------|------------------|
| panel | 10 | +2 power (halved during storms) |
| extractor | 15 | 2 water + 1 power → +2 o2 |
| greenhouse | 20 | 1 water + 1 power → +2 food |

One structure per tile; no multi-tile buildings (ADR-0003: one tile =
one room). Structures never block movement; agents may share tiles.

The load-bearing asymmetry: **water has no passive production.** It comes
only from mining *finite* deposits. Every colony therefore runs a water
countdown — sustainability is about mining rhythm + capacity sizing, not
just building.

## Death & stakes

- o2 shortfall at consumption → instant death (`asphyxiation`).
- water/food shortfall → −10 health/sol (+1/sol recovery while fed);
  health ≤ 0 → death (`starvation_or_dehydration`).
- Deaths are permanent: no respawn, no knowledge transfer to survivors.

## Environment

Seeded dust storms: parameters are **scenario data** (default 2% chance
per sol, duration 3–6 sols); a storm halves panel output. This is the
stub of the M4 event system — radiation, equipment failure etc. land as
more scenario-declared event types, not new engine code paths.

## Outcomes (ADR-0006)

Every episode ends in exactly one terminal state, logged in the trace:

| Outcome | Trigger | Meaning as data |
|---------|---------|-----------------|
| `colony_dead` | all agents dead | failed; cause + sol recorded |
| `success` | **net-positive balance streak**: production + that sol's mining covers ALL consumption (crew + structure inputs) for N consecutive sols (default 30) | the colony actually works, not just persists |
| `sol_cap` | alive at the hard ceiling (default 120 sols) | neither won nor died; stalled |

Note the strictness: a colony that survives only because an agent mines
every day is *not* self-sustaining in the water ledger — `success`
demands a built, balanced economy. Three outcomes keep "died at 40",
"stuck at cap" and "won at 45" as three distinct results.

## Scenarios (ADR-0007)

One declarative JSON file each; the engine never edits code to add one.
A scenario sets: map (procedural+seed or fixed rows+deposits), base,
starting storage/caps, deposit densities, event parameters, win streak,
sol cap. The full scenario dict + its hash are embedded in every trace
header (ADR-0008 attribution: `scenario_hash`, `code_commit`, `version`,
`prompt_version`, `prompt_hash`, `model_id`, `ts_start`). The agent's
rulebook is the versioned file `marscolony/worldbook.md`; any text change
bumps its `WORLDBOOK-VERSION` and its hash rides in the header, so runs
from different prompt versions never share a comparison (freeze policy).

Bundled (`marscolony/scenarios/`):

- **baseline** — standard procedural 32×32, mild storms. The A/B reference
  map family; use fixed seed lists for model comparisons.
- **storm_heavy** — ~12%/sol storms, 4–8 sols. Repeated power-collapse
  stress: measures response to surprise, recovery planning.
- **depletion** — fixed 21×17 map. A 40-unit ice seam visible from spawn,
  a ~190-unit near patch that dries mid-run, a 280-unit far ridge at
  distance ~11. The exploration-vs-exploitation test, no storm noise.

Reserved doors: `ownership` flag (private inventories/gifting = future
scenario family), comms — both deferred behind their own future ADRs
(ADR-0009); M4 multi-agent = world-shared, no message channel.

## Known behavior at v0.3 (measured, not claimed)

With the scripted reference bot: procedural world generation changed with
the deposit layer, so "build once, mine forever" no longer works — most
baseline seeds die sols 57–110 as nearby deposits dry; `depletion` kills
a fully built colony ~sol 56; sustained net-positive streaks reach ~6
(the win needs 30). `success` is proven reachable in tests but the
reference bot can't yet win — the bar models will be scored against is
real pressure, and the outcome distribution separates thriving from
capping from dying.

## Version history of this guidebook

- **0.3.0-engine** (2026-11-25, branch `engine`) — first guidebook.
  Describes: deposits layer & finite mining (ADR-0004), three outcomes
  (ADR-0006), declarative scenarios (ADR-0007), trace attribution
  (ADR-0008). Prior (0.2.0-m2, `fabian` branch): ice was a terrain char,
  only terminal state was extinction, no scenario files.
