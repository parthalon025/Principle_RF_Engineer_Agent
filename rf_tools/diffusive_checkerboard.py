"""DIFFUSIVE aperture scoring + unit-cell materialization for a *plain 1:1
alternating* checkerboard (issue #550) -- the special case of a coding
metasurface where exactly two characterised tiles alternate by lattice
parity across the whole aperture, per patent US12089385B2's own Example 7
embodiment.

WHY THIS IS A SEPARATE MODULE, AND WHY IT IS SCOPED THIS NARROWLY.
`docs/example7-coding-metasurface-scoring-recipe.md` Step 3 gives a closed
form for the plain 1:1 case only -- it "assumes equal-area alternating
tiles" and explicitly does NOT apply to a general N x N, GA/PSO-searched
coding sequence (Cui, Qi, Wan, Zhao & Cheng 2014's own Eq. 3, whose
worked-example numbers in that paper's Table I are a DIFFERENT quantity
this module is not trying to reproduce -- see the test suite for why).
That general arrangement-search objective is deliberately out of scope
here; this module answers only "does a plain checkerboard of these two
already-characterised tiles meet the requirement", which is scoreable
today even though the Element/Coding-Alphabet library the design ultimately
needs is still empty (issue #550's own motivation: ship the tool that works
the moment two tiles exist in the alphabet).

THE SIGN CONVENTION -- worth stating explicitly because it is easy to get
backwards. `RCS_reduction_dB(f) = 20*log10(sin(delta(f)/2))` is NEGATIVE
when the checkerboard is working (bigger negative number = more of the
monostatic return cancelled) and rises toward 0 dB (no cancellation at all)
as the two tiles' phases drift toward being IN phase instead of 180 degrees
apart. This matches Cui et al.'s own Table I, where a BETTER arrangement
reports a MORE NEGATIVE dB figure (-12.08 for N=6, -23.58 for N=20 -- "better
RCS reduction... for larger N", their own words, expressed as a bigger
negative number), and it self-checks against `geometry.unit_cell.
phase_budget_deg`: `phase_budget_deg(10.0)` is 36.87 degrees, and plugging
that back in as `delta` here gives exactly -10.0 dB -- the two functions are
algebraic inverses of each other at the 10 dB point, which is the strongest
evidence available that both carry the sign right (see
tests/test_rf_tools_diffusive_checkerboard.py's round-trip test).

Because the raw score is negative-is-better, "worst-in-band" (the point a
customer's guarantee must hold at) is the value CLOSEST TO ZERO across the
band, i.e. the numeric MAXIMUM of the (non-positive) `RCS_reduction_dB`
curve -- not the minimum. `docs/example7-coding-metasurface-scoring-recipe.
md` section 1.2 writes the aggregation as "score = min over f of
RCS_reduction_dB(f)", copying ADR-0041's absorber-minimax phrasing verbatim
without correcting for the sign flip between "absorption" (a positive,
bigger-is-better quantity, where min IS the worst point) and this signed
quantity (where min is actually the BEST point). That document already
flags its own aggregation section as "recommended... not literature-proven
to the same evidentiary bar as ADR-0041" -- this module resolves the
ambiguity in the physically correct direction (worst = max of this signed
curve) rather than propagating a copy-paste sign error, and says so here so
a future reader comparing this code against that doc's prose is not left
thinking one of them is simply wrong without explanation.

PROVENANCE. The formulas here are the closed-form special case
docs/example7-coding-metasurface-scoring-recipe.md Step 2/3 derives from
docs/supercell-sizing-rule.md -- LITERATURE-SUPPORTED in the sense that
module's own docstring uses the term, though that recipe document is
itself new synthesis (its own words: "new synthesis for this write-up, not
an adopted formula") rather than a formula lifted unchanged from a single
paper. A score this module RETURNS carries the WEAKER of its two input
symbol entries' own provenance (`weaker_provenance` below) -- never a
blanket CALCULATED -- because the score is a function of two measured (or
simulated) tile responses, and is only as trustworthy as the less-certain
of the two.

NOT IN SCOPE (issue #550's own text): the general N x N arrangement search;
reconstructing Cui et al.'s Eq. 3 exactly; the Gustafsson & Sjoberg bound
itself (#465); printing/measuring tiles (#132); full-wave finite-panel
validation; any change to `designs/element_alphabet.py` (that module's
provenance handling is mid-transition per ADR-0053 and this module does not
assume its current or its future shape -- see `weaker_provenance`).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from designs.element_alphabet import lookup_symbol_entries, reduce_response_at_frequency
from geometry.unit_cell import boundary_fraction, generate_coded_unit_cell_array

# A plain 1:1 alternating checkerboard's own two-term coupling budget uses
# `boundary_fraction` at the smallest possible block, Nx=Ny=1 -- one cell
# per symbol, so every cell IS a boundary cell (boundary_fraction(1, 1) ==
# 1.0 by construction; see that function's own nx==1-or-ny==1 branch). This
# is not a simplification of the general Nx*Ny case, it is what "plain 1:1"
# means: there is no larger block to average a coupling error over.
_PLAIN_1_1_BLOCK = (1, 1)

# docs/requirement-derived-thresholds.md's rule -- "A convention is a
# default. It is never a threshold." -- applied here per issue #550's own
# Implementation Decisions: absent a customer-stated reduction figure,
# default to 10 dB (Haji-Ahmadi et al. 2017 and Cui et al. 2014 both report
# "at least 10 dB" as their field's own headline guarantee at the
# 180+/-37deg criterion), and always record that the gap was filled.
DEFAULT_RCS_REDUCTION_THRESHOLD_DB = 10.0

# docs/example7-coding-metasurface-scoring-recipe.md section 3 / designs/
# design_families.py's DIFFUSIVE NO_PHYSICAL_BOUND reason string: a
# checkerboard's two-tile supercell can only launch a propagating
# diffracted order (and so only earns the diffuse-scattering exemption from
# a Rozanov-style absorption bound) if its period D >= sqrt(2)*lambda --
# 42.4 mm at 10 GHz, 30.3 mm at 14 GHz for this project's own band.
_SQRT_2 = math.sqrt(2.0)


class InsufficientTilesError(ValueError):
    """Fewer than two distinct symbols in `symbol_entries` match the full
    `element_family`/band/incidence-angle/process key at every requested
    frequency point. A plain 1:1 checkerboard needs exactly two tiles; one
    or zero means nothing can be scored yet, and this says so loudly rather
    than silently picking a degenerate single-symbol "checkerboard"."""


def _require_positive_finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a real number, got {value!r}")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueError(f"{name} must be finite and > 0, got {value!r}")
    return numeric


def _require_nonnegative_finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a real number, got {value!r}")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError(f"{name} must be finite and >= 0, got {value!r}")
    return numeric


def weaker_provenance(provenance_a: str, provenance_b: str) -> str:
    """The weaker (lower-evidence) of two Element/Coding-Alphabet entries'
    own `provenance` values, per issue #550's own combination rule:
    MEASURED+MEASURED -> MEASURED, MEASURED+SIMULATED -> SIMULATED.

    Reads whichever string each entry actually carries -- it does NOT
    assume every entry is `knowledge.provenance.MEASURED` the way
    `designs/element_alphabet.py` currently hardcodes (that module's own
    docstring states this as an ADR-0027 invariant), and it does NOT
    re-derive provenance from whether a Process record is attached, the
    mechanism ADR-0053 uses internally to admit a `SIMULATED` entry with no
    Process record. Both of those are `designs.element_alphabet`'s own
    admission-time bookkeeping; this function only ever compares two
    already-resolved `provenance` strings by evidence rank, generically, so
    it keeps working unchanged whichever of the two admission routes
    produced either input entry.

    Raises `ValueError` for a provenance value outside the two this
    function currently ranks (`MEASURED`, `SIMULATED`) -- silently ranking
    an unrecognised value would risk understating or overstating the
    combined result's evidence tier.
    """
    rank = {"SIMULATED": 1, "MEASURED": 2}
    try:
        rank_a = rank[provenance_a]
        rank_b = rank[provenance_b]
    except KeyError as exc:
        raise ValueError(
            f"unrecognised provenance value {exc.args[0]!r}; expected one of {sorted(rank)}"
        ) from None
    return provenance_a if rank_a <= rank_b else provenance_b


def phase_error_deg(
    phase_a_deg: float,
    phase_b_deg: float,
    delta_phi_max_deg: float,
) -> float:
    """`delta(f) = |180 - (angle_a - angle_b)| + delta_phi_max*f(N)` --
    docs/example7-coding-metasurface-scoring-recipe.md Step 2: dispersion
    (how far the two tiles' own characterised phases have drifted from
    exactly 180 degrees apart at this frequency) plus coupling error (how
    much a real neighbour perturbs a cell from its Floquet-characterized
    value, `docs/supercell-sizing-rule.md` Sec 2's `delta_phi_max`, budgeted
    here at the plain-1:1 block via `boundary_fraction(1, 1) == 1.0`).

    `delta_phi_max_deg` is the alphabet-level coupling-error constant for
    this tile pair/process (the same quantity `geometry.unit_cell.
    block_size_from_sizing_rule` takes as its own `delta_phi_max_deg`
    argument) -- not a per-frequency measurement, a fixed characterisation
    number.
    """
    delta_phi_max_deg = _require_nonnegative_finite("delta_phi_max_deg", delta_phi_max_deg)
    dispersion_deg = abs(180.0 - (phase_a_deg - phase_b_deg))
    coupling_deg = delta_phi_max_deg * boundary_fraction(*_PLAIN_1_1_BLOCK)
    return dispersion_deg + coupling_deg


def rcs_reduction_db(delta_deg: float) -> float:
    """`RCS_reduction_dB(f) = 20*log10(sin(delta(f)/2))` --
    docs/example7-coding-metasurface-scoring-recipe.md Step 3, the plain
    1:1 alternating checkerboard's closed-form aperture-level reduction.

    See this module's own docstring for the sign convention: this is
    NEGATIVE when the checkerboard cancels well (delta near 0, the two
    tiles close to the ideal 180 degrees apart) and rises toward 0 dB (no
    cancellation) as delta grows toward 180 degrees (the tiles reflecting
    nearly in phase, like a plain PEC sheet).
    """
    sin_half = math.sin(math.radians(delta_deg) / 2.0)
    if sin_half <= 0.0:
        # delta_deg == 0 (mod 360) is the theoretical perfect-cancellation
        # limit -- sin(0) == 0, log10(0) is undefined. Report it as the
        # true limiting case rather than raising: an idealised closed-form
        # input can land exactly here even though no real measurement ever
        # will (a real pair of tiles always carries some finite delta).
        return -math.inf
    return 20.0 * math.log10(sin_half)


def diffracted_order_exists(supercell_period_m: float, wavelength_m: float) -> bool:
    """True if a checkerboard supercell of period `supercell_period_m` can
    launch a propagating diffracted order at `wavelength_m` -- the
    precondition `D >= sqrt(2)*lambda`
    (docs/example7-coding-metasurface-scoring-recipe.md Sec 3;
    designs/design_families.py's DIFFUSIVE `NO_PHYSICAL_BOUND` reason
    string cites the same 42.4 mm at 10 GHz / 30.3 mm at 14 GHz figures).

    This is a NEW check (issue #550: "does not exist nowhere in code
    today") and a different quantity from `geometry.unit_cell.
    _diffraction_sin_theta`, which answers a related but distinct question
    -- whether a sizing-rule BLOCK's dominant diffraction lobe clears the
    panel's own specular-lobe angle `theta_min`. This function only asks
    whether a propagating order exists AT ALL for the checkerboard's own
    two-tile supercell period, independent of any block size or panel.

    `supercell_period_m` is the supercell's own period -- TWICE a single
    tile's pitch for a plain 1:1 alternating checkerboard (one full period
    of the alternation is two tiles), not one tile's own dimension; reading
    it as one tile's pitch is off by a factor of 2 (see
    `checkerboard_supercell_period_m`).
    """
    supercell_period_m = _require_positive_finite("supercell_period_m", supercell_period_m)
    wavelength_m = _require_positive_finite("wavelength_m", wavelength_m)
    return supercell_period_m >= _SQRT_2 * wavelength_m


def checkerboard_supercell_period_m(tile_pitch_m: float) -> float:
    """A plain 1:1 alternating checkerboard's supercell period -- twice a
    single tile's own pitch, since one full period of the 0/1 alternation
    spans two tiles (see `diffracted_order_exists`'s docstring)."""
    return 2.0 * _require_positive_finite("tile_pitch_m", tile_pitch_m)


def diffracted_order_regime(tile_pitch_m: float, wavelength_m: float) -> dict[str, Any]:
    """Decide which of two bound regimes a plain 1:1 checkerboard's tile
    pitch falls into at `wavelength_m`, per
    docs/example7-coding-metasurface-scoring-recipe.md Sec 3 /
    designs/design_families.py's DIFFUSIVE reason string.

    Does NOT implement the Rozanov/Gustafsson & Sjoberg bound itself
    (#465) -- only decides which regime applies, so a caller knows whether
    an apparent RCS reduction is a genuine diffuse-scattering effect
    (exempt from an absorption-style bound because the redirected power has
    somewhere to go) or must instead be judged against an absorption bound
    (the supercell is too small to launch a propagating order at all, so
    any reduction is coming from loss, not redistribution).
    """
    supercell_period_m = checkerboard_supercell_period_m(tile_pitch_m)
    exists = diffracted_order_exists(supercell_period_m, wavelength_m)
    if exists:
        bound_regime = "NO_PHYSICAL_BOUND"
        reason = (
            f"supercell period {supercell_period_m * 1e3:.2f} mm >= "
            f"sqrt(2)*wavelength ({_SQRT_2 * wavelength_m * 1e3:.2f} mm) at "
            f"{wavelength_m * 1e3:.2f} mm wavelength: a propagating diffracted "
            "order exists, so a redirected specular return has somewhere to go "
            "-- this candidate is exempt from an absorption-style bound "
            "(docs/example7-coding-metasurface-scoring-recipe.md Sec 3)."
        )
    else:
        bound_regime = "ROZANOV_BOUNDED"
        reason = (
            f"supercell period {supercell_period_m * 1e3:.2f} mm < "
            f"sqrt(2)*wavelength ({_SQRT_2 * wavelength_m * 1e3:.2f} mm) at "
            f"{wavelength_m * 1e3:.2f} mm wavelength: too small to launch a "
            "propagating diffracted order at all, so any apparent RCS "
            "reduction must be coming from absorption, not redistribution -- "
            "judge this candidate against an absorption bound instead."
        )
    return {
        "supercell_period_m": supercell_period_m,
        "wavelength_m": wavelength_m,
        "diffracted_order_exists": exists,
        "bound_regime": bound_regime,
        "reason": reason,
    }


def resolve_checkerboard_tile_symbols(
    symbol_entries: list[dict[str, Any]],
    element_family: str,
    frequency_points_hz: Sequence[float],
    incidence_angle_deg: float,
    process_id: int,
) -> tuple[str, str]:
    """Resolve the two symbol ids a plain 1:1 alternating checkerboard
    needs, from an already-fetched `designs.element_alphabet.
    fetch_symbol_entries` result -- mirroring `orchestration.
    design_loop_optimization._combinatorial_candidate_options`'s
    alphabet-lookup shape (distinct symbols first, then a per-frequency
    `lookup_symbol_entries` match for each), narrowed to the two symbols
    that match at EVERY requested frequency point, not just one.

    Deterministic: returns the first two matching symbols in sorted
    (alphabetical) order, so the same `symbol_entries` always resolves the
    same pair.

    Raises `InsufficientTilesError`, naming the full key that failed to
    resolve, if fewer than two symbols match `element_family` across the
    whole of `frequency_points_hz` at `incidence_angle_deg`/`process_id` --
    mirroring `_optimize_combinatorial_symbol_placement`'s "zero matching
    entries fails loudly, naming the key" convention (issue #550's own
    Testing Decisions section).
    """
    distinct_symbols = sorted(
        {e["symbol"] for e in symbol_entries if e["element_family"] == element_family}
    )
    usable = [
        symbol
        for symbol in distinct_symbols
        if all(
            lookup_symbol_entries(
                symbol_entries, element_family, symbol, f, incidence_angle_deg, process_id
            )
            for f in frequency_points_hz
        )
    ]
    if len(usable) < 2:
        raise InsufficientTilesError(
            "a plain 1:1 DIFFUSIVE checkerboard needs at least two symbols "
            "characterised across the whole requested band for "
            f"element_family={element_family!r}, incidence_angle_deg="
            f"{incidence_angle_deg!r}, process_id={process_id!r}, "
            f"frequency_points_hz={list(frequency_points_hz)!r}, and only "
            f"{usable!r} matched at every point (of {distinct_symbols!r} "
            "distinct symbols present for this family at all). Nothing can be "
            "scored until at least two tiles are characterised for this "
            "exact family/band/incidence-angle/process combination (issue "
            "#132's print-and-measure work)."
        )
    return usable[0], usable[1]


def score_diffusive_checkerboard(
    symbol_entries: list[dict[str, Any]],
    element_family: str,
    frequency_points_hz: Sequence[float],
    incidence_angle_deg: float,
    process_id: int,
    delta_phi_max_deg: float,
    threshold_db: float | None = None,
) -> dict[str, Any]:
    """Score a plain 1:1 alternating checkerboard built from the two tiles
    `resolve_checkerboard_tile_symbols` resolves, across every point in
    `frequency_points_hz`, as the worst-in-band `RCS_reduction_dB` (see this
    module's docstring for why "worst" is the numeric MAXIMUM of that
    signed curve, not the minimum).

    `threshold_db` is a positive dB magnitude -- "at least this much
    reduction" -- matching how a customer states the requirement (issue
    #550's default: 10 dB, `DEFAULT_RCS_REDUCTION_THRESHOLD_DB`, applied
    and flagged as a filled default only when the caller passes `None`; an
    explicit caller value always overrides without argument, per
    docs/requirement-derived-thresholds.md's "a convention is a default,
    never a threshold").

    Returns a dict naming the worst frequency and its reduction, the full
    per-frequency curve, whether the worst point meets the threshold, the
    threshold actually used and whether it was defaulted, and the
    weakest-of provenance across every tile lookup made.
    """
    if not frequency_points_hz:
        raise ValueError("frequency_points_hz must contain at least one frequency")
    tile_a, tile_b = resolve_checkerboard_tile_symbols(
        symbol_entries, element_family, frequency_points_hz, incidence_angle_deg, process_id
    )

    curve: list[dict[str, Any]] = []
    combined_provenance: str | None = None
    for frequency_hz in frequency_points_hz:
        entry_a = lookup_symbol_entries(
            symbol_entries, element_family, tile_a, frequency_hz, incidence_angle_deg, process_id
        )[0]
        entry_b = lookup_symbol_entries(
            symbol_entries, element_family, tile_b, frequency_hz, incidence_angle_deg, process_id
        )[0]
        phase_a_deg = reduce_response_at_frequency(entry_a["response"], frequency_hz, "phase_deg")
        phase_b_deg = reduce_response_at_frequency(entry_b["response"], frequency_hz, "phase_deg")
        delta_deg = phase_error_deg(phase_a_deg, phase_b_deg, delta_phi_max_deg)
        reduction_db = rcs_reduction_db(delta_deg)
        point_provenance = weaker_provenance(entry_a["provenance"], entry_b["provenance"])
        combined_provenance = (
            point_provenance
            if combined_provenance is None
            else weaker_provenance(combined_provenance, point_provenance)
        )
        curve.append(
            {
                "frequency_hz": frequency_hz,
                "delta_deg": delta_deg,
                "rcs_reduction_db": reduction_db,
                "provenance": point_provenance,
            }
        )

    # Worst-in-band: the point CLOSEST TO ZERO, i.e. the numeric MAXIMUM of
    # this non-positive curve -- see module docstring for the sign
    # convention this depends on.
    worst = max(curve, key=lambda p: p["rcs_reduction_db"])

    threshold_is_default = threshold_db is None
    threshold_db = (
        DEFAULT_RCS_REDUCTION_THRESHOLD_DB if threshold_is_default else float(threshold_db)
    )
    meets_threshold = worst["rcs_reduction_db"] <= -threshold_db

    return {
        "tile_a": tile_a,
        "tile_b": tile_b,
        "curve": curve,
        "worst_rcs_reduction_db": worst["rcs_reduction_db"],
        "worst_frequency_hz": worst["frequency_hz"],
        "threshold_db": threshold_db,
        "threshold_is_default": threshold_is_default,
        "meets_threshold": meets_threshold,
        "provenance": combined_provenance,
    }


def materialize_checkerboard_unit_cell_array(
    tile_a_id: str,
    tile_b_id: str,
    symbol_library: Mapping[str, dict[str, Any] | list[dict[str, Any]]],
    pitch_m: tuple[float, float],
    delta_phi_max_deg: float,
    rcsr_db: float,
    wavelength_m: float,
    panel_size_m: tuple[float, float],
    theta_min_deg: float | None = None,
    max_block_n: int = 32,
) -> list[dict[str, Any]]:
    """Materialize a plain 1:1 alternating checkerboard from a winning tile
    pair, chaining `geometry.unit_cell.block_size_from_sizing_rule` and
    `generate_coded_unit_cell_array` (issue #550) -- no new chaining logic
    of its own, since `generate_coded_unit_cell_array` already derives its
    block size from the sizing rule internally; this function's only job is
    to build the fixed 2x2 alternating-by-parity `layout` a plain 1:1
    checkerboard is, and hand it straight through.

    The arrangement is fixed, not searched: `layout[j][i]` alternates
    `tile_a_id`/`tile_b_id` by `(i + j) % 2`, the smallest layout that
    expresses "two tiles alternating in both directions" -- a general
    arrangement search over more than two symbols is explicitly out of
    scope for this module (see module docstring).
    """
    layout = [[tile_a_id if (i + j) % 2 == 0 else tile_b_id for i in range(2)] for j in range(2)]
    return generate_coded_unit_cell_array(
        layout=layout,
        symbol_library=symbol_library,
        pitch_m=pitch_m,
        delta_phi_max_deg=delta_phi_max_deg,
        rcsr_db=rcsr_db,
        wavelength_m=wavelength_m,
        panel_size_m=panel_size_m,
        theta_min_deg=theta_min_deg,
        max_block_n=max_block_n,
    )
