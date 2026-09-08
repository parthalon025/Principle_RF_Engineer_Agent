"""Drive the COMMITTED two-port path against an answer physics fixes at 0.5.

    MEEP_PYTHON=/opt/conda/envs/mp/bin/python3 uv run python -m \
        verification.meep_two_port_absorption_check

That invocation, and ONLY that one. Unlike
`verification/meep_absorber_validation.py`, this script cannot be run
directly under the conda interpreter that holds Meep: it imports the design
loop, which pulls in scikit-rf and the rest of the project's dependencies,
and that interpreter has none of them. Meep is reached the way the
application reaches it -- MEEP_PYTHON, and the adapter's subprocess handoff
-- which is the point, since driving the committed path is what this script
is for.

WHAT IS BEING CHECKED, AND AGAINST WHAT (issue #244). Five tickets built the
two-port absorber path: an adapter that measures transmitted power (#240), a
closed-form two-port model (#242), and a design loop that picks its
absorption sum from the family's declared port count (#243). Every check on
them so far compares this code against this code, or against a golden file
recorded from this code's own output. This one does not. A thin resistive
sheet hanging in free space absorbs **exactly one half** of the power that
hits it, at most, and does so when its sheet resistance is exactly
eta0/2 = 188.365 ohm/sq. That number is a closed-form maximum from network
theory; it was true before this repository existed and it does not move.

*In plain terms: a single grey film hanging in air can never swallow more
than half of what lands on it, whatever ink you print it with. So if our
machinery says otherwise, the machinery is wrong -- there is no arguing with
this particular answer.*

WHY THIS SHEET AND NOT AN ABSORBER. It is genuinely a two-port problem: a
quarter of the power comes back, a quarter carries straight on through, and
the remaining half is turned into heat. A ground-backed absorber cannot test
the two-port path at all, because its transmission is structurally zero and
`A = 1 - R - T` collapses into `A = 1 - R` whether the arithmetic is right or
not. Here the transmitted quarter is real, sizeable, and exactly known, so a
sum that ignores it is caught immediately.

HOW IT DIFFERS FROM ITS TWO NEIGHBOURS, which it replaces neither:

  * `verification/meep_absorber_validation.py` runs this same sheet, but
    builds `mp.Simulation` itself and re-derives the unit conversions, so
    that the physics check does not assume the adapter it is checking. That
    is the right choice there, and the cost is that the adapter and the loop
    are then untested on this problem.
  * `verification/meep_adapter_transmittance_check.py` drives the real
    adapter, on a conductive slab, and checks R and T against paper. It
    stops at the adapter: nothing in it scores an absorption.

This one goes the whole way: `orchestration/design_loop.py`'s SIMULATION
step, which calls `run_meep_simulation` and then picks the absorption sum
from `ABSORBER_TRANSMISSIVE`'s declared `port_count=2`. What is checked is
therefore the committed path a real design run takes, end to end, against a
number nothing here produced.

THREE THINGS IT REPORTS BEYOND PASS/FAIL:

  1. **What the one-port collapse would have said.** The same measured
     reflectance, scored by the ground-backed family's `A = 1 - R`. That is
     not a hypothetical: issue #216 found the two absorber shapes conflated
     in one design family, and this is the size of the error that
     conflation caused.
  2. **The closed-form two-port model beside the full-wave result**, term by
     term. Where they disagree the disagreement is printed, not smoothed.
  3. **Which of the three numbers is actually converged.** The absorbed
     total is; the reflected and transmitted shares separately are not, and
     saying so is more useful than a tolerance quietly wide enough to hide
     it.

Deliberately a script, not a pytest test: it needs a solver CI does not
have. `tests/test_simulator_reference_cases.py` covers the mechanics -- the
geometry, the scoring, the collapse arithmetic -- against no solver at all.
"""

from __future__ import annotations

import textwrap
from typing import Any

from designs.design_families import ABSORBER, ABSORBER_TRANSMISSIVE
from orchestration.design_loop import _simulate_meep_floquet
from rf_tools.transmissive_absorber import (
    GroundBackedModelMisappliedError,
    one_port_absorption,
    stack_response,
)
from simulation.base import SimulatorError
from verification.simulator_reference_cases import (
    FREE_SHEET_CHARACTERISTIC_LENGTH_M,
    MATCHED_SHEET_RESISTANCE_OHM_SQ,
    REFERENCE_CASES,
    check_reference_case,
)

CASE_ID = "free-standing-resistive-sheet-two-port-10ghz"

#: The closed-form model needs a cell period even for an unpatterned sheet.
#: With `gap_m=None` the sheet is continuous and the grid capacitance --
#: the stray coupling between neighbouring printed elements -- is switched
#: off entirely, so this length has no effect on the answer. It is passed
#: because the signature asks for it, not because it means anything here,
#: and that is worth saying: the patterned term is exactly the part these
#: uniform-sheet cases leave unvalidated.
UNPATTERNED_PERIOD_M = 3e-3


