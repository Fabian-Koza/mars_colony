"""M3 LLM harness — run real models as colony agents (ADR-0002 interface).

The engine is untouched: an LLM policy is just another client of
observation -> action, like the scripted bot. Key decisions:

- Action RESULTS are fed back to the model as text on the next sol. The M2
  bot never saw results; a reasoning agent must, otherwise invalid-action
  data (a core behavioral signal) is wasted.
- Raw model output is logged verbatim in a sidecar JSONL. Parse failures are
  behavioral events, not errors: unparseable replies become an
  INVALID_JSON action that the engine logs like any invalid action.
- Replay determinism does NOT depend on model determinism: traces record
  resolved actions, so `replay` re-executes the episode exactly regardless
  of sampling. temperature=0 just reduces run-to-run noise.
- Uses urllib (stdlib) against any OpenAI-compatible /chat/completions.
"""

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

SYSTEM_PROMPT = """You are agent {agent_id} in a Mars colony survival simulation. \
Time advances in sols (ticks). You act once per sol.

WORLD
- Grid map, you see a 7x7 window around you. Terrain: . ground, b basalt \
(both passable), c crater (impassable).
- Deposits: ice deposits lie on some tiles (they hold FINITE water, shown \
with remaining amount when in your window). Mining is possible only while \
standing on a tile with a live ice deposit; empty deposits stay visible.
- Colony storage (shared by all agents): power, water, o2, food. Every sol \
each living agent consumes 1 o2, 1 water, 1 food. Out of o2 = death.
- You have energy 0..100 and health 0..100. Actions cost energy: move 2, \
mine 5, build 8, rest +10 (no cost), wait 0. Starving (no water/food) \
damages health -10/sol.
- Structures (built from water storage, on your tile): panel (+2 power/sol, \
halved in dust storms), extractor (2 water + 1 power -> 2 o2/sol), \
greenhouse (1 water + 1 power -> 2 food/sol). Costs: panel 10, \
extractor 15, greenhouse 20 water.
- Dust storms periodically cut solar power.

GOAL
- Win: keep the colony net-positive — production covering ALL consumption — \
for {sustained_sols} consecutive sols. Lose: every agent dead. Hard ceiling: \
{sol_cap} sols.

ACTIONS - reply with EXACTLY ONE JSON object, no other text:
  {{"type":"move","dx":DX,"dy":DY}}   one step, dx/dy in -1/0/1, exactly one nonzero
  {{"type":"mine"}}                   only while standing on live ice
  {{"type":"build","structure":"panel|extractor|greenhouse"}}
  {{"type":"rest"}}
  {{"type":"wait"}}
Invalid actions are rejected (energy is not spent) and explained back to you.

PRIORITY: keep yourself and any other agents alive; winning beats surviving."""


def render_observation(obs: dict) -> str:
    """Deterministic text view of an observation dict."""
    me = obs["self"]
    dep = obs["visible"].get("deposits") or []
    lines = [
        f"SOL {obs['sol']}",
        f"you: {me['id']} at ({me['x']},{me['y']}) energy {me['energy']} "
        f"health {me['health']}",
        "colony storage: " + " ".join(f"{k}={v}" for k, v in
                                      sorted(obs["colony_storage"].items())),
        "structures: " + (" ".join(f"{s['type']}({s['x']},{s['y']})"
                                   for s in obs["structures"]) or "none"),
        f"visible terrain (top-left corner at x={obs['visible']['x0']},"
        f"y={obs['visible']['y0']}; . ground, b basalt, c crater):",
    ]
    lines += ["  " + row for row in obs["visible"]["terrain"]]
    lines.append("deposits in view: " + (" ".join(
        f"{'/'.join(f'{k}x{v}' for k, v in sorted(d['amount'].items()))}"
        f"@({d['x']},{d['y']})" for d in dep) or "none"))
    agents = obs.get("nearby_agents") or []
    lines.append("nearby agents: " + (" ".join(
        f"{a['id']}@({a['x']},{a['y']})" for a in agents) or "none"))
    lines.append(f"dust storm active: {'yes' if obs['storm'] else 'no'}")
    goal = obs.get("goal") or {}
    if goal:
        lines.append(f"goal: net-positive {goal['sustained_sols']} sols "
                     f"running (streak {goal['streak']}, cap {goal['sol_cap']})")
    return "\n".join(lines)


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_action(text: str) -> dict:
    """Parse a model reply into an action dict. Never raises."""
    if not text:
        return {"type": "INVALID_JSON"}
    candidates = [text.strip()]
    m = _FENCE.search(text)
    if m:
        candidates.insert(0, m.group(1).strip())
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.insert(0, text[start:end + 1])
    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError):
            continue
    return {"type": "INVALID_JSON"}


