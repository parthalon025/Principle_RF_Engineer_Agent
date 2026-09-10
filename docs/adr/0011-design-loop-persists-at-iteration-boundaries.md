---
status: accepted
---

# The design loop persists to the database at each iteration boundary, not per-step or only at completion

`orchestration/design_loop.py`'s own module docstring (issue #46) deferred
persistence entirely: `DesignLoopState` was caller-held JSON, and the
`designs`/`decision_records`/`engineering_results`/`verification_items`
tables it could write to were left for "a FUTURE ticket." `/grill-with-docs`
on the RF tool orchestration flow picked that ticket up.

**Timing — flush at every `REDESIGN_DECISION → iterate` transition, and
again at `accept_design`; not after every step, and not only at the end.**
Per-step persistence was rejected as unnecessary granularity — a single
calculation mid-iteration isn't itself a meaningful precedent record.
Persisting only at final completion was rejected after considering that an
abandoned loop (conversation ends mid-iteration, no `accept_design` ever
reached) would otherwise leave *zero trace* of what was tried — including
the `REDESIGN_DECISION` step's `rationale`, real "what was tried and why
it didn't work" data. Flushing at each iteration boundary means even an
abandoned loop leaves a full record of every completed iteration, readable
back via `read_design`.

**Correction (found during code review): this is NOT, by itself, precedent
`search_design_records` can find.** An earlier draft of this ADR claimed
flushed decisions would be "surfaced as precedent... by
`search_design_records`" — wrong, and CONTEXT.md already said so before
this ADR was written: `search_design_records` only searches `documents`
rows ingested via `ingest_document` with `source_type=design_record`, and
CONTEXT.md's own "Design/decision record" entry explicitly warns against
conflating that ingested-document concept with the `decision_records`
SQL table this ADR persists to ("_Avoid_: conflating with the
`decision_records` table... a design/decision record is a separate,
searchable knowledge-base document about a *past* design... not an
approval workflow"). This persistence makes a loop's full history
available to read (`read_design`) and gives a future human or agent real
data to write an actual `design_record` document from — it does not, by
itself, make that history searchable as precedent. Bridging the two
(auto-ingesting a flushed loop's history as a searchable document) is a
separate, not-yet-designed feature, not something this ADR builds.

**Failure handling — fail loud.** If a flush fails (a step's action already
ran, but writing it to the database errors), the transition is not treated
as having succeeded — the loop does not silently advance past a boundary
whose data was never actually saved. A later reader (`search_design_records`,
`read_design`, a future loop citing this one as precedent) must never
silently see a completed-looking design that in fact only partially made it
into the database.

**Architecture — `design_loop.py` stays pure; persistence lives in
`orchestration/tooling.py`.** The state machine remains DB-free and
independently unit-testable, matching its original design goal. `tooling.py`
is the existing seam between the pure state transition and the outside
world (it already coerces JSON-boundary shapes for the approval receipt);
persistence calls are added there, not inside `advance_loop_step` itself.

## Consequences

- `start_new_design_loop` now requires `design_key`/`name`/`revision`
  alongside `requirements`, to create the backing `designs` row — a
  breaking change to that tool's input shape (issue #46 predates any real
  caller, so no compatibility shim was added).
- `designs.status` now has real transition logic for the first time — this
  is new work `docs/adr/0007` explicitly deferred ("no transition logic
  between the other states... exists yet"), not a contradiction of it. It
  is set exactly once per flush, not per individual loop step: since
  nothing persists until a flush boundary anyway, an intermediate
  per-step mapping (ANALYSIS/SIMULATION/OPTIMIZATION/VERIFICATION/
  MEASUREMENT/CORRELATION each setting their own status value as reached)
  would only ever be visible for the instant before the same flush
  immediately overwrote it with the transition's own final value — so
  `REDESIGN_DECISION`'s `iterate` sets `designs.status` directly to
  `ANALYSIS` (the next iteration's first real step), and `accept_design`
  sets it directly to `PASS`. None of this reaches `RELEASED`, which stays
  exclusively `manufacturing_release`'s concern (not yet built, per
  ADR-0005).
- `designs.db.record_engineering_result` gains an optional explicit
  `provenance` override for trusted internal callers, rather than only its
  existing `tool_name`-keyed lookup (`designs/provenance.py`). The
  design-loop step handlers already compute the correct provenance
  themselves (from the real calculation/simulation/measurement/correlation
  function's own return value) — routing that through a second,
  tool-name-keyed table would just be a second, redundant source of truth
  for a value already trustworthy. Every existing caller (the ~65
  agent/MCP tool wrappers) is unaffected: the override defaults to unset,
  preserving today's lookup-only behavior exactly.

## Amendment: `orchestration/tooling.py` also re-reads requirements at every hand-back, not just writes at iteration boundaries (issue #100, 2026-09-04)

This ADR's own architecture split — `design_loop.py` stays pure and
DB-free, `tooling.py` is where the database calls live — turned out to cut
only one way in the original implementation: `tooling.py` *wrote*
`designs.requirements` (via `designs.requirement_targets`, #92) but never
*read* it back into a loop's own carried state. `DesignLoopState.requirements`
stayed exactly what `start_design_loop` captured once, for the life of the
loop — so a target proposed or confirmed after loop start via
`propose_requirement_target`/`confirm_requirement_target` landed on the
persisted `designs.requirements` column while every caller's held loop
state kept showing the pre-target snapshot. Issue #100 found this via
`orchestration/lab_test_plan.py`'s own defensive re-read (a fix scoped to
that one consumer, not the underlying gap) and named three options; this
picks option 2 — refresh at the layer that already owns the database call,
not inside `design_loop.py` (ADR's own "stays pure" premise), and not by
retiring the carried-state design entirely (option 3, the most invasive of
the three).

`advance_design_loop_step` and `inspect_design_loop_state` — the two
`tooling.py` functions that ever hand a state dict back to a caller after
loop start — now both re-read `designs.requirements` fresh
(`designs.db.read_design`, the same call `lab_test_plan.py`'s own
belt-and-braces re-read already used) and substitute it for whatever the
loop's own in-memory `requirements` carried, whenever the state dict
carries a `design_id`. Only the top-level `requirements` field is
replaced — `decisions[0]` (the REQUIREMENTS decision `start_design_loop`
recorded once, at loop start) is untouched, so the record of what was
originally stated is never overwritten by a later interpretation of it.
`design_loop.py` gains no new database awareness for this, same as the
original PERSISTENCE design above.

## Amendment: the flush no longer drops `decision.input` for engineering-result decisions (issue #400, 2026-09-10)

`orchestration/tooling.py`'s `_flush_target_for`, for every `calculation`/
`simulation`/`optimization`/`measurement`/`correlation` decision, wrote only
`decision.result` to `engineering_results.value` — `decision.input`, the
step's own recorded query/parameters, was silently discarded at the flush
boundary. This went unnoticed until a combinatorial (Tier B alphabet)
OPTIMIZATION step needed it: `decision.input` is what carries the resolved
`symbol_entries`/`process_id`/`frequency_hz` a placement was searched
against, and without it a persisted combinatorial result names *which*
symbol won each cell but not *which measured process* (machine/ink/cure)
that symbol's response came from — a gap independently worth closing for
the other four decision kinds too, not just this one.

Fixed by folding `decision.input` into the persisted value under an
`"input"` key, alongside `decision.result`'s own fields left at the TOP
level (`_flush_target_for`'s `_ENGINEERING_RESULT_KINDS` branch,
`orchestration/tooling.py`) —
deliberately NOT nesting `decision.result` itself under a matching
`"result"` key: `orchestration/solver.py`'s `_prior_best_from_design`
already reads a persisted row's scored field straight off `value`'s top
level (e.g. `value["resonant_frequency_hz"]`), and nesting it would have
silently broken every existing and future row that reader scores, trading
one dropped fact for another. Every historical row written before this fix
predates the `"input"` key entirely — a reader that needs it must treat its
absence on an old row as "not recorded," the same honest-absence reading
`LoopDecision.iteration`'s own docstring already establishes for a
different pre-existing field.

This amendment pairs with `optimization/combinatorial.py`'s own
`SymbolOption.entry_id`/`CombinatorialPlacementResult.entry_id_layout`
(same issue): `entry_id_layout` names which measured
`symbol_alphabet_entries` row backed each winning cell, and this
amendment is what stops `decision.input`'s matching query context from
being dropped alongside it at the flush.
