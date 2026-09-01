"""psycopg-based reads/writes for `designs` and its auto-created
`verification_items` rows (ticket #17).

Thin I/O module, mirroring `knowledge/db.py`'s style directly: no ORM, raw
SQL via psycopg, matching `db/schema.sql`. Functions take an already-open
connection and never commit it themselves -- the caller (production:
`agent/main.py` / `mcp_server/server.py`'s tool wrappers; tests: the
`db_conn` fixture) owns the transaction boundary.

`create_design` (#17) and `verify_requirement` (#21) are in scope here --
`record_engineering_result`, `record_decision`, and `read_design` (#16's
other `designs/db.py` functions) belong to #18-#20.
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
    validate_verification_status,
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


class UnknownVerificationItemError(Exception):
    """Raised by `verify_requirement` when no `verification_items` row
    exists for the given `(design_id, requirement_id)` pair -- a typoed or
    made-up `requirement_id`, or a `design_id` that doesn't exist. The
    `UNIQUE(design_id, requirement_id)` constraint added in #17 means at
    most one row could ever match, so "no row matched" is unambiguous
    rather than an update-vs-insert judgment call: nothing is written, and
    no stray row is ever created for an unrecognized `requirement_id`.
    """

    def __init__(self, design_id: int, requirement_id: str):
        self.design_id = design_id
        self.requirement_id = requirement_id
        super().__init__(
            f"no verification_items row for design_id={design_id}, "
            f"requirement_id={requirement_id!r} -- requirement_id must match "
            "one of the design's original requirements keys"
        )


def verify_requirement(
    conn: psycopg.Connection,
    design_id: int,
    requirement_id: str,
    method: str,
    status: str,
    expected: Any = None,
    actual: Any = None,
    evidence_uri: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Explicitly record verification of one requirement, updating the
    single `verification_items` row auto-created for it by `create_design`
    (#17).

    - Targets exactly one row via the `(design_id, requirement_id)`
      `UNIQUE` constraint (#17) -- an `UPDATE ... WHERE design_id = %s AND
      requirement_id = %s`, never an insert. No row matches ->
      `UnknownVerificationItemError`, naming both ids; nothing is written
      and no stray row is created.
    - `status` must be one of `VerificationStatus`'s four values (NOT
      VERIFIED/PASS/FAIL/MARGINAL) -- checked before the database is
      touched, raising `designs.validation.InvalidVerificationStatusError`
      on anything else.
    - This call is always explicit. Verification is never inferred by
      matching an `engineering_results.name` against a `requirement_id` --
      a wrong automatic guess would produce a silently wrong verification
      (#21). Folding a `FAIL` into any approval/release gate is out of
      scope here (#16); this only records the status.
    - Every field this function accepts (`method`/`status`/`expected`/
      `actual`/`evidence_uri`/`notes`) is set on every call -- a full
      replace of the row's mutable columns, not a partial patch, so the
      row after the call reflects exactly what was passed, never a stale
      value from an earlier call left untouched by omission.
    """
    validate_verification_status(status)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            UPDATE verification_items
            SET method = %s,
                status = %s,
                expected = %s,
                actual = %s,
                evidence_uri = %s,
                notes = %s
            WHERE design_id = %s AND requirement_id = %s
            RETURNING *
            """,
            (
                method,
                VerificationStatus(status).value,
                Json(expected) if expected is not None else None,
                Json(actual) if actual is not None else None,
                evidence_uri,
                notes,
                design_id,
                requirement_id,
            ),
        )
        row = cur.fetchone()

    if row is None:
        raise UnknownVerificationItemError(design_id, requirement_id)

    return row
