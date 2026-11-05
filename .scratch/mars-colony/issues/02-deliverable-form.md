Type: grilling
Status: resolved
Blocked by: 01

## Question

What form does the deliverable take — a running simulation/software, a written/
research artifact, a mix? What would the supervisor expect to see at the end:
code that runs, a report, a demo? The answer decides which later decisions
(tech stack, architecture, needs) even exist.

## Answer

Form decided (docs/PLAN.md Goals/Non-goals + docs/notes/simulation-engine-approach.md,
2026-11-05): a **headless, deterministic simulation engine + LLM harness +
replayable traces** — explicitly not a game (no graphics in the loop; visualizer,
if ever, is a read-only trace consumer). The research output — behavioral metrics
computed offline from traces — is the product; the engine is the instrument.

What remains open is the *outward* half of the question — what format the
supervisor actually wants to be shown (demo? written report? dataset?) — that now
lives in the supervisor-requirements ticket (04).
