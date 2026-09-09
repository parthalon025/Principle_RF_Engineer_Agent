"""Closed-form filter-prototype synthesis (issue #143).

Turns a filter *specification* -- response shape, order, ripple, band edges,
system impedance -- into an actual ladder of inductor and capacitor values.

In plain terms: a filter is a circuit that passes some frequencies and blocks
others. There is a standard recipe, worked out in the 1950s and tabulated in
every microwave textbook since, that gets you from "3rd order, 0.5 dB ripple,
cut off at 1 GHz, 50 ohm system" to a real list of components. This module is
that recipe, and nothing more.

Three steps, mirroring how the textbooks lay it out:

1. **Prototype g-values.** A normalized, dimensionless description of the
   filter, computed for a 1 ohm source and a 1 rad/s cut-off. These depend
   only on the response shape (`butterworth_g_values`, `chebyshev_g_values`)
   and are what the published tables tabulate.
2. **Frequency transformation.** Map the low-pass prototype onto the band you
   actually want -- high-pass, band-pass, band-stop.
3. **Impedance and frequency scaling.** Scale to the real system impedance and
   the real band edges, producing henries and farads.

Sourced against Pozar, "Microwave Engineering" 4th ed., sections 8.3-8.4 and
Tables 8.3/8.4/8.6. `tests/test_filter_synthesis.py` checks the g-values
against those published tables rather than against this implementation.

A fourth step exists for one case (issue #286):
`realize_lowpass_stepped_impedance_microstrip` turns a *lowpass* ladder's
ideal L/C values into a physical microstrip layout, using the classic
stepped-impedance ("Hi-Z, Lo-Z") approximation (Pozar sec. 8.6): a short,
narrow high-impedance line stands in for each series inductor, a short, wide
low-impedance line for each shunt capacitor. Highpass/bandpass/bandstop
ladders are still not realized -- their branches are single capacitors
(highpass) or two-element resonators (bandpass/bandstop), and the
stepped-impedance method has no equivalent short-line approximation for
either; turning a ladder into coupled-line geometry, resonator stubs or a
specific vendor's 0402 part remains future scope, tracked the same way this
module's own top-of-file note already tracked physical realization in
general -- see ADR-0031 for why this path was chosen over driving a
simulator or the Qucs-S wizard.

Provenance: every value returned here is `CALCULATED` -- deterministic
arithmetic on the caller's inputs, no measurement and no model fitting. This
module returns plain numbers and carries no provenance field itself; the
`synthesize_filter_prototype`/`realize_lowpass_stepped_impedance_microstrip_filter`
tool wrappers tag the result `CALCULATED` inline, following
`calculate_l_network_match`'s precedent for a synthesis tool. It is
deliberately not in `designs/provenance.py`'s table, which maps only those
tools that write an `engineering_results` row.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from rf_tools.calculations import (
    microstrip_effective_permittivity,
    microstrip_synthesize_width_m,
)

__all__ = [
    "FilterElement",
    "FilterNetwork",
    "MicrostripLineSection",
    "butterworth_g_values",
    "chebyshev_g_values",
    "synthesize_filter",
    "realize_lowpass_stepped_impedance_microstrip",
]

_SPEED_OF_LIGHT_M_S = 299_792_458.0

Response = Literal["butterworth", "chebyshev"]
Band = Literal["lowpass", "highpass", "bandpass", "bandstop"]
Position = Literal["series", "shunt"]
Topology = Literal["L", "C", "LC_SERIES", "LC_PARALLEL"]

_RESPONSES = ("butterworth", "chebyshev")
_BANDS = ("lowpass", "highpass", "bandpass", "bandstop")

# Chebyshev's ripple constant: beta = ln(coth(L_Ar / (40/ln 10))). The textbooks
# print the denominator rounded to 17.37; it is exact as 40/ln(10).
_RIPPLE_CONSTANT = 40.0 / math.log(10.0)


@dataclass(frozen=True)
class FilterElement:
    """One branch of the ladder.

    `position` is how the branch sits in the circuit: `series` is in line with
    the signal, `shunt` bridges it to ground. `topology` is what the branch is
    made of -- a lone inductor (`L`) or capacitor (`C`) for low- and high-pass,
    or a two-component resonator for band-pass and band-stop: `LC_SERIES` (the
    two in line with each other) or `LC_PARALLEL` (side by side).

    Exactly the fields the topology uses are populated; the other is `None`.
    """

    position: Position
    topology: Topology
    inductance_h: float | None = None
    capacitance_f: float | None = None


@dataclass(frozen=True)
class FilterNetwork:
    """A synthesized ladder, source end first.

    `load_impedance_ohm` is worth reading rather than assuming: for an
    even-order Chebyshev it is *not* the source impedance. That is a real
    property of equal-ripple filters, not a rounding artefact -- an even-order
    equal-ripple prototype ends on a deliberate mismatch, and the mismatch
    grows with ripple. That usually means picking an odd order instead, or
    accepting an impedance transformation.

    Which direction the mismatch goes depends on how the ladder ends, because
    `g_{N+1}` is not always a resistance. In the standard prototype it is a
    load *resistance* when the last element is a shunt capacitor, and a load
    *conductance* when the last element is a series inductor (Pozar, fig.
    8.25). So a 3 dB even-order design lands at about 5.8x the source
    impedance one way round and about 0.17x it the other -- reading
    `g_{N+1}` as a resistance in both cases gets one of them badly wrong,
    and the resulting filter does not meet its own ripple spec.
    """

    response: Response
    band: Band
    order: int
    source_impedance_ohm: float
    load_impedance_ohm: float
    cutoff_hz: float | None
    center_hz: float | None
    bandwidth_hz: float | None
    ripple_db: float | None
    g_values: tuple[float, ...]
    elements: tuple[FilterElement, ...]

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable form, for crossing an agent/MCP tool boundary.

        Lives here rather than in each tool wrapper so the two surfaces cannot
        drift into reporting different fields for the same network.
        """
        return {
            "response": self.response,
            "band": self.band,
            "order": self.order,
            "source_impedance_ohm": self.source_impedance_ohm,
            "load_impedance_ohm": self.load_impedance_ohm,
            "ripple_db": self.ripple_db,
            "g_values": list(self.g_values),
            "elements": [
                {
                    "position": e.position,
                    "topology": e.topology,
                    "inductance_h": e.inductance_h,
                    "capacitance_f": e.capacitance_f,
                }
                for e in self.elements
            ],
        }


