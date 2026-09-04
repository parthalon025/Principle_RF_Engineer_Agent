# Principle_RF_Engineer_Agent

The domain model for an agent that acts as a principal-level RF
(radio-frequency) engineer: reviewing designs, running RF engineering
calculations, and answering questions the way a senior RF engineer would.

This file is a **glossary and nothing else** — it defines what the project's
terms mean, not what is built. What exists and how to run it lives in
[`README.md`](README.md); the reasoning behind hard-to-reverse choices lives
in [`docs/adr/`](docs/adr/); open work lives in GitHub Issues. Keeping
implementation status out of here is deliberate: status churns every merge,
and a glossary that churns with it stops being trustworthy (see
`docs/agents/domain.md`).

## Vocabulary

- **Provenance**: the evidence class of a stated RF result — exactly one of
  `MEASURED`, `SIMULATED`, `CALCULATED`, `MANUFACTURER-SPECIFIED`,
  `LITERATURE-SUPPORTED`, `INFERRED`, `ASSUMED`, `UNKNOWN`. A closed set, and
  the only confidence vocabulary in the project: there is no parallel
  "provisional"/"draft" tag, and no path by which an LLM-estimated confidence
  becomes a `CALCULATED` one. Never state a value without one once the agent
  produces it. A knowledge-base chunk cited by the agent inherits its
  provenance from the source document's **source type**:
  `datasheet`/`application_note` → `MANUFACTURER-SPECIFIED`;
  `standard`/`textbook`/`paper`/`patent` → `LITERATURE-SUPPORTED`. An
  automatically extracted **component** specification field is
  `MANUFACTURER-SPECIFIED` when the extraction was unambiguous, `INFERRED`
  when the read was ambiguous or low-confidence, and `UNKNOWN` when it
  violates a physical-plausibility bound (e.g. a negative noise figure)
  regardless of the extractor's own confidence — there is no human review
  step, so provenance and physical bounds are the only signal a downstream
  user gets that a value should be double-checked.
- **Evidence hierarchy**: measured > validated simulation > deterministic
  calculation > manufacturer spec > authoritative reference > internal
  engineering history > general web material > LLM inference. Higher wins
  when evidence conflicts.
- **Source type**: the classification of an ingested knowledge document —
  `datasheet`, `application_note`, `standard`, `textbook`, `paper`,
  `patent`, or `design_record`. Fixed at ingest time; determines the
  document's default provenance and authority rank.
