"""Patch antenna synthesis: resonant frequency, bandwidth, curvature effects,
and aperture gain (split out of rf_tools/calculations.py, issue #522/#500)."""

from math import radians, sin

import numpy as np


def wavelength(f_hz: float, c_m_s: float = 299_792_458.0) -> float:
    if f_hz <= 0:
        raise ValueError("Frequency must be positive.")
    return c_m_s / f_hz


# --- Conformal antenna: resonant frequency and bandwidth ---
#
# The functions below implement the standard microstrip patch antenna
# transmission-line model (Balanis, "Antenna Theory: Analysis and Design",
# the widely-used starting point for "resonant frequency from substrate +
# dimensions"). All geometric inputs/outputs are in metres, all frequencies
# in hertz.


def patch_effective_permittivity(eps_r: float, w_m: float, h_m: float) -> float:
    """Effective dielectric constant of a microstrip patch (transmission-line model).

    Standard result (Balanis, "Antenna Theory", transmission-line model for
    a rectangular microstrip patch):

        eps_eff = (eps_r+1)/2 + (eps_r-1)/2 * (1 + 12*h/W)^(-0.5)

    where eps_r is the substrate's relative dielectric constant, h is the
    substrate thickness (m), and W is the patch width (m). Only valid for
    W/h > 1 (the wide-microstrip regime the formula was derived for); a
    narrower patch needs a different fringing-field model not implemented
    here.
    """
    if eps_r <= 1:
        raise ValueError(
            "patch_effective_permittivity's fringing-field fit is only "
            "valid for eps_r > 1 (it interpolates between eps_r and 1)."
        )
    if h_m <= 0:
        raise ValueError("Substrate thickness h_m must be positive.")
    if w_m <= 0:
        raise ValueError("Patch width w_m must be positive.")
    if w_m / h_m <= 1:
        raise ValueError(
            "patch_effective_permittivity is only valid for W/h > 1 "
            "(wide-microstrip transmission-line model)."
        )
    return (eps_r + 1) / 2 + (eps_r - 1) / 2 * (1 + 12 * h_m / w_m) ** -0.5


def patch_length_extension_m(eps_eff: float, w_m: float, h_m: float) -> float:
    """Fringing-field length extension dL for a microstrip patch, in metres.

    Standard result (Balanis, "Antenna Theory", transmission-line model):
    the patch's fringing fields make it look electrically longer than its
    physical length L by 2*dL (one extension per radiating edge), with

        dL = 0.412*h*(eps_eff+0.3)*(W/h+0.264) / ((eps_eff-0.258)*(W/h+0.8))

    where eps_eff is the effective permittivity (see
    patch_effective_permittivity), h the substrate thickness (m), and W the
    patch width (m).
    """
    if eps_eff <= 0.258:
        raise ValueError(
            "patch_length_extension_m requires eps_eff > 0.258 "
            "(the fringing-extension formula's denominator is undefined otherwise)."
        )
    if w_m <= 0:
        raise ValueError("Patch width w_m must be positive.")
    if h_m <= 0:
        raise ValueError("Substrate thickness h_m must be positive.")
    w_over_h = w_m / h_m
    return (
        0.412 * h_m * (eps_eff + 0.3) * (w_over_h + 0.264) / ((eps_eff - 0.258) * (w_over_h + 0.8))
    )


