"""Metamaterial unit-cell effective-medium parameters (Maxwell-Garnett), split
out of this package's former single calculations module, issue #523/#500."""


def maxwell_garnett_effective_permeability(
    fill_fraction: float, mu_r: float, mu_host: float = 1.0
) -> float:
    """Effective relative permeability of a dilute array of magnetic elements.

    Standard Maxwell-Garnett effective-medium mixing formula (Maxwell
    Garnett, 1904; the standard homogenization-theory starting point for
    predicting a metamaterial unit cell's bulk effective magnetic property
    from its element geometry -- see CONTEXT.md's "Metamaterial unit cell"
    entry: elongated, passive-magnetic-property elements at a given fill
    fraction in a host medium), applied here to permeability (the form
    matching this project's actual metamaterial elements) rather than the
    more commonly quoted permittivity form -- both are the same mixing
    rule with mu <-> eps swapped:

        (mu_eff - mu_host) / (mu_eff + 2*mu_host)
            = f * (mu_r - mu_host) / (mu_r + 2*mu_host)

    Solved for mu_eff (closed form):

        beta   = (mu_r - mu_host) / (mu_r + 2*mu_host)
        mu_eff = mu_host * (1 + 2*f*beta) / (1 - f*beta)

    where f is the elements' fill fraction (volume filling factor, 0-1) in
    the host medium, mu_r is the element material's own relative
    permeability, and mu_host is the host medium's relative permeability
    (defaults to 1.0 for free space / a typical non-magnetic host).

    This is a DILUTE-LIMIT approximation: it assumes the elements are
    sparse enough that each sees only the host medium's applied field, not
    its neighbors' scattered fields. It is standard and well cited for
    small fill fractions, but is known to lose accuracy as f grows --
    element-element electromagnetic coupling becomes significant and this
    Clausius-Mossotti-style mixing rule under/overestimates mu_eff. Treat
    f >~ 0.3 as outside this formula's comfortable validity range (a rough,
    commonly cited homogenization-theory rule of thumb, not a hard physical
    cutoff enforced here); do not present this function's output as an
    exact result at high fill fraction without validating against
    simulation or measurement.
    """
    if not 0 <= fill_fraction < 1:
        raise ValueError("Fill fraction must be in [0, 1).")
    if mu_r <= 0:
        raise ValueError("Element relative permeability mu_r must be positive.")
    if mu_host <= 0:
        raise ValueError("Host relative permeability mu_host must be positive.")
    beta = (mu_r - mu_host) / (mu_r + 2 * mu_host)
    denom = 1 - fill_fraction * beta
    if denom == 0:
        raise ValueError(
            "Maxwell-Garnett mixing formula is undefined for this "
            "fill_fraction/mu_r/mu_host combination (1 - f*beta = 0)."
        )
    return mu_host * (1 + 2 * fill_fraction * beta) / denom
