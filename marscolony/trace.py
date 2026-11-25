"""JSONL trace writer + deterministic replayer.

Format (one JSON object per line):
  {"kind":"run",  seed, agents, version, scenario, scenario_hash,
                 code_commit, ts_start}                      <- line 1
  {"kind":"tick", tick, actions, events, deaths, sustainable_sol,
                 state_hash, state}
  {"kind":"end",  reason, ticks, ts_end}

Header attribution fields follow ADR-0008: a run is fully attributable to
(scenario data, code commit, engine version, wall-clock window).

Replay = re-run step() from the seed + RECORDED scenario with the RECORDED
actions and compare per-tick state hashes. Any mismatch = engine is (or
became) non-deterministic or the code changed under an old trace. Engine
version is checked up front: traces from a different engine version are
reported as a version mismatch, not replayed (the schema itself changed at
0.3.0 — deposits layer, outcomes, ADR-0004/0006).
"""

import json
import os
from datetime import datetime, timezone

from . import __version__
from .rules import step
from .scenario import scenario_hash
from .world import make_state


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _git_commit() -> str:
    """Best-effort commit hash, stdlib only (no subprocess). Works in a
    normal checkout (.git/HEAD -> ref -> object file); returns 'unknown'
    outside a repo."""
    try:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        git = os.path.join(root, ".git")
        if os.path.isfile(git):                      # worktree: gitdir file
            with open(git, encoding="utf-8") as f:
                git = os.path.join(root, f.read().split(": ", 1)[1].strip())
        with open(os.path.join(git, "HEAD"), encoding="utf-8") as f:
            head = f.read().strip()
        if head.startswith("ref: "):
            with open(os.path.join(git, head[len("ref: "):]),
                      encoding="utf-8") as f:
                return f.read().strip()
        return head                                  # detached HEAD: raw hash
    except OSError:
        return "unknown"


class TraceWriter:
    def __init__(self, path: str, state: dict):
        self.f = open(path, "w", encoding="utf-8")
        sc = state.get("scenario")
        self.f.write(json.dumps({
            "kind": "run", "seed": state["seed"], "version": __version__,
            "agents": [a["id"] for a in state["agents"]],
            "scenario": sc,
            "scenario_hash": scenario_hash(sc) if sc else None,
            "code_commit": _git_commit(),
            "ts_start": _utcnow(),
        }, sort_keys=True) + "\n")

    def tick(self, report: dict):
        rec = {k: report[k] for k in
               ("tick", "actions", "events", "deaths", "sustainable_sol",
                "state_hash", "state")}
        rec["kind"] = "tick"
        self.f.write(json.dumps(rec, sort_keys=True) + "\n")
        self.f.flush()   # long LLM episodes must be inspectable mid-run

    def close(self, reason: str, ticks: int):
        self.f.write(json.dumps({"kind": "end", "reason": reason,
                                 "ticks": ticks, "ts_end": _utcnow()}) + "\n")
        self.f.close()


def replay(path: str) -> dict:
    """Re-run a trace; returns {"ticks_checked", "mismatches", "end"}."""
    header = None
    checked = 0
    mismatches = []
    end = None
    state = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec["kind"] == "run":
                header = rec
                if rec["version"] != __version__:
                    return {"ticks_checked": 0, "mismatches": [],
                            "version_mismatch": True, "end": None,
                            "version_at_record": rec["version"]}
                state = make_state(rec["seed"], rec["agents"],
                                   rec.get("scenario"))
            elif rec["kind"] == "tick":
                actions = [{"agent": r["agent"], "action": r["action"]}
                           for r in rec["actions"]]
                if state is None:
                    raise ValueError("trace missing run header")
                state, report = step(state, actions)
                if report["state_hash"] != rec["state_hash"]:
                    mismatches.append({
                        "tick": rec["tick"],
                        "recorded": rec["state_hash"][:12],
                        "replayed": report["state_hash"][:12],
                    })
                checked += 1
            elif rec["kind"] == "end":
                end = rec
    return {"ticks_checked": checked, "mismatches": mismatches,
            "version_mismatch": False,
            "end": end, "version_at_record": header["version"] if header else None}