def _validate_order(order: int) -> None:
    if not isinstance(order, int) or isinstance(order, bool):
        raise ValueError("Filter order must be an integer.")
    if order < 1:
        raise ValueError("Filter order must be >= 1.")


def butterworth_g_values(order: int) -> tuple[float, ...]:
    """Maximally-flat prototype g-values, `g0` through `g_{n+1}`.

    `g_k = 2 sin[(2k-1)pi / 2n]`, with `g0 = g_{n+1} = 1` (Pozar eq. 8.51).
    "Maximally flat" means the pass-band has no ripple at all: the response is
    as flat as it can mathematically be at DC, trading a softer roll-off for
    that flatness.
    """
    _validate_order(order)
    g = [1.0]
    g.extend(2.0 * math.sin((2 * k - 1) * math.pi / (2 * order)) for k in range(1, order + 1))
    g.append(1.0)
    return tuple(g)


def chebyshev_g_values(order: int, ripple_db: float) -> tuple[float, ...]:
    """Equal-ripple prototype g-values, `g0` through `g_{n+1}`.

    Pozar eqs. 8.52-8.53. "Equal ripple" means the pass-band is allowed to
    wobble up and down by a fixed amount (`ripple_db`) rather than being flat;
    accepting that wobble buys a noticeably sharper cut-off for the same
    component count.

    `g_{n+1}` is 1 for odd orders and `coth^2(beta/4)` for even ones -- see
    `FilterNetwork.load_impedance_ohm` for why that matters.
    """
    _validate_order(order)
    if ripple_db <= 0:
        raise ValueError("Chebyshev ripple_db must be positive.")

    beta = math.log(1.0 / math.tanh(ripple_db / _RIPPLE_CONSTANT))
    gamma = math.sinh(beta / (2 * order))

    a = [math.sin((2 * k - 1) * math.pi / (2 * order)) for k in range(1, order + 1)]
    b = [gamma**2 + math.sin(k * math.pi / order) ** 2 for k in range(1, order + 1)]

    g = [1.0, 2.0 * a[0] / gamma]
    for k in range(2, order + 1):
        g.append(4.0 * a[k - 2] * a[k - 1] / (b[k - 2] * g[k - 1]))

    if order % 2:
        g.append(1.0)
    else:
        g.append((1.0 / math.tanh(beta / 4.0)) ** 2)
    return tuple(g)


