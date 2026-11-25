"""Observation builder — the agent's ENTIRE window on the world (ADR-0002).

Deliberately partial: terrain visible only within a radius, other agents
visible only nearby. What agents can see is an experimental variable, so it
lives here in one small auditable function, not scattered in the rules.
"""

from .world import GRID_H, GRID_W, terrain_at

VIS_RADIUS = 3


def observation(state: dict, agent_id: str) -> dict:
    a = next((x for x in state["agents"] if x["id"] == agent_id), None)
    if a is None:
        return {"error": "unknown_agent"}

    x0 = max(0, a["x"] - VIS_RADIUS)
    x1 = min(GRID_W, a["x"] + VIS_RADIUS + 1)
    y0 = max(0, a["y"] - VIS_RADIUS)
    y1 = min(GRID_H, a["y"] + VIS_RADIUS + 1)
    terrain = [state["grid"]["terrain"][y][x0:x1] for y in range(y0, y1)]

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

    return {
        "sol": state["tick"],
        "self": {"id": a["id"], "x": a["x"], "y": a["y"],
                 "energy": a["energy"], "health": a["health"]},
        "colony_storage": dict(state["storage"]),
        "structures": structures,
        "visible": {"x0": x0, "y0": y0, "terrain": terrain},
        "nearby_agents": visible_agents,
        "storm": state["weather"]["storm_ticks_left"] > 0,
        "episode_over": state["episode_over"],
    }
