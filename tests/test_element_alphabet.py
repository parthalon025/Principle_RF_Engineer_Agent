"""Tests for designs/element_alphabet.py (issue #256; ADR-0027; CONTEXT.md:
Element/Coding-Alphabet library).

Pure-function tests only, following tests/test_material_properties.py's own
direct-template precedent: `add_process_record`/`add_symbol_entry`/
`lookup_symbol_entries`/`resolve_symbol_entry` carry all of this ticket's
actual validation/lookup logic and need no database, so they are exercised
directly here.

Ticket 2 (this addition) DOES have a live Postgres reachable in this sandbox
-- `postgresql://rf:rf_dev_password@localhost:5432/rfengineer`, per
`.env.example` -- unlike ticket 1's own docstring above, which predates this
and documents the docker-compose path as unreachable. The DB-backed I/O
wrappers (`insert_process_record`, `insert_symbol_entry`,
`fetch_process_record`, `fetch_symbol_entries`,
`resolve_symbol_entry_from_db`) are round-trip tested against that real
database below, in `TestSymbolAlphabetEntryDatabaseRoundTrip`, guarded by a
module-level `DATABASE_URL` connectivity probe (`pytest.mark.skipif`) so this
file still collects and passes in a sandbox where that Postgres genuinely
isn't reachable, without silently skipping when it is.
"""

from __future__ import annotations

import math
import os

import psycopg
import pytest

from designs.element_alphabet import (
    InvalidSymbolAlphabetEntryError,
    add_process_record,
    add_symbol_entry,
    fetch_process_record,
    fetch_symbol_entries,
    insert_process_record,
    insert_symbol_entry,
    lookup_symbol_entries,
    resolve_symbol_entry,
    resolve_symbol_entry_from_db,
)
from knowledge.provenance import MEASURED

# ---------------------------------------------------------------------------
# add_process_record -- validation of every field ADR-0027 point 4 requires.
# ---------------------------------------------------------------------------


def _kwargs(**overrides):
    kwargs = {
        "machine": "Voltera NOVA",
        "ink": "MXene Ti3C2Tx",
        "ink_grade": "battery grade",
        "substrate_stack": "50 um PET on 3 mm PDMS carrier",
        "pass_count": 3,
        "achieved_film_thickness_m": 12.0e-6,
        "cure_schedule": "80 degrees C for 30 min, ambient RH",
    }
    kwargs.update(overrides)
    return kwargs


def test_add_process_record_builds_a_validated_record():
    record = add_process_record(**_kwargs())
    assert record["machine"] == "Voltera NOVA"
    assert record["ink"] == "MXene Ti3C2Tx"
    assert record["ink_grade"] == "battery grade"
    assert record["substrate_stack"] == "50 um PET on 3 mm PDMS carrier"
    assert record["pass_count"] == 3
    assert record["achieved_film_thickness_m"] == pytest.approx(12.0e-6)
    assert record["cure_schedule"] == "80 degrees C for 30 min, ambient RH"


def test_add_process_record_rejects_empty_machine():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="machine"):
        add_process_record(**_kwargs(machine="   "))


def test_add_process_record_rejects_non_string_machine():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="machine"):
        add_process_record(**_kwargs(machine=None))


def test_add_process_record_rejects_empty_ink():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="ink"):
        add_process_record(**_kwargs(ink=""))


def test_add_process_record_rejects_empty_ink_grade():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="ink_grade"):
        add_process_record(**_kwargs(ink_grade="  "))


def test_add_process_record_rejects_empty_substrate_stack():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="substrate_stack"):
        add_process_record(**_kwargs(substrate_stack=""))


def test_add_process_record_rejects_empty_cure_schedule():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="cure_schedule"):
        add_process_record(**_kwargs(cure_schedule="   "))


def test_add_process_record_rejects_negative_pass_count():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="pass_count"):
        add_process_record(**_kwargs(pass_count=-1))


def test_add_process_record_rejects_non_finite_pass_count():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="pass_count"):
        add_process_record(**_kwargs(pass_count=math.inf))


def test_add_process_record_rejects_non_numeric_pass_count():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="pass_count"):
        add_process_record(**_kwargs(pass_count="three"))


def test_add_process_record_rejects_negative_film_thickness():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="achieved_film_thickness_m"):
        add_process_record(**_kwargs(achieved_film_thickness_m=-1.0e-6))


