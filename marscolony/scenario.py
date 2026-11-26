"""Scenarios — declarative data files (ADR-0007).

One scenario = one JSON file; the engine never edits code to add one.
Scenarios are merged over DEFAULT (dicts deep-merge, scalars/lists replace),
validated once at load, and embedded verbatim into the run state so the
pure rules layer stays pure. The scenario dict + its hash go into the trace
header (ADR-0008) — a run is fully attributable to scenario data.

Schema (all keys optional, merged over DEFAULT):
  name                str
  map                 {mode: "procedural", w, h, crater_pct, basalt_pct}
                      {mode: "fixed", terrain: [rows], deposits: {"x,y": {...}}}
  base                [x, y]          (default: map center)
  storage, caps       resource dicts
  deposits            {<type>: {yields, density_pct, amount_min, amount_max}}
  events              {storm: {p_pct, dur_min, dur_max}}
  win                 {sustained_sols}   net-positive streak -> success (ADR-0006)
  sol_cap             int                  hard episode ceiling (ADR-0006)
"""

import hashlib
import json
import os

SCENARIO_DIR = os.path.join(os.path.dirname(__file__), "scenarios")

DEFAULT = {
    "name": "baseline",
    "map": {"mode": "procedural", "w": 32, "h": 32,
            "crater_pct": 1, "basalt_pct": 15},
    "base": None,
    "storage": {"power": 20, "water": 40, "o2": 60, "food": 60},
    "caps": {"power": 100, "water": 200, "o2": 200, "food": 200},
    "deposits": {"ice": {"yields": "water", "density_pct": 4,
                         "amount_min": 30, "amount_max": 70}},
    "events": {"storm": {"p_pct": 2, "dur_min": 3, "dur_max": 6}},
    "win": {"sustained_sols": 30},
    "sol_cap": 120,
}


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def canonical_scenario(scenario: dict) -> str:
    return json.dumps(scenario, sort_keys=True, separators=(",", ":"))


def scenario_hash(scenario: dict) -> str:
    return hashlib.sha256(canonical_scenario(scenario).encode()).hexdigest()


def validate(scenario: dict) -> dict:
    """Structural validation of a merged scenario. Raises ValueError."""
    m = scenario["map"]
    if m.get("mode") not in ("procedural", "fixed"):
        raise ValueError(f"bad map mode {m.get('mode')!r}")
    if m["mode"] == "fixed":
        rows = m.get("terrain")
        if not rows or not isinstance(rows, list):
            raise ValueError("fixed map needs terrain rows")
        h, w = len(rows), len(rows[0])
        if any(len(r) != w for r in rows):
            raise ValueError("fixed map rows ragged")
        # geometry is AUTHORITATIVE for fixed maps (DEFAULT's procedural
        # w/h must not leak through the merge)
        m["w"], m["h"] = w, h
        for cell, dep in (m.get("deposits") or {}).items():
            x, y = map(int, cell.split(","))
            if not (0 <= x < w and 0 <= y < h):
                raise ValueError(f"deposit {cell} outside map")
            for dtype in dep:
                if dtype not in scenario["deposits"]:
                    raise ValueError(f"deposit type {dtype!r} undeclared")
    else:
        for k in ("w", "h"):
            if not isinstance(m.get(k), int) or m[k] < 8:
                raise ValueError(f"procedural map needs {k} >= 8")
    for dtype, spec in scenario["deposits"].items():
        if spec.get("yields") not in scenario["caps"]:
            raise ValueError(f"deposit {dtype} yields unknown resource")
        if spec.get("amount_min", 0) > spec.get("amount_max", 0):
            raise ValueError(f"deposit {dtype} amount range inverted")
    if scenario["win"].get("sustained_sols", 1) < 1:
        raise ValueError("win.sustained_sols must be >= 1")
    if scenario.get("sol_cap", 1) < 1:
        raise ValueError("sol_cap must be >= 1")
    return scenario


def load(name_or_path: str) -> dict:
    """Load scenario by name (bundled) or path to a JSON file."""
    path = name_or_path
    if not path.endswith(".json"):
        path = os.path.join(SCENARIO_DIR, f"{name_or_path}.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return validate(_deep_merge(DEFAULT, data))
