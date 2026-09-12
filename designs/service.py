"""Thin orchestration: validate -> write -> translate exceptions (and,
for reads, fetch -> translate a miss).

`create_design` (ticket #17) is what gets wrapped as the `create_design`
tool in `agent/main.py` and `mcp_server/server.py`, mirroring
`knowledge/ingest.py`'s `ingest_document`: owns the connection lifecycle so
the tool wrappers don't each have to duplicate it, and turns `designs.db`'s
typed exceptions into a structured, `status`-tagged result instead of
letting them cross the tool boundary as a raw stack trace -- "a dangling
reference is rejected with a structured error naming the offending block"
(#17 acceptance criteria).

`read_design` (ticket #18) is the `read_design` tool's backing function,
mirroring `knowledge/read.py`'s `read_document`: owns the connection
lifecycle and turns a missing id into a structured `not_found` result
instead of `None` crossing the tool boundary.

`record_decision` (ticket #20) logs a judgment-laden design decision. See
`designs.db.record_decision` for the full write-path contract (`record_key`
collision handling, always-`PENDING` `approval_status`). Reusing an
existing `record_key` returns a structured `status`-tagged result pointing
at the existing row instead of raising.

`record_engineering_result` (ticket #19) records one `engineering_results`
row for a calculation/Touchstone/simulation tool's own run against
`design_id`. Owns the connection lifecycle the same way `create_design`
does, so every `calculate_*`/`analyze_touchstone_file` tool wrapper in
`agent/main.py`/`mcp_server/server.py` can call this directly instead of
managing a connection itself. Not itself an agent-exposed tool -- called
internally by those wrappers.

`verify_requirement` (ticket #21) explicitly records verification of one
requirement. See `designs.db.verify_requirement` for the full write-path
contract (targets exactly one row via `(design_id, requirement_id)`, full
replace of the row's mutable columns, always explicit -- never inferred).
An unknown `(design_id, requirement_id)` pair or an invalid `status`
returns a structured `status`-tagged result instead of raising --
"verifying an unknown requirement_id is rejected cleanly" (#21's).

All four of #16's tool entry points, plus the internal #19 recording
function, are now implemented here.
"""

from __future__ import annotations

from typing import Any

from designs import db
from designs.lifecycle import IllegalStatusTransitionError, legal_transitions_from
from designs.release_approval import DesignReleaseApprovalError, DesignReleaseApprovalReceipt
from designs.validation import InvalidRequirementsError, InvalidVerificationStatusError


