"""Closed-form absorption of an UNBACKED, TWO-PORT absorbing surface -- the
ANALYSIS-step model for the ABSORBER_TRANSMISSIVE design family (issue #242).

WHY THIS EXISTS, IN PLAIN TERMS. Some of these surfaces are a tinted window
rather than a mirror: energy can leave out the back. `rf_tools/absorber.py`
models a surface with metal behind it, where nothing can get through, so
every watt that does not bounce back must have turned into heat. Take the
metal away and that sum is wrong -- it credits the design for every watt
that escaped through the part. This module counts those watts.

The gap is not a rounding correction. The identical stack -- a 376.73 ohm/sq
sheet a quarter-wavelength off whatever is behind it -- scores **1.00**
backed by metal and **0.44** unbacked. More than half of what the
ground-backed sum called "absorbed" is, in the unbacked structure, power
walking straight out the far side. Issue #216 found the two conflated in one
design family; issue #242 is the second model that split needs.

WHY A SEPARATE MODULE, NOT A FLAG ON THE EXISTING ONE. `rf_tools/absorber.py`
is a short-circuited transmission line terminated by a ground plane. Nothing
passes through it BY CONSTRUCTION -- which is exactly why it is right for
ABSORBER and wrong for anything else. Its Salisbury result is validated
against two independent methods (docs/meep-absorber-validation.md) and is
left untouched. This is a different network, not the same network with a
parameter changed.

THE MODEL. Standard microwave network theory: build the stack as a chain of
ABCD (transmission) matrices, one per physical layer, in order from the side
the wave arrives on, then convert the chain to S-parameters against a port
impedance on each side.

  * A resistive sheet is a SHUNT admittance Y = 1/Z_sheet across the line:

        [[1, 0],
         [Y, 1]]

    Z_sheet is `rf_tools.absorber.patterned_sheet_impedance` -- deliberately
    the SAME sheet model the ground-backed family uses, so that a comparison
    between the two families is a comparison of the structure and not of two
    different opinions about the printed layer.

  * A dielectric slab of thickness d is a length of transmission line:

        eps = eps_r * (1 - j*tan_delta),  n = sqrt(eps),  k0 = 2*pi*f/c
        gamma = j*k0*n,                   Zd = eta0 / n

        [[cosh(gamma*d),      Zd*sinh(gamma*d)],
         [sinh(gamma*d)/Zd,   cosh(gamma*d)   ]]

  * With port impedance Z0 on the incidence side and load ZL on the far side:

        den = A*ZL + B + C*Z0*ZL + D*Z0
        S11 = (A*ZL + B - C*Z0*ZL - D*Z0) / den
        S21 = 2*sqrt(Z0*ZL) / den

        R = |S11|^2,   T = |S21|^2,   A = 1 - R - T

    That last line is the field's universal definition, not a house
    convention -- see docs/absorber-scoring-conventions.md section 1, which
    finds it stated identically in every source it checked.

THE HALF-POWER CEILING. A thin resistive sheet with free space on both sides
absorbs at most **exactly one half** of the power that hits it, and does so
when its sheet resistance is exactly eta0/2 = 188.365 ohm/sq. This is an
exact closed-form maximum, not an approximation, and
docs/meep-absorber-validation.md case 1 confirms it against an FDTD solver
(0.4971 measured against 0.5000 exact, and 0.4999 on a finer mesh). Case 4
there confirms THIS MODULE's own numbers against the same run: at Rs =
eta0/2 the closed form below returns R = T = 0.2500 and A = 0.5000 to
floating-point, against a full-wave 0.2899 / 0.2130 / 0.4971 -- so the two
methods agree on the absorbed total to 0.003 and disagree on the split by
more than ten times that, all of it the grid's doing rather than the
model's. In plain terms: a single resistive
film hanging in air throws away at least half the power that reaches it,
whatever ink you print it with -- half bounces or passes, and no sheet
resistance changes that. A requirement above 50 % needs a different
structure, not a different material, and `single_sheet_half_power_ceiling`
in the `validity` list says so whenever this stack is effectively that shape.

WHAT `load_impedance_ohm` IS FOR, AND WHAT IT IS NOT. The family's answer
always uses ZL = eta0 -- free space behind the part. The parameter exists so
the back of the stack can be driven toward a SHORT CIRCUIT, which turns the
two-port structure into a ground-backed one and must therefore reproduce
`rf_tools.absorber.absorptivity` for the same stack. That cross-check is the
one assertion that catches a sign or a port-normalisation error neither
model would reveal alone: they would have to be wrong in identical ways to
agree, and they were written from different starting points. It converges to
seven decimal places across the whole 6-14 GHz band, including at the band
edges where the answer is 0.8834 and 0.9743 rather than a saturated 1.0.

`load_impedance_ohm` is a diagnostic, NOT a second public model. **The
ground-backed case remains `rf_tools/absorber.py`'s job.** Any run at a load
other than free space carries `load_impedance_is_not_free_space` in its
`validity` list so a shorted diagnostic can never be mistaken for a
candidate's score.

WHAT THIS MODEL DOES NOT KNOW. Normal incidence only -- there is no angle
anywhere in the arithmetic. One dominant propagating mode; nothing here
represents a diffraction order, so results above the grating onset (roughly
where the cell period reaches a wavelength) are outside the model. And this
family's physical bound is UNREAD: see `PHYSICAL_BOUND_STATUS` below for why
that is reported rather than left silent, and why a familiar-looking bound
from the ground-backed family is deliberately not named in the output.
"""