def closed_form_reading(
    frequency_hz: float,
    sheet_resistance_ohm_sq: float = MATCHED_SHEET_RESISTANCE_OHM_SQ,
) -> dict[str, float]:
    """The same bare sheet through `rf_tools/transmissive_absorber.py`.

    A single shunt resistance across free space, no slab behind it
    (`thickness_m=None`), free space as the load. At Rs = eta0/2 this must
    return R = T = 0.25 and A = 0.5 exactly -- the closed form has no mesh
    to be coarse, so anything else would be an arithmetic error in the
    model rather than a discretisation effect.
    """
    response = stack_response(
        frequency_hz=frequency_hz,
        eps_r=1.0,
        tan_delta=0.0,
        thickness_m=None,
        period_m=UNPATTERNED_PERIOD_M,
        gap_m=None,
        sheet_resistance_ohm_sq=sheet_resistance_ohm_sq,
        squares=1.0,
    )
    return {
        "reflectance": response["reflection"],
        "transmittance": response["transmission"],
        "absorptance": response["absorption"],
    }


def one_port_collapse(reflectance: list[float]) -> list[float]:
    """What the ground-backed sum makes of this run's reflectance.

    Deliberately the COMMITTED `one_port_absorption`, aimed at the real
    ground-backed `ABSORBER` family rather than at a stand-in written for
    this script -- because the mistake being measured is not an imaginary
    one. It is what happens when an unbacked surface is filed under the
    ground-backed family, which is precisely what issue #216 found.
    """
    return one_port_absorption(ABSORBER, reflectance)


def overstatement_factor(one_port: float, two_port: float) -> float:
    """How many times larger the collapsed number is than the true one.

    At the matched sheet this is fixed by the 25/25/50 power split and can
    be written down before the run: discarding the transmitted quarter turns
    a half into three quarters, so on the exact numbers the ratio is
    0.75/0.5 = 1.5. The measured value is 1.428 (0.7101 against 0.4971),
    below 1.5 because this mesh reflects slightly too much and a high R
    pulls 1 - R down faster than it pulls 1 - R - T down.

    It is NOT the factor of two "it double-counts the escaping power" would
    suggest. Half of what escapes this particular sheet escapes BACKWARDS,
    and the collapse already subtracts that.
    """
    return one_port / two_port


def guard_refuses_the_collapse_on_this_family() -> str:
    """Confirm `one_port_absorption` refuses the two-port family outright.

    The overstatement above is what the collapse WOULD say; this is the
    reason nobody can reach it by accident through the loop. Returns the
    refusal's own message so the run records what the guard actually says,
    and raises if there is no refusal at all -- a silently permissive guard
    is the failure worth catching here.
    """
    try:
        one_port_absorption(ABSORBER_TRANSMISSIVE, [0.25])
    except GroundBackedModelMisappliedError as exc:
        return str(exc)
    raise AssertionError(
        "one_port_absorption accepted ABSORBER_TRANSMISSIVE, which declares "
        "port_count=2. The refusal that keeps A = 1 - R away from an unbacked "
        "surface is not working -- see rf_tools/transmissive_absorber.py."
    )


def run_through_the_loop(case: Any) -> dict[str, Any]:
    """The reference case, posed to the design loop's SIMULATION step.

    `_simulate_meep_floquet` is private to the loop and imported anyway,
    on purpose: the public entry point needs a whole `DesignLoopState` with
    an ARCHITECTURE decision recorded, and building one here would put a
    scaffold of this script's own between the case and the code under test.
    The narrow import goes straight at the committed function that calls
    the adapter and then chooses the absorption sum -- which is the thing
    #244 exists to check.
    """
    _step, recorded, _provenance = _simulate_meep_floquet(
        ABSORBER_TRANSMISSIVE,
        {
            "geometry": case.geometry,
            "frequency_hz": case.frequency_hz,
            "characteristic_length_m": FREE_SHEET_CHARACTERISTIC_LENGTH_M,
            "nfreq": 1,
        },
    )
    return recorded


def _first(values: Any) -> float:
    return float(values[0])


