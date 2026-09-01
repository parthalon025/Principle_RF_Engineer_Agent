"""Thin orchestration: validate -> write -> translate exceptions.

`create_design` is what gets wrapped as the `create_design` tool in
`agent/main.py` and `mcp_server/server.py` (ticket #17), mirroring
`knowledge/ingest.py`'s `ingest_document`: owns the connection lifecycle so
the two tool wrappers don't each have to duplicate it, and turns
`designs.db`'s typed exceptions into a structured, `status`-tagged result
instead of letting them cross the tool boundary as a raw stack trace --
"a dangling reference is rejected with a structured error naming the
offending block" (#17 acceptance criteria).

`create_design` (#17) and `record_engineering_result` (#19) are in scope
here; `record_decision`, `verify_requirement`, and `read_design` (#16's
other tool entry points) are #18/#20/#21's job.
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


def record_engineering_result(
    design_id: int,
    tool_name: str,
    value: Any,
    tool_version: str | None = None,
) -> dict[str, Any]:
    """Record one `engineering_results` row for a calculation/Touchstone/
    simulation tool's own run against `design_id` (ticket #19). Owns the
    connection lifecycle the same way `create_design` does, so every
    `calculate_*`/`analyze_touchstone_file` tool wrapper in `agent/main.py`/
    `mcp_server/server.py` can call this directly instead of managing a
    connection itself. See `designs.db.record_engineering_result` for the
    full write-path contract (`provenance` looked up from `tool_name`,
    `confidence` always `NULL`). Returns just the new row's id -- wrappers
    merge `{"engineering_result_id": ...}` into their own `recorded_as`
    field, they don't need the rest of the row back.
    """
    conn = db.get_connection()
    try:
        row = db.record_engineering_result(
            conn,
            design_id=design_id,
            tool_name=tool_name,
            value=value,
            tool_version=tool_version,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {"engineering_result_id": row["id"]}
