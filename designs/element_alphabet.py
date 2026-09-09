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

TICKET 1 (below, unchanged) is the Process record only. A **Process
record** is ADR-0027 point 4's "stated box" -- machine, ink and grade,
substrate stack, pass count, achieved film thickness, and cure schedule --
that a symbol-alphabet entry (a "letter") must reference before it can be
admitted as a measurement rather than an assumption: "an entry carrying no
process reference is an assumption, not a measurement."

TICKET 2 (this addition) is the symbol-alphabet entry itself --
`add_symbol_entry`/`lookup_symbol_entries`/`resolve_symbol_entry` and their
I/O counterparts (`insert_symbol_entry`/`fetch_symbol_entries`/
`resolve_symbol_entry_from_db`), which reference a Process record by id.

THE FIVE-PART KEY, AS FIELDS. `element_family`/`symbol` name what the
letter is; `frequency_low_hz`/`frequency_high_hz` and
`incidence_angle_low_deg`/`incidence_angle_high_deg` are the band and
incidence-angle range it is valid across -- both stored as ranges, never a
single point, the same "a band, not a point" discipline
`designs/material_properties.py` already applies to frequency (issue #256
user story 14); `process_id` is the Process record reference.

WHY QUERIES TAKE A POINT, EVEN THOUGH THE STORED KEY IS A RANGE. A caller
asking "does a measured letter cover my design's 10 GHz, 15 degrees
incidence, on the current printer" has a point (a design's actual operating
frequency and incidence angle), not a range -- `lookup_symbol_entries`/
`resolve_symbol_entry` therefore take `frequency_hz`/`incidence_angle_deg`
as points and match them against each stored entry's band/range, exactly
mirroring `designs.material_properties.lookup_entries`'s own
frequency-point-against-stored-band matching. `element_family`, `symbol`,
and `process_id` match exactly (no interval semantics apply to any of the
three -- a family/symbol name and a process id are identities, not ranges).

