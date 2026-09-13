"""Tests for simulation/conservation_checks.py (issue #221).

The real `palace` binary is built into this project's own Docker image
(Dockerfile) but absent on a bare host (confirmed via `which palace`,
outside that image; issue #480 -- see tests/test_palace.py's own header
comment) and never actually driven by this test suite even inside it,
and issue #210 -- which would
run it against a real binary and produce a genuine measured S-parameter
fixture -- is still open as of this writing, so none of this repo has a
real solver-derived S-parameter dataset to test against yet (confirmed by
searching this repo's docs/, simulation/, and tests/ trees). Every fixture
below is therefore SYNTHETIC, built one of two ways:

  - closed-form Fresnel-equation reflection/transmission for a lossless
    dielectric slab (`_fresnel_slab`) -- a textbook result with an exact,
    independently-known power-balance/reciprocity/passivity answer, used
    for the "everything is fine" baseline checks; or
  - a hand-built multi-order set with power fractions chosen by
    construction to sum to exactly 1.0 -- used for the multi-diffraction-
    order and deliberately-broken-entry tests, where a closed form isn't
    needed (only "these numbers are known to sum to 1" is).

NOTE for whoever picks up issue #210: once a real Palace run against the
dielectric-grating example exists, add (or replace this file's synthetic
grating fixture with) a case built from that real output -- this file's
synthetic data proves the *arithmetic and tolerance logic* are correct, not
that a real Palace run actually balances to within this module's tolerance.
"""

from __future__ import annotations

import cmath
import math

import pytest

from simulation.conservation_checks import (
    NOISE_FLOOR_LINEAR,
    POWER_TOLERANCE_DB,
    RECIPROCITY_TOLERANCE_DB,
    SParamEntry,
    check_conservation,
    check_flat_s_parameters,
    check_palace_result,
    entries_from_flat_s_parameters,
    entries_from_palace_modes,
)
from simulation.palace import parse_palace_output

# ---------------------------------------------------------------------------
# Fixture builder: lossless dielectric slab, closed-form Fresnel equations.
# Vacuum on both sides, normal incidence, thickness d_m, relative
# permittivity er -- textbook two-interface reflection/transmission with a
# known-exact answer: |S11|^2 + |S21|^2 == 1 (lossless), S11 == S22 and
# S21 == S12 (a symmetric slab is reciprocal AND its own mirror image), and
# |S11|, |S21| <= 1 (passive) for every real er/d_m/f.
# ---------------------------------------------------------------------------

_C = 299_792_458.0


def _fresnel_slab(frequency_hz: float, er: float, d_m: float) -> tuple[complex, complex]:
    """Return (S11, S21) for a lossless dielectric slab in vacuum at normal
    incidence. Standard two-interface Fresnel result (e.g. Pozar,
    *Microwave Engineering*, the "wave in a dielectric slab" derivation)."""
    n = math.sqrt(er)
    k0 = 2 * math.pi * frequency_hz / _C
    beta = n * k0 * d_m
    r0 = (1 - n) / (1 + n)
    e2 = cmath.exp(-1j * 2 * beta)
    s11 = r0 * (1 - e2) / (1 - r0**2 * e2)
    s21 = (1 - r0**2) * cmath.exp(-1j * beta) / (1 - r0**2 * e2)
    return s11, s21


_SLAB_FREQS_HZ = [3e9, 5e9, 7e9, 9e9, 11e9]
_SLAB_ER = 4.0
_SLAB_D_M = 0.01


def _slab_entries() -> list[SParamEntry]:
    """Full 2-port entry set (both excitations) for the slab above --
    needed so the reciprocity check has both S21 (port-1 excited) and S12
    (port-2 excited) to compare."""
    entries: list[SParamEntry] = []
    for f_hz in _SLAB_FREQS_HZ:
        s11, s21 = _fresnel_slab(f_hz, _SLAB_ER, _SLAB_D_M)
        # Symmetric slab: S22 == S11, S12 == S21 (reciprocity + mirror
        # symmetry of the same physical structure seen from the other side).
        entries += [
            SParamEntry(f_hz, "1", "1", s11),
            SParamEntry(f_hz, "1", "2", s21),
            SParamEntry(f_hz, "2", "2", s11),
            SParamEntry(f_hz, "2", "1", s21),
        ]
    return entries