from __future__ import annotations

import cmath
import math
from collections.abc import Sequence
from typing import Any

from rf_tools.absorber import ETA0_OHM, SPEED_OF_LIGHT_M_S, patterned_sheet_impedance

# The exact optimum for a bare sheet in free space: Rs = eta0/2. At this
# value, and only this value, absorption reaches exactly 0.5.
MATCHED_SHEET_RESISTANCE_OHM_SQ = ETA0_OHM / 2

# The exact ceiling on a bare sheet in free space (see the module docstring).
BARE_SHEET_MAX_ABSORPTION = 0.5

# A slab thinner than this fraction of a wavelength IN THE MATERIAL, at the
# top of the band, does not separate the two faces enough for the stack to be
# anything other than a single sheet in free space -- so the half-power
# ceiling binds it. One twentieth of a wavelength is about 18 degrees of
# round-trip phase, well short of the quarter-wave (90 degrees) a Salisbury
# screen needs to work at all.
SINGLE_SHEET_ELECTRICAL_THICKNESS = 1 / 20

AbcdMatrix = tuple[tuple[complex, complex], tuple[complex, complex]]

IDENTITY_ABCD: AbcdMatrix = ((1, 0), (0, 1))


# --------------------------------------------------------------------------
# The physical bound: reported UNREAD, and reported without a name borrowed
# from another family.
# --------------------------------------------------------------------------

# WHY THE OUTPUT NAMES NO BOUND AT ALL, NOT EVEN TO EXCLUDE ONE.
#
# `ABSORBER_TRANSMISSIVE.physical_bound` is an `UnreadPhysicalBound`: a
# thickness-versus-bandwidth bound may well exist for an unbacked absorbing
# screen, but this programme has not read a primary source for one. Absence
# of a citation is not evidence that no bound exists, so this is reported as
# UNREAD -- which is a different claim from "there isn't one" (that would be
# NO_PHYSICAL_BOUND) and a different claim again from ABSORBER's "here is the
# number".
#
# The registry entry explains WHY the ground-backed family's bound does not
# transfer, and it does so by naming that bound. This model's OUTPUT
# deliberately does not. Issue #216's failure mode is a regenerating one: the
# ground-backed bound's derivation opens by fixing a slab over a perfectly
# reflecting plane, this family has no such plane, and the way the error
# comes back is that somebody greps a transmissive result, finds the familiar
# name sitting beside a number, and reapplies it. The explanation belongs
# where it is attached to the COMPARISON -- designs/design_families.py and
# docs/absorber-scoring-conventions.md -- not where it is attached to a
# transmissive candidate's score. tests/test_transmissive_absorber.py asserts
# the name never appears here.
PHYSICAL_BOUND_STATUS: dict[str, Any] = {
    "status": "unread_primary_source",
    "name": "unbacked/transmissive absorber bandwidth bound",
    "applies": False,
    "why_no_number": (
        "No feasibility bound has been read from a primary source for an "
        "unbacked, two-port absorbing screen, so this result has NOT been "
        "checked against one. That is not a claim that no such bound exists -- "
        "it is a claim that this programme has not looked one up. The "
        "ground-backed family's bound is not a substitute and is deliberately "
        "not quoted here (issue #216); see designs/design_families.py's "
        "ABSORBER_TRANSMISSIVE entry for why it does not transfer."
    ),
    "primary_source_doc": None,
}


class GroundBackedModelMisappliedError(ValueError):
    """Raised when ground-backed absorber ARITHMETIC is aimed at a structure
    that has no ground plane.

    Two callers raise it, for the same physical reason at two different
    prices:

      * `refuse_ground_backed_model` -- the closed-form ANALYSIS model
        (`rf_tools/absorber.py`) pointed at a transmitting family.
      * `one_port_absorption` -- the one-port collapse `A = 1 - R` applied to
        a SIMULATED reflectance for a transmitting family (issue #243).

    Both are the same mistake: a sum whose whole legitimacy is "nothing can
    get out the back" used where power can.
    """


def declared_port_count(family: Any) -> int:
    """The family's declared `port_count`, or a raise if it has none.

    Deliberately NOT `getattr(family, "port_count", 1)`. A default of 1 picks
    the one-port collapse A = 1 - R for anything that failed to say how many
    ports it has -- which is the silent fallback every function below exists
    to forbid, reintroduced at the one place nobody would look for it. An
    object with no declared port count is a state to report, not to guess
    past (issues #216, #243).
    """
    ports = getattr(family, "port_count", None)
    if ports is None:
        name = getattr(family, "name", repr(family))
        raise GroundBackedModelMisappliedError(
            f"Design family {name!r} declares no port_count, so which absorption "
            "sum applies to it cannot be decided. A ground-backed surface is "
            "port_count=1 and uses A = 1 - R; an unbacked one is port_count=2 "
            "and uses A = 1 - R - T. Declare it in designs/design_families.py. "
            "This is not defaulted to 1: assuming a ground plane nobody stated "
            "is exactly how power that escaped out the back gets booked as heat "
            "(issues #216, #243)."
        )
    return int(ports)


