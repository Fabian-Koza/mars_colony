# Mars Colony — Agent Configuration

This file is the single source of truth for how AI agents work on this project.
It is auto-loaded by Hermes Agent (cwd only) and is portable to other agents
(Codex, Claude Code, OpenCode) — keep it tool-agnostic.

## Project

- **Name:** Mars Colony
- **Status:** Planning / documentation phase — no code yet
- **Primary activity in current phase:** documenting the plan (goals, architecture,
  decisions, progress) in `docs/`

## Agent roster

| Agent       | Status   | Notes                                              |
|-------------|----------|----------------------------------------------------|
| Hermes      | Active   | Primary agent for all work sessions                |
| Claude Code | Active   | Installed 2026-11-03; reads CLAUDE.md → this file  |
| OpenCode    | Planned  | May be added later; AGENTS.md must stay compatible |

Rules below apply to every agent working in this repo, current or future.

## Working conventions

1. **Docs-first.** This project is documentation-driven. Before doing anything
   else in a session, read `docs/PLAN.md` and `docs/PROGRESS.md` to restore
   context.
2. **Close every session by updating docs.** At the end of each work session:
   - append a dated entry to `docs/PROGRESS.md` (what was done, what's next,
     anything left broken),
   - update `docs/PLAN.md` if scope or priorities changed.
3. **Decisions get an ADR.** Any non-trivial, hard-to-reverse choice (tech stack,
   architecture, data model) gets a numbered file in `docs/decisions/` — copy
   `docs/decisions/0000-template.md`. Don't edit accepted ADRs; supersede them.
4. **No speculative code.** During the planning phase, do not create source
   code, package manifests, or CI config unless explicitly asked.
5. **Small, reviewable changes.** Prefer many small doc/commit-sized changes
   over one large rewrite.
6. **Secrets** never go in this repo (no API keys, no `.env` committed).

## Repo map

```
AGENTS.md            This file — agent config & rules (source of truth)
CLAUDE.md            Claude Code entry point — imports AGENTS.md, add no rules here
README.md            Human-facing project intro
docs/
  README.md          Docs index — keep current when adding docs
  PLAN.md            The plan: vision, goals, scope, roadmap
  PROGRESS.md        Running session log (newest first)
  decisions/         ADRs — one file per decision
  notes/             Loose research/idea notes (no format obligations)
```

## Hermes-specific

- Session context is auto-injected from this file (cwd only — always run
  Hermes from the repo root).
- Use `hermes --continue` / `--resume <id>` to pick up a previous session here.
- When a durable lesson about *how to work on this project* emerges, record it
  in a project skill or add it here — not in personal memory.