def patch_resonant_frequency_hz(
    eps_r: float,
    w_m: float,
    h_m: float,
    l_m: float,
    c_m_s: float = 299_792_458.0,
) -> float:
    """Dominant-mode (TM010) resonant frequency of a rectangular microstrip patch.

    Standard microstrip transmission-line model result (Balanis, "Antenna
    Theory"):

        eps_eff = patch_effective_permittivity(eps_r, w_m, h_m)
        dL      = patch_length_extension_m(eps_eff, w_m, h_m)
        L_eff   = L + 2*dL
        f_r     = c / (2 * L_eff * sqrt(eps_eff))

    where L is the patch's physical (flat, nominally uncurved) resonant
    length. This is the reference "as-designed-flat" resonant frequency
    that curvature_shifted_resonant_frequency_hz perturbs for a curved
    host surface -- see that function's docstring, and the "Conformal
    antenna" definition in CONTEXT.md, for how the two connect.
    """
    if l_m <= 0:
        raise ValueError("Patch length l_m must be positive.")
    if c_m_s <= 0:
        raise ValueError("Speed of light c_m_s must be positive.")
    eps_eff = patch_effective_permittivity(eps_r, w_m, h_m)
    dl = patch_length_extension_m(eps_eff, w_m, h_m)
    l_eff = l_m + 2 * dl
    return c_m_s / (2 * l_eff * eps_eff**0.5)


# --- Microstrip transmission-line synthesis lives in rf_tools/microstrip_line.py ---
#
# microstrip_effective_permittivity, microstrip_characteristic_impedance_ohm,
# and microstrip_synthesize_width_m (issue #286) live there, along with the
# module-level comment explaining why they are deliberately distinct from
# patch_effective_permittivity/patch_length_extension_m just above, despite
# sharing the same underlying fringing-field formula.


# --- Fractional bandwidth <-> quality factor ---
#
# Standard antenna-engineering relation between an antenna's (loaded)
# quality factor Q and its impedance bandwidth for a given VSWR threshold
# (Balanis, "Antenna Theory"; also Pozar, "Microwave Engineering", sec.
# 6.x resonator-bandwidth treatment, applied to an antenna's resonant
# input impedance):
#
#     FBW = (VSWR - 1) / (Q * sqrt(VSWR))
#
# where FBW = Delta_f / f_r is the fractional bandwidth over which the
# antenna's VSWR stays at or below the given threshold. This is the
# VSWR-dependent bandwidth definition (not the simpler FBW = 1/Q, which is
# the special case of a matched-load half-power/3-dB bandwidth, VSWR ~
# 2.618 -- deliberately not assumed here since VSWR targets in antenna
# design are usually stated explicitly, most commonly VSWR = 2.0).


def fractional_bandwidth_from_q(q: float, vswr: float = 2.0) -> float:
    """Fractional impedance bandwidth from quality factor Q, for a given VSWR threshold.

        FBW = (VSWR - 1) / (Q * sqrt(VSWR))

    vswr defaults to 2.0 (the standard 2:1 VSWR bandwidth definition
    commonly used in antenna design, corresponding to -9.54 dB return
    loss). See module notes above for the formula's source.
    """
    if q <= 0:
        raise ValueError("Quality factor Q must be positive.")
    if vswr <= 1:
        raise ValueError("VSWR must be > 1.")
    return (vswr - 1) / (q * vswr**0.5)


def quality_factor_from_fractional_bandwidth(fbw: float, vswr: float = 2.0) -> float:
    """Quality factor Q from fractional impedance bandwidth, for a given VSWR threshold.

    Inverse of fractional_bandwidth_from_q:

        Q = (VSWR - 1) / (FBW * sqrt(VSWR))
    """
    if fbw <= 0:
        raise ValueError("Fractional bandwidth must be positive.")
    if vswr <= 1:
        raise ValueError("VSWR must be > 1.")
    return (vswr - 1) / (fbw * vswr**0.5)