def refuse_ground_backed_model(family: Any) -> None:
    """Refuse to run `rf_tools.absorber` against a family that transmits.

    WHERE THIS GUARD LIVES, AND WHY HERE.

    It cannot live in `rf_tools/absorber.py`. That module takes only numbers
    -- a permittivity, a thickness, a sheet resistance -- and nothing in that
    signature says whether there is metal behind the stack. There is no fact
    available inside it to test. (It also must not change: its Salisbury
    result is validated against two independent methods.)

    It could live at the dispatch in `orchestration/design_loop.py`, which is
    where a design family and a model actually meet, and that IS where it is
    called from. But it is DEFINED here, next to the model it points at,
    because the rule it encodes -- "these two models are not interchangeable,
    and here is which one applies when" -- is a statement about the PAIR of
    models. A reader who opens either absorber module should be able to find
    it; a reader who opens the loop is looking for dispatch, not physics.

    The check reads what the family DECLARES (`requires_ground_plane`,
    `port_count`), not its name, so a family registered later is covered
    without editing this function. Those two fields are already guaranteed to
    agree with each other by `DesignFamily.__post_init__` (issue #216).

    In plain terms: the ground-backed sum assumes nothing gets out the back.
    Point it at a part that lets 44 % of the power through and it will
    cheerfully report 100 % absorption, and nothing in the number will say so.
    That is a silent wrong answer, which is the one kind this programme
    refuses rather than warns about -- the charter's "warn, never block"
    governs withholding a CANDIDATE from a reader, not letting a model answer
    a question about a different structure.

    Returns None when the family is genuinely ground-backed.
    """
    ground_backed = bool(getattr(family, "requires_ground_plane", False))
    ports = declared_port_count(family)
    if ground_backed and ports == 1:
        return None
    name = getattr(family, "name", repr(family))
    raise GroundBackedModelMisappliedError(
        f"The ground-backed absorber model (rf_tools/absorber.py) was aimed at "
        f"design family {name!r}, which declares requires_ground_plane="
        f"{ground_backed} and port_count={ports}. That model assumes zero "
        "transmission by construction. Where power CAN leave out the back, it "
        "silently books every escaped watt as absorbed -- reporting 1.00 where "
        "the truth is 0.44 for a Salisbury stack. Use "
        "rf_tools.transmissive_absorber.transmissive_absorber_band_response, "
        "which computes A = 1 - |S11|^2 - |S21|^2. See issues #216 and #242."
    )


# --------------------------------------------------------------------------
# Absorption from a SOLVER's reflectance and transmittance (issue #243)
# --------------------------------------------------------------------------
#
# Everything above turns a described stack into R and T by closed form. The
# three functions below do the last, tiny step -- turning an R and a T that
# a full-wave solver measured into an absorption -- and they live here, next
# to `refuse_ground_backed_model`, for the reason that guard's own docstring
# gives: the rule they encode is a statement about the PAIR of absorber
# models, and a reader who opens either absorber module should find it.
# `orchestration/design_loop.py` is where a design family and a solver
# result actually meet, so that is where they are CALLED from -- a reader
# who opens the loop is looking for dispatch, not physics.
#
# The two sums (docs/absorber-scoring-conventions.md section 1):
#
#     one port  (ground-backed):  A = 1 - R
#     two ports (unbacked):       A = 1 - R - T
#
# In plain terms: with metal behind the surface, anything that did not bounce
# back was turned into heat, because there is nowhere else for it to go. With
# free space behind it, some of it simply left through the far side, and that
# share has to come off the total.


def one_port_absorption(family: Any, reflectance: Sequence[float]) -> list[float]:
    """`A = 1 - R`, and a refusal when the family can transmit.

    Legitimate ONLY for a one-port, ground-backed family, where zero
    transmission is guaranteed by construction. Aimed at a two-port family it
    would book every escaped watt as heat: a Salisbury stack that truly
    absorbs 0.44 would be reported at 1.00, and nothing in the number would
    say which it was.

    That is why this raises rather than warning. The charter's "warn, never
    block" governs withholding a CANDIDATE from a reader, and nothing is
    withheld here -- what is refused is a confidently wrong number, the one
    kind no caveat can rescue, because a reader cannot tell it apart from a
    right one.
    """
    ports = declared_port_count(family)
    if ports != 1:
        name = getattr(family, "name", repr(family))
        ground_backed = bool(getattr(family, "requires_ground_plane", False))
        raise GroundBackedModelMisappliedError(
            f"The one-port absorption collapse A = 1 - R was aimed at design "
            f"family {name!r}, which declares port_count={ports} and "
            f"requires_ground_plane={ground_backed}. That collapse assumes "
            "zero transmission by construction, so on a surface with free "
            "space behind it every watt that merely escaped out the back is "
            "booked as heat -- a Salisbury stack that absorbs 0.44 would be "
            "reported at 1.00. Measure the transmitted power and use "
            "two_port_absorption (A = 1 - R - T) instead. See "
            "docs/absorber-scoring-conventions.md section 1, and issues #216 "
            "and #243."
        )
    return [1.0 - float(r) for r in reflectance]


