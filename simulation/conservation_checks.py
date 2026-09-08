"""Checks any simulator's parsed S-parameter result against physics it
cannot violate, regardless of what the mesh, solver, or adapter code got
wrong about the geometry (issue #221).

Three checks, each returning a numeric margin, never a bare pass/fail:

  - POWER BALANCE. For a lossless structure, everything incident comes back
    out: sum over every propagating response (reflection, transmission,
    every propagating diffraction order) of |S|^2 == 1. For a lossy
    structure it must be <= 1, and the shortfall (1 - sum) IS the
    dissipation -- for an absorber design, that shortfall is the quantity
    being designed, not an error.
  - PASSIVITY. No single S-parameter can return more power than went in:
    |S| <= 1, always, for a structure with no active/amplifying element.
  - RECIPROCITY. For any reciprocal medium (everything this project
    currently builds, per CLAUDE.md -- absent a magnetised ferrite or an
    active element, neither of which exists here as a buildable design),
    S_ij == S_ji.

ADR-0028 ("warn, never block", docs/adr/0028-*.md): NONE of this raises or
refuses. A violation is returned alongside the result, annotated with what
is assumed, what it costs if that assumption is wrong, and the cheapest way
to find out -- exactly the shape every other soft-warning check in this
codebase uses (see e.g. simulation/kicad_gerber2ems.py's `warnings` list).
The reader decides what to do with a flagged candidate; this module never
decides for them.

TOLERANCE DERIVATION
=====================
The hard part of this check is not the arithmetic (it is 15 lines of
sum-of-squares); it is drawing a tolerance band wide enough that ordinary
mesh discretisation noise does not "cry wolf" on every real run, and tight
enough that it still catches a gross defect.

Empirical anchor -- issue #221 itself states: "a prior real Palace run
measured residuals of 0.013 dB mean / 0.056 dB max on power-carrying
points". This repo was searched (`docs/`, `simulation/`, `tests/`) for the
run that produced those numbers and none was found: issue #210, the ticket
that would run the Palace adapter against a real binary and produce that
artefact, is still open as of 2026-09-08 (confirmed via the issue tracker
before writing this module) -- so that 0.013/0.056 dB figure is taken here
as a given fact reported by the issue author from outside this repo's
history, not re-derived from a committed source, and is cross-checked below
rather than trusted blindly.

First-principles cross-check -- converting a power-domain fractional error
`x` into dB via `10*log10(1 +/- x)`: a 0.3% power discretisation error is
0.013 dB, a 1.3% error is 0.056 dB. Both are unremarkable residuals for a
low-order (linear edge-element) FEM solve on a coarse-to-moderate mesh --
this adapter's own default mesh density (`simulation/palace.py`'s
`generate_palace_mesh`, "mesh": {"nx"/"ny"/"nz"}, default 2 elements per
feature interval) is explicitly documented there as "deliberately coarse",
so a real run at that default, or a modestly refined one, sitting in the
0.3-1.3% power-residual range is exactly what would be expected -- neither
number implies a solver defect on its own.

Chosen default -- POWER_TOLERANCE_DB = 0.2 dB (a power-domain quantity: for
a single S-parameter, `10*log10(|S|^2) == 20*log10(|S|)`, so the same
constant applies to both the power-balance sum and the single-entry
passivity check without contradiction). That is ~3.6x the cited 0.056 dB
max residual and ~15x the 0.013 dB mean -- wide enough to absorb the spread
this repo's adapters can produce across their own caller-controlled mesh
densities (finer than the coarse default gives a *tighter* residual, not a
looser one, so 0.056 dB is a reasonable upper anchor, not a lower bound),
while a bug at the scale this ticket names ("-139 dB-scale") is unmistakably
gross whenever the corrupted entry carries a non-negligible power fraction:
e.g. an entry that legitimately carries 25% of incident power (-6.02 dB)
corrupted down near the noise floor produces a ~1.25 dB shortfall -- over
6x this tolerance.

HONEST LIMIT, stated rather than hidden: the power-balance check's
sensitivity to any *one* corrupted entry is bounded by how much power that
entry legitimately carries. issue #221's own motivating numbers -- a true
value of -18.9 dB (a 1.29% power fraction) silently replaced by -158 dB
(~0) -- induce a power-balance shortfall of `10*log10(1-0.01288) = -0.056
dB`, which is, by the arithmetic above, indistinguishable in scale from
this same adapter's own ordinary *maximum* discretisation residual. A
power-balance check tight enough to always catch that exact magnitude of
corruption on its own would also flag ordinary, correct runs at their own
documented noise ceiling -- the "don't cry wolf" requirement and "catch
this exact case" requirement are in direct tension at that specific power
fraction, and no tolerance choice resolves both at once. This module
resolves the tension honestly rather than picking a number that quietly
fails one side: it is tuned to reliably catch a corruption that matters to
total energy (this ticket's own explicit acceptance bar, "a gross miss");
tests/test_conservation_checks.py includes a case built from issue #221's
own exact -18.9 dB / -158 dB numbers demonstrating this module correctly
does NOT flag it (by design -- see that test's docstring), alongside a case
at a larger, unambiguous power fraction that it does flag. A corrupted
entry too weak to move the total noticeably is, definitionally, also too
weak to be a load-bearing error in the design decision the result feeds
(ADR-0028's "load-bearing" test) -- catching it needs a different signal
(e.g. comparing against a second independent solve, or a per-mode
plausibility check against precedent), not a tighter power-balance number.

RECIPROCITY_TOLERANCE_DB = 0.5 dB: a reciprocity check differences two
*independently computed* S-parameters (S_ij from one excitation's solve,
S_ji from a different excitation's solve), each carrying its own
POWER_TOLERANCE_DB-scale discretisation noise. Worst-case (uncorrelated,
same-sign-opposing) addition of two 0.2 dB-scale noise sources bounds the
combined difference at ~0.4 dB; 0.5 dB adds a small margin without giving
up much discriminating power.

NOISE FLOOR -- NOISE_FLOOR_DB = -100.0 dB (magnitude 1e-5): issue #221 flags
that a numerical-zero cross-polarised term (its own example: -204 dB) is
noise, not physics, and must not manufacture a false "disagreement" when
compared in dB terms against another near-zero number (the ratio/difference
of two tiny floats is not physically meaningful). -100 dB is chosen with
~100 dB of headroom over this module's own ~0.06 dB-scale tolerances (so it
never masks a real violation at a power-carrying point) while sitting
comfortably above floating-point-only artefacts (typically far below -200
dB) -- any two values both below this floor are treated as "both
numerically zero", not compared by ratio.

USAGE
=====
Build a list of `SParamEntry` (frequency, exciting port/mode, responding
port/mode, complex value) -- either directly, or via one of the two adapter
functions below for this codebase's two existing S-parameter shapes -- and
pass it to `check_conservation()`. See `check_palace_result` and
`check_flat_s_parameters` for the two ready-made entry points; both are
plain functions returning a JSON-serialisable dict, called this module is
NOT wired into every simulator adapter automatically -- see this ticket's
final report / commit message for which one adapter it IS wired into and
why the others were left as standalone opt-in calls.
"""

