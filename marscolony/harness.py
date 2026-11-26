"""M3 LLM harness — run real models as colony agents (ADR-0002 interface).

The engine is untouched: an LLM policy is just another client of
observation -> action, like the scripted bot. Key decisions:

- ADR-0005: the complete rulebook is a static versioned file
  (`worldbook.md`) forming a fixed system-prompt prefix; its sha256
  (prompt_hash) goes into the trace header. Conversation history is FULL
  VERBATIM by default (windowing is a deliberate scenario variant, not an
  accident). A malformed reply gets EXACTLY ONE repair retry showing the
  validation error, then an engine-side `wait`; retry counts are logged
  per turn so "bad at JSON" stays separable from "bad decisions".
- Action RESULTS are fed back to the model as text on the next sol. The M2
  bot never saw results; a reasoning agent must, otherwise invalid-action
  data (a core behavioral signal) is wasted.
- Raw model output is logged verbatim in a sidecar JSONL (one entry per
  turn, incl. every failed attempt). Parse failures are behavioral events,
  not errors.
- Replay determinism does NOT depend on model determinism: traces record
  resolved actions, so `replay` re-executes the episode exactly regardless
  of sampling. temperature=0 just reduces run-to-run noise.
- Uses urllib (stdlib) against any OpenAI-compatible /chat/completions.
"""

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

# --- worldbook (ADR-0005): single canonical rulebook file -------------------

WORLDBOOK_PATH = os.path.join(os.path.dirname(__file__), "worldbook.md")
_WB_CACHE = {}


def load_worldbook(path: "str | None" = None) -> dict:
    """Read the worldbook: {"text", "version", "sha256"}. Cached per path.
    Version comes from the file's `WORLDBOOK-VERSION: x.y` first line —
    the file is the single source of truth (no version constant in code)."""
    p = path or WORLDBOOK_PATH
    if p not in _WB_CACHE:
        with open(p, encoding="utf-8") as f:
            text = f.read()
        m = re.match(r"WORLDBOOK-VERSION:\s*(\S+)", text)
        if not m:
            raise ValueError(f"{p}: missing WORLDBOOK-VERSION header line")
        _WB_CACHE[p] = {"text": text, "version": m.group(1),
                        "sha256": hashlib.sha256(
                            text.encode("utf-8")).hexdigest()}
    return _WB_CACHE[p]


def render_worldbook(text: str, agent_id: str, goal: dict) -> str:
    """Fill the worldbook's fixed tokens. Deterministic, no str.format
    (the rulebook contains literal JSON braces)."""
    return (text
            .replace("{{AGENT_ID}}", str(agent_id))
            .replace("{{SUSTAINED_SOLS}}",
                     str(goal.get("sustained_sols", "?")))
            .replace("{{SOL_CAP}}", str(goal.get("sol_cap", "?"))))


def prompt_info(path: "str | None" = None,
                model_id: "str | None" = None) -> dict:
    """Header attribution block for ADR-0008 (prompt side)."""
    wb = load_worldbook(path)
    return {"prompt_version": wb["version"], "prompt_hash": wb["sha256"],
            "model_id": model_id}


# --- action shape validation (ADR-0005 repair-retry gate) -------------------
# Mirrors ONLY the engine's FORMAT-level checks (rules.py). Spatial and
# resource rejections (impassable, no_deposit, insufficient_*) are DELIBERATE
# decisions with real information — the engine logs those, and the agent
# learns from feedback next sol. Retrying them would hand agents free extra
# attempts per sol and erase decision-quality signal from the trace.

ACTION_TYPES = ("move", "mine", "build", "rest", "wait")
STRUCTURE_TYPES = ("panel", "extractor", "greenhouse")


