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

THE LITERATURE CASES (issue #386) ARE A DIFFERENT ANIMAL, and the second
half of this module holds four of them. A closed-form case checks a solver
against algebra. A literature case checks it against **something somebody
built and measured**, reconstructed from a paper that publishes both the
fabricated geometry and the measured curve.

*In plain terms: the cases above ask "does the calculator add up?". The four
below ask "when somebody actually made this and pointed a radar at it, did
we predict what came back?" -- which is the only question that justifies
handing a `SIMULATED` number to somebody who is going to spend money on it.*

Three things follow, and each has machinery here rather than prose:

  * **The band is not ours to choose.** A literature case's pass band is
    `max(digitization error, the paper's own published simulated-versus-
    measured gap)` -- see `PassBand`. Where the paper publishes no such gap,
    the digitization error alone sets it and `PassBand.set_by` says so. An
    invented tolerance would make the whole exercise circular.
  * **Reflection and transmission are never combined.** `score_reference_case`
    keeps them in separate buckets and offers no total, because two errors of
    opposite sign cancel inside a sum and manufacture a false pass.
  * **UNRESOLVED is a real outcome.** Where the paper's information is
    insufficient, the reconstruction is ambiguous, or no adapter here can
    pose the problem, the answer is UNRESOLVED -- not a coin-flipped
    pass/fail that turns missing information into a verdict.

**Status of the four: one has been executed, three cannot be posed yet.**
`bandpass-fss-silver-paste-arxiv-2511.16777v1` runs today through this
repo's own ABCD primitives and FAILS its passband insertion loss by 1.3 dB
against the paper's own 1 dB gap -- a real finding with a named suspect, not
a green scaffold. The other three carry `unresolved_reason` strings saying
precisely what is missing. Full write-up, scope limits and the
artificial-magnetic-conductor gap: `docs/literature-validation-cases.md`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

__all__ = [
    "FREE_SHEET_CHARACTERISTIC_LENGTH_M",
    "FREE_SHEET_RESOLUTION_PX_PER_A",
    "LITERATURE_CASES",
    "MATCHED_SHEET_RESISTANCE_OHM_SQ",
    "REFERENCE_CASES",
    "Assumption",
    "CaseOutcome",
    "CaseScore",
    "Comparison",
    "Discrepancy",
    "ExpectedValue",
    "LiteratureSource",
    "PassBand",
    "QuantityKind",
    "Reconstruction",
    "ReferenceCase",
    "RunPin",
    "check_reference_case",
    "free_standing_sheet_geometry",
    "half_wave_dipole_geometry",
    "literature_expected_value",
    "score_reference_case",
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


class CaseOutcome(StrEnum):
    """What a scored run says about a case. Three words, not two.

    UNRESOLVED is the one that earns its keep. A case whose reconstruction is
    ambiguous, whose paper omits a load-bearing number, or which no adapter
    here can pose has not passed and has not failed -- and recording it as
    either turns missing information into a verdict somebody will later cite.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    UNRESOLVED = "UNRESOLVED"


class QuantityKind(StrEnum):
    """Which side of the surface a published quantity describes.

    The whole reason this exists: reflection and transmission errors of
    opposite sign cancel inside any total, so a surface that reflects far too
    much and transmits far too little can post a perfect absorbed fraction.
    Scoring them in separate buckets makes that arithmetic unavailable rather
    than merely discouraged.
    """

    REFLECTION = "reflection"
    TRANSMISSION = "transmission"
    OTHER = "other"


class Comparison(StrEnum):
    """How a published number is meant to be met.

    Papers state headline results as bounds at least as often as points --
    "PCR exceeding 95%", "less than 0.2% of the incident power is
    back-reflected", "15-20 dB rejection in the stop-band". Forcing a bound
    into a two-sided band rejects correct answers on the permitted side of
    it, which is its own species of false verdict.
    """

    WITHIN = "within"
    AT_LEAST = "at_least"
    AT_MOST = "at_most"


@dataclass(frozen=True)
class PassBand:
    """How wide a literature case's pass band is, and why exactly that wide.

    `max(digitization error, the paper's own published simulated-versus-
    measured gap)` -- never a number somebody chose because it made the case
    pass. The two inputs are kept as separate fields precisely so a reader
    can see which one is doing the work and argue with it.

    **Digitization error** is how accurately the number can be recovered from
    the paper at all: a fraction of a gridline interval when a curve has to be
    read off a figure, or the rounding of the quoted digits when the paper
    prints the value in its text. It is never zero and `digitization_basis`
    has to say which mechanism was used.

    **Published gap** is how far the paper's own simulation missed the paper's
    own measurement -- an accuracy bar taken from the literature instead of
    one we invented. `None` means the paper publishes no such comparison for
    this quantity, in which case the digitization error alone sets the band
    and `set_by` reports that.

    *In plain terms: how blurry the published number is, versus how badly the
    authors' own model missed their own bench. Whichever is worse is the
    accuracy we are entitled to demand.*
    """

    digitization_error: float
    digitization_basis: str
    published_gap: float | None = None
    published_gap_citation: str = ""

    def __post_init__(self) -> None:
        if not (self.digitization_error > 0.0) or not math.isfinite(self.digitization_error):
            raise ValueError(
                "digitization error must be a positive, finite number; got "
                f"{self.digitization_error!r}. Reading a published number has "
                "real uncertainty and this module refuses to record it as zero."
            )
        if not self.digitization_basis.strip():
            raise ValueError("digitization_basis must say how the error was estimated")
        if self.published_gap is not None:
            if self.published_gap < 0 or not math.isfinite(self.published_gap):
                raise ValueError(f"published_gap must be non-negative; got {self.published_gap!r}")
            if not self.published_gap_citation.strip():
                raise ValueError("a published gap must cite the sentence or figure it came from")

    @property
    def width(self) -> float:
        if self.published_gap is None:
            return self.digitization_error
        return max(self.digitization_error, self.published_gap)

    @property
    def set_by(self) -> str:
        """Which of the two inputs actually decided the width."""
        if self.published_gap is None or self.digitization_error >= self.published_gap:
            return "digitization"
        return "published-gap"


@dataclass(frozen=True)
class ExpectedValue:
    """One published quantity, its tolerance, and where the number comes from."""

    name: str
    value: float
    tolerance: float
    unit: str
    citation: str
    tolerance_rationale: str = ""
    #: Reflection or transmission -- see `QuantityKind`. `OTHER` is the
    #: default so the closed-form cases above keep working unchanged; the
    #: literature cases are required to classify every quantity.
    kind: QuantityKind = QuantityKind.OTHER
    #: Point value or published bound. See `Comparison`.
    comparison: Comparison = Comparison.WITHIN
    #: Where the tolerance came from, for a literature case. When present it
    #: is the single source of the width and `tolerance` must equal it.
    band: PassBand | None = None
    #: The key this quantity is read from in a result dict. Declaring it here
    #: keeps a new quantity from needing an edit to `_actual_value`'s
    #: name-to-field switch, which is exactly where a transcription error
    #: would hide.
    result_key: str = ""

    def __post_init__(self) -> None:
        if self.band is not None and self.tolerance != self.band.width:
            raise ValueError(
                f"{self.name}: tolerance {self.tolerance!r} contradicts its own "
                f"pass band, which is {self.band.width!r} wide "
                f"(set by {self.band.set_by}). Build literature expected values "
                "with literature_expected_value() so the width is computed once."
            )

    def matches(self, actual: float) -> bool:
        if self.comparison is Comparison.AT_LEAST:
            return actual >= self.value - self.tolerance
        if self.comparison is Comparison.AT_MOST:
            return actual <= self.value + self.tolerance
        return abs(actual - self.value) <= self.tolerance


def literature_expected_value(
    *,
    name: str,
    value: float,
    unit: str,
    citation: str,
    kind: QuantityKind,
    band: PassBand,
    rationale: str,
    comparison: Comparison = Comparison.WITHIN,
    result_key: str | None = None,
) -> ExpectedValue:
    """One published quantity whose tolerance is DERIVED from its pass band.

    The width is computed here and nowhere else, so the band and the
    tolerance cannot drift apart -- a comment claiming one number beside a
    field holding another is the failure this closes.

    `result_key` defaults to `name`, because for a literature case the two
    are the same string and repeating it is one more place to mistype.
    """
    return ExpectedValue(
        name=name,
        value=value,
        tolerance=band.width,
        unit=unit,
        citation=citation,
        tolerance_rationale=rationale,
        kind=kind,
        comparison=comparison,
        band=band,
        result_key=name if result_key is None else result_key,
    )


@dataclass(frozen=True)
class Assumption:
    """One load-bearing thing taken on faith, in CLAUDE.md's three parts.

    What is assumed, what it costs if that is wrong, and the cheapest way to
    find out. A case that fails with its assumptions recorded this way tells
    you where to look first; one without them just tells you it failed.
    """

    statement: str
    cost_if_wrong: str
    cheapest_check: str


@dataclass(frozen=True)
class LiteratureSource:
    """The paper a case reconstructs, and which of its curves is scored.

    `scored_against` names the specific figure, because a paper usually
    publishes several and they are not interchangeable. `excluded` names any
    curve deliberately NOT scored and says why -- the mistake it exists to
    prevent is comparing a flat, infinitely-repeating simulation against a
    measurement taken on a curved surface, which is a different physical
    problem and can produce either a false pass or a false fail.
    """

    arxiv_id: str
    version: str
    title: str
    scored_against: str
    excluded: str = ""

    @property
    def citation(self) -> str:
        return f"arXiv:{self.arxiv_id}{self.version} -- {self.title} ({self.scored_against})"


@dataclass(frozen=True)
class Reconstruction:
    """The geometry as rebuilt from the paper, and where that rebuilding guessed.

    `read_from_text` holds the dimensions the paper actually prints.
    `inferred` holds everything that had to be supplied from somewhere else --
    a datasheet, a drawing, a default. Keeping them apart is what makes the
    reconstruction falsifiable: a single merged list would let a guess pass
    for a quotation.
    """

    substrate: str
    read_from_text: tuple[str, ...]
    inferred: tuple[str, ...] = ()
    assumptions: tuple[Assumption, ...] = ()


@dataclass(frozen=True)
class RunPin:
    """The exact code a result was produced by, so it can be re-run later.

    For a case no adapter here can pose, this pins the code whose limits were
    checked to reach that conclusion -- so a reader can tell whether the gap
    has since closed rather than having to re-derive it. `note` says which of
    the two a given pin is.
    """

    solver: str
    solver_version: str
    adapter_module: str
    adapter_commit: str
    note: str = ""


@dataclass(frozen=True)
class CaseScore:
    """One case, scored. Reflection and transmission stay in separate buckets.

    There is deliberately no total, no mean and no aggregate error on this
    object. The moment one exists somebody reports it, and a pair of
    cancelling errors reads as a pass inside it -- which is the exact failure
    the separation is for.
    """

    case_id: str
    outcome: CaseOutcome
    reflection: tuple[Discrepancy, ...] = ()
    transmission: tuple[Discrepancy, ...] = ()
    other: tuple[Discrepancy, ...] = ()
    unresolved_reason: str = ""

    @property
    def listed(self) -> tuple[Discrepancy, ...]:
        """Every discrepancy, for printing. A concatenation, never a sum."""
        return self.reflection + self.transmission + self.other


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
    #: --- literature cases only (issue #386) ------------------------------
    #: The paper being reconstructed. `None` marks a closed-form case, and
    #: that is what `LITERATURE_CASES` filters on -- derived, so a new case
    #: cannot be added to one place and forgotten in the other.
    source: LiteratureSource | None = None
    #: The geometry as rebuilt, and where the rebuilding had to guess.
    reconstruction: Reconstruction | None = None
    #: Solver version and adapter commit, so a result traces to the code that
    #: produced it.
    run: RunPin | None = None
    #: Non-empty when this case cannot yield a verdict at all: the paper omits
    #: something load-bearing, the reconstruction is ambiguous, or no adapter
    #: here can pose the problem. `score_reference_case` returns UNRESOLVED
    #: and refuses to score, however good the result handed to it looks.
    unresolved_reason: str = ""
    #: The ceiling on anything this case can claim. Everything here is a
    #: solver result; none of it is a measurement of our own hardware.
    provenance: str = "SIMULATED"


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


# ==========================================================================
# The literature cases (issue #386)
#
# Four published metasurfaces, each with a fabricated geometry AND a measured
# curve. Read the module docstring first: the band arithmetic, the R/T
# separation and the UNRESOLVED outcome all exist for reasons stated there.
#
# ONE HAS BEEN EXECUTED. `bandpass-fss-silver-paste-arxiv-2511.16777v1` runs
# through this repo's own ABCD primitives, needs no external binary, and
# FAILS. The other three name what is missing instead of guessing at it.
# ==========================================================================


# --- 1. cross-polarisation converter for RCS reduction --------------------

_CPC_SOURCE = LiteratureSource(
    arxiv_id="2607.10687",
    version="v1",
    title=(
        "Chaudhry, Abdullah, Liaquat, Haider, Khan and Hasan, Design and "
        "Experimental Validation of a Multiband Cross-Polarization Conversion "
        "(CPC) Metasurface for Radar Cross Section (RCS) Reduction"
    ),
    scored_against=(
        "Fig. 6, the measured co- and cross-polarised reflection magnitudes, "
        "read at the three cross-polarisation conversion frequencies section "
        "III-D names in its text"
    ),
    excluded=(
        "Fig. 7(b)'s monostatic RCS curves. Those are a 144 mm x 144 mm finite "
        "panel measured against a 10 cm x 10 cm metal plate, and every "
        "periodic solver here models an infinite repeating cell -- the "
        "finite-aperture edge diffraction the paper itself blames for the "
        "shortfall is not in our model at all, so scoring against them would "
        "compare two different physical problems."
    ),
)

#: The paper's own two sets of frequencies. Kept as data rather than folded
#: into prose so the per-band gap below is arithmetic on published numbers,
#: not a figure somebody typed.
_CPC_SIMULATED_HZ = {"c_band": 6.66e9, "x_band": 9.75e9, "ku_band": 15.1e9}
_CPC_MEASURED_HZ = {"c_band": 7.8e9, "x_band": 11.7e9, "ku_band": 18.0e9}

_CPC_GAP_CITATION = (
    'section III-D: "A frequency offset of approximately 0.5-3 GHz is '
    "observed between simulated and measured CPC frequencies, with the "
    'deviation being most prominent in the Ku-band." The per-band number used '
    "here is that same comparison done arithmetically on the paper's own two "
    "sets of figures -- simulated 6.66 / 9.75 / 15.1 GHz in section III-A "
    "against measured 7.8 / 11.7 / 18 GHz in section III-D."
)

_CPC_DIGITIZATION = (
    "the three measured conversion frequencies are quoted in the body text to "
    "0.1 GHz, so the quoting alone contributes about +/-0.05 GHz; recovering "
    "the same peaks from Fig. 6, whose frequency axis spans 4-20 GHz with "
    "2 GHz major divisions, is good to roughly a tenth of a division. The "
    "larger of the two is used."
)


def _cpc_expected(band_name: str, label: str) -> ExpectedValue:
    measured = _CPC_MEASURED_HZ[band_name]
    simulated = _CPC_SIMULATED_HZ[band_name]
    gap = abs(measured - simulated)
    return literature_expected_value(
        name=f"cross_pol_resonance_{band_name}_hz",
        value=measured,
        unit="Hz",
        citation=_CPC_SOURCE.citation,
        kind=QuantityKind.REFLECTION,
        band=PassBand(
            digitization_error=0.2e9,
            digitization_basis=_CPC_DIGITIZATION,
            published_gap=gap,
            published_gap_citation=_CPC_GAP_CITATION,
        ),
        rationale=(
            f"The {label} band is the authors' own simulated-versus-measured "
            f"offset here: {gap / 1e9:.2f} GHz, measured {measured / 1e9:.2f} "
            f"GHz against simulated {simulated / 1e9:.2f} GHz. That is wider "
            "than the 0.2 GHz reading the figure costs, so the published gap "
            "sets the band. Say plainly what that buys: a band this wide -- "
            f"about {100 * gap / measured:.0f} percent of the frequency it "
            "sits at -- can only catch a gross error, a resonance landing in "
            "the wrong radar band or not appearing at all. It is nonetheless "
            "the accuracy the literature entitles us to demand, and inventing "
            "something tighter would make the whole check circular."
        ),
    )


CPC_METASURFACE_RCS = ReferenceCase(
    case_id="cpc-metasurface-rcs-arxiv-2607.10687v1",
    description=(
        "Single-layer cross-polarisation converter on 1.6 mm FR4, ground "
        "backed, 4-20 GHz. *A cross-polarisation converter reflects a wave "
        "back with its orientation rotated by a quarter turn; a radar looking "
        "for its own polarisation back then sees very little, which is one "
        "route to making an object harder to see.* Chosen first of the four "
        "because the authors publish their own measured-versus-simulated "
        "offset, giving an accuracy bar taken from the literature rather than "
        "one we invented, and because it is the only one of the four with "
        "measured oblique-incidence data. NOT RUN: the reconstruction is "
        "ambiguous -- see unresolved_reason."
    ),
    frequency_hz=11.7e9,
    solver="MEEP",
    geometry={
        "model": "bloch-periodic-reflection",
        "unit_cell_period_m": 7e-3,
        "incidence": "normal, x-polarised; the paper also sweeps 0-60 degrees",
        "substrate": {"material": "FR4", "eps_r": 4.4, "tan_delta": 0.02, "thickness_m": 1.6e-3},
        "ground_plane": "copper, modelled as PEC -- zero transmission by construction",
        "metal": {"material": "copper", "conductivity_s_m": 5.8e7, "thickness_m": 0.035e-3},
        "elements": (
            "two split-ring resonators plus a circular ring resonator at one "
            "corner, the anisotropy axes at 45 degrees to the incident "
            "polarisation"
        ),
        # Values verbatim from section II-B. Which symbol labels which
        # feature is NOT in the paper -- that is the whole of this case's
        # unresolved_reason, and the dict deliberately does not guess.
        "tabulated_symbols_mm": {
            "a": 6.0,
            "s": 2.5,
            "m": 1.5,
            "b": 0.58,
            "p": 1.0,
            "z": 7.0,
            "d": 2.0,
        },
    },
    source=_CPC_SOURCE,
    reconstruction=Reconstruction(
        substrate=(
            "FR4, eps_r = 4.4 and tan delta = 0.02, 1.6 mm thick, with a "
            "continuous copper ground plane behind it -- so the structure "
            "transmits nothing and everything it does happens in reflection"
        ),
        read_from_text=(
            "unit cell periodicity 7 mm in both lateral directions (section II-C)",
            "FR4 eps_r = 4.4, tan delta = 0.02, thickness 1.6 mm (sections II-B, II-C)",
            "copper conductivity 5.8e7 S/m, thickness 0.035 mm / 1 oz (section II-C)",
            "the seven optimised dimensions a, s, m, b, p, z, d (section II-B)",
            "simulated 4-20 GHz at 0.05 GHz resolution, Floquet ports, PEC ground",
            "20 x 20 elements, 144 mm x 144 mm prototype milled to +/-50 um",
        ),
        inferred=(
            "which feature each of a, s, m, b, p, z and d labels. The values "
            "are printed; the mapping is only on Fig. 1(d) as leader lines.",
            "the position and orientation of the corner circular ring relative "
            "to the two split rings, likewise a Fig. 1(d)-only fact.",
        ),
        assumptions=(
            Assumption(
                statement=(
                    "The ground plane is taken as a perfect electric conductor, "
                    "as the paper's own simulation setup states, rather than as "
                    "35 um of finite-conductivity copper."
                ),
                cost_if_wrong=(
                    "Almost nothing here: at 10 GHz the wave penetrates well "
                    "under a micrometre into copper, so 35 um is many skin "
                    "depths and the sheet behaves as a mirror. Recorded because "
                    "it is a modelling choice, not because it is in doubt."
                ),
                cheapest_check=(
                    "Re-run the same cell once with a finite-conductivity "
                    "ground and compare; the two should agree to well inside "
                    "the band above."
                ),
            ),
        ),
    ),
    run=RunPin(
        solver="MEEP",
        solver_version="pymeep 1.34.0, the build docs/meep-absorber-validation.md's runs used",
        adapter_module="simulation/meep.py",
        adapter_commit="127c8a5ee76ba82e80b2a0285bd78332895421bd",
        note=(
            "Pins the Bloch-periodic path this case is written against. NOT "
            "YET RUN -- the reconstruction is ambiguous, so there is nothing "
            "to run it on."
        ),
    ),
    unresolved_reason=(
        "The paper prints its seven optimised dimensions as a bare list -- "
        "a = 6 mm, s = 2.5 mm, m = 1.5 mm, b = 0.58 mm, p = 1 mm, z = 7 mm, "
        "d = 2 mm -- and never says which symbol labels which feature; that "
        "mapping exists only as leader lines on Fig. 1(d). Two split rings and "
        "a corner circular ring have well over seven independent dimensions "
        "between them, so the values cannot be attached to features from the "
        "text alone and the metallic pattern cannot be reconstructed uniquely. "
        "Anything drawn and solved here would be a plausible guess scored "
        "against somebody else's measurement, which is worse than no result: a "
        "pass would flatter a guess and a failure would indict the solver for "
        "our drawing. Closing it needs Fig. 1(d) read by eye against the value "
        "list, or the authors asked."
    ),
    expected=(
        _cpc_expected("c_band", "C"),
        _cpc_expected("x_band", "X"),
        _cpc_expected("ku_band", "Ku"),
    ),
)


# --- 2. bianisotropic Huygens' metasurface --------------------------------

_HUYGENS_SOURCE = LiteratureSource(
    arxiv_id="1812.05084",
    version="v1",
    title=(
        "Chen, Abdo-Sanchez, Epstein and Eleftheriades, Theory, design, and "
        "experimental verification of a reflectionless bianisotropic Huygens' "
        "metasurface for wide-angle refraction"
    ),
    scored_against=(
        "Fig. 18's measured specular reflection (0th reflected mode) for the "
        "reflected share, and section IV-B's measured scattered refraction "
        "efficiency at 20.6 GHz for the transmitted share"
    ),
    excluded=(
        "The far-field chamber's own 0th reflected mode, which the paper says "
        "cannot be measured reliably there because the receiving horn blocks "
        "it. The quasi-optical setup is the only place the specular reflection "
        "was actually characterised, so it is the only place this case reads "
        "it from."
    ),
)

HUYGENS_ASSUMED_EPS_R = 10.2
HUYGENS_ASSUMED_TAN_DELTA = 0.0023

BIANISOTROPIC_HUYGENS_REFRACTION = ReferenceCase(
    case_id="bianisotropic-huygens-refraction-arxiv-1812.05084v1",
    description=(
        "Three-layer bianisotropic Huygens' metasurface on Rogers RT/duroid "
        "6010, refracting a normally incident wave to 71.8 degrees at 20 GHz "
        "with near-zero reflection. *A Huygens' metasurface bends a beam by "
        "giving each patch of the sheet its own phase delay; the bianisotropy "
        "is the extra ingredient that stops the sheet reflecting while it "
        "bends.* Chosen second because it has the cleanest measured-versus-"
        "simulated overlay of the four -- both a specular-reflection null and "
        "a refraction efficiency, published as numbers. NOT RUN: see "
        "unresolved_reason."
    ),
    frequency_hz=20e9,
    solver="PALACE",
    geometry={
        "model": "floquet-periodic-transmission",
        "macro_period_m": 15.8e-3,
        "unit_cell_m": [1.58e-3, 1.58e-3],
        "cells_per_period": 10,
        "incidence": "normal; the designed refraction is the +1 Floquet mode at +71.8 degrees",
        "stack_m": [
            {"layer": "copper", "thickness_m": 18e-6, "pattern": "dogbone (top)"},
            {"layer": "RT/duroid 6010", "thickness_m": 0.635e-3},
            {"layer": "copper", "thickness_m": 18e-6, "pattern": "loaded dipole (middle)"},
            {"layer": "Rogers 2929 bondply", "thickness_m": 0.0508e-3},
            {"layer": "RT/duroid 6010", "thickness_m": 0.635e-3},
            {"layer": "copper", "thickness_m": 18e-6, "pattern": "dogbone (bottom)"},
        ],
        "total_thickness_m": 1.3208e-3,
        # Table I, verbatim, in millimetres: (Ltop, Wmid, Lbot) per cell.
        "table_i_mm": (
            (0.8382, 0.5334, 0.9144),
            (0.8382, 0.5334, 0.9144),
            (0.5334, 0.8153, 0.1067),
            (0.5334, 0.8153, 0.1067),
            (0.6858, 0.7391, 0.6553),
            (0.7027, 0.7772, 0.7772),
            (0.7143, 0.9449, 0.8077),
            (0.8382, 0.4191, 0.6096),
            (0.8105, 0.5029, 0.7544),
            (0.8001, 0.5334, 0.8382),
        ),
        "assumed_substrate": {
            "eps_r": HUYGENS_ASSUMED_EPS_R,
            "tan_delta": HUYGENS_ASSUMED_TAN_DELTA,
            "source": "Rogers datasheet, characterised at 10 GHz -- NOT stated in the paper",
        },
    },
    source=_HUYGENS_SOURCE,
    reconstruction=Reconstruction(
        substrate=(
            "three 18 um (1/2 oz) copper layers etched on two 0.635 mm (25 mil) "
            "Rogers RT/duroid 6010 substrates bonded with a 0.0508 mm (2 mil) "
            "Rogers 2929 bondply, 1.3208 mm (52 mil) overall -- about a "
            "wavelength-eleventh at 20 GHz"
        ),
        read_from_text=(
            "unit cell 1.58 mm x 1.58 mm, ten cells to a 15.8 mm macro-period (section III-B)",
            "three metal layers: dogbone, loaded dipole, dogbone (Figs. 9 and 10)",
            "Table I's Ltop, Wmid and Lbot for each of the ten cells, 0.1067-0.9449 mm",
            "copper 18 um; RT/duroid 6010 0.635 mm x2; Rogers 2929 bondply 0.0508 mm",
            "design frequency 20 GHz, normal incidence refracted towards +71.8 degrees",
            "HFSS Floquet-port periodic simulation; 93% simulated refraction efficiency",
        ),
        inferred=(
            "RT/duroid 6010's relative permittivity and loss tangent. The "
            "paper never states either; the Rogers datasheet figures are used "
            "-- see the assumption below, which is the whole of the ticket's "
            "10 GHz-at-20 GHz caveat.",
            "every dogbone dimension other than Ltop and Lbot, and every "
            "loaded-dipole dimension other than Wmid: trace widths, arm widths "
            "and the dipole's loading gap appear only as labelled leader lines "
            "on Fig. 10 and are in no table.",
        ),
        assumptions=(
            Assumption(
                statement=(
                    "RT/duroid 6010 is taken as eps_r = 10.2 and tan delta = "
                    "0.0023, the Rogers datasheet figures characterised at "
                    "10 GHz, applied unchanged at this case's 20 GHz. The paper "
                    "states neither number anywhere."
                ),
                cost_if_wrong=(
                    "Every electrical length in the stack scales as the square "
                    "root of the permittivity, so a few percent of permittivity "
                    "error moves the resonance by a few hundred megahertz -- the "
                    "same size as the 0.8 GHz simulated-versus-measured shift "
                    "this case scores. A wrong permittivity could therefore "
                    "account for the entire quantity being measured, and a pass "
                    "would mean nothing."
                ),
                cheapest_check=(
                    "Measure a bare 0.635 mm 6010 coupon in a resonant cavity or "
                    "a stripline resonator near 20 GHz, or ask Rogers for the "
                    "20 GHz characterisation; either settles it without solving "
                    "anything."
                ),
            ),
        ),
    ),
    run=RunPin(
        solver="Palace",
        solver_version=(
            "Palace commit 43a5483 (schema 1-6-0), the build this repo's "
            "Dockerfile compiles and docs/palace-floquet-validation.md records"
        ),
        adapter_module="simulation/palace.py",
        adapter_commit="0f6db6606afa1712f1b2c4a993d9e60a774158fe",
        note=(
            "Pins the Floquet-port path this case is written against. NOT YET "
            "RUN: no palace binary was on PATH in the session that wrote the "
            "case, and the reconstruction is incomplete regardless."
        ),
    ),
    unresolved_reason=(
        "Table I fixes only three numbers per unit cell -- Ltop, Wmid and Lbot "
        "-- and the paper is explicit that these are the parameters it uses to "
        "tune each layer's admittance. Every other dimension of the two "
        "dogbones and the loaded dipole, including the trace widths that set "
        "how sharply each element resonates, appears only as labelled leader "
        "lines on Fig. 10. The three tuned lengths alone do not determine the "
        "shunt admittances Fig. 8 demands, so a reconstruction from the text "
        "would be ten guessed elements deep. Separately, the substrate "
        "permittivity is not in the paper at all and is being supplied from a "
        "datasheet at half the operating frequency. Either gap alone would "
        "make a verdict here uninterpretable; both together certainly do."
    ),
    expected=(
        literature_expected_value(
            name="specular_reflection_resonance_hz",
            value=20.6e9,
            unit="Hz",
            citation=_HUYGENS_SOURCE.citation,
            kind=QuantityKind.REFLECTION,
            band=PassBand(
                digitization_error=0.1e9,
                digitization_basis=(
                    "Fig. 18's frequency axis runs 17.5-22.5 GHz with 0.5 GHz "
                    "major divisions and the null is broad, so locating its "
                    "minimum is good to roughly a fifth of a division"
                ),
                published_gap=0.8e9,
                published_gap_citation=(
                    "Fig. 18 annotates the simulated null at 19.8 GHz and the "
                    'measured null at 20.6 GHz; section IV-A: "Examining the '
                    "measured specular reflections, a shift of the resonant "
                    'frequency to 20.6 GHz can be seen."'
                ),
            ),
            rationale=(
                "The authors' own 0.8 GHz shift between their simulated and "
                "measured nulls sets this band, being eight times what reading "
                "Fig. 18 costs. They attribute the shift to fabrication error "
                "and material parameters -- and the material parameter in "
                "question is the very permittivity this case has to assume, "
                "which is why that assumption is recorded rather than absorbed. "
                "The DEPTH of the null is deliberately not scored: the paper "
                'states it as a bound ("less than 0.2% of the incident power '
                'is back-reflected", about -27 dB) and never prints a numeric '
                "simulated trough, so there is no published depth gap to build "
                "a band from."
            ),
        ),
        literature_expected_value(
            name="refraction_efficiency",
            value=0.80,
            unit="fraction of scattered power",
            citation=_HUYGENS_SOURCE.citation,
            kind=QuantityKind.TRANSMISSION,
            band=PassBand(
                digitization_error=0.04,
                digitization_basis=(
                    "the efficiencies are quoted in the text as whole "
                    "percentages, worth about +/-0.005; recovering the same "
                    "quantity from Fig. 15's 0-to-1 efficiency axis, drawn with "
                    "0.2 divisions, costs about 0.04, and the larger is used"
                ),
                published_gap=0.13,
                published_gap_citation=(
                    'section IV-B: "the scattered refraction efficiency at '
                    "20.6 GHz is calculated to be approximately 80%. While it "
                    'is lower than the simulated result of 93%..."'
                ),
            ),
            rationale=(
                "The paper's own 93%-simulated against 80%-measured is a "
                "13-point gap, three times what reading Fig. 15 costs, so the "
                "published gap sets the band. Scored SEPARATELY from the "
                "reflection quantity above and never summed with it: this "
                "surface is meant to reflect nothing and refract everything, so "
                "a reconstruction that reflected far too much and refracted far "
                "too little would post a perfectly respectable total while "
                "being wrong twice."
            ),
        ),
    ),
)


# --- 3. band-pass FSS, silver paste dispensed on 3D-printed ABS -----------

_FSS_SOURCE = LiteratureSource(
    arxiv_id="2511.16777",
    version="v1",
    title=(
        "Tehranian, Budhu, Perkowski, Sookdeo, Church, Harris and Pfeiffer, "
        "Design, Fabrication, and Measurement of a Hemispherical Multi-Layer "
        "Band-Pass Frequency Selective Surface"
    ),
    scored_against=(
        "Fig. 17's PLANAR measured transmission -- the Gaussian-beam "
        "post-processed curve -- laid over the simulated unit-cell response, "
        "plus the passband and stop-band figures the abstract and section VI "
        "quote for it"
    ),
    excluded=(
        "Fig. 17's HEMISPHERICAL curve, and Fig. 16 in its entirety. The "
        "hemispherical sample is the same unit cell wrapped onto a 150 mm dome; "
        "the model here is a flat, infinitely repeating cell, so scoring one "
        "against the other would compare two different physical problems and "
        "could return either a false pass or a false fail. Fig. 16 is the same "
        "measurement before the Gaussian-beam post-processing, and its ripple "
        "is diffraction off the sample edges rather than anything the surface "
        "does."
    ),
)

#: The paper's own equivalent-circuit target for the cascaded surface
#: (section II-B): two capacitive layers of 78 fF with a 1.66 nH inductive
#: wire-grid between them. These are the numbers the hexagonal geometries in
#: Table I were sized to realise, and Fig. 3 shows the paper's own circuit
#: model against its own full-wave result for exactly this pair.
FSS_LAYER_CAPACITANCE_F = 78e-15
FSS_LAYER_INDUCTANCE_H = 1.66e-9
FSS_ABS_EPS_R = 2.4
FSS_ABS_TAN_DELTA = 0.006
FSS_SPACER_THICKNESS_M = 1.25e-3
FSS_ENCAPSULATION_THICKNESS_M = 1.0e-3


def _abs_layer(thickness_m: float, role: str) -> dict[str, Any]:
    return {
        "kind": "dielectric",
        "material": "ABS",
        "eps_r": FSS_ABS_EPS_R,
        "tan_delta": FSS_ABS_TAN_DELTA,
        "thickness_m": thickness_m,
        "role": role,
    }


BANDPASS_FSS_SILVER_PASTE = ReferenceCase(
    case_id="bandpass-fss-silver-paste-arxiv-2511.16777v1",
    description=(
        "Three-layer band-pass frequency selective surface, silver paste "
        "DISPENSED on 3D-printed ABS, passband around 10 GHz. *A frequency "
        "selective surface is a patterned sheet that lets some frequencies "
        "through and blocks others -- a filter made of geometry.* By far the "
        "closest published work to this programme's own manufacturing route: "
        "dispensed conductive paste, not etched copper. EXECUTED -- see "
        "verification/fss_bandpass_circuit_check.py -- and it FAILS its "
        "passband insertion loss by about 1.3 dB against the paper's own 1 dB "
        "gap, because the reconstruction cannot include the paste's own loss. "
        "That is the finding, not a defect in the case."
    ),
    frequency_hz=10e9,
    solver="CIRCUIT",
    geometry={
        "model": "abcd-cascade",
        "port_impedance_ohm": _ETA0_OHM,
        "load_impedance_ohm": _ETA0_OHM,
        "incidence": "normal",
        # In the order the wave meets them. ABCD matrices do not commute, so
        # this list IS the part -- a spacer and a sheet the other way round is
        # a different object and the arithmetic will happily solve it.
        "layers": [
            _abs_layer(FSS_ENCAPSULATION_THICKNESS_M, "outer ABS encapsulation"),
            {
                "kind": "shunt_capacitance",
                "farads": FSS_LAYER_CAPACITANCE_F,
                "role": "outer capacitive FSS layer (hexagonal wheel-spoke patches)",
            },
            _abs_layer(FSS_SPACER_THICKNESS_M, "ABS spacer"),
            {
                "kind": "shunt_inductance",
                "henries": FSS_LAYER_INDUCTANCE_H,
                "role": "middle inductive FSS layer (hexagonal wire grid)",
            },
            _abs_layer(FSS_SPACER_THICKNESS_M, "ABS spacer"),
            {
                "kind": "shunt_capacitance",
                "farads": FSS_LAYER_CAPACITANCE_F,
                "role": "inner capacitive FSS layer (hexagonal wheel-spoke patches)",
            },
            _abs_layer(FSS_ENCAPSULATION_THICKNESS_M, "inner ABS encapsulation"),
        ],
        "table_i_mm": {"p": 5.19, "p2": 4.5, "w_L": 0.22, "g": 0.8, "w_C": 0.25},
        "paste_conductivity_s_m": 1e6,
    },
    source=_FSS_SOURCE,
    reconstruction=Reconstruction(
        substrate=(
            "ABS throughout, eps_r = 2.4 and tan delta = 0.006: two 1.25 mm "
            "spacers between the three patterned layers and two 1 mm protective "
            "encapsulation layers outside them, 4.5 mm overall -- a sixth of a "
            "wavelength at 10 GHz"
        ),
        read_from_text=(
            "target sheet reactances C = 78 fF per capacitive layer and "
            "L = 1.66 nH for the inductive layer between them (section II-B)",
            "Table I: p = 5.19 mm, p2 = 4.5 mm, wL = 0.22 mm, g = 0.8 mm, wC = 0.25 mm",
            "ABS eps_r = 2.4, tan delta = 0.006; spacers d1 = 1.25 mm; encapsulation d2 = 1 mm",
            "silver paste modelled as a lossy metal of conductivity 1e6 S/m (section II-B)",
            "3DxTech Black ABS by fused filament fabrication; ACI FS0142 silver "
            "paste micro-dispensed through a 125 um tip (section V)",
            "measured roughly 1.7 dB passband insertion loss and 15-20 dB "
            "stop-band rejection (abstract, section VI)",
        ),
        inferred=(
            "the dispensed silver paste trace THICKNESS, which the paper never "
            "states. Without it the paste's sheet resistance cannot be got from "
            "its 1e6 S/m conductivity, so the shunt elements below are lossless "
            "and the reconstruction under-predicts the passband loss.",
            "the hexagonal wheel-spoke spoke count and arrangement of the "
            "capacitive layers, which appears only in Fig. 2(c). The circuit "
            "reconstruction does not need it -- the paper publishes the sheet "
            "capacitance those spokes were sized to realise -- but a full-wave "
            "reconstruction would.",
            "20 GHz as the frequency at which to read the stop-band. The paper "
            "gives rejection as a band figure, 15-20 dB above 10 GHz, and uses "
            "20 GHz as its own representative stop-band frequency in Figs. "
            "10(b), 13 and 22.",
        ),
        assumptions=(
            Assumption(
                statement=(
                    "The two capacitive layers and the inductive layer are "
                    "modelled as LOSSLESS shunt elements, because the paper "
                    "gives the paste's conductivity but not the dispensed trace "
                    "thickness that would turn it into a sheet resistance."
                ),
                cost_if_wrong=(
                    "It is wrong, and this case measures by how much: the "
                    "reconstruction predicts about 1.3 dB less passband loss "
                    "than the bench saw, more than the paper's own 1 dB "
                    "simulated-versus-measured gap allows. Any claim this case "
                    "supports about printed conductors inherits that."
                ),
                cheapest_check=(
                    "Section a single dispensed trace and measure it, or ask "
                    "the authors for the deposited thickness; a sheet "
                    "resistance follows directly and the model re-runs in "
                    "under a second."
                ),
            ),
            Assumption(
                statement=(
                    "The cascade treats each patterned layer as a single lumped "
                    "shunt reactance, which assumes the layers are far enough "
                    "apart that only the propagating mode couples between them."
                ),
                cost_if_wrong=(
                    "Evanescent coupling between closely spaced FSS layers "
                    "shifts the passband; the paper names exactly this as one "
                    "reason its own circuit model and full-wave result differ."
                ),
                cheapest_check=(
                    "Compare the reconstruction's passband edges against the "
                    "paper's stated 7-13 GHz band, which is what section VI of "
                    "docs/literature-validation-cases.md records."
                ),
            ),
        ),
    ),
    run=RunPin(
        solver="rf_tools.transmissive_absorber ABCD cascade",
        solver_version=(
            "in-repo closed form -- the adapter commit below IS the version, "
            "since there is no external binary to name"
        ),
        adapter_module="rf_tools/transmissive_absorber.py",
        adapter_commit="2823a9c1dd4ba649159fd1d1969332e08e4bcd7d",
        note="EXECUTED. Re-run with `uv run python -m verification.fss_bandpass_circuit_check`.",
    ),
    expected=(
        literature_expected_value(
            name="transmission_db_at_10ghz",
            value=-1.7,
            unit="dB",
            citation=_FSS_SOURCE.citation,
            kind=QuantityKind.TRANSMISSION,
            band=PassBand(
                digitization_error=0.5,
                digitization_basis=(
                    "the paper reports its passband figures hedged to the "
                    'nearest decibel -- "roughly 1.7 dB", "roughly 1 dB" -- so '
                    "recovering either to better than half a decibel is not "
                    "supported by the reporting, and half a decibel is used "
                    "rather than a finer figure-reading estimate"
                ),
                published_gap=1.0,
                published_gap_citation=(
                    'section VI: "Measurements have roughly 1 dB additional '
                    "loss in the passband at 10 GHz\" -- the paper's own "
                    "statement of how far its simulated unit cell sat from its "
                    "measurement there"
                ),
            ),
            rationale=(
                "The paper's own 1 dB simulated-versus-measured passband gap "
                "sets this band, being twice the half-decibel its reporting "
                "supports. The reconstruction returns -0.39 dB against the "
                "measured -1.7 dB and therefore FAILS by about 1.3 dB. That is "
                "the case working: the shunt elements here are lossless because "
                "the paper never states how thick the dispensed silver traces "
                "are, and dispensed paste at 1e6 S/m is roughly sixty times "
                "worse a conductor than copper. In plain terms, our model gives "
                "the surface free wiring and the real one was made of something "
                "more like pencil lead. The band is NOT widened to hide that."
            ),
        ),
        literature_expected_value(
            name="transmission_db_at_20ghz",
            value=-15.0,
            unit="dB",
            citation=_FSS_SOURCE.citation,
            kind=QuantityKind.TRANSMISSION,
            comparison=Comparison.AT_MOST,
            band=PassBand(
                digitization_error=0.5,
                digitization_basis=(
                    "the stop-band rejection is quoted as a whole-decibel range, "
                    '"15-20 dB", so half a decibel is the finest reading its '
                    "own reporting supports"
                ),
            ),
            rationale=(
                "The paper publishes no numeric simulated-versus-measured gap "
                "for the stop-band -- it says only that the measured depth is "
                '"lower than simulation" -- so the digitization error alone '
                "sets this band, and that is recorded rather than papered over "
                "with a number borrowed from the passband. AT_MOST rather than "
                "WITHIN, because 15-20 dB is a floor on how far down the "
                "stop-band sits and the paper gives the range as a band-wide "
                "spread, not a value at 20 GHz. Read the consequence honestly: "
                "a reconstruction rejecting 30 dB here would pass this check "
                "and should NOT be read as agreeing with the measurement. This "
                "is a floor, and the write-up says so."
            ),
        ),
    ),
)


# --- 4. varactor-tuned RIS unit cell in a WR-28 waveguide simulator -------

_VARACTOR_SOURCE = LiteratureSource(
    arxiv_id="2608.06541",
    version="v1",
    title=(
        "Manna, Reher, El Isa, Al-Bassam and Heberling, A 28-GHz "
        "Varactor-Based RIS With Continuous Phase Control: From Unit-Cell "
        "Modeling to Programmable Wavefront Control and Synthesis"
    ),
    scored_against=(
        "Fig. 5, the measured reflection magnitude and phase of the four "
        "fabricated unit cells UC1-UC4 in the modified WR-28 waveguide "
        "fixture, read at the 28 GHz design frequency"
    ),
    excluded=(
        "Everything from section III onward -- the 96-element array, the "
        "beam-steering and the wireless-link measurements. Those are "
        "aperture-level results that depend on the horn illumination and the "
        "bias calibration at least as much as on the unit cell, and every "
        "periodic model here is one cell."
    ),
)

VARACTOR_RIS_UNIT_CELL = ReferenceCase(
    case_id="varactor-ris-unit-cell-arxiv-2608.06541v1",
    description=(
        "28 GHz varactor-tuned reflective unit cell on Rogers RO4003C over "
        "FR4, measured in a WR-28 waveguide simulator. *A varactor is a diode "
        "whose capacitance changes with the voltage across it -- the mechanism "
        "that makes a surface electronically steerable rather than fixed.* "
        "Fourth of the four because it exercises the lumped-element path, a "
        "genuinely different code path, and is the most work to set up. NOT "
        "RUN, and not runnable here at all: see unresolved_reason."
    ),
    frequency_hz=28e9,
    solver="NONE",
    geometry={
        "model": "floquet-periodic-reflection-with-lumped-element",
        "unit_cell_m": [5.36e-3, 5.36e-3],
        "incidence": "normal, y-polarised; the paper also sweeps 0 to -45 degrees",
        "patch_m": {"l2": 1.90e-3, "w2": 2.19e-3, "gap_m": 0.22e-3},
        "stack_m": [
            {"layer": "RO4003C", "thickness_m": 0.305e-3, "eps_r": 3.55, "tan_delta": 0.0027},
            {"layer": "TU-768P 1080 prepreg", "thickness_m": 0.1e-3},
            {
                "layer": "FR4 bias substrate",
                "thickness_m": 1.0e-3,
                "eps_r": 4.3,
                "tan_delta": 0.025,
            },
        ],
        "vias_m": {"drill": 0.3e-3, "clearance": 0.7e-3},
        "varactor": {
            "part": "MACOM MAVR-011020-1411 GaAs flip-chip",
            "series_inductance_h": 88.5e-12,
            "parallel_capacitance_f": 9e-15,
            "series_resistance_ohm": 5.5,
            "tuning_range_f": [0.025e-12, 0.225e-12],
        },
    },
    source=_VARACTOR_SOURCE,
    reconstruction=Reconstruction(
        substrate=(
            "0.305 mm Rogers RO4003C (eps_r = 3.55, tan delta = 0.0027, both "
            "quoted by the paper as 10 GHz figures) over about 0.1 mm of "
            "TU-768P 1080 prepreg over a 1 mm FR4 bias substrate (eps_r = 4.3, "
            "tan delta = 0.025)"
        ),
        read_from_text=(
            "unit cell l1 = w1 = 5.36 mm, half a wavelength at 28 GHz (section II-A)",
            "patch l2 = 1.90 mm, w2 = 2.19 mm; h1 = 0.305 mm, h2 = 1 mm",
            "two rectangular patches separated by a 0.22 mm gap, bridged by the varactor",
            "bias vias 0.3 mm drill, 0.7 mm clearance",
            "MAVR-011020-1411 modelled as Lser = 88.5 pH, Cpar = 9 fF, Rser = 5.5 ohm",
            "capacitance swept 0.025 pF to 0.225 pF; CST Floquet ports, periodic boundaries",
            "measured in a modified WR-28 waveguide fixture against a short standard",
        ),
        inferred=(
            "the radial bias stub's dimensions. The paper describes only "
            "'a radial stub ... on the top metallization layer' and prints no "
            "numbers for it.",
            "the reverse-bias-voltage to capacitance mapping. Fig. 3 sweeps "
            "CAPACITANCE in simulation; Fig. 5, the measured figure, sweeps "
            "reverse bias voltage from 0 to 20 V, and no C(V) curve for the "
            "MAVR-011020-1411 appears anywhere in the paper -- so a "
            "per-capacitance comparison against the measurement cannot be made "
            "at all, only a comparison of the tuning range as a whole.",
        ),
        assumptions=(
            Assumption(
                statement=(
                    "RO4003C is taken at the eps_r = 3.55 and tan delta = "
                    "0.0027 the paper itself quotes, which the paper also "
                    "labels as 10 GHz figures, and applies at 28 GHz."
                ),
                cost_if_wrong=(
                    "The patch is a half-wave resonator on that substrate, so a "
                    "permittivity error moves the resonance and drags the whole "
                    "phase curve with it; a one-percent shift is comfortably "
                    "larger than the 0.7 dB magnitude agreement being scored."
                ),
                cheapest_check=(
                    "Rogers publishes RO4003C characterisation above 10 GHz; "
                    "reading the higher-frequency figure costs nothing and "
                    "settles whether the 10 GHz number was load-bearing here."
                ),
            ),
            Assumption(
                statement=(
                    "The radial bias stub is treated as invisible to the "
                    "radiating structure, on the paper's own stated reason for "
                    "fitting it -- to provide RF isolation between the "
                    "radiating structure and the bias network."
                ),
                cost_if_wrong=(
                    "If the stub is not fully isolating at 28 GHz it loads the "
                    "patch, shifting the resonance and adding loss, and the "
                    "reconstruction would be missing a real part of the RF "
                    "structure rather than an irrelevant one."
                ),
                cheapest_check=(
                    "Once the lumped-element gap is closed, solve the published "
                    "cell twice, with and without a plausible stub. Agreement "
                    "settles it; disagreement means the stub's dimensions have "
                    "to be obtained from the authors."
                ),
            ),
        ),
    ),
    run=RunPin(
        solver="none available in this repository",
        solver_version=(
            "no version applies -- no adapter here can pose this case; the pin "
            "below records the code whose limits were read to reach that "
            "conclusion, so a later reader can check whether the gap has closed"
        ),
        adapter_module="simulation/openems.py",
        adapter_commit="a0939ba56b068a12a7a62c9005676be85d416d08",
        note=(
            "openEMS is the only adapter here that emits a discrete lumped "
            "R/C/L element. It has no periodic boundaries, which is the other "
            "half of what this case needs."
        ),
    ),
    unresolved_reason=(
        "No adapter in this repository can pose this case. It needs a discrete "
        "series R-L-C element bridging a gap INSIDE a Bloch-periodic unit cell, "
        "and the two capabilities live in different adapters: simulation/"
        "openems.py emits openEMS LumpedElement properties but exposes no "
        "periodic boundaries, while simulation/meep.py (Bloch-periodic) and "
        "simulation/palace.py (Floquet ports) have the boundaries and no "
        "discrete lumped element -- Palace's LumpedPort is a port boundary "
        "condition, not a component bridging a gap in a pattern. Separately, "
        "the paper's measured axis is reverse-bias voltage while its simulated "
        "axis is capacitance, and it publishes no C(V) curve for the diode, so "
        "even with a solver the two axes could not be laid over one another "
        "point by point."
    ),
    expected=(
        literature_expected_value(
            name="reflection_magnitude_db_at_28ghz",
            value=-4.6,
            unit="dB",
            citation=_VARACTOR_SOURCE.citation,
            kind=QuantityKind.REFLECTION,
            band=PassBand(
                digitization_error=0.6,
                digitization_basis=(
                    "Fig. 5's magnitude axis runs -18 to 0 dB in 3 dB "
                    "divisions, so a curve read off it is good to about a fifth "
                    "of a division"
                ),
                published_gap=0.7,
                published_gap_citation=(
                    'section II-C: "the measured reflection magnitude closely '
                    "follows the simulated waveguide-embedded response of "
                    '-4.6 dB with a maximum deviation of less than 0.7 dB."'
                ),
            ),
            rationale=(
                "The authors' own worst-case 0.7 dB spread between their "
                "simulation and their four measured cells sets this band, just "
                "over the 0.6 dB reading Fig. 5 costs. It is a genuinely tight "
                "bar -- about a seventh of the value -- which is why this case "
                "would have been worth running had anything here been able to."
            ),
        ),
        literature_expected_value(
            name="reflection_phase_coverage_deg_at_28ghz",
            value=300.0,
            unit="degree",
            citation=_VARACTOR_SOURCE.citation,
            kind=QuantityKind.REFLECTION,
            band=PassBand(
                digitization_error=24.0,
                digitization_basis=(
                    "Fig. 5's phase axis runs 0 to 360 degrees in 60 degree "
                    "divisions; a coverage is the span between the two ends of "
                    "the curve, so a fifth-of-a-division read at each end "
                    "compounds to about 24 degrees"
                ),
            ),
            rationale=(
                "The paper publishes no numeric simulated-versus-measured phase "
                "gap at 28 GHz -- it says only that all four cells reach "
                '"phase coverage approaching 300 degrees" -- so the '
                "digitization error alone sets this band, and that is recorded "
                "rather than borrowed from the 27 GHz figures, where the paper "
                "does print 308-311 degrees. Scored as a span over the whole "
                "tuning range rather than point by point, because the measured "
                "axis is bias voltage and the simulated one is capacitance with "
                "no published curve joining them."
            ),
        ),
    ),
)


#: Every reference case, by id. The first four check the solvers against
#: closed-form answers; the last four against published measurements.
REFERENCE_CASES: dict[str, ReferenceCase] = {
    HALF_WAVE_DIPOLE.case_id: HALF_WAVE_DIPOLE,
    SALISBURY_SCREEN.case_id: SALISBURY_SCREEN,
    FREE_STANDING_RESISTIVE_SHEET.case_id: FREE_STANDING_RESISTIVE_SHEET,
    FREE_STANDING_RESISTIVE_SHEET_TWO_PORT.case_id: FREE_STANDING_RESISTIVE_SHEET_TWO_PORT,
    CPC_METASURFACE_RCS.case_id: CPC_METASURFACE_RCS,
    BIANISOTROPIC_HUYGENS_REFRACTION.case_id: BIANISOTROPIC_HUYGENS_REFRACTION,
    BANDPASS_FSS_SILVER_PASTE.case_id: BANDPASS_FSS_SILVER_PASTE,
    VARACTOR_RIS_UNIT_CELL.case_id: VARACTOR_RIS_UNIT_CELL,
}

#: The literature subset, DERIVED rather than hand-kept. A second list would
#: be a second thing to forget to update, and this module's own history is a
#: catalogue of exactly that failure.
LITERATURE_CASES: dict[str, ReferenceCase] = {
    case_id: case for case_id, case in REFERENCE_CASES.items() if case.source is not None
}


def _actual_value(expected: ExpectedValue, result: dict[str, Any]) -> float | None:
    """Pull one expected quantity out of an adapter's result dict.

    A quantity that declares a `result_key` is read straight from it. That is
    how the literature cases arrive -- declaratively, rather than by adding a
    branch to the switch below for every new published number, which is
    exactly where a transcription error would hide.
    """
    if expected.result_key:
        return _single_point(result.get(expected.result_key))
    return _named_actual_value(expected.name, result)


def _named_actual_value(name: str, result: dict[str, Any]) -> float | None:
    """The closed-form cases' name-to-field switch.

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
        actual = _actual_value(expected, result)
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


def score_reference_case(
    case: ReferenceCase,
    result: dict[str, Any],
    *,
    ignore_unresolved: bool = False,
) -> CaseScore:
    """Score one case into PASS, FAIL or UNRESOLVED, R and T kept apart.

    Three things happen here that `check_reference_case` deliberately does
    not do, because they only make sense for a case reconstructed from a
    paper:

      1. **A case that cannot decide, does not.** If the case carries an
         `unresolved_reason` -- the paper omits a load-bearing number, the
         reconstruction is ambiguous, no adapter here can pose it -- the
         answer is UNRESOLVED and nothing is scored, however well the result
         handed in happens to line up. Anything else would launder missing
         information into a verdict.
      2. **A solver that did not converge is not a failing solver.** A result
         carrying `converged: False` is UNRESOLVED for the same reason.
      3. **Reflection and transmission go in separate buckets**, and no total
         is offered. See `CaseScore`.

    `ignore_unresolved` exists for tests and for the day a reconstruction gap
    is closed by hand: it scores the numbers anyway, which is useful for
    seeing how far off a provisional reconstruction is, and is never how a
    reported result is produced.

    A result labelled `MEASURED` is refused outright rather than scored. Every
    case here is a solver run against somebody else's bench; filing one as our
    own measurement would jump CONTEXT.md's evidence hierarchy by two rungs.
    """
    declared = result.get("provenance")
    if declared is not None and declared != case.provenance:
        raise ValueError(
            f"{case.case_id} is capped at provenance {case.provenance}, but the "
            f"result claims {declared!r}. Nothing in this module is a "
            "measurement of our own hardware and none of it may be labelled "
            "as one."
        )

    if case.unresolved_reason and not ignore_unresolved:
        return CaseScore(
            case_id=case.case_id,
            outcome=CaseOutcome.UNRESOLVED,
            unresolved_reason=case.unresolved_reason,
        )

    if result.get("converged") is False:
        return CaseScore(
            case_id=case.case_id,
            outcome=CaseOutcome.UNRESOLVED,
            unresolved_reason=(
                "the solver reported that it did not converge on this "
                f"reconstruction ({case.case_id}), so the numbers it returned "
                "describe an unfinished solve rather than the structure"
            ),
        )

    by_kind: dict[QuantityKind, list[Discrepancy]] = {kind: [] for kind in QuantityKind}
    kind_of = {expected.name: expected.kind for expected in case.expected}
    for problem in check_reference_case(case, result):
        by_kind[kind_of[problem.name]].append(problem)

    outcome = CaseOutcome.PASS if not any(by_kind.values()) else CaseOutcome.FAIL
    return CaseScore(
        case_id=case.case_id,
        outcome=outcome,
        reflection=tuple(by_kind[QuantityKind.REFLECTION]),
        transmission=tuple(by_kind[QuantityKind.TRANSMISSION]),
        other=tuple(by_kind[QuantityKind.OTHER]),
    )
