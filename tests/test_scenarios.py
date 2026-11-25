"""Engine v0.3 tests — the ADR-conformant build:
deposits (ADR-0004), terminal outcomes (ADR-0006), scenario data
(ADR-0007), trace attribution (ADR-0008)."""

import json
import os
import tempfile
import unittest

from marscolony import scenario as scen
from marscolony.rules import step
from marscolony.runner import run_episode
from marscolony.trace import replay
from marscolony.world import make_state


def act(agent, **action):
    return {"agent": agent, "action": action}


def tmp(name="t.jsonl"):
    return os.path.join(tempfile.mkdtemp(), name)


class TestScenarioData(unittest.TestCase):
    def test_bundled_scenarios_load_and_validate(self):
        for name in ("baseline", "storm_heavy", "depletion"):
            sc = scen.load(name)
            self.assertEqual(sc["name"], name)
            self.assertEqual(len(scen.scenario_hash(sc)), 64)

    def test_hash_is_stable_and_content_sensitive(self):
        a = scen.load("baseline")
        b = scen.load("baseline")
        self.assertEqual(scen.scenario_hash(a), scen.scenario_hash(b))
        b["sol_cap"] = 999
        self.assertNotEqual(scen.scenario_hash(a), scen.scenario_hash(b))

    def test_depletion_is_a_fixed_map(self):
        sc = scen.load("depletion")
        self.assertEqual(sc["map"]["mode"], "fixed")
        self.assertEqual(len(sc["map"]["terrain"]), 17)
        self.assertTrue(all(len(r) == 21 for r in sc["map"]["terrain"]))

    def test_validation_rejects_bad_scenarios(self):
        with self.assertRaises(ValueError):
            scen.validate({"map": {"mode": "procedural", "w": 4, "h": 4},
                           "deposits": {}, "win": {"sustained_sols": 30}})
        bad = scen.load("baseline")
        bad["deposits"]["ore"] = {"yields": "unobtainium"}
        with self.assertRaises(ValueError):
            scen.validate(bad)


class TestDeposits(unittest.TestCase):
    def test_mining_withdraws_finite_deposit_until_depleted(self):
        st = make_state(1, ["a1"], scen.load("depletion"))
        a = st["agents"][0]
        a["x"], a["y"] = 9, 6                     # near patch, 75 ice
        total = 0
        r = {"status": "ok"}
        for _ in range(20):
            st, rep = step(st, [act("a1", type="mine")])
            r = rep["actions"][0]
            if r["status"] != "ok":
                break
            total += r["produced"]["water"]
        self.assertEqual(r["reason"], "deposit_depleted")
        self.assertEqual(total, 75)               # the WHOLE deposit, no more
        # water ledger: start + mined - 1/sol crew consumption every sol
        # (11 sols run: 10 successful mines + the rejected one)
        self.assertEqual(st["storage"]["water"], 40 + 75 - 11)

    def test_depleted_deposit_stays_revealed_in_observation(self):
        from marscolony.observation import observation
        st = make_state(1, ["a1"], scen.load("depletion"))
        st["deposits"]["9,6"] = {"ice": 0}
        st["agents"][0]["x"], st["agents"][0]["y"] = 9, 6
        obs = observation(st, "a1")
        cells = {(d["x"], d["y"]): d["amount"] for d in obs["visible"]["deposits"]}
        self.assertEqual(cells.get((9, 6)), {"ice": 0})

    def test_fixed_map_geometry_is_authoritative(self):
        sc = scen.load("depletion")               # DEFAULT's 32x32 must not leak
        self.assertEqual(sc["map"]["w"], 21)
        self.assertEqual(sc["map"]["h"], 17)
        st = make_state(1, ["a1"], sc)
        self.assertEqual(len(st["grid"]["terrain"]), 17)

    def test_procedural_terrain_has_no_ice_char(self):
        st = make_state(1, ["a1"])                # ADR-0004: terrain = passability
        self.assertNotIn("i", "".join(st["grid"]["terrain"]))