def validate_action_shape(action) -> "str | None":
    """Return a machine-readable reason if the action cannot even reach
    the engine's decision logic, else None. Never raises."""
    if not isinstance(action, dict):
        return "invalid_json"
    t = action.get("type")
    if t == "INVALID_JSON":
        return "invalid_json"
    if t not in ACTION_TYPES:
        return "unknown_action_type"
    if t == "move":
        dx, dy = action.get("dx"), action.get("dy")
        if (not isinstance(dx, int) or not isinstance(dy, int)
                or abs(dx) + abs(dy) != 1):
            return "malformed_move"
    if t == "build" and action.get("structure") not in STRUCTURE_TYPES:
        return "unknown_structure_type"
    return None


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
    """One instance per agent. Keeps its own conversation memory.

    ADR-0005: history is FULL VERBATIM by default (`window=None`); a
    numeric window is reserved for the deliberate memory-stress scenario
    variant, never as an accident of the harness. A format-invalid reply
    triggers exactly ONE repair retry that shows the validation error;
    a second failure resolves to an engine `wait` (logged as auto_wait).
    """

    def __init__(self, client, agent_id: str, window: "int | None" = None,
                 worldbook_path: "str | None" = None):
        self.client = client
        self.agent_id = agent_id
        self.window = window          # None = full verbatim history
        self.wb = load_worldbook(worldbook_path)
        self.convo = []
        self.pending_feedback = []
        self.pending_note = None      # e.g. "you were auto-waited"
        self.log = []                 # sidecar: raw model outputs

    # runner lifecycle -----------------------------------------------------
    def on_results(self, results: list):
        """Called by the runner with this agent's resolved actions."""
        self.pending_feedback = results

    def _system(self, obs: dict) -> str:
        return render_worldbook(self.wb["text"], self.agent_id,
                                obs.get("goal") or {})

    def _ask(self, system: str, raw: str, reason: str) -> tuple:
        """One repair retry. Returns (action, raw2, reason2)."""
        self.convo.append({"role": "assistant", "content": raw})
        self.convo.append({"role": "user", "content":
                           f"REJECTED: {reason}. That reply is not a valid "
                           "action and was NOT sent to the colony. Reply "
                           "again with EXACTLY ONE JSON action object per "
                           "the worldbook schema (if you truly cannot "
                           'choose, reply {"type":"wait"}).'})
        raw2 = self.client.complete(system, self.convo)
        action2 = extract_action(raw2)
        return action2, raw2, validate_action_shape(action2)

    # policy callable: same door as the scripted bot -----------------------
    def __call__(self, obs: dict, mem: dict) -> dict:
        parts = []
        if self.pending_note:
            parts.append(f"NOTE: {self.pending_note}")
            self.pending_note = None
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
        if self.window:      # deliberate variant only; default = verbatim
            users = [i for i, m in enumerate(self.convo) if m["role"] == "user"]
            if len(users) > self.window:
                self.convo = self.convo[users[-self.window]:]

        system = self._system(obs)
        raw = self.client.complete(system, self.convo)
        action = extract_action(raw)
        reason = validate_action_shape(action)
        attempts = [{"raw": raw, "parsed": action}]
        retries = 0
        resolved = "model"

        if reason:                                   # ADR-0005: one retry
            retries = 1
            attempts[0]["reason"] = reason
            action2, raw2, reason2 = self._ask(system, raw, reason)
            attempts.append({"raw": raw2, "parsed": action2})
            if reason2:
                attempts[-1]["reason"] = reason2
                action = {"type": "wait"}
                resolved = "auto_wait"
                self.pending_note = (
                    "your last reply failed validation twice "
                    f"(second reason: {reason2}); the engine "
                    "auto-waited for you this sol.")
            else:
                action = action2
                resolved = "retry"
            self.convo.append({"role": "assistant", "content": raw2})
        else:
            self.convo.append({"role": "assistant", "content": raw})

        self.log.append({"sol": obs.get("sol"), "agent": self.agent_id,
                         "ts": datetime.now(timezone.utc).isoformat(
                             timespec="seconds"),
                         "retries": retries, "resolved": resolved,
                         "raw": attempts[-1]["raw"], "parsed": action,
                         "attempts": attempts})
        return action


def write_sidecar(path: str, policies: dict):
    """Raw model outputs (behavioral ground truth), separate from engine trace."""
    with open(path, "w", encoding="utf-8") as f:
        for p in policies.values():
            for entry in getattr(p, "log", []):
                f.write(json.dumps(entry, sort_keys=True) + "\n")
