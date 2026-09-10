import os
import uuid

import psycopg
import pytest
from dotenv import load_dotenv

from designs.service import (
    create_design,
    read_design,
    record_decision,
    record_engineering_result,
    verify_requirement,
)

load_dotenv()


def _unique(base: str) -> str:
    """A design_key/record_key unique to this call, not a bare literal --
    every write in this file commits a real row to the same shared dev
    database interactive use also points at (`ingest_document`/
    `create_design` commit their own connection, so nothing here rolls
    back). A hardcoded literal collides with a leftover row from an
    interrupted run, or with another concurrent run against that same
    instance -- the xUnit Test Patterns "Unique Data" fixture, not a fresh
    literal per test."""
    return f"{base}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def cleanup_designs():
    """Tracks design ids created by `create_design` (which commits its own
    connection) and deletes them afterward -- unlike `designs/db.py`'s
    tests, this can't rely on a rolled-back transaction for isolation.
    `verification_items` rows cascade-delete with their design."""
    ids: list[int] = []
    yield ids
    if not ids:
        return
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM designs WHERE id = ANY(%s)", (ids,))
    finally:
        conn.close()


def test_create_design_returns_created_status_and_design_id(cleanup_designs):
    design_key = _unique("SVC-DES-1")
    result = create_design(
        design_key=design_key,
        name="Service Layer Design",
        revision="A",
        requirements={},
        architecture={},
    )
    cleanup_designs.append(result["design_id"])

    assert result["status"] == "created"
    assert result["design_key"] == design_key
    assert result["design_status"] == "DRAFT"


def test_create_design_with_reused_design_key_and_revision_returns_structured_error(
    cleanup_designs,
):
    first = create_design(
        design_key="SVC-DES-COLLIDE-1",
        name="First Attempt",
        revision="A",
        requirements={},
        architecture={},
    )
    cleanup_designs.append(first["design_id"])

    result = create_design(
        design_key="SVC-DES-COLLIDE-1",
        name="Second Attempt, Same Key And Revision",
        revision="A",
        requirements={},
        architecture={},
    )

    assert result["status"] == "design_key_revision_collision"
    assert result["existing_design_id"] == first["design_id"]
    assert "SVC-DES-COLLIDE-1" in result["message"]
    assert "A" in result["message"]


def test_create_design_with_dangling_component_id_returns_structured_error(cleanup_designs):
    design_key = _unique("SVC-DES-2")
    result = create_design(
        design_key=design_key,
        name="Dangling Ref via Service",
        revision="A",
        requirements={},
        architecture={"lna": {"component_id": 987_654}},
    )

    assert result["status"] == "dangling_component_reference"
    assert result["offending"] == [{"block": "lna", "component_id": 987_654}]

    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM designs WHERE design_key = %s", (design_key,))
            (count,) = cur.fetchone()
    finally:
        conn.close()
    assert count == 0


def _make_design(cleanup_designs, design_key):
    result = create_design(
        design_key=_unique(design_key),
        name="Decision Host Design",
        revision="A",
        requirements={},
        architecture={},
    )
    cleanup_designs.append(result["design_id"])
    return result["design_id"]


def test_record_decision_returns_recorded_status_and_pending_approval(cleanup_designs):
    design_id = _make_design(cleanup_designs, "SVC-DES-DEC-1")
    record_key = _unique("SVC-DES-DEC-1-topology")
    result = record_decision(
        design_id=design_id,
        record_key=record_key,
        decision="Used a pi-network instead of an L-network.",
        alternatives=["L-network"],
        rationale="Pi-network gives an extra degree of freedom for Q.",
        evidence=[],
    )

    assert result["status"] == "recorded"
    assert result["record_key"] == record_key
    assert result["approval_status"] == "PENDING"
    assert "decision_id" in result


def test_record_decision_threads_design_family_through_to_the_stored_row(cleanup_designs):
    """Issue #167: designs.service.record_decision (the record_decision
    tool wrapper's backing function, mcp_server/server.py and agent/main.py)
    must pass design_family through to designs.db.record_decision, not
    just accept it and drop it -- read_design is the durable proof, since
    record_decision's own structured return value is a narrow
    status/decision_id/design_id/record_key/approval_status projection
    that never echoed decision/rationale/alternatives/evidence either."""
    design_id = _make_design(cleanup_designs, "SVC-DES-DEC-FAMILY")
    record_decision(
        design_id=design_id,
        record_key=_unique("SVC-DES-DEC-FAMILY-architecture"),
        decision="rectangular microstrip patch on FR4",
        alternatives=[],
        rationale="meets band/gain target with a simple, low-cost fabrication",
        evidence=[],
        design_family="patch_antenna",
    )

    stored = read_design(design_id)
    (dr,) = stored["decision_records"]
    assert dr["design_family"] == "patch_antenna"


def test_record_decision_with_reused_record_key_returns_structured_error(cleanup_designs):
    design_id = _make_design(cleanup_designs, "SVC-DES-DEC-2")
    record_key = _unique("SVC-DES-DEC-2-topology")
    first = record_decision(
        design_id=design_id,
        record_key=record_key,
        decision="Used a pi-network instead of an L-network.",
        alternatives=[],
        rationale="Pi-network gives an extra degree of freedom for Q.",
        evidence=[],
    )

    result = record_decision(
        design_id=design_id,
        record_key=record_key,
        decision="Used an L-network instead, on reconsideration.",
        alternatives=[],
        rationale="Changed our minds.",
        evidence=[],
    )

    assert result["status"] == "record_key_collision"
    assert result["existing_decision_id"] == first["decision_id"]
    assert record_key in result["message"]


