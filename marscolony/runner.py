"""Experiment harness: drives episodes and produces behavioral metrics.

The loop here is the M3 contract: obs = observation(state, id) -> policy ->
validated action -> step. Swapping scripted_policy for an LLM call is the
only change M3 needs.
"""

from .bots import new_memory, scripted_policy
from .observation import observation
from .rules import step
from .trace import TraceWriter
from .world import make_state


def run_episode(seed: int, n_agents: int, max_ticks: int, trace_path: str,
                policy=scripted_policy, memory_factory=new_memory,
                policy_factory=None, llm_log_path=None) -> dict:
    """Run one episode. `policy_factory` (M3): zero-arg callable creating a
    fresh policy object per agent; if a policy has .on_results(list), the
    runner feeds it that agent's resolved actions after each tick.
    `llm_log_path`: write raw-model-output sidecar at the end."""
    state = make_state(seed, [f"a{i+1}" for i in range(n_agents)])
    mems = {a["id"]: memory_factory() for a in state["agents"]}
    policies = ({a["id"]: policy_factory() for a in state["agents"]}
                if policy_factory else {})
    writer = TraceWriter(trace_path, state)

    deaths = []
    ticks = 0
    while ticks < max_ticks and state["episode_over"] is None:
        actions = []
        for a in sorted(state["agents"], key=lambda x: x["id"]):
            if not a["alive"]:
                continue
            obs = observation(state, a["id"])
            pol = policies.get(a["id"], policy)
            actions.append({"agent": a["id"], "action": pol(obs, mems[a["id"]])})
        state, report = step(state, actions)
        for pid, pol in policies.items():
            if hasattr(pol, "on_results"):
                pol.on_results([r for r in report["actions"]
                                if r["agent"] == pid])
        deaths.extend(report["deaths"])
        writer.tick(report)
        ticks += 1

    reason = "max_ticks_reached" if state["episode_over"] is None else "extinction"
    writer.close(reason, ticks)
    if llm_log_path and policies:
        from .harness import write_sidecar
        write_sidecar(llm_log_path, policies)

    return {
        "seed": seed,
        "sols_survived": (state["episode_over"]["sol"] + 1
                          if state["episode_over"] else ticks),
        "episode_over": state["episode_over"],
        "deaths": deaths,
        "final_storage": state["storage"],
        "structures": [s["type"] for s in state["structures"]],
        "trace": trace_path,
    }


def metrics_from_trace(trace_path: str) -> dict:
    """Offline metrics — computable from the trace file alone (design note)."""
    import json
    invalid = {"total": 0, "by_reason": {}}
    ok_actions = 0
    events = []
    last_hash = None
    with open(trace_path, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec["kind"] != "tick":
                continue
            last_hash = rec["state_hash"]
            events.extend(rec["events"])
            for r in rec["actions"]:
                if r["status"] == "ok":
                    ok_actions += 1
                else:
                    invalid["total"] += 1
                    by = invalid["by_reason"]
                    by[r["reason"]] = by.get(r["reason"], 0) + 1
    return {"ok_actions": ok_actions, "invalid_actions": invalid,
            "events": events, "final_state_hash": last_hash}
