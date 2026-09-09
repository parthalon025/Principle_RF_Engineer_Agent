"""Tests for designs/requirements_document.py (issue #321).

Pure-function tests only, following tests/test_requirement_targets.py's and
tests/test_design_lifecycle.py's conventions: `draft_requirements_document`/
`revise_requirements_document` plus the transition-checking functions carry
all of the ticket's actual lifecycle/validation logic and are exercised
directly here, exactly like `propose_target`/`confirm_target`/`attach_target`
are in tests/test_requirement_targets.py -- no database needed.

`create_requirements_document`/`transition_requirements_document`/
`read_requirements_document` (the I/O wrappers that actually read/write the
`requirements_documents` table) are NOT tested here: they need a live
Postgres via DATABASE_URL, and there is no database in this sandbox (same
constraint tests/test_requirement_targets.py, tests/test_designs_service.py
and tests/test_tooling.py already document for themselves). Were a live
DATABASE_URL available, a test for them would follow
tests/test_designs_service.py's own `cleanup_designs` fixture convention --
open a real connection, create a design via designs.service.create_design,
call create_requirements_document/transition_requirements_document against
it, assert read_requirements_document's payload carries the expected
revision history, and delete the design afterward. Not written here because
it cannot run in this sandbox and the pure functions it would exercise
end-to-end are already fully covered directly below -- the I/O wrappers
themselves are thin glue (open connection, fetch, validate via the pure
functions, insert, translate exceptions), the same shape
designs/requirement_targets.py's already-integration-tested wrappers use.
"""

from __future__ import annotations

import pytest

from designs.requirement_targets import mark_unscoreable, propose_target
from designs.requirements_document import (
    LEGAL_TRANSITIONS,
    TERMINAL_STATUSES,
    DocumentStatus,
    IllegalDocumentTransitionError,
    InvalidRequirementsDocumentError,
    check_transition,
    coerce_status,
    draft_requirements_document,
    legal_transitions_from,
    revise_requirements_document,
)

S = DocumentStatus


def _proposed(value: float = 2.45e9) -> dict:
    return propose_target(value=value, comparator="EQUALS", unit="Hz")


# ---------------------------------------------------------------------------
# draft_requirements_document -- creation, starting at DRAFT
# ---------------------------------------------------------------------------


def test_draft_requirements_document_starts_at_draft():
    document = draft_requirements_document(
        requirement_ids={"req-1"},
        narrative="Needs to work at 2.4 GHz without losing gain when mounted on the fuselage.",
        requirement_targets={"req-1": _proposed()},
    )
    assert document["status"] == "DRAFT"
    assert document["narrative"].startswith("Needs to work at 2.4 GHz")
    assert document["requirement_targets"]["req-1"]["target_status"] == "PROPOSED"


def test_draft_requirements_document_records_a_single_first_revision():
    document = draft_requirements_document(
        requirement_ids={"req-1"},
        narrative="Some capability narrative.",
        requirement_targets={"req-1": _proposed()},
    )
    assert len(document["revisions"]) == 1
    assert document["revisions"][0]["revision_number"] == 1
    assert document["revisions"][0]["status"] == "DRAFT"


def test_draft_requirements_document_bundles_every_requirement_row():
    document = draft_requirements_document(
        requirement_ids={"req-1", "req-2"},
        narrative="Covers both requirements.",
        requirement_targets={
            "req-1": _proposed(2.4e9),
            "req-2": mark_unscoreable("no numeric bound"),
        },
    )
    assert set(document["requirement_targets"]) == {"req-1", "req-2"}
    assert document["requirement_targets"]["req-2"]["target_status"] == "UNSCOREABLE"


def test_draft_requirements_document_rejects_empty_narrative():
    with pytest.raises(InvalidRequirementsDocumentError, match="narrative"):
        draft_requirements_document(
            requirement_ids={"req-1"}, narrative="", requirement_targets={"req-1": _proposed()}
        )


def test_draft_requirements_document_rejects_whitespace_only_narrative():
    with pytest.raises(InvalidRequirementsDocumentError, match="narrative"):
        draft_requirements_document(
            requirement_ids={"req-1"}, narrative="   ", requirement_targets={"req-1": _proposed()}
        )


def test_draft_requirements_document_rejects_missing_requirement_coverage():
    with pytest.raises(InvalidRequirementsDocumentError, match="req-2"):
        draft_requirements_document(
            requirement_ids={"req-1", "req-2"},
            narrative="Only covers one.",
            requirement_targets={"req-1": _proposed()},
        )


def test_draft_requirements_document_rejects_a_target_for_an_unknown_requirement():
    with pytest.raises(InvalidRequirementsDocumentError, match="req-stray"):
        draft_requirements_document(
            requirement_ids={"req-1"},
            narrative="Names a requirement that does not exist.",
            requirement_targets={"req-1": _proposed(), "req-stray": _proposed()},
        )


