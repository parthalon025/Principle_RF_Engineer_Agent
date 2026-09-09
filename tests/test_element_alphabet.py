"""Tests for designs/element_alphabet.py (issue #256; ADR-0027; CONTEXT.md:
Element/Coding-Alphabet library).

Pure-function tests only, following tests/test_material_properties.py's own
direct-template precedent: `add_process_record` carries all of this ticket's
actual validation logic and needs no database, so it is exercised directly
here. The DB-backed I/O wrappers (`insert_process_record`/
`fetch_process_record`) need a live Postgres via DATABASE_URL, and there is
no database in this sandbox (the docker daemon itself is unreachable here --
`docker compose up -d postgres` cannot be brought up) -- the same constraint
tests/test_material_properties.py, tests/test_requirement_targets.py, and
tests/test_designs_service.py already document for themselves. They are thin
glue over `add_process_record` above, the same shape those modules' own
untested I/O wrappers already have, so no round-trip test is written for
them here; issue #256's own Testing Decisions section documents this exact
split (user story 18) as the one to mirror.
"""

from __future__ import annotations

import math

import pytest

from designs.element_alphabet import (
    InvalidSymbolAlphabetEntryError,
    add_process_record,
)

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
