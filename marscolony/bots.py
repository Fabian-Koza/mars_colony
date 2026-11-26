"""Scripted bot policy — the M2 validation driver.

Bots consume ONLY the observation dict and keep private memory, exactly like
an LLM agent will in M3. They exist to prove the engine works before any
model is involved, and to serve as the reference client of the interface.

Phase machine (deterministic):
  seek -> mine1 (4x) -> site_panel -> mine2 (3x) -> site_extractor
       -> site_greenhouse -> operated
Rest when energy is low; wait when the water tank is full. Once built out,
the bot is resource-self-sufficient: extractor covers crew O2, greenhouse
covers crew food, and it keeps mining water for the extractors' and its own
consumption.
"""

DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]


def new_memory() -> dict:
    return {"known_ice": [], "ice_at": None, "target": None,
            "phase": "seek", "mined": 0, "built": [],
            "build_spot": None, "spots_used": [],
            "steps": 0, "last": None, "alt": False}


def _terrain_abs(obs: dict, ax: int, ay: int):
    vis = obs["visible"]
    gx, gy = ax - vis["x0"], ay - vis["y0"]
    rows = vis["terrain"]
    if 0 <= gy < len(rows) and 0 <= gx < len(rows[0]):
        return rows[gy][gx]
    return None


def _deposit_amount(obs: dict, x: int, y: int) -> int:
    """Remaining mineable ice on a tile, per ADR-0004 deposit layer."""
    for d in obs["visible"]["deposits"]:
        if d["x"] == x and d["y"] == y:
            return sum(v for v in d["amount"].values() if v > 0)
    return 0


def _known_ice_from_obs(obs: dict, mem: dict):
    """Track tiles with LIVE ice; a revealed-empty deposit is forgotten."""
    vis = obs["visible"]
    for d in vis["deposits"]:
        t = (d["x"], d["y"])
        if d["amount"].get("ice", 0) > 0:
            if t not in mem["known_ice"]:
                mem["known_ice"].append(t)
        elif t in mem["known_ice"]:
            mem["known_ice"].remove(t)


def _nearest_ice(obs: dict, mem: dict):
    me = obs["self"]
    if not mem["known_ice"]:
        return None
    return min(mem["known_ice"], key=lambda t: abs(t[0] - me["x"]) + abs(t[1] - me["y"]))


def _free_spot(obs: dict, mem: dict):
    """First deterministic adjacent tile: passable, unoccupied, ice-free,
    unused (building on ice would bury a finite deposit — ADR-0003/0004)."""
    me = obs["self"]
    occupied = {(s["x"], s["y"]) for s in obs["structures"]}
    for dx, dy in DIRS:
        spot = (me["x"] + dx, me["y"] + dy)
        if _terrain_abs(obs, *spot) in (".", "b") \
                and _deposit_amount(obs, *spot) == 0 \
                and spot not in occupied and spot not in mem["spots_used"]:
            return spot
    return None


def _sign(v: int) -> int:
    return 1 if v > 0 else -1 if v < 0 else 0


def _move(dx: int, dy: int) -> dict:
    return {"type": "move", "dx": dx, "dy": dy}


def _toward(me, tgt) -> dict:
    return _move(_sign(tgt[0] - me["x"]), _sign(tgt[1] - me["y"]))


def scripted_policy(obs: dict, mem: dict) -> dict:
    me = obs["self"]
    x, y = me["x"], me["y"]

    # deposit layer (ADR-0004): know live ice, forget depleted
    _known_ice_from_obs(obs, mem)
    here_dep = _deposit_amount(obs, x, y) > 0
    if here_dep:
        mem["ice_at"] = (x, y)

    if me["energy"] < 7:
        return {"type": "rest"}

    # dispatch with up to a few phase cascades (never returns mid-cascade
    # until an action is produced)
    for _ in range(6):
        p = mem["phase"]

        if p == "seek":
            if here_dep:
                mem["phase"] = _next_phase(mem)
                continue
            return _seek(obs, mem, x, y)

        if p in ("mine1", "mine2"):
            if not here_dep:
                mem["phase"] = "seek"
                mem["target"] = None
                continue
            stop_at = 4 if p == "mine1" else 7
            if mem["mined"] >= stop_at:
                mem["phase"] = "site_panel" if p == "mine1" else "site_extractor"
                continue
            mem["mined"] += 1
            return {"type": "mine"}

        if p in ("site_panel", "site_extractor", "site_greenhouse"):
            need = {"site_panel": "panel", "site_extractor": "extractor",
                    "site_greenhouse": "greenhouse"}[p]
            occupied = {(s["x"], s["y"]) for s in obs["structures"]}
            spot = mem["build_spot"]
            if spot is not None and (_terrain_abs(obs, *spot) in (None, "c")
                                     or spot in occupied):
                spot = None
            if spot is None:
                spot = _free_spot(obs, mem)
                mem["build_spot"] = spot
            if spot is None:
                return {"type": "wait"}
            if (x, y) == spot:
                mem["built"].append(need)
                mem["spots_used"].append(spot)
                mem["build_spot"] = None
                mem["phase"] = "mine2" if need == "panel" else _next_phase(mem)
                mem["target"] = None
                return {"type": "build", "structure": need}
            return _toward(me, spot)

        if p == "operated":
            if not here_dep:
                mem["phase"] = "seek"
                mem["target"] = None
                continue
            if obs["colony_storage"]["water"] >= 200:
                return {"type": "wait"}
            mem["mined"] += 1
            return {"type": "mine"}

        raise AssertionError(f"unknown phase {p!r}")

    raise AssertionError("phase machine failed to settle")


def _next_phase(mem: dict) -> str:
    """Where the survival script should be, given actual progress."""
    if "extractor" not in mem["built"]:
        if "panel" in mem["built"]:
            return "mine2" if mem["mined"] < 7 else "site_extractor"
        return "mine1" if mem["mined"] < 4 else "site_panel"
    if "greenhouse" not in mem["built"]:
        return "site_greenhouse"
    return "operated"


def _seek(obs, mem, x, y) -> dict:
    tgt = mem["target"] or _nearest_ice(obs, mem)
    me = obs["self"]
    mem["steps"] += 1
    if tgt is None:
        dx, dy = DIRS[(mem["steps"] // 5) % 4]            # serpentine wander
        return _move(dx, dy)
    mem["target"] = tgt
    if mem["last"] == (x, y, tgt):                        # blocked last step
        mem["alt"] = not mem["alt"]
    mem["last"] = (x, y, tgt)
    ddx, ddy = _sign(tgt[0] - x), _sign(tgt[1] - y)
    if ddx and ddy:
        if mem["alt"]:
            ddx = 0
        else:
            ddy = 0
    return _move(ddx, ddy)