from __future__ import annotations

import cmath
import math
import re
from typing import Any, NamedTuple

# ---------------------------------------------------------------------------
# Tolerances -- see module docstring "TOLERANCE DERIVATION" above for the
# reasoning behind each of these three numbers. All three are keyword
# defaults on check_conservation(), never hardcoded past that one point, so
# a caller with better information (e.g. a real per-run mesh-convergence
# estimate) can override them.
# ---------------------------------------------------------------------------

POWER_TOLERANCE_DB = 0.2
RECIPROCITY_TOLERANCE_DB = 0.5
NOISE_FLOOR_DB = -100.0
NOISE_FLOOR_LINEAR = 10 ** (NOISE_FLOOR_DB / 20.0)  # ~1e-5


class SParamEntry(NamedTuple):
    """One parsed S-parameter data point: the complex response observed at
    `response` (a port, or a Floquet "port(m,n)polarization" diffraction-
    order label) for unit excitation at `excitation`, at `frequency_hz`.
    `excitation == response` is a valid entry (e.g. S11): the port's own
    reflection back into itself."""

    frequency_hz: float
    excitation: str
    response: str
    value: complex


# ---------------------------------------------------------------------------
# Adapter functions: this codebase's two existing S-parameter shapes ->
# SParamEntry rows. Both are honest about what they skip (never invent a
# value for a shape they don't recognize).
# ---------------------------------------------------------------------------

_SIJ_KEY_RE = re.compile(r"^S(\d)(\d)$")