def test_add_process_record_rejects_non_finite_film_thickness():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="achieved_film_thickness_m"):
        add_process_record(**_kwargs(achieved_film_thickness_m=math.nan))


def test_add_process_record_allows_zero_pass_count_and_film_thickness():
    # Zero is a legal (if degenerate) count/thickness -- the validators only
    # reject negative or non-finite values, the same >= 0 discipline
    # designs.material_properties._require_nonnegative_finite_number applies.
    record = add_process_record(**_kwargs(pass_count=0, achieved_film_thickness_m=0.0))
    assert record["pass_count"] == 0
    assert record["achieved_film_thickness_m"] == 0.0


def test_add_process_record_never_silently_coerces_a_bad_value():
    # A bool is technically an int subclass in Python; the validator must
    # not silently accept True/False as a pass count.
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="pass_count"):
        add_process_record(**_kwargs(pass_count=True))


def test_two_runs_on_nominally_identical_settings_are_two_independent_records():
    # Issue #256's Solution section: "achieved" film thickness in particular
    # can vary run to run, so add_process_record never dedupes or merges --
    # each call simply builds its own validated record, independently of any
    # other. This is the pure-function half of that guarantee; the
    # schema-level half (no UNIQUE constraint) lives in db/schema.sql.
    first = add_process_record(**_kwargs(achieved_film_thickness_m=12.0e-6))
    second = add_process_record(**_kwargs(achieved_film_thickness_m=13.5e-6))
    assert first != second
    assert first["achieved_film_thickness_m"] != second["achieved_film_thickness_m"]


# ---------------------------------------------------------------------------
# add_symbol_entry -- validation of the five-part key (ADR-0027 point 4)
# plus geometry/response round-tripping.
# ---------------------------------------------------------------------------

_GEOMETRY = {
    "shape": "box",
    "p1_m": [0.0, 0.0, 0.0],
    "p2_m": [0.001, 0.001, 0.0],
}

_RESPONSE = [
    {"frequency_hz": 9.0e9, "magnitude": 0.98, "phase_deg": -2.0},
    {"frequency_hz": 10.0e9, "magnitude": 0.99, "phase_deg": 0.5},
    {"frequency_hz": 11.0e9, "magnitude": 0.97, "phase_deg": 3.0},
]


def _symbol_kwargs(**overrides):
    kwargs = {
        "element_family": "interdigital_elc",
        "symbol": "elc_finger_4",
        "frequency_low_hz": 8.0e9,
        "frequency_high_hz": 12.0e9,
        "incidence_angle_low_deg": 0.0,
        "incidence_angle_high_deg": 30.0,
        "process_id": 1,
        "geometry": _GEOMETRY,
        "response": _RESPONSE,
    }
    kwargs.update(overrides)
    return kwargs


def test_add_symbol_entry_builds_a_validated_measured_entry():
    entry = add_symbol_entry(**_symbol_kwargs())
    assert entry["element_family"] == "interdigital_elc"
    assert entry["symbol"] == "elc_finger_4"
    assert entry["frequency_low_hz"] == 8.0e9
    assert entry["frequency_high_hz"] == 12.0e9
    assert entry["incidence_angle_low_deg"] == 0.0
    assert entry["incidence_angle_high_deg"] == 30.0
    assert entry["process_id"] == 1
    # Provenance is never a caller choice -- every entry is MEASURED by
    # construction (ADR-0027).
    assert entry["provenance"] == MEASURED
    # Geometry/response round-trip exactly, unchanged.
    assert entry["geometry"] == _GEOMETRY
    assert entry["response"] == _RESPONSE


def test_add_symbol_entry_rejects_empty_element_family():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="element_family"):
        add_symbol_entry(**_symbol_kwargs(element_family="   "))


def test_add_symbol_entry_rejects_empty_symbol():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="symbol"):
        add_symbol_entry(**_symbol_kwargs(symbol=""))


def test_add_symbol_entry_rejects_non_finite_frequency():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="frequency"):
        add_symbol_entry(**_symbol_kwargs(frequency_low_hz=math.nan))


def test_add_symbol_entry_rejects_negative_frequency():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="frequency"):
        add_symbol_entry(**_symbol_kwargs(frequency_low_hz=-1.0))


def test_add_symbol_entry_rejects_inverted_frequency_band():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="frequency"):
        add_symbol_entry(**_symbol_kwargs(frequency_low_hz=12.0e9, frequency_high_hz=8.0e9))


