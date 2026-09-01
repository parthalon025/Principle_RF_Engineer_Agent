"""Thin orchestration: validate -> write -> translate exceptions (and,
for reads, fetch -> translate a miss).

`create_design` is what gets wrapped as the `create_design` tool in
`agent/main.py` and `mcp_server/server.py` (ticket #17), mirroring
`knowledge/ingest.py`'s `ingest_document`: owns the connection lifecycle so
the two tool wrappers don't each have to duplicate it, and turns
`designs.db`'s typed exceptions into a structured, `status`-tagged result
instead of letting them cross the tool boundary as a raw stack trace --
"a dangling reference is rejected with a structured error naming the
offending block" (#17 acceptance criteria).

`read_design` (ticket #18) is the `read_design` tool's backing function,
mirroring `knowledge/read.py`'s `read_document`: owns the connection
lifecycle and turns a missing id into a structured `not_found` result
instead of `None` crossing the tool boundary.

`record_decision` (ticket #20) logs a judgment-laden design decision. See
`designs.db.record_decision` for the full write-path contract (`record_key`
collision handling, always-`PENDING` `approval_status`). Reusing an
existing `record_key` returns a structured `status`-tagged result pointing
at the existing row instead of raising.

`create_design`, `read_design`, and `record_decision` are in scope for this
ticket set; `verify_requirement` (#16's other tool entry point) is #21's
job.
"""

from __future__ import annotations

from typing import Any

from designs import db
from designs.validation import InvalidRequirementsError


def create_design(
    design_key: str,
    name: str,
    revision: str,
    requirements: dict[str, Any],
    architecture: dict[str, Any],
) -> dict[str, Any]:
    """Start a new design in `DRAFT` status. See `designs.db.create_design`
    for the full write-path contract (`requirements` shape check,
    `architecture`'s `component_id` existence check, auto-created
    `verification_items`). A rejected write returns a structured
    `status`-tagged result instead of raising, so the caller -- human or
    agent -- gets a message it can act on rather than a stack trace; a
    write that fails for any other reason still raises.
    """
    conn = db.get_connection()
    try:
        try:
            row = db.create_design(
                conn,
                design_key=design_key,
                name=name,
                revision=revision,
                requirements=requirements,
                architecture=architecture,
            )
        except InvalidRequirementsError as exc:
            conn.rollback()
            return {"status": "invalid_requirements", "message": str(exc)}
        except db.DanglingComponentReferenceError as exc:
            conn.rollback()
            return {
                "status": "dangling_component_reference",
                "offending": exc.offending,
                "message": str(exc),
            }
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "status": "created",
        "design_id": row["id"],
        "design_key": row["design_key"],
        "name": row["name"],
        "revision": row["revision"],
        "design_status": row["status"],
    }


def read_design(design_id: int) -> dict[str, Any]:
    """Fetch a stored design's full payload: `design_key`/`name`/`revision`/
    `status`, its `requirements`, its `architecture` (`component_id`
    references resolved inline to `manufacturer`/`part_number`), and all of
    its `engineering_results`/`decision_records`/`verification_items` rows.
    See `designs.db.read_design` for the aggregation itself.

    A nonexistent `design_id` returns `{"status": "not_found", "design_id":
    design_id}` rather than raising or leaking a DB exception (matching
    `knowledge.read.read_document`'s existing not-found pattern).
    """
    conn = db.get_connection()
    try:
        result = db.read_design(conn, design_id)
    finally:
        conn.close()

    if result is None:
        return {"status": "not_found", "design_id": design_id}

    return result


def record_decision(
    design_id: int,
    record_key: str,
    decision: str,
    alternatives: list[Any],
    rationale: str,
    evidence: list[Any],
    approval_required: bool = True,
) -> dict[str, Any]:
    """Log a judgment-laden design decision. See `designs.db.record_decision`
    for the full write-path contract (`record_key` collision handling,
    always-`PENDING` `approval_status`). Reusing an existing `record_key`
    returns a structured `status`-tagged result pointing at the existing
    row instead of raising, so the caller can look up what was already
    recorded rather than getting a stack trace; a write that fails for any
    other reason still raises.
    """
    conn = db.get_connection()
    try:
        try:
            row = db.record_decision(
                conn,
                design_id=design_id,
                record_key=record_key,
                decision=decision,
                alternatives=alternatives,
                rationale=rationale,
                evidence=evidence,
                approval_required=approval_required,
            )
        except db.RecordKeyCollisionError as exc:
            conn.rollback()
            return {
                "status": "record_key_collision",
                "existing_decision_id": exc.existing["id"],
                "message": (
                    f"record_key {exc.record_key!r} is already in use by "
                    f"decision_id={exc.existing['id']}."
                ),
            }
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "status": "recorded",
        "decision_id": row["id"],
        "design_id": row["design_id"],
        "record_key": row["record_key"],
        "approval_status": row["approval_status"],
    }