# ---------------------------------------------------------------------------
# Baseline: a correct, lossless, passive, reciprocal dataset -> everything
# ok, with real (non-trivial) numeric margins reported, not bare booleans.
# ---------------------------------------------------------------------------


def test_fresnel_slab_baseline_all_checks_pass_with_numeric_margins():
    report = check_conservation(_slab_entries(), lossless=True, reciprocal=True)
    assert report["all_ok"] is True
    assert report["warnings"] == []
    assert len(report["power_balance"]) == len(_SLAB_FREQS_HZ) * 2  # 2 excitations/freq
    for row in report["power_balance"]:
        assert row["ok"] is True
        assert row["power_sum"] == pytest.approx(1.0, abs=1e-6)
        # A numeric margin is reported, not just a bool.
        assert isinstance(row["power_sum_db"], float)
        assert abs(row["power_sum_db"]) < 1e-4
    for row in report["passivity"]:
        assert row["ok"] is True
        assert row["magnitude_db"] <= 0.0
    assert len(report["reciprocity"]) == len(_SLAB_FREQS_HZ)  # one S12/S21 pair per frequency
    for row in report["reciprocity"]:
        assert row["ok"] is True
        assert row["magnitude_diff_db"] < 1e-6
        assert row["phase_diff_deg"] < 1e-6


def test_power_balance_reports_dissipation_when_not_declared_lossless():
    """Same physically-lossless data, but WITHOUT declaring lossless=True:
    the (near-zero) deficit is reported as information, never as a
    violation -- an undeclared or genuinely lossy (e.g. absorber) result
    must not be penalized for having power unaccounted for."""
    report = check_conservation(_slab_entries(), lossless=None, reciprocal=True)
    assert report["all_ok"] is True
    for row in report["power_balance"]:
        assert row["ok"] is True
        assert row["lossless_declared"] is False


# ---------------------------------------------------------------------------
# Multi-order power balance: the ticket's core scope requirement -- sum
# over EVERY propagating order, not just the specular (S11/S21) pair.
# ---------------------------------------------------------------------------


def _grating_entries(
    order_powers: dict[str, float], corrupt: str | None = None
) -> list[SParamEntry]:
    """Hand-built single-excitation, multi-order grating: `order_powers`
    maps a response label to its true power fraction (must sum to 1.0 for
    a lossless case). If `corrupt` names one label, that entry's magnitude
    is replaced with a near-numerical-zero value (-80 dB power) instead of
    its true value -- the same *pattern* as issue #221's motivating bug (a
    real return silently replaced by a near-zero one), at a power fraction
    chosen large enough to be unambiguous (see module docstring's TOLERANCE
    DERIVATION for why the exact -18.9/-158 dB numbers are tested
    separately, not here)."""
    entries = []
    for label, power in order_powers.items():
        mag = math.sqrt(1e-8) if label == corrupt else math.sqrt(power)
        entries.append(SParamEntry(10e9, "1", label, complex(mag, 0.0)))
    return entries


_GRATING_ORDER_POWERS = {"order0": 0.5, "order+1": 0.3, "order-1": 0.2}


def test_multi_order_power_balance_sums_every_order_and_passes():
    entries = _grating_entries(_GRATING_ORDER_POWERS)
    report = check_conservation(entries, lossless=True)
    assert len(report["power_balance"]) == 1
    row = report["power_balance"][0]
    assert row["n_responses"] == 3
    assert row["power_sum"] == pytest.approx(1.0)
    assert row["ok"] is True