# --- Curvature-induced resonant-frequency shift ---
#
# APPROXIMATION NOTICE: unlike the formulas above, there is no single
# settled closed-form textbook formula for exactly how much a microstrip
# patch's resonant frequency shifts when it is conformed to a curved host
# surface -- the general conformal-antenna literature (e.g. Josefsson &
# Persson, "Conformal Array Antenna Theory and Design"; various microstrip-
# on-cylinder studies) agrees curvature perturbs the resonant frequency by
# effectively changing the patch's electrical length as seen by the
# resonant cavity mode, but the reported magnitude/sign vary by bend axis
# (E-plane vs. H-plane), substrate properties, and analysis method, and
# usually require full-wave simulation to pin down precisely.
#
# The model implemented here is a first-order *geometric* proxy for that
# effect, not a re-derivation of a specific paper's result. It models a
# patch of fixed physical (material) length L -- i.e. conformed to the
# host surface by bending, not by stretching -- as an arc of a circle of
# radius R (the host's radius of curvature). The straight-line separation
# between the patch's two radiating edges (the "chord") is what actually
# sets the free-space fringing-field geometry the cavity model depends on,
# and is exactly (circular-arc chord-length geometry):
#
#     chord = 2*R*sin(L / (2*R))
#
# which is always < L for R finite, i.e. curvature always shortens that
# edge-to-edge separation relative to the flat design. Treating the
# resonant frequency as inversely proportional to that edge separation
# (consistent with f_r ~ 1/L_eff in the flat-patch formula above) gives
# the first-order curvature correction:
#
#     f_r_curved = f_r_flat * L / chord = f_r_flat * L / (2*R*sin(L/(2*R)))
#
# This always predicts a small frequency *increase* under curvature (chord
# < L), consistent with the general literature direction ("curvature
# changes the effective electrical length") for a bend that shortens the
# edge-to-edge span; it does not capture bend-axis-dependent sign reversals
# reported in some studies. Validity is restricted to L/R < 0.5 (a
# moderate-curvature regime where the geometric picture above stays a
# credible first-order proxy); treat results near that bound as order-of-
# magnitude estimates only, and validate against simulation/measurement
# before using this for a final design.


def curvature_length_correction_factor(l_m: float, radius_of_curvature_m: float) -> float:
    """First-order geometric length-correction factor for a patch bent to radius R.

    Returns L / chord = L / (2*R*sin(L/(2*R))), always >= 1 -- see the
    module notes above (under "Curvature-induced resonant-frequency
    shift") for the derivation, its approximation status, and its citation.
    Restricted to L/R < 0.5.
    """
    if l_m <= 0:
        raise ValueError("Patch length l_m must be positive.")
    if radius_of_curvature_m <= 0:
        raise ValueError("Radius of curvature must be positive.")
    if l_m / radius_of_curvature_m >= 0.5:
        raise ValueError(
            "curvature_length_correction_factor is only valid for L/R < 0.5 "
            "(moderate-curvature regime; see module notes for the approximation "
            "this bound protects)."
        )
    half_angle = l_m / (2 * radius_of_curvature_m)
    chord = 2 * radius_of_curvature_m * sin(half_angle)
    return l_m / chord


def curvature_shifted_resonant_frequency_hz(
    f_flat_hz: float, l_m: float, radius_of_curvature_m: float
) -> float:
    """Estimated resonant frequency of a nominally-flat patch design conformed to radius R.

        f_r_curved = f_r_flat * curvature_length_correction_factor(L, R)

    f_flat_hz is the resonant frequency of the nominally-flat reference
    design (e.g. from patch_resonant_frequency_hz), L is the patch's
    physical resonant length (m), and radius_of_curvature_m is the host
    surface's radius of curvature (m). See the module notes above (under
    "Curvature-induced resonant-frequency shift") for the model's
    derivation and its explicit approximation/validity caveats -- this is
    a first-order estimate for first-pass sizing, not a substitute for
    simulation or measurement.
    """
    if f_flat_hz <= 0:
        raise ValueError("Flat-design resonant frequency f_flat_hz must be positive.")
    factor = curvature_length_correction_factor(l_m, radius_of_curvature_m)
    return f_flat_hz * factor


