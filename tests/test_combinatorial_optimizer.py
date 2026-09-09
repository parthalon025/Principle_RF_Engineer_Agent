"""Tests for optimization/combinatorial.py's combinatorial symbol-placement
search (issue #255): a categorical "which already-characterised symbol goes
in which grid position" search over a caller-supplied FAKE candidate-symbol
set, exercised entirely with hand-built synthetic data -- no real Element/
Coding-Alphabet library exists in this tree yet (issue #256), and this
module's own contract (optimization/combinatorial.py's module docstring) is
that it never assumes one does.

Every test here builds its own small `candidates` dict by hand, standing in
for what a real alphabet-library lookup would eventually supply -- the same
role the stub `symbol_library` dict plays in
tests/test_geometry_unit_cell.py's own generate_coded_unit_cell_array
tests. The one cross-check test at the bottom (
test_combinatorial_symbol_placement_layout_feeds_generate_coded_unit_cell_array)
confirms the returned `layout` really is that function's own `layout`
argument, unmodified -- it is skipped, not failed, when gdstk (an optional
extra, see geometry/unit_cell.py) is not installed, matching
tests/test_geometry_unit_cell.py's own importorskip guard.
"""

import pytest

from optimization.combinatorial import (
    EmptyCandidateShelfError,
    SymbolOption,
    combinatorial_symbol_placement,
)

# ---------------------------------------------------------------------------
# Small hand-built fake candidate sets. Values are treated as an achieved
# reflection phase in degrees (this module's own units are generic -- "the
# per-position target" -- but degrees is the concrete quantity Delta_phi_max
# is stated in, and using it consistently here keeps every test's numbers
# physically legible).
# ---------------------------------------------------------------------------


def _exact_match_candidates() -> dict[tuple[int, int], list[SymbolOption]]:
    """A 2x1 grid (2 columns, 1 row) where every position has a candidate
    that exactly matches its target -- the "near-zero achieved error"
    case."""
    return {
        (0, 0): [
            SymbolOption(symbol_id="A_far", achieved_value=170.0),
            SymbolOption(symbol_id="A_exact", achieved_value=0.0),
        ],
        (1, 0): [
            SymbolOption(symbol_id="B_far", achieved_value=-160.0),
            SymbolOption(symbol_id="B_exact", achieved_value=10.0),
        ],
    }


_EXACT_MATCH_TARGET = [[0.0, 10.0]]  # target[j][i], one row (j=0), two columns


def test_combinatorial_symbol_placement_finds_exact_match_with_near_zero_error():
    result = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,
        candidates=_exact_match_candidates(),
        delta_phi_max_deg=12.0,
        random_seed=1,
    )

    assert result.layout == [["A_exact", "B_exact"]]
    assert result.achieved_error == pytest.approx(0.0, abs=1e-9)
    assert result.provenance == "CALCULATED"
    assert result.method == "combinatorial_symbol_placement"
    assert result.warnings == []


def test_combinatorial_symbol_placement_records_full_evaluation_trace():
    result = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,
        candidates=_exact_match_candidates(),
        delta_phi_max_deg=12.0,
        random_seed=1,
    )

    # More than just the winner: differential_evolution's population-based
    # search evaluates many candidate placements per generation (see
    # optimization/genetic.py) -- the trace must carry all of them, each
    # tagged with its own achieved error, not just the best one.
    assert len(result.evaluations) > 1
    for entry in result.evaluations:
        assert set(entry) == {"layout", "error", "feasible"}
        assert entry["layout"][0][0] in ("A_far", "A_exact")
        assert entry["layout"][0][1] in ("B_far", "B_exact")
        assert isinstance(entry["error"], float)
        assert isinstance(entry["feasible"], bool)
    # The winning layout must actually appear somewhere in its own trace.
    assert any(e["layout"] == result.layout for e in result.evaluations)


def test_combinatorial_symbol_placement_is_deterministic_given_a_seed():
    result_a = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,
        candidates=_exact_match_candidates(),
        delta_phi_max_deg=12.0,
        random_seed=7,
    )
    result_b = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,
        candidates=_exact_match_candidates(),
        delta_phi_max_deg=12.0,
        random_seed=7,
    )

    assert result_a.layout == result_b.layout
    assert result_a.achieved_error == result_b.achieved_error
    assert result_a.evaluations == result_b.evaluations


