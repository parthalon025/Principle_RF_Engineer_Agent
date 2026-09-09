"""Element/Coding-Alphabet library (issue #256; ADR-0027; CONTEXT.md:
Element/Coding-Alphabet library).

ADR-0027 decided the library's shape in full -- the five-part key
`(element family, symbol, band, incidence-angle range, process)`, why
`process` is a referenced object rather than four more key fields, why
entries never expire, and why provenance is fixed at `MEASURED` rather than
a caller's choice -- but nothing was ever built. This module is that
implementation, in the same two-layer pure/I-O shape
`designs/material_properties.py` already establishes for the sibling
Material-property library (see that module's own docstring for the shape
this one deliberately mirrors).

THIS FIRST SLICE IS THE PROCESS RECORD ONLY (issue #256's ticket 1). A
**Process record** is ADR-0027 point 4's "stated box" -- machine, ink and
grade, substrate stack, pass count, achieved film thickness, and cure
schedule -- that a symbol-alphabet entry (a "letter") must reference before
it can be admitted as a measurement rather than an assumption: "an entry
carrying no process reference is an assumption, not a measurement." The
symbol-alphabet entry itself (`add_symbol_entry`/`lookup_symbol_entries`/
`resolve_symbol_entry` and their I/O counterparts), which references a
Process record by id, is separate, dependent work (ticket 2) and is not
built here.

WHY ink AND grade ARE TWO FIELDS, NOT ONE. ADR-0027 point 4 lists a Process
record's contents as "machine, ink and grade, substrate stack, pass count,
achieved film thickness, and cure schedule" -- two independently stated
facts, not one string. Issue #256's own field list glosses this the same
way: "ink (name/grade)". Splitting them into `ink`/`ink_grade` (rather than
one free-text field a caller has to format consistently) keeps each fact
independently queryable -- "every record on ACI SC1502 carbon, any grade"
is a plain column match, not a substring search.

WHY THERE IS NO UNIQUENESS CONSTRAINT ACROSS A PROCESS RECORD'S FIELDS.
Issue #256's Solution section is explicit: "two runs on the same nominal
settings are still two distinct, independently-referenceable records, since
'achieved' film thickness in particular can vary run to run." Two Process
records with identical `machine`/`ink`/`ink_grade`/`substrate_stack`/
`cure_schedule` and even identical `pass_count` are not merged or rejected
as duplicates -- each print run gets its own record, the same
never-collapse discipline `material_properties`'s per-citation rows already
apply to a disagreeing measurement.

WHY A PROCESS RECORD HAS NO PROVENANCE FIELD OF ITS OWN. Provenance
(`MEASURED`, `knowledge.provenance.MEASURED`) is a property of a
symbol-alphabet *entry* -- the claim that a letter's geometry and response
were printed and measured under a stated process -- not of the process box
itself. ADR-0027's own field list for the Process record (point 4) names no
provenance column, and issue #256's Implementation Decisions section
likewise lists provenance only on the (not-yet-built) symbol-alphabet-entry
table. Adding one here would invent a field ADR-0027 never asked for.

MODULE SHAPE. The same pure/I-O seam `designs/material_properties.py`
already establishes:

  - A pure, DB-free function (`add_process_record`) -- all of this ticket's
    actual validation logic, exhaustively unit-tested in
    `tests/test_element_alphabet.py` with no database needed.
  - Thin I/O wrappers (`insert_process_record`, `fetch_process_record`) --
    read/write the `process_records` table (`db/schema.sql`) directly with
    their own small amount of raw SQL, mirroring `designs/db.py`'s no-ORM
    style: functions take an already-open connection and never commit it
    themselves -- the caller owns the transaction boundary. Not unit-tested
    here, for the same documented reason `designs/material_properties.py`'s
    own I/O wrappers aren't: there is no live DATABASE_URL in this sandbox.
    They are thin glue over `add_process_record`, which carries all the
    real logic and is fully covered.
"""

from __future__ import annotations

import math
from typing import Any

import psycopg
from psycopg.rows import dict_row


class InvalidSymbolAlphabetEntryError(ValueError):
    """Raised by `add_process_record` (and, once ticket 2 lands, by the
    symbol-alphabet-entry functions built alongside it) when the shape it
    was handed is wrong -- an empty `machine`/`ink`/`ink_grade`/
    `substrate_stack`/`cure_schedule`, or a non-finite or negative
    `pass_count`/`achieved_film_thickness_m`. Named and raised the same way
    `designs.material_properties.InvalidMaterialPropertyError` and
    `geometry.unit_cell.SymbolNotFoundError` already are in this codebase --
    naming exactly what's wrong rather than a bare `TypeError`/`KeyError`."""