def test_add_symbol_entry_rejects_non_finite_incidence_angle():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="incidence_angle"):
        add_symbol_entry(**_symbol_kwargs(incidence_angle_high_deg=math.inf))


def test_add_symbol_entry_rejects_inverted_incidence_angle_range():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="incidence_angle"):
        add_symbol_entry(
            **_symbol_kwargs(incidence_angle_low_deg=30.0, incidence_angle_high_deg=0.0)
        )


def test_add_symbol_entry_allows_a_negative_incidence_angle_low_bound():
    # An incidence-angle range spanning both sides of normal incidence
    # (e.g. -30 to +30 degrees) is physically legitimate -- only inversion
    # and non-finiteness are rejected, never a negative value on its own.
    entry = add_symbol_entry(
        **_symbol_kwargs(incidence_angle_low_deg=-30.0, incidence_angle_high_deg=30.0)
    )
    assert entry["incidence_angle_low_deg"] == -30.0


def test_add_symbol_entry_requires_a_process_reference():
    # ADR-0027 / issue #256 user story 4: an entry carrying no process
    # reference is an assumption, not a measurement, and must be rejected
    # -- never silently admitted as a hypothesis.
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="process"):
        add_symbol_entry(**_symbol_kwargs(process_id=None))


def test_add_symbol_entry_rejects_a_non_integer_process_id():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="process"):
        add_symbol_entry(**_symbol_kwargs(process_id="one"))


def test_add_symbol_entry_rejects_a_non_positive_process_id():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="process"):
        add_symbol_entry(**_symbol_kwargs(process_id=0))


def test_add_symbol_entry_requires_geometry():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="geometry"):
        add_symbol_entry(**_symbol_kwargs(geometry=None))


def test_add_symbol_entry_requires_response():
    with pytest.raises(InvalidSymbolAlphabetEntryError, match="response"):
        add_symbol_entry(**_symbol_kwargs(response=None))


def test_add_symbol_entry_accepts_a_list_of_geometry_primitives():
    # geometry/unit_cell.py's own unit_cell shape accepts either a single
    # primitive dict OR a list of them (e.g. combine_shapes()'s return
    # value) -- add_symbol_entry must round-trip both, not just a dict.
    geometry_list = [_GEOMETRY, dict(_GEOMETRY, p1_m=[0.001, 0.0, 0.0])]
    entry = add_symbol_entry(**_symbol_kwargs(geometry=geometry_list))
    assert entry["geometry"] == geometry_list


# ---------------------------------------------------------------------------
# lookup_symbol_entries / resolve_symbol_entry -- match on the full
# five-part key; a non-matching process returns absence, never a status
# flag or an error (ADR-0027's "entries never expire, they stop matching").
# ---------------------------------------------------------------------------


def test_lookup_symbol_entries_matches_family_symbol_band_angle_and_process():
    entry = add_symbol_entry(**_symbol_kwargs())
    matches = lookup_symbol_entries(
        [entry],
        element_family="interdigital_elc",
        symbol="elc_finger_4",
        frequency_hz=10.0e9,
        incidence_angle_deg=15.0,
        process_id=1,
    )
    assert matches == [entry]


def test_lookup_symbol_entries_excludes_a_frequency_outside_the_band():
    entry = add_symbol_entry(**_symbol_kwargs())
    matches = lookup_symbol_entries(
        [entry],
        element_family="interdigital_elc",
        symbol="elc_finger_4",
        frequency_hz=20.0e9,
        incidence_angle_deg=15.0,
        process_id=1,
    )
    assert matches == []


def test_lookup_symbol_entries_excludes_an_incidence_angle_outside_the_range():
    entry = add_symbol_entry(**_symbol_kwargs())
    matches = lookup_symbol_entries(
        [entry],
        element_family="interdigital_elc",
        symbol="elc_finger_4",
        frequency_hz=10.0e9,
        incidence_angle_deg=60.0,
        process_id=1,
    )
    assert matches == []