def two_port_absorption(
    family: Any,
    reflectance: Sequence[float],
    transmittance: Sequence[float],
) -> list[float]:
    """`A = 1 - R - T` for an unbacked surface, point by point in frequency.

    Both spectra must have been measured on the same run at the same
    frequencies, so a length disagreement is a wiring fault, not a physics
    result, and is reported rather than zipped past.

    Nothing is clipped. A negative absorption means R + T came out above one,
    which cannot physically happen and therefore says an assumption behind
    the run is wrong -- see `energy_balance_violations` for the warning that
    goes with it. Clamping it to zero would hide exactly the evidence a
    reader needs.
    """
    reflectance = list(reflectance)
    transmittance = list(transmittance)
    if len(reflectance) != len(transmittance):
        name = getattr(family, "name", repr(family))
        raise ValueError(
            f"Cannot compute A = 1 - R - T for design family {name!r}: the run "
            f"returned {len(reflectance)} reflectance point(s) and "
            f"{len(transmittance)} transmittance point(s). The two must come "
            "from the same run at the same frequencies -- pairing them up "
            "anyway would silently subtract one frequency's transmission from "
            "another frequency's reflection."
        )
    return [1.0 - float(r) - float(t) for r, t in zip(reflectance, transmittance, strict=True)]


#: The `flag` an over-unity energy balance is recorded under. Named once so
#: the loop, the tests and any reader are talking about the same warning.
ENERGY_BALANCE_FLAG = "reflected_plus_transmitted_exceeds_incident"


def energy_balance_violations(
    reflectance: Sequence[float],
    transmittance: Sequence[float],
    frequency_hz: Sequence[float] | None = None,
) -> list[dict[str, Any]]:
    """Every frequency where the power coming back plus the power going
    through is MORE than the power that arrived.

    A passive surface cannot do that -- it has no source of energy inside it
    -- so a sum above one is not a marginal result, it is proof that
    something about the run is wrong (see `energy_balance_warning` for the
    usual suspects). Returns one entry per offending frequency, empty when
    the run is physical.

    A hair over one is arithmetic noise, not a physics claim, so the test
    carries a small tolerance: FDTD flux ratios are the quotient of two
    finite-difference sums and land a fraction of a percent either side of
    the exact answer. `_ENERGY_BALANCE_TOLERANCE` is that allowance, and it
    is deliberately far smaller than any error a reader would care about.
    """
    frequencies = list(frequency_hz) if frequency_hz else []
    violations: list[dict[str, Any]] = []
    for index, (r, t) in enumerate(zip(reflectance, transmittance, strict=True)):
        total = float(r) + float(t)
        if total <= 1.0 + _ENERGY_BALANCE_TOLERANCE:
            continue
        violations.append(
            {
                "index": index,
                "frequency_hz": frequencies[index] if index < len(frequencies) else None,
                "reflectance": float(r),
                "transmittance": float(t),
                "reflected_plus_transmitted": total,
            }
        )
    return violations


#: One part in a thousand. Big enough to absorb an FDTD flux ratio's own
#: discretisation noise, small enough that a real over-unity result -- the
#: kind produced by a monitor plane in the wrong place -- still fires.
_ENERGY_BALANCE_TOLERANCE = 1e-3


def energy_balance_warning(violations: Sequence[dict[str, Any]]) -> dict[str, str]:
    """The charter-shaped warning that rides with an impossible run.

    What is assumed, what it costs if that is wrong, and the cheapest way to
    find out -- the same three parts every warning in this programme owes,
    and it fires only where the assumption is load-bearing, because a
    warning attached to every run is worth the same as none.
    """
    worst = max(v["reflected_plus_transmitted"] for v in violations)
    return {
        "flag": ENERGY_BALANCE_FLAG,
        "assumed": (
            "that the reflectance and transmittance spectra were measured on "
            "the same structure, at the same frequencies, each normalised "
            "against the power that actually arrived. At "
            f"{len(violations)} frequency point(s) they sum to as much as "
            f"{worst:.4f} -- more power leaving than arrived, which a surface "
            "with no energy source inside it cannot do."
        ),
        "costs": (
            "absorption is computed as 1 - R - T, so an inflated sum drives it "
            "below zero and the candidate is scored on a number that is not a "
            "fraction of anything. The usual causes are a monitor plane on the "
            "wrong side of the structure or inside the absorbing boundary, or "
            "a reference run whose normalising power was measured somewhere "
            "the wave never reached."
        ),
        "cheapest_test": (
            "re-run the same cell as a free-standing 188.4 ohm/sq resistive "
            "sheet, whose answer is known in closed form: R = T = 0.25 and "
            "A = 0.5. If those three do not come back, the monitor geometry "
            "is wrong, not the design."
        ),
    }


