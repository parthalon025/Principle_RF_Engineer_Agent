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

Deliberately *not* here: physical realization. Turning a ladder into microstrip
stub lengths, coupled-line geometry or a specific vendor's 0402 part is a
separate problem with its own approximations -- see `geometry/` and the
simulator adapters. This module stops at ideal lumped elements, which is where
the closed-form arithmetic stops being exact.

Provenance: every value returned here is `CALCULATED` -- deterministic
arithmetic on the caller's inputs, no measurement and no model fitting. The
mapping lives in `designs/provenance.py`, keyed by tool name, never set here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

__all__ = [
    "FilterElement",
    "FilterNetwork",
    "butterworth_g_values",
    "chebyshev_g_values",
    "synthesize_filter",
]

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
    grows with ripple. An even-order 3 dB design lands about 5.8x the source
    impedance, which usually means picking an odd order instead or accepting an
    impedance transformation.
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
    g.extend(
        2.0 * math.sin((2 * k - 1) * math.pi / (2 * order))
        for k in range(1, order + 1)
    )
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


def _highpass_element(
    position: Position, g: float, r0: float, wc: float
) -> FilterElement:
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
        raise ValueError(
            f"Unknown response {response!r}; expected one of {_RESPONSES}."
        )
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
                f"center_hz/bandwidth_hz do not apply to a {band} filter; "
                "use cutoff_hz."
            )
        wc = 2 * math.pi * cutoff_hz
        build = _lowpass_element if band == "lowpass" else _highpass_element
        scale_args: tuple[float, ...] = (impedance_ohm, wc)
    else:
        if center_hz is None or bandwidth_hz is None:
            raise ValueError(
                f"center_hz and bandwidth_hz are both required for a {band} filter."
            )
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
                f"cutoff_hz does not apply to a {band} filter; use center_hz "
                "and bandwidth_hz."
            )
        w0 = 2 * math.pi * center_hz
        delta = bandwidth_hz / center_hz
        build = _bandpass_element if band == "bandpass" else _bandstop_element
        scale_args = (impedance_ohm, w0, delta)

    positions: list[Position] = [
        ("shunt" if (i % 2 == 0) == (first_element == "shunt") else "series")
        for i in range(order)
    ]
    elements = tuple(
        build(position, g_k, *scale_args)
        for position, g_k in zip(positions, g[1:-1], strict=True)
    )

    return FilterNetwork(
        response=response,
        band=band,
        order=order,
        source_impedance_ohm=impedance_ohm,
        load_impedance_ohm=impedance_ohm * g[-1],
        cutoff_hz=cutoff_hz,
        center_hz=center_hz,
        bandwidth_hz=bandwidth_hz,
        ripple_db=ripple_db,
        g_values=g,
        elements=elements,
    )