def entries_from_flat_s_parameters(
    s_parameters: dict[str, Any],
    frequency_hz: list[float],
) -> list[SParamEntry]:
    """Convert the flat `{"S<response><excitation>": [[re, im], ...], ...}`
    shape used by simulation/openems.py, simulation/gprmax.py,
    simulation/kicad_gerber2ems.py and simulation/hfss.py (each paired with
    a parallel `frequency_hz` list of the same length) into `SParamEntry`
    rows. "S21" means: response observed at port 2, port 1 excited --
    standard Touchstone/RF convention, matching every one of those
    adapters' own `f"S{output_port}{excited_port}"` construction.

    Single-digit ports only (matches the regex those adapters themselves
    build their "Sij" keys with -- not a new limitation introduced here).
    Non-"Sij" keys in the dict (e.g. "touchstone_file", "computed", "note")
    are skipped, not an error. A `None` entry (a real, honestly-reported
    parse gap in the source adapter) is skipped, not fabricated.
    """
    entries: list[SParamEntry] = []
    for key, values in s_parameters.items():
        match = _SIJ_KEY_RE.match(key)
        if not match or not isinstance(values, list):
            continue
        response, excitation = match.group(1), match.group(2)
        for f_hz, v in zip(frequency_hz, values, strict=False):
            if v is None:
                continue
            re_part, im_part = (v.real, v.imag) if isinstance(v, complex) else (v[0], v[1])
            value = complex(re_part, im_part)
            entries.append(SParamEntry(float(f_hz), excitation, response, value))
    return entries


def entries_from_palace_modes(parsed: dict[str, Any]) -> list[SParamEntry]:
    """Convert simulation/palace.py's `parse_palace_output()` result into
    `SParamEntry` rows, from its FULL `modes` dict -- every diffraction
    order and every polarization component, not the `specular` convenience
    view. This is deliberate, not incidental: `specular` collapses each
    (port, m=0, n=0) mode down to one `f"S{port}1"` key regardless of
    polarization, so a co-polarized and a cross-polarized mode at the same
    diffraction order can collide on that one key -- exactly the class of
    defect issue #221 names (a near-zero cross-pol value overwriting a real
    co-pol one). `modes`, whose keys carry the full mode label including
    polarization, has no such collision -- summing over it is how this
    module's power-balance check sees every real contribution regardless of
    what a downstream convenience view later does with the same data.

    `excitation` is the mode's own "excitation" field (this adapter's
    config always excites port 1, so today this is always "1" -- a future
    multi-excitation config would populate it correctly with no change
    needed here). `response` is `f"P{port}({m},{n}){polarization}"`. A
    `None` value_complex entry (Palace's own "nan" for a non-propagating
    order, or a column this parser could not pair up) is skipped, not
    fabricated -- matching parse_palace_output's own documented convention.
    """
    if not parsed.get("computed"):
        return []
    frequency_hz = parsed["frequency_hz"]
    entries: list[SParamEntry] = []
    for meta in parsed["modes"].values():
        label = f"P{meta['port']}({meta['m']},{meta['n']}){meta['polarization']}"
        excitation = str(meta["excitation"])
        for f_hz, v in zip(frequency_hz, meta["value_complex"], strict=False):
            if v is None:
                continue
            entries.append(SParamEntry(float(f_hz), excitation, label, complex(v[0], v[1])))
    return entries


# ---------------------------------------------------------------------------
# Core checks
# ---------------------------------------------------------------------------


def _power_db(power: float) -> float:
    """10*log10(power), or -inf for power <= 0 (no log(0) crash)."""
    return 10.0 * math.log10(power) if power > 0 else -math.inf


