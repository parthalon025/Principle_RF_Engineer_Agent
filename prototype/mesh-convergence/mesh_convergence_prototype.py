#!/usr/bin/env python3
"""
THROWAWAY PROTOTYPE -- answers one design question about a resolution-
convergence sweep for simulation/meep.py. Nothing here is wired into the
production codebase and nothing here should be imported by it.

THE QUESTION
------------
    Does sweeping `resolution_px_per_a` through
    `verification.simulator_reference_cases.free_standing_sheet_geometry`
    and re-running the MEEP adapter produce a USABLE, MACHINE-READABLE
    error bar on a SIMULATED result -- and specifically, would it have
    found, on its own, what a human already found by hand and wrote into
    docs/meep-absorber-validation.md?

WHY THAT SECOND HALF IS THE REAL TEST. That document already records the
finding, in prose:

    "The absorbed total is converged. The split is not."
    "R is ~16 % high and T ~15 % low at this mesh. A = 1 - R - T is right
     to 0.003 because those errors point opposite ways and cancel."
    "Nothing here validates a reflectance or a transmittance on its own to
     better than about +/-0.06."

A person ran that study, drew the right conclusion, and wrote it where no
code can act on it. A downstream consumer scoring an absorptivity has no
way to learn that R and T separately carry +/-0.06. So the bar for this
prototype is not "can it print some numbers" -- it is "does it recover
that same finding mechanically, as data."

WHAT IS REAL HERE AND WHAT IS NOT
---------------------------------
- MEEP IS NOT INSTALLED in the environment this prototype was written in
  (no `import meep`, no conda). `--real` has therefore NEVER BEEN
  EXECUTED. It is written against `run_meep_simulation`'s documented call
  and result shape, read from simulation/meep.py, and should be treated as
  unproven until someone runs it under an interpreter that has Meep (see
  verification/meep_absorber_validation.py's own header for how that is
  done in this repo).
- `--fake` IS exercised, and is what this prototype's findings rest on. It
  substitutes a synthetic solver with a KNOWN, INVENTED convergence
  signature, chosen to mimic the documented one (R biased high, T biased
  low by a comparable amount, both first-order in pixels-across-the-sheet;
  A = 1 - R - T, so their errors cancel). Its numbers are ASSUMED, not
  CALCULATED or SIMULATED, and prove nothing about MEEP. What they DO test
  is whether the reporting logic below turns such a signature into the
  right verdict -- which is the design question actually being asked.

A CONFOUND IN THE EXISTING EVIDENCE, worth stating because it is why this
sweep is worth running at all. docs/meep-absorber-validation.md's two
absorptance numbers are NOT a clean resolution sweep:

    resolution 80 px/mm, sheet 0.2 mm -> 0.4999   (16 px across the sheet)
    resolution 60 px/mm, sheet 0.1 mm -> 0.4971   ( 6 px across the sheet)

Resolution AND sheet thickness both changed between them, so the pair
cannot separate "finer grid" from "thicker sheet" -- the doc attributes
the difference to discretisation of the sheet, which is consistent with
both. Holding thickness fixed and moving only the grid, which is what
`--real` below does, has not been run in this repo.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from typing import Any

from simulation.convergence import convergence_report

# The quantities a sweep reports on, per field. Deliberately three, not one:
# the whole documented finding is that they converge at different rates.
FIELDS = ("reflectance", "transmittance", "absorptance")

# The pure per-field convergence-analysis core this prototype's own spike
# was about now lives in simulation/convergence.py (issue #540) -- lifted
# verbatim from what was, until then, defined only here. Importing it back
# (rather than keeping a second, drifting copy in this throwaway script)
# means running this prototype's own `--real` path -- the still-blocking
# step named in that module's docstring -- validates the SHIPPED module,
# not a copy of it.


# ---------------------------------------------------------------------------
# DRIVERS
# ---------------------------------------------------------------------------
def fake_solver(pixels_across_sheet: float) -> dict[str, float]:
    """A synthetic solver whose convergence signature is INVENTED to mimic
    the one docs/meep-absorber-validation.md documents: reflectance biased
    high, transmittance biased low by a similar amount, both decaying only
    first-order in pixels-across-the-sheet, with absorptance taken as
    1 - R - T so the two biases cancel in it.

    Truth values are the closed-form ones for a matched free-standing
    sheet: R = T = 0.25, A = 0.5. Every number this returns is ASSUMED.
    """
    bias = 1.0 / pixels_across_sheet
    reflectance = 0.25 + 0.95 * bias
    transmittance = 0.25 - 0.90 * bias
    return {
        "reflectance": reflectance,
        "transmittance": transmittance,
        "absorptance": 1.0 - reflectance - transmittance,
    }


def real_solver_factory(sheet_thickness_m: float) -> Callable[[float], dict[str, float]]:
    """Build a driver that runs the COMMITTED MEEP adapter at a given
    pixels-across-the-sheet, holding sheet thickness fixed.

    NEVER EXECUTED -- see this module's header. Written against
    run_meep_simulation's documented shape in simulation/meep.py.
    """
    from simulation.meep import run_meep_simulation
    from verification.simulator_reference_cases import (
        FREE_SHEET_CHARACTERISTIC_LENGTH_M,
        free_standing_sheet_geometry,
    )

    def run(pixels_across_sheet: float) -> dict[str, float]:
        # pixels across the sheet = resolution (px per a) * thickness / a
        resolution = round(
            pixels_across_sheet * FREE_SHEET_CHARACTERISTIC_LENGTH_M / sheet_thickness_m
        )
        geometry = free_standing_sheet_geometry(
            sheet_thickness_m=sheet_thickness_m,
            resolution_px_per_a=resolution,
        )
        result = run_meep_simulation(
            geometry,
            characteristic_length_m=FREE_SHEET_CHARACTERISTIC_LENGTH_M,
        )
        s = result["s_parameters"]
        if not s.get("computed"):
            raise RuntimeError(
                f"reflectance not computed at resolution {resolution}: {s.get('note')}"
            )
        reflectance = abs(s["reflectance"][0])
        trans_block = s["transmittance"]
        if not trans_block.get("computed"):
            raise RuntimeError(f"transmittance not computed at resolution {resolution}")
        transmittance = abs(trans_block["transmittance"][0])
        return {
            "reflectance": reflectance,
            "transmittance": transmittance,
            "absorptance": 1.0 - reflectance - transmittance,
        }

    return run


def sweep(
    solver: Callable[[float], dict[str, float]], knobs: list[float]
) -> list[tuple[float, dict[str, float]]]:
    return [(k, solver(k)) for k in sorted(knobs)]


def render(report: dict[str, Any]) -> str:
    lines = [
        "",
        # simulation.convergence.convergence_report is solver-agnostic and
        # deliberately does not label the knob itself -- this script is the
        # one place that knows it swept pixels across the sheet.
        "  refinement knob : pixels_across_sheet",
        f"  levels run      : {report['knob_values']}",
        f"  tolerance       : {report['tolerance']}",
        "",
        f"  {'field':<16}{'finest':>10}{'last move':>12}{'still shrinking':>18}{'verdict':>12}",
        f"  {'-' * 68}",
    ]
    for field in FIELDS:
        r = report["per_field"].get(field)
        if r is None:
            continue
        shrinking = {True: "yes", False: "NO", None: "-"}[r["still_shrinking"]]
        verdict = "converged" if r["converged"] else "MOVING"
        lines.append(
            f"  {field:<16}{r['finest_value']:>10.4f}{r['error_bar']:>12.4f}"
            f"{shrinking:>18}{verdict:>12}"
        )
    lines += ["", "  " + report["claim_limit"], ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--real",
        action="store_true",
        help="drive the committed MEEP adapter (NEEDS MEEP; never executed -- see header)",
    )
    parser.add_argument("--sheet-thickness-m", type=float, default=0.1e-3)
    parser.add_argument(
        "--pixels",
        type=float,
        nargs="+",
        default=[6, 12, 24],
        help=(
            "pixels across the sheet, coarse to fine "
            "(default 6 12 24; 6 is what the committed runner uses)"
        ),
    )
    parser.add_argument("--tolerance", type=float, default=0.01)
    parser.add_argument("--json", action="store_true", help="emit the machine-readable report only")
    args = parser.parse_args()

    solver = real_solver_factory(args.sheet_thickness_m) if args.real else fake_solver
    report = convergence_report(sweep(solver, args.pixels), tolerance=args.tolerance)

    if args.json:
        print(json.dumps(report, indent=2))
        return

    print(__doc__.split("WHAT IS REAL HERE")[0].rstrip())
    print("=" * 72)
    print(
        "SOURCE:",
        "REAL MEEP RUN"
        if args.real
        else "FAKE SOLVER (invented signature -- ASSUMED, proves nothing about MEEP)",
    )
    print(render(report))
    print("  machine-readable report:")
    print("  " + json.dumps(report["per_field"], indent=2).replace("\n", "\n  "))


if __name__ == "__main__":
    main()
