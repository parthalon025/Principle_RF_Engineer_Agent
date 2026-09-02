---
status: accepted
---

# The design loop is opt-in governance layered over the tool surface, not the primary way to use it

`/grill-with-docs` on the RF tool orchestration flow considered whether the
agent should be steered toward `start_design_loop`/`advance_design_loop_step`
whenever one is active, rather than calling `calculate_patch_resonant_frequency`,
`run_nec2_simulation`, etc. directly. Rejected: the ~65-tool flat surface and
the 9-step governed loop serve different purposes and both need to stay
frictionless for their own purpose. Quick prototyping and brainstorming —
sanity-checking a resonant frequency, trying a few candidate geometries,
exploring "what if" before anything is worth tracking — must stay a single
tool call with no ceremony. The loop exists for work someone has
deliberately chosen to track formally: it gates `ARCHITECTURE`/
`MEASUREMENT`/`REDESIGN_DECISION` behind a human-approval receipt (issue
#46) and, per ADR-0011, now persists its history to `designs`/
`decision_records`/`engineering_results`/`verification_items`. Steering
every RF calculation through that machinery by default would tax the
exploratory case for the benefit of the tracked case, without the user
having asked for tracking.

Both paths call the same underlying deterministic functions
(`rf_tools.calculations`, `simulation.*`, `measurement.*`) — the loop adds
no new RF capability, only the ordering, gating, and persistence around an
explicit design-iteration workflow.

## Consequences

Nothing structurally stops important design work from happening entirely
outside a tracked loop — there's no way to know from the system alone that
"significant" work bypassed governance. `prompts/principal_engineer.md`
states the distinction explicitly (quick tool calls are exploratory and
untracked; the loop is for design work meant to be recorded and reviewed)
so the model represents its own output accurately to the user, but nothing
enforces the choice.