def main() -> int:
    case = REFERENCE_CASES[CASE_ID]

    try:
        recorded = run_through_the_loop(case)
    except SimulatorError as exc:
        print(
            f"The run could not be made: {exc}\n\n"
            "If Meep is not importable, run this under an interpreter that has "
            "it -- this repo's Dockerfile puts it at "
            "/opt/conda/envs/mp/bin/python3, and MEEP_PYTHON points the "
            "adapter at it."
        )
        return 2

    measured = {
        "reflectance": _first(recorded["reflectance"]),
        "transmittance": _first(recorded["transmittance"]),
        "absorptance": _first(recorded["absorption"]),
    }
    closed = closed_form_reading(case.frequency_hz)
    collapsed = _first(one_port_collapse(recorded["reflectance"]))

    print("\n=== free-standing resistive sheet, through the loop's two-port path ===")
    print(f"  sheet          {MATCHED_SHEET_RESISTANCE_OHM_SQ:.3f} ohm/sq at 10 GHz")
    print(f"  family         {ABSORBER_TRANSMISSIVE.name} (port_count=2)")
    print(f"  sum used       {recorded['absorption_formula']}")
    print(f"  called         {recorded['function']} -> {recorded['simulator']}")
    print(f"  provenance     {recorded['provenance']}")

    print("\n  --- what the run measured, against the exact answer ---")
    print(f"  {'':<14}{'R':>10}{'T':>10}{'A':>10}")
    print(f"  {'exact':<14}{0.25:>10.4f}{0.25:>10.4f}{0.5:>10.4f}")
    print(
        f"  {'full wave':<14}{measured['reflectance']:>10.4f}"
        f"{measured['transmittance']:>10.4f}{measured['absorptance']:>10.4f}"
    )
    print(
        f"  {'delta':<14}{measured['reflectance'] - 0.25:>+10.4f}"
        f"{measured['transmittance'] - 0.25:>+10.4f}"
        f"{measured['absorptance'] - 0.5:>+10.4f}"
    )
    print(
        "\n  Read the deltas, not just the pass: the ABSORBED total is what is\n"
        "  converged here. The reflected and transmitted shares are each off by\n"
        "  well over ten percent, in OPPOSITE directions, so their errors very\n"
        "  nearly cancel in 1 - R - T. In plain terms, this grid counts how much\n"
        "  power vanished into the sheet accurately, and is much vaguer about\n"
        "  which side of the sheet the surviving power left by."
    )

    print("\n  --- closed form (rf_tools/transmissive_absorber.py) beside it ---")
    print(f"  {'':<14}{'R':>10}{'T':>10}{'A':>10}")
    print(
        f"  {'closed form':<14}{closed['reflectance']:>10.4f}"
        f"{closed['transmittance']:>10.4f}{closed['absorptance']:>10.4f}"
    )
    print(
        f"  {'disagreement':<14}{measured['reflectance'] - closed['reflectance']:>+10.4f}"
        f"{measured['transmittance'] - closed['transmittance']:>+10.4f}"
        f"{measured['absorptance'] - closed['absorptance']:>+10.4f}"
    )
    print(
        "\n  The closed form lands on the exact answer to every digit shown, so\n"
        "  the disagreement row above is the SAME discretisation delta again --\n"
        "  and that repetition is the finding, not a redundancy: every bit of\n"
        "  the gap between the two methods belongs to the mesh, and none of it\n"
        "  to the model. The closed form treats the sheet as having no\n"
        "  thickness at all; the grid gives it 0.1 mm across six pixels. That\n"
        "  is a real physical difference, not a rounding error, and it shows up\n"
        "  where you would expect -- in the split between bouncing back and\n"
        "  passing through, hardly at all in the total absorbed."
    )

    print("\n  --- the same run, scored by the one-port collapse A = 1 - R ---")
    print(f"  two-port   A = 1 - R - T = {measured['absorptance']:.4f}")
    print(f"  one-port   A = 1 - R     = {collapsed:.4f}")
    factor = overstatement_factor(collapsed, measured["absorptance"])
    print(f"  overstatement            {factor:.3f}x")
    print(
        "\n  NOT the factor of two a first guess suggests, and the difference is\n"
        "  structural rather than incidental. At the matched sheet the power\n"
        "  splits 25 / 25 / 50 -- a quarter back, a quarter through, a half into\n"
        "  heat -- so discarding the transmitted quarter inflates a half into\n"
        "  three quarters: 1.5 exactly, on the exact numbers. The measured 1.43\n"
        "  is lower only because this mesh reflects a little too much, and a\n"
        "  high R pulls 1 - R down faster than it pulls 1 - R - T down. What it\n"
        "  means for a reader is worse than the ratio sounds: it presents a\n"
        "  surface that passes a fifth of the arriving power straight through as\n"
        "  though it had absorbed seven tenths of it."
    )
    print("\n  The loop cannot reach that number by accident. The guard says:\n")
    print(
        textwrap.fill(
            guard_refuses_the_collapse_on_this_family(),
            width=76,
            initial_indent="    ",
            subsequent_indent="    ",
        )
    )

    problems = check_reference_case(case, recorded)
    print("\n  --- scored against the reference case ---")
    for expected in case.expected:
        failed = any(p.name == expected.name for p in problems)
        print(
            f"  {expected.name:<14}{expected.value:>7.4f} +/- {expected.tolerance:<6.3f}"
            f"{'FAIL' if failed else 'PASS'}"
        )
    for problem in problems:
        print(f"  ! {problem}")

    print(f"\n{'PASSED' if not problems else f'{len(problems)} QUANTITY(S) FAILED'}")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
