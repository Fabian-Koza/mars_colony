"""CLI:  python -m marscolony run --seed 7 --agents 2 --sols 60 --out trace.jsonl
        python -m marscolony replay --trace trace.jsonl
        python -m marscolony metrics --trace trace.jsonl
"""

import argparse
import json
import os
import sys

from .runner import metrics_from_trace, run_episode
from .trace import replay


def main(argv=None):
    p = argparse.ArgumentParser(prog="marscolony")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run one episode (scripted bot or LLM)")
    r.add_argument("--seed", type=int, default=42)
    r.add_argument("--agents", type=int, default=2)
    r.add_argument("--sols", type=int, default=60)
    r.add_argument("--scenario", default="baseline",
                   help="bundled scenario name or path to a scenario .json "
                        "(ADR-0007); e.g. baseline, storm_heavy, depletion")
    r.add_argument("--out", default="trace.jsonl")
    r.add_argument("--policy", choices=["scripted", "llm"], default="scripted")
    r.add_argument("--model", default=os.environ.get("MARS_MODEL", ""))
    r.add_argument("--base-url",
                   default=os.environ.get("OPENAI_BASE_URL", ""))
    r.add_argument("--api-key-env", default="OPENAI_API_KEY")
    r.add_argument("--llm-log", default=None,
                   help="sidecar path for raw model outputs "
                        "(default: <out>.llm.jsonl)")

    rp = sub.add_parser("replay", help="re-execute a trace and verify hashes")
    rp.add_argument("--trace", required=True)

    mp = sub.add_parser("metrics", help="offline metrics from a trace file")
    mp.add_argument("--trace", required=True)

    vz = sub.add_parser("visualize",
                        help="standalone HTML replay of a trace "
                             "(+ raw-LLM sidecar if present)")
    vz.add_argument("--trace", required=True)
    vz.add_argument("--out", default=None)

    sw = sub.add_parser("sweep", help="model x seed matrix, comparable traces")
    sw.add_argument("--models", required=True,
                    help="comma-separated model ids")
    sw.add_argument("--seeds", default="42",
                    help="comma-separated seeds")
    sw.add_argument("--agents", type=int, default=2)
    sw.add_argument("--sols", type=int, default=60)
    sw.add_argument("--outdir", default="sweep")
    sw.add_argument("--scenario", default="baseline",
                    help="bundled scenario name or scenario .json path")
    sw.add_argument("--base-url",
                    default=os.environ.get("OPENAI_BASE_URL", ""))
    sw.add_argument("--api-key-env", default="OPENAI_API_KEY")

    args = p.parse_args(argv)

    if args.cmd == "run":
        kwargs = {}
        if args.policy == "llm":
            from .harness import LLMPolicy, OpenAICompatClient, prompt_info
            api_key = os.environ.get(args.api_key_env, "")
            if not args.model or not args.base_url or not api_key:
                p.error("llm policy needs --model, --base-url and "
                        f"${args.api_key_env}")
            client = OpenAICompatClient(args.base_url, api_key, args.model)
            counter = {"n": 0}   # policy objects are built in agent-id order

            def factory():
                counter["n"] += 1
                return LLMPolicy(client, f"a{counter['n']}")
            kwargs["policy_factory"] = factory
            kwargs["llm_log_path"] = args.llm_log or (args.out + ".llm.jsonl")
            kwargs["prompt_info"] = prompt_info(model_id=args.model)
        result = run_episode(args.seed, args.agents, args.sols, args.out,
                             scenario=args.scenario, **kwargs)
        print(json.dumps(result, indent=2, sort_keys=True))
    elif args.cmd == "replay":
        res = replay(args.trace)
        if res.get("version_mismatch"):
            from . import __version__ as _v
            print(f"replay SKIPPED: trace recorded by engine "
                  f"{res['version_at_record']}, this engine is {_v} — "
                  f"schema differs (ADR-0004/0006). "
                  f"Use the matching version from git history.")
            return 2
        verdict = "OK" if not res["mismatches"] else "MISMATCH"
        print(f"replay {verdict}: {res['ticks_checked']} ticks checked "
              f"(engine version at record: {res['version_at_record']})")
        for m in res["mismatches"][:5]:
            print("  ", m)
        return 0 if verdict == "OK" else 1
    elif args.cmd == "metrics":
        print(json.dumps(metrics_from_trace(args.trace), indent=2, sort_keys=True))
    elif args.cmd == "visualize":
        from .viz import build_html
        out, n, had_raw = build_html(args.trace, args.out)
        print(f"wrote {out} ({n} sols, raw-LLM outputs: "
              f"{'embedded' if had_raw else 'none'})")
    elif args.cmd == "sweep":
        from .experiment import comparison_table, run_matrix, write_results_json
        if not args.base_url or not os.environ.get(args.api_key_env, ""):
            p.error("sweep needs --base-url and "
                    f"${args.api_key_env} set")
        models = [m.strip() for m in args.models.split(",") if m.strip()]
        seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
        results = run_matrix(models, seeds, args.agents, args.sols,
                             args.outdir, args.base_url, args.api_key_env,
                             scenario=args.scenario)
        print(comparison_table(results))
        write_results_json(results, os.path.join(args.outdir, "results.json"))
        print(f"\ntraces + raw-output logs in {args.outdir}/, "
              f"summary in {args.outdir}/results.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
