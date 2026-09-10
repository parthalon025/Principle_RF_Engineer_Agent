"""Tests for designs/requirement_targets.py (issue #92).

Pure-function tests only, following tests/test_calculations.py's
deterministic in/out style -- no database needed, matching this repo's own
instruction to keep this file DB-free where the criterion under test is
genuinely pure logic. `propose_target`/`mark_unscoreable`/`confirm_target`/
`attach_target` carry all of the ticket's actual validation/tagging logic
and are exercised directly here.

`propose_requirement_target`/`mark_requirement_unscoreable`/
`confirm_requirement_target` (the I/O wrappers that actually read/write a
stored design's `requirements` column) are mostly NOT tested here: they
need a live Postgres via DATABASE_URL, which most sandboxes running this
suite don't have (same constraint tests/test_designs_service.py and
tests/test_tooling.py already document for themselves) -- the I/O wrappers
are thin glue (open connection, fetch, validate via the pure functions,
attach, write, translate exceptions), the same shape designs/service.py's
already-integration-tested wrappers use, and the pure functions they call
are already fully covered directly below.

The one exception, guarded by the module-level `DATABASE_URL` connectivity
probe at the bottom of this file (mirroring
tests/test_element_alphabet.py's identical `pytest.mark.skipif` pattern):
`_fetch_requirements`'s row lock (issue #389 -- without it,
two proposals against *different* `requirement_id`s on the same design,
close enough in time, can race: the second reads the `requirements` payload
before the first writes its change back, and silently discards it on
commit). That failure mode needs two real, concurrent connections to
reproduce -- a pure-function test cannot exercise it -- so it is the one
thing in this file that is DB-backed rather than a pure in/out check.
"""

from __future__ import annotations

import math
import os
import threading
import uuid

import psycopg
import pytest
from dotenv import load_dotenv

from designs.requirement_targets import (
    InvalidRequirementTargetError,
    TargetComparator,
    TargetStatus,
    UnknownRequirementError,
    _fetch_requirements,
    attach_intent,
    attach_target,
    confirm_target,
    mark_unscoreable,
    propose_intended_effect,
    propose_requirement_target,
    propose_target,
)
from designs.service import create_design, read_design

load_dotenv()

# ---------------------------------------------------------------------------
# propose_target -- comparator vocabulary and shape validation
# ---------------------------------------------------------------------------


def test_propose_target_point_target_is_tagged_assumed_and_proposed():
    target = propose_target(value=2.45e9, comparator="EQUALS", unit="Hz")
    assert target["target_status"] == "PROPOSED"
    assert target["provenance"] == "ASSUMED"
    assert target["value"] == 2.45e9
    assert target["comparator"] == "EQUALS"
    assert target["unit"] == "Hz"
    assert target["tolerance"] is None
    assert target["reason"] is None
    assert target["confirmed_by"] is None
    assert target["confirmed_at"] is None


def test_propose_target_covers_minimum_bound_comparator():
    target = propose_target(value=5.0, comparator="AT_LEAST", unit="dBi")
    assert target["comparator"] == TargetComparator.AT_LEAST.value


def test_propose_target_covers_maximum_bound_comparator():
    target = propose_target(value=2.0, comparator="AT_MOST", unit="ratio")
    assert target["comparator"] == TargetComparator.AT_MOST.value


def test_propose_target_accepts_optional_tolerance():
    target = propose_target(value=2.45e9, comparator="EQUALS", unit="Hz", tolerance=5e6)
    assert target["tolerance"] == 5e6


def test_propose_target_rejects_unknown_comparator():
    with pytest.raises(InvalidRequirementTargetError, match="comparator"):
        propose_target(value=1.0, comparator="ABOUT_THE_SAME_AS", unit="Hz")


def test_propose_target_rejects_non_numeric_value():
    with pytest.raises(InvalidRequirementTargetError, match="value"):
        propose_target(value="2.45 GHz", comparator="EQUALS", unit="Hz")


def test_propose_target_rejects_bool_as_value():
    # bool is technically an int subclass in Python -- explicitly excluded,
    # same guard designs.validation applies to component_id.
    with pytest.raises(InvalidRequirementTargetError, match="value"):
        propose_target(value=True, comparator="EQUALS", unit="Hz")


def test_propose_target_rejects_non_finite_value():
    with pytest.raises(InvalidRequirementTargetError, match="finite"):
        propose_target(value=math.inf, comparator="EQUALS", unit="Hz")


