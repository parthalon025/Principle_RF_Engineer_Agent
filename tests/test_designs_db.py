import pytest

from designs.db import (
    DanglingComponentReferenceError,
    UnknownVerificationItemError,
    create_design,
    verify_requirement,
)
from designs.validation import InvalidRequirementsError, InvalidVerificationStatusError
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


def test_verify_requirement_updates_the_single_row(db_conn):
    design = create_design(
        db_conn,
        design_key="DES-VERIFY-1",
        name="Verify Design",
        revision="A",
        requirements=_requirements("REQ-1", "REQ-2"),
        architecture={},
    )

    row = verify_requirement(
        db_conn,
        design_id=design["id"],
        requirement_id="REQ-1",
        method="Bench measurement with VNA",
        status="PASS",
        expected={"gain_db": 20.0},
        actual={"gain_db": 20.3},
        evidence_uri="s3://evidence/req-1.csv",
        notes="Measured at room temperature.",
    )

    assert row["design_id"] == design["id"]
    assert row["requirement_id"] == "REQ-1"
    assert row["method"] == "Bench measurement with VNA"
    assert row["status"] == "PASS"
    assert row["expected"] == {"gain_db": 20.0}
    assert row["actual"] == {"gain_db": 20.3}
    assert row["evidence_uri"] == "s3://evidence/req-1.csv"
    assert row["notes"] == "Measured at room temperature."

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT status FROM verification_items WHERE design_id = %s AND requirement_id = %s",
            (design["id"], "REQ-2"),
        )
        (other_status,) = cur.fetchone()
    assert other_status == "NOT VERIFIED"


def test_verify_requirement_rejects_unknown_requirement_id_without_creating_a_row(db_conn):
    design = create_design(
        db_conn,
        design_key="DES-VERIFY-2",
        name="Verify Unknown Design",
        revision="A",
        requirements=_requirements("REQ-1"),
        architecture={},
    )

    with pytest.raises(UnknownVerificationItemError) as exc_info:
        verify_requirement(
            db_conn,
            design_id=design["id"],
            requirement_id="REQ-DOES-NOT-EXIST",
            method="Bench measurement",
            status="PASS",
        )
    assert exc_info.value.design_id == design["id"]
    assert exc_info.value.requirement_id == "REQ-DOES-NOT-EXIST"

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM verification_items WHERE design_id = %s",
            (design["id"],),
        )
        (count,) = cur.fetchone()
    assert count == 1


def test_verify_requirement_rejects_unknown_design_id_without_creating_a_row(db_conn):
    with pytest.raises(UnknownVerificationItemError) as exc_info:
        verify_requirement(
            db_conn,
            design_id=999_999_999,
            requirement_id="REQ-1",
            method="Bench measurement",
            status="PASS",
        )
    assert exc_info.value.design_id == 999_999_999
    assert exc_info.value.requirement_id == "REQ-1"

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM verification_items WHERE design_id = %s",
            (999_999_999,),
        )
        (count,) = cur.fetchone()
    assert count == 0


@pytest.mark.parametrize("status", ["NOT VERIFIED", "PASS", "FAIL", "MARGINAL"])
def test_verify_requirement_accepts_each_status_value(db_conn, status):
    design = create_design(
        db_conn,
        design_key=f"DES-VERIFY-STATUS-{status.replace(' ', '_')}",
        name="Verify Status Design",
        revision="A",
        requirements=_requirements("REQ-1"),
        architecture={},
    )

    row = verify_requirement(
        db_conn,
        design_id=design["id"],
        requirement_id="REQ-1",
        method="Bench measurement",
        status=status,
    )

    assert row["status"] == status


def test_verify_requirement_rejects_invalid_status_without_writing(db_conn):
    design = create_design(
        db_conn,
        design_key="DES-VERIFY-BAD-STATUS",
        name="Verify Bad Status Design",
        revision="A",
        requirements=_requirements("REQ-1"),
        architecture={},
    )

    with pytest.raises(InvalidVerificationStatusError):
        verify_requirement(
            db_conn,
            design_id=design["id"],
            requirement_id="REQ-1",
            method="Bench measurement",
            status="SORT-OF-PASSED",
        )

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT status FROM verification_items WHERE design_id = %s AND requirement_id = %s",
            (design["id"], "REQ-1"),
        )
        (status,) = cur.fetchone()
    assert status == "NOT VERIFIED"