def test_lookup_symbol_entries_against_a_non_matching_process_returns_nothing_not_an_error():
    # The core ADR-0027 model: a process change doesn't invalidate an
    # entry, it just stops matching. No status flag, no exception -- a
    # plain empty list from lookup, and a plain None (never a status
    # dict) from resolve, the same as any other non-matching query.
    entry = add_symbol_entry(**_symbol_kwargs(process_id=1))
    matches = lookup_symbol_entries(
        [entry],
        element_family="interdigital_elc",
        symbol="elc_finger_4",
        frequency_hz=10.0e9,
        incidence_angle_deg=15.0,
        process_id=2,
    )
    assert matches == []
    resolved = resolve_symbol_entry(
        [entry],
        element_family="interdigital_elc",
        symbol="elc_finger_4",
        frequency_hz=10.0e9,
        incidence_angle_deg=15.0,
        process_id=2,
    )
    assert resolved is None


def test_lookup_symbol_entries_is_scoped_to_family_and_symbol():
    entry = add_symbol_entry(**_symbol_kwargs())
    matches = lookup_symbol_entries(
        [entry],
        element_family="interdigital_elc",
        symbol="a_different_symbol",
        frequency_hz=10.0e9,
        incidence_angle_deg=15.0,
        process_id=1,
    )
    assert matches == []


def test_two_entries_differing_only_by_process_are_both_retained_and_independently_retrievable():
    # ADR-0027's own worked example: "the same outline printed in carbon
    # and in MXene is two letters, not one letter under two conditions."
    # Neither merged nor overwritten -- both stored, both independently
    # retrievable by their own process id.
    carbon_entry = add_symbol_entry(**_symbol_kwargs(process_id=1))
    mxene_entry = add_symbol_entry(**_symbol_kwargs(process_id=2))
    entries = [carbon_entry, mxene_entry]

    carbon_matches = lookup_symbol_entries(
        entries,
        element_family="interdigital_elc",
        symbol="elc_finger_4",
        frequency_hz=10.0e9,
        incidence_angle_deg=15.0,
        process_id=1,
    )
    mxene_matches = lookup_symbol_entries(
        entries,
        element_family="interdigital_elc",
        symbol="elc_finger_4",
        frequency_hz=10.0e9,
        incidence_angle_deg=15.0,
        process_id=2,
    )
    assert carbon_matches == [carbon_entry]
    assert mxene_matches == [mxene_entry]
    assert carbon_matches != mxene_matches


def test_resolve_symbol_entry_returns_the_single_matching_entry():
    entry = add_symbol_entry(**_symbol_kwargs())
    resolved = resolve_symbol_entry(
        [entry],
        element_family="interdigital_elc",
        symbol="elc_finger_4",
        frequency_hz=10.0e9,
        incidence_angle_deg=15.0,
        process_id=1,
    )
    assert resolved == entry


def test_resolve_symbol_entry_returns_none_not_a_status_flag_on_a_miss():
    entry = add_symbol_entry(**_symbol_kwargs(process_id=1))
    resolved = resolve_symbol_entry(
        [entry],
        element_family="interdigital_elc",
        symbol="elc_finger_4",
        frequency_hz=10.0e9,
        incidence_angle_deg=15.0,
        process_id=999,
    )
    assert resolved is None


def test_listing_every_entry_in_a_family():
    # Issue #256 user story 21: list every letter currently in a given
    # element family, without querying one symbol at a time.
    entry_a = add_symbol_entry(**_symbol_kwargs(symbol="elc_finger_4", process_id=1))
    entry_b = add_symbol_entry(**_symbol_kwargs(symbol="elc_finger_6", process_id=1))
    other_family_entry = add_symbol_entry(
        **_symbol_kwargs(element_family="split_ring_resonator", symbol="srr_1", process_id=1)
    )
    all_entries = [entry_a, entry_b, other_family_entry]
    family_entries = [e for e in all_entries if e["element_family"] == "interdigital_elc"]
    assert family_entries == [entry_a, entry_b]


# ---------------------------------------------------------------------------
# DB-backed I/O wrappers -- round-trip tested against a real Postgres when
# one is reachable at DATABASE_URL (or the .env.example default), skipped
# otherwise rather than silently omitted. See this module's docstring.
# ---------------------------------------------------------------------------

_TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://rf:rf_dev_password@localhost:5432/rfengineer"
)


def _database_reachable() -> bool:
    try:
        with psycopg.connect(_TEST_DATABASE_URL, connect_timeout=3):
            return True
    except psycopg.OperationalError:
        return False


_DB_REACHABLE = _database_reachable()