def test_combinatorial_symbol_placement_thin_shelf_warns_but_still_places():
    """A position with exactly one candidate has no choice at all -- the
    search must still place it (never skip or crash), but must say so."""
    candidates = {
        (0, 0): [SymbolOption(symbol_id="ONLY_A", achieved_value=5.0)],
        (1, 0): [
            SymbolOption(symbol_id="B_far", achieved_value=-160.0),
            SymbolOption(symbol_id="B_exact", achieved_value=10.0),
        ],
    }

    result = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,
        candidates=candidates,
        delta_phi_max_deg=12.0,
        random_seed=1,
    )

    assert result.layout[0][0] == "ONLY_A"  # the only option, forced
    assert result.layout[0][1] == "B_exact"  # still searched and found
    assert len(result.warnings) == 1
    assert "i=0, j=0" in result.warnings[0]
    assert "one candidate" in result.warnings[0]


def test_combinatorial_symbol_placement_all_positions_thin_shelf_needs_no_search():
    """Every position pinned to a single candidate: nothing left to search,
    but the placement is still built, scored, and returned -- not skipped."""
    candidates = {
        (0, 0): [SymbolOption(symbol_id="ONLY_A", achieved_value=5.0)],
        (1, 0): [SymbolOption(symbol_id="ONLY_B", achieved_value=8.0)],
    }

    result = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,
        candidates=candidates,
        delta_phi_max_deg=12.0,
        random_seed=1,
    )

    assert result.layout == [["ONLY_A", "ONLY_B"]]
    assert len(result.evaluations) == 1
    assert len(result.warnings) == 2


def test_combinatorial_symbol_placement_empty_shelf_raises_clear_error():
    """A position with ZERO candidates cannot be placed at all -- this must
    fail loudly and name the position, mirroring
    geometry.unit_cell.SymbolNotFoundError's "no plausible substitute, so
    refuse and name the gap" reasoning, not silently skip or crash."""
    candidates = {
        (0, 0): [SymbolOption(symbol_id="A_exact", achieved_value=0.0)],
        (1, 0): [],  # nothing characterised for this position yet
    }

    with pytest.raises(EmptyCandidateShelfError, match=r"\(1, 0\)"):
        combinatorial_symbol_placement(
            target=_EXACT_MATCH_TARGET,
            candidates=candidates,
            delta_phi_max_deg=12.0,
            random_seed=1,
        )


def test_combinatorial_symbol_placement_missing_position_key_treated_as_empty_shelf():
    """A position absent from `candidates` entirely is the same "nothing
    available here" situation as an explicit empty list -- both must raise
    the same clear error, not a silent default or a KeyError."""
    candidates = {(0, 0): [SymbolOption(symbol_id="A_exact", achieved_value=0.0)]}
    # (1, 0) is missing entirely.

    with pytest.raises(EmptyCandidateShelfError, match=r"\(1, 0\)"):
        combinatorial_symbol_placement(
            target=_EXACT_MATCH_TARGET,
            candidates=candidates,
            delta_phi_max_deg=12.0,
            random_seed=1,
        )


def test_combinatorial_symbol_placement_respects_delta_phi_max_budget():
    """A 1x2 grid (1 column, 2 rows) where the raw-lowest-error combination
    (error 0.0, both symbols hit their target exactly) puts two symbols 40
    degrees apart as vertical (E-plane) neighbours -- violating a
    12-degree Delta_phi_max budget -- while the best FEASIBLE combination
    scores a strictly higher raw error. The budget-respecting combination
    must win, even though it does not have the lowest raw error overall
    (User Story 7 / Testing Decisions).

    All four combinations, worked out by hand (mean absolute error over
    the 2 positions; neighbour gap = |top - bottom|):
      TOP_EXACT(0)+BOT_FAR(40):   error 0.0,  gap 40 -> INFEASIBLE (best raw error)
      TOP_EXACT(0)+BOT_CLOSE(5):  error 17.5, gap 5  -> feasible (best FEASIBLE)
      TOP_CLOSE(3)+BOT_FAR(40):   error 1.5,  gap 37 -> INFEASIBLE
      TOP_CLOSE(3)+BOT_CLOSE(5):  error 19.0, gap 2  -> feasible
    """
    candidates = {
        (0, 0): [
            SymbolOption(symbol_id="TOP_EXACT", achieved_value=0.0),
            SymbolOption(symbol_id="TOP_CLOSE", achieved_value=3.0),
        ],
        (0, 1): [
            SymbolOption(symbol_id="BOT_FAR", achieved_value=40.0),
            SymbolOption(symbol_id="BOT_CLOSE", achieved_value=5.0),
        ],
    }
    target = [[0.0], [40.0]]  # target[j][i]: row 0 wants 0 deg, row 1 wants 40 deg

    result = combinatorial_symbol_placement(
        target=target,
        candidates=candidates,
        delta_phi_max_deg=12.0,
        random_seed=3,
    )

    # TOP_EXACT + BOT_FAR scores the lowest raw error (0.0) of all four
    # combinations but violates the 12-degree budget (40-degree neighbour
    # gap); it must never win, even though nothing else beats its raw error.
    assert result.layout != [["TOP_EXACT"], ["BOT_FAR"]]
    assert result.layout == [["TOP_EXACT"], ["BOT_CLOSE"]]
    assert result.achieved_error == pytest.approx(17.5)
    # The winning placement's own trace entry must be marked feasible.
    winner_entries = [e for e in result.evaluations if e["layout"] == result.layout]
    assert winner_entries and all(e["feasible"] for e in winner_entries)
    # And the infeasible, lower-raw-error combination must still show up in
    # the trace, tagged infeasible -- evaluated, not hidden.
    violating_entries = [
        e for e in result.evaluations if e["layout"] == [["TOP_EXACT"], ["BOT_FAR"]]
    ]
    assert violating_entries and all(not e["feasible"] for e in violating_entries)


