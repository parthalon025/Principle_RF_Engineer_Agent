---
status: accepted
---

# A design-loop literature-search tool may find and cite a source, never auto-populate a property entry

`/grill-with-docs` on ADR-0030, closing out **Capability warning** (ADR-0025's
2026-09-09 correction), asked what happens when a warning's gap isn't just "the shop
doesn't have this loaded" but "nobody has ever measured this material's RF
properties at all" — a Material-property or Ink-property library miss with no
vendor datasheet to cite. The charter already commits to closing research gaps
where possible: *"the program closes its own research gaps where it can, and names
them precisely where it cannot."* Today the loop can only search documents a human
has already ingested (`search_knowledge`); discovering a new paper is entirely a
human's job.

Background research this session (`docs/manufacturing-equipment-api-research.md`)
found no usable API for sourcing equipment or bulk material data, but confirmed the
relevant machinery already exists on the literature side: `paper` is an ingestible
source type, and a paper lands at `LITERATURE-SUPPORTED` provenance once ingested
(`CONTEXT.md`'s Evidence hierarchy). What's missing is discovery, not consumption.

**Decision: the design loop gets one narrow tool — search external literature for a
Material-/Ink-property miss — that finds and cites candidate sources. It never
writes a library entry itself.**

- **Scope is exactly the gap, nothing broader.** The tool fires only when a
  Material-property or Ink-property lookup misses and a Capability warning has
  already been raised; it is not a general-purpose research tool available to every
  role at every step.
- **It returns candidates with citations, not settled numbers.** A found paper's
  reported εr/tanδ (or ink resistivity/cure schedule) is surfaced to whoever is
  reviewing the warning — a human, same as any other Material-property library
  entry today — who decides whether to add it. The tool does not call
  `ingest_document` or write to the library on its own.
- **Provenance is unaffected by who found the source.** Once a human adds the entry
  by citing the paper the tool surfaced, it carries the same `LITERATURE-SUPPORTED`
  provenance any manually-found paper would — per `CONTEXT.md`'s closed provenance
  set, there is no separate tier for "found by a tool" versus "found by a person."

## Considered and rejected

- **Auto-populate the library entry from the paper's reported value.** Rejected:
  the same reasoning that already keeps the Material-property library from parsing
  a document itself — *"the library itself never parses a document; an uploaded
  document is the citation/audit trail, not an extraction target"* — applies
  identically whether the document arrived via a human upload or a tool's search
  result.
- **A general-purpose research tool available at any step.** Rejected as unbounded
  scope creep against a narrow, well-understood gap; if a broader need surfaces
  later it can be proposed on its own evidence, not smuggled in here.

## Consequences

- This is new tool surface, not yet built — a separate, ticketed piece of work.
- The equipment and materials-catalog gaps `docs/manufacturing-equipment-api-research.md`
  found have no equivalent tool, because no queryable source exists for either; a
  Capability warning for those stays a citation-only spec (`CONTEXT.md`'s
  **Capability warning**) for a human to research by hand.
