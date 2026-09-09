"""The durable, independent audit trail for approval-gate decisions (issue
#258 ticket 1 of a 5-ticket chain; ADR-0028's "warn, never block" posture and
its one surviving hard stop; ADR-0014's "never bypasses approval gates").

WHY THIS MODULE EXISTS, AND WHY IT IS SEPARATE FROM A RECEIPT.
`orchestration/approval.py`'s `LoopStepApprovalReceipt` and
`designs/release_approval.py`'s `DesignReleaseApprovalReceipt` are both
HMAC-signed proof that a human approved ONE specific decision -- but both
modules say plainly, in their own docstrings, that the signing key is
generated once per process, kept only in memory, and deliberately does NOT
survive a restart. That is correct and this module does not change it: it
means a stale approval can never resurface after a restart and be misapplied
(issue #258, story #35). It also means that once a process restarts, the
receipt is gone, and nothing in this codebase can answer "who approved (or
refused) what, and when" -- which is exactly the question an auditor asks
after the fact (story #27).

This module is that durable answer. It is a plain, append-only sink: one
function writes a record, one function reads records back. It never verifies
a receipt, never grants or refuses an approval, and never decides anything --
those are still, exclusively, `orchestration/approval.py`'s and
`designs/release_approval.py`'s jobs (ADR-0014: this module is additive,
never a second path through either gate). A later ticket in this same
5-ticket chain wires the two approval-granting call sites to call
`append_audit_record` after they decide; THIS ticket builds only the sink,
and does not modify either gate module (see this module's own module-level
`__all__` -- there is no verification function here at all).

WHAT AN AUDIT RECORD HOLDS -- reusing the existing fingerprint shape, not a
new one. Story #30: the audit record must never be a substitute for the
signed receipt, and neither weakens the other -- the receipt is what the
code checks, this table is what a person checks later. So a record does not
store a receipt's `token` (that is the receipt's own, meaningless once its
signing key is gone) -- it stores exactly the `fingerprint_fields` dict a
human was shown before deciding: `orchestration.design_loop
._decision_fingerprint_fields`'s `{loop_id, iteration, step, content}` for a
loop-step decision, or `designs.release_approval.release_fingerprint_fields`'s
`{design_id, design_key, revision, target}` for a release decision. Neither
shape is reinvented here; both are accepted as opaque, JSON-serializable
dicts. `decision_fingerprint` is the same canonical SHA-256 hash of those
fields that `orchestration/approval.py`'s and `designs/release_approval.py`'s
own (each separately, deliberately duplicated -- see their own docstrings)
`_canonical_fingerprint` helper produces, computed here the identical way, so
a caller holding a still-live receipt can confirm this row is for the same
decision without re-deriving the hash by hand.

`gate` says which of the two approval mechanisms the decision belongs to
(`GATE_LOOP_STEP` or `GATE_DESIGN_RELEASE`) -- the two fingerprint shapes
above are not distinguishable by structure alone (a loop-step decision could
coincidentally have the same keys as some future release-shaped dict), so
the caller states it explicitly rather than this module guessing from shape.
`loop_id` is a convenience column, not a third source of truth: it is lifted
straight out of `fingerprint_fields["loop_id"]` when present (a loop-step
decision always carries one) and left `NULL` otherwise (a release decision
never has one) -- purely so `fetch_audit_records` can filter by it without
every caller writing their own JSONB query.

`outcome` is `OUTCOME_APPROVED` or `OUTCOME_REFUSED` -- never a bare
boolean, and a refusal is written with exactly the same completeness as an
approval (story #29): the same fingerprint_fields, the same approved_by, the
same kind of row, just a different outcome. `approved_by` is the identity of
the human who decided (required, exactly as both approval-granting functions
already require it themselves) -- for a refusal this is who refused it, not
who was asked. `decided_at` is assigned by the database itself
(`now()`, same as every other `created_at`-style column in `db/schema.sql`)
rather than accepted as a caller-supplied argument, so the timestamp in the
audit trail can never be backdated or forward-dated by whatever called this
function.

GENUINELY APPEND-ONLY, NOT BY CONVENTION. This module provides exactly two
public functions, `append_audit_record` (INSERT ... RETURNING) and
`fetch_audit_records` (SELECT). There is no update/delete/remove function
anywhere in this file, exported or not -- `tests/test_approval_audit.py`
holds this at two levels: a structural test enumerating every public,
module-level callable and asserting none of their names could be one, and a
belt-and-braces source-text check that no `UPDATE`/`DELETE` SQL statement
appears anywhere in this file at all. A second, disagreeing audit row for
the same decision is not possible either -- there is nothing to disagree
with, since a decision is only ever approved or refused once by the human
approval surface a later ticket builds; if that ever needs to change, it
needs its own new row, never an edit to this one.

DURABILITY. `append_audit_record` takes an already-open connection and never
commits it itself -- the caller owns the transaction boundary, exactly the
convention `designs/db.py` and `designs/material_properties.py` already
establish. The DURABILITY this module exists for comes from the caller
actually committing (a human-approval surface built in a later ticket will,
same as any other real write); nothing here is durable on its own if a
caller never commits, and nothing here is more or less durable than any
other row in this project's Postgres database.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import psycopg
from psycopg.rows import dict_row

__all__ = [
    "AUDIT_GATES",
    "AUDIT_OUTCOMES",
    "GATE_DESIGN_RELEASE",
    "GATE_LOOP_STEP",
    "OUTCOME_APPROVED",
    "OUTCOME_REFUSED",
    "InvalidAuditRecordError",
    "append_audit_record",
    "fetch_audit_records",
]

# Which approval mechanism a decision belongs to (see this module's
# docstring's "WHAT AN AUDIT RECORD HOLDS" section). Matches
# orchestration/approval.py (loop-step gate) and designs/release_approval.py
# (design-release gate) one-for-one -- not a new taxonomy invented here.
GATE_LOOP_STEP = "loop_step"
GATE_DESIGN_RELEASE = "design_release"
AUDIT_GATES = frozenset({GATE_LOOP_STEP, GATE_DESIGN_RELEASE})

# A decision is one of exactly these two outcomes -- never a bare boolean
# (issue #258, story #27: "who decided, what exact decision content they
# were shown, what they decided, and when").
OUTCOME_APPROVED = "approved"
OUTCOME_REFUSED = "refused"
AUDIT_OUTCOMES = frozenset({OUTCOME_APPROVED, OUTCOME_REFUSED})


class InvalidAuditRecordError(ValueError):
    """Raised by `append_audit_record` when the shape it was handed is
    wrong -- an unknown `gate`, an unknown `outcome`, an empty
    `approved_by`, or a non-dict `fingerprint_fields`. Named and raised the
    same way `designs.material_properties.InvalidMaterialPropertyError` is:
    naming exactly what's wrong, checked before the database is touched."""


