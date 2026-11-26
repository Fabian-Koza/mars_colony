# Progress Log

Session log — newest entry first. Every work session ends with an entry here:
what was done, decisions made, what's next, anything left broken.

Format: `## YYYY-MM-DD — <agent> — <one-line summary>`

---

## 2026-11-26 — Fabian + Hermes — ADR-0003..0009 ACCEPTED; engine merged to fabian

**Done**
- Fabian walked through all seven ADRs and accepted them as drafted
  (via the verdict form). Status lines + decisions index flipped to
  Accepted (2026-11-26). PLAN open questions resolved.
- Merge gate met: `engine` (0.3.0-engine + ADR-0005 harness) merged into
  `fabian`.

**Next**
- First real-model episode against worldbook v1.0 (single smoke run, then
  the 5-seed x {baseline, depletion} outcome sweep, ADR-0008 protocol:
  shared seed list, medians+spread).
- Bot v2 (success-capable scripted client) — optional but lets a
  `success` run be demonstrated and visualized end to end.

**Broken / known gaps**
- None new.

## 2026-11-26 — Hermes — ADR-0005 in harness: worldbook file, verbatim history, one repair retry

**Done**
- `marscolony/worldbook.md` (WORLDBOOK-VERSION 1.0): the complete rulebook
  as one versioned file — spatial micro-rules (ADR-0003), deposit rules
  (ADR-0004), costs/rates/thresholds, action schema, reply protocol, one
  worked example. Ad-hoc SYSTEM_PROMPT string is gone. A guard test asserts
  the worldbook's numbers match the engine constants (drift = test failure).
- `harness.py`: `load_worldbook()` (version parsed from file, sha256
  computed — the file is the version source of truth), `prompt_info()`
  attribution block, `validate_action_shape()` mirroring ONLY the engine's
  format-level rejections (invalid_json / unknown_action_type /
  malformed_move / unknown_structure_type).
- ADR-0005 policy in `LLMPolicy`: format-invalid reply -> EXACTLY ONE
  repair retry showing the validation error; second failure -> engine-side
  `wait` + a NOTE next sol telling the agent it was auto-waited (honest
  trace: the sent wait is a real wait). Spatial/resource rejections are
  NEVER retried — they are decision-quality signal owned by the engine.
  Conversation history is now FULL VERBATIM by default (`window=None`;
  the numeric window survives as the deliberate memory-stress variant).
- ADR-0008 attribution completed: trace header gains `prompt_version`,
  `prompt_hash`, `model_id` (null for scripted runs); engine state schema
  is untouched so `__version__` stays 0.3.0-engine and old traces stay
  replayable. Sidecar entries gain per-turn `retries`, `resolved`
  (model/retry/auto_wait) and `attempts[]` (every raw output + rejection
  reason). Sweep results + comparison table gain rty/aw columns — "bad at
  JSON" is now a separate metric from "bad decisions".
- Verified: 66/66 tests (+18); scripted + LLM-style (FakeClient) episodes
  replay hash-clean; two same-seed scripted runs identical over 25 ticks;
  viz renders attempts (JSON parses back, id check, node --check OK).

**Next**
- Fabian's verdict on ADR-0003..0009 (walkthrough delivered 2026-11-26;
  clarify form timed out — status untouched, all seven still Proposed).
- Worldbook edits after acceptance = content change = new prompt_hash and
  a WORLDBOOK-VERSION bump (ADR-0008 freeze policy); first real-model run
  should follow.
- Bot v2 (success-capable scripted client) and the 5-seed outcome sweep
  still queued behind the ADR verdict.

**Broken / known gaps**
- Carry-over: legacy scripted bot cannot reach `success` (bot v2 queued).
- Long-episode context overflow (verbatim history) will need its own ADR
  per ADR-0005 — not hit at <=120 sols.

## 2026-11-25 — Hermes — Engine branch: v0.3 engine implementing ADR-0004..0008

**Done**
- New branch `engine` (from fabian): first ADR-conformant engine build,
  version `0.3.0-engine`. Evolves the M2 kernel rather than rewriting.
- ADR-0004: terrain is passability-only; sparse `deposits` layer, finite
  amounts (mine withdraws, depleted stays revealed), max 2 types/tile;
  ice terrain char retired (old 0.2.x traces now refused at replay with a
  clear version-mismatch message).
- ADR-0006: three terminal outcomes — `colony_dead`, `success`
  (scenario-declared net-positive streak; per-sol balance ledger incl.
  structure inputs; a colony mining to stay alive is NOT self-sustaining),
  `sol_cap` (runner-owned ceiling).
- ADR-0007: `marscolony/scenario.py` loader + bundled scenarios
  `baseline`, `storm_heavy` (stress), `depletion` (fixed 21x17 map: visible
  seam + drying near patch + far ridge = exploration pressure).
  Scenario dict embedded in state; CLI `--scenario` on run/sweep.
