"""ANALYSIS-step dispatch for the design loop (issue #511, split out of
`orchestration/design_loop.py` per issue #498).

This is a pure move: `_handle_analysis`, its three per-model handlers
(`_handle_analysis_absorber`, `_handle_analysis_transmissive_absorber`,
`_handle_analysis_patch`), and the `_ANALYSIS_MODELS` dispatch table they
share moved here unchanged -- no function signature, dispatch logic, or
table contents changed as part of the split. `orchestration/design_loop.py`
imports this module and wires `_handle_analysis` into its own
`_STEP_HANDLERS` table, exactly the way it already did before the names
lived here (re-exported from `orchestration.design_loop` so nothing that
already imported them from there needs to change).

Deliberately imports its shared kernel (`_registry_family_of_record`,
`_require_fields`, `_resolve_eps_r_bounds`, `DesignLoopValidationError`,
`DesignLoopState`) FROM `orchestration.design_loop` rather than the other
way around -- those stay the state machine's own concern (issue #498's
"Implementation Decisions": the ledger/validation helpers and the family-of-
record lookup are not one of the four cited reasons to change, and this
ticket does not relocate them). `design_loop.py`, in turn, imports the names
this module defines back out of it to populate its own `_STEP_HANDLERS`
table -- a genuine two-way dependency between the two modules. The imports
FROM `.design_loop` below are therefore done lazily, inside each function
that needs them, rather than at this module's top level: a top-level
`from .design_loop import ...` here would deadlock against `design_loop.py`'s
own top-level import of this module whichever module a caller happened to
import first (the one imported first would still be mid-execution, with the
name the other side wants not yet bound, when the cycle closes). Deferring
these lookups to call time sidesteps the ordering question entirely --
by the time any handler here actually RUNS, both modules have finished
importing, in either order.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from designs.design_families import (
    UndeclaredAnalysisModelError as _UndeclaredAnalysisModelError,
)
from rf_tools.absorber import absorber_band_response as _absorber_band_response
from rf_tools.patch_synthesis import patch_resonant_frequency_hz as _patch_resonant_frequency_hz
from rf_tools.transmissive_absorber import (
    refuse_ground_backed_model as _refuse_ground_backed_model,
)
from rf_tools.transmissive_absorber import (
    transmissive_absorber_band_response as _transmissive_absorber_band_response,
)

if TYPE_CHECKING:
    # Type-only -- see the module docstring for why the runtime names this
    # module needs from `.design_loop` are imported lazily instead, inside
    # each function that uses them.
    from .design_loop import DesignLoopState


def _handle_analysis(
    state: DesignLoopState, step_input: dict[str, Any]
) -> tuple[str, dict[str, Any], str | None]:
    """Run the analysis the design family DECLARES (issue #239).

    Issue #191 first split this step in two, but it chose between the halves
    by comparing the family's NAME against the single string "ABSORBER":
    everything else got the patch-antenna resonant-frequency formula,
    whether or not it was a patch antenna. That is how ABSORBER_TRANSMISSIVE
    (#216) came to be analysed as a transmitting antenna the moment it was
    created -- its name simply is not the word "ABSORBER". In plain terms:
    the loop was reading the label on the box to decide which instrument to
    reach for.

    It now reads `analysis_model` off the registry entry
    (`designs/design_families.py`) and looks that name up in
    `_ANALYSIS_MODELS` below. ABSORBER and PATCH declare exactly the models
    they already ran, so both return identical results to before.

    A family that declares no model raises here rather than borrowing
    another family's. That is deliberate and is NOT the charter's "warn,
    never block" being broken -- that rule governs withholding a candidate
    design from a reader, and nothing is withheld here. What is refused is
    manufacturing a number the programme cannot stand behind: an analysis
    that answers a question about a different device produces a confidently
    wrong number, not an uncertain one, and no warning attached to it would
    tell a reader which it was.
    """
    from .design_loop import DesignLoopValidationError, _registry_family_of_record

    family = _registry_family_of_record(state, "analysis")
    try:
        model = family.declared_analysis_model()
    except _UndeclaredAnalysisModelError as exc:
        # Re-raised as this loop's own error type, message intact, the same
        # way _handle_architecture re-raises UnknownDesignFamilyError: a
        # caller of advance_loop_step should not have to know the registry's
        # exception vocabulary to learn that a step could not run. The
        # registry error stays attached as __cause__ for anyone who does.
        raise DesignLoopValidationError(str(exc)) from exc
    handler = _ANALYSIS_MODELS.get(model.name)
    if handler is None:
        raise DesignLoopValidationError(
            f"Design family {family.name!r} declares analysis_model "
            f"{model.name!r} ({model.function}), and this loop has no handler "
            "wired for it. Add one to _ANALYSIS_MODELS in "
            "orchestration/design_loop_analysis.py, or correct the declaration "
            "in designs/design_families.py -- running a different family's "
            "model instead is the exact defect issue #239 removed."
        )
    return handler(family, step_input)


def _handle_analysis_absorber(
    family: Any,
    step_input: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    """Worst-in-band absorption for a ground-backed printed absorber.

    Scored on the single worst-absorbing frequency in the required band
    (#110's minimax rule), never the mean or the peak. The result carries
    a `validity` list naming each load-bearing assumption -- notably the
    unrecovered thin-spacer term (#190) -- and never withholds a number
    for one: the loop reports and proceeds.

    Refuses a transmissive stack before computing anything (#242). This
    model's whole legitimacy is that a ground plane guarantees nothing gets
    through, so every watt not reflected became heat; applied to a surface
    with free space behind it, it would credit as absorbed the power that
    simply escaped out the back. The guard is defined beside the two-port
    model it points at, and reads what the family DECLARES -- its
    `requires_ground_plane` and `port_count` -- rather than its name.
    """
    from .design_loop import _require_fields, _resolve_eps_r_bounds

    _refuse_ground_backed_model(family)
    _require_fields(
        step_input,
        {
            "f_low_hz",
            "f_high_hz",
            "tan_delta",
            "thickness_m",
            "period_m",
            "gap_m",
            "sheet_resistance_ohm_sq",
            "squares",
        },
        "analysis",
    )
    eps_r_low, eps_r_high, material_property = _resolve_eps_r_bounds(step_input, "analysis")

    def response(eps_r: float) -> dict[str, Any]:
        return _absorber_band_response(
            f_low_hz=step_input["f_low_hz"],
            f_high_hz=step_input["f_high_hz"],
            eps_r=eps_r,
            tan_delta=step_input["tan_delta"],
            thickness_m=step_input["thickness_m"],
            period_m=step_input["period_m"],
            gap_m=step_input["gap_m"],
            sheet_resistance_ohm_sq=step_input["sheet_resistance_ohm_sq"],
            squares=step_input["squares"],
        )

    at_low = response(eps_r_low)
    if eps_r_high == eps_r_low:
        result = dict(at_low)
    else:
        # A bracketed permittivity (ADR-0015's Family fallback bracket)
        # gives a RANGE of worst-case absorption, not one false-precise
        # number -- #127's rule: a guess on a decisive property swings the
        # answer widely, and that swing IS the warning.
        at_high = response(eps_r_high)
        result = dict(at_low)
        result["worst_absorption_low"] = min(
            at_low["worst_absorption"], at_high["worst_absorption"]
        )
        result["worst_absorption_high"] = max(
            at_low["worst_absorption"], at_high["worst_absorption"]
        )
        # Both endpoints' warnings apply; neither is discarded.
        seen = {v["flag"] for v in result["validity"]}
        result["validity"] = list(result["validity"]) + [
            v for v in at_high["validity"] if v["flag"] not in seen
        ]
    if material_property is not None:
        result["material_property"] = material_property
    return "calculation", result, "CALCULATED"


def _handle_analysis_transmissive_absorber(
    family: Any,
    step_input: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    """Worst-in-band absorption for an UNBACKED, TWO-PORT surface (#242).

    Same minimax rule as the ground-backed handler above -- the single
    worst-absorbing frequency in the band, never the mean and never the peak
    (#110) -- and the same bracketed-permittivity treatment (ADR-0015/#127: a
    guess on a decisive property yields a RANGE, and the swing IS the
    warning).

    What differs is the sum. This family has no metal behind it, so power can
    leave out the back, and absorption is what is left after BOTH the
    reflected and the transmitted share: A = 1 - |S11|^2 - |S21|^2
    (docs/absorber-scoring-conventions.md section 1). The transmitted
    fraction rides along in the result rather than being folded away, because
    for this family it is a different decision: "44 % absorbed" and "44 %
    absorbed, 44 % straight through the part" are not the same answer to
    someone who has to know whether whatever sits behind the surface will
    hear it.

    The family's physical bound rides along as UNREAD rather than absent, and
    the Rozanov bound is never quoted here: its own opening line fixes a slab
    over a perfectly reflecting plane, which this family has not got.
    """
    from .design_loop import _require_fields, _resolve_eps_r_bounds

    del family  # the model needs no family fact; the signature is the dispatch's
    _require_fields(
        step_input,
        {
            "f_low_hz",
            "f_high_hz",
            "tan_delta",
            "thickness_m",
            "period_m",
            "gap_m",
            "sheet_resistance_ohm_sq",
            "squares",
        },
        "analysis",
    )
    eps_r_low, eps_r_high, material_property = _resolve_eps_r_bounds(step_input, "analysis")

    def response(eps_r: float) -> dict[str, Any]:
        return _transmissive_absorber_band_response(
            f_low_hz=step_input["f_low_hz"],
            f_high_hz=step_input["f_high_hz"],
            eps_r=eps_r,
            tan_delta=step_input["tan_delta"],
            thickness_m=step_input["thickness_m"],
            period_m=step_input["period_m"],
            gap_m=step_input["gap_m"],
            sheet_resistance_ohm_sq=step_input["sheet_resistance_ohm_sq"],
            squares=step_input["squares"],
        )

    at_low = response(eps_r_low)
    if eps_r_high == eps_r_low:
        result = dict(at_low)
    else:
        at_high = response(eps_r_high)
        result = dict(at_low)
        result["worst_absorption_low"] = min(
            at_low["worst_absorption"], at_high["worst_absorption"]
        )
        result["worst_absorption_high"] = max(
            at_low["worst_absorption"], at_high["worst_absorption"]
        )
        # Both endpoints' warnings apply; neither is discarded.
        seen = {v["flag"] for v in result["validity"]}
        result["validity"] = list(result["validity"]) + [
            v for v in at_high["validity"] if v["flag"] not in seen
        ]
    if material_property is not None:
        result["material_property"] = material_property
    return "calculation", result, "CALCULATED"


def _handle_analysis_patch(
    family: Any,
    step_input: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    from .design_loop import _require_fields, _resolve_eps_r_bounds

    del family  # a patch resonance needs no family fact; the signature is uniform
    _require_fields(step_input, {"w_m", "h_m", "l_m"}, "analysis")
    eps_r_low, eps_r_high, material_property = _resolve_eps_r_bounds(step_input, "analysis")

    frequency_at_low = _patch_resonant_frequency_hz(
        eps_r_low, step_input["w_m"], step_input["h_m"], step_input["l_m"]
    )
    if eps_r_high == eps_r_low:
        result = {
            "function": "patch_resonant_frequency_hz",
            "resonant_frequency_hz": frequency_at_low,
            "provenance": "CALCULATED",
        }
    else:
        frequency_at_high = _patch_resonant_frequency_hz(
            eps_r_high, step_input["w_m"], step_input["h_m"], step_input["l_m"]
        )
        # Higher eps_r lowers the resonant frequency (f ~ 1/sqrt(eps_r)), so
        # eps_r_low's frequency is the HIGHER of the two -- min/max over the
        # actual results, never assumed from the eps_r ordering.
        result = {
            "function": "patch_resonant_frequency_hz",
            "resonant_frequency_hz_low": min(frequency_at_low, frequency_at_high),
            "resonant_frequency_hz_high": max(frequency_at_low, frequency_at_high),
            "provenance": "CALCULATED",
        }
    if material_property is not None:
        result["material_property"] = material_property
    return "calculation", result, "CALCULATED"


# The dispatch table `_handle_analysis` reads. One named calculation per
# declared model name -- never an arbitrary callable crossing the tool
# boundary, the same reasoning optimization/rf_objectives.py gives for wiring
# one named objective. A family declaring a name that is not a key here is a
# reported failure, not a fallback.
_ANALYSIS_MODELS: dict[str, Any] = {
    "ABSORBER_BAND_RESPONSE": _handle_analysis_absorber,
    "TRANSMISSIVE_ABSORBER_BAND_RESPONSE": _handle_analysis_transmissive_absorber,
    "PATCH_RESONANT_FREQUENCY": _handle_analysis_patch,
}
