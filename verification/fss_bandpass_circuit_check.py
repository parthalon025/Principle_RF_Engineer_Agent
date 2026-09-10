"""Drive a published, MEASURED band-pass FSS through this repo's own maths.

    uv run python -m verification.fss_bandpass_circuit_check

No solver binary, no container, no conda environment. That is the point of
this one: of the four literature reference cases issue #386 built, this is
the only one this repository can pose today, so it is the only one that
produces a number rather than a reason it cannot.

WHAT IS BEING CHECKED, AND AGAINST WHAT. Every reference case that came
before this checked a solver against ALGEBRA -- a half-wave dipole's
73 + j42.5 ohms, a matched sheet's exact one half. Those prove the plumbing.
None of them proves that anything here, handed a real printed metasurface,
predicts what the object did on a bench. Tehranian et al. built one: three
patterned silver-paste layers dispensed inside a 4.5 mm 3D-printed ABS
radome, and they measured it (arXiv:2511.16777v1). This script reconstructs
their surface from the numbers they publish, solves it with
`rf_tools/transmissive_absorber.py`'s ABCD primitives, and scores the result
against their planar measurement.

*In plain terms: somebody printed a filter out of silver paste and measured
it. We rebuild it out of the numbers in their paper, run our own arithmetic
over it, and see whether we would have predicted what their instrument
showed. This is the first time anything in this repository has been asked
that question about a printed part.*

THE ANSWER IS A FAILURE, AND THE FAILURE IS THE USEFUL PART. The stop-band
lands where the paper says it does. The passband does not: the
reconstruction returns about -0.39 dB of insertion loss at 10 GHz where the
bench measured roughly -1.7 dB, missing by more than the paper's own 1 dB
simulated-versus-measured gap allows. The suspect is named rather than
absorbed into a wider tolerance -- the paper states its silver paste's
conductivity (10^6 S/m, some sixty times worse a conductor than copper) but
never how thick the dispensed traces are, so the sheet resistance cannot be
computed and the shunt elements below are LOSSLESS. In plain terms: our
model gave the surface free wiring, and the real one was made of something
closer to pencil lead.

That is directly load-bearing for this programme, whose own manufacturing
route is dispensed paste rather than etched copper. It says a lossless
circuit reconstruction of a paste-printed surface will flatter its passband,
and roughly by how much.

WHY THE PLANAR CURVE AND NOT THE HEMISPHERICAL ONE. The paper's headline
result is the same unit cell wrapped onto a 150 mm dome. This model is a
flat, infinitely repeating cell. Scoring one against the other would compare
two different physical problems and could return either a false pass or a
false fail, so Fig. 17's planar curve is the only thing read here and the
case records the exclusion in its own `source.excluded`.

WHY A CIRCUIT MODEL IS A LEGITIMATE RECONSTRUCTION HERE, and not a shortcut.
The paper does not merely leave a circuit model implicit: it designs the
surface with one, publishes the two element values the geometry was sized to
realise (C = 78 fF per capacitive layer, L = 1.66 nH for the inductive layer
between them), and prints its own circuit model against its own full-wave
result in Fig. 3. The wheel-spoke pattern that realises those values appears
only in a figure and is not reconstructible from the text -- but it does not
need to be, because the quantity it was drawn to produce is published. What
a full-wave run would add is checked in
`docs/literature-validation-cases.md`, not claimed here.

Deliberately a script rather than a pytest test, matching its three Meep
neighbours: it prints a comparison a human reads. The mechanics -- the stack
order, the passivity, the executed numbers -- are asserted in
`tests/test_literature_reference_cases.py`, which runs everywhere.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from rf_tools.transmissive_absorber import (
    cascade,
    dielectric_slab_abcd,
    s_parameters,
    shunt_sheet_abcd,
)
from verification.simulator_reference_cases import (
    BANDPASS_FSS_SILVER_PASTE,
    CaseOutcome,
    CaseScore,
    Comparison,
    score_reference_case,
)

CASE_ID = BANDPASS_FSS_SILVER_PASTE.case_id

#: The two frequencies the case is scored at, and the result keys they are
#: recorded under. Kept beside each other so a frequency cannot be changed
#: without the key it is filed as changing with it.
SCORED_POINTS: dict[str, float] = {
    "transmission_db_at_10ghz": 10e9,
    "transmission_db_at_20ghz": 20e9,
}


def _layers() -> list[dict[str, Any]]:
    return list(BANDPASS_FSS_SILVER_PASTE.geometry["layers"])


def _omega(frequency_hz: float) -> float:
    return 2 * math.pi * frequency_hz


@dataclass(frozen=True)
class _LayerKind:
    """Everything this script knows about one kind of layer, held together.

    The reconstruction's layers are plain dicts tagged with a `kind` string,
    and three different questions get asked of that tag: what ABCD matrix the
    layer contributes, whether it counts toward the dielectric thickness, and
    how it prints. Answering each with its own `if kind == ...` chain means
    three edits to add a fourth kind and three places for them to disagree --
    and the printing chain in particular used to end in a bare `else`, so an
    unrecognised layer would have been described as an inductor rather than
    rejected. One key, one entry, one place to be wrong.

    ON THE PHYSICS, since it is easy to skim past in a table: a capacitive
    FSS layer is a shunt susceptance jwC across the line, an inductive one is
    1/(jwL). Both are LOSSLESS, and that is not an oversight -- see the module
    docstring and the case's own recorded assumption. The paste's real loss
    cannot be reconstructed from what the paper publishes, so it is left out
    visibly rather than approximated by a number nobody could cite. The
    `(LOSSLESS)` each description carries is there so a reader of the printed
    output cannot miss it either.
    """

    is_dielectric: bool
    abcd: Callable[[dict[str, Any], float], Any]
    describe: Callable[[dict[str, Any]], str]


_LAYER_KINDS: dict[str, _LayerKind] = {
    "dielectric": _LayerKind(
        is_dielectric=True,
        abcd=lambda layer, hz: dielectric_slab_abcd(
            hz, layer["eps_r"], layer["tan_delta"], layer["thickness_m"]
        ),
        describe=lambda layer: f"{layer['thickness_m'] * 1e3:.2f} mm ABS, eps_r {layer['eps_r']}",
    ),
    "shunt_capacitance": _LayerKind(
        is_dielectric=False,
        abcd=lambda layer, hz: shunt_sheet_abcd(1j * _omega(hz) * layer["farads"]),
        describe=lambda layer: f"shunt {layer['farads'] * 1e15:.0f} fF  (LOSSLESS)",
    ),
    "shunt_inductance": _LayerKind(
        is_dielectric=False,
        abcd=lambda layer, hz: shunt_sheet_abcd(1 / (1j * _omega(hz) * layer["henries"])),
        describe=lambda layer: f"shunt {layer['henries'] * 1e9:.2f} nH  (LOSSLESS)",
    ),
}


def _layer_kind(layer: dict[str, Any]) -> _LayerKind:
    """The single lookup, so an unrecognised kind fails loudly and in one place."""
    kind = layer["kind"]
    if kind not in _LAYER_KINDS:
        raise ValueError(f"unknown layer kind {kind!r} in the reconstruction")
    return _LAYER_KINDS[kind]


def layer_stack_thickness_m() -> float:
    """Total dielectric thickness of the reconstruction, in metres.

    The paper's own figure is 4.5 mm. A stack that does not add up to it has
    a layer missing or doubled -- an error no S-parameter comparison would
    reveal, because a stack of the wrong thickness still produces a perfectly
    plausible band-pass somewhere else.
    """
    return sum(layer["thickness_m"] for layer in _layers() if _layer_kind(layer).is_dielectric)


def circuit_reading(frequency_hz: float) -> dict[str, float]:
    """|S11| and |S21| in dB at one frequency, through the committed primitives.

    The layers are cascaded in the order the wave meets them, straight off
    the case's own geometry. ABCD matrices do not commute, so that order IS
    the part: a spacer and a patterned sheet the other way round is a
    different object, and the arithmetic would solve it just as happily.
    """
    geometry = BANDPASS_FSS_SILVER_PASTE.geometry
    matrices = [_layer_kind(layer).abcd(layer, frequency_hz) for layer in _layers()]
    s11, s21 = s_parameters(
        cascade(*matrices),
        geometry["port_impedance_ohm"],
        geometry["load_impedance_ohm"],
    )
    return {
        "frequency_hz": float(frequency_hz),
        "s11_db": _to_db(s11),
        "s21_db": _to_db(s21),
    }


def _to_db(value: complex) -> float:
    magnitude = abs(value)
    if magnitude == 0.0:
        return -math.inf
    return 20 * math.log10(magnitude)


def result_record() -> dict[str, Any]:
    """The reconstruction's answer, shaped for `score_reference_case`.

    Flat keys, matching the `result_key` each expected value declares, so
    nothing has to be renamed on the way in. `provenance` is SIMULATED and
    stays there: this is arithmetic over somebody else's published design,
    not a measurement of anything we own.
    """
    record: dict[str, Any] = {
        "function": "circuit_reading",
        "simulator": "rf_tools.transmissive_absorber (ABCD cascade)",
        "provenance": BANDPASS_FSS_SILVER_PASTE.provenance,
        "converged": True,
    }
    for key, frequency_hz in SCORED_POINTS.items():
        record[key] = circuit_reading(frequency_hz)["s21_db"]
    return record


def run_case() -> CaseScore:
    """Solve and score the case in one call, for the script and the tests."""
    return score_reference_case(BANDPASS_FSS_SILVER_PASTE, result_record())


def passband_edges_db(threshold_db: float = -1.0) -> tuple[float, float]:
    """Where the reconstruction's transmission crosses `threshold_db`.

    Reported rather than scored. The paper calls its surface a "wide-band
    (7-13 GHz) band-pass" without saying at what depth those edges are taken,
    so turning that phrase into a pass/fail would need a definition the paper
    does not supply -- exactly the kind of invented criterion this case's
    bands are built to avoid.
    """
    inside = [
        i * 1e7 for i in range(400, 2001) if circuit_reading(i * 1e7)["s21_db"] >= threshold_db
    ]
    if not inside:
        return (math.nan, math.nan)
    return (min(inside), max(inside))


def main() -> int:
    case = BANDPASS_FSS_SILVER_PASTE
    assert case.source is not None and case.run is not None
    record = result_record()
    score = score_reference_case(case, record)

    print("\n=== band-pass FSS, silver paste dispensed on 3D-printed ABS ===")
    print(f"  paper          {case.source.citation}")
    print(f"  scored against {case.source.scored_against}")
    print(f"  solver         {case.run.solver}")
    print(f"  pinned at      {case.run.adapter_module} @ {case.run.adapter_commit[:12]}")
    print(f"  provenance     {record['provenance']}")

    print("\n  --- the reconstruction, in the order the wave meets it ---")
    for layer in _layers():
        detail = _layer_kind(layer).describe(layer)
        print(f"    {detail:<34}{layer['role']}")
    print(f"    {f'{layer_stack_thickness_m() * 1e3:.2f} mm':<34}total dielectric thickness")

    print("\n  --- transmission, reconstruction against the bench ---")
    print(f"  {'':<8}{'ours':>10}{'paper':>10}   band")
    for expected in case.expected:
        actual = record[expected.result_key]
        label = expected.result_key.replace("transmission_db_at_", "").upper()
        relation = "<=" if expected.comparison is Comparison.AT_MOST else "+/-"
        print(
            f"  {label:<8}{actual:>10.3f}{expected.value:>10.3f}"
            f"   {relation} {expected.tolerance:.2f} {expected.unit}"
            f"  ({expected.band.set_by if expected.band else 'chosen'})"
        )

    low, high = passband_edges_db()
    print(
        f"\n  Reported, not scored: the -1 dB passband runs "
        f"{low / 1e9:.2f}-{high / 1e9:.2f} GHz, against the paper's stated "
        f"7-13 GHz band.\n  The paper does not say at what depth it takes those "
        "edges, so this is a sanity\n  check on the reconstruction rather than a "
        "criterion it can pass or fail."
    )

    print("\n  --- scored, reflection and transmission kept apart ---")
    print(f"  outcome        {score.outcome.value}")
    print(f"  reflection     {len(score.reflection)} discrepancy(s)")
    print(f"  transmission   {len(score.transmission)} discrepancy(s)")
    if score.unresolved_reason:
        print(f"  unresolved     {score.unresolved_reason}")
    for problem in score.listed:
        print(f"  ! {problem}")

    if score.outcome is CaseOutcome.FAIL:
        print(
            "\n  The failure is the finding. This reconstruction has LOSSLESS\n"
            "  shunt elements, because the paper gives its silver paste's\n"
            "  conductivity (10^6 S/m, roughly sixty times worse than copper)\n"
            "  but never how thick the dispensed traces are -- and without a\n"
            "  thickness there is no sheet resistance to put in. So the model\n"
            "  wires the surface for free and the bench did not. The stop-band,\n"
            "  which is set by the reactances rather than by the losses, lands\n"
            "  where the paper says it does; the passband, where the loss shows\n"
            "  up, is about 1.3 dB too shallow.\n\n"
            "  What that costs this programme, plainly: a lossless circuit model\n"
            "  of a paste-printed surface will flatter its passband, and this is\n"
            "  the first measurement of by how much. The band was NOT widened to\n"
            "  make it pass -- see the case's own tolerance rationale."
        )

    return 0 if score.outcome is CaseOutcome.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