def test_propose_target_rejects_empty_unit():
    with pytest.raises(InvalidRequirementTargetError, match="unit"):
        propose_target(value=1.0, comparator="EQUALS", unit="")


def test_propose_target_rejects_whitespace_only_unit():
    with pytest.raises(InvalidRequirementTargetError, match="unit"):
        propose_target(value=1.0, comparator="EQUALS", unit="   ")


def test_propose_target_rejects_negative_tolerance():
    with pytest.raises(InvalidRequirementTargetError, match="tolerance"):
        propose_target(value=1.0, comparator="EQUALS", unit="Hz", tolerance=-0.1)


def test_propose_target_rejects_non_finite_tolerance():
    with pytest.raises(InvalidRequirementTargetError, match="finite"):
        propose_target(value=1.0, comparator="EQUALS", unit="Hz", tolerance=math.nan)


def test_propose_target_allows_negative_value():
    # RF quantities (dB/dBi/dBm) are routinely negative -- must not be
    # rejected as if a physical-plausibility bound applied here.
    target = propose_target(value=-3.0, comparator="AT_LEAST", unit="dB")
    assert target["value"] == -3.0


# ---------------------------------------------------------------------------
# mark_unscoreable -- the "no defensible target" path
# ---------------------------------------------------------------------------


def test_mark_unscoreable_records_reason_with_no_fabricated_value():
    target = mark_unscoreable("prose states a qualitative goal with no numeric bound")
    assert target["target_status"] == "UNSCOREABLE"
    assert target["provenance"] == "ASSUMED"
    assert target["reason"] == "prose states a qualitative goal with no numeric bound"
    assert target["value"] is None
    assert target["comparator"] is None
    assert target["unit"] is None
    assert target["tolerance"] is None


def test_mark_unscoreable_rejects_empty_reason():
    with pytest.raises(InvalidRequirementTargetError, match="reason"):
        mark_unscoreable("")


def test_mark_unscoreable_rejects_whitespace_only_reason():
    with pytest.raises(InvalidRequirementTargetError, match="reason"):
        mark_unscoreable("   ")


# ---------------------------------------------------------------------------
# confirm_target -- confirmation records who and when, and only from PROPOSED
# ---------------------------------------------------------------------------


def test_confirm_target_records_confirmed_by_and_confirmed_at():
    proposed = propose_target(value=2.45e9, comparator="EQUALS", unit="Hz")
    confirmed = confirm_target(
        proposed, confirmed_by="j.mcfarland", confirmed_at="2026-09-03T00:00:00+00:00"
    )
    assert confirmed["target_status"] == "CONFIRMED"
    assert confirmed["confirmed_by"] == "j.mcfarland"
    assert confirmed["confirmed_at"] == "2026-09-03T00:00:00+00:00"


def test_confirm_target_preserves_the_confirmed_value_and_provenance():
    proposed = propose_target(value=5.0, comparator="AT_LEAST", unit="dBi", tolerance=0.5)
    confirmed = confirm_target(proposed, confirmed_by="j.mcfarland")
    assert confirmed["value"] == 5.0
    assert confirmed["comparator"] == "AT_LEAST"
    assert confirmed["unit"] == "dBi"
    assert confirmed["tolerance"] == 0.5
    # provenance is deliberately still ASSUMED after confirmation -- see the
    # module docstring's "WHY PROVENANCE STAYS ASSUMED" section.
    assert confirmed["provenance"] == "ASSUMED"


def test_confirm_target_does_not_mutate_its_input():
    proposed = propose_target(value=2.45e9, comparator="EQUALS", unit="Hz")
    confirm_target(proposed, confirmed_by="j.mcfarland")
    assert proposed["target_status"] == "PROPOSED"
    assert proposed["confirmed_by"] is None


def test_confirm_target_fills_in_a_real_timestamp_by_default():
    proposed = propose_target(value=2.45e9, comparator="EQUALS", unit="Hz")
    confirmed = confirm_target(proposed, confirmed_by="j.mcfarland")
    assert confirmed["confirmed_at"] is not None
    assert isinstance(confirmed["confirmed_at"], str)


def test_confirm_target_rejects_an_unscoreable_target():
    unscoreable = mark_unscoreable("no numeric bound stated")
    with pytest.raises(InvalidRequirementTargetError, match="UNSCOREABLE|target_status"):
        confirm_target(unscoreable, confirmed_by="j.mcfarland")


