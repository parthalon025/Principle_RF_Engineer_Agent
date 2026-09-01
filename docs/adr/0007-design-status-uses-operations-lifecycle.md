---
status: accepted
---

# `designs.status` uses `docs/OPERATIONS.md`'s existing lifecycle

The `/grill-with-docs` session that produced ADR-0005/0006 and issue #16
proposed `designs.status` as just `DRAFT`/`ACTIVE`, deferring every
release-related state to whichever future ticket builds
`manufacturing_release`. That was a mistake, not a considered trade-off:
`docs/OPERATIONS.md` already specifies a full workflow lifecycle —
`DRAFT → ANALYSIS → SIMULATION → OPTIMIZATION → VERIFICATION →
CONDITIONAL-PASS/PASS/FAIL/BLOCKED → RELEASED`, with "`RELEASED` requires
human approval" stated outright — and nobody consulted it before writing
the spec. `designs.status` is that lifecycle, not a two-value stand-in
invented for this ticket set.

This corrects, rather than contradicts, ADR-0005: `RELEASED` already
*is* the human-approval-gated terminal state ADR-0005 discusses in the
abstract via `manufacturing_release` — `OPERATIONS.md` had already settled
that a release needs human sign-off before this epic existed. The scope
boundary ADR-0005 draws (the gate isn't operative yet — no tool checks it,
no UI flips it) still holds; only the shape of `status` changes.

## Consequences

`designs/models.py`'s `DesignStatus` takes all nine `OPERATIONS.md` values,
not two. A design is created in `DRAFT` (unchanged). Nothing in the
design-creation ticket (#17) or its siblings (#18-#21) builds transition
logic between the other states or enforces `OPERATIONS.md`'s state order —
that remains future work, same as `manufacturing_release` itself; this ADR
only fixes which values the column may legally hold, not how a design
moves between them.