class TestOutcomes(unittest.TestCase):
    def _sustainable_state(self):
        """One agent mining a rich patch + full infra: net-positive ledger."""
        sc = scen.load("depletion")
        sc["win"] = {"sustained_sols": 3}
        st = make_state(1, ["a1"], sc)
        st["deposits"]["9,6"] = {"ice": 500}
        st["agents"][0]["x"], st["agents"][0]["y"] = 9, 6
        st["storage"] = {"power": 20, "water": 150, "o2": 100, "food": 100}
        st["structures"] += [
            {"id": "s2", "type": "panel", "x": 1, "y": 1},
            {"id": "s3", "type": "extractor", "x": 2, "y": 2},
            {"id": "s4", "type": "greenhouse", "x": 3, "y": 3},
        ]
        return st

    def test_sustained_net_positive_wins(self):
        st = self._sustainable_state()
        reports = []
        for _ in range(5):
            st, rep = step(st, [act("a1", type="mine")])
            reports.append(rep)
            if st["episode_over"]:
                break
        self.assertEqual(st["episode_over"]["outcome"], "success")
        self.assertTrue(all(r["sustainable_sol"] for r in reports))
        self.assertTrue(any(e["type"] == "episode_over" and
                            e["outcome"] == "success"
                            for e in reports[-1]["events"]))

    def test_actions_rejected_after_success(self):
        st = self._sustainable_state()
        for _ in range(3):
            st, _ = step(st, [act("a1", type="mine")])
        st, rep = step(st, [act("a1", type="wait")])
        self.assertEqual(rep["actions"][0]["reason"], "episode_over")

    def test_extinction_outcome_reports_colony_dead(self):
        st = make_state(9, ["a1"])
        st["storage"]["o2"] = 0
        st, _ = step(st, [act("a1", type="wait")])
        self.assertEqual(st["episode_over"]["outcome"], "colony_dead")
        self.assertEqual(st["episode_over"]["cause"], "asphyxiation")

    def test_runner_reports_sol_cap_as_distinct_outcome(self):
        sc = scen.load("baseline")
        sc["sol_cap"] = 5
        res = run_episode(seed=3, n_agents=1, max_ticks=50,
                          trace_path=tmp(), scenario=sc)
        self.assertEqual(res["outcome"], "sol_cap")
        self.assertEqual(res["sols_survived"], 5)


class TestAttribution(unittest.TestCase):
    def test_trace_header_carries_attribution(self):
        path = tmp()
        run_episode(seed=42, n_agents=1, max_ticks=3, trace_path=path,
                    scenario="depletion")
        with open(path) as f:
            head = json.loads(f.readline())
            f.seek(0)
            last = json.loads(f.readlines()[-1])
        self.assertEqual(head["kind"], "run")
        self.assertEqual(head["scenario"]["name"], "depletion")
        self.assertEqual(head["scenario_hash"],
                         scen.scenario_hash(head["scenario"]))
        self.assertEqual(len(head["code_commit"]), 40)   # real commit in repo
        self.assertIn("T", head["ts_start"])              # ISO timestamp
        self.assertEqual(last["reason"], "sol_cap")
        self.assertIn("ts_end", last)

    def test_replay_reuses_recorded_scenario(self):
        path = tmp()
        run_episode(seed=42, n_agents=2, max_ticks=25, trace_path=path,
                    scenario="storm_heavy")
        res = replay(path)
        self.assertFalse(res["version_mismatch"])
        self.assertEqual(res["ticks_checked"], 25)
        self.assertEqual(res["mismatches"], [])

    def test_replay_refuses_foreign_engine_version(self):
        path = tmp()
        with open(path, "w") as f:
            f.write(json.dumps({"kind": "run", "seed": 1, "agents": ["a1"],
                                "version": "0.2.0-m2"}) + "\n")
        res = replay(path)
        self.assertTrue(res["version_mismatch"])
        self.assertEqual(res["version_at_record"], "0.2.0-m2")


class TestDeterminismWithScenarios(unittest.TestCase):
    def test_fixed_map_replays_bitwise_across_runs(self):
        p1, p2 = tmp("a.jsonl"), tmp("b.jsonl")
        r1 = run_episode(seed=5, n_agents=2, max_ticks=40, trace_path=p1,
                         scenario="depletion")
        r2 = run_episode(seed=5, n_agents=2, max_ticks=40, trace_path=p2,
                         scenario="depletion")
        self.assertEqual(r1["outcome"], r2["outcome"])
        self.assertEqual(r1["sustain_streak"], r2["sustain_streak"])
        for p in (p1, p2):
            self.assertEqual(replay(p)["mismatches"], [])

    def test_depletion_scenario_run_is_decisive(self):
        """The scenario engine must produce a real outcome, not just spin."""
        res = run_episode(seed=5, n_agents=1, max_ticks=120, trace_path=tmp(),
                          scenario="depletion")
        self.assertIn(res["outcome"],
                      ("colony_dead", "success", "sol_cap"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
