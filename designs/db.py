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
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from db.pool import checkout_connection
from designs.lifecycle import (
    TERMINAL_STATUSES,
    check_transition,
    coerce_status,
    transition_requires_release_approval,
)
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
    """Check a connection out of the process-wide pool (`db.pool`, issue
    #406), configured from `DATABASE_URL` the first time one is asked for.

    Same call shape as the direct `psycopg.connect(...)` this replaced --
    `conn = get_connection()` ... `conn.close()` -- but `close()` is now a
    return to the pool rather than a disconnect, so the next call reuses
    this connection's backend instead of opening another against
    Postgres's fixed ceiling. Every connection handed out also arrives
    carrying a bounded `lock_timeout` and `statement_timeout`, so a caller
    blocked on a row another agent is editing gets a clear, prompt error
    instead of waiting indefinitely. See `db/pool.py` for the reasoning and
    for the two things not to do with a pooled connection.
    """
    return checkout_connection()


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
    conn: psycopg.Connection, component_refs: list[tuple[str, int]]
) -> list[dict[str, Any]]:
    """Return `{"block": ..., "component_id": ...}` for every `component_id`
    in `component_refs` that has no matching `components` row, in the order
    `component_refs` lists them. Empty list -> every reference resolves
    (including when there are none at all).

    `component_refs` is the caller's own already-computed
    `designs.validation._iter_component_refs(architecture)` walk -- a list
    of `(block, component_id)` pairs -- passed in rather than an
    `architecture` dict this function would have to walk itself, so
    `create_design` can walk `architecture` exactly once and reuse the
    result both for this existence check and for its own
    `design_component_refs` insert.
    """
    if not component_refs:
        return []
    component_ids = [component_id for _, component_id in component_refs]

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
        for block, component_id in component_refs
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
    design_family: str | None = None,
    design_family_canonical: str | None = None,
    considered_and_dropped: list[Any] | None = None,
    capability_warnings: list[Any] | None = None,
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

    `design_family` (issue #167; CONTEXT.md's "Design family",
    docs/adr/0018) is optional/nullable -- only a caller recording an
    ARCHITECTURE or REDESIGN_DECISION design-loop decision
    (`orchestration/tooling.py`'s `_flush_target_for`) passes one; every
    other `record_decision` call (a plain design-record entry with no
    design-loop behind it) leaves it `None`, same as today. This function
    does not validate the value against a known-family list -- that
    belongs to the still-open design family registry (docs/adr/0018), not
    this write path.

    `design_family_canonical` (issue #408; ADR-0037) is `design_family`'s
    companion, never derived from it here -- the caller (orchestration/
    tooling.py) already has the registry's `canonical_name` in hand from
    `orchestration/design_loop.py`'s ARCHITECTURE step and passes it
    through verbatim, same optional/nullable shape as `design_family`
    immediately above.

    `considered_and_dropped` (issue #322; ADR-0025's Considered-and-dropped
    ledger) is optional, defaulting to `[]` -- same "only a design-loop
    ARCHITECTURE/REDESIGN_DECISION call ever states one" shape as
    `design_family` immediately above. The `reason_kind="capability-verdict"`
    narrowing (issue #322) is enforced upstream, by
    `orchestration.design_loop`'s step validation, before a decision ever
    reaches this write path -- this is a storage layer, not a second place
    to re-check the rule.

    ISSUE #396: each entry is inserted as its own row in
    `considered_and_dropped_entries` (FK'd to the `decision_records` row
    just inserted, on the SAME connection/transaction -- no commit happens
    in between), not written into `decision_records.considered_and_dropped`
    any more -- that column is left at its own schema default (`'[]'::jsonb`)
    from here on. The row this function returns, and every entry
    `read_design` reports for this decision, are reconstructed from that
    table (`_read_considered_and_dropped_entries`) rather than read back off
    the column, so both stay byte-for-byte identical to what a caller
    actually passed in here.

    `capability_warnings` (issue #324; ADR-0025's 2026-09-09 correction;
    CONTEXT.md's "Capability warning") is optional, defaulting to `[]` --
    wholly separate from `considered_and_dropped` above (a design candidate
    carrying a Capability warning stays `kept`; it is never one of that
    ledger's entries). Same "only a design-loop ARCHITECTURE/
    REDESIGN_DECISION call ever states one" shape as `considered_and_dropped`,
    and stored the same way (issue #397; parent #393): each entry becomes its
    own row in `capability_warning_entries`, FK'd to this `decision_records`
    row, in the SAME transaction as the insert below -- not a JSON blob on
    the row itself. `decision_records.capability_warnings` (the column) is
    no longer written with real content here; it is left at its schema
    default (`[]`) and is no longer authoritative for this data (issue #393:
    "nothing should read them as authoritative after this ships") --
    `read_design` reconstructs the equivalent list by reading the child
    table instead, so a caller of this function or of `read_design` sees the
    exact same shape as before. The shape check (issue #324) is enforced
    upstream, by `orchestration.design_loop`'s step validation -- this
    function stores each entry verbatim, just in a different place.
    """
    existing = find_decision_by_record_key(conn, record_key)
    if existing is not None:
        raise RecordKeyCollisionError(record_key, existing)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO decision_records
                (design_id, record_key, decision, alternatives, rationale,
                 evidence, design_family, design_family_canonical,
                 approval_required, approval_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                design_id,
                record_key,
                decision,
                Json(alternatives),
                rationale,
                Json(evidence),
                design_family,
                design_family_canonical,
                approval_required,
                "PENDING",
            ),
        )
        row = cur.fetchone()
        assert row is not None

        if capability_warnings:
            cur.executemany(
                """
                INSERT INTO capability_warning_entries
                    (decision_record_id, family, capability_kind, capability_property,
                     value, comparator, unit, reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        row["id"],
                        entry["family"],
                        entry["capability_kind"],
                        entry["capability_property"],
                        entry["value"],
                        entry["comparator"],
                        entry["unit"],
                        entry["reason"],
                    )
                    for entry in capability_warnings
                ],
            )

    # The RETURNING * above reflects the (now-inert) schema default for this
    # column, not what was actually recorded -- fill in what this call
    # actually just wrote, so a caller of record_decision itself (not just
    # of read_design) sees the real entries without a second round trip.
    row["capability_warnings"] = copy.deepcopy(capability_warnings) if capability_warnings else []

    _insert_considered_and_dropped_entries(conn, row["id"], considered_and_dropped or [])
    row["considered_and_dropped"] = _read_considered_and_dropped_entries(conn, [row["id"]]).get(
        row["id"], []
    )

    return row


def _insert_considered_and_dropped_entries(
    conn: psycopg.Connection, decision_record_id: int, entries: list[dict[str, Any]]
) -> None:
    """Insert one `considered_and_dropped_entries` row per entry in
    `entries`, preserving each entry's position in the original list as
    `entry_index` -- the write half of `_read_considered_and_dropped_entries`
    below (issue #396). A no-op for an empty list, so a caller that never
    stated a ledger causes no query at all.

    Every entry here has already passed
    `orchestration.design_loop._validate_considered_and_dropped` (this
    module's own long-standing contract: `record_decision` stores what it is
    given, it does not re-validate the shape) -- `family`/`verdict`/
    `reason`/`reason_kind` are always present; `requirement_id`/
    `validity_box_property`/`theta_max_deg` are read with `.get(...)`
    (`None` when absent) since only a `reason_kind="capability-verdict"`
    entry ever states them.
    """
    if not entries:
        return
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO considered_and_dropped_entries
                (decision_record_id, entry_index, family, verdict, reason, reason_kind,
                 requirement_id, validity_box_property, theta_max_deg)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    decision_record_id,
                    index,
                    entry["family"],
                    entry["verdict"],
                    entry["reason"],
                    entry["reason_kind"],
                    entry.get("requirement_id"),
                    entry.get("validity_box_property"),
                    entry.get("theta_max_deg"),
                )
                for index, entry in enumerate(entries)
            ],
        )


# The considered_and_dropped_entries columns every ledger-entry row carries,
# beyond decision_record_id/entry_index -- named once here (issue #396 code
# review) so `_read_considered_and_dropped_entries`'s grouped SELECT and
# `find_capability_verdict_entries`'s joined SELECT build their column list
# from the same tuple instead of each spelling it out by hand. The two
# queries still differ in shape (grouped by decision_record_id vs. joined
# through decision_records) -- only the column list itself is shared, and it
# is the same list `_entry_dict_from_row` below reads back off a row.
_ENTRY_COLUMNS = (
    "family",
    "verdict",
    "reason",
    "reason_kind",
    "requirement_id",
    "validity_box_property",
    "theta_max_deg",
)


def _entry_dict_from_row(row: dict[str, Any]) -> dict[str, Any]:
    """Build one considered_and_dropped ledger entry dict from a
    `considered_and_dropped_entries` row (or an equivalent dict carrying the
    same keys, e.g. `find_capability_verdict_entries`'s joined query) --
    shared by every reader of this table (issue #396) so they all
    reconstruct an entry the exact same way: `requirement_id`/
    `validity_box_property`/`theta_max_deg` are omitted from the returned
    dict entirely when NULL, never carried as an explicit `None`, so a plain
    human-decision/engineering-judgment entry (which never states them)
    round-trips byte-for-byte identical to what `record_decision` was
    originally called with."""
    entry: dict[str, Any] = {
        "family": row["family"],
        "verdict": row["verdict"],
        "reason": row["reason"],
        "reason_kind": row["reason_kind"],
    }
    for optional_field in ("requirement_id", "validity_box_property", "theta_max_deg"):
        if row.get(optional_field) is not None:
            entry[optional_field] = row[optional_field]
    return entry


def _read_considered_and_dropped_entries(
    conn: psycopg.Connection, decision_record_ids: list[int]
) -> dict[int, list[dict[str, Any]]]:
    """Reconstruct the considered_and_dropped ledger for every id in
    `decision_record_ids` from `considered_and_dropped_entries` (issue
    #396), in original `entry_index` order -- one query regardless of how
    many ids are asked for, the same "IN-list, not N+1" shape
    `read_engineering_results_for_scoring` already established. Used by
    both `record_decision` (a single freshly-inserted id) and `read_design`
    (every decision_records row a design has).

    Returns `{decision_record_id: [entry, ...]}`; an id with no entries
    recorded is simply absent from the dict (the caller already defaults a
    miss to `[]`, matching `read_engineering_results_for_scoring`'s own
    "empty list on a miss" contract at the call site rather than here).
    `decision_record_ids=[]` returns `{}` without querying at all.
    """
    grouped: dict[int, list[dict[str, Any]]] = {}
    if not decision_record_ids:
        return grouped

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT decision_record_id, {", ".join(_ENTRY_COLUMNS)}
            FROM considered_and_dropped_entries
            WHERE decision_record_id = ANY(%s)
            ORDER BY decision_record_id, entry_index
            """,
            (list(decision_record_ids),),
        )
        rows = cur.fetchall()

    for row in rows:
        grouped.setdefault(row["decision_record_id"], []).append(_entry_dict_from_row(row))
    return grouped


def find_capability_verdict_entries(
    conn: psycopg.Connection, design_id: int | None = None
) -> list[dict[str, Any]]:
    """Every `reason_kind="capability-verdict"` `considered_and_dropped_
    entries` row, joined through `decision_records` (issue #396).

    `design_id=None` (the default) is ADR-0025's own named payoff query --
    CONTEXT.md's Considered-and-dropped ledger entry: "every entry dropped
    as a capability-verdict is exactly what relaxing that requirement
    unlocks" -- across EVERY design this database holds, not just one.
    Passing `design_id` scopes it to a single design: the exact query
    `orchestration.tooling.reevaluate_capability_verdicts` runs (issue #396
    acceptance criterion 3), instead of looping over `read_design`'s
    aggregated JSON in Python.

    Returns one dict per matching row, `{"design_id": ..., "record_key":
    ..., "entry": {...}}` -- `entry` is the same ledger-entry shape
    `_read_considered_and_dropped_entries` reconstructs, ready to hand
    straight to `orchestration.design_loop.capability_verdict_holds`
    unchanged. Ordered by `design_id`, then `decision_records.id`, then
    `entry_index` -- the same encounter order `read_design`'s own
    `decision_records ORDER BY id` / entries `ORDER BY entry_index`
    already establishes.
    """
    cde_columns = ", ".join(f"cde.{column}" for column in _ENTRY_COLUMNS)
    query = f"""
        SELECT dr.design_id, dr.record_key, {cde_columns}
        FROM considered_and_dropped_entries cde
        JOIN decision_records dr ON dr.id = cde.decision_record_id
        WHERE cde.reason_kind = 'capability-verdict'
    """
    params: tuple[Any, ...] = ()
    if design_id is not None:
        query += " AND dr.design_id = %s"
        params = (design_id,)
    query += " ORDER BY dr.design_id, dr.id, cde.entry_index"

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    return [
        {
            "design_id": row["design_id"],
            "record_key": row["record_key"],
            "entry": _entry_dict_from_row(row),
        }
        for row in rows
    ]


class DesignKeyRevisionCollisionError(Exception):
    """Raised by `create_design` when `(design_key, revision)` is already in
    use. Carries the existing row so the caller can point at it instead of
    crashing on the database's own `UNIQUE(design_key, revision)` constraint
    -- the same dedup-and-point-back shape as `record_decision`'s
    `RecordKeyCollisionError` and `knowledge.db.insert_document`'s
    `DuplicateDocumentError`. A *different* `revision` under an
    already-used `design_key` is not a collision -- CONTEXT.md's own rule
    that a released design gets a new revision depends on that pair, not
    `design_key` alone, being the identity key."""

    def __init__(self, design_key: str, revision: str, existing: dict[str, Any]):
        self.design_key = design_key
        self.revision = revision
        self.existing = existing
        super().__init__(
            f"design_key {design_key!r} revision {revision!r} already in use (id={existing['id']})"
        )


def find_design_by_key_and_revision(
    conn: psycopg.Connection, design_key: str, revision: str
) -> dict[str, Any] | None:
    """Return the `designs` row for this exact `(design_key, revision)`
    pair, if any -- that pair is unique (`db/schema.sql`), so at most one
    row can ever match."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM designs WHERE design_key = %s AND revision = %s",
            (design_key, revision),
        )
        return cur.fetchone()


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

    - `(design_key, revision)` is globally unique. Reusing an exact pair
      already in use raises `DesignKeyRevisionCollisionError` carrying the
      existing row -- never silently overwritten, never a raw database
      exception -- mirroring `record_decision`'s `record_key` handling. A
      different `revision` under the same `design_key` is a different,
      independent row, not a collision.
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
    - Every `(block, component_id)` pair the same walk found (issue
      #395/#392) is also written to `design_component_refs` -- the real,
      database-enforced link a caller uses via
      `find_designs_referencing_component` to ask "which designs use
      component X", and that Postgres itself uses to refuse deleting a
      `components` row a live design still references
      (`db/schema.sql`'s `component_id` FK, default `RESTRICT`).
      `architecture` is walked via `_iter_component_refs` exactly once,
      up front; that one list feeds both `_find_dangling_component_refs`'s
      existence check above and this insert -- no second walk of
      `architecture` to re-derive the same `(block, component_id)` pairs.
      `architecture={}` (every design-loop-created design today) writes no
      rows here, same as it creates no `verification_items` rows when
      `requirements={}`.
    - The `designs` insert, its `verification_items` auto-creation, and its
      `design_component_refs` auto-creation are all statements on the same
      connection with no commit between them, so they share whatever
      transaction the caller is already in -- never left half-done.
      (Deliberately *not* wrapped in its own nested
      `with conn.transaction():`: psycopg treats that as a genuine
      top-level transaction -- auto-committing on a clean exit -- unless
      some earlier statement on this connection already opened one, which
      isn't guaranteed here the way it is in `knowledge.db.insert_document`
      -- e.g. `architecture` with no `component_id` refs never queries
      `components` at all. Plain sequential statements avoid depending on
      that invariant and match this module's own contract: the caller
      owns the transaction boundary, not `create_design`. For the same
      reason, the `(design_key, revision)` collision check below is a
      pre-check only, not also a caught `UniqueViolation` around the
      INSERT -- catching it here would leave the caller's transaction
      poisoned with no savepoint to recover to.)
    """
    existing = find_design_by_key_and_revision(conn, design_key, revision)
    if existing is not None:
        raise DesignKeyRevisionCollisionError(design_key, revision, existing)

    validate_requirements(requirements)

    component_refs = _iter_component_refs(architecture)
    offending = _find_dangling_component_refs(conn, component_refs)
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

        if component_refs:
            cur.executemany(
                """
                INSERT INTO design_component_refs (design_id, component_id, block)
                VALUES (%s, %s, %s)
                """,
                [(design_row["id"], component_id, block) for block, component_id in component_refs],
            )

    return design_row


def find_designs_referencing_component(
    conn: psycopg.Connection, component_id: int
) -> list[dict[str, Any]]:
    """Return `{"id": ..., "design_key": ..., "revision": ..., "block": ...}`
    for every `design_component_refs` row naming this `component_id` (issue
    #395/#392) -- the "which designs use component X" lookup `db/schema.sql`'s
    `design_component_refs_component_id_idx` exists to make a fast, indexed
    query instead of a full-table scan of every design's `architecture`
    JSON. Ordered by design id then block, so a component referenced from
    several blocks of the same design, or from several different designs,
    comes back in a stable order. Returns `[]` for a `component_id`
    referenced by no design (including one that doesn't exist) -- never
    raises, mirroring this module's other plain-read functions
    (`read_engineering_results_for_scoring`).

    Read-only counterpart to `create_design`'s write into the same table --
    this function only ever SELECTs.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT d.id, d.design_key, d.revision, dcr.block
            FROM design_component_refs dcr
            JOIN designs d ON d.id = dcr.design_id
            WHERE dcr.component_id = %s
            ORDER BY d.id, dcr.block
            """,
            (component_id,),
        )
        return cur.fetchall()


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

    Each decision record's `capability_warnings` (issue #397) is
    reconstructed from `capability_warning_entries` rather than read
    straight off the `decision_records` column -- see that table's own
    schema comment and `record_decision`'s docstring for why. The
    reconstruction itself is delegated to `read_capability_warning_entries`
    below (this function's other direct-table caller is
    `orchestration.tooling.reevaluate_capability_warnings`) rather than a
    second inline query against the same table, so a future column change
    to `capability_warning_entries` has one query to update, not two.
    Everything else about this function's output is unchanged.
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
            "design_family, design_family_canonical, "
            "capability_warnings, approval_required, approval_status, created_at "
            "FROM decision_records WHERE design_id = %s ORDER BY id",
            (design_id,),
        )
        decision_records = cur.fetchall()

        # Issue #397: `decision_records.capability_warnings` (selected above)
        # is no longer written with real content by `record_decision` --
        # replace it here with the equivalent list read back from
        # `capability_warning_entries`, so this function's OUTPUT shape is
        # unchanged even though the underlying storage moved to its own
        # table. Reuses `read_capability_warning_entries` below rather than
        # a second inline query against the same table -- its flat,
        # `record_key`-tagged rows are grouped back onto each decision
        # record here by that same `record_key` (every `decision_records`
        # row already carries one) instead of by id, and `record_key` is
        # dropped per entry since a decision record's own
        # `capability_warnings` list has never carried its parent's key
        # redundantly. Skipped entirely when there are no decision_records
        # rows for this design -- `capability_warning_entries` is FK'd to
        # `decision_records`, so there could be no entries either.
        capability_warnings_by_record_key: dict[str, list[dict[str, Any]]] = {}
        if decision_records:
            for entry in read_capability_warning_entries(conn, design_id) or []:
                entry = dict(entry)
                record_key = entry.pop("record_key")
                capability_warnings_by_record_key.setdefault(record_key, []).append(entry)
        for row in decision_records:
            row["capability_warnings"] = capability_warnings_by_record_key.get(
                row["record_key"], []
            )

        cur.execute(
            "SELECT id, requirement_id, requirement, method, expected, actual, status, "
            "evidence_uri, notes "
            "FROM verification_items WHERE design_id = %s ORDER BY id",
            (design_id,),
        )
        verification_items = cur.fetchall()

    # Issue #396: considered_and_dropped is no longer a column on the
    # decision_records row itself -- reconstructed here, one query for every
    # decision_records row this design has (not N+1), from
    # considered_and_dropped_entries instead.
    entries_by_decision_record_id = _read_considered_and_dropped_entries(
        conn, [row["id"] for row in decision_records]
    )
    for row in decision_records:
        row["considered_and_dropped"] = entries_by_decision_record_id.get(row["id"], [])

    return {
        "design_id": design_row["id"],
        "design_key": design_row["design_key"],
        "name": design_row["name"],
        "revision": design_row["revision"],
        "status": design_row["status"],
        "requirements": design_row["requirements"],
        "architecture": architecture,
        "supersedes_design_id": design_row["supersedes_design_id"],
        "engineering_results": [_serialize_row(r) for r in engineering_results],
        "decision_records": [_serialize_row(r) for r in decision_records],
        "verification_items": verification_items,
    }


def read_capability_warning_entries(
    conn: psycopg.Connection, design_id: int
) -> list[dict[str, Any]] | None:
    """Return every persisted `capability_warning_entries` row for
    `design_id`, joined to its parent `decision_records` row for
    `record_key` -- the direct-table read `orchestration.tooling.
    reevaluate_capability_warnings` (issue #397) queries, replacing that
    function's old approach of calling `read_design` and looping over each
    decision record's aggregated (JSON) `capability_warnings` list in
    Python. `read_design` above is this function's other caller: it groups
    these same rows back onto each decision record by `record_key`, so the
    one query here is the only place either caller's SQL touches
    `capability_warning_entries`.

    Returns `None` if no `designs` row matches `design_id` at all -- mirrors
    `read_design`'s own not-found signal, so a caller (`reevaluate_
    capability_warnings`) can distinguish "this design doesn't exist" from
    "this design exists but has no capability_warnings entries" (`[]`,
    e.g. no decision_records yet, or none of them carry any). Checked
    directly against `designs` rather than inferred from an empty join
    result, since the latter cannot tell those two cases apart.

    One dict per entry -- `record_key`, `family`, `capability_kind`,
    `capability_property`, `value`, `comparator`, `unit`, `reason` -- the
    same shape a `capability_warnings` entry has always had, ordered by
    entry id (write order, matching the order the old JSON array held them
    in). Every field `orchestration.design_loop.capability_warning_holds`
    reads (`capability_kind`/`capability_property`/`comparator`/`value`) is
    present, so a caller can pass a returned dict straight into that
    function unchanged.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM designs WHERE id = %s", (design_id,))
        if cur.fetchone() is None:
            return None

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT dr.record_key, cwe.family, cwe.capability_kind, cwe.capability_property,
                   cwe.value, cwe.comparator, cwe.unit, cwe.reason
            FROM capability_warning_entries cwe
            JOIN decision_records dr ON dr.id = cwe.decision_record_id
            WHERE dr.design_id = %s
            ORDER BY cwe.id
            """,
            (design_id,),
        )
        return cur.fetchall()


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
    loop's flush, per ADR-0011. Three things it never does: skip the release
    gate, permit entering `RELEASED` out of order, or let a design leave a
    terminal status. It relaxes the order work moves in, never whether
    finished work can be reopened.

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
        # A terminal status is terminal for every caller: `allow_nonsequential`
        # relaxes the ORDER work moves in, not whether finished work can be
        # reopened. Without this a loop flush could walk a RELEASED design back
        # to ANALYSIS, contradicting the terminality the lifecycle promises.
        leaving_terminal = coerce_status(current["status"]) in TERMINAL_STATUSES
        if releasing or leaving_terminal or not allow_nonsequential:
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


def read_engineering_results_for_scoring(
    conn: psycopg.Connection,
    design_id: int,
    tool_names: list[str],
) -> dict[str, list[dict[str, Any]]]:
    """Read-only: every `engineering_results` row recorded for `design_id`
    whose `tool_name` is one of `tool_names`, grouped by `tool_name` and
    ordered `id` ascending (recording order) within each group.

    Built for `orchestration.solver.run_candidate_search`'s optional
    `design_id` parameter (issue #87's cross-run-learning follow-up to
    #95's own user story #21, "a design's score history across
    iterations"): that caller needs, for a small fixed set of step
    tool_names, every value this design has ever recorded for each -- so it
    can find the best-scoring one and seed a NEW search's plateau-window
    baseline from a design's own past results, instead of starting cold
    every call. This function only ever SELECTs -- it is the read half of
    that read/write split, matching every other plain-read function in
    this module (`find_decision_by_record_key`, `read_design`); scoring
    the returned raw values against a target is the caller's job, not
    this one's -- `designs/db.py` computes nothing here, same as
    everywhere else in this module.

    Returns `{tool_name: [{"id": ..., "tool_name": ..., "value": ...,
    "created_at": ...}, ...]}` -- every requested `tool_name` is a key
    even when it has no matching rows (an empty list, not an absent key),
    so a caller iterating `tool_names` never has to guess between "no
    rows yet" and "wasn't asked for". `value` is exactly the JSONB
    payload `record_engineering_result` stored for that row (a step's raw
    result dict, e.g. `{"resonant_frequency_hz": ...}`) -- not a score.
    `tool_names=[]` returns `{}` without querying the database at all.
    """
    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in tool_names}
    if not tool_names:
        return grouped

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, tool_name, value, created_at FROM engineering_results "
            "WHERE design_id = %s AND tool_name = ANY(%s) ORDER BY id",
            (design_id, list(tool_names)),
        )
        rows = cur.fetchall()

    for row in rows:
        grouped[row["tool_name"]].append(_serialize_row(row))
    return grouped


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
