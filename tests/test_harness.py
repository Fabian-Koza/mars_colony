"""M3 harness tests — offline, deterministic, no network (FakeClient)."""

import json
import os
import tempfile
import unittest

from marscolony.harness import (LLMPolicy, extract_action,
                                render_observation, write_sidecar)
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
        self.assertIsNone(res["episode_over"])
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
        self.assertIn("not_on_ice", second_prompt)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
