---
status: accepted
---

# A candidate's score carries a full per-input provenance profile, display-only, frozen at calculation

Issue #112, a sub-item of the #104 wayfinder map, asked how a candidate's
score should inherit the weakest provenance rung among the inputs that fed
it — datasheet, literature, patent, Maxwell-Garnett estimate, solver output.
As posed, the question presupposed something the code did not do: a 2026-09-05
research pass (`docs/grilling-pass-2026-09-05.md` §3, PR #179) found that
`success_score()` (`designs/success_score.py:448–584`) takes `actual_value`
as a bare, untagged float and records nothing about what produced it. Its
result dict carries `provenance` (always `"CALCULATED"`, the arithmetic's
own), `target_provenance` (always `"ASSUMED"`, by construction),
`target_status`, and `note_provenance` — none of it a tag on the *inputs*.
There was, at the time, no total order to take a minimum over either:
`knowledge/provenance.py`'s `_TIER_AUTHORITY_RANK` — built to rank retrieved
documents for literature search per ADR-0002, not to compare `MEASURED`
against `ASSUMED` — covered only three of CONTEXT.md's then-eight provenance
tiers (`MANUFACTURER_SPECIFIED`=20, `LITERATURE_SUPPORTED`=40,
`INTERNAL_HISTORY`=60), and the ladder itself was incomplete.

Weakest-link already has in-repo precedent for score *value*:
`orchestration/solver.py`'s `worst_of_scored_steps` convergence rule sets `overall_score_percent` to the
**minimum** across a candidate's ANALYSIS/SIMULATION/OPTIMIZATION scores,
stamping every result with `"convergence_rule": "worst_of_scored_steps"`
(`:1002`), and its own comment (`:157–164`) rejects best-of and mean-of for
the same reasoning this ticket raised about provenance. But the same pass
found a gap that precedent doesn't answer: weakest-link is blind to
sensitivity — an `ASSUMED` input the answer barely depends on and one that
single-handedly decides it collapse to an identical tag. The literature
survey cut against a pure weakest-link rule regardless: **NASA-STD-7009B
explicitly forbids** combining its Credibility Assessment Scale factors into
one figure of merit, for exactly the failure this ticket named — a single
low factor drags every candidate to a shared floor and destroys the ability
to tell them apart. GRADE does combine into one certainty rating (*"the
lowest rating of certainty among the critical outcomes will generally
provide an upper limit for the overall certainty"*), but grades one body of
evidence, never rival candidates against each other. Provenance semirings
(Green, Karvounarakis & Tannen, PODS 2007) validate weakest-link as the
algebraically correct combinator for the composition that actually exists
here — every input is a genuine AND, since losing one makes `actual_value`
uncomputable — and W3C PROV validates keeping a per-input graph rather than
a flattened tag, while supplying no combining rule of its own. Two
candidate combinators were flagged and set aside as mismatched: GUM's
quadrature combination, which presupposes every contributor is already a
standard uncertainty of the *same* physical quantity entering *one*
equation, and Dempster–Shafer, built to reconcile several sources
disagreeing about the *same* proposition — neither describes summarizing
several different inputs' evidence classes.

## Decision

1. **A score carries a full per-input provenance profile**, not a
   collapsed single tag. This follows NASA-STD-7009B's own reasoning
   directly: collapsing trust factors into one number is exactly what
   destroys discrimination between candidates, and a summary statistic can
   always be computed from a stored profile later — never reconstructed
   once the profile itself was discarded.

2. **The profile is display-only.** It never affects `score_percent` and
   never enters `orchestration/solver.py`'s comparison or ordering logic —
   it is shown alongside the score for a human to weigh, matching the
   map's standing "no thumb on the scale" rule. Of the four points decided
   here, this is the one kept deliberately reversible: ranking behavior can
   be layered on top later once a tagging pipeline is trusted; it cannot be
   safely removed once other code has come to depend on it.

3. **A score is a frozen snapshot, never restated.** It does not mutate
   when an input's provenance later improves — literature-supported
   becoming measured after a coupon run, for instance — because it is a
   record of what was known when it was computed, not a live view. This
   matches the pattern already settled for issue #100.

4. **The total order and the summary formula are deferred, not decided.**
   CONTEXT.md's provenance set is closed at nine values. No total order
   across those nine rungs, and no weakest-link/summary formula, is
   specified by this decision. That question needs real tagged data to
   design against responsibly, and is recorded on the #104 map as fog, not
   yet filed as its own ticket. What is committed now is only the additive
   slice that makes tagging possible at all: an
   `input_provenance: list[str] | None = None` field on `success_score()`'s
   output, carried straight through the result dict, defaulting to `None`
   when a caller supplies nothing, with no change to `solver.py` or
   `design_loop.py`.

## Considered and rejected

- **A collapsed weakest-link tag as the sole recorded output.** Rejected on
  NASA-STD-7009B's own reasoning (one low factor drags every candidate to
  the same floor) and on sensitivity-blindness: an input the answer barely
  depends on and one that single-handedly decides it would produce an
  identical tag.
- **Reusing `knowledge/provenance.py`'s `_TIER_AUTHORITY_RANK` as the
  provenance total order.** Rejected: that table ranks retrieved documents
  for literature search (ADR-0002), covered only three of the eight
  provenance tiers current at the time, and was never built to compare
  `MEASURED` against `ASSUMED`.
- **GUM-style quadrature combination of provenance.** Rejected: it
  presupposes every contributor is already a standard uncertainty of the
  same physical quantity entering one equation, which is not this
  composition.
- **Dempster–Shafer combination.** Rejected: built to reconcile multiple
  sources disagreeing about the same proposition, not to summarize several
  different inputs' evidence classes feeding one calculation.
- **Designing the full weakest-link/summary rule now, in the abstract.**
  Rejected in favor of deferral — there is no tagged data yet to design
  against, and picking a formula without it risks the same shape of error
  as importing a combinator from an unrelated domain, which is precisely
  what ruled out GUM and Dempster–Shafer above.

## Consequences

- `orchestration/solver.py`'s ranking and `score_percent` computation are
  untouched by this decision, by design. Any future move to let provenance
  weight ranking is a separate decision this ADR does not make and should
  not be read as implying.
- **The total order across CONTEXT.md's nine provenance rungs, and the
  weakest-link/summary formula, remain open.** They are logged as fog on
  the #104 map, not yet filed as their own ticket, and nothing here should
  be read as having settled either.
- The additive field itself is still open implementation work, not a
  shipped fact. A later sweep of the map (`docs/RUNNING-LISTS.md`, "Found
  while grilling the map itself," item 30) found the string
  `input_provenance` occurring nowhere in `designs/success_score.py`, or
  anywhere else in the repository, after the map had already recorded it as
  shipped. The decision recorded above stands unchanged — the sweep's own
  conclusion was *"the decisions are sound and remain recorded; only the
  claim that they shipped was false"* — but adding the field to
  `success_score()` remains to be done.
- This ADR does not decide, and does not need to decide, how a future
  consumer of the profile (a rejection-memory lookup in ADR-0026's vein, or
  any later ranking feature) is meant to read it back; the profile as
  decided here is only what a caller supplies at calculation time.

