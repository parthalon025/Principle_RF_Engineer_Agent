"""Thin orchestration: validate -> write -> translate exceptions.

`create_design` and `verify_requirement` are what get wrapped as tools in
`agent/main.py` and `mcp_server/server.py` (tickets #17 and #21), mirroring
`knowledge/ingest.py`'s `ingest_document`: owns the connection lifecycle so
the tool wrappers don't each have to duplicate it, and turns `designs.db`'s
typed exceptions into a structured, `status`-tagged result instead of
letting them cross the tool boundary as a raw stack trace -- "a dangling
reference is rejected with a structured error naming the offending block"
(#17 acceptance criteria); "verifying an unknown requirement_id is rejected
cleanly" (#21's).

Only `create_design` and `verify_requirement` are in scope for these
tickets; `record_decision` and `read_design` (#16's other tool entry
points) are #18-#20's job.
"""

from __future__ import annotations

from typing import Any

from designs import db
from designs.validation import InvalidRequirementsError, InvalidVerificationStatusError


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


def verify_requirement(
    design_id: int,
    requirement_id: str,
    method: str,
    status: str,
    expected: Any = None,
    actual: Any = None,
    evidence_uri: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Explicitly record verification of one requirement. See
    `designs.db.verify_requirement` for the full write-path contract
    (targets exactly one row via `(design_id, requirement_id)`, full
    replace of the row's mutable columns, always explicit -- never
    inferred). An unknown `(design_id, requirement_id)` pair or an invalid
    `status` returns a structured `status`-tagged result instead of
    raising, so the caller -- human or agent -- gets a message it can act
    on rather than a stack trace; a write that fails for any other reason
    still raises.
    """
    conn = db.get_connection()
    try:
        try:
            row = db.verify_requirement(
                conn,
                design_id=design_id,
                requirement_id=requirement_id,
                method=method,
                status=status,
                expected=expected,
                actual=actual,
                evidence_uri=evidence_uri,
                notes=notes,
            )
        except InvalidVerificationStatusError as exc:
            conn.rollback()
            return {"status": "invalid_status", "message": str(exc)}
        except db.UnknownVerificationItemError as exc:
            conn.rollback()
            return {"status": "unknown_requirement", "message": str(exc)}
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "status": "verified",
        "design_id": row["design_id"],
        "requirement_id": row["requirement_id"],
        "verification_status": row["status"],
        "method": row["method"],
        "expected": row["expected"],
        "actual": row["actual"],
        "evidence_uri": row["evidence_uri"],
        "notes": row["notes"],
    }
