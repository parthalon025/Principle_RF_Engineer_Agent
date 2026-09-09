---
status: accepted
---

# The Requirements document is a CDD-style artifact per design, and ARCHITECTURE gates on its confirmation

`/grill-with-docs` on ADR-0030 (intended effect) asked how the "grilling session
with whoever speaks for the customer" that ADR-0030 already names actually produces
`intended_effect` and a Requirement target. The obvious reading — the interviewing
agent writes one string, done — undersells what ADR-0030 itself already borrows:
`Threshold`/`Objective` (#122) comes from JCIDS Enclosure B, the DoD framework
governing how a program writes down what it needs. That framework doesn't hand a
system a single field; it produces a reviewed document, and the Threshold/Objective
pair specifically lives inside one stage of it — the **Capability Development
Document (CDD)**, which spells out a system's Key Performance Parameters after an
earlier document has already stated the capability gap.

**Decision: requirement intake produces a CDD-style Requirements document, one per
Design, that a human reviews and an LLM revises before anything is extracted from
it.**

Five parts:

**One document per Design, not one per Customer requirement.** A real CDD bundles
every KPP for one system into a single document a reviewer reads once; splitting it
into N disconnected fragments (one per requirement row) would make a reviewer
reassemble the picture themselves. `requirements[requirement_id]` still holds each
requirement row exactly as before — the document is the human-facing artifact those
rows get read out of, not a replacement for them.

**Lifecycle: `DRAFT → UNDER_REVIEW → REFINED → CONFIRMED`.** The interviewing agent
drafts it from the grilling conversation, a human reads it and pushes back, the
agent revises, and the cycle repeats until the human confirms. Every round is kept,
never overwritten — the same instinct that keeps an ADR's own corrections dated and
appended rather than silently rewriting the claim they correct (ADR-0020, ADR-0024).
A reviewer later can see not just what was finally agreed, but what the first draft
got wrong and why it changed.

**`Requirement target` and `Intended effect` are extracted from the confirmed
document, not elicited standalone.** ADR-0030's own decision — that intended effect
is "another key inside a requirement's own entry" — stands unchanged; this only
changes how that key gets filled in. The document is what a human actually argues
with; the extracted fields are the small, structured summary the design loop reads
cheaply, the same relationship a Design's `architecture` map already has to the full
prose `rationale` sitting next to it.

**ARCHITECTURE gates on the document reaching `CONFIRMED`.** `design_family` is
already a required field on the ARCHITECTURE decision (#161); this adds one
precondition upstream of it, at the same checkpoint, rather than a second
independent check on `intended_effect` directly — a confirmed document already
guarantees `intended_effect` exists, so checking the field too would just be the
same gate asked twice. In plain terms: you don't get to pick a physical approach
before the customer's actual ask is locked in.

**Provenance is unaffected.** `intended_effect`/`target` stay `ASSUMED` regardless
of how many review rounds confirm them — per ADR-0030 and #122's existing reasoning,
confirmation is a trust signal about a reading, never a stronger kind of evidence.

## Considered and rejected

- **A single-shot elicitation, no document.** What ADR-0030 implicitly assumed.
  Rejected once the JCIDS parallel was pushed on: a program never locks in a
  capability requirement from one unreviewed answer, and neither should this.
- **One document per Customer requirement.** Rejected: fragments the review into N
  disconnected reads for something a real CDD keeps as one document, and gives a
  reviewer no way to see how a design's several requirements relate to each other.
- **Overwriting the document in place on each revision.** Rejected on the same
  grounds ADR-0020 already settled for ADRs themselves — a correction that erases
  what it corrects destroys the lesson along with the mistake.

## Consequences

- **No schema change to `requirements[requirement_id]`.** The document is new
  persistence (a `design_id`-scoped row with a status and revision history);
  `intended_effect`/`target` land in the same dict keys ADR-0030 and #122 already
  specified.
- **`attach_intent` (ADR-0030's still-unimplemented function) now writes from a
  confirmed document, not from a bare tool argument.** Its own shape is unchanged;
  its caller changes.
- Architecture stays a judgment step and stays unscored (`success_score.py`'s
  `JUDGMENT_STEPS`) — this ADR adds a precondition to when it may run, not a new
  scored output.
- This is a decisions-and-glossary change; implementation (the document's
  persistence, the ARCHITECTURE gate check, `attach_intent`'s new caller) is
  separate, ticketed work.