def _check_power_balance(
    entries: list[SParamEntry],
    lossless: bool | None,
    tolerance_db: float,
) -> list[dict[str, Any]]:
    groups: dict[tuple[float, str], list[SParamEntry]] = {}
    for e in entries:
        groups.setdefault((e.frequency_hz, e.excitation), []).append(e)

    results: list[dict[str, Any]] = []
    for (f_hz, excitation), group in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        power_sum = sum(abs(e.value) ** 2 for e in group)
        power_db = _power_db(power_sum)
        excess_db = max(0.0, power_db) if math.isfinite(power_db) else math.inf
        # Deficit ("missing" power) is only a VIOLATION when the structure
        # is declared lossless -- otherwise it's the dissipation the
        # structure was built to have (e.g. an absorber), reported as
        # information, never flagged.
        deficit_db = max(0.0, -power_db) if math.isfinite(power_db) else math.inf
        violates_excess = excess_db > tolerance_db
        violates_deficit = lossless is True and deficit_db > tolerance_db
        ok = not (violates_excess or violates_deficit)
        dissipation_fraction = max(0.0, 1.0 - power_sum)

        notes = [
            f"sum|S|^2 over {len(group)} response(s) at {f_hz / 1e9:.4f} GHz "
            f"(excitation {excitation!r}) = {power_sum:.6g} ({power_db:+.4f} dB)."
        ]
        if violates_excess:
            notes.append(
                "ASSUMED: a passive structure (no active/amplifying element). "
                f"COST IF WRONG: {excess_db:.4f} dB of power ({(power_sum - 1) * 100:.3g}% "
                "more out than in) appears from nowhere -- either a genuine gain "
                "element the requirement never declared, or a parsing/units defect "
                "(wrong port reference impedance, a mislabeled column, a "
                "dictionary-key collision like issue #221's motivating bug). "
                "CHEAPEST CHECK: re-derive this one frequency point's S-parameters "
                "by hand from the raw solver output file."
            )
        if lossless is True and violates_deficit:
            notes.append(
                "ASSUMED: structure declared lossless. "
                f"COST IF WRONG: {deficit_db:.4f} dB ({dissipation_fraction * 100:.3g}% of "
                "incident power) is unaccounted for -- either the lossless "
                "declaration is wrong (an unmodeled lossy material or loss "
                "tangent), a propagating diffraction order was left out of this "
                "sum, or a real return was silently dropped (issue #221's "
                "motivating bug: two mode labels collided on one dictionary key "
                "and the near-zero one survived). "
                "CHEAPEST CHECK: list every mode/port this excitation covers at "
                "this frequency and confirm none are missing from the sum."
            )
        elif lossless is not True and dissipation_fraction > 0:
            notes.append(
                f"{dissipation_fraction * 100:.3g}% of incident power is not "
                "returned at any parsed port/order. If this structure is meant "
                "to be an absorber, this dissipation fraction IS the quantity "
                "being designed. If it is meant to be lossless, re-call with "
                "lossless=True to have this flagged as a violation instead of "
                "reported as information."
            )

        results.append(
            {
                "frequency_hz": f_hz,
                "excitation": excitation,
                "n_responses": len(group),
                "power_sum": power_sum,
                "power_sum_db": power_db,
                "excess_db": excess_db,
                "deficit_db": deficit_db,
                "dissipation_fraction": dissipation_fraction,
                "lossless_declared": lossless is True,
                "tolerance_db": tolerance_db,
                "ok": ok,
                "note": " ".join(notes),
            }
        )
    return results


def _check_passivity(entries: list[SParamEntry], tolerance_db: float) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for e in sorted(entries, key=lambda e: (e.frequency_hz, e.excitation, e.response)):
        power = abs(e.value) ** 2
        magnitude_db = _power_db(power)  # == 20*log10(|S|); same dB scale as power balance
        excess_db = max(0.0, magnitude_db) if math.isfinite(magnitude_db) else math.inf
        ok = excess_db <= tolerance_db
        note = (
            f"|S[{e.response}<-{e.excitation}]| = {abs(e.value):.6g} ({magnitude_db:+.4f} dB) "
            f"at {e.frequency_hz / 1e9:.4f} GHz."
        )
        if not ok:
            note += (
                " ASSUMED: passive structure -- no port returns more power than "
                f"entered it. COST IF WRONG: this single S-parameter alone implies "
                f"{(power - 1) * 100:.3g}% power gain at this port -- either a "
                "genuine active/amplifying element the requirement never "
                "declared, or a units/reference-impedance defect. CHEAPEST CHECK: "
                "confirm this port's characteristic impedance matches the "
                "solver's own reference impedance."
            )
        results.append(
            {
                "frequency_hz": e.frequency_hz,
                "excitation": e.excitation,
                "response": e.response,
                "magnitude_db": magnitude_db,
                "excess_db": excess_db,
                "tolerance_db": tolerance_db,
                "ok": ok,
                "note": note,
            }
        )
    return results


