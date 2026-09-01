"""psycopg-based reads/writes for `designs` and its auto-created
`verification_items` rows (ticket #17).

Thin I/O module, mirroring `knowledge/db.py`'s style directly: no ORM, raw
SQL via psycopg, matching `db/schema.sql`. Functions take an already-open
connection and never commit it themselves -- the caller (production:
`agent/main.py` / `mcp_server/server.py`'s tool wrappers; tests: the
`db_conn` fixture) owns the transaction boundary.

`create_design` (#17) and `record_engineering_result` (#19) are in scope
here -- `record_decision` (#20), `verify_requirement` (#21), and
`read_design` (#18) belong to the sibling tickets.
"""

from __future__ import annotations

import os
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from designs.models import DesignStatus, VerificationStatus
from designs.provenance import provenance_for_tool
from designs.validation import (
    _iter_component_refs,
    extract_component_refs,
    validate_requirements,
)


def get_connection() -> psycopg.Connection:
    """Open a new connection using DATABASE_URL from the environment."""
    return psycopg.connect(os.environ["DATABASE_URL"])


class DanglingComponentReferenceError(Exception):
    """Raised by `create_design` when `architecture` references a
    `component_id` with no matching `components` row. Carries every
    offending reference -- not just the first one found -- as
    `offending`, a list of `{"block": ..., "component_id": ...}` dicts,
    so the caller sees the full picture in one round trip instead of
    fixing dangling references one at a time. Nothing is written to
    `designs` or `verification_items` when this is raised.
    """

    def __init__(self, offending: list[dict[str, Any]]):
        self.offending = offending
        detail = "; ".join(
            f"block {o['block']!r} references component_id={o['component_id']} "
            "(no such component)"
            for o in offending
        )
        super().__init__(f"architecture has dangling component_id reference(s): {detail}")


def _find_dangling_component_refs(
    conn: psycopg.Connection, architecture: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return `{"block": ..., "component_id": ...}` for every `component_id`
    referenced in `architecture` that has no matching `components` row, in
    the order `extract_component_refs` encountered them. Empty list ->
    every reference resolves (including when there are none at all)."""
    component_ids = extract_component_refs(architecture)
    if not component_ids:
        return []

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM components WHERE id = ANY(%s)",
            (list(set(component_ids)),),
        )
        existing_ids = {row[0] for row in cur.fetchall()}

    missing = {cid for cid in component_ids if cid not in existing_ids}
    if not missing:
        return []
    return [
        {"block": block, "component_id": component_id}
        for block, component_id in _iter_component_refs(architecture)
        if component_id in missing
    ]


def create_design(
    conn: psycopg.Connection,
    design_key: str,
    name: str,
    revision: str,
    requirements: dict[str, Any],
    architecture: dict[str, Any],
) -> dict[str, Any]:
    """Insert a new `designs` row in `DRAFT` status, plus one
    `verification_items` row per `requirements` key (all `NOT VERIFIED`).

    - `requirements` is shape-checked by
      `designs.validation.validate_requirements` before anything touches
      the database -- a dict keyed by `requirement_id`, each value
      carrying a `requirement` text field -- raising
      `InvalidRequirementsError` on a wrong shape.
    - Every `component_id` referenced anywhere in `architecture`
      (`designs.validation.extract_component_refs`) is existence-checked
      against real `components` rows before anything is written. Any
      dangling reference raises `DanglingComponentReferenceError` naming
      every offending block; no `designs` or `verification_items` row is
      created.
    - The `designs` insert and its `verification_items` auto-creation are
      two statements on the same connection with no commit between them,
      so they share whatever transaction the caller is already in --
      never left half-done. (Deliberately *not* wrapped in its own nested
      `with conn.transaction():`: psycopg treats that as a genuine
      top-level transaction -- auto-committing on a clean exit -- unless
      some earlier statement on this connection already opened one, which
      isn't guaranteed here the way it is in `knowledge.db.insert_document`
      -- e.g. `architecture` with no `component_id` refs never queries
      `components` at all. Plain sequential statements avoid depending on
      that invariant and match this module's own contract: the caller
      owns the transaction boundary, not `create_design`.)
    """
    validate_requirements(requirements)

    offending = _find_dangling_component_refs(conn, architecture)
    if offending:
        raise DanglingComponentReferenceError(offending)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO designs (design_key, name, revision, status, requirements, architecture)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                design_key,
                name,
                revision,
                DesignStatus.DRAFT.value,
                Json(requirements),
                Json(architecture),
            ),
        )
        design_row = cur.fetchone()
        assert design_row is not None

        if requirements:
            cur.executemany(
                """
                INSERT INTO verification_items
                    (design_id, requirement_id, requirement, method, status)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    (
                        design_row["id"],
                        requirement_id,
                        value["requirement"],
                        # `method` is NOT NULL with no schema default, but a
                        # verification method isn't known until a human/agent
                        # actually calls `verify_requirement` (#20) -- left
                        # empty rather than a placeholder string that would
                        # read as a real (if vague) method.
                        "",
                        VerificationStatus.NOT_VERIFIED.value,
                    )
                    for requirement_id, value in requirements.items()
                ],
            )

    return design_row


def record_engineering_result(
    conn: psycopg.Connection,
    design_id: int,
    tool_name: str,
    value: Any,
    tool_version: str | None = None,
) -> dict[str, Any]:
    """Insert one `engineering_results` row for a calculation/Touchstone/
    simulation tool run against `design_id` (ticket #19; CONTEXT.md:
    Engineering result).

    `result_type` and `name` are both the tool's own name (`tool_name`) --
    this ticket's wrappers have no separate human-supplied label to give
    `name`, so it mirrors `result_type` rather than inventing one.
    `provenance` is never caller-supplied: it's looked up from `tool_name`
    via `designs.provenance.provenance_for_tool`, which raises `ValueError`
    for a tool with no mapping. `confidence` is always `NULL` -- deterministic
    calculations don't carry a confidence signal (CONTEXT.md). `value` is
    stored as-is via `Json`, so it accepts either a bare JSON scalar (a
    `calculate_vswr`-style tool returning a plain float) or a JSON object
    (a `calculate_noise_figure`/`analyze_touchstone_file`-style tool
    returning a dict) -- whatever the tool's own return payload is.

    Same transaction-boundary contract as `create_design`: takes an
    already-open connection and never commits it itself.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO engineering_results
                (design_id, result_type, name, value, provenance, tool_name, tool_version,
                 confidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NULL)
            RETURNING *
            """,
            (
                design_id,
                tool_name,
                tool_name,
                Json(value),
                provenance_for_tool(tool_name),
                tool_name,
                tool_version,
            ),
        )
        row = cur.fetchone()
        assert row is not None
    return row
