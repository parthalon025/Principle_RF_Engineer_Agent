"""Closed-form absorption response of a ground-backed printed absorber --
the ANALYSIS-step model for the ABSORBER design family, replacing the
patch-antenna resonant-frequency formula that the loop applied to every
family regardless of what it was designing (issue #191).

WHAT THIS COMPUTES. One number the Success score can act on: the fraction
of incident power a printed metamaterial skin absorbs, at a stated
frequency, given its stack. In plain terms -- how much of the radar energy
hitting this surface turns into heat instead of bouncing back.

THE MODEL. Costa, Monorchio & Manara's equivalent-circuit absorber stack
(arXiv:1211.1902), with Luukkonen's grid capacitance -- the pairing map
#104 adopted at #111, superseding Maxwell-Garnett. Three elements:

  * A grounded dielectric spacer, treated as a short-circuited transmission
    line of length `thickness_m`: Z_d = j * eta_d * tan(beta * d). A
    quarter-wave from the ground plane this looks like an open circuit,
    which is what lets a resistive sheet above it dissipate rather than
    short out.
  * A patterned resistive sheet above it, as the patch's own resistance in
    SERIES with the gap capacitance between neighbouring patches. The
    resistance is sheet resistance multiplied by how many square tiles long
    the current path is (#128's finding: for a lossy printed element the
    geometry is the loss knob, not the film thickness).
  * The two in parallel, referenced to free space.

    A = 1 - |Gamma|^2,  Gamma = (Z_in - eta_0) / (Z_in + eta_0)

Transmission is absent by construction: the family requires a ground plane
(`designs.design_families.ABSORBER.requires_ground_plane`), so nothing gets
through and every non-reflected watt is dissipated. This model must NOT be
applied to a two-port structure -- Example 3's own published original is
two-port, and there absorptivity is 1 - |S11|^2 - |S21|^2.

WHAT IT IS NOT. This is a SCATTERING SURROGATE (#111): valid for predicting
reflection, never for extracting a material's own effective permittivity or
permeability. Homogenisation is provably invalid near resonance, which is
exactly where an absorber works.

A KNOWN, UNQUANTIFIED BIAS. Costa's eq (10) corrects the gap capacitance
for evanescent Floquet modes reflecting off the ground plane, which matter
once the spacer thins below ~0.3 * the cell period. That term has not been
recovered (#190). Its DIRECTION is known -- capacitance rises, so the true
resonance sits BELOW this model's prediction -- but not its magnitude. Every
response computed inside that regime carries `thin_spacer_bias_unrecovered`
in its `validity` list. Per this project's charter the model reports and
proceeds; it never refuses to return a number.
"""

from __future__ import annotations

import cmath
import math
from typing import Any

from rf_tools import physical_bounds
from rf_tools.calculations import (
    capacitive_grid_sheet_capacitance_f,
    grid_gap_loss_tangent,
    path_resistance_from_squares,
)

SPEED_OF_LIGHT_M_S = 299_792_458.0
ETA0_OHM = 376.730313412

# Below this spacer-thickness-to-period ratio, Costa's eq (10) evanescent
# correction is load-bearing and this model does not carry it (#190).
THIN_SPACER_RATIO = 0.3


def _require_positive(name: str, value: float) -> float:
    if value <= 0:
        raise ValueError(f"{name} must be positive; got {value!r}.")
    return float(value)


