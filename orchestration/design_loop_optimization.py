"""OPTIMIZATION-step dispatch for the design loop (issue #519, split out of
`orchestration/design_loop.py` per issue #498 -- the last of the three
dispatch-axis extractions, after ANALYSIS (#511) and SIMULATION (#516)).

This is a pure move: `_handle_optimization`, its two search handlers
(`_optimize_continuous_patch_length`, `_optimize_combinatorial_symbol_
placement`), the supporting helpers the combinatorial path needs
(`_combinatorial_candidate_options`, `_combinatorial_result_to_dict`), the
family-declaration reader (`_optimizer_class_for`), and the `_OPTIMIZER_
HANDLERS` dispatch table they share, all moved here unchanged -- no function
signature, dispatch logic, or table contents changed as part of the split.
`orchestration/design_loop.py` imports this module and wires
`_handle_optimization` into its own `_STEP_HANDLERS` table, exactly the way
it already did before the names lived here (re-exported from
`orchestration.design_loop` so nothing that already imported them from there
needs to change -- `tests/test_design_loop.py` imports `_combinatorial_
result_to_dict` and `_optimizer_class_for` directly from there).

Deliberately imports its shared kernel (`_registry_family_of_record`,
`_require_fields`, `DesignLoopValidationError`, `DesignLoopState`,
`OPTIMIZE_CONTINUOUS_PATCH_LENGTH_REQUIRED_FIELDS`) FROM `orchestration.
design_loop` rather than the other way around -- those stay the state
machine's own concern (issue #498's "Implementation Decisions": the
ledger/validation helpers and the family-of-record lookup are not one of the
four cited reasons to change, and this ticket does not relocate them).
`OPTIMIZE_CONTINUOUS_PATCH_LENGTH_REQUIRED_FIELDS` in particular is the named
constant issue #510 already added to `design_loop.py` so `orchestration/
solver.py` could import it instead of restating the field set as its own
literal; `_optimize_continuous_patch_length` below references that same
constant rather than re-inlining it, and it still lives in `design_loop.py`
-- moving the handler here does not move the constant, since `solver.py`'s
own `from .design_loop import OPTIMIZE_CONTINUOUS_PATCH_LENGTH_REQUIRED_
FIELDS` must keep resolving unchanged.
`design_loop.py`, in turn, imports the names this module defines back out of
it to populate its own `_STEP_HANDLERS` table -- a genuine two-way
dependency between the two modules. The imports FROM `.design_loop` below
are therefore done lazily, inside each function that needs them, rather than
at this module's top level: a top-level `from .design_loop import ...` here
would deadlock against `design_loop.py`'s own top-level import of this
module whichever module a caller happened to import first (the one imported
first would still be mid-execution, with the name the other side wants not
yet bound, when the cycle closes). Deferring these lookups to call time
sidesteps the ordering question entirely -- by the time any handler here
actually RUNS, both modules have finished importing, in either order.

`_optimize_patch_length_for_target_frequency` and `_combinatorial_symbol_
placement` are ALSO looked up lazily from `.design_loop` -- inside
`_optimize_continuous_patch_length`/`_optimize_combinatorial_symbol_
placement` respectively -- even though importing them directly from
`optimization.rf_objectives`/`optimization.combinatorial` at this module's
top level would not create the cycle above. The reason is `tests/
test_design_loop.py`'s own fixtures, unchanged by this split: they fake a
search with `monkeypatch.setattr(design_loop_module,
"_optimize_patch_length_for_target_frequency", fake_optimize)` and
`monkeypatch.setattr(design_loop_module, "_combinatorial_symbol_placement",
exploding_search)` -- i.e. they patch the name on `orchestration.design_
loop`, not here. A direct top-level import here would bind this module's OWN
copy of the name at import time, and the handler would keep calling that
copy forever after -- the monkeypatch would silently stop intercepting
anything. Reading the name back off `.design_loop` at call time, the same
way `_require_fields`/`DesignLoopValidationError` already are, means each
call sees whatever `design_loop.py` currently has bound to that name --
patched or not -- so the existing fixtures keep working unchanged.
`design_loop.py` keeps its own top-level import of these two names for
exactly this reason (see its own comment there), even though nothing in
that module calls them directly any more. `_EmptyCandidateShelfError` stays
imported at `design_loop.py`'s top level for the identical reason:
`tests/test_design_loop.py` constructs one directly as `design_loop_
module._EmptyCandidateShelfError(...)`, so `design_loop.py` must keep the
name bound as its own module attribute even though only this module's
`except` clause below reads it (looked up lazily, same as the others).

`_lookup_symbol_entries`, `_reduce_response_at_frequency` (`designs.element_
alphabet`) and `SymbolOption` (`optimization.combinatorial`) are, by
contrast, imported directly at THIS module's top level rather than lazily
from `.design_loop`: nothing outside this module -- no test, no other
caller -- reaches any of the three off `orchestration.design_loop`, so there
is no monkeypatch-interception contract to preserve for them, and no reverse-
dependency cycle to avoid (they come from `designs`/`optimization`, not from
`design_loop.py` itself).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from designs.element_alphabet import lookup_symbol_entries as _lookup_symbol_entries
from designs.element_alphabet import (
    reduce_response_at_frequency as _reduce_response_at_frequency,
)
from optimization.combinatorial import SymbolOption as _SymbolOption

if TYPE_CHECKING:
    # Type-only -- see the module docstring for why the runtime names this
    # module needs from `.design_loop` are imported lazily instead, inside
    # each function that uses them.
    from .design_loop import DesignLoopState


def _optimizer_class_for(state: DesignLoopState) -> str | None:
    """The `optimizer_class` (`designs/design_families.py`) this iteration's
    ARCHITECTURE-recorded family declares -- issue #255 ticket 1.

    Mirrors `_simulation_adapter_for`: it reads the SAME family-lookup seam
    `_handle_analysis` (#239) and `_handle_simulation` (#229) already use
    (`_registry_family_of_record`) to resolve which family this iteration's
    step belongs to, off the recorded ARCHITECTURE decision -- never a
    second, parallel lookup, and never a hardcoded family-name list (issue
    #255's own user story 3/17: dispatch must key off the family's declared
    field).

    Unlike `_simulation_adapter_for`, this never raises for an UNSET value.
    `optimizer_class` is an open, optional field (ADR-0018) -- `None` is
    what every family in this tree declares today (nothing has opted into
    `COMBINATORIAL` yet) and is itself a legitimate, un-raising answer
    ("this family's OPTIMIZATION step is the plain continuous search"), not
    a missing-declaration error the way an unsettled `simulation_adapter`
    is. Only "there is no ARCHITECTURE decision to read a family off at
    all" raises here, via `_registry_family_of_record`.
    """
    from .design_loop import _registry_family_of_record

    return _registry_family_of_record(state, "optimization").optimizer_class


def _optimize_continuous_patch_length(
    _family: Any, step_input: dict[str, Any]
) -> tuple[str, dict[str, Any], str | None]:
    """The plain continuous patch-length search (issue #255 ticket 1) --
    this loop's ONLY OPTIMIZATION path until issue #267 added
    `_optimize_combinatorial_symbol_placement` beside it. Handles
    `optimizer_class == "CONTINUOUS"` and, via `_OPTIMIZER_HANDLERS`'s
    lookup key below, the unset (`None`) case too -- see `_handle_
    optimization`'s docstring for why both route here identically.

    `_family` is unused: this search has never needed anything off the
    registry entry, unlike its COMBINATORIAL sibling (which needs the
    family's name for its own error messages). It is still accepted, not
    dropped, so both entries in `_OPTIMIZER_HANDLERS` share one call
    signature `(family, step_input)` -- the same uniform-signature
    discipline `_ANALYSIS_MODELS`/`_SIMULATION_ADAPTERS`'s handlers already
    follow.
    """
    from .design_loop import (
        OPTIMIZE_CONTINUOUS_PATCH_LENGTH_REQUIRED_FIELDS,
        _optimize_patch_length_for_target_frequency,
        _require_fields,
    )

    _require_fields(step_input, OPTIMIZE_CONTINUOUS_PATCH_LENGTH_REQUIRED_FIELDS, "optimization")
    result = _optimize_patch_length_for_target_frequency(
        eps_r=step_input["eps_r"],
        w_m=step_input["w_m"],
        h_m=step_input["h_m"],
        target_frequency_hz=step_input["target_frequency_hz"],
        length_lower_m=step_input["length_lower_m"],
        length_upper_m=step_input["length_upper_m"],
        method=step_input.get("method", "bayesian"),
        n_evaluations=step_input.get("n_evaluations", 20),
    )
    return "optimization", result, result.get("provenance", "CALCULATED")


def _handle_optimization(
    state: DesignLoopState, step_input: dict[str, Any]
) -> tuple[str, dict[str, Any], str | None]:
    """Dispatch OPTIMIZATION to the search this design family's declared
    `optimizer_class` calls for (issue #255 ticket 1; wired up to a real
    `COMBINATORIAL` search at issue #267; converted to the same dict-
    dispatch pattern as `_handle_analysis`/`_handle_simulation` at issue
    #508 -- this docstring claimed that pattern from issue #255 onward, but
    the code underneath it was actually a chain of `if/elif optimizer_class
    == ... / raise` checks with no table a reader (or the error message
    below) could point at).

    `optimizer_class == "CONTINUOUS"`, and a family that declares no
    optimizer_class at all (`None` -- every family in `designs/
    design_families.py` except REFLECTION_PHASE/DIFFUSIVE; ADR-0018 leaves
    the field open until a family opts in), both route to the SAME
    patch-length search this step has always run, byte-for-byte unchanged:
    same required fields, same call, same result shape (issue #255 ticket
    1's own acceptance criterion, re-confirmed unchanged by issues #267 and
    #508). The `None` case is folded into the `"CONTINUOUS"` lookup key
    right here, before `_OPTIMIZER_HANDLERS` is consulted, rather than
    given its own dict entry -- `None` is not itself an `optimizer_class`
    value a family could declare a handler for, it is the ABSENCE of one.

    `optimizer_class == "COMBINATORIAL"` -- the shape issue #109/CONTEXT.md
    give REFLECTION_PHASE and DIFFUSIVE's Tier B optimizer, a genetic-
    algorithm search over a pre-characterized symbol alphabet -- routes to
    `_optimize_combinatorial_symbol_placement` (issue #267), which resolves
    real candidate symbols from the Element/Coding-Alphabet library (issue
    #256) and hands them to `optimization.combinatorial.
    combinatorial_symbol_placement` (issue #255 ticket 2). See that
    function's own docstring for the full shape of this branch, including
    why a family with nothing characterised yet still fails loudly here
    rather than falling through to the continuous search.

    Any OTHER declared value (a hypothetical third `optimizer_class`, e.g.
    ML-direct inverse design -- ADR-0018 names this as a credible future
    value) is not a key in `_OPTIMIZER_HANDLERS`, so `.get` returns `None`
    and the block below raises, naming the family and the unhandled value
    -- per issue #255's user story 4, reported by name, never guessed past,
    in the exact wording style `_handle_analysis`'s own "no handler wired"
    raise uses for `_ANALYSIS_MODELS`.
    """
    from .design_loop import DesignLoopValidationError, _registry_family_of_record

    optimizer_class = _optimizer_class_for(state)
    if optimizer_class is None:
        optimizer_class = "CONTINUOUS"
    family = _registry_family_of_record(state, "optimization")
    handler = _OPTIMIZER_HANDLERS.get(optimizer_class)
    if handler is None:
        raise DesignLoopValidationError(
            f"Design family {family.name!r} declares optimizer_class "
            f"{optimizer_class!r}, and this loop has no handler wired for it. "
            "Add one to _OPTIMIZER_HANDLERS in orchestration/design_loop.py, "
            "or correct the declaration in designs/design_families.py -- "
            "silently falling through to the patch-length search is exactly "
            "what issues #239/#241 already removed for ANALYSIS/SIMULATION."
        )
    return handler(family, step_input)


def _combinatorial_candidate_options(
    symbol_entries: list[dict[str, Any]],
    element_family: str,
    frequency_hz: float,
    incidence_angle_deg: float,
    process_id: int,
    response_field: str,
) -> list[_SymbolOption]:
    """Resolve the ONE shared set of candidate symbols a COMBINATORIAL
    OPTIMIZATION step searches over, from an already-fetched
    `designs.element_alphabet.fetch_symbol_entries` result (issue #267
    design decision 2).

    `symbol_entries` is whatever the caller already fetched for
    `element_family` -- this function, like `designs.element_alphabet.
    lookup_symbol_entries` it calls, never touches a database itself (see
    `_optimize_combinatorial_symbol_placement`'s own docstring for why).

    HOW CANDIDATES ARE FOUND: every DISTINCT `symbol` name present in
    `symbol_entries` is checked, via `lookup_symbol_entries`, against the
    single shared `(frequency_hz, incidence_angle_deg, process_id)` point
    query -- reusing that function's own public match logic rather than
    reaching into its private `_symbol_entry_matches` helper (a module
    should not depend on another module's underscore-prefixed internals;
    `lookup_symbol_entries` is the supported seam for exactly this "does a
    stored entry match this point" question). ALL matching entries for a
    symbol are kept, not just the first: `resolve_symbol_entry`'s own
    docstring is explicit that "picking the best of several [simultaneously
    matching] candidates is the combinatorial optimizer's job" -- this is
    that job, so an ambiguous symbol (e.g. two runs whose declared bands
    happen to overlap the query point) contributes one `SymbolOption` per
    matching entry, and the search decides which one, if any, belongs in
    the winning layout.

    Returns a plain list, empty if nothing matches -- the caller checks for
    that and raises a named error before ever reaching
    `combinatorial_symbol_placement` (design decision 4a).
    """
    distinct_symbols = sorted({entry["symbol"] for entry in symbol_entries})
    options: list[_SymbolOption] = []
    for symbol in distinct_symbols:
        matches = _lookup_symbol_entries(
            symbol_entries,
            element_family,
            symbol,
            frequency_hz,
            incidence_angle_deg,
            process_id,
        )
        for entry in matches:
            achieved_value = _reduce_response_at_frequency(
                entry["response"], frequency_hz, response_field
            )
            # entry_id (issue #400): the matched row's own `id`, when it has
            # one -- a REAL `designs.element_alphabet.fetch_symbol_entries`
            # row always does (it's the table's own `BIGSERIAL PRIMARY
            # KEY`, via `SELECT *`). `.get`, not `entry["id"]`: a hand-built
            # fixture entry (a test's own `symbol_entries`, standing in for
            # the not-yet-existing Element/Coding-Alphabet library
            # lookup -- see this function's own docstring) may omit `id`
            # entirely, and `None` here is the honest "not resolved against
            # a real row" reading `SymbolOption.entry_id`'s own docstring
            # already documents, not a reason to raise on a well-formed but
            # id-less caller-supplied entry.
            options.append(
                _SymbolOption(
                    symbol_id=symbol, achieved_value=achieved_value, entry_id=entry.get("id")
                )
            )
    return options


def _combinatorial_result_to_dict(result: Any) -> dict[str, Any]:
    """`optimization.combinatorial.CombinatorialPlacementResult` -> a flat,
    JSON-friendly dict -- the same "flat dict, JSON-friendly for the
    MCP/agent tool boundary" convention `optimization.rf_objectives.
    optimize_patch_length_for_target_frequency`'s own docstring states for
    the continuous path's result, applied here so `LoopDecision.result`
    (this module's docstring's "STATE DESIGN" section: `DesignLoopState`
    is a plain, JSON-serializable dataclass) can hold this step's result
    exactly the way it holds every other step's.

    `combinatorial_symbol_placement`'s own return value is deliberately
    NOT already this shape -- it stays generic/reusable there (a `Position`
    `(i, j)` TUPLE key and `SymbolOption` dataclass values in
    `candidate_snapshot`, neither of which is valid JSON), and this
    dispatch site is what owns converting it, the same "generic function,
    JSON conversion at the tool boundary" split `rf_objectives` already
    draws for its own result.
    """
    candidate_snapshot = [
        {
            "i": i,
            "j": j,
            "candidates": [
                {
                    "symbol_id": option.symbol_id,
                    "achieved_value": option.achieved_value,
                    # entry_id (issue #400): the matched symbol_alphabet_
                    # entries.id this option resolved from, so a candidate
                    # that was AVAILABLE at (i, j) but not chosen is still
                    # traceable to its own measured row, not just the
                    # winning cell's own entry_id_layout entry below.
                    "entry_id": option.entry_id,
                }
                for option in options
            ],
        }
        # Row-major, j-outer/i-inner -- the SAME grid-walk order
        # optimization.combinatorial's own `positions = [(i, j) for j in
        # range(n_rows) for i in range(n_cols)]` and `_grid_from_choices`'s
        # `layout[j][i]` already use, so this debug/audit snapshot's order
        # agrees with every other grid walk this feature touches (each
        # entry is still self-describing via its own "i"/"j" fields either
        # way, but there is no reason for this one list to be the odd one
        # out).
        for (i, j), options in sorted(
            result.candidate_snapshot.items(), key=lambda kv: (kv[0][1], kv[0][0])
        )
    ]
    return {
        # Which search actually ran, stated the same way every other
        # family-dispatched step states it (issue #334), so
        # `orchestration/tooling.py`'s flush files this row under the
        # combinatorial search rather than under the continuous patch-length
        # one this family never touched. `method` happens to carry the same
        # string here, but it is not the same fact: on the CONTINUOUS path
        # `method` is the search algorithm ("parameter_sweep"/
        # "bayesian_optimize"), so a reader cannot use it as a tool name.
        "function": "combinatorial_symbol_placement",
        "method": result.method,
        "layout": result.layout,
        # entry_id_layout (issue #400): the SAME [j][i] shape as "layout"
        # above, naming which measured symbol_alphabet_entries row -- and
        # therefore which process/machine/ink -- backed the WINNING choice
        # at each cell. A bare symbol_id in "layout" cannot answer that on
        # its own: several entries can share one symbol/band/incidence-
        # angle-range/process (ADR-0027 point 4's "two runs are still two
        # distinct rows" rule).
        "entry_id_layout": result.entry_id_layout,
        "achieved_error": result.achieved_error,
        "evaluations": result.evaluations,
        "target": result.target,
        "candidate_snapshot": candidate_snapshot,
        "delta_phi_max_deg": result.delta_phi_max_deg,
        "random_seed": result.random_seed,
        "warnings": result.warnings,
        "objective_name": result.objective_name,
        "provenance": result.provenance,
    }


def _optimize_combinatorial_symbol_placement(
    family: Any,
    step_input: dict[str, Any],
) -> tuple[str, dict[str, Any], str | None]:
    """The COMBINATORIAL OPTIMIZATION path for REFLECTION_PHASE/DIFFUSIVE
    (issue #267): resolve real candidate symbols from the Element/
    Coding-Alphabet library (issue #256) and hand them to `optimization.
    combinatorial.combinatorial_symbol_placement` (issue #255 ticket 2) --
    replacing `_handle_optimization`'s former "not wired yet" raise (ticket
    1's interim safety net).

    step_input FIELDS, AND WHY (design decision 1). Required:
    `element_family`, `symbol_entries` (a list already fetched via
    `designs.element_alphabet.fetch_symbol_entries` -- this module never
    opens a database connection itself; `_resolve_eps_r_bounds`'s own "the
    design loop stays the DB-free, pure state machine" rule applies here
    identically -- the caller resolves the library lookup, this handler
    only filters/reduces the plain list it was handed), `frequency_hz`,
    `incidence_angle_deg`, `process_id` (the SAME three names
    `designs.element_alphabet.lookup_symbol_entries` itself uses -- the
    path of least translation for a caller who already has that function's
    signature in front of it), `target` (matching
    `combinatorial_symbol_placement`'s own parameter name and
    `target[j][i]` shape), and `delta_phi_max_deg` (ditto). Optional,
    forwarded unchanged when given: `random_seed`, `max_generations`,
    `population_size`, `objective_name` --
    `combinatorial_symbol_placement`'s own defaults apply when omitted.

    `frequency_hz`, NOT `target_frequency_hz`: the CONTINUOUS branch just
    above this one in `_handle_optimization` uses `target_frequency_hz`,
    but this handler's SIMULATION-step sibling for these same two families,
    `_simulate_palace_floquet`, already uses a bare `frequency_hz` for the
    identical "one point on the band this run is evaluated at" idea, and
    `lookup_symbol_entries`'s own parameter is spelled `frequency_hz` too.
    Both spellings are established precedent in this codebase;
    `frequency_hz` is chosen here because it agrees with BOTH of this
    handler's direct neighbours (the sibling SIMULATION handler for these
    families, and the library function this handler calls), where
    `target_frequency_hz` would only agree with the unrelated continuous
    patch-length search.

    ONE SHARED CANDIDATE SET, NOT ONE PER GRID POSITION (design decision
    2): nothing in this codebase varies incidence angle or process across a
    single design's grid, so "the current design's target band,
    incidence-angle range, and process" (issue #267's own wording) is ONE
    point query, resolved once by `_combinatorial_candidate_options` and
    reused identically at every `(i, j)` position
    `combinatorial_symbol_placement` asks about.

    THE RESPONSE-TO-SCALAR FIELD IS NAMED "phase_deg" HERE, NOT DEFAULTED
    INSIDE THE REDUCTION FUNCTION (design decision 3): REFLECTION_PHASE and
    DIFFUSIVE are both designed by their per-cell reflection PHASE
    (designs/design_families.py's own comments on both families -- "a
    coding cell IS its reflection phase"). That fact belongs at THIS call
    site, not baked into `designs.element_alphabet.
    reduce_response_at_frequency`, which stays generic on purpose,
    mirroring `SymbolOption.achieved_value`'s own "generic on purpose"
    docstring.

    ZERO MATCHING ENTRIES FAILS LOUDLY, NAMING THE KEY, BEFORE THE
    COMBINATORIAL SEARCH EVER RUNS (design decision 4a): every grid
    position shares the one candidate list `_combinatorial_candidate_
    options` resolves, so an empty result means EVERY position has nothing
    to place -- checked and reported here, naming exactly which
    family/band/incidence-angle/process came up empty, rather than letting
    `combinatorial_symbol_placement` discover it position-by-position via
    `EmptyCandidateShelfError`. In production today the alphabet holds
    nothing (issue #132's print-and-measure work has not happened) -- this
    is the path a real run actually takes, and it must never fall through
    to the continuous patch-length search (the same discipline issues
    #239/#241 already apply to ANALYSIS/SIMULATION).

    `EmptyCandidateShelfError` (design decision 4b) -- raised by
    `combinatorial_symbol_placement` itself, reachable if some narrower gap
    slips past the check above -- is re-raised as `DesignLoopValidationError`
    with its own message intact, the same `raise DesignLoopValidationError
    (str(exc)) from exc` convention `_handle_architecture`/`_handle_analysis`/
    `_declared_adapter_name` already use for every other adapter-level
    exception in this file.

    THE TARGET-SHAPE GUARD BELOW ALSO CHECKS RAGGEDNESS (design decision
    4c), duplicating part of `optimization.combinatorial._validate_target`'s
    own non-empty/rectangular check. That duplication is only partly
    avoidable -- this handler needs `n_rows`/`n_cols` before it can build
    `candidates` at all, a real constraint of `combinatorial_symbol_
    placement`'s signature (the caller supplies candidates, so the caller
    must already know the grid shape) -- but the two checks must agree on
    what they reject: a ragged `target` that only `_validate_target` caught
    would raise a bare, un-wrapped `ValueError` from inside
    `combinatorial_symbol_placement`, past this handler's `except
    _EmptyCandidateShelfError` clause, with none of this dispatch layer's
    naming/wrapping discipline. Checking row-length consistency here too
    closes that gap up front, the same place the non-empty/2D check already
    lives.
    """
    from .design_loop import (
        DesignLoopValidationError,
        _combinatorial_symbol_placement,
        _EmptyCandidateShelfError,
        _require_fields,
    )

    _require_fields(
        step_input,
        {
            "element_family",
            "symbol_entries",
            "frequency_hz",
            "incidence_angle_deg",
            "process_id",
            "target",
            "delta_phi_max_deg",
        },
        "optimization",
    )
    element_family = step_input["element_family"]
    frequency_hz = step_input["frequency_hz"]
    incidence_angle_deg = step_input["incidence_angle_deg"]
    process_id = step_input["process_id"]
    target = step_input["target"]

    candidate_options = _combinatorial_candidate_options(
        symbol_entries=step_input["symbol_entries"],
        element_family=element_family,
        frequency_hz=frequency_hz,
        incidence_angle_deg=incidence_angle_deg,
        process_id=process_id,
        response_field="phase_deg",
    )
    if not candidate_options:
        raise DesignLoopValidationError(
            f"Design family {family.name!r} needs at least one candidate symbol "
            f"for element_family={element_family!r} at frequency_hz={frequency_hz!r}, "
            f"incidence_angle_deg={incidence_angle_deg!r}, process_id={process_id!r}, "
            "and none of the supplied symbol_entries match that key. Every grid "
            "position in this design shares this same lookup, so none of them can "
            "be placed until at least one symbol is characterised for this "
            "family/band/incidence-angle/process (issue #132's print-and-measure "
            "work) -- this never falls through to the continuous patch-length "
            "search (the same discipline issues #239/#241 already apply to "
            "ANALYSIS/SIMULATION, per issue #267)."
        )

    if not isinstance(target, list) or not target or not isinstance(target[0], list):
        raise DesignLoopValidationError(
            "optimization step_input['target'] must be a non-empty 2D grid "
            f"(target[j][i]), got {target!r}"
        )
    n_rows = len(target)
    n_cols = len(target[0])
    if any(not isinstance(row, list) or len(row) != n_cols for row in target):
        raise DesignLoopValidationError(
            "optimization step_input['target'] must be rectangular (every row "
            f"the same length): row lengths were "
            f"{[len(row) if isinstance(row, list) else type(row).__name__ for row in target]}"
        )
    candidates = {(i, j): candidate_options for j in range(n_rows) for i in range(n_cols)}

    try:
        result = _combinatorial_symbol_placement(
            target=target,
            candidates=candidates,
            delta_phi_max_deg=step_input["delta_phi_max_deg"],
            random_seed=step_input.get("random_seed"),
            max_generations=step_input.get("max_generations", 100),
            population_size=step_input.get("population_size", 15),
            objective_name=step_input.get("objective_name"),
        )
    except _EmptyCandidateShelfError as exc:
        raise DesignLoopValidationError(str(exc)) from exc

    recorded = _combinatorial_result_to_dict(result)
    return "optimization", recorded, recorded["provenance"]


# The dispatch table `_handle_optimization` reads -- this loop's counterpart
# to `_ANALYSIS_MODELS`/`_SIMULATION_ADAPTERS` above. One named handler per
# declared `optimizer_class` value (`"CONTINUOUS"` also standing in for the
# unset/`None` case -- see `_handle_optimization`'s own docstring for why
# that fold happens before this dict is consulted rather than as a third
# entry here). A family declaring a value that is not a key here is a
# reported failure, not a fallback (issue #508).
_OPTIMIZER_HANDLERS: dict[str, Any] = {
    "CONTINUOUS": _optimize_continuous_patch_length,
    "COMBINATORIAL": _optimize_combinatorial_symbol_placement,
}