def test_checking_only_the_specular_order_alone_is_not_meaningful():
    """Demonstrates the ticket's own caution: 'balancing only S11/S21 would
    silently pass on exactly the periodic structures this project
    designs' -- for a real grating that legitimately spreads power over
    several propagating orders, a check that only sees ONE of them has no
    way to distinguish 'the other orders legitimately carry the rest of
    the power' from 'something is broken'. It is not that such a narrow
    check always screams false alarm (a tight tolerance would) or always
    stays silent (a loose one would) -- it is that its result is
    meaningless either way, because the number it's comparing against 1.0
    was never supposed to be 1.0 on its own. Summing every propagating
    order (as this module always does) is what makes the comparison to
    1.0 mean something."""
    only_specular = [e for e in _grating_entries(_GRATING_ORDER_POWERS) if e.response == "order0"]
    report = check_conservation(only_specular, lossless=True)
    row = report["power_balance"][0]
    assert row["power_sum"] == pytest.approx(0.5)  # NOT close to 1.0 -- yet nothing is wrong
    assert row["ok"] is False  # a narrow check flags a perfectly correct grating result


# ---------------------------------------------------------------------------
# Regression: the deliberately-broken variant, built the way issue #221
# describes -- one entry corrupted from its true (non-negligible) value
# down to a near-numerical-zero one, mimicking the real defect (two mode
# labels collided on one dictionary key and the near-zero one survived).
# ---------------------------------------------------------------------------


def test_gross_corruption_of_one_order_is_flagged_by_power_balance():
    good = check_conservation(_grating_entries(_GRATING_ORDER_POWERS), lossless=True)
    assert good["power_balance"][0]["ok"] is True

    broken = check_conservation(
        _grating_entries(_GRATING_ORDER_POWERS, corrupt="order+1"), lossless=True
    )
    row = broken["power_balance"][0]
    assert row["ok"] is False
    assert row["power_sum"] == pytest.approx(0.7, abs=1e-6)  # lost the 30%-power order
    assert row["deficit_db"] > POWER_TOLERANCE_DB
    assert "ASSUMED" in row["note"] and "CHEAPEST CHECK" in row["note"]
    assert row["note"] in broken["warnings"]
    assert broken["all_ok"] is False


def test_gross_corruption_does_not_trip_passivity_only_power_balance():
    """Passivity alone CANNOT catch a value that got too small (a
    corrupted-to-near-zero entry is, if anything, MORE comfortably
    passive) -- this is exactly why power balance is a separate,
    necessary check, not a restatement of passivity."""
    broken = check_conservation(
        _grating_entries(_GRATING_ORDER_POWERS, corrupt="order+1"), lossless=True
    )
    assert all(row["ok"] for row in broken["passivity"])


def test_issue_221_exact_numbers_boundary_case_is_not_flagged_by_design():
    """issue #221's own motivating numbers: a true value of -18.9 dB (a
    1.29% power fraction) silently replaced by -158 dB (~0). As derived in
    simulation/conservation_checks.py's module docstring TOLERANCE
    DERIVATION section: the power-balance shortfall this induces
    (10*log10(1 - 10**(-18.9/10)) = -0.056 dB) is, by construction of the
    cited empirical numbers, indistinguishable in scale from this same
    adapter's own reported MAXIMUM ordinary discretization residual
    (also 0.056 dB). A tolerance tight enough to always catch this exact
    magnitude would also flag ordinary, correct runs at their own
    documented noise ceiling -- so this module does NOT flag it, by
    design, and this test exists to make that an intentional, tested
    decision rather than an accidental gap. See the module docstring for
    the full reasoning and the honest tradeoff this represents."""
    true_power = 10 ** (-18.9 / 10)
    remainder_power = 1.0 - true_power
    entries = [
        SParamEntry(10e9, "1", "dominant", complex(math.sqrt(remainder_power), 0.0)),
        # Corrupted: -158 dB power instead of the true -18.9 dB.
        SParamEntry(10e9, "1", "weak_order", complex(10 ** (-158 / 20), 0.0)),
    ]
    report = check_conservation(entries, lossless=True)
    row = report["power_balance"][0]
    assert row["deficit_db"] == pytest.approx(0.0564, abs=0.001)
    assert row["deficit_db"] < POWER_TOLERANCE_DB
    assert row["ok"] is True  # documented limitation, not a bug -- see docstring above


# ---------------------------------------------------------------------------
# Passivity
# ---------------------------------------------------------------------------


