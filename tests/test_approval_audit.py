"""The durable, independent audit trail for approval-gate decisions (issue
#258 ticket 1; ADR-0028; ADR-0014).

`orchestration/approval.py` and `designs/release_approval.py` both mint a
cryptographically-signed receipt for exactly one human decision -- but both
say plainly, in their own module docstrings, that the signing key is
process-local and does NOT survive a restart. Once a process restarts, the
receipt itself is gone; nothing in this codebase can say afterwards who
approved (or refused) what, or when.

`orchestration/approval_audit.py` is the durable record that outlives that.
This ticket builds only the sink -- an append function and a read function --
and does not touch either approval gate itself (`orchestration/approval.py`
and `designs/release_approval.py` are unmodified this ticket; a later ticket
wires them to call into this module).

These tests hold three properties:

  1. What goes in comes back out exactly, in order, filterable by loop id.
  2. The module is STRUCTURALLY append-only -- no function anywhere in its
     public surface could update or delete a row, not merely "nobody calls
     one".
  3. A record survives the append connection being closed and a fresh one
     opened -- proof this is real, durable storage, not in-memory state
     dressed up to look like it (the whole reason this module exists,
     given the approval receipts' own keys do NOT survive a restart).
"""

from __future__ import annotations

import inspect
import os
import uuid

import psycopg
import pytest

from orchestration.approval_audit import (
    AUDIT_GATES,
    AUDIT_OUTCOMES,
    GATE_DESIGN_RELEASE,
    GATE_LOOP_STEP,
    OUTCOME_APPROVED,
    OUTCOME_REFUSED,
    InvalidAuditRecordError,
    append_audit_record,
    fetch_audit_records,
)

LOOP_FIELDS = {
    "loop_id": "loop-audit-test-1",
    "iteration": 1,
    "step": "architecture",
    "content": {"topology": "patch_array", "elements": 4},
}

RELEASE_FIELDS = {
    "design_id": 42,
    "design_key": "AUDIT-TEST-1",
    "revision": "2",
    "target": "RELEASED",
}


# --- appending and reading back --------------------------------------------


def test_append_and_read_back_one_record_exactly(db_conn):
    written = append_audit_record(
        db_conn,
        gate=GATE_LOOP_STEP,
        fingerprint_fields=LOOP_FIELDS,
        approved_by="a.engineer",
        outcome=OUTCOME_APPROVED,
    )

    assert written["gate"] == GATE_LOOP_STEP
    assert written["loop_id"] == "loop-audit-test-1"
    assert written["fingerprint_fields"] == LOOP_FIELDS
    assert written["approved_by"] == "a.engineer"
    assert written["outcome"] == OUTCOME_APPROVED
    assert written["decided_at"] is not None

    [record] = fetch_audit_records(db_conn, loop_id="loop-audit-test-1")
    assert record["id"] == written["id"]
    assert record["gate"] == GATE_LOOP_STEP
    assert record["loop_id"] == "loop-audit-test-1"
    assert record["fingerprint_fields"] == LOOP_FIELDS
    assert record["approved_by"] == "a.engineer"
    assert record["outcome"] == OUTCOME_APPROVED
    assert record["decided_at"] == written["decided_at"]


def test_a_refusal_is_recorded_just_as_completely_as_an_approval(db_conn):
    """Issue #258, story #29: a refused decision must be just as
    recoverable as an approved one, not a lesser record."""
    written = append_audit_record(
        db_conn,
        gate=GATE_LOOP_STEP,
        fingerprint_fields=LOOP_FIELDS,
        approved_by="a.engineer",
        outcome=OUTCOME_REFUSED,
    )
    assert written["outcome"] == OUTCOME_REFUSED

    [record] = fetch_audit_records(db_conn, loop_id="loop-audit-test-1")
    assert record["outcome"] == OUTCOME_REFUSED
    assert record["fingerprint_fields"] == LOOP_FIELDS
    assert record["approved_by"] == "a.engineer"


def test_design_release_decisions_have_no_loop_id(db_conn):
    """release_fingerprint_fields (designs/release_approval.py) carries no
    loop_id -- the column must come back NULL, not an empty string or a
    fabricated value, and must never surface in a loop_id-filtered fetch."""
    written = append_audit_record(
        db_conn,
        gate=GATE_DESIGN_RELEASE,
        fingerprint_fields=RELEASE_FIELDS,
        approved_by="a.decisionmaker",
        outcome=OUTCOME_APPROVED,
    )
    assert written["loop_id"] is None
    assert written["fingerprint_fields"] == RELEASE_FIELDS

    assert fetch_audit_records(db_conn, loop_id="loop-audit-test-1") == [] or all(
        r["id"] != written["id"] for r in fetch_audit_records(db_conn, loop_id="loop-audit-test-1")
    )