def test_draft_requirements_document_rejects_a_malformed_target_entry():
    with pytest.raises(InvalidRequirementsDocumentError, match="req-1"):
        draft_requirements_document(
            requirement_ids={"req-1"},
            narrative="A target entry that is just a bare number, not a proposed shape.",
            requirement_targets={"req-1": 2.4e9},
        )


def test_draft_requirements_document_rejects_an_already_confirmed_target_entry():
    # A document holds proposals pending confirmation -- an individual
    # target that is already CONFIRMED does not belong inside a document
    # that has not itself been confirmed.
    confirmed = propose_target(value=1.0, comparator="EQUALS", unit="Hz")
    confirmed["target_status"] = "CONFIRMED"
    with pytest.raises(InvalidRequirementsDocumentError, match="req-1"):
        draft_requirements_document(
            requirement_ids={"req-1"},
            narrative="Some narrative.",
            requirement_targets={"req-1": confirmed},
        )


def test_draft_requirements_document_accepts_no_requirements_at_all():
    document = draft_requirements_document(
        requirement_ids=set(),
        narrative="A design with no requirements yet.",
        requirement_targets={},
    )
    assert document["requirement_targets"] == {}


# ---------------------------------------------------------------------------
# revise_requirements_document -- the DRAFT -> UNDER_REVIEW -> REFINED ->
# CONFIRMED lifecycle, illegal transitions rejected
# ---------------------------------------------------------------------------


def test_the_happy_path_walks_end_to_end():
    document = draft_requirements_document(
        requirement_ids={"req-1"}, narrative="v1", requirement_targets={"req-1": _proposed()}
    )
    under_review = revise_requirements_document(
        document, "UNDER_REVIEW", "v1", {"req-1": _proposed()}, {"req-1"}
    )
    assert under_review["status"] == "UNDER_REVIEW"

    refined = revise_requirements_document(
        under_review,
        "REFINED",
        "v2 -- corrected per reviewer feedback",
        {"req-1": _proposed()},
        {"req-1"},
    )
    assert refined["status"] == "REFINED"

    confirmed = revise_requirements_document(
        refined,
        "CONFIRMED",
        "v2 -- corrected per reviewer feedback",
        {"req-1": _proposed()},
        {"req-1"},
    )
    assert confirmed["status"] == "CONFIRMED"


def test_a_document_cannot_skip_straight_from_draft_to_confirmed():
    """The transition issue #321's acceptance criteria names explicitly."""
    document = draft_requirements_document(
        requirement_ids={"req-1"}, narrative="v1", requirement_targets={"req-1": _proposed()}
    )
    with pytest.raises(IllegalDocumentTransitionError) as exc:
        revise_requirements_document(document, "CONFIRMED", "v1", {"req-1": _proposed()}, {"req-1"})
    assert "DRAFT" in str(exc.value)
    assert "CONFIRMED" in str(exc.value)


def test_a_document_cannot_skip_from_under_review_to_confirmed():
    document = draft_requirements_document(
        requirement_ids={"req-1"}, narrative="v1", requirement_targets={"req-1": _proposed()}
    )
    under_review = revise_requirements_document(
        document, "UNDER_REVIEW", "v1", {"req-1": _proposed()}, {"req-1"}
    )
    with pytest.raises(IllegalDocumentTransitionError):
        revise_requirements_document(
            under_review, "CONFIRMED", "v1", {"req-1": _proposed()}, {"req-1"}
        )


def test_refined_can_repeat_the_review_cycle():
    """ADR-0031: 'the agent revises, and the cycle repeats until the human
    confirms' -- REFINED can go back to UNDER_REVIEW for another round."""
    document = draft_requirements_document(
        requirement_ids={"req-1"}, narrative="v1", requirement_targets={"req-1": _proposed()}
    )
    under_review = revise_requirements_document(
        document, "UNDER_REVIEW", "v1", {"req-1": _proposed()}, {"req-1"}
    )
    refined = revise_requirements_document(
        under_review, "REFINED", "v2", {"req-1": _proposed()}, {"req-1"}
    )
    back_under_review = revise_requirements_document(
        refined, "UNDER_REVIEW", "v2", {"req-1": _proposed()}, {"req-1"}
    )
    assert back_under_review["status"] == "UNDER_REVIEW"


