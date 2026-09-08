"""Reference cases for validating simulator adapters (issue #144).

An adapter's own unit tests use hand-built fakes: they confirm the adapter
writes the right input deck and correctly parses output it is handed. That
says nothing about whether a real solve produces physically correct numbers.

In plain terms: those tests check that we can talk to the solver, not that
the solver told us the truth and we read it correctly. Those are different
claims, and only the second one justifies the `SIMULATED` provenance tag --
CONTEXT.md's evidence hierarchy ranks *validated* simulation second only to
measurement.

Three of the four cases below have now been checked that way (see the status
note further down); the fourth has not.

A reference case is a problem whose right answer is published and independent
of this codebase, so running it end to end says something a fake cannot: that
the deck we generate, the solver, and the parser together produce physics.

**The canonical first case is a half-wave dipole**, because its input
impedance is one of the most reproduced numbers in antenna engineering. A thin
half-wave dipole in free space presents about 73 + j42.5 ohms at its feed --
in plain terms, it looks like a 73-ohm resistor in series with a small
inductor, which is why 75-ohm coaxial cable exists and why practical dipoles
are trimmed slightly short to cancel that leftover inductance.

**Status: three of the four cases HAVE now been executed** against a real
solver -- pymeep 1.34.0, installed from conda-forge exactly as this repo's
own Dockerfile does it. `free-standing-resistive-sheet-10ghz` returned
0.4971 against an exact 0.5, and `salisbury-screen-10ghz` returned 1.0000 at
the design frequency and agreed with the independent closed-form model in
`rf_tools/absorber.py` to within 0.001 across 6-14 GHz. The third,
`free-standing-resistive-sheet-two-port-10ghz`, is the same sheet posed
THROUGH the committed adapter and scored by the design loop's two-port
arithmetic rather than by a hand-built simulation; it returned 0.4971 with
R = 0.2899 and T = 0.2130. All three are recorded in
`docs/meep-absorber-validation.md` with the numbers and how to re-run them.

That is the first time anything in this repository has been validated
against physics rather than against a fake, and it is what the `SIMULATED`
provenance tag has been claiming all along.

`half-wave-dipole-300mhz` is still unexecuted: it needs NEC2++, which this
repo's Dockerfile builds but CI does not. The expected values there remain
transcribed from the citation, and the runner below still skips when the
binary is absent.

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
    "FREE_SHEET_CHARACTERISTIC_LENGTH_M",
    "FREE_SHEET_RESOLUTION_PX_PER_A",
    "MATCHED_SHEET_RESISTANCE_OHM_SQ",
    "REFERENCE_CASES",
    "Discrepancy",
    "ExpectedValue",
    "ReferenceCase",
    "check_reference_case",
    "free_standing_sheet_geometry",
    "half_wave_dipole_geometry",
]

_C = 299_792_458.0
_ETA0_OHM = 376.730313412

#: Half the impedance of free space. The ONE sheet resistance at which a bare
#: film hanging in air absorbs its closed-form maximum of exactly one half.
MATCHED_SHEET_RESISTANCE_OHM_SQ = _ETA0_OHM / 2

#: Meep's characteristic length for the free-standing-sheet geometry below --
#: 1 mm, the same `a` the other absorber runs use. It is not part of the
#: geometry dict because the adapter takes it as its own argument, but a
#: runner needs it and it belongs next to the geometry it goes with.
FREE_SHEET_CHARACTERISTIC_LENGTH_M = 1e-3

#: Grid resolution in pixels per `a`, i.e. per millimetre. At 60 a 0.1 mm
#: sheet is six pixels thick -- enough for the absorbed total, NOT enough to
#: split reflection from transmission accurately; see the two-port case's
#: tolerance rationales for what that costs and why it is stated rather than
#: papered over.
FREE_SHEET_RESOLUTION_PX_PER_A = 60


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
    #: Which adapter can pose this case. A case is only meaningful to the
    #: solver its geometry is written for: the dipole's wire list means
    #: nothing to an FDTD grid, and an absorber stack means nothing to a
    #: thin-wire method-of-moments code. Runners MUST filter on this rather
    #: than iterating every case -- without it the NEC2 runner would hand a
    #: Salisbury screen's empty wire list to nec2++ the moment that binary
    #: appeared on PATH, and "solve this absorber as a wire antenna" is a
    #: question with no sensible answer.
    solver: str = "NEC2"


def half_wave_dipole_geometry(
    frequency_hz: float,
    *,
    length_wavelengths: float = 0.5,
    radius_wavelengths: float = 1e-5,
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
                "x1_m": 0.0,
                "y1_m": 0.0,
                "z1_m": -half,
                "x2_m": 0.0,
                "y2_m": 0.0,
                "z2_m": half,
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
            "theta_start_deg": 0.0,
            "theta_step_deg": 5.0,
            "theta_count": 37,
            "phi_start_deg": 0.0,
            "phi_step_deg": 90.0,
            "phi_count": 1,
        },
    }


def free_standing_sheet_geometry(
    frequency_hz: float = 10e9,
    *,
    sheet_resistance_ohm_sq: float = MATCHED_SHEET_RESISTANCE_OHM_SQ,
    sheet_thickness_m: float = 0.1e-3,
    characteristic_length_m: float = FREE_SHEET_CHARACTERISTIC_LENGTH_M,
    resolution_px_per_a: int = FREE_SHEET_RESOLUTION_PX_PER_A,
) -> dict[str, Any]:
    """A bare resistive film hanging in free space, posed for `simulation.meep`.

    Unlike the dipole above, this geometry is written in the shape
    `simulation.meep.run_meep_simulation` actually consumes, so the case can
    be driven through the COMMITTED adapter rather than through a
    hand-assembled simulation. That is the point of the two-port case below:
    `verification/meep_absorber_validation.py` builds its own `mp.Simulation`
    on purpose, so that the physics check does not assume the adapter is
    right -- which leaves the adapter itself unchecked on this problem. This
    closes it from the other side.

    THE LAYOUT along z, in millimetres, for a 70 mm cell:

        -35 |<-PML 10->| src -23 | refl -19 | sheet 0 | tran +21 |<-PML->| +35

    Every plane has a job and a reason for where it sits. The source stands
    clear of the absorbing layer so the pulse is fully formed before it is
    measured; the reflection plane sits between source and sheet so the wave
    crosses it twice (out, then back again); the transmission plane sits on
    the far side of the sheet and clear of the far PML, so what crosses it is
    only what got THROUGH. `reference_monitor_center_m` is deliberately the
    reflection plane itself: reflectance is normalised against what arrived
    at the plane it is measured on, which is the recipe
    `verification/meep_absorber_validation.py`'s `_reflectance_1d` uses.

    THE SHEET IS DECLARED BY ITS SHEET RESISTANCE, not by a conductivity,
    because that drives the adapter's own ohms-per-square conversion
    (`sigma = 1/(Rs*t)`) rather than routing around it. Issue #230 was
    exactly this defect: a sheet modelled as ideal perfect metal, which
    reflects everything and absorbs nothing however it was designed.

    *In plain terms: a thin grey film stretched across the tube the wave
    travels down. Some of the wave bounces off it, some carries on through,
    and the rest is turned into heat. The three planes are where we stand to
    count each share.*

    Transverse extent is +/-1 m -- vastly larger than the (zero-width) cell,
    so the sheet spans it completely and the structure is a continuous film
    rather than an element floating in the middle of one.
    """
    half_cell_m = 35e-3
    pml_m = 10e-3
    inner_edge_m = -half_cell_m + pml_m
    return {
        "cell_size_m": [0.0, 0.0, 2 * half_cell_m],
        "pml_thickness_m": pml_m,
        "mesh_cell_size_m": characteristic_length_m / resolution_px_per_a,
        # In `conductors`, not `materials`, deliberately: the adapter's
        # reference run omits conductors and keeps materials, so the sheet
        # has to be a conductor for the baseline run to be an empty cell.
        # Listed as a material it would be present in BOTH runs and there
        # would be nothing to measure the structure against.
        "conductors": [
            {
                "shape": "box",
                "p1_m": [-1.0, -1.0, -sheet_thickness_m / 2],
                "p2_m": [1.0, 1.0, sheet_thickness_m / 2],
                "sheet_resistance_ohm_sq": sheet_resistance_ohm_sq,
                "thickness_m": sheet_thickness_m,
            }
        ],
        "port": {
            "center_m": [0.0, 0.0, inner_edge_m + 2e-3],
            "size_m": [0.0, 0.0, 0.0],
            "direction": "z",
            "component": "Ex",
            "frequency_hz": frequency_hz,
            "fractional_bandwidth": 0.2,
        },
        "reflection_monitor_center_m": [0.0, 0.0, inner_edge_m + 6e-3],
        "reference_monitor_center_m": [0.0, 0.0, inner_edge_m + 6e-3],
        "transmission_monitor_center_m": [0.0, 0.0, half_cell_m - pml_m - 4e-3],
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

_SALISBURY = (
    "Salisbury screen: a 377 ohm/sq resistive sheet a quarter wavelength above a "
    "ground plane. Standard textbook absorber (e.g. Munk, Frequency Selective "
    "Surfaces, ch. 9); the quarter-wave spacer transforms the short at the ground "
    "plane into an open circuit, leaving a sheet matched to free space."
)
_FREE_SHEET = (
    "Free-standing resistive sheet at normal incidence: a shunt Rs across free "
    "space. Z = Rs || eta0, Gamma = (Z-eta0)/(Z+eta0), A = 1 - |Gamma|^2 - "
    "|1+Gamma|^2, maximised at exactly 0.5 when Rs = eta0/2 = 188.365 ohm/sq."
)

SALISBURY_SCREEN = ReferenceCase(
    case_id="salisbury-screen-10ghz",
    description=(
        "Salisbury screen at 10 GHz: 376.73 ohm/sq sheet, 7.494 mm air spacer, "
        "ground plane. The canonical absorber, and the case that exercises a "
        "periodic boundary, a finite-conductivity sheet and a ground plane at "
        "once. EXECUTED against Meep 1.34.0 -- see this module's status note."
    ),
    frequency_hz=10e9,
    solver="MEEP",
    geometry={},  # posed by verification/meep_absorber_validation.py
    expected=(
        ExpectedValue(
            name="absorptance",
            value=1.0,
            tolerance=0.02,
            unit="fraction",
            citation=_SALISBURY,
            tolerance_rationale=(
                "A matched sheet over a quarter-wave spacer absorbs everything at "
                "the design frequency in theory. Real runs land just under: an FDTD "
                "grid discretises the spacer, and a sheet of finite thickness is not "
                "quite the zero-thickness ideal. A measured 0.9917 at resolution 12 "
                "px/mm and 1.0000 at 60 px/mm bracket the convergence; +/-0.02 "
                "passes a correct solve at usable resolution while still failing any "
                "model whose sheet does not dissipate."
            ),
        ),
    ),
)

FREE_STANDING_RESISTIVE_SHEET = ReferenceCase(
    case_id="free-standing-resistive-sheet-10ghz",
    description=(
        "Free-standing 188.365 ohm/sq sheet at 10 GHz, no ground plane. Its peak "
        "absorptance is exactly 0.5 -- an unusually sharp check, because the value "
        "is a closed-form maximum rather than an approximation. EXECUTED against "
        "Meep 1.34.0, which returns 0.4971 at the committed runner's mesh (and "
        "0.4999 at the finer one the first sweep used -- see "
        "docs/meep-absorber-validation.md case 1, which quotes both rather than "
        "picking the flattering one)."
    ),
    frequency_hz=10e9,
    solver="MEEP",
    geometry={},
    expected=(
        ExpectedValue(
            name="absorptance",
            value=0.5,
            tolerance=0.01,
            unit="fraction",
            citation=_FREE_SHEET,
            tolerance_rationale=(
                "The 0.5 maximum is exact, so the tolerance covers discretisation "
                "only. A model that treats conductors as lossless perfect metal "
                "returns 0 here and fails by a mile, which is the point: this case "
                "catches the exact defect #230 recorded."
            ),
        ),
    ),
)


_FREE_SHEET_SPLIT = (
    "Same shunt-Rs network as above, read one term at a time: at Rs = eta0/2 "
    "the sheet impedance in parallel with free space is eta0/3, so "
    "Gamma = -1/2 exactly, R = |Gamma|^2 = 1/4 and T = |1+Gamma|^2 = 1/4. The "
    "power splits 25/25/50 -- a quarter back, a quarter through, a half into "
    "heat -- and that split is what makes the one-port collapse's "
    "overstatement computable in advance."
)

FREE_STANDING_RESISTIVE_SHEET_TWO_PORT = ReferenceCase(
    case_id="free-standing-resistive-sheet-two-port-10ghz",
    description=(
        "The same free-standing 188.365 ohm/sq sheet at 10 GHz, but posed "
        "THROUGH the committed adapter and scored by the loop's two-port "
        "arithmetic (A = 1 - R - T), rather than by a hand-built simulation. "
        "Its sibling case above validates the physics while deliberately "
        "bypassing the adapter; this one validates the path a real design "
        "run actually takes: run_meep_simulation, then "
        "orchestration/design_loop.py's port-count dispatch. Run by "
        "verification/meep_two_port_absorption_check.py; EXECUTED against "
        "Meep 1.34.0, which returned A = 0.4971 (R = 0.2899, T = 0.2130). "
        "See docs/meep-absorber-validation.md case 4."
    ),
    frequency_hz=10e9,
    solver="MEEP",
    geometry=free_standing_sheet_geometry(10e9),
    expected=(
        ExpectedValue(
            name="absorptance",
            value=0.5,
            tolerance=0.01,
            unit="fraction",
            citation=_FREE_SHEET,
            tolerance_rationale=(
                "The 0.5 maximum is exact, so this band covers discretisation "
                "only, and it is the SAME +/-0.01 the hand-built sibling case "
                "carries -- deliberately, because routing the identical "
                "problem through the adapter and the loop must not need a "
                "looser standard to pass. The measured 0.4971 sits at three "
                "tenths of the band. It is not loose: a model that treats "
                "conductors as lossless perfect metal returns 0 here (defect "
                "#230), and the one-port collapse A = 1 - R returns 0.7101, "
                "both failing by a wide margin."
            ),
        ),
        ExpectedValue(
            name="reflectance",
            value=0.25,
            tolerance=0.06,
            unit="fraction",
            citation=_FREE_SHEET_SPLIT,
            tolerance_rationale=(
                "SIX TIMES the absorptance band, and that is a real finding "
                "rather than a tuned number. R and T are each far less "
                "converged than their difference from one: at this mesh the "
                "run gives R = 0.2899 (16% high) and T = 0.2130 (15% low), "
                "errors that are anti-correlated and very nearly cancel in "
                "1 - R - T. In plain terms, the grid is good at counting how "
                "much power vanished into the sheet and much worse at saying "
                "which side of it the surviving power went. +/-0.06 still "
                "catches what this case is for: a transmittance off by the "
                "factor of two a wrong normalisation plane produces (#240) "
                "lands at 0.5 or 0.125, a missing sheet at R = 0, and a "
                "perfect-metal sheet at R = 1."
            ),
        ),
        ExpectedValue(
            name="transmittance",
            value=0.25,
            tolerance=0.06,
            unit="fraction",
            citation=_FREE_SHEET_SPLIT,
            tolerance_rationale=(
                "The same six-times band, for the same reason and measured "
                "on the same run: T = 0.2130 against an exact 0.25. Asserted "
                "at all -- rather than left to the absorptance total -- "
                "because T is the quantity #240 added and #243 depends on, "
                "and a transmittance that is silently zero would still let "
                "A = 1 - R - T look plausible while being the one-port "
                "collapse in disguise."
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
    SALISBURY_SCREEN.case_id: SALISBURY_SCREEN,
    FREE_STANDING_RESISTIVE_SHEET.case_id: FREE_STANDING_RESISTIVE_SHEET,
    FREE_STANDING_RESISTIVE_SHEET_TWO_PORT.case_id: FREE_STANDING_RESISTIVE_SHEET_TWO_PORT,
}


def _actual_value(name: str, result: dict[str, Any]) -> float | None:
    """Pull one expected quantity out of an adapter's result dict.

    Two shapes are read, because two different runners produce them. The
    impedance/gain names come from a NEC2 result. The three power names --
    `absorptance`, `reflectance`, `transmittance` -- are read from the
    record `orchestration/design_loop.py`'s SIMULATION step writes, verbatim
    and with its own key names, so a MEEP case can be checked against
    exactly what the loop recorded rather than against a shim rebuilt from
    it. A shim is a place for a transcription error to hide, and this whole
    module exists to catch transcription errors.
    """
    impedance = result.get("impedance") or {}
    if name == "input_resistance":
        return _as_float(impedance.get("resistance_ohms"))
    if name == "input_reactance":
        return _as_float(impedance.get("reactance_ohms"))
    if name == "gain_dbi":
        return _as_float(result.get("gain_dbi"))
    if name in _POWER_SPECTRUM_KEYS:
        return _single_point(result.get(_POWER_SPECTRUM_KEYS[name]))
    raise ValueError(f"no accessor for expected value {name!r}")


#: Expected-value name -> the key the design loop records it under. The
#: loop calls absorption `absorption`; a reference case calls the published
#: quantity `absorptance`. The mapping is stated once, here, rather than by
#: renaming either side to match the other.
_POWER_SPECTRUM_KEYS = {
    "absorptance": "absorption",
    "reflectance": "reflectance",
    "transmittance": "transmittance",
}


def _single_point(value: Any) -> float | None:
    """One number out of a spectrum the loop recorded as a list.

    A reference case names ONE frequency, so a run answering it must have
    been asked for one frequency (`nfreq=1`). A longer spectrum is not
    silently reduced -- taking the first point of a nine-point sweep would
    check the band edge against the design frequency's published answer and
    call it a pass. Returning None makes it a discrepancy, which is what it
    is.
    """
    if isinstance(value, (list, tuple)):
        return _as_float(value[0]) if len(value) == 1 else None
    return _as_float(value)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def check_reference_case(case: ReferenceCase, result: dict[str, Any]) -> tuple[Discrepancy, ...]:
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
