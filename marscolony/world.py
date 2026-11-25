"""World state construction: grid, deposits, storage, structures, agents.

ADR-0004 layering: `terrain` encodes PASSABILITY only ('.'/'b' passable,
'c' crater blocked); extractables live in a sparse `deposits` layer keyed
"x,y" -> {type: remaining_amount}. A tile may hold up to two deposit types
(ADR-0004); each deposit is FINITE — mining withdraws from it, depleted
deposits stay as revealed-but-empty entries (agents can see exhaustion).

State shape is defined by the scenario dict (ADR-0007) embedded in the run
state, so make_state stays a pure function of (seed, agent_ids, scenario).
"""

from .rng import rand_below
from .scenario import DEFAULT

PASSABLE = ".b"           # terrain is passability only (crater 'c' blocks)
MAX_DEPOSIT_TYPES = 2     # ADR-0004: max 2 deposit types per tile


def make_state(seed: int, agent_ids: list, scenario: "dict | None" = None) -> dict:
    """Build the tick-0 state. Fully determined by (seed, agent_ids, scenario)."""
    sc = scenario or DEFAULT
    rng_box = {"rng": seed & 0xFFFFFFFFFFFFFFFF}

    w, h = sc["map"]["w"], sc["map"]["h"]
    bx, by = sc["base"] if sc.get("base") else (w // 2, h // 2)

    if sc["map"]["mode"] == "fixed":
        rows = [list(r) for r in sc["map"]["terrain"]]
        deposits = {cell: dict(dep)
                    for cell, dep in (sc["map"].get("deposits") or {}).items()}
    else:
        crater = sc["map"].get("crater_pct", 1)
        basalt = sc["map"].get("basalt_pct", 15)
        rows = []
        for _y in range(h):
            row = []
            for _x in range(w):
                r = rand_below(rng_box, 100)
                if r < crater:
                    row.append("c")
                elif r < crater + basalt:
                    row.append("b")
                else:
                    row.append(".")
            rows.append(row)
        deposits = {}
        for dtype in sorted(sc["deposits"]):       # deterministic order
            spec = sc["deposits"][dtype]
            dmin, dmax = spec.get("amount_min", 30), spec.get("amount_max", 70)
            for y in range(h):
                for x in range(w):
                    if rand_below(rng_box, 100) < spec.get("density_pct", 0) \
                            and len(deposits.get(f"{x},{y}", {})) < MAX_DEPOSIT_TYPES:
                        cell = deposits.setdefault(f"{x},{y}", {})
                        cell[dtype] = dmin + rand_below(rng_box, dmax - dmin + 1)

    # Clear the base neighborhood so spawn is always sane and reachable
    # (and never bury a finite deposit under the base — ADR-0004).
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if 0 <= by + dy < h and 0 <= bx + dx < w:
                rows[by + dy][bx + dx] = "."
                deposits.pop(f"{bx + dx},{by + dy}", None)

    state = {
        "seed": seed,
        "tick": 0,
        "rng": rng_box["rng"],
        "scenario": sc,
        "grid": {"w": w, "h": h, "terrain": ["".join(r) for r in rows]},
        "deposits": deposits,
        "storage": dict(sc["storage"]),
        "caps": dict(sc["caps"]),
        "structures": [
            {"id": "s1", "type": "base", "x": bx, "y": by},
        ],
        "agents": [
            {"id": a, "x": bx, "y": by, "energy": 100,
             "health": 100, "alive": True}
            for a in agent_ids
        ],
        "weather": {"storm_ticks_left": 0},
        "sustain": {"streak": 0},          # ADR-0006 success tracking
        "next_entity_id": 2,
        "episode_over": None,              # {outcome, sol, ...} — ADR-0006
    }
    return state


# --- lookup helpers (read-only views over state) ---

def in_bounds(state: dict, x: int, y: int) -> bool:
    return 0 <= x < state["grid"]["w"] and 0 <= y < state["grid"]["h"]


def terrain_at(state: dict, x: int, y: int) -> str:
    return state["grid"]["terrain"][y][x]


def passable_at(state: dict, x: int, y: int) -> bool:
    return in_bounds(state, x, y) and terrain_at(state, x, y) in PASSABLE


def deposits_at(state: dict, x: int, y: int):
    return state["deposits"].get(f"{x},{y}")


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