def test_confirmed_is_terminal():
    document = draft_requirements_document(
        requirement_ids={"req-1"}, narrative="v1", requirement_targets={"req-1": _proposed()}
    )
    under_review = revise_requirements_document(
        document, "UNDER_REVIEW", "v1", {"req-1": _proposed()}, {"req-1"}
    )
    refined = revise_requirements_document(
        under_review, "REFINED", "v1", {"req-1": _proposed()}, {"req-1"}
    )
    confirmed = revise_requirements_document(
        refined, "CONFIRMED", "v1", {"req-1": _proposed()}, {"req-1"}
    )
    assert legal_transitions_from(S.CONFIRMED) == frozenset()
    assert S.CONFIRMED in TERMINAL_STATUSES
    for target in DocumentStatus:
        with pytest.raises(IllegalDocumentTransitionError):
            revise_requirements_document(confirmed, target, "v1", {"req-1": _proposed()}, {"req-1"})


def test_a_status_cannot_transition_to_itself():
    for status in DocumentStatus:
        with pytest.raises(IllegalDocumentTransitionError):
            check_transition(status, status)


def test_every_status_is_a_key_in_the_transition_map():
    assert set(LEGAL_TRANSITIONS) == set(DocumentStatus)


def test_check_transition_accepts_plain_strings():
    check_transition("DRAFT", "UNDER_REVIEW")
    with pytest.raises(IllegalDocumentTransitionError):
        check_transition("DRAFT", "CONFIRMED")


def test_an_unknown_status_is_rejected_by_name():
    with pytest.raises(ValueError, match="ACTIVE"):
        check_transition("DRAFT", "ACTIVE")


def test_coerce_status_accepts_a_documentstatus_or_its_string_value():
    assert coerce_status(S.DRAFT) is S.DRAFT
    assert coerce_status("DRAFT") is S.DRAFT


def test_revise_requirements_document_rejects_updated_content_that_omits_a_requirement():
    document = draft_requirements_document(
        requirement_ids={"req-1", "req-2"},
        narrative="v1",
        requirement_targets={"req-1": _proposed(), "req-2": mark_unscoreable("no bound")},
    )
    with pytest.raises(InvalidRequirementsDocumentError, match="req-2"):
        revise_requirements_document(
            document, "UNDER_REVIEW", "v2", {"req-1": _proposed()}, {"req-1", "req-2"}
        )


# ---------------------------------------------------------------------------
# History readback -- every revision kept, never overwritten
# ---------------------------------------------------------------------------


def test_every_revision_is_kept_and_readable_after_a_status_advances():
    document = draft_requirements_document(
        requirement_ids={"req-1"}, narrative="v1", requirement_targets={"req-1": _proposed(1.0)}
    )
    under_review = revise_requirements_document(
        document,
        "UNDER_REVIEW",
        "v2 -- reviewer pushed back on the frequency",
        {"req-1": _proposed(2.0)},
        {"req-1"},
    )
    refined = revise_requirements_document(
        under_review, "REFINED", "v3 -- corrected", {"req-1": _proposed(3.0)}, {"req-1"}
    )

    assert [r["revision_number"] for r in refined["revisions"]] == [1, 2, 3]
    assert [r["status"] for r in refined["revisions"]] == ["DRAFT", "UNDER_REVIEW", "REFINED"]
    assert refined["revisions"][0]["narrative"] == "v1"
    assert refined["revisions"][0]["requirement_targets"]["req-1"]["value"] == 1.0
    assert refined["revisions"][1]["narrative"] == "v2 -- reviewer pushed back on the frequency"
    assert refined["revisions"][2]["narrative"] == "v3 -- corrected"


def test_the_current_view_mirrors_only_the_latest_revision():
    document = draft_requirements_document(
        requirement_ids={"req-1"}, narrative="v1", requirement_targets={"req-1": _proposed(1.0)}
    )
    under_review = revise_requirements_document(
        document, "UNDER_REVIEW", "v2", {"req-1": _proposed(2.0)}, {"req-1"}
    )
    assert under_review["narrative"] == "v2"
    assert under_review["requirement_targets"]["req-1"]["value"] == 2.0
    # the superseded first draft is still readable in the history
    assert under_review["revisions"][0]["narrative"] == "v1"


def test_revise_requirements_document_does_not_mutate_its_input():
    document = draft_requirements_document(
        requirement_ids={"req-1"}, narrative="v1", requirement_targets={"req-1": _proposed(1.0)}
    )
    revise_requirements_document(
        document, "UNDER_REVIEW", "v2", {"req-1": _proposed(2.0)}, {"req-1"}
    )
    assert document["status"] == "DRAFT"
    assert document["narrative"] == "v1"
    assert len(document["revisions"]) == 1


# ---------------------------------------------------------------------------
# DocumentStatus -- the fixed vocabulary itself
# ---------------------------------------------------------------------------


def test_document_status_covers_the_four_lifecycle_states():
    assert {s.value for s in DocumentStatus} == {"DRAFT", "UNDER_REVIEW", "REFINED", "CONFIRMED"}