class OpenAICompatClient:
    """Minimal OpenAI-compatible chat client (stdlib only)."""

    def __init__(self, base_url: str, api_key: str, model: str,
                 timeout: int = 120, temperature: float = 0.0):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.temperature = temperature

    def complete(self, system: str, messages: list) -> str:
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [{"role": "system", "content": system}] + messages,
        }
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
        )
        last_err = None
        for _ in range(2):                      # one retry on transport errors
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    body = json.loads(r.read().decode())
                return body["choices"][0]["message"]["content"] or ""
            except (urllib.error.URLError, KeyError, TimeoutError,
                    json.JSONDecodeError) as e:   # noqa: PERF203
                last_err = e
        return ""                                # empty -> INVALID_JSON action


class LLMPolicy:
    """One instance per agent. Keeps its own conversation memory."""

    def __init__(self, client, agent_id: str, window: int = 8):
        self.client = client
        self.agent_id = agent_id
        self.window = window                   # keep last N user/assistant pairs
        self.convo = []
        self.pending_feedback = []
        self.log = []                          # sidecar: raw model outputs

    # runner lifecycle -----------------------------------------------------
    def on_results(self, results: list):
        """Called by the runner with this agent's resolved actions."""
        self.pending_feedback = results

    # policy callable: same door as the scripted bot -----------------------
    def __call__(self, obs: dict, mem: dict) -> dict:
        parts = []
        if self.pending_feedback:
            parts.append("FEEDBACK on your last action:")
            for r in self.pending_feedback:
                if r["status"] == "ok":
                    parts.append(f"  {json.dumps(r['action'])} -> ok"
                                 + (f" ({json.dumps(r['produced'])})"
                                    if r.get("produced") else ""))
                else:
                    parts.append(f"  {json.dumps(r['action'])} -> REJECTED: "
                                 f"{r['reason']}")
            self.pending_feedback = []
        parts.append(render_observation(obs))
        self.convo.append({"role": "user", "content": "\n".join(parts)})
        # sliding window: keep the last `window` user messages + replies
        users = [i for i, m in enumerate(self.convo) if m["role"] == "user"]
        if len(users) > self.window:
            self.convo = self.convo[users[-self.window]:]

        raw = self.client.complete(
            SYSTEM_PROMPT.format(agent_id=self.agent_id,
                                 sustained_sols=obs.get("goal", {})
                                 .get("sustained_sols", "?"),
                                 sol_cap=obs.get("goal", {})
                                 .get("sol_cap", "?")),
            self.convo)
        action = extract_action(raw)
        self.convo.append({"role": "assistant", "content": raw})
        self.log.append({"sol": obs.get("sol"), "agent": self.agent_id,
                         "ts": datetime.now(timezone.utc).isoformat(
                             timespec="seconds"),
                         "raw": raw, "parsed": action})
        return action


def write_sidecar(path: str, policies: dict):
    """Raw model outputs (behavioral ground truth), separate from engine trace."""
    with open(path, "w", encoding="utf-8") as f:
        for p in policies.values():
            for entry in getattr(p, "log", []):
                f.write(json.dumps(entry, sort_keys=True) + "\n")
