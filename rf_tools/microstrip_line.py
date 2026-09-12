import math

# --- Microstrip line: characteristic impedance and width synthesis (issue #286) ---
#
# Distinct from patch_effective_permittivity/patch_length_extension_m in
# rf_tools/calculations.py, on purpose: those restate this identical
# Hammerstad fringing-field fit inside Balanis's patch-ANTENNA presentation,
# which frames it for W/h > 1 (a resonant patch is normally much wider than
# the substrate is thick) and enforces that as a hard precondition. Pozar's
# general microstrip TRANSMISSION-LINE treatment ("Microwave Engineering"
# 4th ed., Table 3.2) states the same eps_eff formula with no such floor,
# and adds the characteristic-impedance analysis/synthesis pair below,
# which DOES split at W/h = 1 -- exactly the geometry
# rf_tools/filter_synthesis.py's stepped-impedance realization needs: its
# high-impedance ("Hi-Z") line sections come out narrow (W/h < 1, outside
# patch_effective_permittivity's own domain) and its low-impedance ("Lo-Z")
# sections come out wide (W/h > 1). Two functions computing the same
# fringing-field number for two different stated domains is deliberate
# here, the same way rf_tools/calculations.py already carries two published
# forms of Costa's thin-spacer correction side by side (COSTA_EQ10_FORMS)
# rather than picking one and hoping it generalizes.


def microstrip_effective_permittivity(eps_r: float, w_m: float, h_m: float) -> float:
    """Effective dielectric constant of a microstrip line, valid for any W/h
    (Pozar, "Microwave Engineering" 4th ed., Table 3.2):

        eps_eff = (eps_r+1)/2 + (eps_r-1)/2 * (1 + 12*h/W)^(-0.5)

    Same closed form as patch_effective_permittivity above -- restated here
    because Pozar's general line treatment carries no W/h > 1 floor, unlike
    Balanis's patch-antenna one (see the module note just above).
    """
    if eps_r <= 1:
        raise ValueError(f"eps_r must be > 1; got {eps_r!r}.")
    if h_m <= 0:
        raise ValueError("Substrate thickness h_m must be positive.")
    if w_m <= 0:
        raise ValueError("Line width w_m must be positive.")
    return (eps_r + 1) / 2 + (eps_r - 1) / 2 * (1 + 12 * h_m / w_m) ** -0.5


def microstrip_characteristic_impedance_ohm(eps_r: float, w_m: float, h_m: float) -> float:
    """Characteristic impedance of a microstrip line from its geometry (the
    analysis direction: width known, impedance wanted). Pozar, Table 3.2,
    split at W/h = 1:

        W/h <= 1:  Z0 = (60/sqrt(eps_eff)) * ln(8h/W + W/(4h))
        W/h >= 1:  Z0 = (120*pi/sqrt(eps_eff)) / (W/h + 1.393 + 0.667*ln(W/h + 1.444))

    eps_eff is microstrip_effective_permittivity(eps_r, w_m, h_m). This is
    the inverse direction of microstrip_synthesize_width_m, and exists
    mainly to check that pairing: running a synthesized width back through
    this function recovers the target Z0 to within Pozar's own stated
    accuracy for the pair (about 1%), which is the standard way this
    approximate design procedure is verified in the literature.
    """
    if eps_r <= 1:
        raise ValueError(f"eps_r must be > 1; got {eps_r!r}.")
    if w_m <= 0:
        raise ValueError("Line width w_m must be positive.")
    if h_m <= 0:
        raise ValueError("Substrate thickness h_m must be positive.")
    eps_eff = microstrip_effective_permittivity(eps_r, w_m, h_m)
    w_over_h = w_m / h_m
    if w_over_h <= 1:
        return (60.0 / eps_eff**0.5) * math.log(8.0 / w_over_h + w_over_h / 4.0)
    return (120.0 * math.pi / eps_eff**0.5) / (
        w_over_h + 1.393 + 0.667 * math.log(w_over_h + 1.444)
    )


def microstrip_synthesize_width_m(z0_ohm: float, eps_r: float, h_m: float) -> float:
    """Microstrip line width for a target characteristic impedance (the
    synthesis direction: impedance known, width wanted). Pozar, Table 3.2:

        A = Z0/60 * sqrt((eps_r+1)/2) + (eps_r-1)/(eps_r+1) * (0.23 + 0.11/eps_r)
        W/h = 8*e^A / (e^(2A) - 2)                                    -- narrow/high-Z0

        B = 377*pi / (2*Z0*sqrt(eps_r))
        W/h = (2/pi) * [B-1-ln(2B-1) + (eps_r-1)/(2*eps_r)*(ln(B-1)+0.39-0.61/eps_r)]
                                                                        -- wide/low-Z0

    The A-formula is only self-consistent where it predicts W/h <= 2 (a
    genuinely narrow, high-impedance line); computed for a lower target Z0
    it would predict W/h > 2, so the B-formula is used instead. This project
    verified the pair by hand against two independently published worked
    examples reproducing this exact procedure before relying on it here
    (see rf_tools/filter_synthesis.py's stepped-impedance realization and
    tests/test_microstrip_line.py).

    Returns the width in metres for a substrate of thickness h_m and
    relative permittivity eps_r.
    """
    if z0_ohm <= 0:
        raise ValueError("z0_ohm must be positive.")
    if eps_r <= 1:
        raise ValueError(f"eps_r must be > 1; got {eps_r!r}.")
    if h_m <= 0:
        raise ValueError("Substrate thickness h_m must be positive.")
    a = z0_ohm / 60.0 * ((eps_r + 1) / 2) ** 0.5 + (eps_r - 1) / (eps_r + 1) * (0.23 + 0.11 / eps_r)
    w_over_h = 8.0 * math.exp(a) / (math.exp(2 * a) - 2.0)
    if w_over_h > 2.0:
        b = 377.0 * math.pi / (2.0 * z0_ohm * eps_r**0.5)
        w_over_h = (2.0 / math.pi) * (
            b
            - 1.0
            - math.log(2 * b - 1)
            + (eps_r - 1) / (2 * eps_r) * (math.log(b - 1) + 0.39 - 0.61 / eps_r)
        )
    return w_over_h * h_m