def _prototype_g_values(
    response: Response, order: int, ripple_db: float | None
) -> tuple[float, ...]:
    if response == "butterworth":
        if ripple_db is not None:
            raise ValueError(
                "ripple_db does not apply to a butterworth (maximally flat) "
                "response, which has no pass-band ripple by definition. Use "
                "response='chebyshev' to trade ripple for a sharper cut-off."
            )
        return butterworth_g_values(order)
    if ripple_db is None:
        raise ValueError("ripple_db is required for a chebyshev response.")
    return chebyshev_g_values(order, ripple_db)


def _lowpass_element(position: Position, g: float, r0: float, wc: float) -> FilterElement:
    if position == "series":
        return FilterElement("series", "L", inductance_h=g * r0 / wc)
    return FilterElement("shunt", "C", capacitance_f=g / (r0 * wc))


def _highpass_element(position: Position, g: float, r0: float, wc: float) -> FilterElement:
    """High-pass swaps each element for its opposite and inverts g.

    A series inductor becomes a series capacitor, a shunt capacitor becomes a
    shunt inductor (Pozar eq. 8.55).
    """
    if position == "series":
        return FilterElement("series", "C", capacitance_f=1.0 / (r0 * wc * g))
    return FilterElement("shunt", "L", inductance_h=r0 / (wc * g))


def _bandpass_element(
    position: Position, g: float, r0: float, w0: float, delta: float
) -> FilterElement:
    """Each single element becomes a two-component resonator tuned to `w0`."""
    if position == "series":
        return FilterElement(
            "series",
            "LC_SERIES",
            inductance_h=g * r0 / (delta * w0),
            capacitance_f=delta / (w0 * g * r0),
        )
    return FilterElement(
        "shunt",
        "LC_PARALLEL",
        inductance_h=delta * r0 / (w0 * g),
        capacitance_f=g / (delta * w0 * r0),
    )


def _bandstop_element(
    position: Position, g: float, r0: float, w0: float, delta: float
) -> FilterElement:
    """Band-stop is band-pass with each resonator's topology inverted."""
    if position == "series":
        return FilterElement(
            "series",
            "LC_PARALLEL",
            inductance_h=g * r0 * delta / w0,
            capacitance_f=1.0 / (w0 * delta * g * r0),
        )
    return FilterElement(
        "shunt",
        "LC_SERIES",
        inductance_h=r0 / (w0 * delta * g),
        capacitance_f=delta * g / (w0 * r0),
    )


def _load_impedance(r0: float, g_last: float, last_position: Position) -> float:
    """Denormalize `g_{N+1}` into a real load impedance.

    `g_{N+1}` is a load *resistance* when the ladder ends in a shunt element
    and a load *conductance* when it ends in a series element (Pozar, fig.
    8.25) -- so it is divided in one case and multiplied in the other.
    Treating it as a resistance in both directions silently produces a filter
    that misses its own ripple specification: an order-2, 3 dB Chebyshev
    terminated at 290 ohms instead of 8.6 ohms runs 3-12 dB of passband loss
    where the spec says 0-3 dB.
    """
    return r0 * g_last if last_position == "shunt" else r0 / g_last


