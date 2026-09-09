---
status: accepted
---

# A simulator's historical accuracy is a fact about the tool — but the ledger stays documentation-only until two preconditions clear

Issue [#150](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/150)
asked whether CORRELATION results (SIMULATED-vs-MEASURED comparisons,
`rf_tools/correlation.py`) should accumulate across designs into a queryable
"this simulator historically ran N% off" ledger, given the loop's own rule
that "a guess never becomes settled by repetition." ADR-0015 already carved
out one exception to that rule — a material's permittivity is a fact about
the material, not about any one requirement — and this ticket asked whether
a tool's own accuracy is the same shape of fact.

**Decision: the analogy holds, with a hard validity boundary the ADR-0015
precedent didn't need — and no ledger code lands from this ticket.**

## The analogy, and its limit

A simulator's error pattern is a fact about the tool, reusable across
designs the same way a material's εr is reusable across requirements.
Kennedy & O'Hagan (*JRSS-B*, 2001) formalise exactly this as a model
discrepancy term. But Brynjarsdóttir & O'Hagan (2014) — by one of the same
authors, written specifically to correct misuse of the 2001 framework —
show that discrepancy degrades to meaningless once queried far enough from
where it was fitted, with nothing in the maths raising a hand to say so.
ASME V&V 20 and Koziel's antenna-surrogate "domain confinement" work both
corroborate the same limit from adjacent directions.

*In plain terms: "our simulator ran 3% high on patch antennas" tells you
almost nothing about whether it runs high on a metamaterial cell.* Unlike a
material property, which is valid wherever that material is used, a
discrepancy is valid only inside the region it was fitted in. **A query
outside that region must return nothing, never a degraded number.**

## Two things this ticket's own thread got wrong, corrected here

1. **`design_family` is not blocked, despite the 2026-09-05 research pass's
   conclusion.** Issue #167 (closed 2026-09-08) made `design_family` reach
   `decision_records`, but `orchestration/tooling.py`'s engineering-result
   flush branch still doesn't copy it onto `engineering_results` directly.
   It is nonetheless recoverable **today, via a join on the shared
   `design_id`** between `engineering_results` and `decision_records` — no
   schema change needed. The "simulator only, or blocked" framing was stale.
2. **"Simulator" is a real, multi-valued fact in the execution path — but
   the column that would record it lies.** `orchestration/design_loop.py`'s
   `_handle_simulation` genuinely dispatches per design family's declared
   `simulation_adapter` (issue #229): NEC2, `MEEP_FLOQUET`, and Palace are
   all live, wired-in adapters, not a hypothetical future. But
   `orchestration/tooling.py`'s `_tool_name_for` resolves the persisted
   `engineering_results.tool_name` from a fixed per-step table that always
   writes `"run_nec2_simulation"` for any SIMULATION-kind decision,
   regardless of which adapter actually ran. Filed as **issue #334** — a
   correctness bug independent of this decision, since the true identity
   already survives inside the result's own JSONB `value` blob
   (`function`/`simulator` keys), just not in a queryable column.

## Validated (against known-exact math) is not the same claim as trusted (against physical reality)

`docs/meep-absorber-validation.md` already did real, rigorous work checking
Meep against answers that are exactly known independent of this codebase — a
free-standing resistive sheet's closed-form absorption maximum, a Salisbury
screen against an independent equivalent-circuit model, a conductive slab
against an exact ABCD-derived answer — two of the four cases running through
the real adapter and the real design-loop SIMULATION step. That is a
genuine, separate achievement, and it answers a genuine, separate question:
**does the adapter compute what it claims to compute.**

It does not answer this ticket's question — **does the computed number
match what a physically fabricated, physically measured part does** — which
is what CORRELATION is for and what the ADR-0015 analogy is about. A
simulator can be numerically flawless and still miss physical reality for
reasons no amount of exact-math checking catches (fabrication tolerance,
surface finish, an unmodelled loss mechanism). Conflating the two would
repeat the exact category error `RUNNING-LISTS.md` §3 keeps recording
elsewhere in this project. Kept distinct here so a later reader does not
assume `verification/`'s work already answers this ticket.

## What is allowed, once built

Advisory only, per the thread's own proposal, unchanged: an `INFERRED`-
tagged note attached to a new SIMULATION result and to the solver's report
("historically, correlated runs like this one ran N% off, within region
X") — **never** a score adjustment, never a candidate filter, never
anything touching an approval gate. Per issue #112's already-settled rule
(a score's provenance profile is display-only, never rank-affecting), this
constraint is not a special case invented for this ticket — it is the
project's standing rule applied to one more input.

## Considered and rejected

- **Build the "simulator-only key" slice now**, per the 2026-09-05 research
  pass's proposed cheap first step. Rejected: it would query a column
  (`tool_name`) that is currently wrong for every non-NEC2 run (#334), and
  real CORRELATION-row volume is still near zero (correlation needs a
  MEASUREMENT behind it — ADR-0013 allows an externally-obtained measured
  result, so the Example-3-vs-Landy work (#142/#233) could plausibly supply
  the first real row, but nothing exists yet). Building against zero-to-one
  rows through a known-bugged column is speculative infrastructure, not a
  decision this ticket should ship as code.
- **Reject the ADR-0015 analogy outright**, on the grounds that "a guess
  never becomes settled by repetition" should have no exceptions. Rejected:
  the analogy holds on the same reasoning ADR-0015 already accepted, and the
  boundary condition (query nothing outside the fitted region) is exactly
  what keeps this exception from becoming the general case the standing
  rule warns against.

## Consequences

- No code lands from this ticket. The eventual ledger's key —
  `(simulator, design_family via join, frequency band)` — is fully
  specifiable, but filed separately as a `ready-for-agent` implementation
  issue, blocked on #334, matching the pattern already established by
  #167/#205/#254/#334: scoped work filed once its shape is known, even
  while blocked, rather than left as vague fog.
- Two related ideas surfaced while researching this ticket, neither
  resolved here, both added to map #104's "Not yet specified":
  - **A formal "validated" tag**, distinct from bare `SIMULATED`, carrying
    its own validity box (structure type, incidence angle, band) — today
    the validated/bare distinction lives only as prose in
    `docs/meep-absorber-validation.md`. Per #112, any such tag stays
    display-only.
  - **A computed input-uncertainty band**, complementary to this ledger and
    buildable without new measurement: re-running a solver across a
    material property's already-recorded `±` range (ADR-0015) to report how
    far the output could move given known input uncertainty. This bounds
    *known-unknown* uncertainty; it structurally cannot catch the kind of
    model-reality gap only a real measurement reveals, so it complements
    rather than substitutes for this ticket's ledger.
- This is a plan-only decision (#104's map is explicitly plan-only); no
  code changes accompany it.
