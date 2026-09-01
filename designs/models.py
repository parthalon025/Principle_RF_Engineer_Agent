"""Shared types for the design-tracking package.

Ticket #17 (design creation, first of the #16 epic) adds the two enums the
domain model fixes for a `designs` row and a `verification_items` row --
see CONTEXT.md's Vocabulary section and docs/adr/0005/0006/0007 for the
rationale. Draft dataclasses for `engineering_results`/`decision_records`
move between pipeline stages the same way `knowledge/models.py`'s
`DocumentDraft`/`ChunkDraft` do, but belong to #18-#21, whichever ticket
first needs to write one of those tables -- not added here.
"""

from __future__ import annotations

from enum import StrEnum


class DesignStatus(StrEnum):
    """Lifecycle status of a `designs` row.

    This is `docs/OPERATIONS.md`'s existing workflow lifecycle --
    `DRAFT -> ANALYSIS -> SIMULATION -> OPTIMIZATION -> VERIFICATION ->
    CONDITIONAL-PASS/PASS/FAIL/BLOCKED -> RELEASED`, `RELEASED` requiring
    human approval -- not a set of values invented for this ticket set
    (docs/adr/0007 corrects #16/#17's original spec, which proposed a
    two-value `DRAFT`/`ACTIVE` stand-in without having consulted
    `OPERATIONS.md` first).

    `create_design` (#17) only ever writes `DRAFT`. No transition logic
    between the other nine states, and no enforcement of `OPERATIONS.md`'s
    state order, exists yet in this ticket or its #18-#21 siblings -- this
    enum only fixes which values the column may legally hold, not how a
    design moves between them.
    """

    DRAFT = "DRAFT"
    ANALYSIS = "ANALYSIS"
    SIMULATION = "SIMULATION"
    OPTIMIZATION = "OPTIMIZATION"
    VERIFICATION = "VERIFICATION"
    CONDITIONAL_PASS = "CONDITIONAL-PASS"
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    RELEASED = "RELEASED"


class VerificationStatus(StrEnum):
    """Status of one `verification_items` row (#16 story 19, 7). A row is
    auto-created NOT_VERIFIED per requirement key at design-creation time
    (this ticket); moving it to PASS/FAIL/MARGINAL is `verify_requirement`'s
    concern (#20), always by an explicit call, never inferred."""

    NOT_VERIFIED = "NOT VERIFIED"
    PASS = "PASS"
    FAIL = "FAIL"
    MARGINAL = "MARGINAL"