def synthesize_filter(
    *,
    response: Response,
    band: Band,
    order: int,
    impedance_ohm: float = 50.0,
    ripple_db: float | None = None,
    cutoff_hz: float | None = None,
    center_hz: float | None = None,
    bandwidth_hz: float | None = None,
    first_element: Position = "shunt",
) -> FilterNetwork:
    """Synthesize a lumped-element ladder filter.

    `cutoff_hz` is required for `lowpass`/`highpass`; `center_hz` and
    `bandwidth_hz` for `bandpass`/`bandstop`. `ripple_db` is required for
    `chebyshev` and rejected for `butterworth`.

    For `bandpass`/`bandstop`, `center_hz` is the *geometric* centre of the
    band -- `sqrt(f_lower * f_upper)`, which is what the standard transformation
    assumes -- so the band edges are not `center_hz +/- bandwidth_hz/2`. The
    width between the edges is exactly `bandwidth_hz`, but they sit slightly
    asymmetrically about `center_hz`, increasingly so as the band widens. For a
    10% bandwidth the edges land at about 0.9512 and 1.0512 times `center_hz`,
    where an arithmetic reading would predict 0.95 and 1.05.

    `first_element` picks which of the two equivalent ladders to build: the
    same g-values realize either a shunt-first (capacitor-input) or series-first
    (inductor-input) network. They are electrically equivalent; pick whichever
    yields component values you can actually buy.

    Raises `ValueError` on any inconsistent specification rather than guessing
    -- a filter silently synthesized against the wrong band edges looks
    perfectly plausible in its output.
    """
    if response not in _RESPONSES:
        raise ValueError(f"Unknown response {response!r}; expected one of {_RESPONSES}.")
    if band not in _BANDS:
        raise ValueError(f"Unknown band {band!r}; expected one of {_BANDS}.")
    if first_element not in ("series", "shunt"):
        raise ValueError("first_element must be 'series' or 'shunt'.")
    if impedance_ohm <= 0:
        raise ValueError("impedance_ohm must be positive.")

    g = _prototype_g_values(response, order, ripple_db)

    if band in ("lowpass", "highpass"):
        if cutoff_hz is None:
            raise ValueError(f"cutoff_hz is required for a {band} filter.")
        if cutoff_hz <= 0:
            raise ValueError("cutoff_hz must be positive.")
        if center_hz is not None or bandwidth_hz is not None:
            raise ValueError(
                f"center_hz/bandwidth_hz do not apply to a {band} filter; use cutoff_hz."
            )
        wc = 2 * math.pi * cutoff_hz
        build = _lowpass_element if band == "lowpass" else _highpass_element
        scale_args: tuple[float, ...] = (impedance_ohm, wc)
    else:
        if center_hz is None or bandwidth_hz is None:
            raise ValueError(f"center_hz and bandwidth_hz are both required for a {band} filter.")
        if center_hz <= 0:
            raise ValueError("center_hz must be positive.")
        if bandwidth_hz <= 0:
            raise ValueError("bandwidth_hz must be positive.")
        if bandwidth_hz >= center_hz:
            raise ValueError(
                "bandwidth_hz must be narrower than center_hz; a fractional "
                "bandwidth of 1 or more puts the lower band edge at or below "
                "DC, where this transformation does not hold."
            )
        if cutoff_hz is not None:
            raise ValueError(
                f"cutoff_hz does not apply to a {band} filter; use center_hz and bandwidth_hz."
            )
        w0 = 2 * math.pi * center_hz
        delta = bandwidth_hz / center_hz
        build = _bandpass_element if band == "bandpass" else _bandstop_element
        scale_args = (impedance_ohm, w0, delta)

    positions: list[Position] = [
        ("shunt" if (i % 2 == 0) == (first_element == "shunt") else "series") for i in range(order)
    ]
    elements = tuple(
        build(position, g_k, *scale_args) for position, g_k in zip(positions, g[1:-1], strict=True)
    )

    return FilterNetwork(
        response=response,
        band=band,
        order=order,
        source_impedance_ohm=impedance_ohm,
        load_impedance_ohm=_load_impedance(impedance_ohm, g[-1], positions[-1]),
        cutoff_hz=cutoff_hz,
        center_hz=center_hz,
        bandwidth_hz=bandwidth_hz,
        ripple_db=ripple_db,
        g_values=g,
        elements=elements,
    )