def _check_reciprocity(
    entries: list[SParamEntry],
    reciprocal: bool | None,
    tolerance_db: float,
) -> tuple[list[dict[str, Any]], str | None]:
    if reciprocal is False:
        return [], (
            "reciprocity check skipped: caller declared this medium non-reciprocal "
            "(e.g. a magnetised ferrite or an active element) -- see "
            "simulation/conservation_checks.py's `reciprocal` parameter."
        )

    by_key: dict[tuple[float, str, str], complex] = {}
    for e in entries:
        by_key[(e.frequency_hz, e.excitation, e.response)] = e.value

    seen_pairs: set[tuple[float, frozenset]] = set()
    results: list[dict[str, Any]] = []
    for (f_hz, exc, resp), value_ab in by_key.items():
        if exc == resp:
            continue  # S_ii is a passivity/power-balance datum, not a reciprocity pair
        pair_key = (f_hz, frozenset((exc, resp)))
        if pair_key in seen_pairs:
            continue
        value_ba = by_key.get((f_hz, resp, exc))
        if value_ba is None:
            continue  # no reverse-excitation data present -- not computable, not a violation
        seen_pairs.add(pair_key)

        mag_ab, mag_ba = abs(value_ab), abs(value_ba)
        if mag_ab < NOISE_FLOOR_LINEAR and mag_ba < NOISE_FLOOR_LINEAR:
            results.append(
                {
                    "frequency_hz": f_hz,
                    "port_a": exc,
                    "port_b": resp,
                    "s_ab_db": _power_db(mag_ab**2),
                    "s_ba_db": _power_db(mag_ba**2),
                    "magnitude_diff_db": 0.0,
                    "phase_diff_deg": 0.0,
                    "tolerance_db": tolerance_db,
                    "ok": True,
                    "note": (
                        f"both S[{resp}<-{exc}] and S[{exc}<-{resp}] are below the "
                        f"numerical noise floor (|S| < {NOISE_FLOOR_LINEAR:.1e}, "
                        f"{NOISE_FLOOR_DB:.0f} dB) at {f_hz / 1e9:.4f} GHz -- treated "
                        "as both zero, not compared (see module docstring's NOISE "
                        "FLOOR reasoning)."
                    ),
                }
            )
            continue

        s_ab_db = _power_db(mag_ab**2)
        s_ba_db = _power_db(mag_ba**2)
        magnitude_diff_db = abs(s_ab_db - s_ba_db)
        phase_ab = math.degrees(cmath.phase(value_ab))
        phase_ba = math.degrees(cmath.phase(value_ba))
        phase_diff_deg = abs((phase_ab - phase_ba + 180.0) % 360.0 - 180.0)
        ok = magnitude_diff_db <= tolerance_db
        note = (
            f"S[{resp}<-{exc}] = {s_ab_db:+.4f} dB vs S[{exc}<-{resp}] = {s_ba_db:+.4f} dB "
            f"({magnitude_diff_db:.4f} dB apart), {phase_diff_deg:.2f} deg phase apart, "
            f"at {f_hz / 1e9:.4f} GHz."
        )
        if not ok:
            note += (
                " ASSUMED: reciprocal medium -- no magnetised ferrite or active "
                "element (true of everything this project currently builds, per "
                "CLAUDE.md). COST IF WRONG: a reciprocity break this large "
                f"({magnitude_diff_db:.4f} dB) is not explainable by mesh/solver "
                "noise alone -- likely a parsing defect (a mislabeled port, a "
                "dictionary-key collision, a sign error) or a genuinely "
                "non-reciprocal structure never declared as one (pass "
                "reciprocal=False if it is). CHEAPEST CHECK: re-read both "
                "excitations' raw output rows for this frequency by hand and "
                "confirm which port was actually driven for each."
            )
        results.append(
            {
                "frequency_hz": f_hz,
                "port_a": exc,
                "port_b": resp,
                "s_ab_db": s_ab_db,
                "s_ba_db": s_ba_db,
                "magnitude_diff_db": magnitude_diff_db,
                "phase_diff_deg": phase_diff_deg,
                "tolerance_db": tolerance_db,
                "ok": ok,
                "note": note,
            }
        )
    return results, None


