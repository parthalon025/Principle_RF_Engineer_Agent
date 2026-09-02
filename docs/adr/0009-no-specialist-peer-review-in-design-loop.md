---
status: accepted
---

# The design loop records decisions as-authored; it does not add a specialist peer-review step

`/grill-with-docs` on the RF tool orchestration flow considered whether
`advance_design_loop_step` should require a specialist role (antenna,
microwave, ...) to formally weigh in before an `ARCHITECTURE` or
`REDESIGN_DECISION` step is recorded — the same way `GATED_STEPS` already
requires a human-approval receipt for those steps. Rejected: every
specialist role in `agent/main.py`'s `ROLE_SPECS` is the same underlying
LLM under a different system-prompt/tool-scoping, not an independent human
expert. A "specialist sign-off" between two LLM personas would not
constitute independent review — it would just be the model checking its
own work under a different hat, and recording that as if it were a real
second opinion would misrepresent the decision's actual evidence quality.

The principal role can still consult a specialist informally in
conversation before authoring an `ARCHITECTURE`/`REDESIGN_DECISION` step —
nothing prevents that — but the loop records only the conclusion
(`decision`/`rationale` in `step_input`), not a formal chain of who was
asked. `LoopStepApprovalReceipt`'s human-approval gate (`GATED_STEPS`,
`orchestration/approval.py`) remains the loop's only real independent
check, because it is bound to an actual human, not another LLM invocation.

## Consequences

If this project later needs to prove a specialist perspective was actually
consulted on a given decision (e.g. for a customer audit), that requires a
new mechanism — this ADR does not build a seam for it, unlike the
approval-callback pattern used elsewhere in this codebase. Revisit if that
need arises.
