"""psycopg-based reads/writes for `designs` and its auto-created
`verification_items` rows (ticket #17).

Thin I/O module, mirroring `knowledge/db.py`'s style directly: no ORM, raw
SQL via psycopg, matching `db/schema.sql`. Functions take an already-open
connection and never commit it themselves -- the caller (production:
`agent/main.py` / `mcp_server/server.py`'s tool wrappers; tests: the
`db_conn` fixture) owns the transaction boundary.

`create_design` (#17) and `read_design` (#18) are in scope here --
`record_engineering_result`, `record_decision`, and `verify_requirement`
(#16's other `designs/db.py` functions) belong to #19-#21.
"""

from __future__ import annotations

import copy
import datetime
import os
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from designs.models import DesignStatus, VerificationStatus
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


def read_design(conn: psycopg.Connection, design_id: int) -> dict[str, Any] | None:
    """Fetch a design plus everything hung off it in one payload (ticket
    #18): its `requirements`/`architecture` (every `component_id`
    referenced in `architecture` resolved inline to its `manufacturer`/
    `part_number`, not left as a bare id), and all of its
    `engineering_results`, `decision_records`, and `verification_items`
    rows. This is the one human-visible surface for the whole #16 feature
    area -- everything else (#17/#19/#20/#21) is write-only until this
    exists.

    Returns None if no `designs` row matches `design_id` -- mirrors
    `knowledge.db.get_document`'s not-found signal rather than raising or
    returning an empty/ambiguous payload. A design with none of
    `engineering_results`/`decision_records` populated yet (both still
    possible before #19/#20 land) comes back with those as empty lists,
    never an error -- nothing here assumes any of the three related tables
    holds rows for this design.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM designs WHERE id = %s", (design_id,))
        design_row = cur.fetchone()
    if design_row is None:
        return None

    architecture = _resolve_architecture_components(conn, design_row["architecture"])

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, result_type, name, value, provenance, source_uri, tool_name, "
            "tool_version, model_revision, confidence, created_at "
            "FROM engineering_results WHERE design_id = %s ORDER BY id",
            (design_id,),
        )
        engineering_results = cur.fetchall()

        cur.execute(
            "SELECT id, record_key, decision, alternatives, rationale, evidence, "
            "approval_required, approval_status, created_at "
            "FROM decision_records WHERE design_id = %s ORDER BY id",
            (design_id,),
        )
        decision_records = cur.fetchall()

        cur.execute(
            "SELECT id, requirement_id, requirement, method, expected, actual, status, "
            "evidence_uri, notes "
            "FROM verification_items WHERE design_id = %s ORDER BY id",
            (design_id,),
        )
        verification_items = cur.fetchall()

    return {
        "design_id": design_row["id"],
        "design_key": design_row["design_key"],
        "name": design_row["name"],
        "revision": design_row["revision"],
        "status": design_row["status"],
        "requirements": design_row["requirements"],
        "architecture": architecture,
        "engineering_results": [_serialize_row(r) for r in engineering_results],
        "decision_records": [_serialize_row(r) for r in decision_records],
        "verification_items": verification_items,
    }


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of `row` with any `datetime`/`date` values (e.g.
    `created_at`) converted to ISO-8601 strings, so `read_design`'s payload
    is JSON-serializable end to end -- matches `knowledge.read.read_document`'s
    existing `publication_date.isoformat()` handling."""
    return {
        key: value.isoformat() if isinstance(value, (datetime.date, datetime.datetime)) else value
        for key, value in row.items()
    }


def _resolve_architecture_components(
    conn: psycopg.Connection, architecture: dict[str, Any]
) -> dict[str, Any]:
    """Return a deep copy of `architecture` with every `component_id`
    reference (`designs.validation.extract_component_refs`'s walk) augmented
    inline with the referenced component's `manufacturer`/`part_number`,
    fetched in one query -- so a caller sees a resolved reference, not a
    bare id (#18 acceptance criteria). A `component_id` with no matching
    `components` row (shouldn't happen behind `create_design`'s own
    existence check, but nothing here re-enforces it) resolves to
    `manufacturer`/`part_number` of None rather than raising.
    """
    component_ids = extract_component_refs(architecture)
    if not component_ids:
        return copy.deepcopy(architecture)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, manufacturer, part_number FROM components WHERE id = ANY(%s)",
            (list(set(component_ids)),),
        )
        resolved = {row["id"]: row for row in cur.fetchall()}

    def _walk(node: Any) -> Any:
        if isinstance(node, dict):
            new_node = {key: _walk(value) for key, value in node.items()}
            component_id = node.get("component_id")
            if isinstance(component_id, int) and not isinstance(component_id, bool):
                match = resolved.get(component_id)
                new_node["manufacturer"] = match["manufacturer"] if match else None
                new_node["part_number"] = match["part_number"] if match else None
            return new_node
        if isinstance(node, list):
            return [_walk(item) for item in node]
        return node

    return _walk(architecture)
