"""Discretisation-error reporting for a mesh/grid-refinement sweep (issue
#540), lifted from `prototype/mesh-convergence/mesh_convergence_prototype.py`
(PR #528's spike) into a real, tested, solver-agnostic module.

WHAT THIS MODULE IS FOR, AND WHY IT EXISTS AT ALL. Every mesh this repo's
solver adapters use is a hardcoded default -- openEMS requires caller-
supplied mesh lines and only checks they exist (`simulation/openems.py`),
Elmer's own docstring calls its default max element size "a coarse
heuristic, not a mesh-convergence-verified value", and Palace defaults to
2 elements per feature interval, "deliberately coarse". Nothing in this
repo has ever refined a mesh to see whether a `SIMULATED` result's answer
stops moving -- so nothing here can currently say HOW converged a solver's
number is, only that a solver produced it. `convergence_report` below is
the reporting half of closing that gap: given a sequence of results at
increasing refinement, it turns "did the answer stop moving" into a real
per-field error bar and verdict, exactly reproducing (mechanically, as
data) the finding `docs/meep-absorber-validation.md` recorded by hand:
"the absorbed total is converged, the split is not."

WHAT THIS MODULE IS *NOT*, DELIBERATELY (issue #540's own remaining,
BLOCKING step). This module is pure reporting logic -- given a sweep's
results, it reports on them. It does NOT run a sweep, drive a solver, or
attach an error bar to any `SIMULATED` result anywhere in this repo. The
prototype's own README states plainly why: whether this reporting logic
is trustworthy for a real solver still rests on the prototype's `--real`
path being run under an interpreter with Meep actually installed, to
check whether MEEP's real convergence behaviour resembles the synthetic
signature `--fake` was tested against -- and that has NEVER been done
(there is no Meep binary in this sandbox, nor in the environment the
prototype was originally written in). Wiring a per-field error bar onto a
real `SIMULATED` result before that check would be exactly the "confident
result nobody validated" failure mode this whole ticket exists to close,
so issue #540 STAYS OPEN after this module lands -- see that issue for
the named remaining step (run `prototype/mesh-convergence/
mesh_convergence_prototype.py --real` under a Meep-equipped interpreter,
then lift this logic's *use*, not just its code, into a real adapter).

THE THREE DESIGN DECISIONS THIS MODULE ENCODES (unchanged from the
prototype, reasoning restated here since the prototype itself is
throwaway and not meant to be read once this lands):

1. Per field, never one verdict for the whole solve -- different outputs
   of the same run converge at different rates, and a single scalar
   erases exactly the finding that matters (reflectance and transmittance
   individually unconverged while their difference, absorptance, already
   is).
2. The error bar is the LAST SUCCESSIVE DIFFERENCE, never a Richardson
   extrapolation. Extrapolating would buy a tighter bar only by assuming a
   convergence order, and a resistive sheet a few pixels thick with
   subpixel smoothing is exactly the case where that assumption is worth
   least -- refusing to assume over-states the uncertainty rather than
   under-stating it, the conservative direction to err in.
3. The refinement knob is left to the caller to define (the prototype's
   own choice was pixels across the thinnest feature, not raw grid
   resolution, because that is what a subpixel-smoothed thin sheet's
   accuracy actually tracks) -- this module only ever sees `(knob,
   {field: value})` pairs, never a resolution or a solver call itself.
"""

from __future__ import annotations

from typing import Any


def convergence_report(
    samples: list[tuple[float, dict[str, float]]],
    tolerance: float = 0.01,
) -> dict[str, Any]:
    """Turn a refinement sweep into a per-field error bar and verdict.

    `samples` is `[(knob, {field: value}), ...]` in INCREASING refinement
    order -- `knob` is whatever a caller refined (e.g. pixels across the
    thinnest feature); every `field` present in any sample's dict is
    reported on independently, `None` if fewer than two samples include
    it. At least two samples are required; three is the useful minimum, in
    that two give a movement with nothing to say whether it is shrinking.

    Returns:
        {
          "knob_values": the sorted knob values actually swept,
          "tolerance": as given,
          "per_field": {field: {
              "values": the field's own value at each sample carrying it,
              "successive_deltas": abs(value[i+1] - value[i]) for each step,
              "still_shrinking": True/False once >=2 deltas exist, else None,
              "error_bar": the LAST successive delta -- see module
                  docstring point 2 for why this, not an extrapolation,
              "converged": error_bar <= tolerance,
              "finest_value": the field's value at the finest sample,
          }, ...},
          "converged_fields": sorted field names that settled,
          "unconverged_fields": sorted field names still moving,
          "claim_limit": one plain-English sentence naming what may and
              may not be claimed from this sweep,
          "provenance_note": a fixed reminder that this measures
              discretisation error ONLY -- a converged wrong answer is
              still wrong; this checks neither the model nor the adapter.
        }

    Raises `ValueError` if fewer than two samples are given, or `samples`
    is not already in increasing knob order (a caller sorting order is not
    this function's job to infer or silently correct).
    """
    if len(samples) < 2:
        raise ValueError("need at least two refinement levels to see any movement")

    knobs = [k for k, _ in samples]
    if knobs != sorted(knobs):
        raise ValueError(f"samples must be in increasing refinement order, got {knobs}")

    per_field: dict[str, Any] = {}
    for field in {f for _, values in samples for f in values}:
        series = [values[field] for _, values in samples if field in values]
        if len(series) < 2:
            continue
        # strict=False is deliberate: series[1:] is one shorter by
        # construction -- that offset IS the pairwise walk.
        deltas = [abs(b - a) for a, b in zip(series, series[1:], strict=False)]
        error_bar = deltas[-1]
        per_field[field] = {
            "values": series,
            "successive_deltas": deltas,
            # Is the movement itself shrinking? Two samples can't say.
            "still_shrinking": None if len(deltas) < 2 else deltas[-1] < deltas[-2],
            "error_bar": error_bar,
            "converged": error_bar <= tolerance,
            "finest_value": series[-1],
        }

    converged = [f for f, r in per_field.items() if r["converged"]]
    unconverged = [f for f, r in per_field.items() if not r["converged"]]
    return {
        "knob_values": knobs,
        "tolerance": tolerance,
        "per_field": per_field,
        "converged_fields": sorted(converged),
        "unconverged_fields": sorted(unconverged),
        # The sentence a downstream consumer actually needs.
        "claim_limit": _claim_limit(per_field, tolerance),
        "provenance_note": (
            "This is an estimate of DISCRETISATION error only -- how much "
            "the answer still moves as the grid is refined. It says nothing "
            "about whether the model, the materials, or the adapter are "
            "right. A converged wrong answer is still wrong."
        ),
    }


def _claim_limit(per_field: dict[str, Any], tolerance: float) -> str:
    """One plain-English sentence naming what may and may not be claimed."""
    bad = sorted(f for f, r in per_field.items() if not r["converged"])
    if not bad:
        return (
            f"Every reported field moved by no more than {tolerance} across the "
            f"last refinement, so each may be quoted to about that precision."
        )
    parts = ", ".join(f"{f} (+/-{per_field[f]['error_bar']:.3f})" for f in bad)
    ok = sorted(f for f, r in per_field.items() if r["converged"])
    ok_text = f" {', '.join(ok)} did settle." if ok else ""
    return (
        f"Still moving at the finest grid run: {parts}. Do not quote these to "
        f"better than the stated figure, and do not build a downstream claim "
        f"(a return-loss or shielding number) on one of them alone.{ok_text}"
    )
