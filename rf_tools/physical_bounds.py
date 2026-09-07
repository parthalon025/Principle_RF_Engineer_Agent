"""Physical feasibility bounds -- the per-design-family functions that answer
"is this requirement achievable at all, by anyone?" before the loop spends a
solver run finding out (ADR-0018; CONTEXT.md: Physical bound; issue #109).

WHAT A PHYSICAL BOUND IS, AND WHY IT IS NOT ONE FUNCTION. Issue #109 settled
that `physical_bound` is "a genuinely different function per family -- Rozanov
for absorbers, Gustafsson & Sjoberg for reflection-phase steering,
Nel/Skrivervik/Gustafsson for patch antennas -- not one formula with a swapped
constant", and ADR-0018 made that the deciding argument for modelling the
design family registry as an open interface. This module is the evidence for
that decision rather than an assertion of it: the two bounds implemented here
take different inputs (a thickness and a band; a reference half-wave
simulation and a target frequency), return different quantities (a minimum
metres of stack-up; a dimensionless quality factor), and rest on different
physics (a causality/dispersion integral over a ground-backed slab; a stored-
energy-over-radiated-power ratio on a LOSSLESS substrate). Nothing about them
generalises into a shared signature, and pretending otherwise would put a
number in front of a designer that does not mean what they think it means.

THE ONE MISTAKE THIS MODULE EXISTS TO PREVENT. Both bounds sound like "the
best bandwidth you can get", and they are not interchangeable:

  * The Rozanov bound governs an absorber, whose bandwidth comes from power
    DISSIPATED in a deliberately lossy stack.
  * The patch Q-factor bound governs a radiator, whose bandwidth comes from
    power RADIATED away, and whose derivation assumes an explicitly lossless
    substrate, a PEC patch, a PEC ground, and (in the source's own appendix)
    "no ohmic losses".

Citing the patch bound against an absorber design -- or Rozanov against an
antenna -- is a category error that produces a confident, wrong, unfalsifiable
number. `docs/patch-q-factor-bound-primary-source.md` and
`docs/rozanov-bound-primary-source.md` are the first-hand readings behind each,
including the stated assumptions that decide applicability. The registry in
`designs/design_families.py` is what keeps them apart in practice, by making a
family declare which one it is entitled to.

PROVENANCE. Every formula here is `LITERATURE-SUPPORTED` -- read from the
primary source, not from a secondary restatement (which for Rozanov matters:
the widely-quoted "lambda/17" is the paper's ABSTRACT rounding of its own
derivation's 17.2). Values this module returns are `CALCULATED`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

SPEED_OF_LIGHT_M_S = 299_792_458.0

# Impedance of free space, the reference a sheet resistance is compared
# against. CODATA-consistent value used repo-wide (a Salisbury screen's
# 376.73 ohm/sq resistive sheet is the canonical instance).
FREE_SPACE_IMPEDANCE_OHM = 376.730313412


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------


def _require_positive(name: str, value: float) -> float:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number; got {value!r}.")
    return float(value)


def _require_band(f_low_hz: float, f_high_hz: float) -> tuple[float, float]:
    low = _require_positive("f_low_hz", f_low_hz)
    high = _require_positive("f_high_hz", f_high_hz)
    if high <= low:
        raise ValueError(
            f"f_high_hz must be strictly greater than f_low_hz; got {low!r} and {high!r}."
        )
    return low, high


def reflectivity_db_to_magnitude(reflectivity_db: float) -> float:
    """|rho| (linear, 0..1) from a reflectivity stated in dB.

    Accepts either sign convention -- a target is written "-10 dB" as often
    as "10 dB of reduction" -- and interprets both as the same 0.3162
    magnitude, since a reflectivity above unity is not a target anyone
    means. This is the conversion Rozanov's own Eq. (10) folds into its
    `Gamma_0 = 20 log rho_0`.
    """
    if not math.isfinite(reflectivity_db):
        raise ValueError(f"reflectivity_db must be finite; got {reflectivity_db!r}.")
    magnitude_db = -abs(reflectivity_db)
    if magnitude_db == 0:
        raise ValueError(
            "reflectivity_db must be non-zero: 0 dB is total reflection, for which "
            "the Rozanov integral is unbounded and every thickness 'passes'."
        )
    return 10.0 ** (magnitude_db / 20.0)


# --------------------------------------------------------------------------
# ABSORBER family: the Rozanov bound
# --------------------------------------------------------------------------
#
# K. N. Rozanov, "Ultimate thickness to bandwidth ratio of radar absorbers",
# IEEE Trans. Antennas Propag. 48(8):1230-1234, 2000.
# doi:10.1109/8.884491. Read first-hand in
# docs/rozanov-bound-primary-source.md; equation numbers below are Rozanov's.
#
# The working form, Eq. (9) -- what a design is actually measured against:
#
#     |ln rho_0| * (lambda_max - lambda_min)  <  2 * pi^2 * SUM_i mu_s,i d_i
#
# Read left to right it is a statement about area under a curve: the total
# "absorbing work" a ground-backed slab can do, integrated across all
# wavelengths, is capped by its thickness. Spend it on a wide band and you
# get shallow absorption; spend it on deep absorption and you get a narrow
# band. mu_s (the static relative permeability) is the ONLY term a design
# can raise above 1, which is why magnetic loading is the only lever that
# moves the bound rather than merely approaching it.
#
# IN PLAIN TERMS: a thin absorber cannot also be a broadband one, and the
# exchange rate between the two is fixed by physics rather than by
# cleverness. If a requirement asks for both beyond what this allows, no
# amount of design effort produces it -- the honest answer is "make it
# thicker, accept a narrower band, or add magnetic material".
#
# VALIDITY BOX (from the paper's own Sections II-III, not inferred): a
# metal-backed magnetodielectric slab, normal incidence, passive and
# causal materials, mu_s finite. It bounds a GROUND-BACKED reflector; it
# says nothing about a transmitting (two-port) structure.


def rozanov_min_thickness_m(
    f_low_hz: float,
    f_high_hz: float,
    reflectivity_db: float,
    mu_s: float = 1.0,
) -> float:
    """Thinnest ground-backed absorber that could reach `reflectivity_db`
    across `f_low_hz`..`f_high_hz` -- a floor no design beats, not a target.

    Rozanov Eq. (9), solved for thickness:

        d_min = |ln rho_0| * (lambda_max - lambda_min) / (2 * pi^2 * mu_s)

    `mu_s` defaults to 1.0, the non-magnetic case, which is the relevant one
    for a printed skin: a printed conductor pattern on a dielectric host has
    no static permeability to spend, so `mu_s > 1` requires deliberately
    adding a magnetic filler and should be passed only when the stack
    actually contains one.

    The famous "an absorber cannot be thinner than lambda_max/17.2" is this
    function's own wide-band limit (f_high >> f_low) at -10 dB, not a
    separate rule -- see `rozanov_broadband_thickness_floor_m`.
    """
    low, high = _require_band(f_low_hz, f_high_hz)
    _require_positive("mu_s", mu_s)
    rho_0 = reflectivity_db_to_magnitude(reflectivity_db)
    lambda_max = SPEED_OF_LIGHT_M_S / low
    lambda_min = SPEED_OF_LIGHT_M_S / high
    return abs(math.log(rho_0)) * (lambda_max - lambda_min) / (2 * math.pi**2 * mu_s)


def rozanov_broadband_thickness_floor_m(
    f_low_hz: float, reflectivity_db: float = -10.0, mu_s: float = 1.0
) -> float:
    """The wide-band (lambda_max >> lambda_min) floor, Rozanov Eq. (10):

        lambda_max * |Gamma_0|  <=  40 * pi^2 * SUM mu_s,i d_i / ln(10)

    At -10 dB and mu_s = 1 this is `lambda_max / 17.2`. NOTE that 17.2 is
    the DERIVATION's value; the paper's abstract rounds it to 17, and that
    rounding is the route by which the figure reaches most secondary
    sources. Prefer `rozanov_min_thickness_m` when the band is actually
    known -- this form deliberately throws away `f_high` and is therefore
    the more permissive (thinner) of the two.
    """
    low = _require_positive("f_low_hz", f_low_hz)
    _require_positive("mu_s", mu_s)
    lambda_max = SPEED_OF_LIGHT_M_S / low
    gamma_0_db = abs(reflectivity_db)
    if gamma_0_db == 0:
        raise ValueError("reflectivity_db must be non-zero.")
    return lambda_max * gamma_0_db * math.log(10.0) / (40 * math.pi**2 * mu_s)


def rozanov_max_fractional_bandwidth(
    thickness_m: float,
    center_frequency_hz: float,
    reflectivity_db: float,
    mu_s: float = 1.0,
) -> float:
    """Widest fractional bandwidth `(f_high - f_low) / f_center` a
    ground-backed absorber of `thickness_m` could hold at `reflectivity_db`,
    centred on `center_frequency_hz`. The inverse question to
    `rozanov_min_thickness_m`, and the one a requirement usually poses.

    Returns a fraction (0.4 == 40 %), or `math.inf` when the thickness is
    sufficient for an unbounded band about that centre -- which is not a
    promise of infinite bandwidth but a statement that the Rozanov integral
    has stopped being the binding constraint, and something else (the
    electrical-thickness ceiling, the matching network, the ink) decides.

    Derivation, from Eq. (9) with a band symmetric in frequency about f_c
    (f_low = f_c(1 - B/2), f_high = f_c(1 + B/2)):

        lambda_max - lambda_min = (c / f_c) * [1/(1 - B/2) - 1/(1 + B/2)]
                                = (c / f_c) * B / (1 - B^2/4)

    so with  S = 2 pi^2 mu_s d f_c / (|ln rho_0| c)  the bound becomes
    B / (1 - B^2/4) <= S, a quadratic in B whose admissible root is

        B = 2 * (sqrt(S^2 + 1) - 1) / S
    """
    d = _require_positive("thickness_m", thickness_m)
    f_c = _require_positive("center_frequency_hz", center_frequency_hz)
    _require_positive("mu_s", mu_s)
    rho_0 = reflectivity_db_to_magnitude(reflectivity_db)
    s = 2 * math.pi**2 * mu_s * d * f_c / (abs(math.log(rho_0)) * SPEED_OF_LIGHT_M_S)
    if s <= 0:
        return 0.0
    fractional = 2 * (math.sqrt(s * s + 1) - 1) / s
    # B -> 2 is the limit where f_low -> 0; past that the band no longer has
    # a positive lower edge and the fractional-bandwidth question is not the
    # one being asked.
    return math.inf if fractional >= 2.0 else fractional


def rozanov_lowest_feasible_center_hz(
    thickness_m: float,
    fractional_bandwidth: float,
    reflectivity_db: float,
    mu_s: float = 1.0,
) -> float:
    """Lowest centre frequency at which `thickness_m` can still hold
    `fractional_bandwidth` at `reflectivity_db` -- the LOW-FREQUENCY WALL of
    a fixed thickness budget.

    This is the number that decides which customer requirements a fixed skin
    budget can serve at all. For the programme's 0.87-2.0 mm budget at a
    40 % band and 90 % absorption (-10 dB) it returns 8.37 GHz and 3.64 GHz
    respectively -- reproducing `docs/five-paper-absorber-corpus-findings.md`
    Section 2, which derived them by hand.

    Inverts the quadratic in `rozanov_max_fractional_bandwidth`: solving
    B = 2(sqrt(S^2+1) - 1)/S for S gives S = 4B / (4 - B^2), and S is linear
    in f_c.
    """
    d = _require_positive("thickness_m", thickness_m)
    b = _require_positive("fractional_bandwidth", fractional_bandwidth)
    _require_positive("mu_s", mu_s)
    if b >= 2.0:
        raise ValueError(
            "fractional_bandwidth must be < 2.0 (a band symmetric about f_c with a "
            f"positive lower edge); got {b!r}."
        )
    rho_0 = reflectivity_db_to_magnitude(reflectivity_db)
    s = 4 * b / (4 - b * b)
    return s * abs(math.log(rho_0)) * SPEED_OF_LIGHT_M_S / (2 * math.pi**2 * mu_s * d)


# --------------------------------------------------------------------------
# The other wall: electrical thickness
# --------------------------------------------------------------------------
#
# Rozanov bounds a fixed thickness from BELOW in frequency. The opposite
# wall is not a bound at all but a MODEL VALIDITY limit: an "electrically
# thin metamaterial skin" stops being one once the stack is a meaningful
# fraction of a wavelength, at which point it is a multi-mode dielectric
# slab and needs a different model -- a different design family, not a
# rescaled one. lambda/10 is the conventional dividing line.


def electrically_thin_ceiling_hz(thickness_m: float, wavelength_fraction: float = 0.10) -> float:
    """Highest frequency at which `thickness_m` is still electrically thin.

    Above the returned frequency the thin-skin framing expires: the stack is
    no longer a sheet perturbing a wave, it is a slab the wave propagates
    inside, and a circuit-model surrogate (Luukkonen/Costa and friends) is
    outside its validity box. `wavelength_fraction` defaults to 0.10, the
    usual lambda/10 convention; state it explicitly if a family uses another.

    For the programme's budget: 0.87 mm expires at 34.5 GHz, 2.0 mm at
    15.0 GHz.
    """
    d = _require_positive("thickness_m", thickness_m)
    frac = _require_positive("wavelength_fraction", wavelength_fraction)
    return frac * SPEED_OF_LIGHT_M_S / d


@dataclass(frozen=True)
class ThinSkinWindow:
    """The frequency window a fixed thickness budget can serve as a thin
    absorber skin: Rozanov from below, electrical thickness from above."""

    thickness_m: float
    lowest_feasible_center_hz: float
    electrically_thin_ceiling_hz: float

    @property
    def is_empty(self) -> bool:
        """True when the two walls have crossed -- the budget cannot serve
        this bandwidth/reflectivity requirement at ANY frequency."""
        return self.lowest_feasible_center_hz >= self.electrically_thin_ceiling_hz


def thin_skin_absorber_window(
    thickness_m: float,
    fractional_bandwidth: float,
    reflectivity_db: float,
    mu_s: float = 1.0,
    wavelength_fraction: float = 0.10,
) -> ThinSkinWindow:
    """Both walls of a thickness budget at once.

    The budget "fails at both ends, for opposite reasons": below the lower
    wall physics forbids the bandwidth, above the upper wall the thin-skin
    model expires. Neither end is a design deficiency to be optimised away.
    """
    return ThinSkinWindow(
        thickness_m=thickness_m,
        lowest_feasible_center_hz=rozanov_lowest_feasible_center_hz(
            thickness_m, fractional_bandwidth, reflectivity_db, mu_s
        ),
        electrically_thin_ceiling_hz=electrically_thin_ceiling_hz(
            thickness_m, wavelength_fraction
        ),
    )


# --------------------------------------------------------------------------
# PATCH family: the Nel/Skrivervik/Gustafsson Q-factor bound
# --------------------------------------------------------------------------
#
# D. Nel, A. K. Skrivervik & M. Gustafsson, "Q-factor Bounds for Microstrip
# Patch Antennas", IEEE Trans. Antennas Propag., 2023.
# doi:10.1109/TAP.2023.3243726 (preprint: Lund University TEAT-7275).
# Read first-hand in docs/patch-q-factor-bound-primary-source.md.
#
# Q = 2 * omega * max{W_e, W_m} / P_d,  with  P_d = P_r + P_sw
#
# READ THE DENOMINATOR. P_d is radiated power plus surface-wave leakage --
# energy that gets AWAY, not energy turned into heat. The model is an
# infinite PEC ground plane, an infinite LOSSLESS dielectric, a PEC patch,
# and (appendix, verbatim) "no ohmic losses". This bound therefore does not
# apply to an absorber, whose entire bandwidth mechanism is the dissipation
# this model excludes by construction.
#
# VALIDITY BOX, from the paper's own statements:
#   1. ONE dominant resonance over the bandwidth.
#   2. NO vertical structure -- shorting pins, stacked patches and
#      miniaturised ground planes are named and explicitly excluded.
#   3. Lossless throughout.
#   4. Two-resonance widening is listed in the conclusion as FUTURE WORK,
#      so this bound cannot be cited against a multi-resonance design.


def patch_q_factor_lower_bound(
    frequency_hz: float,
    half_wave_reference_frequency_hz: float,
    half_wave_reference_q: float,
) -> float:
    """Lowest Q -- so widest bandwidth -- any patch geometry could achieve at
    `frequency_hz`, given one reference half-wave-resonant patch on the same
    substrate and design region (Eq. 5.1):

        Q_lb(f) = Q_hw * (f_hw / f)^5

    IN PLAIN TERMS: shrinking a patch below its natural half-wavelength size
    costs bandwidth as the FIFTH power of how far you shrink it. Halve the
    size and roughly thirty times the bandwidth is gone. That is far steeper
    than the cube of the free-space Chu bound, and the paper attributes the
    difference to the ground plane, calling the result "orders of magnitude
    tighter than the Chu bound".

    The bound is computed by current optimisation over EVERY admissible
    current distribution in the design region, so it is not a comparison
    against a shortlist of shapes -- real published designs sit within 10 %
    of it, meaning single-resonance shape optimisation has almost nothing
    left to give. Widening is the cheap lever instead: Q falls roughly
    linearly with patch width.

    `half_wave_reference_q` comes from one simulation of a half-wave patch
    on the same substrate -- cheap, but it IS a required input, which is
    exactly why this bound cannot share a signature with Rozanov's.

    Raises when `frequency_hz` exceeds the half-wave reference: the
    fifth-power form is stated for the BELOW-resonance regime, and above it
    the expression would return an optimistic number outside its own
    derivation.
    """
    f = _require_positive("frequency_hz", frequency_hz)
    f_hw = _require_positive("half_wave_reference_frequency_hz", half_wave_reference_frequency_hz)
    q_hw = _require_positive("half_wave_reference_q", half_wave_reference_q)
    if f > f_hw:
        raise ValueError(
            "patch_q_factor_lower_bound is the below-half-wave-resonance scaling "
            f"(Eq. 5.1); frequency_hz={f!r} is above the half-wave reference "
            f"{f_hw!r}, where the fifth-power form does not apply."
        )
    return q_hw * (f_hw / f) ** 5


def patch_max_fractional_bandwidth(
    frequency_hz: float,
    half_wave_reference_frequency_hz: float,
    half_wave_reference_q: float,
    vswr: float = 2.0,
) -> float:
    """Widest fractional bandwidth a patch could hold at `frequency_hz`, by
    converting `patch_q_factor_lower_bound` through the standard
    VSWR-bandwidth relation already in `rf_tools.calculations`.

    `vswr` defaults to 2.0, this repo's existing convention. Pass 1.92496
    for the -10 dB return-loss definition the source paper uses in its own
    worked example.
    """
    from rf_tools.calculations import fractional_bandwidth_from_q

    q_lb = patch_q_factor_lower_bound(
        frequency_hz, half_wave_reference_frequency_hz, half_wave_reference_q
    )
    return fractional_bandwidth_from_q(q_lb, vswr=vswr)