# --------------------------------------------------------------------------
# The ABCD primitives
# --------------------------------------------------------------------------


def shunt_sheet_abcd(admittance_siemens: complex) -> AbcdMatrix:
    """A thin sheet across the line, as an ABCD matrix.

    A resistive sheet is electrically a SHUNT element: the wave sees it as
    something bridging the two conductors of the equivalent line, so current
    is diverted through it while the voltage across it is continuous. That is
    what the zero in the top-right corner says -- no series impedance, no
    thickness.

    Infinite admittance (perfect metal) short-circuits the line, giving a
    mirror; zero admittance is no sheet at all.
    """
    return ((1, 0), (admittance_siemens, 1))


def dielectric_slab_abcd(
    frequency_hz: float, eps_r: float, tan_delta: float, thickness_m: float
) -> AbcdMatrix:
    """A slab of dielectric, as a length of transmission line.

        eps = eps_r * (1 - j*tan_delta)   complex permittivity, loss included
        n   = sqrt(eps)                   refractive index
        k0  = 2*pi*f/c                    free-space wavenumber
        gamma = j*k0*n                    propagation constant in the slab
        Zd  = eta0 / n                    the slab's wave impedance

    A lossless slab exactly half a wavelength thick IN THE MATERIAL transforms
    its load to itself and vanishes; a quarter-wavelength slab inverts it.
    Those two are the model's own sanity checks and both are asserted in
    tests/test_transmissive_absorber.py.

    A zero-thickness slab returns the identity -- nothing between the ports
    is nothing -- rather than a near-identity built out of cosh(0) arithmetic
    that a caller then has to trust.
    """
    _require_non_negative("thickness_m", thickness_m)
    _require_positive("frequency_hz", frequency_hz)
    if eps_r < 1:
        raise ValueError(f"eps_r must be >= 1; got {eps_r!r}.")
    if tan_delta < 0:
        raise ValueError(f"tan_delta must be non-negative; got {tan_delta!r}.")

    if thickness_m == 0.0:
        return IDENTITY_ABCD

    eps_complex = eps_r * (1 - 1j * tan_delta)
    n = cmath.sqrt(eps_complex)
    k0 = 2 * math.pi * frequency_hz / SPEED_OF_LIGHT_M_S
    gamma = 1j * k0 * n
    z_slab = ETA0_OHM / n

    cosh_gd = cmath.cosh(gamma * thickness_m)
    sinh_gd = cmath.sinh(gamma * thickness_m)
    return ((cosh_gd, z_slab * sinh_gd), (sinh_gd / z_slab, cosh_gd))


def cascade(*matrices: AbcdMatrix) -> AbcdMatrix:
    """Chain layers into one network, in physical order from the incidence
    side.

    ORDER MATTERS AND DOES NOT COMMUTE -- a sheet in front of a slab is a
    different part from a slab in front of a sheet, and the matrices say so.
    Passing them in the wrong order is a real design error the arithmetic
    will faithfully compute an answer for, so callers pass them the way the
    wave meets them.
    """
    result: AbcdMatrix = IDENTITY_ABCD
    for matrix in matrices:
        result = _multiply(result, matrix)
    return result


def _multiply(left: AbcdMatrix, right: AbcdMatrix) -> AbcdMatrix:
    (a1, b1), (c1, d1) = left
    (a2, b2), (c2, d2) = right
    return (
        (a1 * a2 + b1 * c2, a1 * b2 + b1 * d2),
        (c1 * a2 + d1 * c2, c1 * b2 + d1 * d2),
    )


def s_parameters(
    abcd: AbcdMatrix, port_impedance_ohm: complex, load_impedance_ohm: complex
) -> tuple[complex, complex]:
    """Convert one ABCD matrix to (S11, S21) against two port impedances.

    S11 is the fraction of the wave's VOLTAGE that comes back; S21 the
    fraction that gets through. Squaring either converts voltage to power,
    which is why absorption is 1 - |S11|^2 - |S21|^2 and not 1 - S11 - S21.

    The `sqrt(Z0*ZL)` in the S21 numerator is the part that is easy to drop
    and impossible to notice: without it the transmitted POWER is wrong by
    the ratio of the two port impedances, which is exactly 1 when they match
    -- so the error hides completely in the two-port free-space case and only
    surfaces in the shorted cross-check. That is why the cross-check is the
    load-bearing test rather than a nicety.
    """
    (a, b), (c, d) = abcd
    z0 = complex(port_impedance_ohm)
    zl = complex(load_impedance_ohm)
    den = a * zl + b + c * z0 * zl + d * z0
    if den == 0:
        raise ValueError(
            "Degenerate network: the S-parameter denominator is zero for this "
            f"stack at port impedances Z0={port_impedance_ohm!r}, "
            f"ZL={load_impedance_ohm!r}."
        )
    s11 = (a * zl + b - c * z0 * zl - d * z0) / den
    s21 = 2 * cmath.sqrt(z0 * zl) / den
    return s11, s21


