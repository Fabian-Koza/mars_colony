# 0005 — Full worldbook in prompt; verbatim history; one repair retry

- **Date:** 2026-11-25
- **Status:** Proposed
- **Decided with:** Fabian + Hermes

## Context

The agent's information regime — what it is told about the rules, what it
remembers across sols, and what happens on malformed output — is the
biggest confound in LLM behavioral measurement. Today it is emergent
accident, not design: the harness prompt is ad-hoc, each sol appends a
fresh observation, and invalid actions already log reasons but there is no
repair policy.

## Decision

**The agent gets the complete rulebook up front.** A static, versioned
worldbook file (costs, production rates, death thresholds, spatial rules
from ADR-0003, deposit rules from ADR-0004, action JSON schema, one worked
example) forms a fixed system-prompt prefix; its hash is recorded in the
trace header. **Full verbatim history** (all past observations/actions)
stays in context while episodes fit; summarization/memory-windowing is a
later deliberate scenario variant, not a workaround. **Malformed/invalid
action → exactly one retry** showing the validation error, then the agent
auto-`wait`s that sol; the retry count is logged. **Every observation
includes the previous sol's action resolution** (`ok`/`invalid + reason`).

## Options considered

1. **Full worldbook vs hidden rules** — hidden rules measure
   reverse-engineering of a spec, not decisions under scarcity; keep
   knowledge as an experimental *axis* via scenario variants (`full`,
   `economy_only`, `no_death_rules`), never as the baseline. Chosen.
2. **Verbatim history vs summary memory** — ~100 sols x ~250 tokens fits
   easily; inventing a memory architecture now solves a problem we don't
   have. Chosen for now; windowed-memory scenario variant becomes a
   memory-stress experiment later.
3. **Zero-tolerance auto-wait (no retry)** — harsher, but it conflates
   JSON formatting skill with decision quality, which destroys
   cross-model comparability (our 6-model sweep already shows invalid-count
   spread 2..8). Rejected; the retry count itself becomes a metric.

## Consequences

- Easy: "bad decisions" vs "bad at JSON" become separable metrics;
  static-prefix-first ordering also earns vLLM prefix caching; prompt-text
  changes are version bumps (see ADR-0008 freeze policy).
- Required discipline: worldbook lives in one file; changing any rule text
  requires a version bump; per-turn timestamps added to the LLM log
  (still missing) so decision-latency can become a metric.
- Long-episode context overflow, when it arrives, is handled by a new ADR
  (memory model), not by ad-hoc truncation in the harness.
