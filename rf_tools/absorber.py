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

THE THIN-SPACER BIAS, NOW CARRIED (#245). Costa's eq (10) corrects the gap
capacitance for evanescent Floquet modes reflecting off the ground plane --
the printed pattern couples to its own mirror image and stores more charge
than a free-standing grid would:

    C0_thin = C0 - (2p*eps_0/pi) * ln(1 - exp(-4*pi*d/p))

p the cell period, d the spacer thickness. Costa, Genovesi, Monorchio &
Manara, arXiv:1211.1902 eq (10); published as IEEE TAP 61(3), 1201-1209.
This model APPLIES that term -- `absorptivity` hands `thickness_m` down to
`capacitive_grid_sheet_capacitance_f`, which composes it. What used to be
flagged here as unrecovered (#190) is recovered; the flag that replaced it
is narrower and is described below.

*In plain terms: the closer the ground plane sits behind the printed
pattern, the more charge builds up between the two, and the lower the
surface resonates. Leaving the term out drew the resonance about 1% too
high at #128's design point.*

APPLIED UNCONDITIONALLY, NOT GATED AT `THIN_SPACER_RATIO`. Costa writes the
regime boundary as `if (d > 0.3D)`, but eq (10) itself decays smoothly --
about 2.2% of C0 at d/p = 0.25, under 0.1% at d/p = 0.5 -- and is the better
approximation on both sides of that ratio. Gating it at 0.3 would put a step
discontinuity in the capacitance at exactly the ratio this programme's
designs cluster around, which is an optimiser hazard with no physics behind
it. This is a reasoned deviation from a literal reading of the paper.

WHAT IS STILL DISPUTED (#234). The same author publishes the same equation
twice with different prefactors applied at different points: `2D*eps_0/pi`
substituted into the UNLOADED C0 (Costa et al. 2013, the conservative
default here), and `2D*eps_0*eps_r/pi` subtracted from an ALREADY-LOADED
capacitance (Costa & Borgese 2021, arXiv:2102.10666). On the loaded
capacitance the two differ by `eps_r/eps_eff` -- 1.487 at eps_r = 2.9, NOT
by eps_r -- because the 2021 form never meets eq (6)'s eps_eff loading. At
#128's design point that is 9.893 GHz against 9.843 GHz, from an uncorrected
10.000 GHz. Responses inside the thin-spacer regime carry
`thin_spacer_prefactor_disputed`, and every response records which form
produced it in `costa_eq10_prefactor`. Per this project's charter the model
reports and proceeds; it never refuses to return a number. See
`docs/costa-thin-spacer-correction.md`.
"""

from __future__ import annotations

import cmath
import math
from typing import Any

from rf_tools import physical_bounds
from rf_tools.calculations import (
    COSTA_EQ10_PREFACTOR,
    capacitive_grid_sheet_capacitance_f,
    grid_effective_permittivity,
    grid_gap_loss_tangent,
    path_resistance_from_squares,
)

SPEED_OF_LIGHT_M_S = 299_792_458.0
ETA0_OHM = 376.730313412

# Costa's regime boundary, `if (d > 0.3D)`. Its job here changed at #245:
# it no longer gates a warning about a MISSING term -- the term is applied at
# every ratio -- it marks where the correction is large enough (a couple of
# per cent of C0 and rising) that the unresolved disagreement between the two
# published forms of eq (10) could change a decision. Above it the two forms
# differ by less than a tenth of a per cent and nobody needs telling.
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
    gap_m: float | None,
    eps_r: float,
    tan_delta: float,
    sheet_resistance_ohm_sq: float,
    squares: float,
    spacer_thickness_m: float | None = None,
) -> complex:
    """Impedance of the printed conductive layer.

    Patterned (`gap_m` a length): the element's own resistance in series
    with the capacitance of the gaps between neighbouring elements.

        Z_s = R_s * N_squares + 1 / (omega*C*tan_d_gap + j*omega*C)

    Unpatterned (`gap_m=None`): a continuous sheet with no gaps anywhere,
    so there is no gap capacitance and the layer is purely resistive.

        Z_s = R_s * N_squares

    `gap_m=None` is NOT the same as a very small gap, and cannot be reached
    by shrinking one. Luukkonen's grid capacitance diverges only
    logarithmically -- `ln(1/sin(pi*g/2p))` -- so even a 1 nm gap on a 3 mm
    period leaves about 65 ohm of reactance at 10 GHz, enough to drag a
    resonance a full GHz. A continuous sheet is a different structure, not
    a limiting case, and it needs its own branch.

    Found by cross-checking a Salisbury screen against a Meep FDTD run: the
    closed form put the absorption peak at 9 GHz where Meep (and theory)
    put it at 10. Without this branch the model could not reproduce the
    canonical absorber at all, which also meant it could not be validated
    against one.

    `squares` is how many square tiles long the current path is, which is
    what turns a printable sheet resistance into a useful one: a narrow ring
    multiplies it, a short wide bridge divides it. It is the design's loss
    knob, and it spans three orders of magnitude where printable film
    thickness spans about eight to one. A continuous sheet is 1 square by
    definition, so `squares` should be 1.0 when `gap_m` is None.
    """
    _require_positive("frequency_hz", frequency_hz)
    _require_positive("sheet_resistance_ohm_sq", sheet_resistance_ohm_sq)
    _require_positive("squares", squares)

    r_eff = path_resistance_from_squares(sheet_resistance_ohm_sq, squares)
    if gap_m is None:
        return complex(r_eff, 0.0)

    c_sheet = capacitive_grid_sheet_capacitance_f(
        period_m, gap_m, eps_r, spacer_thickness_m=spacer_thickness_m
    )
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
    gap_m: float | None,
    sheet_resistance_ohm_sq: float,
    squares: float,
) -> float:
    """Fraction of incident power absorbed (0..1) at one frequency, at
    normal incidence, for a ground-backed stack. See the module docstring
    for the model and its validity.

    `thickness_m` reaches the sheet as well as the slab: it is the spacer
    the wave travels through AND the distance to the mirror the patches
    couple to, so it sets both the slab's electrical length and Costa's
    eq (10) thin-spacer capacitance correction (#245). The signature is
    unchanged -- the correction needed no new input, only the existing one
    carried one level further down.
    """
    z_d = grounded_slab_impedance(frequency_hz, eps_r, tan_delta, thickness_m)
    z_s = patterned_sheet_impedance(
        frequency_hz,
        period_m,
        gap_m,
        eps_r,
        tan_delta,
        sheet_resistance_ohm_sq,
        squares,
        spacer_thickness_m=thickness_m,
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
    gap_m: float | None,
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

    It also returns `costa_eq10_prefactor`: which of the two published forms
    of Costa's thin-spacer correction produced these numbers (#234, #245).
    That is a module-level choice in `rf_tools.calculations`, not an argument
    here -- a caller free to vary it design-by-design could pick whichever
    form flatters the candidate in front of them. Recording it is what lets
    two runs that disagree be told apart from two runs of different code.
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
        # The correction is APPLIED at every ratio; what this flag reports is
        # the one thing #245 could not settle -- which of two published
        # prefactors, applied at which point, is the right one (#234). Below
        # 0.3 the two answers are far enough apart to matter; above it they
        # differ by under a tenth of a per cent and warning would be noise.
        form_gap = eps_r / grid_effective_permittivity(eps_r)
        validity.append(
            {
                "flag": "thin_spacer_prefactor_disputed",
                "assumed": (
                    f"spacer-to-period ratio is {ratio:.3f}, below "
                    f"{THIN_SPACER_RATIO}, so Costa's eq (10) thin-spacer "
                    "correction is numerically significant here. It IS applied "
                    f"(#245), in the '{COSTA_EQ10_PREFACTOR}' form -- Costa et "
                    "al. 2013, arXiv:1211.1902 eq (10), prefactor 2D*eps_0/pi "
                    "substituted into the unloaded grid capacitance. The same "
                    "author publishes a second form -- Costa & Borgese 2021, "
                    "arXiv:2102.10666 eq (10), prefactor 2D*eps_0*eps_r/pi "
                    "subtracted from an already-loaded capacitance -- which "
                    f"lands eps_r/eps_eff = {form_gap:.3f} times larger on the "
                    "loaded capacitance. Which is right is unresolved (#234). "
                    "In plain terms: both papers agree extra charge builds up "
                    "between the pattern and the ground plane, and disagree by "
                    "about half again over how much"
                ),
                "costs": (
                    "if the other form is the right one this stack resonates "
                    "lower still, by roughly another half a per cent in "
                    "frequency: at #128's design point an uncorrected 10.000 "
                    "GHz becomes 9.893 GHz under this form and 9.843 GHz under "
                    "the other, and the gap needed to hold a target frequency "
                    "widens by about another 14 um. That is a trim to a "
                    "geometry, not a different design -- but it is larger than "
                    "the tolerance a printed gap is drawn to"
                ),
                "cheapest_test": (
                    "read the original both papers cite -- Tretyakov & Simovski "
                    "2003 -- and see which prefactor it carries; it is closed "
                    "access with no repository copy found so far "
                    "(RUNNING-LISTS.md section 1), so the fallback is one "
                    "Floquet unit-cell full-wave solve of this stack, whose "
                    "resonance separates the two forms by about 0.5%"
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
        # Which published form of Costa's eq (10) produced these numbers.
        # #234 is a live question and settling it moves every resonance in
        # this file; a result that does not say which form it used cannot be
        # compared against one computed before or after that change.
        "costa_eq10_prefactor": COSTA_EQ10_PREFACTOR,
        "validity": validity,
        "provenance": "CALCULATED",
    }
