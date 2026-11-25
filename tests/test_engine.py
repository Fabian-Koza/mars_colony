"""M2 engine kernel tests: determinism, replay, rules math, deaths, validation."""

import os
import tempfile
import unittest

from marscolony.bots import new_memory, scripted_policy
from marscolony.observation import observation
from marscolony.rules import step, state_hash
from marscolony.runner import run_episode
from marscolony.trace import replay
from marscolony.world import make_state


def act(agent, **action):
    return {"agent": agent, "action": action}


def tmp_trace(name="t.jsonl"):
    return os.path.join(tempfile.mkdtemp(), name)


class TestPurityAndDeterminism(unittest.TestCase):
    def test_step_does_not_mutate_input(self):
        st = make_state(1, ["a1"])
        before = state_hash(st)
        step(st, [act("a1", type="wait")])
        self.assertEqual(state_hash(st), before)

    def test_same_seed_same_trajectory(self):
        h1 = []
        h2 = []
        for hashes in (h1, h2):
            st = make_state(7, ["a1", "a2"])
            mems = {a["id"]: new_memory() for a in st["agents"]}
            for _ in range(40):
                actions = []
                for a in sorted(st["agents"], key=lambda x: x["id"]):
                    if a["alive"]:
                        actions.append(act(a["id"], **scripted_policy(
                            observation(st, a["id"]), mems[a["id"]]))
                        )
                st, rep = step(st, actions)
                hashes.append(rep["state_hash"])
        self.assertEqual(h1, h2)
        self.assertEqual(len(set(h1)), len(h1))  # not stuck at one hash

    def test_different_seed_different_trajectory(self):
        sa, _ = step(make_state(1, ["a1"]), [act("a1", type="wait")])
        sb, _ = step(make_state(2, ["a1"]), [act("a1", type="wait")])
        self.assertNotEqual(state_hash(sa), state_hash(sb))

    def test_replay_matches_run(self):
        path = tmp_trace()
        run_episode(seed=11, n_agents=2, max_ticks=50, trace_path=path)
        res = replay(path)
        self.assertEqual(res["ticks_checked"], 50)
        self.assertEqual(res["mismatches"], [])


class TestActionValidation(unittest.TestCase):
    def test_invalid_actions_are_logged_not_raised(self):
        st = make_state(3, ["a1"])
        bad = [
            (act("ghost", type="wait"), "unknown_agent"),
            (act("a1", type="self_destruct"), "unknown_action_type"),
            (act("a1", type="mine"), "not_on_ice"),
            (act("a1", type="build", structure="death_star"),
             "unknown_structure_type"),
            (act("a1", type="build", structure="panel"), "tile_occupied"),
        ]
        st, rep = step(st, [intent for intent, _ in bad])
        reasons = [r["reason"] for r in rep["actions"]]
        # step() resolves in agent-id order (a1... before ghost)
        expected = [reason for _, reason in sorted(bad, key=lambda b: str(b[0]["agent"]))]
        self.assertEqual(reasons, expected)
        self.assertTrue(all(r["status"] == "invalid" for r in rep["actions"]))

    def test_move_bounds_and_terrain(self):
        st = make_state(5, ["a1"])
        a = st["agents"][0]
        a["x"], a["y"] = 0, 0
        st, rep = step(st, [act("a1", type="move", dx=-1, dy=0)])
        self.assertEqual(rep["actions"][0]["reason"],
                         "impassable_or_out_of_bounds")
        self.assertEqual(a["energy"], 100)  # invalid: energy not spent

    def test_malformed_move(self):
        st = make_state(5, ["a1"])
        st, rep = step(st, [act("a1", type="move", dx=2, dy=0)])
        self.assertEqual(rep["actions"][0]["reason"], "malformed_move")

    def test_energy_gate_and_costs(self):
        st = make_state(5, ["a1"])
        st["agents"][0]["energy"] = 1
        st, rep = step(st, [act("a1", type="move", dx=1, dy=0)])
        self.assertEqual(rep["actions"][0]["reason"], "insufficient_energy")
        st, rep = step(st, [act("a1", type="wait")])
        self.assertEqual(rep["actions"][0]["status"], "ok")
        self.assertEqual(st["agents"][0]["energy"], 1)  # wait costs 0