def test_passivity_flags_gain_with_numeric_excess():
    entries = [SParamEntry(1e9, "1", "1", complex(1.05, 0.0))]  # |S|=1.05 > 1
    report = check_conservation(entries, reciprocal=False)
    row = report["passivity"][0]
    assert row["ok"] is False
    expected_db = 10 * math.log10(1.05**2)
    assert row["magnitude_db"] == pytest.approx(expected_db)
    assert row["excess_db"] == pytest.approx(expected_db)
    assert "ASSUMED" in row["note"]


def test_passivity_within_tolerance_is_not_flagged():
    small_excess = 10 ** (POWER_TOLERANCE_DB / 20 / 2)  # well under the 0.2 dB band
    entries = [SParamEntry(1e9, "1", "1", complex(small_excess, 0.0))]
    report = check_conservation(entries, reciprocal=False)
    assert report["passivity"][0]["ok"] is True


# ---------------------------------------------------------------------------
# Reciprocity
# ---------------------------------------------------------------------------


def test_reciprocity_flags_a_real_break():
    entries = [
        SParamEntry(1e9, "1", "2", complex(0.7071067811865476, 0.0)),  # -3.01 dB
        SParamEntry(1e9, "2", "1", complex(0.5, 0.0)),  # -6.02 dB -- 3 dB apart
    ]
    report = check_conservation(entries, reciprocal=True)
    assert len(report["reciprocity"]) == 1
    row = report["reciprocity"][0]
    assert row["ok"] is False
    assert row["magnitude_diff_db"] == pytest.approx(3.0103, abs=1e-3)
    assert row["magnitude_diff_db"] > RECIPROCITY_TOLERANCE_DB
    assert "ASSUMED" in row["note"]


def test_reciprocal_false_skips_the_check_with_an_explanatory_note():
    entries = [
        SParamEntry(1e9, "1", "2", complex(0.9, 0.0)),
        SParamEntry(1e9, "2", "1", complex(0.1, 0.0)),  # would fail reciprocity if checked
    ]
    report = check_conservation(entries, reciprocal=False)
    assert report["reciprocity"] == []
    assert report["reciprocity_note"] is not None
    assert "non-reciprocal" in report["reciprocity_note"]
    assert report["all_ok"] is True  # nothing flagged -- the check was declared skipped


def test_reciprocity_with_no_reverse_direction_data_is_simply_absent():
    """Palace's own adapter only ever excites port 1 (see
    simulation/palace.py) -- there is no S_{port1<-port2} data to compare
    against. This must not be treated as a violation OR silently ignored:
    it should just produce no reciprocity rows for that pair."""
    entries = [SParamEntry(1e9, "1", "2", complex(0.5, 0.0))]  # only one direction
    report = check_conservation(entries, reciprocal=True)
    assert report["reciprocity"] == []
    assert report["all_ok"] is True


def test_reciprocity_numerical_noise_floor_is_not_a_false_disagreement():
    """Two numerical-zero cross-polarized-style terms (issue #221's own
    example: -204 dB) must not manufacture a false 'disagreement' just
    because comparing two near-zero floats in dB terms is numerically
    unstable."""
    entries = [
        SParamEntry(1e9, "1", "2", complex(10 ** (-158 / 20), 0.0)),
        SParamEntry(1e9, "2", "1", complex(10 ** (-204 / 20), 0.0)),
    ]
    assert abs(entries[0].value) < NOISE_FLOOR_LINEAR
    assert abs(entries[1].value) < NOISE_FLOOR_LINEAR
    report = check_conservation(entries, reciprocal=True)
    row = report["reciprocity"][0]
    assert row["ok"] is True
    assert "noise floor" in row["note"]


# ---------------------------------------------------------------------------
# Adapter functions: this codebase's two existing S-parameter shapes.
# ---------------------------------------------------------------------------


def test_entries_from_flat_s_parameters_basic_shape():
    s_parameters = {
        "S11": [[0.1, 0.0], [0.2, 0.0]],
        "S21": [[0.9, 0.0], [0.8, 0.0]],
        "note": "not an Sij key -- must be skipped, not crash",
        "computed": True,
    }
    entries = entries_from_flat_s_parameters(s_parameters, frequency_hz=[1e9, 2e9])
    assert len(entries) == 4
    s11_at_1ghz = next(e for e in entries if e.response == "1" and e.frequency_hz == 1e9)
    assert s11_at_1ghz.excitation == "1"
    assert s11_at_1ghz.value == complex(0.1, 0.0)
    s21_at_2ghz = next(
        e for e in entries if e.response == "2" and e.excitation == "1" and e.frequency_hz == 2e9
    )
    assert s21_at_2ghz.value == complex(0.8, 0.0)