# --------------------------------------------------------------------------
# The model
# --------------------------------------------------------------------------


def _require_positive(name: str, value: float) -> float:
    if value <= 0:
        raise ValueError(f"{name} must be positive; got {value!r}.")
    return float(value)


def _require_non_negative(name: str, value: float) -> float:
    if value < 0:
        raise ValueError(f"{name} must be non-negative; got {value!r}.")
    return float(value)


def stack_response(
    frequency_hz: float,
    eps_r: float,
    tan_delta: float,
    thickness_m: float | None,
    period_m: float,
    gap_m: float | None,
    sheet_resistance_ohm_sq: float,
    squares: float,
    load_impedance_ohm: float | None = None,
) -> dict[str, Any]:
    """Reflection, transmission and absorption at ONE frequency, at normal
    incidence, for an unbacked stack.

    The stack is built in the order the wave meets it: the printed resistive
    sheet first, then the dielectric slab it sits on (if any), then whatever
    is behind. `thickness_m=None` or `0.0` means no slab -- a bare sheet
    hanging in free space, which is the case with the exact 0.5 ceiling.

    `load_impedance_ohm` defaults to eta0, free space behind the part, which
    is the family's own case. See the module docstring for the only other
    thing it is for.

    Returns `s11`/`s21` as complex numbers alongside the three power
    fractions, because the phase is what a downstream comparison against a
    published S-parameter plot needs and throwing it away here would mean
    recomputing the whole chain to get it back.
    """
    if load_impedance_ohm is None:
        load = ETA0_OHM
    else:
        load = _require_positive("load_impedance_ohm", load_impedance_ohm)

    sheet_impedance = patterned_sheet_impedance(
        frequency_hz, period_m, gap_m, eps_r, tan_delta, sheet_resistance_ohm_sq, squares
    )
    layers = [shunt_sheet_abcd(1 / sheet_impedance)]
    if thickness_m:
        layers.append(dielectric_slab_abcd(frequency_hz, eps_r, tan_delta, thickness_m))

    s11, s21 = s_parameters(cascade(*layers), ETA0_OHM, load)
    reflection = abs(s11) ** 2
    transmission = abs(s21) ** 2
    # Numerical noise can put a passive stack a hair outside [0, 1]; clamp
    # rather than report a physically impossible number. Same treatment
    # rf_tools/absorber.py gives its own result, for the same reason.
    absorption = min(1.0, max(0.0, 1.0 - reflection - transmission))
    return {
        "frequency_hz": float(frequency_hz),
        "s11": s11,
        "s21": s21,
        "reflection": reflection,
        "transmission": transmission,
        "absorption": absorption,
    }


def transmissive_absorptivity(
    frequency_hz: float,
    eps_r: float,
    tan_delta: float,
    thickness_m: float | None,
    period_m: float,
    gap_m: float | None,
    sheet_resistance_ohm_sq: float,
    squares: float,
    load_impedance_ohm: float | None = None,
) -> float:
    """Just the absorbed fraction (0..1), for parity with
    `rf_tools.absorber.absorptivity`. Everything else is in `stack_response`.
    """
    return stack_response(
        frequency_hz,
        eps_r,
        tan_delta,
        thickness_m,
        period_m,
        gap_m,
        sheet_resistance_ohm_sq,
        squares,
        load_impedance_ohm,
    )["absorption"]


