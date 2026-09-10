import pytest
from psycopg.types.json import Json

from designs.db import (
    DanglingComponentReferenceError,
    DesignKeyRevisionCollisionError,
    RecordKeyCollisionError,
    UnknownDesignError,
    UnknownVerificationItemError,
    create_design,
    read_design,
    read_engineering_results_for_scoring,
    record_decision,
    record_engineering_result,
    update_design_status,
    verify_requirement,
)
from designs.lifecycle import IllegalStatusTransitionError
from designs.release_approval import (
    DesignReleaseApprovalError,
    release_fingerprint_fields,
    request_design_release_approval,
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


def test_create_design_rejects_design_key_revision_collision_and_points_at_existing_row(db_conn):
    first = create_design(
        db_conn,
        design_key="DES-COLLIDE-1",
        name="First Attempt",
        revision="A",
        requirements={},
        architecture={},
    )

    with pytest.raises(DesignKeyRevisionCollisionError) as exc_info:
        create_design(
            db_conn,
            design_key="DES-COLLIDE-1",
            name="Second Attempt, Same Key And Revision",
            revision="A",
            requirements={},
            architecture={},
        )
    assert exc_info.value.design_key == "DES-COLLIDE-1"
    assert exc_info.value.revision == "A"
    assert exc_info.value.existing["id"] == first["id"]

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM designs WHERE design_key = %s AND revision = %s",
            ("DES-COLLIDE-1", "A"),
        )
        (count,) = cur.fetchone()
    assert count == 1


def test_create_design_allows_a_different_revision_under_the_same_design_key(db_conn):
    first = create_design(
        db_conn,
        design_key="DES-COLLIDE-2",
        name="Revision A",
        revision="A",
        requirements={},
        architecture={},
    )
    second = create_design(
        db_conn,
        design_key="DES-COLLIDE-2",
        name="Revision B",
        revision="B",
        requirements={},
        architecture={},
    )

    assert first["id"] != second["id"]
    assert first["design_key"] == second["design_key"] == "DES-COLLIDE-2"
    assert {first["revision"], second["revision"]} == {"A", "B"}


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
    for requirement_id, requirement_text, status in items:
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


def _make_design(db_conn, design_key="ER-DES"):
    row = create_design(
        db_conn,
        design_key=design_key,
        name="Engineering Result Fixture Design",
        revision="A",
        requirements={},
        architecture={},
    )
    return row["id"]


def test_record_engineering_result_writes_one_row_with_expected_fields(db_conn):
    design_id = _make_design(db_conn, design_key="ER-DES-1")
    row = record_engineering_result(
        db_conn,
        design_id=design_id,
        tool_name="calculate_vswr",
        value=2.0,
    )

    assert row["design_id"] == design_id
    assert row["result_type"] == "calculate_vswr"
    assert row["name"] == "calculate_vswr"
    assert row["value"] == 2.0
    assert row["provenance"] == "CALCULATED"
    assert row["tool_name"] == "calculate_vswr"
    assert row["tool_version"] is None
    assert row["confidence"] is None

    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM engineering_results WHERE design_id = %s", (design_id,))
        (count,) = cur.fetchone()
    assert count == 1


def test_record_engineering_result_stores_dict_value_as_jsonb(db_conn):
    design_id = _make_design(db_conn, design_key="ER-DES-2")
    payload = {"noise_factor": 1.5, "noise_figure_db": 1.76, "provenance": "CALCULATED"}
    row = record_engineering_result(
        db_conn,
        design_id=design_id,
        tool_name="calculate_noise_figure",
        value=payload,
    )
    assert row["value"] == payload
    assert row["provenance"] == "CALCULATED"


# ---------------------------------------------------------------------------
# read_engineering_results_for_scoring (issue #87's cross-run-learning
# follow-up to #95): a plain, read-only SELECT -- orchestration/solver.py's
# run_candidate_search(design_id=...) is the one caller, using it to seed a
# new search's plateau-window baseline from a design's own past results.
# Matches this file's existing db_conn convention: one rolled-back
# transaction per test does both the write (record_engineering_result) and
# the read under test.
# ---------------------------------------------------------------------------