WHY A NON-MATCHING PROCESS RETURNS AN EMPTY LIST/`None`, NEVER A STATUS
FLAG OR AN ERROR. ADR-0027 point 3: "entries never expire; they stop
matching." When the machine or ink changes, nothing about an old entry
becomes invalid -- it simply describes a process that is no longer the one
in use, so a query scoped to the new process id never matches it. This is
achieved structurally, by `process_id` being part of every match test, not
by any separate "is this entry still current" check -- there is no status
column on `symbol_alphabet_entries` for exactly this reason (see
`db/schema.sql`'s own comment on that table).

WHY TWO ENTRIES DIFFERING ONLY BY PROCESS ARE BOTH KEPT, NEVER MERGED.
ADR-0027 point 4's own worked example: "the same outline printed in carbon
and in MXene is two letters, not one letter under two conditions." There is
no uniqueness constraint across the five key fields (`db/schema.sql`), the
same "no UNIQUE constraint" reasoning `process_records` already documents
for itself -- two runs are two distinct, independently-referenceable rows.

WHY GEOMETRY/RESPONSE ARE NOT DEEPLY VALIDATED HERE. `geometry` must match
the primitive-dict shape `geometry/unit_cell.py` already expects (a single
"box"/"polygon" dict, or a list of them) so a fetched entry can be handed
straight into `generate_unit_cell_array`/`generate_coded_unit_cell_array`
with no reshaping (user story 10), and `response` is the characterised
`|Gamma|`/`angle Gamma` vs. frequency curve (a list of
`{frequency_hz, magnitude, phase_deg}` points, user story 13) -- but this
module only requires each be PRESENT (not `None`), the same "round-trip,
don't re-validate a shape another module already owns" boundary issue
#256's own Testing Decisions section draws ("geometry/response fields
round-trip"). Deep validation of primitive-dict correctness belongs to
`geometry/unit_cell.py`'s own functions, which already raise on a malformed
primitive when it's actually consumed; duplicating that check here would
own logic this module has no other reason to know about.

PROVENANCE IS NEVER A CALLER CHOICE. Unlike
`designs.material_properties.add_entry`'s `provenance` parameter,
`add_symbol_entry` takes no `provenance` argument at all -- every entry
this module can build is `knowledge.provenance.MEASURED`, set internally,
because every Element/Coding-Alphabet entry is this program's own bench
measurement by construction (ADR-0027; see that constant's own docstring
for why it differs from the Material-property library's three-tier
choice).

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

  - Pure, DB-free functions (`add_process_record`, `add_symbol_entry`,
    `lookup_symbol_entries`, `resolve_symbol_entry`,
    `reduce_response_at_frequency`) -- all of both tickets' (plus issue
    #267's response-curve-to-scalar reduction) actual validation/lookup
    logic, exhaustively unit-tested in `tests/test_element_alphabet.py`
    with no database needed.
  - Thin I/O wrappers (`insert_process_record`, `fetch_process_record`,
    `insert_symbol_entry`, `fetch_symbol_entries`,
    `resolve_symbol_entry_from_db`) -- read/write the `process_records`/
    `symbol_alphabet_entries` tables (`db/schema.sql`) directly with their
    own small amount of raw SQL, mirroring `designs/db.py`'s no-ORM style:
    functions take an already-open connection and never commit it
    themselves -- the caller owns the transaction boundary. Ticket 1's own
    wrappers were left untested for lack of a live DATABASE_URL in that
    ticket's sandbox; ticket 2 (this addition) DOES have one reachable
    (`postgresql://rf:rf_dev_password@localhost:5432/rfengineer`, per
    `.env.example`), so all five wrappers -- ticket 1's included -- are
    round-trip tested in `tests/test_element_alphabet.py`'s
    `TestSymbolAlphabetEntryDatabaseRoundTrip`, guarded by a connectivity
    probe so the file still collects cleanly if that Postgres is ever
    unreachable again.
"""

from __future__ import annotations

import math
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from knowledge.provenance import MEASURED


class InvalidSymbolAlphabetEntryError(ValueError):
    """Raised by `add_process_record`/`add_symbol_entry` when the shape
    either function was handed is wrong -- for a Process record, an empty
    `machine`/`ink`/`ink_grade`/`substrate_stack`/`cure_schedule`, or a
    non-finite or negative `pass_count`/`achieved_film_thickness_m`; for a
    symbol-alphabet entry, an empty `element_family`/`symbol`, a non-finite
    or inverted frequency band or incidence-angle range, or a missing/
    invalid `process_id` (ADR-0027: "an entry carrying no process
    reference is an assumption, not a measurement"). Named and raised the
    same way `designs.material_properties.InvalidMaterialPropertyError` and
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


def _require_process_id(value: Any) -> int:
    """`process_id` must be a real, positive integer id -- never `None`
    (ADR-0027: "an entry carrying no process reference is an assumption,
    not a measurement," issue #256 user story 4), never a bool (a bool is
    an `int` subclass in Python but was never a row id), and never a
    non-integer value that could not possibly name a `process_records`
    row. This is the pure-function half of "refuse a dangling/missing
    process reference"; the schema's `NOT NULL REFERENCES
    process_records(id)` (`db/schema.sql`) is the other half, catching a
    syntactically valid but nonexistent id at insert time (user story 16)."""
    if value is None:
        raise InvalidSymbolAlphabetEntryError(
            "process_id is required -- an entry carrying no process reference "
            "is an assumption, not a measurement (ADR-0027)"
        )
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidSymbolAlphabetEntryError(f"process_id must be an integer, got {value!r}")
    if value <= 0:
        raise InvalidSymbolAlphabetEntryError(
            f"process_id must be a positive integer, got {value!r}"
        )
    return value


def _require_present(field_name: str, value: Any) -> Any:
    """`geometry`/`response` must be present (not `None`) -- this module
    round-trips both rather than re-validating their internal shape, which
    belongs to `geometry/unit_cell.py` (see this module's own docstring's
    "WHY GEOMETRY/RESPONSE ARE NOT DEEPLY VALIDATED HERE" section)."""
    if value is None:
        raise InvalidSymbolAlphabetEntryError(f"{field_name} is required and must not be None")
    return value


def add_symbol_entry(
    element_family: str,
    symbol: str,
    frequency_low_hz: float,
    frequency_high_hz: float,
    incidence_angle_low_deg: float,
    incidence_angle_high_deg: float,
    process_id: int,
    geometry: dict[str, Any] | list[dict[str, Any]],
    response: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate and build one symbol-alphabet entry -- ADR-0027's five-part
    key `(element family, symbol, band, incidence-angle range, process)`
    plus the geometry and characterised response that key admits.

    `element_family` and `symbol` must be non-empty strings.
    `frequency_low_hz`/`frequency_high_hz` must be finite and `>= 0`, with
    `frequency_high_hz >= frequency_low_hz` (the same "band, not a point"
    discipline `designs.material_properties.add_entry` already applies to
    its own frequency fields). `incidence_angle_low_deg`/
    `incidence_angle_high_deg` must be finite, with
    `incidence_angle_high_deg >= incidence_angle_low_deg` -- no
    non-negativity constraint, since a range spanning both sides of normal
    incidence (e.g. -30 to +30 degrees) is physically legitimate.

    `process_id` must be a real Process record reference -- see
    `_require_process_id`. `geometry` and `response` must both be present
    (see `_require_present`); neither is re-validated beyond that.

    `provenance` is never a parameter: every entry this function builds is
    `knowledge.provenance.MEASURED`, by construction (ADR-0027) -- see this
    module's own docstring.

    Raises `InvalidSymbolAlphabetEntryError` naming exactly which field is
    wrong -- never coerces or guesses a fixed-up value.
    """
    resolved_family = _require_nonempty_string("element_family", element_family)
    resolved_symbol = _require_nonempty_string("symbol", symbol)

    freq_low = _require_nonnegative_finite_number("frequency_low_hz", frequency_low_hz)
    freq_high = _require_nonnegative_finite_number("frequency_high_hz", frequency_high_hz)
    if freq_high < freq_low:
        raise InvalidSymbolAlphabetEntryError(
            f"frequency_high_hz ({freq_high!r}) must be >= frequency_low_hz ({freq_low!r})"
        )

    angle_low = _require_finite_number("incidence_angle_low_deg", incidence_angle_low_deg)
    angle_high = _require_finite_number("incidence_angle_high_deg", incidence_angle_high_deg)
    if angle_high < angle_low:
        raise InvalidSymbolAlphabetEntryError(
            f"incidence_angle_high_deg ({angle_high!r}) must be >= "
            f"incidence_angle_low_deg ({angle_low!r})"
        )

    resolved_process_id = _require_process_id(process_id)
    resolved_geometry = _require_present("geometry", geometry)
    resolved_response = _require_present("response", response)

    return {
        "element_family": resolved_family,
        "symbol": resolved_symbol,
        "frequency_low_hz": freq_low,
        "frequency_high_hz": freq_high,
        "incidence_angle_low_deg": angle_low,
        "incidence_angle_high_deg": angle_high,
        "process_id": resolved_process_id,
        "geometry": resolved_geometry,
        "response": resolved_response,
        "provenance": MEASURED,
    }


def _symbol_entry_matches(
    entry: dict[str, Any],
    element_family: str,
    symbol: str,
    frequency_hz: float,
    incidence_angle_deg: float,
    process_id: int,
) -> bool:
    return (
        entry["element_family"] == element_family
        and entry["symbol"] == symbol
        and entry["frequency_low_hz"] <= frequency_hz <= entry["frequency_high_hz"]
        and entry["incidence_angle_low_deg"]
        <= incidence_angle_deg
        <= entry["incidence_angle_high_deg"]
        and entry["process_id"] == process_id
    )


def lookup_symbol_entries(
    entries: list[dict[str, Any]],
    element_family: str,
    symbol: str,
    frequency_hz: float,
    incidence_angle_deg: float,
    process_id: int,
) -> list[dict[str, Any]]:
    """Return every stored entry matching the full five-part key --
    `element_family`, `symbol`, and `process_id` exactly, with
    `frequency_hz`/`incidence_angle_deg` matched as points against each
    entry's stored band/range (see this module's own docstring's "WHY
    QUERIES TAKE A POINT" section) -- ALL of them, in the order given,
    never merged or reduced to one. `entries` is whatever the caller
    already fetched (in production, `fetch_symbol_entries`'s result; in a
    test, a hand-built list) -- this function itself never touches a
    database, so it composes with either.

    A query against a `process_id` that does not match any stored entry's
    process simply returns an empty list -- no status flag, no exception.
    This is ADR-0027 point 3's "entries never expire; they stop matching"
    model, enforced structurally by `process_id` being part of every match
    test above, not by a separate validity check.
    """
    return [
        e
        for e in entries
        if _symbol_entry_matches(
            e, element_family, symbol, frequency_hz, incidence_angle_deg, process_id
        )
    ]


def resolve_symbol_entry(
    entries: list[dict[str, Any]],
    element_family: str,
    symbol: str,
    frequency_hz: float,
    incidence_angle_deg: float,
    process_id: int,
) -> dict[str, Any] | None:
    """`lookup_symbol_entries`, narrowed to the single entry a caller
    building a coded surface actually needs (`geometry.unit_cell.
    generate_coded_unit_cell_array`'s `symbol_library` argument expects one
    geometry per symbol id, per issue #256 user story 10) -- the first
    match in `entries`' order, or `None` if none match. `None`, never a
    status dict: unlike
    `designs.material_properties.resolve_material_property` (which has a
    Family fallback bracket to fall back to and reports `status="no_data"`
    when even that is absent), this library has no fallback tier to
    distinguish -- ADR-0027's own model is a plain absence, "no status
    flag, just absence" (issue #256's own Testing Decisions section).
    Ambiguity between several simultaneously-matching entries (multiple
    letters printed under the same process with overlapping bands) is not
    resolved here -- picking the best of several candidates is the
    combinatorial optimizer's job (out of scope; ADR-0018's
    `optimizer_class="COMBINATORIAL"`), not this lookup's.
    """
    matches = lookup_symbol_entries(
        entries, element_family, symbol, frequency_hz, incidence_angle_deg, process_id
    )
    return matches[0] if matches else None


def reduce_response_at_frequency(
    response: list[dict[str, Any]],
    frequency_hz: float,
    field_name: str,
) -> float:
    """Reduce one symbol-alphabet entry's characterised `response` curve --
    a list of `{frequency_hz, magnitude, phase_deg}` points, NOT guaranteed
    sorted (a fetched row is whatever order it was inserted/measured in) --
    to the single scalar value of `field_name` at `frequency_hz` (issue
    #267 acceptance criterion 3): the shape `optimization.combinatorial.
    SymbolOption.achieved_value` needs, so a design-loop caller can turn a
    real measured curve into one number per candidate symbol.

    Sorts a COPY of `response` by its own `frequency_hz` field first (never
    mutates the caller's list, never assumes it arrived sorted), then:

      - if `frequency_hz` is at or below the lowest stored point, or at or
        above the highest, returns that nearest endpoint's `field_name`
        value -- clamped, not extrapolated: the nearest actually-measured
        fact stands in for a point outside the curve, the same "nearest
        available fact, not a guessed one" reasoning nearest-point
        selection already uses inside the bracketed case below.
      - otherwise linearly interpolates `field_name` between the two
        points bracketing `frequency_hz` -- more defensible than picking
        the single nearer point once a curve has more than one point,
        which every real fixture in this alphabet does (issue #267
        acceptance criterion 3 explicitly allows either).

    `field_name` names which field of each response point to read
    (`"phase_deg"`, `"magnitude"`, ...) -- a caller-supplied string, not a
    hardcoded `"phase_deg"` internally, mirroring `SymbolOption.
    achieved_value`'s own "generic on purpose" docstring: this function
    never assumes the quantity being reduced is a reflection phase
    specifically, only that it is a real number recorded at each
    `frequency_hz` point. REFLECTION_PHASE/DIFFUSIVE's own dispatch call
    site is what names `"phase_deg"` explicitly, because a coding cell IS
    its reflection phase there (design_families.py's own comment on both
    families) -- not because this function assumes it.

    Raises `InvalidSymbolAlphabetEntryError` if `response` is empty -- there
    is no measured point here to reduce, and returning a made-up number
    would misrepresent an assumption as a measurement (this module's own
    "provenance is never a caller choice" discipline, applied to a derived
    value instead of a stored one) -- the same named-exception discipline
    every other input-validation failure in this module already uses,
    rather than a bare `ValueError` this one function would otherwise be
    the sole exception to.
    """
    if not response:
        raise InvalidSymbolAlphabetEntryError(
            "response is empty -- there is no measured point to reduce a scalar from"
        )
    points = sorted(response, key=lambda point: point["frequency_hz"])
    if frequency_hz <= points[0]["frequency_hz"]:
        return float(points[0][field_name])
    if frequency_hz >= points[-1]["frequency_hz"]:
        return float(points[-1][field_name])
    for lower, upper in zip(points, points[1:], strict=False):
        if lower["frequency_hz"] <= frequency_hz <= upper["frequency_hz"]:
            span = upper["frequency_hz"] - lower["frequency_hz"]
            if span == 0:
                # Two points stored at the identical frequency -- nothing to
                # interpolate across; the earlier (sort-stable) one stands.
                return float(lower[field_name])
            fraction = (frequency_hz - lower["frequency_hz"]) / span
            return float(lower[field_name] + fraction * (upper[field_name] - lower[field_name]))
    raise AssertionError(  # pragma: no cover -- unreachable given the clamps above
        f"frequency_hz={frequency_hz!r} was not bracketed by any pair of sorted "
        "response points despite failing both endpoint clamp checks"
    )


# ---------------------------------------------------------------------------
# I/O layer: persistent storage in `process_records`/`symbol_alphabet_entries`
# (db/schema.sql). Same connection-lifecycle discipline as designs/db.py and
# designs/material_properties.py's own I/O wrappers: functions take an
# already-open connection and never commit it themselves -- the caller owns
# the transaction boundary. Round-trip tested in
# tests/test_element_alphabet.py's TestSymbolAlphabetEntryDatabaseRoundTrip
# against the live Postgres reachable in this sandbox (see this module's
# docstring's "MODULE SHAPE" section) -- each wrapper is still thin glue over
# the pure functions above, which carry all the real validation/lookup logic.
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


def insert_symbol_entry(
    conn: psycopg.Connection,
    element_family: str,
    symbol: str,
    frequency_low_hz: float,
    frequency_high_hz: float,
    incidence_angle_low_deg: float,
    incidence_angle_high_deg: float,
    process_id: int,
    geometry: dict[str, Any] | list[dict[str, Any]],
    response: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate (`add_symbol_entry`) and insert one symbol-alphabet entry.

    Every call inserts a new row -- there is no update/upsert path here,
    deliberately: two entries differing only by `process_id` are two
    distinct, independently-referenceable letters, never merged (ADR-0027
    point 4's carbon-vs-MXene worked example; see this module's own
    docstring).

    `process_id` referencing a nonexistent `process_records` row fails
    loudly here -- `symbol_alphabet_entries.process_id`'s `NOT NULL
    REFERENCES process_records(id)` constraint (`db/schema.sql`) raises
    `psycopg.errors.ForeignKeyViolation` rather than silently creating a
    dangling reference (issue #256 user story 16). This function does not
    catch that error -- it propagates to the caller, who owns the
    transaction and must roll it back before reusing `conn`.
    """
    entry = add_symbol_entry(
        element_family=element_family,
        symbol=symbol,
        frequency_low_hz=frequency_low_hz,
        frequency_high_hz=frequency_high_hz,
        incidence_angle_low_deg=incidence_angle_low_deg,
        incidence_angle_high_deg=incidence_angle_high_deg,
        process_id=process_id,
        geometry=geometry,
        response=response,
    )
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO symbol_alphabet_entries
                (element_family, symbol, frequency_low_hz, frequency_high_hz,
                 incidence_angle_low_deg, incidence_angle_high_deg, process_id,
                 geometry, response, provenance)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                entry["element_family"],
                entry["symbol"],
                entry["frequency_low_hz"],
                entry["frequency_high_hz"],
                entry["incidence_angle_low_deg"],
                entry["incidence_angle_high_deg"],
                entry["process_id"],
                Json(entry["geometry"]),
                Json(entry["response"]),
                entry["provenance"],
            ),
        )
        row = cur.fetchone()
        assert row is not None
    return row


def fetch_symbol_entries(conn: psycopg.Connection, element_family: str) -> list[dict[str, Any]]:
    """Return every stored symbol-alphabet entry for `element_family`, in
    insertion order -- issue #256 user story 21: list every letter
    currently in a given family, without querying one symbol at a time.
    `lookup_symbol_entries`/`resolve_symbol_entry` then narrow this down by
    symbol/band/incidence-angle range/process, the same "caller fetches,
    pure function filters" seam `designs.material_properties.
    fetch_material_property_entries`/`lookup_entries` already use."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM symbol_alphabet_entries WHERE element_family = %s ORDER BY id",
            (element_family,),
        )
        return cur.fetchall()


def resolve_symbol_entry_from_db(
    conn: psycopg.Connection,
    element_family: str,
    symbol: str,
    frequency_hz: float,
    incidence_angle_deg: float,
    process_id: int,
) -> dict[str, Any] | None:
    """`resolve_symbol_entry`, fetching its `entries` input from the
    database first (every entry in `element_family`, via
    `fetch_symbol_entries`) -- the one query a caller building a coded
    surface actually needs: the letter for this symbol, at my design's
    frequency and incidence angle, printed under my current process, or
    nothing."""
    entries = fetch_symbol_entries(conn, element_family)
    return resolve_symbol_entry(
        entries,
        element_family=element_family,
        symbol=symbol,
        frequency_hz=frequency_hz,
        incidence_angle_deg=incidence_angle_deg,
        process_id=process_id,
    )
