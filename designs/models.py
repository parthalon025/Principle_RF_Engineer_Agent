"""Shared types for the design-tracking package.

Ticket #17 (design creation, first of the #16 epic) adds the two enums the
domain model fixes for a `designs` row and a `verification_items` row --
see CONTEXT.md's Vocabulary section and docs/adr/0005/0006 for the
rationale. Draft dataclasses for `engineering_results`/`decision_records`
move between pipeline stages the same way `knowledge/models.py`'s
`DocumentDraft`/`ChunkDraft` do, but belong to #18-#21, whichever ticket
first needs to write one of those tables -- not added here.
"""

from __future__ import annotations

from enum import StrEnum


class DesignStatus(StrEnum):
    """Lifecycle status of a `designs` row (#16 story 5/6). A design always
    starts DRAFT; ACTIVE is the only other status this ticket-set defines.
    Any `manufacturing_release`-related status is explicitly out of scope
    until the ticket that adds that tool exists."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"


class VerificationStatus(StrEnum):
    """Status of one `verification_items` row (#16 story 19, 7). A row is
    auto-created NOT_VERIFIED per requirement key at design-creation time
    (this ticket); moving it to PASS/FAIL/MARGINAL is `verify_requirement`'s
    concern (#20), always by an explicit call, never inferred."""

    NOT_VERIFIED = "NOT VERIFIED"
    PASS = "PASS"
    FAIL = "FAIL"
    MARGINAL = "MARGINAL"