def transmissive_absorber_band_response(
    f_low_hz: float,
    f_high_hz: float,
    eps_r: float,
    tan_delta: float,
    thickness_m: float | None,
    period_m: float,
    gap_m: float | None,
    sheet_resistance_ohm_sq: float,
    squares: float,
    load_impedance_ohm: float | None = None,
    points: int = 41,
) -> dict[str, Any]:
    """Sweep the required band and report the SINGLE WORST-ABSORBING
    frequency in it, not the mean and not the peak.

    #110's minimax rule, matching how `absorber_band_response` already
    reports: averaging lets one lucky peak hide a design that fails
    everywhere else, and a customer who asks for 90 % across a band is asking
    for 90 % at every frequency in it. In plain terms -- a surface is only as
    good as its weakest point in the band you care about.

    Reports reflection and transmission at that worst point alongside the
    absorption, because for THIS family they are a different decision: "44 %
    absorbed" and "44 % absorbed, 44 % straight through the part" are not the
    same result, and only the second one tells a systems engineer whether
    whatever sits behind the surface is going to hear it.

    Also returns the family's physical bound as UNREAD (see
    `PHYSICAL_BOUND_STATUS`) and a `validity` list naming every assumption
    that is load-bearing for THIS stack. `validity` never blocks the result;
    it travels with it.
    """
    if f_high_hz <= f_low_hz:
        raise ValueError(
            f"f_high_hz must exceed f_low_hz; got f_low_hz={f_low_hz!r}, f_high_hz={f_high_hz!r}."
        )
    if points < 2:
        raise ValueError(f"points must be at least 2; got {points!r}.")

    step = (f_high_hz - f_low_hz) / (points - 1)
    curve = []
    for i in range(points):
        frequency_hz = f_low_hz + i * step
        point = stack_response(
            frequency_hz,
            eps_r,
            tan_delta,
            thickness_m,
            period_m,
            gap_m,
            sheet_resistance_ohm_sq,
            squares,
            load_impedance_ohm,
        )
        # The complex S-parameters are dropped from the recorded curve: the
        # loop serialises this dict into a decision record, and a complex
        # number is not JSON. `stack_response` still returns them for a
        # caller that wants phase.
        curve.append(
            {
                "frequency_hz": point["frequency_hz"],
                "reflection": point["reflection"],
                "transmission": point["transmission"],
                "absorption": point["absorption"],
            }
        )

    worst = min(curve, key=lambda p: p["absorption"])
    best = max(curve, key=lambda p: p["absorption"])

    return {
        "function": "transmissive_absorber_band_response",
        # Which sum produced this number, carried on the result itself (#243).
        # The SIMULATION record states this too, but a reader may only ever see
        # THIS one: when the full-wave step refuses, the closed-form result is
        # what survives as the candidate's evidence, and a bare absorption
        # figure does not say whether the power that left out the back was
        # subtracted or counted as heat.
        "port_count": 2,
        "absorption_formula": "A = 1 - R - T",
        "worst_absorption": worst["absorption"],
        "worst_frequency_hz": worst["frequency_hz"],
        "reflection_at_worst": worst["reflection"],
        "transmission_at_worst": worst["transmission"],
        "best_absorption": best["absorption"],
        "best_frequency_hz": best["frequency_hz"],
        "curve": curve,
        "physical_bound": dict(PHYSICAL_BOUND_STATUS),
        "validity": _validity(
            f_high_hz=f_high_hz,
            eps_r=eps_r,
            thickness_m=thickness_m,
            period_m=period_m,
            gap_m=gap_m,
            load_impedance_ohm=load_impedance_ohm,
        ),
        "provenance": "CALCULATED",
    }


def grating_onset_hz(period_m: float, eps_r: float) -> float:
    """Roughly the frequency above which the repeating cell stops being small
    against a wavelength and starts diffracting.

    At normal incidence the first diffraction order goes propagating when the
    cell period reaches one wavelength -- and it does so first in the DENSER
    medium, where the wavelength is shorter, hence the sqrt(eps_r):

        f_onset ~ c / (period * sqrt(eps_r))

    In plain terms: below this the surface only sends power straight back and
    straight through, which is all a two-port model can describe. Above it the
    surface also flings power off at an angle, and this model has no term for
    that at all -- worse, `A = 1 - R - T` would book the diffracted power as
    heat, quietly flattering the design.

    WHY THIS REPLACES THE GROUND-BACKED MODEL'S THICKNESS WARNING. The
    ground-backed model carries `electrically_thick_at_band_top`, keyed on
    slab thickness against lambda/10. That check is not carried over here,
    and dropping it is deliberate rather than an oversight: the slab in this
    chain is a full transmission line with its own phase term, which is EXACT
    for a uniform slab at normal incidence at any thickness -- a Salisbury
    screen's quarter-wave spacer is a third of a wavelength thick and the
    chain handles it exactly, as the cross-check against
    docs/meep-absorber-validation.md's whole 6-14 GHz band shows. Warning
    about it would fire on every well-designed stack in this family, and a
    warning that fires on everything says nothing. The assumption that IS
    load-bearing and IS violated at high frequency is single-mode
    propagation, which the cell PERIOD governs, not the slab thickness.
    """
    _require_positive("period_m", period_m)
    if eps_r < 1:
        raise ValueError(f"eps_r must be >= 1; got {eps_r!r}.")
    return SPEED_OF_LIGHT_M_S / (period_m * math.sqrt(eps_r))


def _electrical_thickness_at(frequency_hz: float, eps_r: float, thickness_m: float) -> float:
    """Slab thickness as a fraction of a wavelength IN THE MATERIAL. This is
    the number that decides whether a slab separates the two faces of the
    stack or is simply not there electrically."""
    wavelength_in_material_m = SPEED_OF_LIGHT_M_S / (frequency_hz * math.sqrt(eps_r))
    return thickness_m / wavelength_in_material_m