def test_confirm_target_rejects_an_already_confirmed_target():
    proposed = propose_target(value=2.45e9, comparator="EQUALS", unit="Hz")
    confirmed_once = confirm_target(proposed, confirmed_by="j.mcfarland")
    with pytest.raises(InvalidRequirementTargetError):
        confirm_target(confirmed_once, confirmed_by="someone.else")


def test_confirm_target_rejects_empty_confirmed_by():
    proposed = propose_target(value=2.45e9, comparator="EQUALS", unit="Hz")
    with pytest.raises(InvalidRequirementTargetError, match="confirmed_by"):
        confirm_target(proposed, confirmed_by="")


# ---------------------------------------------------------------------------
# attach_target -- prose is preserved alongside every target, no migration
# ---------------------------------------------------------------------------


def test_attach_target_preserves_the_original_prose():
    requirements = {
        "req-1": {"requirement": "needs to work at 2.4 GHz without losing gain"},
    }
    target = propose_target(value=2.4e9, comparator="EQUALS", unit="Hz")
    updated = attach_target(requirements, "req-1", target)
    assert updated["req-1"]["requirement"] == "needs to work at 2.4 GHz without losing gain"
    assert updated["req-1"]["target"] == target


def test_attach_target_does_not_mutate_its_input():
    requirements = {"req-1": {"requirement": "some prose"}}
    target = propose_target(value=1.0, comparator="EQUALS", unit="Hz")
    attach_target(requirements, "req-1", target)
    assert "target" not in requirements["req-1"]


def test_attach_target_replaces_a_prior_target_on_correction():
    requirements = {"req-1": {"requirement": "some prose"}}
    first = propose_target(value=1.0, comparator="EQUALS", unit="Hz")
    with_first = attach_target(requirements, "req-1", first)
    second = propose_target(value=2.0, comparator="EQUALS", unit="Hz")
    with_second = attach_target(with_first, "req-1", second)
    assert with_second["req-1"]["target"]["value"] == 2.0
    assert with_second["req-1"]["requirement"] == "some prose"


def test_attach_target_preserves_other_keys_on_the_requirement_entry():
    requirements = {
        "req-1": {"requirement": "some prose", "priority": "high"},
    }
    target = propose_target(value=1.0, comparator="EQUALS", unit="Hz")
    updated = attach_target(requirements, "req-1", target)
    assert updated["req-1"]["priority"] == "high"


def test_attach_target_rejects_unknown_requirement_id():
    requirements = {"req-1": {"requirement": "some prose"}}
    target = propose_target(value=1.0, comparator="EQUALS", unit="Hz")
    with pytest.raises(UnknownRequirementError, match="req-does-not-exist"):
        attach_target(requirements, "req-does-not-exist", target)


def test_attach_target_can_attach_an_unscoreable_result():
    requirements = {
        "req-1": {"requirement": "should feel robust when flexed"},
    }
    target = mark_unscoreable("no numeric bound in the prose")
    updated = attach_target(requirements, "req-1", target)
    assert updated["req-1"]["target"]["target_status"] == "UNSCOREABLE"
    assert updated["req-1"]["target"]["reason"] == "no numeric bound in the prose"


# ---------------------------------------------------------------------------
# propose_intended_effect / attach_intent -- attach_target's direct sibling
# (docs/adr/0030, issue #323)
# ---------------------------------------------------------------------------


def test_propose_intended_effect_is_tagged_assumed():
    intended_effect = propose_intended_effect("behave as a magnetic mirror")
    assert intended_effect["effect"] == "behave as a magnetic mirror"
    assert intended_effect["provenance"] == "ASSUMED"


def test_propose_intended_effect_rejects_empty_effect():
    with pytest.raises(InvalidRequirementTargetError, match="effect"):
        propose_intended_effect("")


def test_propose_intended_effect_rejects_whitespace_only_effect():
    with pytest.raises(InvalidRequirementTargetError, match="effect"):
        propose_intended_effect("   ")


def test_attach_intent_preserves_the_original_prose_and_any_target():
    requirements = {
        "req-1": {
            "requirement": "needs to behave as a magnetic mirror when mounted on the fuselage",
            "target": propose_target(value=2.4e9, comparator="EQUALS", unit="Hz"),
        },
    }
    intended_effect = propose_intended_effect("behave as a magnetic mirror")
    updated = attach_intent(requirements, "req-1", intended_effect)
    assert updated["req-1"]["requirement"].startswith("needs to behave")
    assert updated["req-1"]["target"]["value"] == 2.4e9
    assert updated["req-1"]["intended_effect"] == intended_effect


