---
status: accepted
---

# A human's recorded rejection carries forward; the rejected value does not

Issue #104's wayfinder map states, as its most-repeated standing
preference, that **a guess never becomes settled by repetition**: each
design pass re-derives its constraints from the original customer
requirement rather than inheriting the previous pass's conclusions.
Ticket #125 ("What does an overnight run hand the morning reviewer?")
wants the opposite behaviour for one specific thing — when a reviewer
rejects a proposal in the morning, the next run should not present the
same idea again. The map flagged the collision explicitly and required
that any carve-out **argue itself** in the manner of ADR-0015 rather
than be assumed. This is that argument.

## Decision

**A human's recorded rejection is a deliberate, named exception to the
no-inheritance rule, on the same grounds as ADR-0015's material
properties.** ADR-0015 carved out material data because a material's εr
at 10 GHz is a fact about the *material*, true regardless of which
requirement is asking, whereas a threshold is a fact about one
requirement. The same distinction applies here: *"a human rejected this
proposal on 8 September, because X"* is a fact about **what a person
decided**. It is history, not physics, and replaying it inherits no
engineering guess.

**The discipline that keeps this honest: store the refusal, never the
conclusion.** The record is the rejection event — what was proposed, who
refused it, when, and the stated reason. It is *not* a statement that the
underlying idea is wrong. A later run may read "this was refused before,
and here is why" and must still re-derive the physics from scratch. *In
plain terms: the loop is allowed to remember that you said no. It is not
allowed to conclude that you were right.*

That line is what keeps the exception narrow. Storing the rejected
*value* as settled would launder a guess into a fact by exactly the route
the standing preference exists to block; storing the *event* records
something that genuinely happened and cannot be re-derived by any amount
of recomputation.

**Why it earns an exception at all — an efficiency argument, not a
courtesy one.** A run has a fixed evaluation budget (`evaluation_budget`,
`orchestration/solver.py:1085`). Every slot spent re-testing an idea the
reviewer already killed is a slot not spent finding a better design. Under
the stated goal of getting the best result against the customer's
requirement, re-proposing dead ideas is not merely tiresome — it directly
lowers the ceiling on the answer, because the budget is finite. The
reviewer's patience is the lesser of the two costs.

**Storage and shape** follow ADR-0025: the rejection is keyed against
that ADR's structured considered-and-dropped ledger, so a
proposal-generation call can look up "was this already refused" and get a
deterministic hit or miss rather than a probabilistic read of prose.

## Considered and rejected

- **No memory at all — re-derive everything every run, exception-free.**
  The purest reading of the standing preference, and rejected on the
  budget argument above: it spends a finite resource re-litigating
  settled human decisions, which costs result quality rather than only
  patience.
- **Remembering the rejected value as settled** ("silicone was ruled
  out"). Rejected: this is precisely the laundering the no-inheritance
  rule exists to prevent. A reviewer's no in one context is not a
  physical fact about the material, and a later requirement with a
  different host surface may make the same candidate correct.
- **Folding this into ADR-0025 as a sub-decision.** Rejected on
  ADR-0015's precedent and on the map's own recorded experience: a
  rule-exception buried inside a longer document about something else is
  applied by future readers who never encounter the argument for it —
  the failure mode `docs/RUNNING-LISTS.md` §3 keeps recording. Kept
  separate so it can also be superseded alone if the carve-out proves
  wrong, without disturbing the report design.

## Consequences

- **Blocked on a prerequisite.** `orchestration/tooling.py:237`
  hardcodes `"alternatives": []` for every `architecture_decision` and
  `redesign_decision`, discarding rejected options at the flush. Until
  that reads from the step input, there is nothing for this ADR to
  remember. Filed as its own `ready-for-agent` issue.
- **The exception list is now two entries long** (ADR-0015's material
  properties, and this). A third should be viewed with suspicion: an
  exception per awkward case is how a rule stops meaning anything.
