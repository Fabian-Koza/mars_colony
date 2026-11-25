"""Experiment harness: drives episodes and produces behavioral metrics.

The loop here is the M3 contract: obs = observation(state, id) -> policy ->
validated action -> step. Swapping scripted_policy for an LLM call is the
only change M3 needs.

Episode semantics (ADR-0006): the engine decides `colony_dead` and
`success`; the runner owns the third terminal state — reaching the sol
ceiling (min of requested max_ticks and scenario sol_cap) yields `sol_cap`.
"""

from .bots import new_memory, scripted_policy
from .observation import observation
from .rules import step
from .scenario import load as load_scenario
from .trace import TraceWriter
from .world import make_state


def run_episode(seed: int, n_agents: int, max_ticks: int, trace_path: str,
                scenario=None, policy=scripted_policy,
                memory_factory=new_memory,
                policy_factory=None, llm_log_path=None) -> dict:
    """Run one episode. `scenario`: dict or scenario name/path (ADR-0007).
    `policy_factory` (M3): zero-arg callable creating a fresh policy object
    per agent; if a policy has .on_results(list), the runner feeds it that
    agent's resolved actions after each tick. `llm_log_path`: write
    raw-model-output sidecar at the end."""
    sc = scenario if isinstance(scenario, dict) or scenario is None \
        else load_scenario(scenario)
    sc = sc or None
    cap = (sc or {}).get("sol_cap", max_ticks)
    max_ticks = min(max_ticks, cap)

    state = make_state(seed, [f"a{i+1}" for i in range(n_agents)], sc)
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

    if state["episode_over"] is None and ticks >= max_ticks:
        state["episode_over"] = {"outcome": "sol_cap", "sol": state["tick"] - 1}
    outcome = state["episode_over"]["outcome"] if state["episode_over"] else "ongoing"
    writer.close(outcome, ticks)
    if llm_log_path and policies:
        from .harness import write_sidecar
        write_sidecar(llm_log_path, policies)

    return {
        "seed": seed,
        "scenario": (sc or {}).get("name", "baseline"),
        "outcome": outcome,
        "sols_survived": (state["episode_over"]["sol"] + 1
                          if state["episode_over"] else ticks),
        "episode_over": state["episode_over"],
        "sustain_streak": state["sustain"]["streak"],
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
    sustainable_sols = 0
    last_hash = None
    outcome = None
    with open(trace_path, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec["kind"] == "end":
                outcome = rec["reason"]
            if rec["kind"] != "tick":
                continue
            last_hash = rec["state_hash"]
            events.extend(rec["events"])
            if rec.get("sustainable_sol"):
                sustainable_sols += 1
            for r in rec["actions"]:
                if r["status"] == "ok":
                    ok_actions += 1
                else:
                    invalid["total"] += 1
                    by = invalid["by_reason"]
                    by[r["reason"]] = by.get(r["reason"], 0) + 1
    return {"ok_actions": ok_actions, "invalid_actions": invalid,
            "events": events, "sustainable_sols": sustainable_sols,
            "outcome": outcome, "final_state_hash": last_hash}
