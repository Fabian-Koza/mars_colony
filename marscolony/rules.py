"""The tick engine: step(state, actions) -> (new_state, report).

Pure over plain data (ADR-0001): deep-copies the incoming state, mutates the
copy, never touches wall-clock or the global `random` module. Fixed tick
order: actions -> production -> consumption/deaths -> environment -> commit.

Invalid actions are LOGGED as first-class data, never raised as errors
(ADR-0002): agent failure modes are behavioral observations.

Engine v0.3 (ADR-0004/0006/0007): mining withdraws from FINITE deposits;
storm parameters come from the scenario; every sol is scored for
sustainability and a sustained streak ends the episode with `success`;
extinction ends it with `colony_dead` (the runner adds `sol_cap`).
"""

import copy
import hashlib
import json

from .rng import rand_below
from .world import (
    agent_by_id, deposits_at, passable_at, structure_at,
)

ACTION_COST = {"move": 2, "mine": 5, "build": 8, "rest": 0, "wait": 0}
BUILD_COST = {"panel": 10, "extractor": 15, "greenhouse": 20}
MINE_YIELD = 8
REST_ENERGY = 10
MAX_ENERGY = 100
MAX_HEALTH = 100
CONSUME = {"o2": 1, "water": 1, "food": 1}
STARVE_DAMAGE = 10


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def state_hash(state: dict) -> str:
    return hashlib.sha256(canonical_json(state).encode()).hexdigest()


def step(state: dict, actions: list) -> tuple:
    """Advance one sol. `actions` = [{"agent": id, "action": {...}}, ...].

    Returns (new_state, report) where report carries the behavioral data for
    this tick: per-action results, events, deaths, and the new state hash.
    """
    s = copy.deepcopy(state)
    results, events, deaths = [], [], []
    # per-sol balance counters for the sustainability score (ADR-0006)
    bal = {"mined_water": 0,
           "power_prod": 0, "o2_prod": 0, "food_prod": 0,
           "water_in": 0, "power_in": 0,
           "cons_o2": 0, "cons_water": 0, "cons_food": 0,
           "shortfall": False}

    # 1. resolve agent actions in deterministic (agent id) order
    for intent in sorted(actions, key=lambda a: str(a.get("agent"))):
        r = _resolve_action(s, intent)
        results.append(r)
        if r["status"] == "ok" and r.get("produced") and r["action"].get("type") == "mine":
            bal["mined_water"] += r["produced"].get("water", 0)

    # 2. production systems (structure id order)
    storm = s["weather"]["storm_ticks_left"] > 0
    for st in sorted(s["structures"], key=lambda x: x["id"]):
        out = s["storage"]
        if st["type"] == "panel":
            gain = 1 if storm else 2
            bal["power_prod"] += gain
            out["power"] = min(out["power"] + gain, s["caps"]["power"])
        elif st["type"] == "extractor":
            if out["water"] >= 2 and out["power"] >= 1:
                out["water"] -= 2
                out["power"] -= 1
                bal["water_in"] += 2
                bal["power_in"] += 1
                bal["o2_prod"] += 2
                out["o2"] = min(out["o2"] + 2, s["caps"]["o2"])
        elif st["type"] == "greenhouse":
            if out["water"] >= 1 and out["power"] >= 1:
                out["water"] -= 1
                out["power"] -= 1
                bal["water_in"] += 1
                bal["power_in"] += 1
                bal["food_prod"] += 2
                out["food"] = min(out["food"] + 2, s["caps"]["food"])

    # 3. consumption + deaths (agent id order)
    for a in sorted(s["agents"], key=lambda x: x["id"]):
        if not a["alive"]:
            continue
        out = s["storage"]
        fed = True
        if out["o2"] >= CONSUME["o2"]:
            out["o2"] -= CONSUME["o2"]
            bal["cons_o2"] += 1
        else:
            bal["shortfall"] = True
            _kill(s, a, "asphyxiation", deaths)
            continue
        if out["water"] >= CONSUME["water"]:
            out["water"] -= CONSUME["water"]
            bal["cons_water"] += 1
        else:
            bal["shortfall"] = True
            fed = False
            a["health"] -= STARVE_DAMAGE
        if out["food"] >= CONSUME["food"]:
            out["food"] -= CONSUME["food"]
            bal["cons_food"] += 1
        else:
            bal["shortfall"] = True
            fed = False
            a["health"] -= STARVE_DAMAGE
        if not fed and a["health"] <= 0:
            _kill(s, a, "starvation_or_dehydration", deaths)
        elif fed and a["health"] < MAX_HEALTH:
            a["health"] = min(MAX_HEALTH, a["health"] + 1)

    # 4. environment / events — sole RNG consumer per tick (besides actions,
    #    which currently draw none). Storm parameters are scenario data
    #    (ADR-0007); rng call pattern is constant, so p_pct=0 stays cheap
    #    and deterministic.
    storm_spec = s.get("scenario", {}).get("events", {}).get("storm", {})
    if s["weather"]["storm_ticks_left"] > 0:
        s["weather"]["storm_ticks_left"] -= 1
        if s["weather"]["storm_ticks_left"] == 0:
            events.append({"type": "storm_end", "sol": s["tick"]})
    elif rand_below(s, 100) < storm_spec.get("p_pct", 2):
        dmin = storm_spec.get("dur_min", 3)
        dmax = storm_spec.get("dur_max", 6)
        dur = dmin + rand_below(s, dmax - dmin + 1)
        s["weather"]["storm_ticks_left"] = dur
        events.append({"type": "storm_start", "sol": s["tick"], "duration": dur})

    # 5. commit — sustainability score (ADR-0006): a sol counts when gross
    #    production (structures + this sol's mining) covers ALL consumption
    #    — crew and structure inputs — with no shortfall. Water only counts
    #    what was actually mined: a colony that must keep mining to stay
    #    alive is NOT self-sustaining in the water ledger.
    alive = [a for a in s["agents"] if a["alive"]]
    sustainable = bool(alive) and not bal["shortfall"] and (
        bal["o2_prod"] >= bal["cons_o2"]
        and bal["food_prod"] >= bal["cons_food"]
        and bal["power_prod"] >= bal["power_in"]
        and bal["mined_water"] >= bal["water_in"] + bal["cons_water"]
    )
    if alive:
        s["sustain"]["streak"] = s["sustain"]["streak"] + 1 if sustainable else 0
    else:
        s["sustain"]["streak"] = 0

    s["tick"] += 1
    if s["episode_over"] is None:
        required = s.get("scenario", {}).get("win", {}).get("sustained_sols", 30)
        if not alive:
            s["episode_over"] = {
                "outcome": "colony_dead",
                "cause": deaths[0]["cause"] if deaths else "unknown",
                "sol": s["tick"] - 1,
            }
            events.append({"type": "episode_over",
                           "outcome": "colony_dead", "sol": s["tick"] - 1})
        elif s["sustain"]["streak"] >= required:
            s["episode_over"] = {"outcome": "success", "sol": s["tick"] - 1,
                                 "sustained_streak": s["sustain"]["streak"]}
            events.append({"type": "episode_over", "outcome": "success",
                           "sol": s["tick"] - 1})

    report = {
        "tick": state["tick"],
        "actions": results,
        "events": events,
        "deaths": deaths,
        "sustainable_sol": sustainable,
        "state_hash": state_hash(s),
        "state": s,
    }
    return s, report