def _require_nonempty_string(field_name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidSymbolAlphabetEntryError(
            f"{field_name} must be a non-empty string, got {value!r}"
        )
    return value


def _require_finite_number(field_name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidSymbolAlphabetEntryError(f"{field_name} must be a real number, got {value!r}")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise InvalidSymbolAlphabetEntryError(f"{field_name} must be finite, got {value!r}")
    return numeric


def _require_nonnegative_finite_number(field_name: str, value: Any) -> float:
    numeric = _require_finite_number(field_name, value)
    if numeric < 0:
        raise InvalidSymbolAlphabetEntryError(f"{field_name} must be >= 0, got {value!r}")
    return numeric


def add_process_record(
    machine: str,
    ink: str,
    ink_grade: str,
    substrate_stack: str,
    pass_count: float,
    achieved_film_thickness_m: float,
    cure_schedule: str,
) -> dict[str, Any]:
    """Validate and build one Process record (ADR-0027 point 4).

    `machine`, `ink`, `ink_grade`, `substrate_stack`, and `cure_schedule`
    must all be non-empty strings -- ADR-0027's "stated box" is a set of
    concrete facts about how a letter was made, never a blank left for a
    caller to fill in later. `pass_count` and `achieved_film_thickness_m`
    must be real, finite numbers `>= 0` -- a negative pass count or film
    thickness cannot describe anything a printer actually did.

    Raises `InvalidSymbolAlphabetEntryError` naming exactly which field is
    wrong -- never coerces or guesses a fixed-up value, the same discipline
    `designs.material_properties.add_entry` already applies to its own
    fields.
    """
    resolved_machine = _require_nonempty_string("machine", machine)
    resolved_ink = _require_nonempty_string("ink", ink)
    resolved_ink_grade = _require_nonempty_string("ink_grade", ink_grade)
    resolved_substrate_stack = _require_nonempty_string("substrate_stack", substrate_stack)
    resolved_cure_schedule = _require_nonempty_string("cure_schedule", cure_schedule)

    resolved_pass_count = _require_nonnegative_finite_number("pass_count", pass_count)
    resolved_thickness = _require_nonnegative_finite_number(
        "achieved_film_thickness_m", achieved_film_thickness_m
    )

    return {
        "machine": resolved_machine,
        "ink": resolved_ink,
        "ink_grade": resolved_ink_grade,
        "substrate_stack": resolved_substrate_stack,
        "pass_count": resolved_pass_count,
        "achieved_film_thickness_m": resolved_thickness,
        "cure_schedule": resolved_cure_schedule,
    }


# ---------------------------------------------------------------------------
# I/O layer: persistent storage in `process_records` (db/schema.sql). Same
# connection-lifecycle discipline as designs/db.py and
# designs/material_properties.py's own I/O wrappers: functions take an
# already-open connection and never commit it themselves -- the caller owns
# the transaction boundary. Not unit-tested here -- no live DATABASE_URL in
# this sandbox (see this module's docstring's "MODULE SHAPE" section); each
# wrapper is thin glue over `add_process_record` above, which carries all
# the real logic and is fully covered.
# ---------------------------------------------------------------------------


def insert_process_record(
    conn: psycopg.Connection,
    machine: str,
    ink: str,
    ink_grade: str,
    substrate_stack: str,
    pass_count: float,
    achieved_film_thickness_m: float,
    cure_schedule: str,
) -> dict[str, Any]:
    """Validate (`add_process_record`) and insert one Process record.

    Every call inserts a new row -- there is no update/upsert path here,
    deliberately: issue #256's Solution section is explicit that two runs on
    nominally identical settings are still two distinct,
    independently-referenceable Process records (see this module's
    docstring's "WHY THERE IS NO UNIQUENESS CONSTRAINT" section)."""
    record = add_process_record(
        machine=machine,
        ink=ink,
        ink_grade=ink_grade,
        substrate_stack=substrate_stack,
        pass_count=pass_count,
        achieved_film_thickness_m=achieved_film_thickness_m,
        cure_schedule=cure_schedule,
    )
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO process_records
                (machine, ink, ink_grade, substrate_stack, pass_count,
                 achieved_film_thickness_m, cure_schedule)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                record["machine"],
                record["ink"],
                record["ink_grade"],
                record["substrate_stack"],
                record["pass_count"],
                record["achieved_film_thickness_m"],
                record["cure_schedule"],
            ),
        )
        row = cur.fetchone()
        assert row is not None
    return row


def fetch_process_record(conn: psycopg.Connection, process_record_id: int) -> dict[str, Any] | None:
    """Return the stored Process record with this id, or `None` if no row
    matches -- mirrors `designs.material_properties.fetch_family_bracket`'s
    "None means not found" convention. This is the shape ticket 2's
    symbol-alphabet-entry lookups (and the schema's own
    `REFERENCES process_records(id)` foreign key) will resolve a process
    reference through."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM process_records WHERE id = %s", (process_record_id,))
        return cur.fetchone()