def _validity(
    *,
    f_high_hz: float,
    eps_r: float,
    thickness_m: float | None,
    period_m: float,
    gap_m: float | None,
    load_impedance_ohm: float | None,
) -> list[dict[str, str]]:
    """Every warning that is load-bearing for THIS stack, and none that is not.

    Each entry carries what is assumed, what it costs if that is wrong, and
    the cheapest way to find out -- the charter's warning shape, and the same
    three fields `rf_tools/absorber.py`'s own entries use. A warning is only
    useful if it is rare and specific: warning on everything and warning on
    nothing are the same outcome, so every check below is conditional on
    something about this particular stack.
    """
    validity: list[dict[str, str]] = []

    electrical_thickness = (
        _electrical_thickness_at(f_high_hz, eps_r, thickness_m) if thickness_m else 0.0
    )
    if electrical_thickness < SINGLE_SHEET_ELECTRICAL_THICKNESS:
        validity.append(
            {
                "flag": "single_sheet_half_power_ceiling",
                "assumed": (
                    "this stack behaves as a single thin resistive sheet with free "
                    "space on both sides -- its slab is "
                    + (
                        "absent"
                        if not thickness_m
                        else f"only {electrical_thickness:.4f} wavelengths thick in "
                        f"the material at {f_high_hz / 1e9:.2f} GHz, below "
                        f"{SINGLE_SHEET_ELECTRICAL_THICKNESS}"
                    )
                    + " -- and such a sheet has an EXACT closed-form maximum "
                    "absorption of 0.5, reached only at "
                    f"Rs = eta0/2 = {MATCHED_SHEET_RESISTANCE_OHM_SQ:.3f} ohm/sq"
                ),
                "costs": (
                    "any requirement above 50 % absorption is unreachable by this "
                    "SHAPE at any sheet resistance and with any ink; the shortfall "
                    "is structural, not a tuning error, so time spent adjusting "
                    "the printed layer is time wasted. A spacer thick enough to "
                    "give a quarter-wave round trip, or a second resistive layer, "
                    "is what changes the answer"
                ),
                "cheapest_test": (
                    "sweep sheet resistance across a decade in this same model: "
                    "the peak will sit at eta0/2 and reach 0.5, and no value will "
                    "beat it. Confirmed independently against FDTD in "
                    "docs/meep-absorber-validation.md case 1 (0.4971 from the "
                    "committed runner, 0.4999 from a finer mesh, against an "
                    "exact 0.5000)"
                ),
            }
        )

    if load_impedance_ohm is not None and not math.isclose(
        load_impedance_ohm, ETA0_OHM, rel_tol=1e-9
    ):
        validity.append(
            {
                "flag": "load_impedance_is_not_free_space",
                "assumed": (
                    f"the medium behind this surface has wave impedance "
                    f"{load_impedance_ohm:.6g} ohm, not free space's "
                    f"{ETA0_OHM:.3f} ohm. This family's own answer is the "
                    "free-space one; a different load is a DIAGNOSTIC run"
                ),
                "costs": (
                    "this number is not the candidate's score and must not be "
                    "reported as one. Driving the load toward zero (a short) "
                    "reproduces the GROUND-BACKED answer, which for a Salisbury "
                    "stack is 1.00 against the unbacked 0.44 -- so a shorted "
                    "diagnostic mistaken for a score overstates absorption by "
                    "more than a factor of two"
                ),
                "cheapest_test": (
                    "re-run with load_impedance_ohm left at its default and "
                    "compare; the gap between the two IS the power leaving out "
                    "the back of the part"
                ),
            }
        )

    if gap_m is not None:
        validity.append(
            {
                "flag": "grid_capacitance_unvalidated",
                "assumed": (
                    f"Luukkonen's grid capacitance represents the {gap_m * 1e3:.3f} mm "
                    "gaps between neighbouring printed elements. EVERY case this "
                    "programme has validated against an independent solver "
                    "(docs/meep-absorber-validation.md) is a UNIFORM sheet, which "
                    "switch that term off entirely -- so the term a patterned cell "
                    "depends on is precisely the part no solver has checked here"
                ),
                "costs": (
                    "the resonant frequency this model predicts for a patterned "
                    "cell may be wrong, and the gap needed to hit a target "
                    "frequency wrong with it. Neither the size nor the direction "
                    "of that error is known for this family"
                ),
                "cheapest_test": (
                    "one periodic unit-cell solve of this exact cell, compared "
                    "against this model's predicted resonance -- the same "
                    "cross-check that caught the continuous-sheet error at #230"
                ),
            }
        )

    onset_hz = grating_onset_hz(period_m, eps_r)
    if f_high_hz > onset_hz:
        validity.append(
            {
                "flag": "higher_order_modes_in_band",
                "assumed": (
                    f"the repeating cell stays small against a wavelength, so only "
                    f"one wave travels each way and a two-port chain describes the "
                    f"whole structure. For a {period_m * 1e3:.2f} mm cell on eps_r="
                    f"{eps_r:.2f} that holds to about {onset_hz / 1e9:.2f} GHz, but "
                    f"the band runs to {f_high_hz / 1e9:.2f} GHz"
                ),
                "costs": (
                    "above that frequency the surface also throws power off at an "
                    "angle, which this model has no term for at all. Both the "
                    "transmission and the absorption reported near the top of the "
                    "band are then wrong in an unknown direction -- the missing "
                    "power is neither reflected straight back nor passed straight "
                    "through, and A = 1 - R - T silently books it as heat"
                ),
                "cheapest_test": (
                    "one periodic unit-cell solve at the top of the band with the "
                    "higher diffraction orders switched on, compared against this "
                    "model's transmission there"
                ),
            }
        )

    return validity
