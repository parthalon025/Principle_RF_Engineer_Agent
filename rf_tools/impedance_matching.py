def quarter_wave_transformer_impedance(z_source: float, z_load: float) -> float:
    """Characteristic impedance of a quarter-wave (Q-wave) transformer.

    Matches two *real* (resistive) impedances at the design frequency
    where the transformer section is electrically one quarter-wavelength
    long:

        Z_transformer = sqrt(Z_source * Z_load)

    This is the standard, well-defined case (Pozar, "Microwave
    Engineering"); it is not valid for complex/reactive impedances -- use
    l_network_match for a complex load instead.
    """
    if z_source <= 0:
        raise ValueError("Source impedance must be positive.")
    if z_load <= 0:
        raise ValueError("Load impedance must be positive.")
    return (z_source * z_load) ** 0.5


def l_network_match(z_source: float, z_load: complex) -> list[tuple[float, float]]:
    """Synthesize a lossless L-network matching z_load to a real z_source.

    Standard two-solution L-network synthesis (Pozar, "Microwave
    Engineering", sec. 5.1). Returns a list of one or two (X, B) pairs,
    where X is a series reactance in ohms (positive = inductive,
    negative = capacitive) and B is a shunt susceptance in siemens
    (positive = capacitive, negative = inductive). Both pairs are valid,
    independent solutions to the same matching problem (e.g. one may be
    realizable with smaller/cheaper components at a given frequency); a
    single solution is returned only when the two roots coincide exactly
    (e.g. a purely resistive load already equal to z_source).

    Topology is chosen from Re(z_load) relative to z_source, per Pozar:

    - Re(z_load) >= z_source: the shunt element (B) connects directly
      across the load, with the series element (X) between that node and
      the source -- i.e. build the network load-to-source as
      1/(1/z_load + jB) then + jX, and that total should equal z_source.
    - Re(z_load) < z_source: the series element (X) connects directly to
      the load, with the shunt element (B) between that node and the
      source -- i.e. build the network load-to-source as
      1/(1/(z_load + jX) + jB), and that total should equal z_source.

    Raises ValueError if z_source or Re(z_load) is not positive (an L-network
    matching a purely reactive or active/negative-resistance load is a
    different problem, not covered here).
    """
    if z_source <= 0:
        raise ValueError("Source impedance must be positive.")
    zl = complex(z_load)
    rl, xl = zl.real, zl.imag
    if rl <= 0:
        raise ValueError("Load resistance (real part of z_load) must be positive.")

    solutions: list[tuple[float, float]] = []
    if rl >= z_source:
        denom = rl**2 + xl**2
        discriminant = rl**2 + xl**2 - z_source * rl
        sqrt_term = (rl / z_source) ** 0.5 * discriminant**0.5
        gl = rl / denom
        bl_prime = -xl / denom
        for b in {(xl + sqrt_term) / denom, (xl - sqrt_term) / denom}:
            x = (bl_prime + b) * z_source / gl
            solutions.append((float(x), float(b)))
    else:
        discriminant = rl * (z_source - rl)
        sqrt_term = discriminant**0.5
        for x in {-xl + sqrt_term, -xl - sqrt_term}:
            b = (xl + x) / (rl * z_source)
            solutions.append((float(x), float(b)))
    return solutions