class TestSystemsMath(unittest.TestCase):
    def _state_with(self, structures, storage):
        st = make_state(9, ["a1"])
        st["structures"] = [dict(base, id=f"s{i+1}")
                            for i, base in enumerate(structures)]
        st["storage"] = storage
        st["agents"] = []          # isolate systems from consumption
        return st

    def test_extractor_math(self):
        st = self._state_with(
            [{"type": "base", "x": 16, "y": 16},
             {"type": "extractor", "x": 5, "y": 5}],
            {"power": 5, "water": 10, "o2": 0, "food": 5})
        st, _ = step(st, [])
        self.assertEqual(st["storage"], {"power": 4, "water": 8, "o2": 2, "food": 5})

    def test_extractor_stars_without_inputs(self):
        st = self._state_with(
            [{"type": "base", "x": 16, "y": 16},
             {"type": "extractor", "x": 5, "y": 5}],
            {"power": 0, "water": 10, "o2": 0, "food": 5})
        st, _ = step(st, [])
        self.assertEqual(st["storage"]["o2"], 0)

    def test_panel_halved_in_storm(self):
        st = self._state_with(
            [{"type": "base", "x": 16, "y": 16},
             {"type": "panel", "x": 5, "y": 5}],
            {"power": 0, "water": 0, "o2": 0, "food": 0})
        st["weather"]["storm_ticks_left"] = 2
        st, _ = step(st, [])
        self.assertEqual(st["storage"]["power"], 1)   # 1 in storm, not 2

    def test_power_capped(self):
        st = self._state_with(
            [{"type": "base", "x": 16, "y": 16},
             {"type": "panel", "x": 5, "y": 5}],
            {"power": 100, "water": 0, "o2": 0, "food": 0})
        st, _ = step(st, [])
        self.assertEqual(st["storage"]["power"], 100)


class TestDeathsAndEpisode(unittest.TestCase):
    def test_asphyxiation_kills_and_ends_episode(self):
        st = make_state(9, ["a1"])
        st["storage"]["o2"] = 0
        st, rep = step(st, [act("a1", type="wait")])
        self.assertEqual(rep["deaths"],
                         [{"agent": "a1", "sol": 0, "cause": "asphyxiation"}])
        self.assertIsNotNone(st["episode_over"])

    def test_starvation_kills_after_ten_sols(self):
        st = make_state(9, ["a1"])
        st["storage"]["water"] = 0
        deaths = []
        for _ in range(12):
            if st["episode_over"]:
                break
            st, rep = step(st, [act("a1", type="wait")])
            deaths.extend(rep["deaths"])
        self.assertEqual(len(deaths), 1)
        self.assertEqual(deaths[0]["cause"], "starvation_or_dehydration")
        self.assertEqual(deaths[0]["sol"], 9)   # 10 sols of -10 health

    def test_dead_agent_actions_rejected(self):
        st = make_state(9, ["a1"])
        st["storage"]["o2"] = 0
        st, _ = step(st, [])
        st, rep = step(st, [act("a1", type="wait")])
        self.assertEqual(rep["actions"][0]["reason"], "agent_dead")

    def test_actions_ignored_after_episode_over(self):
        st = make_state(9, ["a1"])
        st["storage"]["o2"] = 0
        st, _ = step(st, [])
        st["agents"][0]["alive"] = True  # resurrect to test the gate itself
        st, rep = step(st, [act("a1", type="wait")])
        self.assertEqual(rep["actions"][0]["reason"], "episode_over")


class TestScriptedBotIntegration(unittest.TestCase):
    def test_bot_builds_infrastructure_and_survives(self):
        path = tmp_trace()
        res = run_episode(seed=7, n_agents=1, max_ticks=60, trace_path=path)
        self.assertIn("panel", res["structures"])
        self.assertIn("extractor", res["structures"])
        self.assertIn("greenhouse", res["structures"])
        self.assertIsNone(res["episode_over"])
        self.assertEqual(res["sols_survived"], 60)
        self.assertEqual(res["deaths"], [])


class TestObservationContract(unittest.TestCase):
    def test_observation_is_partial(self):
        st = make_state(4, ["a1", "a2"])
        st["agents"][1]["x"], st["agents"][1]["y"] = 0, 0   # far away
        obs = observation(st, "a1")
        self.assertNotIn("a2", [a["id"] for a in obs["nearby_agents"]])
        self.assertEqual(len(obs["visible"]["terrain"][0]), 7)  # radius-3 window

    def test_observation_is_json_serializable(self):
        import json
        st = make_state(4, ["a1"])
        json.dumps(observation(st, "a1"), sort_keys=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
