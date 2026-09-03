---
status: accepted
---

# The design loop's MEASUREMENT step accepts only externally-obtained results; a lab report may accompany one as unparsed context

Follows directly from ADR-0012: with `measurement/vna.py` and the rest of
the instrument-actuation package gone, `orchestration/design_loop.py`'s
`MEASUREMENT` step has no live-instrument path left to offer as an
alternative. This ADR settles what replaces it, not just that something
must.

**The sole data source is a human bringing back a Touchstone (.sNp) file
from testing they ran independently** — a bench or range measurement on
whatever equipment was at hand, with no SCPI/VISA connection to this system
at all. It is parsed via the existing `rf_tools/touchstone.py`
`analyze_touchstone` (Phase 2, unmodified) and tagged `MEASURED` provenance
— this project's evidence hierarchy (`CONTEXT.md`) ranks data by how it was
obtained (a real physical-instrument reading), not by whether this system
watched the instrument produce it, so a Touchstone file the user hands back
earns exactly the same top-tier provenance a live-actuated VNA reading
would have.

**A lab report may be attached alongside the Touchstone file as supporting
context — test date, range/chamber, calibration standard, ambient
conditions, a PDF or free-text write-up — but its contents are not
automatically parsed for numbers.** A human transcribes whatever value
matters into the structured Touchstone data; the report itself rides along
for audit trail, not as a second data-extraction path. Considered and
rejected for this pass: reusing `knowledge/ingest.py` + `knowledge/
extract.py`'s provenance-aware document-extraction pipeline — the same
per-field MANUFACTURER-SPECIFIED/INFERRED/UNKNOWN discipline ADR-0003
established for datasheet component extraction — to auto-extract measured
values directly from an unstructured lab report. Rejected as a materially
larger feature (a new document `source_type`, a new extraction field schema
tuned to measurement semantics rather than component specs, its own test
suite and its own provenance-mapping questions) that deserves a dedicated
grilling session rather than riding in as a sub-decision of this one. "Up to
lab reports" is honored as *attachable context of any kind*, not as an
auto-extracted data source — yet.

## Consequences

- `MEASUREMENT`'s `GATED_STEPS` membership is unchanged: advancing past it
  still requires a `LoopStepApprovalReceipt` — the business decision "should
  this design accept this measurement evidence at all" is unaffected by
  where the data came from.
- No dual-mode branching is needed in `_handle_measurement` — with the
  live-instrument path gone (ADR-0012), external results are simply the only
  path, not a fallback alongside one.
- A future "auto-extract from lab reports" feature, if built, is additive on
  top of this: the Touchstone-file path this ADR settles keeps working
  unchanged either way.
