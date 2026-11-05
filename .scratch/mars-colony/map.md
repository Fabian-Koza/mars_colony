# Wayfinder map: Mars Colony — Find the Start

Label: `wayfinder:map`
Tracker: local-markdown on branch `fabian` of https://github.com/Fabian-Koza/mars_colony

## Destination

The 3-person team (plus supervisor) has an agreed, committed **baseline of basic
needs** and a **roadmap** for Mars Colony: what the project is, what the first
version must do, which milestones come in which order, and who picks up the first
milestone — so the next work session can start with nothing left to decide.

## Notes

- Domain: Mars Colony — LLM-behavior simulation study in planning phase (`AGENTS.md`, `docs/PLAN.md`, `docs/notes/simulation-engine-approach.md`).
- Team: 3 people + 1 supervisor. Decisions are the team's; the supervisor signs off at the end of this map.
- Plan, don't do (default): tickets resolve decisions, they don't deliver the build.
- Skills every session should consult: **grilling** (all HITL tickets), **domain-modeling** (the moment a term or decision crystallises — start `GLOSSARY.md` / ADRs then).
- Tracker layout: this file is the map; tickets are `issues/NN-<slug>.md` (`Type:`, `Status:`, `Blocked by:` lines per the local-markdown convention).
- Concurrent sessions exist: a sibling session drafted the vision + engine approach on 2026-11-05. Re-read `docs/` before working any ticket.

## Decisions so far

<!-- one line per closed ticket: gist + link -->

- [Project vision](issues/01-project-vision.md): LLM-behavior observation instrument dressed as a Mars-colony sim — sim is the instrument, behavioral data is the product (team ratification at sign-off).
- [Deliverable form](issues/02-deliverable-form.md): headless deterministic tick engine + LLM harness + replayable traces; no graphics in the loop; metrics computed offline from traces.

## Not yet specified

- Trace/log schema and the metrics it must make computable — the engine note says design the log around the questions; sharpens once fidelity/tick and single-vs-multi-agent settle.
- Collaboration mechanics for 3 people + agents: branch strategy, review rules, how Hermes / Claude Code / OpenCode split work.
- When M0 "Foundation" closes: this branch's push + merge is most of it; graduation is imminent.
- Supervisor review loop between milestones (cadence, format, what needs approval) — will sharpen out of the supervisor-requirements ticket.
- Splitting roadmap work across the 3 people (ownership per milestone) — can't be sliced before the roadmap is ratified.

## Out of scope

- Actual implementation of the project beyond "where to start": this map ends at the agreed needs + roadmap; building is a fresh effort from that destination.
- Team changes or recruitment.