def test_combinatorial_symbol_placement_rejects_ragged_target():
    with pytest.raises(ValueError, match="rectangular"):
        combinatorial_symbol_placement(
            target=[[0.0, 10.0], [5.0]],
            candidates=_exact_match_candidates(),
            delta_phi_max_deg=12.0,
            random_seed=1,
        )


def test_combinatorial_symbol_placement_rejects_empty_target():
    with pytest.raises(ValueError):
        combinatorial_symbol_placement(
            target=[],
            candidates={},
            delta_phi_max_deg=12.0,
            random_seed=1,
        )


def test_combinatorial_symbol_placement_tags_target_and_candidate_snapshot():
    result = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,
        candidates=_exact_match_candidates(),
        delta_phi_max_deg=12.0,
        random_seed=1,
        objective_name="reflection_phase_placement",
    )

    assert result.target == _EXACT_MATCH_TARGET
    assert result.objective_name == "reflection_phase_placement"
    assert result.delta_phi_max_deg == 12.0
    assert result.random_seed == 1
    assert set(result.candidate_snapshot) == {(0, 0), (1, 0)}
    assert result.candidate_snapshot[(0, 0)] == _exact_match_candidates()[(0, 0)]
    # A snapshot, not a live reference -- mutating the caller's dict
    # afterward must not change what the result already recorded.
    fresh_candidates = _exact_match_candidates()
    fresh_candidates[(0, 0)].append(SymbolOption(symbol_id="NEW", achieved_value=999.0))
    result2 = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,
        candidates=fresh_candidates,
        delta_phi_max_deg=12.0,
        random_seed=1,
    )
    fresh_candidates[(0, 0)].append(SymbolOption(symbol_id="EVEN_NEWER", achieved_value=1.0))
    assert len(result2.candidate_snapshot[(0, 0)]) == 3  # unaffected by the later append


# ---------------------------------------------------------------------------
# Cross-check: the returned layout is directly usable as
# generate_coded_unit_cell_array's own `layout` argument, per this module's
# whole reason for matching that function's shape (issue #255 User Story
# 16). Skipped (not failed) when gdstk isn't installed, matching
# tests/test_geometry_unit_cell.py's own guard.
# ---------------------------------------------------------------------------

gdstk = pytest.importorskip(
    "gdstk", reason="gdstk not installed -- run `uv sync --extra geometry` first"
)

from geometry.unit_cell import generate_coded_unit_cell_array  # noqa: E402


def test_combinatorial_symbol_placement_layout_feeds_generate_coded_unit_cell_array():
    result = combinatorial_symbol_placement(
        target=_EXACT_MATCH_TARGET,
        candidates=_exact_match_candidates(),
        delta_phi_max_deg=12.0,
        random_seed=1,
    )

    # Real unit-cell primitive geometry, keyed by the same symbol ids this
    # module's own placement chose -- standing in for a real
    # Element/Coding-Alphabet library lookup (#256), same as
    # tests/test_geometry_unit_cell.py's own hand-built symbol_library.
    symbol_library = {
        "A_exact": {"shape": "box", "p1_m": [0.0, 0.0, 0.0], "p2_m": [0.005, 0.005, 0.001]},
        "B_exact": {"shape": "box", "p1_m": [0.0, 0.0, 0.0], "p2_m": [0.006, 0.004, 0.001]},
    }

    primitives = generate_coded_unit_cell_array(
        result.layout,
        symbol_library,
        pitch_m=(0.015, 0.015),
        delta_phi_max_deg=12.0,
        rcsr_db=10.0,
        wavelength_m=0.03,
        panel_size_m=(0.18, 0.18),
        name_prefix="block",
    )

    assert len(primitives) > 0
    assert all(p["shape"] == "box" for p in primitives)