def test_entries_from_flat_s_parameters_skips_none_values():
    s_parameters = {"S11": [[0.1, 0.0], None]}
    entries = entries_from_flat_s_parameters(s_parameters, frequency_hz=[1e9, 2e9])
    assert len(entries) == 1


def test_check_flat_s_parameters_end_to_end():
    s_parameters = {"S11": [[0.5, 0.0]], "S21": [[0.8660254, 0.0]]}
    report = check_flat_s_parameters(s_parameters, frequency_hz=[10e9], lossless=True)
    assert report["all_ok"] is True
    assert report["power_balance"][0]["power_sum"] == pytest.approx(1.0, abs=1e-5)


def test_entries_from_palace_modes_uses_full_mode_set_not_specular():
    """The whole point (see module docstring): building entries from the
    full `modes` dict, not the `specular` convenience view, means a
    co-polarized and cross-polarized mode at the SAME diffraction order
    both survive as distinct entries instead of colliding."""
    parsed = {
        "computed": True,
        "frequency_hz": [10e9],
        "modes": {
            "S[P1(0,0)TE][1]": {
                "port": 1,
                "m": 0,
                "n": 0,
                "polarization": "TE",
                "excitation": 1,
                "value_complex": [[0.1135727, 0.0]],  # -18.9 dB, co-pol
            },
            "S[P1(0,0)TM][1]": {
                "port": 1,
                "m": 0,
                "n": 0,
                "polarization": "TM",
                "excitation": 1,
                "value_complex": [[1.258925e-08, 0.0]],  # -158 dB, cross-pol
            },
            "S[P2(0,0)TE][1]": {
                "port": 2,
                "m": 0,
                "n": 0,
                "polarization": "TE",
                "excitation": 1,
                "value_complex": [[0.99353, 0.0]],  # the rest of the power
            },
        },
    }
    entries = entries_from_palace_modes(parsed)
    assert len(entries) == 3
    labels = {e.response for e in entries}
    # Both polarization components at (0,0) survive as distinct labels --
    # no collision, unlike the buggy `specular[f"S{port}1"]` construction
    # this sidesteps (see simulation/palace.py's `specular` code, which
    # keys ONLY on port -- not polarization -- for m=n=0).
    assert "P1(0,0)TE" in labels
    assert "P1(0,0)TM" in labels
    assert "P2(0,0)TE" in labels

    report = check_conservation(entries, lossless=True)
    # Correctly balanced: nothing was ever actually lost at the `modes`
    # level -- only a downstream convenience view (specular) would have
    # collided these two polarization keys.
    assert report["power_balance"][0]["ok"] is True


def test_check_palace_result_passes_through_computed_false():
    parsed = {"computed": False, "note": "no port-floquet-S.csv"}
    result = check_palace_result(parsed)
    assert result == {"computed": False, "note": "no port-floquet-S.csv"}


# ---------------------------------------------------------------------------
# End-to-end integration: a synthetic port-floquet-S.csv (the real Palace
# output format, per simulation/palace.py's parse_palace_output -- see that
# module's own module docstring for the format citation) with THREE
# propagating orders -- a reflection and two transmission diffraction
# orders -- through the real parser and this module's real check, both for
# a correct (lossless, sums to 1.0) case and a corrupted one.
# ---------------------------------------------------------------------------