def test_record_engineering_result_returns_engineering_result_id(cleanup_designs):
    design = create_design(
        design_key=_unique("SVC-ER-1"),
        name="Engineering Result Service Fixture",
        revision="A",
        requirements={},
        architecture={},
    )
    cleanup_designs.append(design["design_id"])

    result = record_engineering_result(
        design_id=design["design_id"],
        tool_name="calculate_wavelength",
        value=0.1,
    )

    assert isinstance(result["engineering_result_id"], int)

    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT design_id, provenance, confidence FROM engineering_results WHERE id = %s",
                (result["engineering_result_id"],),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    assert row == (design["design_id"], "CALCULATED", None)


def test_create_design_with_malformed_requirements_returns_structured_error(cleanup_designs):
    design_key = _unique("SVC-DES-3")
    result = create_design(
        design_key=design_key,
        name="Bad Requirements via Service",
        revision="A",
        requirements={"REQ-1": "not a dict"},
        architecture={},
    )

    assert result["status"] == "invalid_requirements"
    assert "REQ-1" in result["message"]

    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM designs WHERE design_key = %s", (design_key,))
            (count,) = cur.fetchone()
    finally:
        conn.close()
    assert count == 0


def test_read_design_returns_not_found_for_nonexistent_id():
    result = read_design(999_999)
    assert result == {"status": "not_found", "design_id": 999_999}


def test_read_design_returns_full_payload_for_created_design(cleanup_designs):
    requirements = {"REQ-1": {"requirement": "Gain >= 20 dB."}}
    design_key = _unique("SVC-DES-READ-1")
    created = create_design(
        design_key=design_key,
        name="Service Read Design",
        revision="A",
        requirements=requirements,
        architecture={},
    )
    cleanup_designs.append(created["design_id"])

    result = read_design(created["design_id"])

    assert result["design_id"] == created["design_id"]
    assert result["design_key"] == design_key
    assert result["name"] == "Service Read Design"
    assert result["revision"] == "A"
    assert result["status"] == "DRAFT"
    assert result["requirements"] == requirements
    assert result["architecture"] == {}
    assert result["engineering_results"] == []
    assert result["decision_records"] == []
    assert len(result["verification_items"]) == 1
    assert result["verification_items"][0]["requirement_id"] == "REQ-1"


def test_verify_requirement_returns_verified_status_and_updated_fields(cleanup_designs):
    design = create_design(
        design_key=_unique("SVC-DES-VERIFY-1"),
        name="Verify via Service",
        revision="A",
        requirements={"REQ-1": {"requirement": "Gain >= 20 dB."}},
        architecture={},
    )
    cleanup_designs.append(design["design_id"])

    result = verify_requirement(
        design_id=design["design_id"],
        requirement_id="REQ-1",
        method="Bench measurement with VNA",
        status="PASS",
        expected={"gain_db": 20.0},
        actual={"gain_db": 20.3},
        evidence_uri="s3://evidence/req-1.csv",
        notes="Measured at room temperature.",
    )

    assert result["status"] == "verified"
    assert result["design_id"] == design["design_id"]
    assert result["requirement_id"] == "REQ-1"
    assert result["verification_status"] == "PASS"
    assert result["method"] == "Bench measurement with VNA"
    assert result["expected"] == {"gain_db": 20.0}
    assert result["actual"] == {"gain_db": 20.3}
    assert result["evidence_uri"] == "s3://evidence/req-1.csv"
    assert result["notes"] == "Measured at room temperature."


def test_verify_requirement_with_unknown_requirement_id_returns_structured_error(
    cleanup_designs,
):
    design = create_design(
        design_key=_unique("SVC-DES-VERIFY-2"),
        name="Verify Unknown via Service",
        revision="A",
        requirements={"REQ-1": {"requirement": "Gain >= 20 dB."}},
        architecture={},
    )
    cleanup_designs.append(design["design_id"])

    result = verify_requirement(
        design_id=design["design_id"],
        requirement_id="REQ-DOES-NOT-EXIST",
        method="Bench measurement",
        status="PASS",
    )

    assert result["status"] == "unknown_requirement"
    assert "REQ-DOES-NOT-EXIST" in result["message"]


def test_verify_requirement_with_invalid_status_returns_structured_error(cleanup_designs):
    design = create_design(
        design_key=_unique("SVC-DES-VERIFY-3"),
        name="Verify Bad Status via Service",
        revision="A",
        requirements={"REQ-1": {"requirement": "Gain >= 20 dB."}},
        architecture={},
    )
    cleanup_designs.append(design["design_id"])

    result = verify_requirement(
        design_id=design["design_id"],
        requirement_id="REQ-1",
        method="Bench measurement",
        status="SORT-OF-PASSED",
    )

    assert result["status"] == "invalid_status"
    assert "SORT-OF-PASSED" in result["message"]
