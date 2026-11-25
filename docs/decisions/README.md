# Decision Records (ADRs)

One file per non-trivial, hard-to-reverse decision. Numbered sequentially:
`NNNN-short-slug.md`. Copy `0000-template.md` to start one.

Lifecycle statuses: **Proposed → Accepted / Rejected**, later **Superseded by NNNN**.
Accepted ADRs are never edited — a change of mind gets a new ADR that supersedes
the old one (update the old one's Status line to point at the new number).

| # | Title | Status |
|---|-------|--------|
| [0001](0001-engine-shape-headless-python-tick-engine.md) | Engine shape: headless deterministic Python tick engine | Accepted |
| [0002](0002-agent-interface-text-json-api.md) | Agent interface: text/JSON obs–action API, ≤4 agents | Accepted |
| [0003](0003-tile-granularity-and-spatial-rules.md) | Spatial model: one tile = one room; no-gotchas tile rules | Proposed |
| [0004](0004-terrain-deposit-layering.md) | Split terrain and deposits; finite multi-resource deposits | Proposed |
| [0005](0005-worldbook-and-agent-protocol.md) | Full worldbook in prompt; verbatim history; one repair retry | Proposed |
| [0006](0006-episode-terminal-states.md) | Episode semantics: three terminal states, permanent death | Proposed |
| [0007](0007-scenario-format-declarative-data.md) | Scenarios are declarative data files | Proposed |
| [0008](0008-experiment-protocol.md) | Experiment protocol: paired seeds, versioned artifacts, ≥5 seeds | Proposed |
| [0009](0009-defer-comms-and-private-ownership.md) | Defer inter-agent communication and private ownership | Proposed |

Keep the table above current when adding a record.