@pytest.mark.skipif(
    not _DB_REACHABLE,
    reason=f"no reachable Postgres at {_TEST_DATABASE_URL!r} in this sandbox",
)
class TestSymbolAlphabetEntryDatabaseRoundTrip:
    """`insert_process_record`/`insert_symbol_entry`/`fetch_process_record`/
    `fetch_symbol_entries`/`resolve_symbol_entry_from_db` exercised against a
    real, live `symbol_alphabet_entries`/`process_records` schema. Every test
    opens its own connection and rolls back at the end, so nothing written
    here is left behind in the shared database.
    """

    @pytest.fixture
    def conn(self):
        connection = psycopg.connect(_TEST_DATABASE_URL)
        try:
            yield connection
        finally:
            connection.rollback()
            connection.close()

    def _insert_process(self, conn, **overrides):
        kwargs = {
            "machine": "Voltera NOVA",
            "ink": "MXene Ti3C2Tx",
            "ink_grade": "battery grade",
            "substrate_stack": "50 um PET on 3 mm PDMS carrier",
            "pass_count": 3,
            "achieved_film_thickness_m": 12.0e-6,
            "cure_schedule": "80 degrees C for 30 min, ambient RH",
        }
        kwargs.update(overrides)
        return insert_process_record(conn, **kwargs)

    def test_insert_and_fetch_process_record_round_trips(self, conn):
        inserted = self._insert_process(conn)
        fetched = fetch_process_record(conn, inserted["id"])
        assert fetched is not None
        assert fetched["machine"] == "Voltera NOVA"
        assert fetched["ink"] == "MXene Ti3C2Tx"

    def test_fetch_process_record_returns_none_for_an_unknown_id(self, conn):
        assert fetch_process_record(conn, 2**62) is None

    def test_insert_symbol_entry_round_trips_geometry_and_response(self, conn):
        process = self._insert_process(conn)
        inserted = insert_symbol_entry(conn, **_symbol_kwargs(process_id=process["id"]))
        assert inserted["element_family"] == "interdigital_elc"
        assert inserted["provenance"] == MEASURED
        assert inserted["geometry"] == _GEOMETRY
        assert inserted["response"] == _RESPONSE

        fetched = fetch_symbol_entries(conn, element_family="interdigital_elc")
        assert any(row["id"] == inserted["id"] for row in fetched)

    def test_insert_symbol_entry_fails_loudly_against_a_nonexistent_process(self, conn):
        # User story 16: an entry tied to a process id that does not exist
        # must fail loudly (the FK constraint), never create a dangling
        # reference.
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            insert_symbol_entry(conn, **_symbol_kwargs(process_id=2**62))
        conn.rollback()

    def test_resolve_symbol_entry_from_db_matches_the_full_key(self, conn):
        process = self._insert_process(conn)
        insert_symbol_entry(conn, **_symbol_kwargs(process_id=process["id"]))

        resolved = resolve_symbol_entry_from_db(
            conn,
            element_family="interdigital_elc",
            symbol="elc_finger_4",
            frequency_hz=10.0e9,
            incidence_angle_deg=15.0,
            process_id=process["id"],
        )
        assert resolved is not None
        assert resolved["symbol"] == "elc_finger_4"

    def test_resolve_symbol_entry_from_db_returns_none_for_a_non_matching_process(self, conn):
        process = self._insert_process(conn)
        other_process = self._insert_process(conn, achieved_film_thickness_m=20.0e-6)
        insert_symbol_entry(conn, **_symbol_kwargs(process_id=process["id"]))

        resolved = resolve_symbol_entry_from_db(
            conn,
            element_family="interdigital_elc",
            symbol="elc_finger_4",
            frequency_hz=10.0e9,
            incidence_angle_deg=15.0,
            process_id=other_process["id"],
        )
        assert resolved is None

    def test_two_entries_differing_only_by_process_both_persist_independently(self, conn):
        process_a = self._insert_process(conn)
        process_b = self._insert_process(
            conn, ink="carbon ACI SC1502", achieved_film_thickness_m=8.0e-6
        )

        entry_a = insert_symbol_entry(conn, **_symbol_kwargs(process_id=process_a["id"]))
        entry_b = insert_symbol_entry(conn, **_symbol_kwargs(process_id=process_b["id"]))

        assert entry_a["id"] != entry_b["id"]
        fetched = fetch_symbol_entries(conn, element_family="interdigital_elc")
        fetched_ids = {row["id"] for row in fetched}
        assert {entry_a["id"], entry_b["id"]} <= fetched_ids
