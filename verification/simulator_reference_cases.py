"""Reference cases for validating simulator adapters (issue #144).

The simulator adapters are tested against hand-built fakes: the tests confirm
an adapter writes the right input deck and correctly parses output it is
handed. Nothing confirms that a real solve produces physically correct
numbers.

In plain terms: we test that we can talk to the solver, not that the solver
told us the truth and we read it correctly. Those are different claims, and
only the second one justifies the `SIMULATED` provenance tag -- CONTEXT.md's
evidence hierarchy ranks *validated* simulation second only to measurement,
and today nothing performs that validation.

A reference case is a problem whose right answer is published and independent
of this codebase, so running it end to end says something a fake cannot: that
the deck we generate, the solver, and the parser together produce physics.

**The canonical first case is a half-wave dipole**, because its input
impedance is one of the most reproduced numbers in antenna engineering. A thin
half-wave dipole in free space presents about 73 + j42.5 ohms at its feed --
in plain terms, it looks like a 73-ohm resistor in series with a small
inductor, which is why 75-ohm coaxial cable exists and why practical dipoles
are trimmed slightly short to cancel that leftover inductance.

**Honest status: none of these cases has been executed.** No solver binary is
installed in the environment this was written in, and CI installs none either
(every full-wave solver here needs a manual or conda build -- see README.md).
The expected values are transcribed from the cited references, and the runner
below skips when the binary is absent. The first real run is therefore
unproven, exactly like `simulation/hfss.py` and the distributor clients. What
this module removes is the excuse that there was nothing to run.

Tolerances are engineering judgement, not published error bars: a real NEC2
solve of a finite-radius, finitely-segmented wire will not reproduce the
infinitesimally-thin analytic ideal exactly, and the bands below are set wide
enough to pass a correct implementation while still failing a wrong one (a
sign error, a units error, a mis-parsed column -- the failures that actually
happen). Each is annotated with why it is the width it is.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "REFERENCE_CASES",
    "Discrepancy",
    "ExpectedValue",
    "ReferenceCase",
    "check_reference_case",
    "half_wave_dipole_geometry",
]

_C = 299_792_458.0


@dataclass(frozen=True)
class ExpectedValue:
    """One published quantity, its tolerance, and where the number comes from."""

    name: str
    value: float
    tolerance: float
    unit: str
    citation: str
    tolerance_rationale: str = ""

    def matches(self, actual: float) -> bool:
        return abs(actual - self.value) <= self.tolerance


@dataclass(frozen=True)
class Discrepancy:
    """One expected value a run failed to reproduce."""

    name: str
    expected: float
    tolerance: float
    actual: float | None
    unit: str
    citation: str

    def __str__(self) -> str:
        got = "missing from the result" if self.actual is None else f"{self.actual:.4g}"
        return (
            f"{self.name}: expected {self.expected:.4g} +/- {self.tolerance:.4g} "
            f"{self.unit}, got {got}  [{self.citation}]"
        )


@dataclass(frozen=True)
class ReferenceCase:
    """A problem with a published answer, plus how to pose it to a solver."""

    case_id: str
    description: str
    frequency_hz: float
    geometry: dict[str, Any]
    expected: tuple[ExpectedValue, ...] = field(default=())


def half_wave_dipole_geometry(
    frequency_hz: float, *, length_wavelengths: float = 0.5, radius_wavelengths: float = 1e-5,
    segments: int = 21,
) -> dict[str, Any]:
    """A centre-fed straight dipole along z, in free space.

    `segments` is odd so there is an exact centre segment to excite -- feeding
    off-centre changes the impedance, which is precisely the kind of quiet
    setup error a reference case exists to catch.

    `radius_wavelengths` defaults to 1e-5, thin enough that the analytic
    thin-wire figures apply; a fatter wire lowers the reactance noticeably.
    """
    if segments % 2 == 0:
        raise ValueError("segments must be odd so the dipole has a centre segment to feed")
    wavelength = _C / frequency_hz
    half = length_wavelengths * wavelength / 2.0
    return {
        "wires": [
            {
                "tag": 1,
                "segments": segments,
                "x1_m": 0.0, "y1_m": 0.0, "z1_m": -half,
                "x2_m": 0.0, "y2_m": 0.0, "z2_m": half,
                "radius_m": radius_wavelengths * wavelength,
            }
        ],
        "ground_condition": "free_space",
        "excitation": {
            "wire_tag": 1,
            "segment": segments // 2 + 1,
            "voltage_real": 1.0,
            "voltage_imag": 0.0,
        },
        "pattern": {
            "theta_start_deg": 0.0, "theta_step_deg": 5.0, "theta_count": 37,
            "phi_start_deg": 0.0, "phi_step_deg": 90.0, "phi_count": 1,
        },
    }


_BALANIS = "Balanis, Antenna Theory 4th ed., sec. 8.4 (thin half-wave dipole)"
_BALANIS_D = "Balanis, Antenna Theory 4th ed., sec. 4.6 (half-wave dipole directivity)"

HALF_WAVE_DIPOLE = ReferenceCase(
    case_id="half-wave-dipole-300mhz",
    description=(
        "Centre-fed thin half-wave dipole in free space at 300 MHz. The most "
        "reproduced impedance figure in antenna engineering, and the standard "
        "first validation case for a method-of-moments wire solver."
    ),
    frequency_hz=300e6,
    geometry=half_wave_dipole_geometry(300e6),
    expected=(
        ExpectedValue(
            name="input_resistance",
            value=73.0,
            tolerance=6.0,
            unit="ohm",
            citation=_BALANIS,
            tolerance_rationale=(
                "The analytic 73 ohms assumes an infinitesimally thin wire. A "
                "segmented finite-radius model lands a few ohms off; +/-6 "
                "passes a correct solve while still failing anything that has "
                "the wrong feed point or the wrong length."
            ),
        ),
        ExpectedValue(
            name="input_reactance",
            value=42.5,
            tolerance=12.0,
            unit="ohm",
            citation=_BALANIS,
            tolerance_rationale=(
                "Reactance is far more sensitive to wire radius and "
                "segmentation than resistance is, so the band is wider. The "
                "sign still matters: a full-length half-wave dipole is "
                "inductive, and a negative reactance here means the model is "
                "resonating short, not that the tolerance was too tight."
            ),
        ),
        ExpectedValue(
            name="gain_dbi",
            value=2.15,
            tolerance=0.35,
            unit="dBi",
            citation=_BALANIS_D,
            tolerance_rationale=(
                "Directivity 1.643 = 2.15 dBi for the ideal case. A lossless "
                "NEC2 solve should sit very close; the band mostly absorbs "
                "pattern-sampling granularity."
            ),
        ),
    ),
)

#: Every reference case, by id. One for now -- the dipole is the case that
#: catches the most wrong implementations per unit of effort. A folded dipole
#: (~292 ohms, four times the dipole) and a quarter-wave monopole over perfect
#: ground (~36.5 + j21.25, exactly half the dipole) are the natural next two,
#: and both are cheap to add here once the first one has actually been run.
REFERENCE_CASES: dict[str, ReferenceCase] = {
    HALF_WAVE_DIPOLE.case_id: HALF_WAVE_DIPOLE,
}


def _actual_value(name: str, result: dict[str, Any]) -> float | None:
    """Pull one expected quantity out of an adapter's result dict."""
    impedance = result.get("impedance") or {}
    if name == "input_resistance":
        return _as_float(impedance.get("resistance_ohm"))
    if name == "input_reactance":
        return _as_float(impedance.get("reactance_ohm"))
    if name == "gain_dbi":
        return _as_float(result.get("gain_dbi"))
    raise ValueError(f"no accessor for expected value {name!r}")


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def check_reference_case(
    case: ReferenceCase, result: dict[str, Any]
) -> tuple[Discrepancy, ...]:
    """Every published value `result` failed to reproduce. Empty == passed.

    A quantity missing from the result is a discrepancy, not a skip: an
    adapter that silently returns no impedance has failed the case just as
    surely as one that returns the wrong number.
    """
    problems = []
    for expected in case.expected:
        actual = _actual_value(expected.name, result)
        if actual is None or not expected.matches(actual):
            problems.append(
                Discrepancy(
                    name=expected.name,
                    expected=expected.value,
                    tolerance=expected.tolerance,
                    actual=actual,
                    unit=expected.unit,
                    citation=expected.citation,
                )
            )
    return tuple(problems)
