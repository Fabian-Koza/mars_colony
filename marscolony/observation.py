"""Observation builder — the agent's ENTIRE window on the world (ADR-0002).

Deliberately partial: terrain and deposits visible only within a radius,
other agents visible only nearby. What agents can see is an experimental
variable, so it lives here in one small auditable function, not scattered
in the rules. ADR-0004: deposits are revealed (with remaining amount) when
in range — depleted (amount 0) deposits stay visible, exhaustion is
knowledge the agent earned.
"""

from .scenario import DEFAULT

VIS_RADIUS = 3


def observation(state: dict, agent_id: str) -> dict:
    a = next((x for x in state["agents"] if x["id"] == agent_id), None)
    if a is None:
        return {"error": "unknown_agent"}

    w = state["grid"]["w"]
    h = state["grid"]["h"]
    x0 = max(0, a["x"] - VIS_RADIUS)
    x1 = min(w, a["x"] + VIS_RADIUS + 1)
    y0 = max(0, a["y"] - VIS_RADIUS)
    y1 = min(h, a["y"] + VIS_RADIUS + 1)
    terrain = [state["grid"]["terrain"][y][x0:x1] for y in range(y0, y1)]

    visible_deposits = []
    for cell, dep in sorted(state["deposits"].items()):
        dx, dy = (int(v) for v in cell.split(","))
        if x0 <= dx < x1 and y0 <= dy < y1:
            visible_deposits.append({"x": dx, "y": dy, "amount": dict(dep)})

    visible_agents = [
        {"id": o["id"], "x": o["x"], "y": o["y"], "alive": o["alive"]}
        for o in state["agents"]
        if o["id"] != agent_id
        and abs(o["x"] - a["x"]) <= VIS_RADIUS and abs(o["y"] - a["y"]) <= VIS_RADIUS
    ]
    # Structures are colony-shared knowledge (comms assumption for M2;
    # revisit observability of structures in M4 scenario design).
    structures = [{"type": s["type"], "x": s["x"], "y": s["y"]}
                  for s in state["structures"]]

    sc = state.get("scenario") or DEFAULT
    return {
        "sol": state["tick"],
        "self": {"id": a["id"], "x": a["x"], "y": a["y"],
                 "energy": a["energy"], "health": a["health"]},
        "colony_storage": dict(state["storage"]),
        "structures": structures,
        "visible": {"x0": x0, "y0": y0, "terrain": terrain,
                    "deposits": visible_deposits},
        "nearby_agents": visible_agents,
        "storm": state["weather"]["storm_ticks_left"] > 0,
        # colony goal knowledge (ADR-0006/0007): sustained net-positive streak
        "goal": {"sustained_sols": sc["win"]["sustained_sols"],
                 "streak": state["sustain"]["streak"],
                 "sol_cap": sc.get("sol_cap")},
        "episode_over": state["episode_over"],
    }
