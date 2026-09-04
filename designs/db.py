"""psycopg-based reads/writes for `designs` and its auto-created
`verification_items` rows (ticket #17).

Thin I/O module, mirroring `knowledge/db.py`'s style directly: no ORM, raw
SQL via psycopg, matching `db/schema.sql`. Functions take an already-open
connection and never commit it themselves -- the caller (production:
`agent/main.py` / `mcp_server/server.py`'s tool wrappers; tests: the
`db_conn` fixture) owns the transaction boundary.

`create_design` (#17), `read_design` (#18), `record_decision` (#20),
`record_engineering_result` (#19), and `verify_requirement` (#21) are all
in scope here -- every `designs/db.py` function #16 called for.
"""

from __future__ import annotations

import copy
import datetime
import os
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from designs.lifecycle import check_transition, transition_requires_release_approval
from designs.models import DesignStatus, VerificationStatus
from designs.provenance import provenance_for_tool
from designs.release_approval import (
    check_design_release_approval_gate,
    release_fingerprint_fields,
)
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
            f"block {o['block']!r} references component_id={o['component_id']} (no such component)"
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


def find_decision_by_record_key(conn: psycopg.Connection, record_key: str) -> dict[str, Any] | None:
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


class UnknownDesignError(Exception):
    """Raised by `update_design_status` when no `designs` row exists for
    `design_id` -- mirrors `UnknownVerificationItemError`'s "no row
    matched is unambiguous" reasoning (the `designs` primary key means at
    most one row could ever match). Nothing is written."""

    def __init__(self, design_id: int):
        self.design_id = design_id
        super().__init__(f"no designs row for design_id={design_id}")


def update_design_status(
    conn: psycopg.Connection,
    design_id: int,
    status: str,
    *,
    approval: Any = None,
    allow_nonsequential: bool = False,
) -> dict[str, Any]:
    """Set `designs.status` (docs/adr/0011 -- the design loop's first real
    caller of a status transition; docs/adr/0007 fixed the nine legal
    values but deferred building any transition logic between them).

    `status` must be one of `DesignStatus`'s values -- checked before the
    database is touched, same discipline as `verify_requirement`'s own
    `status` check. An unknown `design_id` raises `UnknownDesignError`
    rather than silently affecting zero rows. `updated_at` is bumped to
    `now()` in the same statement -- this is the only function that
    changes `designs.status` after creation, so there is no separate
    "touch updated_at" call to keep in sync with it.

    Issue #145 adds the two rules ADR-0007 deferred:

    - **Ordering.** The transition must be legal per `designs.lifecycle`.
      A design can no longer jump DRAFT -> RELEASED, or move at all once
      RELEASED. Raises `IllegalStatusTransitionError` (a `ValueError`, so
      callers already catching `ValueError` around this function keep
      treating a refusal as a refusal).
    - **The release gate.** Entering `RELEASED` additionally requires a
      valid `DesignReleaseApprovalReceipt` in `approval`, bound to this
      design's key and revision (`designs.release_approval`). No workflow
      issues those yet, so nothing can currently be released -- which is
      the intended behaviour, not a gap.

    `allow_nonsequential=True` skips the *ordering* check only, for a caller
    that has legitimately walked the stages in memory and is persisting the
    outcome at an iteration boundary rather than at each step -- the design
    loop's flush, per ADR-0011. It never skips the release gate, and never
    permits entering `RELEASED` out of order: releasing is the one transition
    no caller may relax.

    The current row is read `FOR UPDATE` so the check and the write cannot
    straddle a concurrent transition.
    """
    if status not in {member.value for member in DesignStatus}:
        raise ValueError(
            f"status must be one of {sorted(m.value for m in DesignStatus)}, got {status!r}"
        )

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT design_key, revision, status FROM designs WHERE id = %s FOR UPDATE",
            (design_id,),
        )
        current = cur.fetchone()
        if current is None:
            raise UnknownDesignError(design_id)

        releasing = transition_requires_release_approval(current["status"], status)
        if releasing or not allow_nonsequential:
            check_transition(current["status"], status)
        if releasing:
            check_design_release_approval_gate(
                approval,
                release_fingerprint_fields(
                    design_id=design_id,
                    design_key=current["design_key"],
                    revision=current["revision"],
                    target=status,
                ),
            )

        cur.execute(
            """
            UPDATE designs
            SET status = %s, updated_at = now()
            WHERE id = %s
            RETURNING *
            """,
            (status, design_id),
        )
        row = cur.fetchone()

    return row


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
                status,
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


def record_engineering_result(
    conn: psycopg.Connection,
    design_id: int,
    tool_name: str,
    value: Any,
    tool_version: str | None = None,
    provenance: str | None = None,
) -> dict[str, Any]:
    """Insert one `engineering_results` row for a calculation/Touchstone/
    simulation tool run against `design_id` (ticket #19; CONTEXT.md:
    Engineering result).

    `result_type` and `name` are both the tool's own name (`tool_name`) --
    this ticket's wrappers have no separate human-supplied label to give
    `name`, so it mirrors `result_type` rather than inventing one.
    `provenance` is looked up from `tool_name` via
    `designs.provenance.provenance_for_tool` (which raises `ValueError` for
    a tool with no mapping) UNLESS the caller passes `provenance` explicitly
    -- an escape hatch added by docs/adr/0011 for trusted internal callers
    that have already computed the correct provenance themselves from a
    real function's own return value (`orchestration/tooling.py`'s
    design-loop persistence is the one caller that uses it: the loop's own
    step handlers, not this module's tool-name table, are the source of
    truth for a design-loop decision's provenance). Every existing caller
    -- the ~65 agent/MCP tool wrappers -- never passes it, so their
    behavior is unchanged. `confidence` is always `NULL` -- deterministic
    calculations don't carry a confidence signal (CONTEXT.md). `value` is
    stored as-is via `Json`, so it accepts either a bare JSON scalar (a
    `calculate_vswr`-style tool returning a plain float) or a JSON object
    (a `calculate_noise_figure`/`analyze_touchstone_file`-style tool
    returning a dict) -- whatever the tool's own return payload is.

    Same transaction-boundary contract as `create_design`: takes an
    already-open connection and never commits it itself.
    """
    resolved_provenance = provenance if provenance is not None else provenance_for_tool(tool_name)
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
                resolved_provenance,
                tool_name,
                tool_version,
            ),
        )
        row = cur.fetchone()
        assert row is not None
    return row