- **Patent** (a source type): a granted patent or published application.
  Sits at the authoritative-reference tier like a `paper`, but ranks
  deliberately *below* one: a patent office examines for novelty,
  non-obviousness and candor, not for whether a stated number was measured
  correctly or reproduces, so its technical figures are published and
  permanent but not peer-reviewed. Same rank as an arXiv preprint, for the
  same reason (`knowledge/provenance.py`'s `PATENT_AUTHORITY_RANK`).
  _Two things it is not._ It is not a component source — component
  extraction stays restricted to `datasheet`/`application_note`, so a
  patent is never mined for orderable-part specifications. And its
  **claims** are not design guidance: a claim is legal text defining the
  boundary of a monopoly, often describing configurations nobody built or
  measured, whereas the description's worked examples are closer to a
  paper's reported results. Chunking is by text and cannot tell the two
  apart, so a retrieved patent chunk may be either — cite its numbers,
  never read its claim language as a recommendation.
- **Authority rank**: a per-document integer position in the evidence
  hierarchy, defaulted from source type (datasheet/application_note sit at
  the manufacturer-spec tier; standard/textbook/paper sit at the
  authoritative-reference tier) and overridable per document. Knowledge
  retrieval sorts by authority rank before match score, so higher-tier
  evidence surfaces first when sources conflict.
- **Component**: one exact orderable manufacturer part (package and
  tape-and-reel suffix included — a different package is a different
  component, not a variant of the same row), identified by
  `(manufacturer, part_number)`. Its specifications are extracted
  automatically from its datasheet, per field, each carrying its own
  provenance, unit, test condition, and source chunk/page reference.
  _Avoid_: Part, SKU — those don't carry the exact-orderable-code
  distinction this term does.
- **Category**: the fixed classification of a component that determines
  which specification fields it's expected to have — `amplifier`,
  `filter`, `mixer`, `attenuator`, `coupler_splitter`,
  `circulator_isolator`, `switch`, `antenna`, `connector_cable`, or
  `passive_component`.
- **Adaptive EM skin**: the umbrella technology category this repo's
  target designs belong to — a layered, flexible electromagnetic surface
  (metamaterial elements plus an antenna layer and spacer) that mounts on
  a curved or flat host surface to transmit, absorb, reflect, or steer RF
  energy. Not a specific product; a category.
  _Avoid_: EM skin (ambiguous without "adaptive"), smart skin.
- **Conformal antenna**: an antenna designed to mount on and follow a
  curved or non-planar host surface without its resonant frequency,
  gain, or match degrading relative to a flat reference design.
  _Avoid_: Flexible antenna — describes the substrate, not the
  mounting requirement; a flexible antenna mounted flat isn't
  exercising the conformal property.
- **Metamaterial unit cell**: the repeating element (e.g. an elongated,
  passive-magnetic-property element with tailored geometry) whose
  geometry — not material composition — produces an antenna's effective
  permittivity/permeability. The base building block a metamaterial
  antenna design starts from.
  _Avoid_: Meta-atom — an optics-context term, not this project's.
- **Customer requirement**: a stated design target for one antenna/EM-skin
  design — frequency band, gain or VSWR/bandwidth target, form factor,
  host-surface curvature, and platform — that anchors a request for
  design guidance. Distinct from a Component's specification, which
  describes an existing manufactured part rather than a target for a new
  one.
- **Design guidance**: the agent's output for a customer requirement — a
  parameter recommendation (e.g. unit-cell spacing, layer stack, expected
  gain) with rationale tracing back to CALCULATED results and/or
  LITERATURE-SUPPORTED sources. Not a fabrication-ready CAD file or mesh;
  a human still builds the prototype from it.
- **Design/decision record**: an internally-authored write-up of what was
  decided for a prior design, why, and what alternatives were considered —
  ingested as an ordinary `documents` row (`source_type = design_record`,
  CONTEXT.md: Source type) through the same `ingest_document` pipeline as
  any other document, and retrieved via `search_design_records`, a
  `search_knowledge` wrapper scoped to that source type — so a design can be
  checked against precedent before it's proposed. Sits at the "internal
  engineering history" evidence tier (see Evidence hierarchy above): below
  authoritative reference, since it is the team's own experience rather than
  a published authority.
  _Avoid_: conflating with the `decision_records` table (`db/schema.sql`) —
  that table tracks one specific design's own approval-gated decisions
  (`design_id`, `approval_status`) as the design is being made; a
  design/decision record is a separate, searchable knowledge-base document
  about a *past* design, consulted for precedent, not an approval workflow.
- **Test iteration**: evaluating a physical prototype's measured data (a
  Touchstone file from bench/range testing a human ran independently and
  brought back — this system has no live instrument-control path of its
  own, see ADR-0012/ADR-0013) against the customer requirement it was built
  to meet, and recommending specific design revisions. Distinct from
  simulation — the input is real measured hardware data, not a simulated
  result. A lab report may accompany the Touchstone file as unparsed
  supporting context (test conditions, calibration, notes); it is not
  itself a source of extracted numeric data (ADR-0013).
- **Success score**: a `CALCULATED`-provenance, deterministic proximity
  metric — how close a design-loop step's actual numeric result (an
  achieved frequency, a simulated gain, an optimized dimension) lands to
  the customer requirement's own stated numeric target. Computed only for
  steps whose result is numeric and comparable to a stated target
  (`ANALYSIS`/`SIMULATION`/`OPTIMIZATION`/`VERIFICATION`/`CORRELATION`); a
  human judgment step (`ARCHITECTURE`/`REDESIGN_DECISION`) has no success
  score. Never an LLM-estimated confidence number standing in for the real
  metric — an optional `INFERRED`-tagged narrative note may ride alongside
  one for context a formula can't capture, but never replaces it (ADR-0014).
  _Avoid_: confidence, probability — both suggest a subjective estimate,
  which this explicitly is not.
