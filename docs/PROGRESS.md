# Progress Log

Session log — newest entry first. Every work session ends with an entry here:
what was done, decisions made, what's next, anything left broken.

Format: `## YYYY-MM-DD — <agent> — <one-line summary>`

---

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