- ADR-0008 (engine-side): trace header carries scenario+hash, code_commit,
  ts_start/ts_end; LLM sidecar entries now have per-turn `ts`.
  ADR-0005 worldbook-file + repair-retry deliberately NOT built yet.
- Fixed-map validation lesson: DEFAULT's w/h leak through the merge —
  fixed-map geometry is authoritative (regression test added).
- Verified: 48/48 tests; scripted-bot episodes on all 3 scenarios replay
  hash-clean; depletion kills a built-out colony at sol ~56 (pressure
  works); baseline max sustain streak 6/30 (win is reachable but demands
  more than single build-out — legacy bot cannot win yet, by design:
  `success` should separate thriving from capping).

**Next**
- Fabian accepts/rejects ADR-0003..0009 (engine implements the drafts).
- Worldbook file + one-repair-retry (ADR-0005) in harness; prompt version
  bump protocol; then a 0.3.0 sweep (5 seeds x baseline+depletion) to get
  first outcome-distribution data.
- Bot v2 (optional): mine-marathon/rest cadence + panel doubling so the
  scripted client can demonstrate a `success` run end to end.

**Broken / known gaps**
- Legacy scripted bot dies in most v0.3 baseline seeds (57-110 sols) —
  acceptable for a validation client, but a `success`-capable reference
  bot is still missing.

## 2026-11-25 — Hermes — Drafted foundational ADR set 0003–0009 (Proposed)

**Done**
- Answered Fabian's design questions (tile↔room granularity, resources per
  tile, turn timing real vs in-game) and enumerated the 8 foundational
  decisions still open before the next build phase, with recommendations.