def grounded_slab_impedance(
    frequency_hz: float, eps_r: float, tan_delta: float, thickness_m: float
) -> complex:
    """Input impedance looking into a grounded dielectric spacer.

    A short-circuited transmission line of length `thickness_m`:

        Z_d = j * (eta_0 / n) * tan(k_0 * n * d),   n = sqrt(eps_r(1 - j tan_d))

    Returns a complex impedance in ohms. Lossy substrates give it a real
    part, which is the substrate's own dissipation -- adopting Costa's full
    model moved substrate loss on silicone from a few per cent of the loss
    budget to 20-36 % of it, so this term is not a rounding detail.
    """
    _require_positive("frequency_hz", frequency_hz)
    _require_positive("thickness_m", thickness_m)
    if eps_r < 1:
        raise ValueError(f"eps_r must be >= 1; got {eps_r!r}.")
    if tan_delta < 0:
        raise ValueError(f"tan_delta must be non-negative; got {tan_delta!r}.")

    eps_complex = eps_r * (1 - 1j * tan_delta)
    n = cmath.sqrt(eps_complex)
    k0 = 2 * math.pi * frequency_hz / SPEED_OF_LIGHT_M_S
    return 1j * (ETA0_OHM / n) * cmath.tan(k0 * n * thickness_m)


def patterned_sheet_impedance(
    frequency_hz: float,
    period_m: float,
    gap_m: float,
    eps_r: float,
    tan_delta: float,
    sheet_resistance_ohm_sq: float,
    squares: float,
) -> complex:
    """Impedance of the printed patterned layer: its own resistance in
    series with the capacitance of the gaps between neighbouring elements.

        Z_s = R_s * N_squares + 1 / (omega*C*tan_d_gap + j*omega*C)

    `squares` is how many square tiles long the current path is, which is
    what turns a printable sheet resistance into a useful one: a narrow ring
    multiplies it, a short wide bridge divides it. It is the design's loss
    knob, and it spans three orders of magnitude where printable film
    thickness spans about eight to one.
    """
    _require_positive("frequency_hz", frequency_hz)
    _require_positive("sheet_resistance_ohm_sq", sheet_resistance_ohm_sq)
    _require_positive("squares", squares)

    r_eff = path_resistance_from_squares(sheet_resistance_ohm_sq, squares)
    c_sheet = capacitive_grid_sheet_capacitance_f(period_m, gap_m, eps_r)
    tan_gap = grid_gap_loss_tangent(eps_r, tan_delta)

    omega = 2 * math.pi * frequency_hz
    # A lossy capacitor: Y = omega*C*tan_delta + j*omega*C. The real part is
    # the gap dielectric's dissipation, diluted by the air above the gap.
    y_cap = omega * c_sheet * tan_gap + 1j * omega * c_sheet
    return r_eff + 1 / y_cap


def absorptivity(
    frequency_hz: float,
    eps_r: float,
    tan_delta: float,
    thickness_m: float,
    period_m: float,
    gap_m: float,
    sheet_resistance_ohm_sq: float,
    squares: float,
) -> float:
    """Fraction of incident power absorbed (0..1) at one frequency, at
    normal incidence, for a ground-backed stack. See the module docstring
    for the model and its validity."""
    z_d = grounded_slab_impedance(frequency_hz, eps_r, tan_delta, thickness_m)
    z_s = patterned_sheet_impedance(
        frequency_hz, period_m, gap_m, eps_r, tan_delta, sheet_resistance_ohm_sq, squares
    )
    # The sheet and the grounded spacer sit in parallel across the same port.
    denom = z_s + z_d
    z_in = (z_s * z_d) / denom if abs(denom) > 0 else complex(float("inf"), 0)
    gamma = (z_in - ETA0_OHM) / (z_in + ETA0_OHM)
    absorbed = 1.0 - abs(gamma) ** 2
    # Numerical noise can put a passive stack a hair outside [0, 1]; clamp
    # rather than report a physically impossible number.
    return min(1.0, max(0.0, absorbed))