def test_attach_intent_does_not_mutate_its_input():
    requirements = {"req-1": {"requirement": "some prose"}}
    intended_effect = propose_intended_effect("absorb the wave")
    attach_intent(requirements, "req-1", intended_effect)
    assert "intended_effect" not in requirements["req-1"]


def test_attach_intent_replaces_a_prior_intent_on_correction():
    requirements = {"req-1": {"requirement": "some prose"}}
    first = propose_intended_effect("absorb the wave")
    with_first = attach_intent(requirements, "req-1", first)
    second = propose_intended_effect("reflect in phase")
    with_second = attach_intent(with_first, "req-1", second)
    assert with_second["req-1"]["intended_effect"]["effect"] == "reflect in phase"
    assert with_second["req-1"]["requirement"] == "some prose"


def test_attach_intent_preserves_other_keys_on_the_requirement_entry():
    requirements = {"req-1": {"requirement": "some prose", "priority": "high"}}
    intended_effect = propose_intended_effect("steer the beam")
    updated = attach_intent(requirements, "req-1", intended_effect)
    assert updated["req-1"]["priority"] == "high"


def test_attach_intent_rejects_unknown_requirement_id():
    requirements = {"req-1": {"requirement": "some prose"}}
    intended_effect = propose_intended_effect("absorb the wave")
    with pytest.raises(UnknownRequirementError, match="req-does-not-exist"):
        attach_intent(requirements, "req-does-not-exist", intended_effect)


# ---------------------------------------------------------------------------
# TargetComparator / TargetStatus -- the fixed vocabularies themselves
# ---------------------------------------------------------------------------


def test_target_comparator_covers_point_minimum_and_maximum():
    assert {c.value for c in TargetComparator} == {"EQUALS", "AT_LEAST", "AT_MOST"}


def test_target_status_covers_the_three_lifecycle_states():
    assert {s.value for s in TargetStatus} == {"PROPOSED", "CONFIRMED", "UNSCOREABLE"}


# ---------------------------------------------------------------------------
# DB-backed: _fetch_requirements's row lock (issue #389) -- see this
# module's docstring for why this is the one DB-backed exception here.
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
    reason=f"no reachable Postgres at {_TEST_DATABASE_URL.split('@')[-1]!r} in this sandbox",
)
class TestFetchRequirementsRowLock:
    @pytest.fixture
    def design_id(self):
        result = create_design(
            design_key=f"REQ-TARGET-LOCK-{uuid.uuid4().hex[:8]}",
            name="Row Lock Fixture Design",
            revision="A",
            requirements={
                "REQ-1": {"requirement": "Gain >= 20 dB."},
                "REQ-2": {"requirement": "VSWR <= 1.5."},
            },
            architecture={},
        )
        design_id = result["design_id"]
        yield design_id
        conn = psycopg.connect(_TEST_DATABASE_URL, autocommit=True)
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM designs WHERE id = %s", (design_id,))
        finally:
            conn.close()

    def test_propose_requirement_target_persists_via_read_design(self, design_id):
        result = propose_requirement_target(
            design_id=design_id,
            requirement_id="REQ-1",
            value=20.0,
            comparator="AT_LEAST",
            unit="dB",
        )
        assert result["status"] == "proposed"

        stored = read_design(design_id)
        assert stored["requirements"]["REQ-1"]["target"]["value"] == 20.0

    def test_fetch_requirements_for_update_blocks_a_concurrent_fetch_until_release(self, design_id):
        """The core issue #389 regression test. Without `FOR UPDATE`, two
        proposals against different requirement_ids on the same design can
        both read the `requirements` payload before either writes it back,
        so the second write silently discards the first's change. Proving
        that needs two real, concurrent connections -- a pure-function test
        cannot reproduce a database lock."""
        conn1 = psycopg.connect(_TEST_DATABASE_URL)
        conn2 = psycopg.connect(_TEST_DATABASE_URL)
        unblocked = threading.Event()
        try:
            _fetch_requirements(conn1, design_id)  # holds the row lock, uncommitted

            def _blocked_fetch():
                _fetch_requirements(conn2, design_id)
                unblocked.set()

            thread = threading.Thread(target=_blocked_fetch)
            thread.start()
            # conn2's FOR UPDATE must block while conn1 holds the lock -- a
            # generous window to prove it does NOT complete.
            assert not unblocked.wait(timeout=0.5)

            conn1.rollback()  # releases the lock without persisting anything
            assert unblocked.wait(timeout=2.0)
            thread.join()
        finally:
            conn1.close()
            conn2.close()