def create_design(
    design_key: str,
    name: str,
    revision: str,
    requirements: dict[str, Any],
    architecture: dict[str, Any],
    assumptions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Start a new design in `DRAFT` status. See `designs.db.create_design`
    for the full write-path contract (`(design_key, revision)` collision
    handling, `requirements` shape check, `architecture`'s `component_id`
    existence check, auto-created `verification_items`). A rejected write
    returns a structured `status`-tagged result instead of raising, so the
    caller -- human or agent -- gets a message it can act on rather than a
    stack trace; a write that fails for any other reason still raises.

    `assumptions` (issue #413) is passed straight through to
    `designs.db.create_design` -- `None` (the default) stores `{}`. No
    shape check, unlike `requirements`.
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
                assumptions=assumptions,
            )
        except db.DesignKeyRevisionCollisionError as exc:
            conn.rollback()
            return {
                "status": "design_key_revision_collision",
                "existing_design_id": exc.existing["id"],
                "message": (
                    f"design_key {exc.design_key!r} revision {exc.revision!r} is "
                    f"already in use by design_id={exc.existing['id']}."
                ),
            }
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
    design_family: str | None = None,
    approval_required: bool = True,
) -> dict[str, Any]:
    """Log a judgment-laden design decision. See `designs.db.record_decision`
    for the full write-path contract (`record_key` collision handling,
    always-`PENDING` `approval_status`, `design_family`). Reusing an
    existing `record_key` returns a structured `status`-tagged result
    pointing at the existing row instead of raising, so the caller can
    look up what was already recorded rather than getting a stack trace;
    a write that fails for any other reason still raises.
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
                design_family=design_family,
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


def record_engineering_result(
    design_id: int,
    tool_name: str,
    value: Any,
    tool_version: str | None = None,
    provenance: str | None = None,
) -> dict[str, Any]:
    """Record one `engineering_results` row for a calculation/Touchstone/
    simulation tool's own run against `design_id` (ticket #19). Owns the
    connection lifecycle the same way `create_design` does, so every
    `calculate_*`/`analyze_touchstone_file` tool wrapper in `agent/main.py`/
    `mcp_server/server.py` can call this directly instead of managing a
    connection itself. See `designs.db.record_engineering_result` for the
    full write-path contract (`provenance` looked up from `tool_name` unless
    passed explicitly -- docs/adr/0011 -- `confidence` always `NULL`).
    Returns just the new row's id -- wrappers merge
    `{"engineering_result_id": ...}` into their own `recorded_as` field,
    they don't need the rest of the row back.
    """
    conn = db.get_connection()
    try:
        row = db.record_engineering_result(
            conn,
            design_id=design_id,
            tool_name=tool_name,
            value=value,
            tool_version=tool_version,
            provenance=provenance,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {"engineering_result_id": row["id"]}


def coerce_release_approval(approval: Any) -> Any:
    """dict -> `DesignReleaseApprovalReceipt` coercion for a release-approval
    receipt that already crossed an agent/MCP JSON tool boundary and back
    (issue #258 ticket 4).

    Mirrors `orchestration.design_loop`'s own `_coerce_receipt` -- same
    shape, but for `DesignReleaseApprovalReceipt` instead of
    `LoopStepApprovalReceipt`: a dict is rebuilt via
    `DesignReleaseApprovalReceipt(**approval)` (exactly what that class's
    own docstring in `designs/release_approval.py` says a `to_dict()`
    output reconstructs through); anything else -- `None`, or an
    already-constructed receipt -- passes through unchanged.

    A dict that doesn't even match the receipt's fields (missing/extra
    keys) also passes through unchanged rather than raising `TypeError`
    here: `designs.release_approval.check_design_release_approval_gate`
    already refuses anything that isn't a real `DesignReleaseApprovalReceipt`
    instance with a clear message, so a malformed dict is left for that
    existing check to reject cleanly instead of crashing this coercion
    step. This function never fabricates a valid receipt -- it only
    reconstructs one that `request_design_release_approval` (via the
    ticket-3 `approval_cli`) already minted elsewhere.

    Shared by `agent/main.py`'s and `mcp_server/server.py`'s
    `advance_design_status` tool wrappers, which both import it the same
    way they already import `update_design_status` below, so the coercion
    logic lives in exactly one place instead of two hand-duplicated
    copies."""
    if isinstance(approval, dict):
        try:
            return DesignReleaseApprovalReceipt(**approval)
        except TypeError:
            return approval
    return approval


def update_design_status(
    design_id: int,
    status: str,
    *,
    approval: Any = None,
    allow_nonsequential: bool = False,
) -> dict[str, Any]:
    """Set a design's `status` (docs/adr/0011, issue #145). See
    `designs.db.update_design_status` for the full write-path contract
    (`status` value check, lifecycle ordering, the RELEASED approval gate,
    `updated_at` bump). Every refusal returns a structured `status`-tagged
    result instead of raising, matching every other function in this module;
    a write that fails for any other reason still raises.

    The three refusals are tagged apart because they need different fixes:

    - `invalid_status` -- that is not one of the nine legal values at all.
    - `illegal_transition` -- a real status, but not reachable from where
      this design currently is. `legal_next` names what is.
    - `release_not_approved` -- the move to RELEASED needs a signed
      human-approval receipt (`designs.release_approval`), and none valid
      for this design revision was supplied.
    """
    conn = db.get_connection()
    try:
        try:
            row = db.update_design_status(
                conn,
                design_id=design_id,
                status=status,
                approval=approval,
                allow_nonsequential=allow_nonsequential,
            )
        except IllegalStatusTransitionError as exc:
            conn.rollback()
            return {
                "status": "illegal_transition",
                "message": str(exc),
                "current_status": exc.current.value,
                "requested_status": exc.target.value,
                "legal_next": sorted(s.value for s in legal_transitions_from(exc.current)),
            }
        except DesignReleaseApprovalError as exc:
            conn.rollback()
            return {"status": "release_not_approved", "message": str(exc)}
        except ValueError as exc:
            conn.rollback()
            return {"status": "invalid_status", "message": str(exc)}
        except db.UnknownDesignError as exc:
            conn.rollback()
            return {"status": "not_found", "design_id": exc.design_id}
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "status": "updated",
        "design_id": row["id"],
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