def absorber_band_response(
    f_low_hz: float,
    f_high_hz: float,
    eps_r: float,
    tan_delta: float,
    thickness_m: float,
    period_m: float,
    gap_m: float,
    sheet_resistance_ohm_sq: float,
    squares: float,
    points: int = 41,
) -> dict[str, Any]:
    """Sweep the required band and report the SINGLE WORST-ABSORBING
    frequency in it, not the mean and not the peak.

    That choice is #110's: averaging lets one lucky deep null hide a design
    that fails everywhere else, and a customer who asks for 90 % across a
    band is asking for 90 % at every frequency in it. In plain terms -- a
    surface is only as good as its weakest point in the band you care about.

    Returns the worst absorption and where it falls, the full curve, and a
    `validity` list naming every assumption that is load-bearing for THIS
    stack. `validity` never blocks the result; it travels with it.
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
        f = f_low_hz + i * step
        curve.append(
            {
                "frequency_hz": f,
                "absorption": absorptivity(
                    f,
                    eps_r,
                    tan_delta,
                    thickness_m,
                    period_m,
                    gap_m,
                    sheet_resistance_ohm_sq,
                    squares,
                ),
            }
        )

    worst = min(curve, key=lambda p: p["absorption"])
    best = max(curve, key=lambda p: p["absorption"])

    validity: list[dict[str, str]] = []

    ratio = thickness_m / period_m
    if ratio < THIN_SPACER_RATIO:
        validity.append(
            {
                "flag": "thin_spacer_bias_unrecovered",
                "assumed": (
                    f"spacer-to-period ratio is {ratio:.3f}, below "
                    f"{THIN_SPACER_RATIO}, where evanescent Floquet modes off the "
                    "ground plane raise the gap capacitance; Costa's eq (10) "
                    "correction for that is not implemented here (#190)"
                ),
                "costs": (
                    "the true resonance sits BELOW this prediction and the gap "
                    "needed for a target frequency is WIDER than computed; the "
                    "direction is known, the magnitude is not"
                ),
                "cheapest_test": (
                    "one Floquet unit-cell solve at this stack, compared against "
                    "this model's predicted resonance"
                ),
            }
        )

    ceiling_hz = physical_bounds.electrically_thin_ceiling_hz(thickness_m)
    if f_high_hz > ceiling_hz:
        validity.append(
            {
                "flag": "electrically_thick_at_band_top",
                "assumed": (
                    f"the spacer stays electrically thin, valid to "
                    f"{ceiling_hz / 1e9:.2f} GHz for {thickness_m * 1e3:.2f} mm, "
                    f"but the band runs to {f_high_hz / 1e9:.2f} GHz"
                ),
                "costs": (
                    "the lumped equivalent circuit stops representing the stack "
                    "near the top of the band, so absorption there is unreliable"
                ),
                "cheapest_test": "a full-wave solve at the top of the band only",
            }
        )

    # Rozanov advises, never gates (#129): a design that appears to beat the
    # bound means an assumption was violated, and saying so is the useful
    # output -- not a failed candidate.
    rozanov_floor_m = physical_bounds.rozanov_min_thickness_m(
        f_low_hz, f_high_hz, reflectivity_db=-10.0
    )
    if thickness_m < rozanov_floor_m:
        validity.append(
            {
                "flag": "below_rozanov_floor_for_10db",
                "assumed": (
                    f"a non-magnetic stack, for which Rozanov's floor across this "
                    f"band at -10 dB is {rozanov_floor_m * 1e3:.2f} mm; this stack "
                    f"is {thickness_m * 1e3:.2f} mm"
                ),
                "costs": (
                    "a -10 dB result across the WHOLE band is not physically "
                    "available at this thickness; a narrower band or a thicker "
                    "stack is; if the model reports one anyway, an assumption "
                    "behind it is wrong"
                ),
                "cheapest_test": (
                    "widen the stack to the floor and re-run, or narrow the band "
                    "to what the thickness affords"
                ),
            }
        )

    return {
        "function": "absorber_band_response",
        "worst_absorption": worst["absorption"],
        "worst_frequency_hz": worst["frequency_hz"],
        "best_absorption": best["absorption"],
        "best_frequency_hz": best["frequency_hz"],
        "curve": curve,
        "rozanov_min_thickness_m": rozanov_floor_m,
        "validity": validity,
        "provenance": "CALCULATED",
    }