def test_read_engineering_results_for_scoring_returns_empty_lists_for_no_rows(db_conn):
    design_id = _make_design(db_conn, design_key="ER-SCORE-1")
    result = read_engineering_results_for_scoring(
        db_conn, design_id, ["patch_resonant_frequency_hz", "run_nec2_simulation"]
    )
    assert result == {"patch_resonant_frequency_hz": [], "run_nec2_simulation": []}


def test_read_engineering_results_for_scoring_returns_rows_in_recording_order(db_conn):
    design_id = _make_design(db_conn, design_key="ER-SCORE-2")
    for freq_hz in (2.40e9, 2.44e9, 2.46e9):
        record_engineering_result(
            db_conn,
            design_id=design_id,
            tool_name="patch_resonant_frequency_hz",
            value={"resonant_frequency_hz": freq_hz},
            # patch_resonant_frequency_hz is a design-loop-internal function
            # name, not one of designs.provenance's ~65 registered agent/MCP
            # tool names -- explicit provenance is the same escape hatch
            # orchestration/tooling.py's own flush uses for it (see
            # record_engineering_result's own docstring).
            provenance="CALCULATED",
        )

    result = read_engineering_results_for_scoring(
        db_conn, design_id, ["patch_resonant_frequency_hz"]
    )

    rows = result["patch_resonant_frequency_hz"]
    assert [row["value"]["resonant_frequency_hz"] for row in rows] == [2.40e9, 2.44e9, 2.46e9]
    assert all("id" in row and "created_at" in row for row in rows)


def test_read_engineering_results_for_scoring_filters_by_design_id(db_conn):
    design_a = _make_design(db_conn, design_key="ER-SCORE-3A")
    design_b = _make_design(db_conn, design_key="ER-SCORE-3B")
    record_engineering_result(
        db_conn,
        design_id=design_a,
        tool_name="patch_resonant_frequency_hz",
        value={"resonant_frequency_hz": 2.40e9},
        provenance="CALCULATED",
    )
    record_engineering_result(
        db_conn,
        design_id=design_b,
        tool_name="patch_resonant_frequency_hz",
        value={"resonant_frequency_hz": 9.90e9},
        provenance="CALCULATED",
    )

    result = read_engineering_results_for_scoring(
        db_conn, design_a, ["patch_resonant_frequency_hz"]
    )

    assert [
        row["value"]["resonant_frequency_hz"] for row in result["patch_resonant_frequency_hz"]
    ] == [2.40e9]


def test_read_engineering_results_for_scoring_filters_by_tool_name(db_conn):
    design_id = _make_design(db_conn, design_key="ER-SCORE-4")
    record_engineering_result(
        db_conn,
        design_id=design_id,
        tool_name="patch_resonant_frequency_hz",
        value={"resonant_frequency_hz": 2.40e9},
        provenance="CALCULATED",
    )
    record_engineering_result(
        db_conn,
        design_id=design_id,
        tool_name="run_nec2_simulation",
        value={"gain_dbi": 6.0},
        provenance="SIMULATED",
    )

    result = read_engineering_results_for_scoring(
        db_conn, design_id, ["patch_resonant_frequency_hz"]
    )

    assert list(result.keys()) == ["patch_resonant_frequency_hz"]
    assert len(result["patch_resonant_frequency_hz"]) == 1


def test_read_engineering_results_for_scoring_with_no_tool_names_returns_empty_dict(db_conn):
    design_id = _make_design(db_conn, design_key="ER-SCORE-5")
    assert read_engineering_results_for_scoring(db_conn, design_id, []) == {}


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


