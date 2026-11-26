"""M3 harness tests — offline, deterministic, no network (FakeClient)."""

import hashlib
import json
import os
import tempfile
import unittest

from marscolony import rules
from marscolony.harness import (LLMPolicy, extract_action,
                                load_worldbook, prompt_info,
                                render_observation, validate_action_shape,
                                write_sidecar)
from marscolony.rules import step
from marscolony.runner import run_episode
from marscolony.trace import replay
from marscolony.world import make_state


class FakeClient:
    """Canned replies, cycled. Records (system, messages) per call."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, system, messages):
        self.calls.append({"system": system, "messages": list(messages)})
        return self.replies[min(len(self.calls) - 1, len(self.replies) - 1)]


def tmp(name="t.jsonl"):
    return os.path.join(tempfile.mkdtemp(), name)


class TestActionParsing(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(extract_action('{"type":"wait"}'),
                         {"type": "wait"})

    def test_fenced_json(self):
        self.assertEqual(extract_action('```json\n{"type":"mine"}\n```'),
                         {"type": "mine"})

    def test_prose_wrapped_json(self):
        got = extract_action('I will scout. {"type":"move","dx":1,"dy":0} ok?')
        self.assertEqual(got, {"type": "move", "dx": 1, "dy": 0})

    def test_garbage_becomes_engine_logged_action(self):
        act = extract_action("I refuse to choose.")
        self.assertEqual(act["type"], "INVALID_JSON")
        # and the engine logs it as an invalid action, not an exception:
        st = make_state(1, ["a1"])
        st, rep = step(st, [{"agent": "a1", "action": act}])
        self.assertEqual(rep["actions"][0]["status"], "invalid")
        self.assertEqual(rep["actions"][0]["reason"], "unknown_action_type")

    def test_empty_reply(self):
        self.assertEqual(extract_action(""), {"type": "INVALID_JSON"})


class TestObservationRendering(unittest.TestCase):
    def test_render_is_deterministic_text(self):
        st = make_state(4, ["a1"])
        from marscolony.observation import observation
        r1 = render_observation(observation(st, "a1"))
        r2 = render_observation(observation(st, "a1"))
        self.assertEqual(r1, r2)
        for needle in ("SOL 0", "energy", "colony storage", "i" and "terrain",
                       "dust storm"):
            self.assertIn(needle, r1)


class TestLLMPolicyIntegration(unittest.TestCase):
    def test_happy_path_waits_and_survives_short_run(self):
        client = FakeClient(['{"type":"wait"}'])
        path, side = tmp(), tmp("s.jsonl")
        res = run_episode(seed=3, n_agents=1, max_ticks=5, trace_path=path,
                          policy_factory=lambda: LLMPolicy(client, "a1"),
                          llm_log_path=side)
        self.assertEqual(res["outcome"], "sol_cap")   # alive at the cap
        with open(side) as f:
            entries = [json.loads(l) for l in f]
        self.assertEqual(len(entries), 5)
        self.assertTrue(all(e["parsed"] == {"type": "wait"} for e in entries))
        self.assertTrue(all(e["agent"] == "a1" for e in entries))

    def test_feedback_of_rejected_action_reaches_next_prompt(self):
        client = FakeClient([  # sol0: illegal mine (spawn is not ice)
            '{"type":"mine"}',
            '{"type":"wait"}',   # sol1 — prompt must carry the rejection
            '{"type":"wait"}',
        ])
        run_episode(seed=3, n_agents=1, max_ticks=2, trace_path=tmp(),
                    policy_factory=lambda: LLMPolicy(client, "a1"))
        second_prompt = client.calls[1]["messages"][-1]["content"]
        self.assertIn("REJECTED", second_prompt)
        self.assertIn("no_deposit", second_prompt)

    def test_conversation_window_bounds_memory(self):
        client = FakeClient(['{"type":"wait"}'])
        pol = LLMPolicy(client, "a1", window=3)
        st = make_state(3, ["a1"])
        from marscolony.observation import observation
        for _ in range(10):
            pol(observation(st, "a1"), {})
            users = [m for m in pol.convo if m["role"] == "user"]
            self.assertLessEqual(len(users), 3)

    def test_multi_agent_sidecar_and_replay(self):
        client = FakeClient(['{"type":"wait"}'])
        path = tmp()
        run_episode(seed=9, n_agents=3, max_ticks=4, trace_path=path,
                    policy_factory=lambda: LLMPolicy(client, "a?"),
                    llm_log_path=None)
        rep = replay(path)
        self.assertEqual(rep["ticks_checked"], 4)
        self.assertEqual(rep["mismatches"], [])


class TestSidecarFormat(unittest.TestCase):
    def test_sidecar_is_jsonl_sorted(self):
        pol = LLMPolicy(FakeClient(['{"type":"wait"}']), "a1")
        pol.log = [{"sol": 0, "agent": "a1", "raw": "x",
                    "parsed": {"type": "wait"}}]
        path = tmp("side.jsonl")
        write_sidecar(path, {"a1": pol})
        with open(path) as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["agent"], "a1")


class TestExperimentMatrix(unittest.TestCase):
    def test_matrix_offline_and_table(self):
        from marscolony.experiment import comparison_table, run_matrix
        out = tempfile.mkdtemp()

        def fake_factory(model):
            def make(agent_id):
                # model name is echoed into replies: proves model wiring
                return LLMPolicy(
                    FakeClient([f'{{"type":"wait"}} (from {model})']),
                    agent_id)
            return make

        results = run_matrix(["model-A", "model-B"], [1, 2], n_agents=1,
                             sols=4, out_dir=out, base_url="x",
                             api_key_env="NOPE", client_factory=fake_factory)
        self.assertEqual(len(results), 4)
        self.assertEqual({r["model"] for r in results},
                         {"model-A", "model-B"})
        for r in results:
            self.assertTrue(os.path.exists(r["trace"]))
            self.assertTrue(os.path.exists(r["llm_log"]))
            self.assertEqual(r["sols_survived"], 4)
            self.assertEqual(r["invalid_actions"]["total"], 0)
        table = comparison_table(results)
        self.assertIn("model-A", table)
        self.assertEqual(len(table.splitlines()), 6)  # hdr, rule, 4 rows


class TestWorldbook(unittest.TestCase):
    """ADR-0005: the rulebook is one versioned file, and its numbers must
    not drift from the engine constants it describes."""

    def test_loader_version_and_hash(self):
        wb = load_worldbook()
        self.assertRegex(wb["version"], r"^\d+\.\d+")
        with open(os.path.join(os.path.dirname(
                rules.__file__), "worldbook.md"), encoding="utf-8") as f:
            self.assertEqual(
                wb["sha256"],
                hashlib.sha256(f.read().encode("utf-8")).hexdigest())

    def test_prompt_info_block(self):
        pi = prompt_info(model_id="m/1")
        self.assertEqual(set(pi),
                         {"prompt_version", "prompt_hash", "model_id"})
        self.assertEqual(pi["model_id"], "m/1")

    def test_numbers_match_engine(self):
        wb = load_worldbook()["text"]
        for act, cost in rules.ACTION_COST.items():
            self.assertRegex(
                wb, rf"{act}:\s*energy \+?{cost}",
                f"worldbook energy cost for {act} drifted from engine")
        self.assertRegex(wb, rf"yield {rules.MINE_YIELD} water")
        self.assertRegex(wb, rf"restores \+{rules.REST_ENERGY} energy")
        for stype, cost in rules.BUILD_COST.items():
            self.assertRegex(wb, rf"{stype}:\s*cost {cost}",
                             f"worldbook build cost for {stype} drifted")
        self.assertRegex(wb, r"1 o2, 1 water, 1 food")
        self.assertEqual(rules.CONSUME, {"o2": 1, "water": 1, "food": 1})

    def test_tokens_filled(self):
        from marscolony.harness import render_worldbook
        out = render_worldbook(load_worldbook()["text"], "a7",
                               {"sustained_sols": 30, "sol_cap": 120})
        self.assertNotIn("{{", out)
        self.assertIn("agent a7", out)
        self.assertIn("for 30 consecutive", out)
        self.assertIn("sol 120", out)


class TestActionShapeValidation(unittest.TestCase):
    """Only FORMAT-level invalidity is retried; decision-level rejections
    stay with the engine (they are the behavioral signal)."""

    def test_valid_shapes_pass(self):
        for a in ({"type": "wait"}, {"type": "rest"}, {"type": "mine"},
                  {"type": "move", "dx": 1, "dy": 0},
                  {"type": "build", "structure": "panel"}):
            self.assertIsNone(validate_action_shape(a))

    def test_format_reasons(self):
        self.assertEqual(validate_action_shape({"type": "INVALID_JSON"}),
                         "invalid_json")
        self.assertEqual(validate_action_shape("not even a dict"),
                         "invalid_json")
        self.assertEqual(validate_action_shape({"type": "fly"}),
                         "unknown_action_type")
        self.assertEqual(
            validate_action_shape({"type": "move", "dx": 2, "dy": 0}),
            "malformed_move")
        self.assertEqual(
            validate_action_shape({"type": "move", "dx": 1, "dy": 1}),
            "malformed_move")
        self.assertEqual(
            validate_action_shape({"type": "move", "dx": 1}),
            "malformed_move")
        self.assertEqual(
            validate_action_shape({"type": "build", "structure": "reactor"}),
            "unknown_structure_type")

    def test_decision_level_actions_pass_shape_gate(self):
        # spatial/resource legality is the ENGINE's call, never retried:
        for a in ({"type": "mine"},                      # no_deposit etc.
                  {"type": "build", "structure": "panel"}):
            self.assertIsNone(validate_action_shape(a))


class TestRepairRetry(unittest.TestCase):
    """ADR-0005: exactly one repair retry, then auto-wait. Retry counts
    are logged so 'bad at JSON' is separable from 'bad decisions'."""

    def _obs(self):
        st = make_state(3, ["a1"])
        from marscolony.observation import observation
        return observation(st, "a1")

    def test_valid_first_try_single_call(self):
        c = FakeClient(['{"type":"wait"}'])
        pol = LLMPolicy(c, "a1")
        self.assertEqual(pol(self._obs(), {}), {"type": "wait"})
        self.assertEqual(len(c.calls), 1)
        self.assertEqual(pol.log[-1]["retries"], 0)
        self.assertEqual(pol.log[-1]["resolved"], "model")

    def test_one_retry_recovers(self):
        c = FakeClient(["I will think about it.", '{"type":"rest"}'])
        pol = LLMPolicy(c, "a1")
        self.assertEqual(pol(self._obs(), {}), {"type": "rest"})
        self.assertEqual(len(c.calls), 2)                     # exactly one
        retry_prompt = c.calls[1]["messages"][-1]["content"]
        self.assertIn("REJECTED", retry_prompt)
        self.assertIn("invalid_json", retry_prompt)
        self.assertEqual(c.calls[1]["messages"][-2]["content"],
                         "I will think about it.")            # shown back
        e = pol.log[-1]
        self.assertEqual(e["retries"], 1)
        self.assertEqual(e["resolved"], "retry")
        self.assertEqual(len(e["attempts"]), 2)
        self.assertEqual(e["attempts"][0]["reason"], "invalid_json")
        self.assertNotIn("reason", e["attempts"][1])          # repaired one

    def test_two_failures_auto_wait(self):
        c = FakeClient(["nonsense", "still nonsense"])
        pol = LLMPolicy(c, "a1")
        self.assertEqual(pol(self._obs(), {}), {"type": "wait"})
        self.assertEqual(len(c.calls), 2)                     # never a 3rd
        e = pol.log[-1]
        self.assertEqual(e["resolved"], "auto_wait")
        self.assertEqual(e["parsed"], {"type": "wait"})
        self.assertEqual(e["attempts"][1]["reason"], "invalid_json")
        # the sent wait is HONEST in the trace; the NOTE tells the agent
        # next sol that it was auto-waited, not chosen (turn 2's first
        # call is index 2: [t1c1, t1c2, t2c1, t2c2]):
        pol(self._obs(), {})
        self.assertIn("auto-waited", c.calls[2]["messages"][-1]["content"])

    def test_auto_wait_action_replays_clean(self):
        c = FakeClient(["junk", "junk"])
        path = tmp()
        res = run_episode(seed=3, n_agents=1, max_ticks=3, trace_path=path,
                          policy_factory=lambda: LLMPolicy(c, "a1"))
        self.assertEqual(res["outcome"], "sol_cap")
        rep = replay(path)
        self.assertEqual(rep["mismatches"], [])

    def test_unknown_type_also_retries(self):
        c = FakeClient(['{"type":"fly","dx":1}', '{"type":"wait"}'])
        pol = LLMPolicy(c, "a1")
        self.assertEqual(pol(self._obs(), {}), {"type": "wait"})
        self.assertEqual(pol.log[-1]["resolved"], "retry")
        self.assertEqual(pol.log[-1]["attempts"][0]["reason"],
                         "unknown_action_type")


class TestVerbatimHistory(unittest.TestCase):
    def test_default_keeps_full_history(self):
        c = FakeClient(['{"type":"wait"}'])
        pol = LLMPolicy(c, "a1")
        st = make_state(3, ["a1"])
        from marscolony.observation import observation
        for _ in range(12):
            pol(observation(st, "a1"), {})
        users = [m for m in pol.convo if m["role"] == "user"]
        self.assertEqual(len(users), 12)      # nothing dropped

    def test_window_override_still_bounds(self):
        c = FakeClient(['{"type":"wait"}'])
        pol = LLMPolicy(c, "a1", window=3)
        st = make_state(3, ["a1"])
        from marscolony.observation import observation
        for _ in range(10):
            pol(observation(st, "a1"), {})
            users = [m for m in pol.convo if m["role"] == "user"]
            self.assertLessEqual(len(users), 3)


class TestHeaderAttribution(unittest.TestCase):
    """ADR-0008: prompt side of the header (worldbook version/hash, model)."""

    def _header(self, path):
        with open(path, encoding="utf-8") as f:
            return json.loads(f.readline())

    def test_scripted_run_has_null_prompt_fields(self):
        path = tmp()
        run_episode(seed=3, n_agents=1, max_ticks=2, trace_path=path)
        h = self._header(path)
        self.assertIsNone(h["prompt_hash"])
        self.assertIsNone(h["model_id"])

    def test_llm_run_header_carries_worldbook_identity(self):
        path = tmp()
        run_episode(seed=3, n_agents=1, max_ticks=2, trace_path=path,
                    policy_factory=lambda: LLMPolicy(FakeClient(
                        ['{"type":"wait"}']), "a1"),
                    prompt_info=prompt_info(model_id="fake/x"))
        h = self._header(path)
        wb = load_worldbook()
        self.assertEqual(h["prompt_hash"], wb["sha256"])
        self.assertEqual(h["prompt_version"], wb["version"])
        self.assertEqual(h["model_id"], "fake/x")
        # additive header must not disturb replay:
        self.assertEqual(replay(path)["mismatches"], [])


class TestSidecarRetryTelemetry(unittest.TestCase):
    def test_sidecar_metrics_offline(self):
        from marscolony.experiment import sidecar_harness_metrics
        pol = LLMPolicy(FakeClient(["junk", '{"type":"wait"}',
                                    "junk", "junk"]), "a1")
        st = make_state(3, ["a1"])
        from marscolony.observation import observation
        pol(observation(st, "a1"), {})      # turn 1: retry -> repaired
        pol(observation(st, "a1"), {})      # turn 2: retry -> auto_wait
        path = tmp("s.jsonl")
        write_sidecar(path, {"a1": pol})
        m = sidecar_harness_metrics(path)
        self.assertEqual(m, {"retries_total": 2, "turns": 2,
                             "auto_waits": 1})

    def test_missing_sidecar_zero_metrics(self):
        from marscolony.experiment import sidecar_harness_metrics
        self.assertEqual(sidecar_harness_metrics(tmp("none.jsonl")),
                         {"retries_total": 0, "turns": 0, "auto_waits": 0})


if __name__ == "__main__":
    unittest.main(verbosity=2)