def test_multiple_records_for_the_same_loop_id_all_persist_in_order(db_conn):
    loop_id = "loop-audit-test-multi"
    steps = ["architecture", "measurement", "redesign_decision"]
    written_ids = []
    for step in steps:
        record = append_audit_record(
            db_conn,
            gate=GATE_LOOP_STEP,
            fingerprint_fields={**LOOP_FIELDS, "loop_id": loop_id, "step": step},
            approved_by="a.engineer",
            outcome=OUTCOME_APPROVED,
        )
        written_ids.append(record["id"])

    fetched = fetch_audit_records(db_conn, loop_id=loop_id)
    assert [r["id"] for r in fetched] == written_ids
    assert [r["fingerprint_fields"]["step"] for r in fetched] == steps


def test_fetch_with_no_loop_id_returns_every_record_including_release_gate(db_conn):
    """`fetch_audit_records` with no filter is the "everything" read -- a
    superset check (not exact equality) because the audit log is durable,
    real storage and earlier test runs may have left rows behind, exactly
    as a production audit log would."""
    loop_record = append_audit_record(
        db_conn,
        gate=GATE_LOOP_STEP,
        fingerprint_fields={**LOOP_FIELDS, "loop_id": "loop-audit-test-all"},
        approved_by="a.engineer",
        outcome=OUTCOME_APPROVED,
    )
    release_record = append_audit_record(
        db_conn,
        gate=GATE_DESIGN_RELEASE,
        fingerprint_fields=RELEASE_FIELDS,
        approved_by="a.decisionmaker",
        outcome=OUTCOME_REFUSED,
    )

    all_ids = {r["id"] for r in fetch_audit_records(db_conn)}
    assert loop_record["id"] in all_ids
    assert release_record["id"] in all_ids


def test_fingerprint_fields_round_trip_key_order_independent(db_conn):
    """Two dicts with the same content in a different key order are the
    same decision -- the stored decision_fingerprint must agree, mirroring
    the order-independence both approval gates' own fingerprints already
    guarantee (tests/test_design_release_approval.py)."""
    a = append_audit_record(
        db_conn,
        gate=GATE_LOOP_STEP,
        fingerprint_fields=LOOP_FIELDS,
        approved_by="a.engineer",
        outcome=OUTCOME_APPROVED,
    )
    b = append_audit_record(
        db_conn,
        gate=GATE_LOOP_STEP,
        fingerprint_fields=dict(reversed(list(LOOP_FIELDS.items()))),
        approved_by="a.engineer",
        outcome=OUTCOME_APPROVED,
    )
    assert a["decision_fingerprint"] == b["decision_fingerprint"]


# --- validation --------------------------------------------------------


def test_gate_must_be_a_known_value(db_conn):
    with pytest.raises(InvalidAuditRecordError, match="gate"):
        append_audit_record(
            db_conn,
            gate="not_a_real_gate",
            fingerprint_fields=LOOP_FIELDS,
            approved_by="a.engineer",
            outcome=OUTCOME_APPROVED,
        )


def test_outcome_must_be_a_known_value(db_conn):
    with pytest.raises(InvalidAuditRecordError, match="outcome"):
        append_audit_record(
            db_conn,
            gate=GATE_LOOP_STEP,
            fingerprint_fields=LOOP_FIELDS,
            approved_by="a.engineer",
            outcome="maybe",
        )


def test_approved_by_is_required():
    with pytest.raises(InvalidAuditRecordError, match="approved_by"):
        # No db_conn needed -- validation happens before the database is
        # touched, same discipline as designs/material_properties.py's
        # add_entry.
        append_audit_record(
            None,
            gate=GATE_LOOP_STEP,
            fingerprint_fields=LOOP_FIELDS,
            approved_by="",
            outcome=OUTCOME_APPROVED,
        )


def test_fingerprint_fields_must_be_a_dict():
    with pytest.raises(InvalidAuditRecordError, match="fingerprint_fields"):
        append_audit_record(
            None,
            gate=GATE_LOOP_STEP,
            fingerprint_fields="not-a-dict",
            approved_by="a.engineer",
            outcome=OUTCOME_APPROVED,
        )