# --- Periodic/coded-surface curvature validity box (S <= 2*theta_max*R) ---
#
# A DIFFERENT curvature question than the patch model above: not "how much
# does the resonant frequency shift", but "does a Tier B coded/periodic
# surface's element still behave the way it was characterised, once the
# host bends it". docs/curvature-effects-on-em-surfaces.md section 4.2
# derives the rule from Khan et al.'s measured central-angle/element-
# stability relation: on a cylinder of radius R, a cell an arc distance s
# from the crown sees a local incidence angle theta(s) = s/R (section 0(i)).
# An element is only characterised (CONTEXT.md's Validity box) up to some
# angular-stability limit theta_max before its reflection response leaves
# the tolerance the design actually needs -- so the usable aperture arc
# length is bounded by
#
#     S <= 2 * theta_max * R
#
# (the special case S = 2*45degrees*R is Khan et al.'s own worked result).
# Exceeding it is exactly the validity-box violation issue #322/ADR-0021/
# ADR-0025 mean by a family's OWN characterised limits excluding it -- a
# fact about the requirement's stated host curvature and the chosen
# family's own characterised element, never about configured shop
# equipment.


def curvature_exceeds_validity_box(
    arc_length_m: float, host_radius_m: float, theta_max_deg: float
) -> bool:
    """True if a periodic/coded surface's stated host curvature puts its
    outermost cells beyond the characterised element's angular-stability
    limit -- i.e. `arc_length_m > 2 * theta_max * host_radius_m` (module
    notes above, "Periodic/coded-surface curvature validity box"; docs/
    curvature-effects-on-em-surfaces.md section 4.2).

    `arc_length_m` (S) is the requirement's own stated usable aperture arc
    length along the bend; `host_radius_m` (R) is the host's stated radius
    of curvature; `theta_max_deg` is the chosen family/element's OWN
    characterised angular-stability limit (never a shop-equipment figure).
    Both S and R must be positive, and theta_max_deg must be in (0, 90]
    degrees (no published element stays angle-stable at or past grazing
    incidence) -- raises ValueError otherwise, the geometry is undefined.
    """
    if arc_length_m <= 0:
        raise ValueError("arc_length_m must be positive.")
    if host_radius_m <= 0:
        raise ValueError("host_radius_m must be positive.")
    if not 0 < theta_max_deg <= 90:
        raise ValueError("theta_max_deg must be in (0, 90] degrees.")
    return arc_length_m > 2 * radians(theta_max_deg) * host_radius_m


# --- Aperture antenna gain ---


def aperture_gain(area_m2: float, freq_hz: float, aperture_efficiency: float = 0.55) -> float:
    """Estimated linear (dimensionless) gain of an aperture antenna.

    Standard aperture-antenna gain formula (Balanis, "Antenna Theory:
    Analysis and Design"):

        G = 4*pi*A_eff / lambda^2 * eta_ap

    where A_eff is the antenna's physical aperture area (m^2), lambda is
    the free-space wavelength at freq_hz (computed via this module's own
    wavelength() function, per this project's convention of composing
    prior deterministic functions rather than recomputing them), and
    eta_ap is the aperture efficiency -- the fraction of the physical
    aperture that radiates as if uniformly illuminated (illumination
    taper, spillover, and phase error all reduce it below 1.0).

    aperture_efficiency defaults to 0.55, a commonly cited "typical"
    aperture efficiency for practical reflector/horn/array apertures
    (Balanis; antenna-engineering references commonly cite a broad
    0.5-0.6 "typical" range). This default is a nominal planning value,
    not a measured or simulated figure for any specific design -- pass an
    explicit value once one is known (datasheet, simulation, or
    measurement).

    Returns linear gain (dimensionless, referenced to an isotropic
    radiator); use linear_to_db() from rf_tools.link_noise_budget to
    convert to dBi.
    """
    if area_m2 <= 0:
        raise ValueError("Aperture area must be positive.")
    if not 0 < aperture_efficiency <= 1:
        raise ValueError("Aperture efficiency must be in (0, 1].")
    lambda_m = wavelength(freq_hz)
    return 4 * np.pi * area_m2 / lambda_m**2 * aperture_efficiency
