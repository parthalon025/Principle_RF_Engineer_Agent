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
the `REDESIGN_DECISION` step's `rationale`, which is exactly the "what was
tried and why it didn't work" data `search_design_records` exists to
surface as precedent for future designs (CONTEXT.md: Design/decision
record). Flushing at each iteration boundary means even an abandoned loop
leaves a full record of every completed iteration.

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