def test_audit_gates_and_outcomes_are_exactly_the_documented_values():
    assert AUDIT_GATES == {GATE_LOOP_STEP, GATE_DESIGN_RELEASE}
    assert AUDIT_OUTCOMES == {OUTCOME_APPROVED, OUTCOME_REFUSED}


# --- structural: genuinely append-only, not by convention -------------------


def test_no_update_or_delete_function_exists_anywhere_in_the_module():
    """The load-bearing property (issue #258): it must be structurally
    impossible to update or delete an audit row through this module's
    public surface -- not merely a function nobody happens to call. Every
    public, module-level callable's name is checked, not just __all__, so
    a helper added later without being exported still gets caught."""
    import orchestration.approval_audit as audit_module

    forbidden_substrings = ("update", "delete", "remove")
    offending = [
        name
        for name, obj in vars(audit_module).items()
        if callable(obj)
        and not name.startswith("_")
        and inspect.getmodule(obj) is audit_module
        and any(bad in name.lower() for bad in forbidden_substrings)
    ]
    assert offending == [], (
        f"orchestration/approval_audit.py must expose no update/delete/remove "
        f"function -- found: {offending}"
    )


def test_no_sql_update_or_delete_statement_appears_in_the_module_source():
    """Belt-and-braces on the same property, checked at the SQL-string
    level rather than by scanning the whole file's prose (this module's
    own docstring talks *about* update/delete not existing, which would
    give a naive whole-file substring search false positives): every
    string literal passed as a `cur.execute(...)` query in this module is
    parsed out and checked for an UPDATE/DELETE SQL keyword.
    append_audit_record only ever INSERTs, fetch_audit_records only ever
    SELECTs."""
    import ast

    import orchestration.approval_audit as audit_module

    tree = ast.parse(inspect.getsource(audit_module))
    queries = [
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ]
    assert queries, "expected at least one cur.execute(...) query in this module"
    for query in queries:
        upper = query.upper()
        assert "UPDATE " not in upper, f"found an UPDATE statement: {query!r}"
        assert "DELETE " not in upper, f"found a DELETE statement: {query!r}"


# --- durability across a process restart ------------------------------------


def test_a_record_survives_the_writing_connection_closing_and_reopening():
    """The entire point of this module (see its docstring, and issue
    #258's story #27): a receipt's signing key is process-local and does
    NOT survive a restart, but this audit record must. This test proves
    durable storage, not in-memory state -- it commits on one connection,
    closes it, opens a brand new one, and reads back from that.

    Skipped with an explicit reason (never silently) if no real Postgres
    is reachable in this environment."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip(
            "DATABASE_URL is not set in this environment -- the "
            "durability-across-restart property could not be exercised "
            "against a real Postgres here. See the test's own docstring: "
            "this is the one property that structurally CANNOT be proven "
            "against an in-memory or mocked connection, so it is skipped "
            "with this explicit reason rather than faked."
        )

    # A fresh, random loop_id every run: this test's whole point is to
    # commit a REAL, durable row (unlike every other test in this file,
    # which relies on the db_conn fixture's rollback-on-teardown and so
    # never actually persists anything) -- so, exactly like a production
    # audit log, rows from earlier runs of this same test are still sitting
    # in the table. A fixed loop_id would make "exactly one record" true
    # only on a pristine database and false on every rerun; a fresh id
    # each time keeps the assertion meaningful either way.
    loop_id = f"loop-audit-test-durability-{uuid.uuid4()}"
    fingerprint_fields = {**LOOP_FIELDS, "loop_id": loop_id}

    write_conn = psycopg.connect(database_url)
    try:
        written = append_audit_record(
            write_conn,
            gate=GATE_LOOP_STEP,
            fingerprint_fields=fingerprint_fields,
            approved_by="a.engineer",
            outcome=OUTCOME_APPROVED,
        )
        write_conn.commit()
    finally:
        write_conn.close()

    # A fresh connection -- nothing here shares any state, in-memory or
    # otherwise, with write_conn above.
    read_conn = psycopg.connect(database_url)
    try:
        records = fetch_audit_records(read_conn, loop_id=loop_id)
    finally:
        read_conn.close()

    assert len(records) == 1
    assert records[0]["id"] == written["id"]
    assert records[0]["fingerprint_fields"] == fingerprint_fields
    assert records[0]["approved_by"] == "a.engineer"
    assert records[0]["outcome"] == OUTCOME_APPROVED