def _kill(state: dict, agent: dict, cause: str, deaths: list):
    agent["alive"] = False
    deaths.append({"agent": agent["id"], "sol": state["tick"], "cause": cause})


def _invalid(intent: dict, reason: str) -> dict:
    return {"agent": intent.get("agent"), "action": intent.get("action"),
            "status": "invalid", "reason": reason, "produced": None}


def _resolve_action(state: dict, intent: dict) -> dict:
    action = intent.get("action") or {}
    a = agent_by_id(state, intent.get("agent"))
    if a is None:
        return _invalid(intent, "unknown_agent")
    if not a["alive"]:
        return _invalid(intent, "agent_dead")
    if state["episode_over"] is not None:
        return _invalid(intent, "episode_over")

    atype = action.get("type")
    if atype not in ACTION_COST:
        return _invalid(intent, "unknown_action_type")
    if a["energy"] < ACTION_COST[atype]:
        return _invalid(intent, "insufficient_energy")

    if atype == "move":
        dx, dy = action.get("dx"), action.get("dy")
        if not isinstance(dx, int) or not isinstance(dy, int) or abs(dx) + abs(dy) != 1:
            return _invalid(intent, "malformed_move")
        nx, ny = a["x"] + dx, a["y"] + dy
        if not passable_at(state, nx, ny):
            return _invalid(intent, "impassable_or_out_of_bounds")
        a["x"], a["y"] = nx, ny

    elif atype == "mine":
        # ADR-0004: mine withdraws from a FINITE deposit on the agent's tile.
        dep = deposits_at(state, a["x"], a["y"])
        if not dep:
            return _invalid(intent, "no_deposit")
        dtype = next((t for t in sorted(dep) if dep[t] > 0), None)
        if dtype is None:
            return _invalid(intent, "deposit_depleted")
        resource = (state.get("scenario", {}).get("deposits", {})
                    .get(dtype, {}).get("yields", "water"))
        free = state["caps"][resource] - state["storage"][resource]
        if free <= 0:
            return _invalid(intent, "storage_full")
        got = min(MINE_YIELD, free, dep[dtype])
        dep[dtype] -= got
        state["storage"][resource] += got
        produced = {resource: got, "deposit_left": dep[dtype]}

    elif atype == "build":
        stype = action.get("structure")
        if stype not in BUILD_COST:
            return _invalid(intent, "unknown_structure_type")
        if structure_at(state, a["x"], a["y"]) is not None:
            return _invalid(intent, "tile_occupied")
        cost = BUILD_COST[stype]
        if state["storage"]["water"] < cost:
            return _invalid(intent, "insufficient_water_for_build")
        state["storage"]["water"] -= cost
        sid = f"s{state['next_entity_id']}"
        state["next_entity_id"] += 1
        state["structures"].append({"id": sid, "type": stype, "x": a["x"], "y": a["y"]})
        produced = {"built": sid, "structure": stype}

    elif atype == "rest":
        a["energy"] = min(MAX_ENERGY, a["energy"] + REST_ENERGY)
        produced = {"energy": a["energy"]}

    # wait: no-op
    a["energy"] -= ACTION_COST[atype]
    result = {"agent": a["id"], "action": action, "status": "ok",
              "reason": None, "produced": locals().get("produced")}
    return result