@dataclass(frozen=True)
class MicrostripLineSection:
    """One physical microstrip line realizing one branch of a lowpass ladder.

    `topology` is always `"L"` or `"C"` (the two topologies a lowpass ladder
    actually contains) -- it names which `FilterElement` this section
    approximates, not the line's own shape, and lines up with
    `characteristic_impedance_ohm`: a `"L"` section always sits at the
    ladder's `z_high_ohm` and a `"C"` section always at its `z_low_ohm`
    (see `realize_lowpass_stepped_impedance_microstrip`).
    """

    position: Position
    topology: Topology
    characteristic_impedance_ohm: float
    width_m: float
    length_m: float
    electrical_length_rad: float
    effective_permittivity: float

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable form, for crossing an agent/MCP tool boundary --
        mirrors `FilterNetwork.to_dict`'s reason for existing."""
        return {
            "position": self.position,
            "topology": self.topology,
            "characteristic_impedance_ohm": self.characteristic_impedance_ohm,
            "width_m": self.width_m,
            "length_m": self.length_m,
            "electrical_length_rad": self.electrical_length_rad,
            "effective_permittivity": self.effective_permittivity,
        }


def realize_lowpass_stepped_impedance_microstrip(
    network: FilterNetwork,
    *,
    eps_r: float,
    h_m: float,
    z_high_ohm: float = 120.0,
    z_low_ohm: float = 20.0,
) -> tuple[MicrostripLineSection, ...]:
    """Realize a lowpass ladder as stepped-impedance ("Hi-Z, Lo-Z") microstrip
    lines (Pozar, "Microwave Engineering" 4th ed., sec. 8.6; issue #286).

    A short length of transmission line approximates a series inductor when
    its characteristic impedance is high, and a shunt capacitor when it is
    low -- comparing the ABCD parameters of a short line (`cos(bl)~1`,
    `sin(bl)~bl`) against those of an ideal series-L or shunt-C branch gives:

        series L branch: bl = wc * L / z_high_ohm   (a narrow, HIGH-Z line)
        shunt  C branch: bl = wc * C * z_low_ohm     (a wide, LOW-Z line)

    where `wc` is the network's own `cutoff_hz` in rad/s and `L`/`C` are the
    branch's already-denormalized `inductance_h`/`capacitance_f`. This is
    the same pair independently confirmed against two published worked
    examples of this exact procedure while implementing this function (see
    `tests/test_filter_synthesis.py`); one of them reproduces Pozar's own
    5th-order Butterworth example almost exactly (`g` = 0.6180, 1.6180,
    2.0000, 1.6180, 0.6180 with `z_high_ohm=100`, `z_low_ohm=20` gives
    `bl` = 0.2472, 0.809, 0.8, 0.809, 0.2472 rad).

    Each section's width comes from `microstrip_synthesize_width_m` at that
    section's impedance (`z_high_ohm` for `"L"`, `z_low_ohm` for `"C"`) on a
    substrate of relative permittivity `eps_r` and thickness `h_m`; its
    physical length is `bl` divided by that width's own guided-wave number
    `beta = wc * sqrt(eps_eff) / c` -- so, algebraically, `wc` cancels and a
    section's length depends only on its branch value, impedance and
    `eps_eff`, not on the cutoff frequency directly. `z_high_ohm` defaults to
    120 ohm and `z_low_ohm` to 20 ohm, Pozar's own example values and a
    commonly repeated starting point in the literature reviewed for this
    ticket; a real board's manufacturable trace-width range should override
    both.

    Two things this approximation does NOT capture, by construction: it
    assumes each `bl` is small enough that `sin(bl)~bl` stays a good
    approximation (a rule of thumb is `bl < pi/4`; accuracy degrades
    gracefully, not catastrophically, as sections get electrically longer,
    so this is not gated here -- matching this project's own precedent for
    not gating a smoothly-degrading approximation at an arbitrary threshold,
    see `capacitive_grid_sheet_capacitance_f`'s d/p=0.3 note in
    `rf_tools/calculations.py`), and it uses each width's quasi-static
    `eps_eff` evaluated at the cutoff frequency only -- no dispersion, no
    coupling between adjacent sections, and no discontinuity (step)
    reactance at the width transitions themselves. Cross-check any result
    that matters against a full-wave simulator or measurement before
    fabrication, the same caveat `synthesize_filter_prototype` already
    carries for the ideal lumped-element ladder this extends.

    ONLY the lowpass band is supported (raises `ValueError` otherwise): a
    highpass ladder's branches are single capacitors/inductors of the
    *opposite* topology this method has no line-length formula for, and a
    bandpass/bandstop ladder's branches are two-element resonators
    (`LC_SERIES`/`LC_PARALLEL`) with no single-line equivalent at all. See
    this module's own top docstring and issue #286 for that scope choice.
    """
    if network.band != "lowpass":
        raise ValueError(
            f"realize_lowpass_stepped_impedance_microstrip only supports "
            f"band='lowpass' networks; got {network.band!r}. The "
            f"stepped-impedance Hi-Z/Lo-Z method approximates a series "
            f"inductor as a narrow high-impedance line and a shunt "
            f"capacitor as a wide low-impedance line -- a highpass, "
            f"bandpass or bandstop ladder's branches (series C/shunt L, or "
            f"two-element LC resonators) have no equivalent short-line "
            f"realization under this method (issue #286)."
        )
    if network.cutoff_hz is None:
        raise ValueError(
            "network.cutoff_hz is required (a lowpass FilterNetwork from "
            "synthesize_filter always sets it; this network did not)."
        )
    if eps_r <= 1:
        raise ValueError(f"eps_r must be > 1; got {eps_r!r}.")
    if h_m <= 0:
        raise ValueError("h_m must be positive.")
    if z_high_ohm <= 0 or z_low_ohm <= 0:
        raise ValueError("z_high_ohm and z_low_ohm must both be positive.")
    if z_high_ohm <= z_low_ohm:
        raise ValueError(
            f"z_high_ohm ({z_high_ohm!r}) must exceed z_low_ohm ({z_low_ohm!r}) "
            f"-- the method needs a genuinely high line and a genuinely low "
            f"one; Pozar recommends keeping the ratio as large as the target "
            f"board's manufacturable trace widths allow."
        )

    omega_c = 2 * math.pi * network.cutoff_hz
    sections = []
    for element in network.elements:
        if element.topology == "L":
            z0 = z_high_ohm
            assert element.inductance_h is not None  # lowpass "L" always sets this
            beta_l = omega_c * element.inductance_h / z0
        elif element.topology == "C":
            z0 = z_low_ohm
            assert element.capacitance_f is not None  # lowpass "C" always sets this
            beta_l = omega_c * element.capacitance_f * z0
        else:
            raise ValueError(
                f"realize_lowpass_stepped_impedance_microstrip has no microstrip "
                f"realization for a {element.topology!r} branch (issue #286); "
                f"only the 'L'/'C' branches a lowpass ladder produces are supported."
            )
        width_m = microstrip_synthesize_width_m(z0, eps_r, h_m)
        eps_eff = microstrip_effective_permittivity(eps_r, width_m, h_m)
        beta = omega_c * eps_eff**0.5 / _SPEED_OF_LIGHT_M_S
        sections.append(
            MicrostripLineSection(
                position=element.position,
                topology=element.topology,
                characteristic_impedance_ohm=z0,
                width_m=width_m,
                length_m=beta_l / beta,
                electrical_length_rad=beta_l,
                effective_permittivity=eps_eff,
            )
        )
    return tuple(sections)
