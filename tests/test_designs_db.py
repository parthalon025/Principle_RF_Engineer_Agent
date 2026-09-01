import pytest

from designs.db import (
    DanglingComponentReferenceError,
    RecordKeyCollisionError,
    create_design,
    record_decision,
)
from designs.validation import InvalidRequirementsError
from knowledge.db import upsert_component


def _make_component(db_conn, part_number="ACM-AMP-1"):
    row = upsert_component(
        db_conn,
        manufacturer="Acme RF",
        part_number=part_number,
        category="amplifier",
        specifications={"gain_db": {"value": 20.0, "unit": "dB"}},
        datasheet_document_id=None,
    )
    return row["id"]


def _requirements(*ids):
    return {req_id: {"requirement": f"Requirement {req_id}."} for req_id in ids}


def _make_design(db_conn, design_key="DES-DEC"):
    row = create_design(
        db_conn,
        design_key=design_key,
        name="Decision Host Design",
        revision="A",
        requirements={},
        architecture={},
    )
    return row["id"]


def test_create_design_creates_row_in_draft_status(db_conn):
    row = create_design(
        db_conn,
        design_key="DES-1",
        name="Test Design",
        revision="A",
        requirements={},
        architecture={},
    )
    assert row["design_key"] == "DES-1"
    assert row["name"] == "Test Design"
    assert row["revision"] == "A"
    assert row["status"] == "DRAFT"


def test_create_design_with_empty_requirements_creates_no_verification_items(db_conn):
    row = create_design(
        db_conn,
        design_key="DES-2",
        name="Empty Reqs Design",
        revision="A",
        requirements={},
        architecture={},
    )
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM verification_items WHERE design_id = %s", (row["id"],))
        (count,) = cur.fetchone()
    assert count == 0


def test_create_design_auto_creates_one_verification_item_per_requirement(db_conn):
    requirements = _requirements("REQ-1", "REQ-2", "REQ-3")
    row = create_design(
        db_conn,
        design_key="DES-3",
        name="Multi-Req Design",
        revision="A",
        requirements=requirements,
        architecture={},
    )

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT requirement_id, requirement, status FROM verification_items "
            "WHERE design_id = %s ORDER BY requirement_id",
            (row["id"],),
        )
        items = cur.fetchall()

    assert [i[0] for i in items] == ["REQ-1", "REQ-2", "REQ-3"]
    for (requirement_id, requirement_text, status) in items:
        assert requirement_text == f"Requirement {requirement_id}."
        assert status == "NOT VERIFIED"


def test_create_design_accepts_valid_component_id_reference(db_conn):
    component_id = _make_component(db_conn, part_number="ACM-AMP-VALID")
    row = create_design(
        db_conn,
        design_key="DES-4",
        name="Valid Architecture Design",
        revision="A",
        requirements={},
        architecture={"lna": {"component_id": component_id}},
    )
    assert row["architecture"] == {"lna": {"component_id": component_id}}


def test_create_design_rejects_dangling_component_id(db_conn):
    with pytest.raises(DanglingComponentReferenceError) as exc_info:
        create_design(
            db_conn,
            design_key="DES-5",
            name="Dangling Ref Design",
            revision="A",
            requirements={},
            architecture={"lna": {"component_id": 999_999}},
        )
    offending = exc_info.value.offending
    assert offending == [{"block": "lna", "component_id": 999_999}]

    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM designs WHERE design_key = %s", ("DES-5",))
        (count,) = cur.fetchone()
    assert count == 0


def test_create_design_rejects_dangling_reference_without_writing_verification_items(db_conn):
    with pytest.raises(DanglingComponentReferenceError):
        create_design(
            db_conn,
            design_key="DES-6",
            name="Dangling Ref With Reqs",
            revision="A",
            requirements=_requirements("REQ-1"),
            architecture={"lna": {"component_id": 999_998}},
        )

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM verification_items vi "
            "JOIN designs d ON d.id = vi.design_id WHERE d.design_key = %s",
            ("DES-6",),
        )
        (count,) = cur.fetchone()
    assert count == 0


def test_create_design_reports_multiple_offending_blocks(db_conn):
    with pytest.raises(DanglingComponentReferenceError) as exc_info:
        create_design(
            db_conn,
            design_key="DES-7",
            name="Multiple Dangling Refs",
            revision="A",
            requirements={},
            architecture={
                "lna": {"component_id": 111_111},
                "mixer": {"component_id": 222_222},
            },
        )
    offending_blocks = {o["block"] for o in exc_info.value.offending}
    assert offending_blocks == {"lna", "mixer"}


def test_create_design_rejects_malformed_requirements_and_writes_nothing(db_conn):
    with pytest.raises(InvalidRequirementsError):
        create_design(
            db_conn,
            design_key="DES-8",
            name="Bad Requirements Design",
            revision="A",
            requirements={"REQ-1": "not a dict"},
            architecture={},
        )

    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM designs WHERE design_key = %s", ("DES-8",))
        (count,) = cur.fetchone()
    assert count == 0


# --- record_decision -----------------------------------------------------


def test_record_decision_writes_row_with_pending_approval_status(db_conn):
    design_id = _make_design(db_conn, design_key="DES-DEC-1")
    row = record_decision(
        db_conn,
        design_id=design_id,
        record_key="DES-DEC-1-topology",
        decision="Used a pi-network instead of an L-network.",
        alternatives=["L-network"],
        rationale="Pi-network gives an extra degree of freedom for Q.",
        evidence=[],
    )
    assert row["design_id"] == design_id
    assert row["record_key"] == "DES-DEC-1-topology"
    assert row["decision"] == "Used a pi-network instead of an L-network."
    assert row["approval_required"] is True
    assert row["approval_status"] == "PENDING"


def test_record_decision_round_trips_alternatives_and_evidence_as_jsonb(db_conn):
    design_id = _make_design(db_conn, design_key="DES-DEC-2")
    alternatives = [
        {"option": "L-network", "rejected_because": "insufficient Q control"},
        {"option": "T-network", "rejected_because": "extra component count"},
    ]
    evidence = [
        {"type": "calculation", "reference": "cascade_gain run 2026-08-01"},
        {"type": "measurement", "reference": "VNA sweep #42"},
    ]
    row = record_decision(
        db_conn,
        design_id=design_id,
        record_key="DES-DEC-2-topology",
        decision="Used a pi-network instead of an L-network.",
        alternatives=alternatives,
        rationale="Pi-network gives an extra degree of freedom for Q.",
        evidence=evidence,
    )
    assert row["alternatives"] == alternatives
    assert row["evidence"] == evidence


def test_record_decision_rejects_record_key_collision_and_points_at_existing_row(db_conn):
    design_id = _make_design(db_conn, design_key="DES-DEC-3")
    first = record_decision(
        db_conn,
        design_id=design_id,
        record_key="DES-DEC-3-topology",
        decision="Used a pi-network instead of an L-network.",
        alternatives=[],
        rationale="Pi-network gives an extra degree of freedom for Q.",
        evidence=[],
    )

    with pytest.raises(RecordKeyCollisionError) as exc_info:
        record_decision(
            db_conn,
            design_id=design_id,
            record_key="DES-DEC-3-topology",
            decision="Used an L-network instead, on reconsideration.",
            alternatives=[],
            rationale="Changed our minds.",
            evidence=[],
        )
    assert exc_info.value.record_key == "DES-DEC-3-topology"
    assert exc_info.value.existing["id"] == first["id"]

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM decision_records WHERE record_key = %s",
            ("DES-DEC-3-topology",),
        )
        (count,) = cur.fetchone()
    assert count == 1