- **Design**: a `designs` row — a named, revisioned unit of engineering work
  (`design_key`, `name`, `revision`, `status`) that `requirements`,
  `architecture`, engineering results, decisions, and verification all hang
  off of via `design_id`. `status` is `docs/OPERATIONS.md`'s existing
  workflow lifecycle, not a value set invented for this feature area:
  `DRAFT → ANALYSIS → SIMULATION → OPTIMIZATION → VERIFICATION →
  CONDITIONAL-PASS/PASS/FAIL/BLOCKED → RELEASED`. A design is created in
  `DRAFT` and moves one legal step at a time: it cannot skip a stage, cannot
  reach `RELEASED` without a signed human-approval receipt, and cannot move
  at all once `RELEASED` — a released design gets a new `revision` rather
  than being edited back into engineering. Work in progress can become
  `BLOCKED` from any stage, and `FAIL`/`BLOCKED`/`CONDITIONAL-PASS` return to
  `ANALYSIS` for rework (see `docs/adr/0007`).
  `requirements` is `{requirement_id: {requirement: <text>, ...}}`, keyed
  the same way `verification_items.requirement_id` references it.
  `architecture` is a functional-block map,
  `{block_name: {component_id, role, ...}}`, where `component_id` is a real,
  write-time-validated foreign reference into `components` — never a
  free-text part number — so a design's evidence trail can be traced from a
  functional block to the exact orderable part backing it (see
  `docs/adr/0006`).
- **Engineering result**: an `engineering_results` row, recorded
  automatically as a side effect whenever a calculation/Touchstone/
  simulation tool runs with a `design_id` supplied — never a separate,
  rememberable logging step. Its `provenance` is a static per-tool-category
  mapping (`calculate_*`/Touchstone analysis → `CALCULATED`,
  `run_nec`/`run_openems`/`run_hfss` → `SIMULATED`), not caller-supplied.
  `confidence` is `NULL` for deterministic calculations — a meaningful
  signal only for simulation convergence or extraction ambiguity, not for
  arithmetic that's either right or an exception.
- **Decision record**: a `decision_records` row logging a judgment-laden
  design choice between real alternatives (contrast **Engineering result**,
  which is a mechanical readout with no judgment in it). Unlike component
  extraction (ADR-0003) or engineering results, logging one is an agent
  judgment call, not a structural trigger — there's no physical-plausibility
  check standing in for "was this the right trade-off" the way `UNKNOWN`
  substitutes for a human on a bad datasheet read. Every decision starts
  `approval_status = 'PENDING'`; see `docs/adr/0005` for what that gate
  does and does not yet do. `record_key` (globally unique) follows
  `{design_key}-{slug}`; reusing one is rejected with a pointer to the
  existing record, same dedup-and-point-back shape as `ingest_document`'s
  checksum check.
- **Verification item**: a `verification_items` row tracking one
  requirement's status (`NOT VERIFIED` default, `PASS`/`FAIL`/`MARGINAL`),
  auto-created per key in a design's `requirements` at design-creation time
  so every stated requirement is guaranteed a row, but populated only by an
  explicit `verify_requirement` call — never inferred by matching an
  `engineering_results` name against a `requirement_id`, since a wrong
  automatic match would be a silently wrong verification.

- **Golden query**: a question paired with the knowledge-base documents that
  ought to answer it, held in `verification/golden_queries.json`. The fixed
  set of them is what lets a change to embedding, chunking or ranking be
  scored: without known-right answers, a retrieval regression and a retrieval
  improvement look identical. Expected documents are named at document
  granularity, never chunk — which chunk of a paper answered a question is not
  a stable thing to assert.
  _Avoid_: test query — these are graded against known answers, not merely
  executed.
- **Reference case**: a simulation problem whose correct answer is published
  independently of this codebase (e.g. a half-wave dipole's 73 + j42.5 ohm
  feed impedance), run end to end through a solver adapter so the deck we
  generate, the solver, and the parser are checked together. Distinct from the
  adapter's own tests, which use hand-built fakes and can only show that we
  talk to the solver correctly, not that the solver told us the truth. Passing
  one is what would let `SIMULATED` mean *validated* simulation in the
  **Evidence hierarchy** above.
  _Avoid_: benchmark — that measures speed, not correctness.

`/domain-modeling` should keep extending this section as more terms and
decisions get resolved (see `docs/agents/domain.md`).
