# Model Selection

Match Claude model tier to the task, not a blanket default. Positioning below is sourced from Anthropic's own model announcements, applied to this repo's actual task categories.

| Model | Anthropic's positioning | Lane in this repo | Effort |
| --- | --- | --- | --- |
| **Haiku 4.5** | Cheapest/fastest; ~73% SWE-bench Verified; built for high-volume, parallelized sub-agent work. | Bulk mechanical fan-outs: the independent DB/schema tickets (idempotent `ALTER TABLE` additions, index/constraint fixes), triage sweeps, straightforward test scaffolding. | Low |
| **Sonnet** | Best speed/intelligence balance, near-Opus quality at lower cost; Anthropic positions it as strongest on *brownfield code* — race conditions, hidden tests, the parts nobody wants to touch. | The default workhorse: most substantive implementation and standard review, including the concurrency-hardening tickets (row locks, advisory locks, connection pooling) — exactly the brownfield territory Anthropic calls out. | Medium/high |
| **Opus** | Built for hard agentic coding: multi-file refactors, deep cross-file debugging, long unattended runs, production-quality code with minimal oversight. | The harder Field-bundle-epic legs: novel numerics (e.g. the combinatorial-optimizer's ordinal-encoded search), solver-adapter plumbing (Palace/MEEP field export), cross-cutting refactors, and pre-merge review. | High/xhigh |
| **Fable** | Anthropic's most capable model (Mythos-class, above Opus); self-correcting on multi-hour/multi-day autonomous work; strongest on the hardest ambiguous reasoning. Pricier per call than Sonnet/Opus. | Reserve for the single highest-ambiguity call in a pipeline — e.g. judging a real Palace solver run against a published reference for the embedded-PEC-conductor validation, where a wrong call invalidates every downstream claim in the Field bundle. Use sparingly; never a default or bulk-fan-out lane. | Highest, used rarely |

Pick deliberately per workflow stage and state the choice rather than defaulting silently. See the operator's global CLAUDE.md (`~/.claude/CLAUDE.md`, Operating Principles #5) for the underlying sources and the cross-project version of this table.