def _canonical_fingerprint(fields: dict[str, Any]) -> str:
    """A stable SHA-256 fingerprint of `fields` -- byte-for-byte the same
    algorithm `orchestration/approval.py`'s and `designs/release_approval.py`'s
    own (each module's separately-kept) `_canonical_fingerprint` helper
    already uses, so a hash computed there and a hash computed here agree
    for identical fields. Deliberately reimplemented rather than imported:
    those two helpers are each private to their own module for the same
    reason (per each module's own docstring, the two gates' fingerprinting
    must never be coupled through a shared dependency that a future change
    to one could silently affect the other through)."""
    canonical = json.dumps(fields, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def append_audit_record(
    conn: psycopg.Connection,
    gate: str,
    fingerprint_fields: dict[str, Any],
    approved_by: str,
    outcome: str,
) -> dict[str, Any]:
    """Append one audit record. The ONLY way to write into this table --
    there is no update or delete function anywhere in this module (see this
    module's own docstring's "GENUINELY APPEND-ONLY" section).

    `gate` must be `GATE_LOOP_STEP` or `GATE_DESIGN_RELEASE`.
    `fingerprint_fields` must be the exact dict the human reviewing this
    decision was shown -- the same shape `request_loop_step_approval`/
    `request_design_release_approval` fingerprint their own receipt to, not
    a summary or paraphrase of it. `approved_by` is the identity of the
    human who decided (required, exactly as both approval-granting
    functions already require). `outcome` must be `OUTCOME_APPROVED` or
    `OUTCOME_REFUSED`.

    Raises `InvalidAuditRecordError` naming exactly which field is wrong,
    checked before the database is touched -- never coerces or guesses a
    fixed-up value. Takes an already-open connection and never commits it
    itself; the caller owns the transaction boundary (same convention as
    `designs/db.py` and `designs/material_properties.py`).
    """
    if gate not in AUDIT_GATES:
        raise InvalidAuditRecordError(f"gate must be one of {sorted(AUDIT_GATES)}, got {gate!r}")

    if not isinstance(fingerprint_fields, dict):
        raise InvalidAuditRecordError(
            f"fingerprint_fields must be a dict -- the exact decision content a "
            f"human was shown before deciding -- got {type(fingerprint_fields).__name__}"
        )

    if not isinstance(approved_by, str) or not approved_by.strip():
        raise InvalidAuditRecordError(
            f"approved_by (the identity of the deciding human) is required for an "
            f"auditable record, got {approved_by!r}"
        )

    if outcome not in AUDIT_OUTCOMES:
        raise InvalidAuditRecordError(
            f"outcome must be one of {sorted(AUDIT_OUTCOMES)}, got {outcome!r}"
        )

    loop_id = fingerprint_fields.get("loop_id")
    decision_fingerprint = _canonical_fingerprint(fingerprint_fields)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO approval_audit_log
                (gate, loop_id, fingerprint_fields, decision_fingerprint, approved_by, outcome)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                gate,
                loop_id,
                psycopg.types.json.Json(fingerprint_fields),
                decision_fingerprint,
                approved_by,
                outcome,
            ),
        )
        row = cur.fetchone()
        assert row is not None
    return row


def fetch_audit_records(
    conn: psycopg.Connection,
    loop_id: str | None = None,
) -> list[dict[str, Any]]:
    """Read audit records back, oldest first (insertion order).

    `loop_id=None` (the default) returns every record in the table --
    every loop-step decision AND every design-release decision, since a
    release decision's fingerprint carries no loop_id to filter on in the
    first place. Pass a specific `loop_id` to see only that design loop's
    decisions -- a release-gate record never matches, since its `loop_id`
    column is always `NULL` (see this module's docstring).

    This function only ever SELECTs -- the read half of this module's
    append/read split, matching `designs/material_properties.py`'s
    `fetch_material_property_entries`.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        if loop_id is None:
            cur.execute("SELECT * FROM approval_audit_log ORDER BY id")
        else:
            cur.execute(
                "SELECT * FROM approval_audit_log WHERE loop_id = %s ORDER BY id",
                (loop_id,),
            )
        return cur.fetchall()