# --- read_design -----------------------------------------------------


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
    """#19's writer function (record_engineering_result) isn't implemented in
    this worktree yet -- its row is inserted directly to exercise
    read_design's aggregation of a table it doesn't own writing to;
    decision_records is exercised via the real record_decision (#20)."""
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
    record_decision(
        db_conn,
        design_id=design_id,
        record_key="DEC-1",
        decision="Use Acme LNA",
        alternatives=[],
        rationale="Best noise figure available.",
        evidence=[],
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
    assert dr["approval_status"] == "PENDING"


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
    assert row["design_family"] is None  # not given -- most decisions aren't about one


def test_record_decision_persists_and_round_trips_design_family(db_conn):
    """Issue #167: design_family (CONTEXT.md's "Design family", docs/adr/0018)
    is optional/nullable on record_decision, but when a caller states one
    (orchestration/tooling.py's ADR-0011 flush, for an ARCHITECTURE or
    REDESIGN_DECISION design-loop decision) it must actually land in the
    decision_records row and be readable back out via read_design -- not
    silently dropped, which is exactly the bug this issue closes."""
    design_id = _make_design(db_conn, design_key="DES-DEC-FAMILY")
    row = record_decision(
        db_conn,
        design_id=design_id,
        record_key="DES-DEC-FAMILY-architecture",
        decision="rectangular microstrip patch on FR4",
        alternatives=[],
        rationale="meets band/gain target with a simple, low-cost fabrication",
        evidence=[],
        design_family="patch_antenna",
    )
    assert row["design_family"] == "patch_antenna"

    result = read_design(db_conn, design_id)
    (dr,) = result["decision_records"]
    assert dr["design_family"] == "patch_antenna"


def test_record_decision_defaults_considered_and_dropped_to_empty_list(db_conn):
    """Issue #322 (ADR-0025's Considered-and-dropped ledger). A caller that
    never states one (every non-design-loop decision, and today most
    design-loop ones too) gets `[]`, matching this column's schema
    default -- never NULL, so a reader can always iterate it."""
    design_id = _make_design(db_conn, design_key="DES-DEC-LEDGER-DEFAULT")
    row = record_decision(
        db_conn,
        design_id=design_id,
        record_key="DES-DEC-LEDGER-DEFAULT-topology",
        decision="Used a pi-network instead of an L-network.",
        alternatives=[],
        rationale="Pi-network gives an extra degree of freedom for Q.",
        evidence=[],
    )
    assert row["considered_and_dropped"] == []


def test_record_decision_persists_and_round_trips_considered_and_dropped(db_conn):
    """Issue #322 (ADR-0025's Considered-and-dropped ledger; CONTEXT.md's
    entry of the same name). A design-loop ARCHITECTURE/REDESIGN_DECISION
    flush (orchestration/tooling.py) passes a real ledger; it must land in
    the row and read back out via read_design -- this function stores it
    verbatim, the reason_kind narrowing (issue #322) is enforced upstream by
    orchestration.design_loop before a decision ever reaches this call."""
    design_id = _make_design(db_conn, design_key="DES-DEC-LEDGER")
    ledger = [
        {
            "family": "reflection_phase_surface",
            "verdict": "dropped",
            "reason": "host curvature exceeds this family's angle-stable element validity box",
            "reason_kind": "capability-verdict",
            "requirement_id": "R1",
            "validity_box_property": "curvature",
            "theta_max_deg": 45.0,
        },
        {
            "family": "patch_antenna",
            "verdict": "kept",
            "reason": "meets band/gain target with a simple, low-cost fabrication",
            "reason_kind": "engineering-judgment",
        },
    ]
    row = record_decision(
        db_conn,
        design_id=design_id,
        record_key="DES-DEC-LEDGER-architecture",
        decision="rectangular microstrip patch on FR4",
        alternatives=[],
        rationale="meets band/gain target with a simple, low-cost fabrication",
        evidence=[],
        design_family="patch_antenna",
        considered_and_dropped=ledger,
    )
    assert row["considered_and_dropped"] == ledger

    result = read_design(db_conn, design_id)
    (dr,) = result["decision_records"]
    assert dr["considered_and_dropped"] == ledger


def test_record_decision_defaults_capability_warnings_to_empty_list(db_conn):
    """Issue #324 (ADR-0025's 2026-09-09 correction; CONTEXT.md's
    "Capability warning") -- a wholly separate column from
    considered_and_dropped above. A caller that never states one gets `[]`,
    matching this column's schema default -- never NULL, so a reader can
    always iterate it."""
    design_id = _make_design(db_conn, design_key="DES-DEC-CAPWARN-DEFAULT")
    row = record_decision(
        db_conn,
        design_id=design_id,
        record_key="DES-DEC-CAPWARN-DEFAULT-topology",
        decision="Used a pi-network instead of an L-network.",
        alternatives=[],
        rationale="Pi-network gives an extra degree of freedom for Q.",
        evidence=[],
    )
    assert row["capability_warnings"] == []


def test_record_decision_persists_and_round_trips_capability_warnings(db_conn):
    """Issue #324. A design-loop ARCHITECTURE/REDESIGN_DECISION flush
    (orchestration/tooling.py) passes a real capability_warnings list; it
    must land in the row and read back out via read_design, independently
    of whatever considered_and_dropped carries on the same row -- this
    function stores it verbatim, the shape check (issue #324) is enforced
    upstream by orchestration.design_loop before a decision ever reaches
    this call."""
    design_id = _make_design(db_conn, design_key="DES-DEC-CAPWARN")
    warnings = [
        {
            "family": "patch_antenna",
            "capability_kind": "fabrication",
            "capability_property": "min_feature_size_mm",
            "value": 0.2,
            "comparator": "AT_MOST",
            "unit": "mm",
            "reason": "needs 0.2 mm features; loaded printer achieves 0.5 mm",
        }
    ]
    row = record_decision(
        db_conn,
        design_id=design_id,
        record_key="DES-DEC-CAPWARN-architecture",
        decision="checkerboard AMC absorber",
        alternatives=[],
        rationale="best absorption for the stated band",
        evidence=[],
        design_family="patch_antenna",
        capability_warnings=warnings,
    )
    assert row["capability_warnings"] == warnings
    # considered_and_dropped is untouched -- issue #324 acceptance criterion
    # 3: the two mechanisms never affect each other.
    assert row["considered_and_dropped"] == []

    result = read_design(db_conn, design_id)
    (dr,) = result["decision_records"]
    assert dr["capability_warnings"] == warnings
    assert dr["considered_and_dropped"] == []


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


# --- verify_requirement -----------------------------------------------------


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


# --- design-status transitions (issue #145) -------------------------------
#
# The ordering rules and the release gate are unit-tested without a database
# in tests/test_design_lifecycle.py and tests/test_design_release_approval.py.
# These check that the write path actually enforces them, and that a refused
# transition leaves the stored row untouched.


def _walk(db_conn, design_id, *statuses):
    for status in statuses:
        update_design_status(db_conn, design_id=design_id, status=status)


def test_update_design_status_walks_the_lifecycle(db_conn):
    design_id = _make_design(db_conn, design_key="DES-LIFECYCLE")
    _walk(db_conn, design_id, "ANALYSIS", "SIMULATION", "OPTIMIZATION", "VERIFICATION")
    row = update_design_status(db_conn, design_id=design_id, status="PASS")
    assert row["status"] == "PASS"


def test_update_design_status_refuses_a_skipped_stage_and_stores_nothing(db_conn):
    design_id = _make_design(db_conn, design_key="DES-SKIP")
    with pytest.raises(IllegalStatusTransitionError):
        update_design_status(db_conn, design_id=design_id, status="VERIFICATION")
    assert read_design(db_conn, design_id)["status"] == "DRAFT"


def test_update_design_status_refuses_draft_straight_to_released(db_conn):
    design_id = _make_design(db_conn, design_key="DES-JUMP")
    with pytest.raises(IllegalStatusTransitionError):
        update_design_status(db_conn, design_id=design_id, status="RELEASED")
    assert read_design(db_conn, design_id)["status"] == "DRAFT"


def test_reaching_pass_still_cannot_be_released_without_an_approval(db_conn):
    """The gate ADR-0007 requires: a design that legitimately passed
    verification still cannot be released by this write path alone."""
    design_id = _make_design(db_conn, design_key="DES-NOAPPROVAL")
    _walk(db_conn, design_id, "ANALYSIS", "SIMULATION", "OPTIMIZATION", "VERIFICATION", "PASS")
    with pytest.raises(DesignReleaseApprovalError):
        update_design_status(db_conn, design_id=design_id, status="RELEASED")
    assert read_design(db_conn, design_id)["status"] == "PASS"


def test_a_valid_release_receipt_releases_the_design(db_conn):
    design_id = _make_design(db_conn, design_key="DES-RELEASE")
    _walk(db_conn, design_id, "ANALYSIS", "SIMULATION", "OPTIMIZATION", "VERIFICATION", "PASS")
    approval = request_design_release_approval(
        release_fingerprint_fields(design_id=design_id, design_key="DES-RELEASE", revision="A"),
        approved_by="a.engineer",
        approval_callback=lambda _: True,
    )
    row = update_design_status(db_conn, design_id=design_id, status="RELEASED", approval=approval)
    assert row["status"] == "RELEASED"


def test_a_release_receipt_for_another_design_is_refused(db_conn):
    """The receipt is bound to the design it approved, so it cannot be
    replayed against a different one that happens to be sitting at PASS."""
    approved_id = _make_design(db_conn, design_key="DES-APPROVED")
    other_id = _make_design(db_conn, design_key="DES-OTHER")
    for design_id in (approved_id, other_id):
        _walk(
            db_conn,
            design_id,
            "ANALYSIS",
            "SIMULATION",
            "OPTIMIZATION",
            "VERIFICATION",
            "PASS",
        )
    approval = request_design_release_approval(
        release_fingerprint_fields(design_id=approved_id, design_key="DES-APPROVED", revision="A"),
        approved_by="a.engineer",
        approval_callback=lambda _: True,
    )
    with pytest.raises(DesignReleaseApprovalError):
        update_design_status(db_conn, design_id=other_id, status="RELEASED", approval=approval)
    assert read_design(db_conn, other_id)["status"] == "PASS"


def test_released_is_terminal_in_the_write_path(db_conn):
    design_id = _make_design(db_conn, design_key="DES-TERMINAL")
    _walk(db_conn, design_id, "ANALYSIS", "SIMULATION", "OPTIMIZATION", "VERIFICATION", "PASS")
    approval = request_design_release_approval(
        release_fingerprint_fields(design_id=design_id, design_key="DES-TERMINAL", revision="A"),
        approved_by="a.engineer",
        approval_callback=lambda _: True,
    )
    update_design_status(db_conn, design_id=design_id, status="RELEASED", approval=approval)
    with pytest.raises(IllegalStatusTransitionError):
        update_design_status(db_conn, design_id=design_id, status="ANALYSIS")
    assert read_design(db_conn, design_id)["status"] == "RELEASED"


def test_allow_nonsequential_permits_the_design_loops_boundary_flush(db_conn):
    """ADR-0011: the loop walks the stages in memory and persists once per
    iteration, so its DRAFT -> PASS write skips stages legitimately."""
    design_id = _make_design(db_conn, design_key="DES-LOOPFLUSH")
    row = update_design_status(
        db_conn, design_id=design_id, status="PASS", allow_nonsequential=True
    )
    assert row["status"] == "PASS"


def test_allow_nonsequential_never_opens_the_release_gate(db_conn):
    """The ordering relaxation is bookkeeping; releasing is safety. No caller
    may relax the latter, so RELEASED stays both ordered and gated."""
    design_id = _make_design(db_conn, design_key="DES-NOBYPASS")
    with pytest.raises(IllegalStatusTransitionError):
        update_design_status(
            db_conn, design_id=design_id, status="RELEASED", allow_nonsequential=True
        )
    assert read_design(db_conn, design_id)["status"] == "DRAFT"


def test_allow_nonsequential_cannot_reopen_a_released_design(db_conn):
    """A terminal status is terminal for every caller. The ordering escape
    hatch relaxes the order work moves in, not whether finished work can be
    reopened -- otherwise a loop flush could walk a RELEASED design back to
    ANALYSIS and contradict the terminality the lifecycle promises."""
    design_id = _make_design(db_conn, design_key="DES-REOPEN")
    _walk(db_conn, design_id, "ANALYSIS", "SIMULATION", "OPTIMIZATION", "VERIFICATION", "PASS")
    approval = request_design_release_approval(
        release_fingerprint_fields(design_id=design_id, design_key="DES-REOPEN", revision="A"),
        approved_by="a.engineer",
        approval_callback=lambda _: True,
    )
    update_design_status(db_conn, design_id=design_id, status="RELEASED", approval=approval)
    with pytest.raises(IllegalStatusTransitionError):
        update_design_status(
            db_conn, design_id=design_id, status="ANALYSIS", allow_nonsequential=True
        )
    assert read_design(db_conn, design_id)["status"] == "RELEASED"


def test_an_unknown_status_is_still_rejected_before_the_row_is_read(db_conn):
    design_id = _make_design(db_conn, design_key="DES-BADSTATUS")
    with pytest.raises(ValueError, match="status must be one of"):
        update_design_status(db_conn, design_id=design_id, status="ACTIVE")
    assert read_design(db_conn, design_id)["status"] == "DRAFT"


def test_an_unknown_design_id_raises_rather_than_updating_nothing(db_conn):
    with pytest.raises(UnknownDesignError):
        update_design_status(db_conn, design_id=999_999, status="ANALYSIS")
