---
status: accepted
---

# Material properties persist in a cross-run library; requirement-derived constraints still don't

Issue #104's wayfinder map ("Printed metamaterial EM skin design loop") had
already established, as an informal standing preference, that a design
pass never inherits a prior pass's conclusions: each pass re-derives its
constraints fresh from the original customer requirement, because a guess
must not become settled fact merely by having been made before. Ticket
#127 ("What does the loop do with a substrate that has no permittivity
data at all?") ran into the case that convention doesn't obviously cover —
a candidate material with no usable property data at all — and grilling
it surfaced that material data is not the same kind of thing as a
requirement-derived constraint, and needed its own decision.

**Decision: material properties (permittivity, loss tangent, conductivity,
etc.) are a deliberate, named exception to the no-inheritance rule.** A
threshold or a bend radius is a fact about one customer requirement; a
material's εr at 10 GHz is a fact about the material, true regardless of
which requirement is asking. So filled-in material data lives in a
persistent **Material-property library** (`CONTEXT.md`) that accumulates
across every run, for any requirement, rather than being re-derived per
pass.

**How an entry is added.** A human either cites/uploads a source document
— a manufacturer datasheet lands at `MANUFACTURER-SPECIFIED`, a cited
paper carries whatever rung its own original measurement had (the same
convention already in use for literature-sourced data reaching this
project as `LITERATURE-SUPPORTED`) — or types a bare value with a
one-line note of where it came from, even "no source, just entering it,"
which lands at `ASSUMED`. The library never parses an arbitrary document
itself; a human transcribes the number, and the upload is the
citation/audit trail, not an extraction target. This directly follows
ADR-0013's precedent for the `MEASUREMENT` step's lab report ("a human
transcribes whatever value matters into the structured data; the report
itself rides along for audit trail, not as a second data-extraction
path") — that ADR considered and rejected auto-extracting numbers from
unstructured documents as "a materially larger feature... that deserves
a dedicated grilling session rather than riding in as a sub-decision,"
and this decision makes the same call for the same reason, for a
different kind of document.

**When no entry exists at all.** The lookup falls back to a **Family
fallback bracket** — a cited range for the material's broad family
(generic polymer, generic conductor, etc.), never a single borrowed point
value. A point value was considered and rejected: #127's own worked
example (Laird Eccosorb BSR/MFS, whose datasheet publishes attenuation
only) and its earlier one (TPU, whose "no data anywhere" turned out to be
a fetch failure, not a fact) both show that a single number borrowed from
"something similar" quietly decides the result for whichever property
matters most to the objective — for an absorber, that's the substrate's
loss, so a bad point guess there is assuming the answer, not a rounding
error.

## Considered and rejected

- **Silently excluding a candidate with no data.** Makes the loop's own
  knowledge gaps invisible — #127's TPU history is a direct demonstration
  of an absence that was actually a fetch failure, discovered only because
  someone kept looking.
- **A single borrowed point value** from a chemically or structurally
  similar material. Rejected for the reason above: it hides exactly how
  much the guess could be wrong, for the property most likely to decide
  the score.
- **The loop parsing arbitrary datasheets/papers itself.** Rejected as
  out of scope for this decision — a document-understanding project, not
  a data-entry-with-citation one.

## Consequences

- Any score built from a Family fallback bracket, or from an individual
  `ASSUMED` library entry, is computed at both ends of the range rather
  than collapsed to a point. A guess on a decisive property produces a
  visibly wide spread in the resulting rank; that spread is the warning,
  with no separate per-property "is this too important to guess" rule
  needed.
- A per-run toggle (default **on**, matching issue #117's "silence is
  permissive") lets a human exclude family-bracket-guessed candidates from
  a given run's ranked output for a conservative, pre-fabrication pass.
  Excluded candidates are still listed with the reason — nothing vanishes
  from the output without a trace, toggle or not.
- This is a plan-only decision (issue #104's map is explicitly plan-only);
  no code changes accompany it. Implementation — the library's storage,
  the upload/entry UI, the fallback-bracket table's actual family list —
  lands as separate `ready-for-agent` issues once the design-loop spec is
  otherwise complete.
