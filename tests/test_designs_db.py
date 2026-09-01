import pytest
from psycopg.types.json import Json

from designs.db import DanglingComponentReferenceError, create_design, read_design
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


def test_read_design_returns_none_for_nonexistent_id(db_conn):
    assert read_design(db_conn, 999_999) is None


def test_read_design_returns_design_fields_and_empty_related_lists(db_conn):
    requirements = _requirements("REQ-1", "REQ-2")
    created = create_design(
        db_conn,
        design_key="DES-READ-1",
        name="Read Me Design",
        revision="B",
        requirements=requirements,
        architecture={},
    )

    result = read_design(db_conn, created["id"])

    assert result["design_id"] == created["id"]
    assert result["design_key"] == "DES-READ-1"
    assert result["name"] == "Read Me Design"
    assert result["revision"] == "B"
    assert result["status"] == "DRAFT"
    assert result["requirements"] == requirements
    assert result["architecture"] == {}
    assert result["engineering_results"] == []
    assert result["decision_records"] == []
    assert len(result["verification_items"]) == 2
    assert {vi["requirement_id"] for vi in result["verification_items"]} == {"REQ-1", "REQ-2"}


def test_read_design_resolves_component_id_to_manufacturer_and_part_number(db_conn):
    component_id = _make_component(db_conn, part_number="ACM-AMP-READ")
    created = create_design(
        db_conn,
        design_key="DES-READ-2",
        name="Read Architecture Design",
        revision="A",
        requirements={},
        architecture={"lna": {"component_id": component_id, "gain_db": 20}},
    )

    result = read_design(db_conn, created["id"])

    assert result["architecture"] == {
        "lna": {
            "component_id": component_id,
            "gain_db": 20,
            "manufacturer": "Acme RF",
            "part_number": "ACM-AMP-READ",
        }
    }


def test_read_design_includes_engineering_results_and_decision_records(db_conn):
    """#19/#20's writer functions (record_engineering_result/record_decision)
    aren't implemented in this worktree yet -- rows are inserted directly to
    exercise read_design's aggregation of tables it doesn't own writing to."""
    created = create_design(
        db_conn,
        design_key="DES-READ-3",
        name="Read Results And Decisions Design",
        revision="A",
        requirements={},
        architecture={},
    )
    design_id = created["id"]

    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO engineering_results "
            "(design_id, result_type, name, value, provenance) "
            "VALUES (%s, %s, %s, %s, %s)",
            (design_id, "gain", "Cascade Gain", Json({"value": 12.0, "unit": "dB"}), "CALCULATED"),
        )
        cur.execute(
            "INSERT INTO decision_records "
            "(design_id, record_key, decision, rationale, approval_status) "
            "VALUES (%s, %s, %s, %s, %s)",
            (design_id, "DEC-1", "Use Acme LNA", "Best noise figure available.", "APPROVED"),
        )

    result = read_design(db_conn, design_id)

    assert len(result["engineering_results"]) == 1
    er = result["engineering_results"][0]
    assert er["result_type"] == "gain"
    assert er["name"] == "Cascade Gain"
    assert er["value"] == {"value": 12.0, "unit": "dB"}
    assert er["provenance"] == "CALCULATED"

    assert len(result["decision_records"]) == 1
    dr = result["decision_records"][0]
    assert dr["record_key"] == "DEC-1"
    assert dr["decision"] == "Use Acme LNA"
    assert dr["approval_status"] == "APPROVED"
