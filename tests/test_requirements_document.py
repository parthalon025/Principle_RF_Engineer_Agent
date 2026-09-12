"""Tests for designs/requirements_document.py (issue #321).

Pure-function tests only, following tests/test_requirement_targets.py's and
tests/test_design_lifecycle.py's conventions: `draft_requirements_document`/
`revise_requirements_document` plus the transition-checking functions carry
all of the ticket's actual lifecycle/validation logic and are exercised
directly here, exactly like `propose_target`/`confirm_target`/`attach_target`
are in tests/test_requirement_targets.py -- no database needed.

`create_requirements_document`/`transition_requirements_document`/
`read_requirements_document` (the I/O wrappers that actually read/write the
`requirements_documents` table) are mostly NOT tested here: they need a live
Postgres via DATABASE_URL, which most sandboxes running this suite don't have
(same constraint tests/test_requirement_targets.py, tests/test_designs_service.py
and tests/test_tooling.py already document for themselves) -- the I/O wrappers
are thin glue (open connection, fetch, validate via the pure functions,
insert, translate exceptions), the same shape
designs/requirement_targets.py's already-integration-tested wrappers use, and
the pure functions they call are already fully covered directly above.

The one exception, guarded by the module-level `DATABASE_URL` connectivity
probe at the bottom of this file (mirroring
tests/test_requirement_targets.py's identical `pytest.mark.skipif` pattern,
itself mirroring tests/test_element_alphabet.py's): `create_requirements_document`'s
and `transition_requirements_document`'s `not_found`/`already_exists`/
`no_document`/`illegal_transition`/`invalid_document` rollback branches
(issue #504, issue #514) -- every one of these is an early
`conn.rollback(); return {...}` inside the outer try/except that issue #504
is about to collapse into a shared helper, and none of them had a test at the
public-function level before this. Pinning today's exact `status`-tagged
dict for each is the regression net that refactor needs.
"""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest
from dotenv import load_dotenv

from designs.requirement_targets import mark_unscoreable, propose_intended_effect, propose_target
from designs.requirements_document import (
    LEGAL_TRANSITIONS,
    TERMINAL_STATUSES,
    DocumentStatus,
    IllegalDocumentTransitionError,
    InvalidRequirementsDocumentError,
    check_transition,
    coerce_status,
    create_requirements_document,
    draft_requirements_document,
    extract_requirement_fields,
    legal_transitions_from,
    revise_requirements_document,
    transition_requirements_document,
)
from designs.service import create_design

load_dotenv()

S = DocumentStatus


def _proposed(value: float = 2.45e9) -> dict:
    return propose_target(value=value, comparator="EQUALS", unit="Hz")


def _proposed_with_intent(value: float, effect: str) -> dict:
    """A `propose_target` shape carrying an `intended_effect` extra key --
    how a document's per-requirement entry states both the numeric target
    and the intended effect together (issue #323, docs/adr/0030)."""
    target = propose_target(value=value, comparator="EQUALS", unit="Hz")
    target["intended_effect"] = propose_intended_effect(effect)
    return target