def check_conservation(
    entries: list[SParamEntry],
    *,
    lossless: bool | None = None,
    reciprocal: bool | None = True,
    power_tolerance_db: float = POWER_TOLERANCE_DB,
    reciprocity_tolerance_db: float = RECIPROCITY_TOLERANCE_DB,
) -> dict[str, Any]:
    """Check a normalized list of `SParamEntry` rows against power balance,
    passivity and reciprocity. Never raises on a violation (ADR-0028) --
    every check result carries a numeric margin and an `ok` bool, and a
    violation's own `note` states what is assumed, what it costs if that
    assumption is wrong, and the cheapest way to find out; nothing here
    withholds or refuses the underlying result.

    `lossless`: True to also flag a power-balance DEFICIT (missing energy)
    as a violation -- appropriate when the structure is declared to have no
    lossy material. None/False (default None) reports any deficit as
    information (the dissipation fraction) rather than a violation, which
    is correct for an undeclared or deliberately lossy (e.g. absorber)
    structure. A power-balance EXCESS (more energy out than in) is always
    flagged regardless of this flag -- gain is never physically free.

    `reciprocal`: False declares this medium non-reciprocal (a magnetised
    ferrite or an active element) and skips the reciprocity check entirely
    with an explanatory note rather than silently omitting or failing on
    it -- see module docstring. Default True attempts the check on whatever
    paired excitation/response data is present; frequency/port pairs with
    no reverse-direction data simply produce no reciprocity entry (not
    computable is not the same as a violation).

    Returns a JSON-serializable dict: `{"power_balance": [...],
    "passivity": [...], "reciprocity": [...], "reciprocity_note":
    str|None, "warnings": [str, ...], "n_entries": int, "all_ok": bool}`.
    `warnings` collects every `note` whose check was NOT ok, in the order
    found -- the flat, single list a caller wanting "what should I read"
    without walking three sub-lists can use directly.
    """
    power_balance = _check_power_balance(entries, lossless, power_tolerance_db)
    passivity = _check_passivity(entries, power_tolerance_db)
    reciprocity, reciprocity_note = _check_reciprocity(
        entries, reciprocal, reciprocity_tolerance_db
    )

    warnings = [r["note"] for r in power_balance if not r["ok"]]
    warnings += [r["note"] for r in passivity if not r["ok"]]
    warnings += [r["note"] for r in reciprocity if not r["ok"]]

    all_ok = not warnings

    return {
        "power_balance": power_balance,
        "passivity": passivity,
        "reciprocity": reciprocity,
        "reciprocity_note": reciprocity_note,
        "warnings": warnings,
        "n_entries": len(entries),
        "all_ok": all_ok,
    }


# ---------------------------------------------------------------------------
# Ready-made entry points for this codebase's two existing S-parameter
# shapes (see module docstring USAGE).
# ---------------------------------------------------------------------------


def check_palace_result(
    parsed: dict[str, Any],
    *,
    lossless: bool | None = None,
    reciprocal: bool | None = True,
) -> dict[str, Any]:
    """`entries_from_palace_modes(parsed)` + `check_conservation(...)` in
    one call -- the natural way to check a `simulation.palace.
    parse_palace_output()` (or `run_palace_simulation()["s_parameters"]`)
    result. Returns `{"computed": False, ...}` unchanged (nothing to check)
    when `parsed` itself has no data; otherwise the `check_conservation`
    dict described there."""
    if not parsed.get("computed"):
        return {"computed": False, "note": parsed.get("note", "nothing to check")}
    entries = entries_from_palace_modes(parsed)
    return check_conservation(entries, lossless=lossless, reciprocal=reciprocal)


def check_flat_s_parameters(
    s_parameters: dict[str, Any],
    frequency_hz: list[float],
    *,
    lossless: bool | None = None,
    reciprocal: bool | None = True,
) -> dict[str, Any]:
    """`entries_from_flat_s_parameters(...)` + `check_conservation(...)` in
    one call -- the natural way to check the flat `{"Sij": [[re, im], ...]}`
    result shape used by simulation/openems.py, simulation/gprmax.py,
    simulation/kicad_gerber2ems.py and simulation/hfss.py. This module is
    NOT wired into any of those four adapters automatically (see this
    ticket's commit message / final report for why) -- a caller wanting the
    check for one of them calls this directly on that adapter's own
    `s_parameters`/`frequency_hz` result fields.
    """
    entries = entries_from_flat_s_parameters(s_parameters, frequency_hz)
    return check_conservation(entries, lossless=lossless, reciprocal=reciprocal)
