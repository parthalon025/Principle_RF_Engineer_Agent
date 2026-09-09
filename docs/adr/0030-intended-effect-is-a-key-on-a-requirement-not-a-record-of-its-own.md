---
status: accepted
---

# A requirement's intended effect is a key on the requirement, and it is what makes the considered-and-dropped ledger comparable across designs

`/grill-with-docs` asked where to record "what the customer is trying to
achieve", prompted by a patent-summary site that tags each mechanism with a
"scientific effect". The obvious reading — add an effect taxonomy — was
rejected: **Design family** already classifies mechanism, and does it better,
carrying a `physical_bound`, an `optimizer_class` and a `simulation_adapter`
rather than a bare label.

What is genuinely missing sits on the other side of the seam
`designs/design_families.py:43-45` already names: *"SELECTION STAYS
HUMAN-AUTHORED … the loop does not attempt to infer a family from a
requirement's prose."* Families describe how a thing is solved. Nothing
describes what the customer wanted.

**Decision: an intended effect is another key inside a requirement's own
entry, beside `requirement` and `target`.** Not a record of its own, not a
field on a family.

Five parts, each load-bearing:

**It attaches to a Customer requirement.** `designs/validation.py` checks only
that `requirement` is a non-empty string and explicitly tolerates extra keys,
and `designs/requirement_targets.py:52-63` already argues this exact move for
`target` — *"a target is simply another key … living next to `requirement`"*.
So this needs no schema migration and no new table, and `attach_target` is a
template for `attach_intent`. A separate record was rejected as a second
overlapping home for one idea.

**Its vocabulary is open, not a closed enum**, following **Optimizer class**,
which `CONTEXT.md` keeps "stored as an open value, not a hardcoded
two-literal enum" so an approach nobody needs yet has room. A closed set would
already be wrong: Examples 1 and 2 need an effect ("behave as a magnetic
mirror") that no current family serves (#220).

**It is established by interview, not inferred silently.** Requirement intake
becomes a grilling session with whoever speaks for the customer — or a
questionnaire when the customer is reachable and the proxy is not. Provenance
stays `ASSUMED` regardless, on the same reasoning the glossary already gives
for a Requirement target: even confirmed by a human it is a reading of
someone's words, not anybody's measurement. Confirmation rides the separate
status axis.

**Having none is a legal answer.** A bend radius, a mass budget or a cure
ceiling asks nothing of the wave. Forcing every requirement to name an effect
would make the model invent one, which is the failure `UNSCOREABLE` already
exists to prevent for targets.

**It keys the considered-and-dropped ledger.** This is the point. ADR-0025's
ledger records, per design, which families were weighed and why each was set
aside. Without a shared key those lists cannot be compared between designs;
with one, "what else could serve this ask, and why was it dropped last time"
becomes a query. One intended effect served by several families **is** the
trade space, and the charter's promise of options with trade-offs is otherwise
left to whether the model remembers to mention them.

## Consequences

- **Blocked on #205.** `orchestration/tooling.py:237` hardcodes
  `"alternatives": []` at the flush, so every rejected alternative is
  discarded today. ADR-0025 and ADR-0026 are both already blocked on the same
  line. A key for a ledger that cannot be written is worth little, so #205
  lands first.
- **This widens `capability-verdict` beyond fabrication.** `CONTEXT.md`'s
  ledger entry scopes that reason kind to "the current configured fabrication
  capability … equipment changes, so 'we could not build this' must expire
  with the machine that could not build it". A family dropped because the
  requirement's stated curvature exceeds its element's angular stability
  (`S ≤ 2·θ_max·R`, `docs/curvature-effects-on-em-surfaces.md`) is the same
  shape of verdict against a different capability — one stated by the
  requirement rather than configured by the shop, and it must expire the same
  way when that requirement changes. **ADR-0025 needs a dated amendment**
  under ADR-0020's test: its Decision paragraph does not change, only the
  scope of what counts as a capability.
- **The loop still does not infer a family from prose.** Intent narrows
  nothing automatically; it records what was asked and makes what was
  discarded legible. Driving selection from a lookup table was considered and
  rejected as putting code in the business of choosing physics, against both
  `design_families.py:43-45` and the charter's rule that the judgment is the
  model's.
- Architecture is a judgment step and stays unscored (`success_score.py`'s
  `JUDGMENT_STEPS`). Nothing here creates a number to score.

## Corrections

### 2026-09-09 — the anticipated widening of `capability-verdict` didn't happen; a new mechanism did instead

**What this ADR's Consequences said:**

> This widens `capability-verdict` beyond fabrication. ... A family
> dropped because the requirement's stated curvature exceeds its
> element's angular stability... is the same shape of verdict against a
> different capability... **ADR-0025 needs a dated amendment** under
> ADR-0020's test.

**What happened instead.** `/grill-with-docs` revisited this directly:
equipment, ink and material availability were never a sound fit for
`capability-verdict` at all, on ADR-0021's own rule that an unbuildable
candidate is reported, never dropped. Rather than widen
`capability-verdict` to cover both the curvature case and the fabrication
case, ADR-0025's 2026-09-09 correction narrows it to the curvature case
alone and introduces a new, separate **Capability warning** mechanism for
equipment/ink/material shortfalls — one that never drops a candidate,
matching the charter's "present equipment... shape the ranking and the
warnings, never the search."

This ADR's core decision is unaffected: intended effect is still a key on
the requirement, not a record of its own, and it still keys the ledger.
What changes is only the shape of the ledger entry it keys — corrected at
ADR-0025, per ADR-0020's "amend at the ADR that owns the claim."

Separately, ADR-0031 answers how `intended_effect` is actually produced:
via a reviewed Requirements document, not a single-shot answer. This
ADR's own decision — a key on the requirement, not a record of its own —
still stands; ADR-0031 only changes what fills the key in.
