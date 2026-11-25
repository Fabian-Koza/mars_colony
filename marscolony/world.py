"""World state construction: grid, storage, structures, agents (pure data)."""

from .rng import rand_below

GRID_W = 32
GRID_H = 32
BASE_X, BASE_Y = 16, 16
PASSABLE = ".ib"          # regolith, basalt, ice (crater 'c' is impassable)

CAPS = {"power": 100, "water": 200, "o2": 200, "food": 200}
START_STORAGE = {"power": 20, "water": 40, "o2": 60, "food": 60}


def make_state(seed: int, agent_ids: list) -> dict:
    """Build the tick-0 state. Fully determined by (seed, agent_ids)."""
    rng_box = {"rng": seed & 0xFFFFFFFFFFFFFFFF}

    rows = []
    for _y in range(GRID_H):
        row = []
        for _x in range(GRID_W):
            r = rand_below(rng_box, 100)
            if r < 4:
                row.append("i")   # ice 4%
            elif r < 5:
                row.append("c")   # crater 1%
            elif r < 20:
                row.append("b")   # basalt 15%
            else:
                row.append(".")   # regolith
        rows.append(row)

    # Clear the base neighborhood so spawn is always sane and reachable.
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            rows[BASE_Y + dy][BASE_X + dx] = "."

    state = {
        "seed": seed,
        "tick": 0,
        "rng": rng_box["rng"],
        "grid": {"w": GRID_W, "h": GRID_H, "terrain": ["".join(r) for r in rows]},
        "storage": dict(START_STORAGE),
        "caps": dict(CAPS),
        "structures": [
            {"id": "s1", "type": "base", "x": BASE_X, "y": BASE_Y},
        ],
        "agents": [
            {"id": a, "x": BASE_X, "y": BASE_Y, "energy": 100,
             "health": 100, "alive": True}
            for a in agent_ids
        ],
        "weather": {"storm_ticks_left": 0},
        "next_entity_id": 2,
        "episode_over": None,
    }
    return state


# --- lookup helpers (read-only views over state) ---

def in_bounds(state: dict, x: int, y: int) -> bool:
    return 0 <= x < state["grid"]["w"] and 0 <= y < state["grid"]["h"]


def terrain_at(state: dict, x: int, y: int) -> str:
    return state["grid"]["terrain"][y][x]


def passable_at(state: dict, x: int, y: int) -> bool:
    return in_bounds(state, x, y) and terrain_at(state, x, y) in PASSABLE


def structure_at(state: dict, x: int, y: int):
    for s in state["structures"]:
        if s["x"] == x and s["y"] == y:
            return s
    return None


def agent_by_id(state: dict, agent_id):
    for a in state["agents"]:
        if a["id"] == agent_id:
            return a
    return None
