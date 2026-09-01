"""psycopg-based reads/writes for `designs` and its auto-created
`verification_items` rows (ticket #17).

Thin I/O module, mirroring `knowledge/db.py`'s style directly: no ORM, raw
SQL via psycopg, matching `db/schema.sql`. Functions take an already-open
connection and never commit it themselves -- the caller (production:
`agent/main.py` / `mcp_server/server.py`'s tool wrappers; tests: the
`db_conn` fixture) owns the transaction boundary.

Only `create_design` is in scope for this ticket -- `record_engineering_result`,
`record_decision`, `verify_requirement`, and `read_design` (#16's other
`designs/db.py` functions) belong to #18-#21.
"""

from __future__ import annotations

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


class RecordKeyCollisionError(Exception):
    """Raised by `record_decision` when `record_key` is already in use.
    Carries the existing row so the caller can point at it instead of
    silently overwriting -- the same dedup-and-point-back shape as
    `knowledge.db.insert_document`'s `DuplicateDocumentError`."""

    def __init__(self, record_key: str, existing: dict[str, Any]):
        self.record_key = record_key
        self.existing = existing
        super().__init__(f"record_key already in use: {record_key!r} (id={existing['id']})")


def find_decision_by_record_key(
    conn: psycopg.Connection, record_key: str
) -> dict[str, Any] | None:
    """Return the `decision_records` row with this `record_key`, if any --
    `record_key` is globally unique (`db/schema.sql`), so at most one row
    can ever match."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM decision_records WHERE record_key = %s", (record_key,))
        return cur.fetchone()


def record_decision(
    conn: psycopg.Connection,
    design_id: int,
    record_key: str,
    decision: str,
    alternatives: list[Any],
    rationale: str,
    evidence: list[Any],
    approval_required: bool = True,
) -> dict[str, Any]:
    """Insert a new `decision_records` row, always starting
    `approval_status = 'PENDING'` (docs/adr/0005: recording a decision is
    always an agent judgment call, never a structural trigger -- unlike
    `engineering_results`/`verification_items`, nothing here infers a
    decision from a calculation or architecture change).

    `record_key` is globally unique. Reusing one already in use raises
    `RecordKeyCollisionError` carrying the existing row -- never silently
    overwritten -- mirroring `knowledge.db.insert_document`'s
    checksum-based dedup-and-point-back.
    """
    existing = find_decision_by_record_key(conn, record_key)
    if existing is not None:
        raise RecordKeyCollisionError(record_key, existing)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO decision_records
                (design_id, record_key, decision, alternatives, rationale,
                 evidence, approval_required, approval_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                design_id,
                record_key,
                decision,
                Json(alternatives),
                rationale,
                Json(evidence),
                approval_required,
                "PENDING",
            ),
        )
        row = cur.fetchone()
        assert row is not None

    return row


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