def _confirm(document: dict, narrative: str, requirement_targets: dict, requirement_ids) -> dict:
    """Walk `document` through the full DRAFT -> UNDER_REVIEW -> REFINED ->
    CONFIRMED lifecycle, restating the same content at every step (mirrors
    test_the_happy_path_walks_end_to_end) -- a convenience for extraction
    tests that don't care about the intermediate review rounds themselves."""
    under_review = revise_requirements_document(
        document, "UNDER_REVIEW", narrative, requirement_targets, requirement_ids
    )
    refined = revise_requirements_document(
        under_review, "REFINED", narrative, requirement_targets, requirement_ids
    )
    return revise_requirements_document(
        refined, "CONFIRMED", narrative, requirement_targets, requirement_ids
    )


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
    """ADR-0034: 'the agent revises, and the cycle repeats until the human
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


# ---------------------------------------------------------------------------
# extract_requirement_fields -- attach_target/attach_intent from a CONFIRMED
# document onto a design's own requirements (issue #323, docs/adr/0034)
# ---------------------------------------------------------------------------


def test_extract_requirement_fields_writes_target_and_intended_effect():
    requirement_targets = {"req-1": _proposed_with_intent(2.4e9, "behave as a magnetic mirror")}
    document = draft_requirements_document(
        requirement_ids={"req-1"},
        narrative="Needs to behave as a magnetic mirror at 2.4 GHz.",
        requirement_targets=requirement_targets,
    )
    confirmed = _confirm(document, document["narrative"], requirement_targets, {"req-1"})

    requirements = {"req-1": {"requirement": "needs to behave as a magnetic mirror at 2.4 GHz"}}
    updated = extract_requirement_fields(requirements, confirmed)

    assert updated["req-1"]["target"]["value"] == 2.4e9
    assert updated["req-1"]["target"]["target_status"] == "PROPOSED"
    assert updated["req-1"]["intended_effect"]["effect"] == "behave as a magnetic mirror"
    # the original prose is untouched
    assert updated["req-1"]["requirement"] == "needs to behave as a magnetic mirror at 2.4 GHz"


def test_extract_requirement_fields_handles_the_compound_ask_case():
    """A customer wanting two different things from one design is two
    ordinary Customer requirement rows, each independently extracted with
    its own intended_effect from the same confirmed document (issue #323
    acceptance criteria)."""
    requirement_targets = {
        "req-1": _proposed_with_intent(2.4e9, "behave as a magnetic mirror"),
        "req-2": _proposed_with_intent(10.0, "absorb the wave"),
    }
    document = draft_requirements_document(
        requirement_ids={"req-1", "req-2"},
        narrative="Wants both a magnetic mirror and absorption from one design.",
        requirement_targets=requirement_targets,
    )
    confirmed = _confirm(document, document["narrative"], requirement_targets, {"req-1", "req-2"})

    requirements = {
        "req-1": {"requirement": "should behave as a magnetic mirror"},
        "req-2": {"requirement": "should absorb the wave"},
    }
    updated = extract_requirement_fields(requirements, confirmed)

    assert updated["req-1"]["intended_effect"]["effect"] == "behave as a magnetic mirror"
    assert updated["req-2"]["intended_effect"]["effect"] == "absorb the wave"
    assert updated["req-1"]["target"]["value"] == 2.4e9
    assert updated["req-2"]["target"]["value"] == 10.0


def test_extract_requirement_fields_leaves_a_requirement_without_a_stated_effect():
    """ADR-0030's 'having none is a legal answer' -- a bend radius asks
    nothing of the wave, so a document entry with no intended_effect key
    leaves the requirement without one after extraction."""
    requirement_targets = {"req-1": _proposed(5.0)}  # no intended_effect key
    document = draft_requirements_document(
        requirement_ids={"req-1"},
        narrative="bend radius <= 5 mm",
        requirement_targets=requirement_targets,
    )
    confirmed = _confirm(document, document["narrative"], requirement_targets, {"req-1"})

    requirements = {"req-1": {"requirement": "bend radius <= 5 mm"}}
    updated = extract_requirement_fields(requirements, confirmed)

    assert "intended_effect" not in updated["req-1"]
    assert updated["req-1"]["target"]["value"] == 5.0


def test_extract_requirement_fields_rejects_a_document_that_is_not_confirmed():
    requirement_targets = {"req-1": _proposed_with_intent(2.4e9, "behave as a magnetic mirror")}
    document = draft_requirements_document(
        requirement_ids={"req-1"}, narrative="v1", requirement_targets=requirement_targets
    )
    requirements = {"req-1": {"requirement": "some prose"}}
    with pytest.raises(InvalidRequirementsDocumentError, match="CONFIRMED"):
        extract_requirement_fields(requirements, document)


def test_extract_requirement_fields_provenance_stays_assumed_across_review_rounds():
    """issue #323 acceptance criteria: intended_effect/target provenance
    stays ASSUMED regardless of how many review rounds the document went
    through."""
    v1_targets = {"req-1": _proposed_with_intent(1.0, "absorb the wave")}
    document = draft_requirements_document(
        requirement_ids={"req-1"}, narrative="v1", requirement_targets=v1_targets
    )
    v2_targets = {"req-1": _proposed_with_intent(2.0, "absorb the wave, revised")}
    under_review = revise_requirements_document(
        document, "UNDER_REVIEW", "v2", v2_targets, {"req-1"}
    )
    v3_targets = {"req-1": _proposed_with_intent(3.0, "absorb the wave, corrected")}
    refined = revise_requirements_document(under_review, "REFINED", "v3", v3_targets, {"req-1"})
    confirmed = revise_requirements_document(refined, "CONFIRMED", "v3", v3_targets, {"req-1"})

    requirements = {"req-1": {"requirement": "some prose"}}
    updated = extract_requirement_fields(requirements, confirmed)

    assert updated["req-1"]["target"]["provenance"] == "ASSUMED"
    assert updated["req-1"]["intended_effect"]["provenance"] == "ASSUMED"


def test_extract_requirement_fields_does_not_mutate_its_inputs():
    requirement_targets = {"req-1": _proposed_with_intent(1.0, "absorb the wave")}
    document = draft_requirements_document(
        requirement_ids={"req-1"}, narrative="v1", requirement_targets=requirement_targets
    )
    confirmed = _confirm(document, document["narrative"], requirement_targets, {"req-1"})

    requirements = {"req-1": {"requirement": "some prose"}}
    extract_requirement_fields(requirements, confirmed)
    assert "target" not in requirements["req-1"]
    assert "intended_effect" not in requirements["req-1"]


# ---------------------------------------------------------------------------
# DB-backed: create_requirements_document / transition_requirements_document
# rollback branches (issue #504, issue #514) -- see this module's docstring
# for why this is the one DB-backed section here.
# ---------------------------------------------------------------------------

_TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://rf:rf_dev_password@localhost:5432/rfengineer"
)


def _database_reachable() -> bool:
    try:
        with psycopg.connect(_TEST_DATABASE_URL, connect_timeout=3):
            return True
    except psycopg.OperationalError:
        return False


_DB_REACHABLE = _database_reachable()

#: A design_id no `designs` row will ever have -- ids are a positive serial
#: primary key, so a negative id is unambiguously nonexistent without
#: needing to create-then-delete a design just to get a fresh one.
_NONEXISTENT_DESIGN_ID = -1


@pytest.mark.skipif(
    not _DB_REACHABLE,
    reason=f"no reachable Postgres at {_TEST_DATABASE_URL.split('@')[-1]!r} in this sandbox",
)
class TestCreateAndTransitionRequirementsDocumentRollbackBranches:
    @pytest.fixture
    def cleanup_designs(self):
        """Mirrors tests/test_designs_service.py's own fixture of the same
        name: `create_design` commits its own connection, so cleanup can't
        rely on a rolled-back transaction for isolation."""
        ids: list[int] = []
        yield ids
        if not ids:
            return
        conn = psycopg.connect(_TEST_DATABASE_URL, autocommit=True)
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM designs WHERE id = ANY(%s)", (ids,))
        finally:
            conn.close()

    @pytest.fixture
    def design_id(self, cleanup_designs):
        """A stored design with a single Customer requirement row, `REQ-1`
        -- exactly the coverage `draft_requirements_document`/
        `revise_requirements_document` require."""
        result = create_design(
            design_key=f"REQDOC-{uuid.uuid4().hex[:8]}",
            name="Requirements Document Fixture Design",
            revision="A",
            requirements={"REQ-1": {"requirement": "Gain >= 20 dB."}},
            architecture={},
        )
        design_id = result["design_id"]
        cleanup_designs.append(design_id)
        return design_id

    # -- create_requirements_document ------------------------------------

    def test_create_requirements_document_not_found(self):
        result = create_requirements_document(
            design_id=_NONEXISTENT_DESIGN_ID,
            narrative="Needs to work at 2.4 GHz.",
            requirement_targets={"REQ-1": _proposed()},
        )
        assert result == {"status": "not_found", "design_id": _NONEXISTENT_DESIGN_ID}

    def test_create_requirements_document_already_exists(self, design_id):
        first = create_requirements_document(
            design_id=design_id,
            narrative="Needs to work at 2.4 GHz.",
            requirement_targets={"REQ-1": _proposed()},
        )
        assert first["status"] == "created"

        second = create_requirements_document(
            design_id=design_id,
            narrative="A second, different narrative.",
            requirement_targets={"REQ-1": _proposed(5.0e9)},
        )
        assert second == {
            "status": "already_exists",
            "design_id": design_id,
            "message": (
                f"design_id {design_id!r} already has a Requirements document -- "
                "call transition_requirements_document to revise it"
            ),
        }

    def test_create_requirements_document_invalid_document(self, design_id):
        result = create_requirements_document(
            design_id=design_id,
            narrative="",
            requirement_targets={"REQ-1": _proposed()},
        )
        assert result["status"] == "invalid_document"
        assert "narrative" in result["message"]

    # -- transition_requirements_document ---------------------------------

    def test_transition_requirements_document_not_found(self):
        result = transition_requirements_document(
            design_id=_NONEXISTENT_DESIGN_ID,
            status="UNDER_REVIEW",
            narrative="Needs to work at 2.4 GHz.",
            requirement_targets={"REQ-1": _proposed()},
        )
        assert result == {"status": "not_found", "design_id": _NONEXISTENT_DESIGN_ID}

    def test_transition_requirements_document_no_document(self, design_id):
        result = transition_requirements_document(
            design_id=design_id,
            status="UNDER_REVIEW",
            narrative="Needs to work at 2.4 GHz.",
            requirement_targets={"REQ-1": _proposed()},
        )
        assert result == {
            "status": "no_document",
            "design_id": design_id,
            "message": (
                f"design_id {design_id!r} has no Requirements document yet -- "
                "call create_requirements_document first"
            ),
        }

    def test_transition_requirements_document_illegal_transition(self, design_id):
        created = create_requirements_document(
            design_id=design_id,
            narrative="Needs to work at 2.4 GHz.",
            requirement_targets={"REQ-1": _proposed()},
        )
        assert created["status"] == "created"

        # DRAFT -> CONFIRMED directly is illegal -- the acceptance
        # criteria's own worked example, at the public-function level.
        result = transition_requirements_document(
            design_id=design_id,
            status="CONFIRMED",
            narrative="Needs to work at 2.4 GHz.",
            requirement_targets={"REQ-1": _proposed()},
        )
        assert result["status"] == "illegal_transition"
        assert result["current_status"] == "DRAFT"
        assert result["requested_status"] == "CONFIRMED"
        assert result["legal_next"] == ["UNDER_REVIEW"]
        assert "DRAFT" in result["message"]
        assert "CONFIRMED" in result["message"]
        assert set(result) == {
            "status",
            "message",
            "current_status",
            "requested_status",
            "legal_next",
        }

    def test_transition_requirements_document_invalid_document(self, design_id):
        created = create_requirements_document(
            design_id=design_id,
            narrative="Needs to work at 2.4 GHz.",
            requirement_targets={"REQ-1": _proposed()},
        )
        assert created["status"] == "created"

        result = transition_requirements_document(
            design_id=design_id,
            status="UNDER_REVIEW",
            narrative="   ",
            requirement_targets={"REQ-1": _proposed()},
        )
        assert result["status"] == "invalid_document"
        assert "narrative" in result["message"]
