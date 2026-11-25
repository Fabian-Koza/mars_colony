"""JSONL trace writer + deterministic replayer.

Format (one JSON object per line):
  {"kind":"run",  seed, scenario, agents, version}          <- line 1
  {"kind":"tick", tick, actions, events, deaths, state_hash, state}
  {"kind":"end",  reason, ticks}

Replay = re-run step() from the seed with the RECORDED actions and compare
per-tick state hashes. Any mismatch = engine is (or became) non-deterministic
or the code changed under an old trace.
"""

import json

from . import __version__
from .rules import step
from .world import make_state


class TraceWriter:
    def __init__(self, path: str, state: dict):
        self.f = open(path, "w", encoding="utf-8")
        self.f.write(json.dumps({
            "kind": "run", "seed": state["seed"], "version": __version__,
            "agents": [a["id"] for a in state["agents"]],
        }, sort_keys=True) + "\n")

    def tick(self, report: dict):
        rec = {k: report[k] for k in
               ("tick", "actions", "events", "deaths", "state_hash", "state")}
        rec["kind"] = "tick"
        self.f.write(json.dumps(rec, sort_keys=True) + "\n")
        self.f.flush()   # long LLM episodes must be inspectable mid-run

    def close(self, reason: str, ticks: int):
        self.f.write(json.dumps({"kind": "end", "reason": reason,
                                 "ticks": ticks}) + "\n")
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
                state = make_state(rec["seed"], rec["agents"])
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
            "end": end, "version_at_record": header["version"] if header else None}