- Drafted ADR-0003…0009 (all **Proposed**, pending Fabian's acceptance):
  0003 one tile = one room + no-gotchas spatial rules; 0004 terrain/deposit
  split with finite, multi-resource deposits (max 2 types/tile); 0005 full
  worldbook in static prompt + verbatim history + one repair retry; 0006
  three terminal states (colony_dead / success / sol_cap), permanent death;
  0007 scenarios as declarative JSON (fixed maps for A/B, procedural for
  robustness); 0008 experiment protocol (paired seeds, >=5, header carries
  code_commit/prompt_hash/scenario_hash/ts, prompt freeze policy);
  0009 comms + private ownership deferred behind their own future ADRs
  (refines 0002, does not supersede it).
- Updated decisions index and PLAN.md open questions.

**Next**
- Fabian reviews 0003–0009 -> flip to Accepted (or amend/reject per ADR).
- Build implied once accepted: deposits layer (world/rules/obs/viz),
  worldbook file + retry-with-feedback in harness, terminal-state split in
  rules, scenario loader + 3 starter scenarios, trace-header fields +
  per-turn timestamps in the LLM log.
- Uncommitted from last session still present (M2/M3 code + docs);
  commit pending Fabian's word.

**Broken / known gaps**
- Nothing new; carry-over: `.llm.jsonl` lacks timestamps (ADR-0008 fix).

## 2026-11-05 — Hermes — First full 6-model sweep: results + per-model HTML

**Done**
- 6-model x seed42 x 2-agent x 40-sol sweep completed; ALL traces replay
  hash-clean (6/6).
- Results: 4/6 models survived all 40 sols with full infrastructure
  (GLM-5.3-Flash, Mistral-Large-4-1T, Qwen3.8-27B, Qwen3.8-Flash-Next).
  Qwen3-Coder-Next: 0 structures built -> both agents starved at sol 29.
  gemma-4-31B: built 5 structures but asphyxiated at sol 30 (O2 economy
  never closed). Deaths always hit BOTH agents the same sol (symmetric
  trajectories in shared world — note for study design).
- Format compliance signal: invalid-action counts range 2 (Qwen3.8-Flash)
  to 8 (Qwen3-Coder); reasons distinguish spatial errors (impassable,
  not_on_ice) from format errors (malformed_move, unknown_action_type).
- Per-model visual HTML generated + copied to /home/operations/viz/
  (one .html per model, raw model outputs embedded); delivery to user via
  scp (confirmed working).
- M5 partially underway: visualizer (viz.py) done; metric suite still thin.

**Next (M4/M5)**
- M4: communication actions + scenario/event design (storms never fired on
  seed 42 — need storm-heavy seeds to measure stress response).
- M5: proper metric suite (efficiency, planning horizon, invalid-reason
  taxonomy); multi-seed matrices (n>=5 seeds/model for any real claim).
- Consider commit + ADR for trace/HTML artifacts location.

**Broken / known gaps**
- Single-seed results are anecdotes, not measurements — treat the table as
  a smoke test of the experimental pipeline (which it now is, end to end).

## 2026-11-05 — Hermes — Trace visualizer (M5 piece) + sweep still running

**Done**
- `marscolony/viz.py` + CLI `visualize`: reads a trace (+ auto-detects the
  raw-LLM sidecar), emits a STANDALONE dark-theme HTML replay (ADR-0001:
  read-only consumer, sim loop untouched). Timeline scrub/play, terrain+
  structures+agents map with legend, storage gauges, storm badge, per-sol
  action verdicts (OK/REJECTED+reason), events/deaths, raw model output
  behind every action.
- Generated + verified: glm-run.html (40-sol GLM sweep episode, 80 raw
  outputs embedded) and qwen-smoke.html. Verified structurally (embedded
  JSON parses, DOM ids complete, node --check OK); local browser unusable
  (missing libnspr4) so no pixel check — user opens HTML directly.
- TraceWriter.tick now flushes per tick (long LLM episodes inspectable
  mid-run).

**In flight**
- 6-model sweep: 1/6 done at last check (GLM alive 2/2, full infra),
  Mistral-Large in progress. On exit: verify replays + comparison table +
  one HTML per model.

**Files for the user**
- /home/operations/.hermes/cache/scratch/glm-run.html
- /home/operations/.hermes/cache/scratch/qwen-smoke.html

## 2026-11-05 — Hermes — M3 LLM harness + model sweep runner

**Done**
- `marscolony/harness.py`: SYSTEM_PROMPT (rules + action JSON schema),
  `render_observation()` (deterministic text view), `extract_action()`
  (tolerant JSON extraction; garbage -> INVALID_JSON action the engine
  LOGS like any invalid action), `OpenAICompatClient` (stdlib urllib,
  temperature 0), `LLMPolicy` (per-agent conversation + sliding window of
  last 8 sols).
- M3 design decisions: (1) action RESULTS are fed back to the model next
  sol ("REJECTED: <reason>") — the M2 bot never saw results; a reasoning
  agent must. (2) raw model text logged verbatim to `<out>.llm.jsonl`
  sidecar; engine trace stays pure. (3) replay determinism independent of
  model sampling (traces record resolved actions).
- `marscolony/experiment.py` + CLI `sweep`: model x seed matrix on identical
  worlds (engine determinism makes cross-model comparison clean); outputs
  comparison table + results.json + per-run traces + raw-output sidecars.
- Runner gained `policy_factory` / `on_results` / `llm_log_path`.
- `tests/test_harness.py`: 12 offline tests (FakeClient, no network):
  parsing, feedback-injection into next prompt, window bounds, multi-agent,
  matrix + table. Suite now 31/31.
- Cloud endpoint confirmed live: api.ai.ustp.host/v1 with the user's 6
  models (GLM-5.3-Flash, Mistral-Large-4-1T, Qwen3-Coder-Next,
  Qwen3.8-27B, Qwen3.8-Flash-Next, gemma-4-31B). Harness is
  model-agnostic via `--model`.

**In flight / next**
- Live smoke run (Qwen3.8-27B, seed 42, 1 agent, 12 sols) — verify, then
  run the full 6-model sweep (2 agents, ~40-60 sols, seeds 42+43) with
  traces kept in scratch; first behavioral comparison table.
- Then M4: scenario/events design (communication actions, storm policy),
  M5 metric analysis.

**Broken / known gaps**
- Live sweep results pending verification of the smoke run.

## 2026-11-05 — Hermes — M2 engine kernel implemented and validated

**Done**
- Kernel design pinned in `docs/notes/m2-kernel-design.md`: 1 tick = 1 sol;
  resources power/water/o2/food (colony-shared, ints); action space v0
  move/mine/build/rest/wait (give/communicate → M4); JSONL trace schema.
- First code in repo, stdlib-only: `marscolony/` — rng.py (splitmix64, RNG
  state inside state dict → pure `step()`), world.py, rules.py (tick engine,
  invalid actions logged not raised), observation.py (radius-3 partial
  observability), bots.py (deterministic scripted survival bot:
  seek→mine→panel→mine→extractor→greenhouse→operated), trace.py (writer +
  deterministic replayer), runner.py (episode harness + offline metrics),
  __main__.py (`python -m marscolony run|replay|metrics`).
- `tests/test_engine.py`: 19 tests — purity, determinism, replay, action
  validation, production math, death conditions, observation contract.
  All pass.
- Validation: seed 42 / 2 agents / 60 sols — two runs byte-identical
  (same sha256), replay OK 60/60 ticks. Sweep 30 seeds × 4 agents ×
  100 sols: 0 crashes, 0 replay mismatches; 10/30 extinctions
  (asphyxiation) from the naive wander bot failing to reach ice —
  legitimate scenario difficulty, good behavioral variance signal.
- Balance tuning: mine yield 5→8 (see design note) so a built-out colony is
  sustainable; extinction must come from decisions, not arithmetic.

**Next**
- M3: LLM harness — observation text builder + JSON action parsing
  (pydantic schemas OK to introduce in the harness, engine stays stdlib),
  run a real model against the same interface the scripted bot uses.
- Consider committing (repo has first code now; untracked: marscolony/,
  tests/; modified docs + AGENTS/PLAN/PROGRESS).

**Broken / known gaps**
- Bot navigation is greedy/naive (no pathfinding) → high early-death rate
  with 4 agents; fine for validation, could improve later.
- Structures visible colony-wide in observations (comms assumption;
  revisit in M4 observability design).

## 2026-11-05 — Hermes — Wayfinder map charted: "Find the Start"

**Done**
- Ran the external wayfinder skill (mattpocock/skills): charted the open
  question — *where does this project start, what are its basic needs, what
  does the roadmap look like* — as a decision-ticket map at
  `.scratch/mars-colony/` (`map.md` + numbered tickets), on new branch `fabian`.
- Reconciled with the sibling session's output the same day: tickets
  *Project vision* and *Deliverable form* recorded resolved (answers = PLAN.md
  vision + engine approach); the engine note's five open decisions graduated
  from fog into tickets 08–11 (language, agent interface, single-vs-multi,
  fidelity+tick).
- Frontier (open, unblocked, unclaimed): Team capability inventory (03),
  Supervisor requirements (04), Agent interface (09), Single-vs-multi (10),
  Fidelity+tick (11).
- First commit on `fabian`: all planning docs + tracker. Team = 3 people +
  1 supervisor recorded in map Notes.

**Next**
- One ticket per session. Cheapest high-value: run 09/10/11 (ADR decisions);
  03 needs all 3 people (checklist ready in ticket body).
- Push `fabian` once `gh` device-flow auth is done.

**Broken / known gaps**
- Vision wording is Fabian's alone so far — the other two must ratify
  (happens at ticket 07 sign-off).

## 2026-11-05 — Hermes — Project defined: LLM behavior sim; engine approach drafted

**Done**
- Vision, goals, non-goals filled in `docs/PLAN.md`: Mars-colony sim whose
  purpose is observing LLM agent behavior; sim = instrument, data = product.
- Roadmap M2–M5 defined (engine kernel → LLM harness → scenarios → analysis).
- New note `docs/notes/simulation-engine-approach.md`: headless deterministic
  tick engine (`state' = f(state, actions)`), observation/action API,
  trace-first logging, layered diagram, minimal-kernel scope, open ADR
  decisions (language, interface format, single vs multi-agent, fidelity,
  tick granularity).

**Next**
- Settle the open decisions above → write first ADRs (0001 engine shape,
  0002 agent interface).
- Then M2: implement engine kernel (first code in repo — only after ADRs).

**Broken / known gaps**
- No ADRs yet; architecture is proposal-level, not accepted.

## 2026-11-05 — Hermes — Engine decisions settled; ADR-0001 & 0002 accepted

**Done**
- Settled the open architecture decisions with Fabian:
  Python · text/JSON obs–action API · multi-agent from day one (max 4) ·
  abstract resource-colony fidelity · headless deterministic tick engine.
- Wrote `decisions/0001-engine-shape-headless-python-tick-engine.md` and
  `decisions/0002-agent-interface-text-json-api.md` (Accepted); updated
  decisions index, PLAN.md (M1 done, open questions trimmed), and the
  approach note.

**Next**
- M2 engine kernel: remaining design details are the trace/log schema,
  minimal resource set + action space, and tick granularity (1 sol vs
  fraction). These can be decided during kernel design/implementation —
  explicit go-ahead from Fabian needed before writing first code.

**Broken / known gaps**
- None.

## 2026-11-03 — Hermes — Claude Code installed & wired in

**Done**
- Installed Claude Code CLI v2.1.317 (native installer → `~/.local/bin/claude`, PATH added to `~/.bashrc`).
- Added `CLAUDE.md` (imports AGENTS.md — no rule duplication).
- AGENTS.md roster updated: Claude Code active, OpenCode still planned.

**Open**
- Claude Code is NOT logged in yet — user must run `claude` → `/login` (or export ANTHROPIC_API_KEY).

## 2026-11-03 — Hermes — Initial scaffolding

**Done**
- Created `AGENTS.md` (agent config + working rules; Hermes active, OpenCode planned).
- Created docs scaffolding: `docs/README.md` (index), `PLAN.md`, `PROGRESS.md`,
  `decisions/` with ADR template, `notes/`.
- Added root `README.md`.

**Next**
- Fill in the vision, goals, and non-goals in `docs/PLAN.md`.
- Decide project form/deliverable; open questions listed at the bottom of PLAN.md.
- Consider `git init` + first commit once the plan has substance.

**Broken / known gaps**
- Plan is a skeleton — vision and goals are placeholders by design.