def _build_grating_csv(corrupt_order1: bool) -> str:
    import csv
    import io

    # Power fractions by construction: reflection 0.1 (-10.0 dB), specular
    # transmission 0.6 (-2.2185 dB), +1 transmitted diffraction order 0.3
    # (-5.2288 dB) -- sums to 1.0 exactly (lossless). `corrupt_order1`
    # replaces the +1 order's magnitude with a near-numerical-zero value,
    # the same PATTERN as issue #221's motivating defect (a real,
    # non-negligible return silently lost).
    # Palace's own port-floquet-S.csv separates the two diffraction-order
    # indices with a SEMICOLON, not a comma -- confirmed against a real
    # Palace binary (issue #210); see simulation/palace.py's _MODE_RE
    # docstring for the citation. A comma here would make this fixture test
    # nothing, since parse_palace_output() would silently return
    # computed=False for every row.
    order1_db = "-80.0" if corrupt_order1 else "-5.2288"
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "f (GHz)",
            "|S[P1(0;0)TE][1]| (dB)",
            "arg(S[P1(0;0)TE][1]) (deg.)",
            "|S[P2(0;0)TE][1]| (dB)",
            "arg(S[P2(0;0)TE][1]) (deg.)",
            "|S[P2(1;0)TE][1]| (dB)",
            "arg(S[P2(1;0)TE][1]) (deg.)",
        ]
    )
    writer.writerow(["10.000000e+00", "-10.0", "0.0", "-2.2185", "0.0", order1_db, "0.0"])
    return buf.getvalue()


def test_palace_integration_correct_grating_result_balances():
    csv_text = _build_grating_csv(corrupt_order1=False)
    parsed = parse_palace_output(csv_text)
    assert parsed.get("computed") is True, (
        f"parse_palace_output did not recognize any mode column -- "
        f"csv_text={csv_text!r} parsed={parsed!r}"
    )
    result = check_palace_result(parsed, lossless=True)
    assert "power_balance" in result, f"check_palace_result returned: {result!r}"
    assert result["power_balance"][0]["power_sum"] == pytest.approx(1.0, abs=1e-3)
    assert result["all_ok"] is True


def test_palace_integration_corrupted_grating_order_is_flagged():
    """The regression case this ticket asks for: a realistic multi-order
    Palace-shaped CSV, run through the REAL parser
    (simulation.palace.parse_palace_output) and this module's REAL check,
    where one propagating diffraction order's return was silently lost --
    the same pattern as issue #221's motivating defect."""
    csv_text = _build_grating_csv(corrupt_order1=True)
    parsed = parse_palace_output(csv_text)
    assert parsed.get("computed") is True, (
        f"parse_palace_output did not recognize any mode column -- "
        f"csv_text={csv_text!r} parsed={parsed!r}"
    )
    result = check_palace_result(parsed, lossless=True)
    assert "power_balance" in result, f"check_palace_result returned: {result!r}"
    row = result["power_balance"][0]
    assert row["ok"] is False
    assert row["power_sum"] == pytest.approx(0.7, abs=1e-3)
    assert result["all_ok"] is False
    assert any("CHEAPEST CHECK" in w for w in result["warnings"])


def test_palace_integration_specular_only_view_would_have_looked_fine():
    """Contrast: `parsed["specular"]` (S11/S21 only) does NOT include the
    (1,0) transmission order at all, in EITHER the correct or corrupted
    CSV -- so a check built only from `specular` cannot see this defect
    change anything (it never had the missing order in the first place).
    This is exactly the ticket's warning about balancing only S11/S21 on a
    real grating: checking `modes` (as check_palace_result does) is what
    makes this defect visible at all."""
    good_csv = _build_grating_csv(corrupt_order1=False)
    bad_csv = _build_grating_csv(corrupt_order1=True)
    parsed_good = parse_palace_output(good_csv)
    parsed_bad = parse_palace_output(bad_csv)
    assert parsed_good.get("computed") is True, f"csv_text={good_csv!r} parsed={parsed_good!r}"
    assert parsed_bad.get("computed") is True, f"csv_text={bad_csv!r} parsed={parsed_bad!r}"
    assert "specular" in parsed_good, f"parsed_good={parsed_good!r}"
    assert "specular" in parsed_bad, f"parsed_bad={parsed_bad!r}"
    # Polarization-qualified keys (issue #227's fix for #221's own motivating
    # collision bug) -- both fixtures only exercise TE, so S11_TE/S21_TE.
    assert parsed_good["specular"].keys() == parsed_bad["specular"].keys() == {"S11_TE", "S21_TE"}
    assert (
        parsed_good["specular"]["S21_TE"] == parsed_bad["specular"]["S21_TE"]
    )  # unchanged either way
