"""M3 experiment runner: same scenario x several models, comparable traces.

Because the engine is deterministic (ADR-0001), every model in a matrix gets
the IDENTICAL world: same terrain, same storm schedule, same starting
storage. The only variable is the model. Comparison output per run:
sols survived, ok/invalid actions by reason, structures built, deaths.
"""

import json
import os

from .harness import LLMPolicy, OpenAICompatClient
from .runner import metrics_from_trace, run_episode


def default_client_factory(base_url, api_key_env, model):
    import os as _os

    def make(agent_id):
        client = OpenAICompatClient(base_url,
                                    _os.environ.get(api_key_env, ""), model)
        return LLMPolicy(client, agent_id)
    return make


def run_matrix(models, seeds, n_agents, sols, out_dir, base_url,
               api_key_env, client_factory=None):
    """models x seeds grid. Returns list of per-run result dicts.

    client_factory(model) -> make_policy(agent_id): injectable for tests."""
    os.makedirs(out_dir, exist_ok=True)
    make_for = client_factory or (
        lambda m: default_client_factory(base_url, api_key_env, m))
    results = []
    for model in models:
        for seed in seeds:
            tag = f"{model.replace('/', '_')}__seed{seed}"
            trace = os.path.join(out_dir, f"{tag}.trace.jsonl")
            side = os.path.join(out_dir, f"{tag}.llm.jsonl")
            make_policy = make_for(model)
            counter = {"n": 0}

            def factory(make_policy=make_policy, counter=counter):
                counter["n"] += 1
                return make_policy(f"a{counter['n']}")

            r = run_episode(seed=seed, n_agents=n_agents, max_ticks=sols,
                            trace_path=trace, policy_factory=factory,
                            llm_log_path=side)
            m = metrics_from_trace(trace)
            r.update({"model": model, "sweep_dir": out_dir,
                      "ok_actions": m["ok_actions"],
                      "invalid_actions": m["invalid_actions"],
                      "trace": trace, "llm_log": side})
            results.append(r)
    return results


def comparison_table(results) -> str:
    """Plain-text comparison table (offline, from results+metrics only)."""
    hdr = (f"{'model':38} {'seed':>4} {'surv':>5} {'ok':>5} {'bad':>4} "
           f"{'built':>3} {'deaths':>6}  invalid by reason")
    lines = [hdr, "-" * len(hdr)]
    for r in results:
        built = [s for s in r["structures"] if s != "base"]
        bad = r["invalid_actions"]["total"]
        reasons = ",".join(f"{k}:{v}" for k, v in
                           sorted(r["invalid_actions"]["by_reason"].items()))
        lines.append(f"{r['model']:38} {r['seed']:>4} "
                     f"{r['sols_survived']:>5} {r['ok_actions']:>5} "
                     f"{bad:>4} {len(built):>3} {len(r['deaths']):>6}  {reasons}")
    return "\n".join(lines)


def write_results_json(results, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, sort_keys=True)
