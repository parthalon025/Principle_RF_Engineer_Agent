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
  host-surface curvature, platform, and ground-plane presence (whether the
  host surface is asserted to be a reliable conductive backing) — that
  anchors a request for design guidance. Distinct from a Component's
  specification, which describes an existing manufactured part rather
  than a target for a new one.
- **Requirement target**: the structured interpretation (`value`,
  `comparator`, `unit`, optional `tolerance`) an agent proposes for one
  Customer requirement's prose, so a Success score has something to
  measure a design's progress against (#92). Provenance is always
  `ASSUMED` — even once a human confirms it, it is still nobody's
  measurement, simulation or calculation, just a reading of the customer's
  own words — so confirmation is tracked as a separate `target_status` axis
  (`PROPOSED` → `CONFIRMED`, plus `confirmed_by`/`confirmed_at`) rather than
  inventing a stronger provenance tier. A requirement whose prose yields no
  defensible target is `UNSCOREABLE`, with the reason recorded, never given
  an invented number.
  _Avoid_: a `CONFIRMED` provenance tier — Provenance's eight-value set is
  fixed; confirmation is a trust signal about the reading, not a new kind
  of evidence.
- **Threshold/Objective**: the two values a Requirement target's numeric
  value may carry, adopted from defence-acquisition practice (JCIDS
  Enclosure B, via #122) to settle #117. **Threshold** is the minimum
  acceptable value — a candidate that fails it is rejected outright, so it
  prunes the candidate space. **Objective** is the desired value — among
  candidates that clear the threshold, closer to it scores better, so it
  never prunes. Objective is optional; a requirement giving only a
  threshold is a hard bound with no soft zone to rank on. Hardness is
  asserted, never inferred: a requirement whose threshold and objective
  coincide says so explicitly (`Threshold = Objective`) rather than leaving
  a reader to guess which one a lone number is. The gap between the two is
  the **trade space** a design is actually optimised within. A stated
  preference with no hard floor (e.g. "prefer MXene where it's competitive")
  is an objective with no threshold — so it stays a visible, arguable part
  of the requirement rather than an unstated bias baked into the scorer
  (#105). A "constraint" is not a separate kind of object in this model —
  it is an ordinary requirement whose threshold happens to do the work of
  pruning.
- **Requirement-derived constraint**: a design parameter (a threshold, a
  bend radius, a band) whose value comes from one specific Customer
  requirement. Re-derived fresh every design pass from the requirement's
  own text — never inherited from a prior pass's conclusion, even across
  revisions of the same design, because a guess is not allowed to become
  settled fact merely by having been made before. Contrast **Material-
  property library** entry, the one kind of data this project deliberately
  does carry forward between passes, because it is a fact about a
  material rather than about any one requirement.
- **Material-property library**: a persistent store of physical material
  properties (permittivity, loss tangent, conductivity, etc.), keyed by
  `(material, frequency, property)` rather than by design or requirement —
  a deliberate, named exception to the Requirement-derived constraint
  rule above. An entry accumulates once and is reused by every future
  design that references that material, rather than being re-derived per
  pass. A human adds an entry either by citing a source document (a
  manufacturer datasheet → `MANUFACTURER-SPECIFIED`; a cited paper →
  whatever provenance rung its own original measurement carries) or by
  entering a bare value with a one-line note of where it came from, even
  "no source" — which lands at `ASSUMED`. The library itself never parses
  a document; an uploaded document is the citation/audit trail, not an
  extraction target.
  _Avoid_: material database — this is a growing, per-entry-provenanced
  knowledge record, not a fixed reference table.
- **Family fallback bracket**: what a Material-property library lookup
  returns when no entry exists yet for the specific material asked for —
  a `min, max` range for the material's broad family (e.g. "generic
  polymer," "generic conductor"), never a single point value, each
  independently cited for why it honestly bounds that family. A specific
  material's own library entry always overrides its family's bracket the
  moment one exists, and brackets narrow over time as more per-material
  entries accumulate — the same way the library itself grows. A design
  that scores a candidate from a bracket (or from any `ASSUMED` entry)
  computes the score at both ends of the range rather than collapsing it
  to one number: a decisive property's bracket produces a visibly wide
  spread in the resulting rank — the spread itself is the signal that
  this guess matters — while a minor property's bracket barely moves it.
- **Fabrication capability**: the configured, cross-run set of what a
  specific piece of equipment can currently build — which processes, what
  cure ceiling, what minimum feature size, whether it can embed a discrete
  component — checked per candidate design, the same way a Material-
  property library entry is checked per material: not re-derived per
  requirement, and never hardcoded into the loop's own logic. Three
  independent, easily-conflated stages: **print** (laying down a flat
  pattern — no fabrication process this project uses can produce a solid,
  volumetric shape), **cure** (setting/cross-linking a printed material —
  gated by whether the finished part can leave its host and reach an
  external oven, not by any one machine's own built-in warming plate,
  which exists only to keep ink viscosity steady during printing), and
  **laminate** (bonding an already-cured, separately-built layer onto the
  final host). A design that fails today's capability check is excluded
  from selection with the reason stated, never silently dropped — the
  same treatment a Material-property library miss gets.
  _Avoid_: fabrication route — describes one chosen path through a
  capability, not the configured set a path gets chosen from; printer
  capability — too narrow, since cure and lamination are not properties
  of the printer alone.
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
- **Symbol** (Tier B design family element): a single characterised member
  of a symbol alphabet — its geometry and tuning parameter, its
  characterised reflection response (`|Γ|` and `∠Γ` versus frequency across
  the family's band), a provenance rung *per quantity* rather than one for
  the whole record, and a validity box. Admission requires all three in
  evidence: printed successfully at the declared process conditions,
  geometry measured, and response characterised — so any design built from
  admitted symbols is printable by construction (#130).
- **Symbol alphabet** (design family field, Tier B only): the finite,
  characterised set of symbols a Tier B family assembles designs from by
  choosing and placing them, rather than tuning continuous dimensions.
  Characterised on a continuous parameter but admitting only a quantised
  set as letters — a deliberate deviation from field norm (published
  practice tabulates a continuous phase-versus-parameter curve), traded
  for admission-by-printability and pre-measurability. Turns a family's
  optimizer class from continuous tuning into combinatorial selection and
  placement. Tier A families never declare one (#130).
  _Avoid_: element library — this project's alphabet specifically admits
  only symbols that have been printed, measured, and validity-boxed; a
  generic "library" doesn't carry that admission bar.
- **Validity box**: the stated set of conditions a symbol's or alphabet's
  characterised numbers hold under — pitch, substrate, ink, pass count,
  cure schedule, incidence-angle range, and the neighbour set it was
  characterised against (Marcuvitz's practice, #130/#131). Any change to it
  invalidates the record it covers; a pitch change invalidates an entire
  alphabet's `Δφ_max`, not one symbol's.
- **`Δφ_max`**: the worst-case unlike-neighbour phase error a symbol
  alphabet exhibits at its design pitch — a property of the alphabet, not
  of any one symbol, measured once by comparing a symbol's characterised
  phase curve against the same symbol with its two E-plane neighbours
  swapped for the alphabet's extremes. Sets the phase budget a coding
  block's size must satisfy against the requirement's own RCS-reduction
  target (#130).
- **Design family**: the classification of a design's target physics and
  topology (e.g. absorber, reflection-phase steering surface, polarization
  converter, diffusive-backscatter surface, plain patch antenna) that
  determines which analysis/optimization functions, simulation setup, and
  physical bound apply (see `docs/adr/0018`). Declared as a required
  `design_family` string field on the ARCHITECTURE decision, alongside the
  existing free-form `decision`/`rationale` prose, not left implicit in
  which hardwired function the loop happened to call (`_handle_architecture`,
  #161). This is the minimal-slice implementation only: a bare string, with
  no enum/registry validation that it names a real, known family — that
  belongs to the still-open design family registry (`docs/adr/0018`), which
  also covers the per-family `optimizer_class`/`simulation_adapter`/
  `physical_bound` fields this one does not yet declare. #150 and #151 key
  off this field. Selection stays human-authored: the loop does not attempt
  to infer a family from a requirement's prose.
- **Design family registry**: the open interface every design family
  implements — a thin common set of spine fields (band, host thickness,
  both cell periods, host εr/tanδ, conductor σ, incidence/polarisation
  envelope, ground-plane presence, `R = 3T`, `T ≤ 2mm`) plus family-specific
  fields that differ in *kind*, not just value, across families: design
  variables, analysis function, optimizer class, simulation adapter, and
  physical bound. See `docs/adr/0018` for why this is an open interface
  rather than one fixed schema with optional fields.
  _Avoid_: family schema — implies a single shape every family fills in;
  the per-family parts are genuinely heterogeneous objects, not optional
  slots in a common shape.
- **Simulation tier** (design family field): whether a family's entire
  evaluation is a single unit-cell solve (**Tier A** — absorbers and other
  uniform surfaces, Examples 1, 2, 3, 6) or whether the unit-cell solve only
  populates a phase-versus-parameter lookup that an aperture-level
  evaluation then consumes, because the designed-for behaviour — a steered
  beam, a suppressed backscatter lobe — does not exist at unit-cell level at
  all (**Tier B** — Examples 4, 5, 7). Established in #107. Cross-cuts,
  rather than aligns with, the separate port-count, post-processing, and
  sweep-axis differences between families. Only Tier B families carry a
  symbol alphabet (#130) and an Element/Coding-Alphabet library entry.
- **Physical bound** (design family field): a family's fundamental
  feasibility predicate relating achievable performance to size or
  thickness — e.g. the Rozanov bound for absorbers, the Gustafsson &
  Sjöberg bound for reflection-phase steering surfaces, the Nel,
  Skrivervik & Gustafsson Q-factor bound for patch antennas. A genuinely
  different function with different required inputs per family, not one
  formula with a per-family constant swapped in. Its legal values include
  "none known" — true today for diffusive/coding backscatter-reduction
  surfaces, where no causality-based bound has been published.
- **Optimizer class** (design family field): which optimization approach a
  family's OPTIMIZATION step uses — `CONTINUOUS` (gradient-friendly tuning
  of a few dimensions, e.g. a patch's length) or `COMBINATORIAL`
  (genetic-algorithm search over a pre-characterized symbol alphabet,
  see #130) today. Stored as an open value, not a hardcoded two-literal
  enum: ML-direct inverse design (train once, map a target response
  straight to geometry in a single pass, no search loop) is an established
  third shape in the literature, not yet needed by any family this
  registry serves but real enough to leave room for.
  _Avoid_: treating particle-swarm or simulated-annealing as separate
  values — the literature treats them as siblings of genetic search within
  `COMBINATORIAL`, not distinct classes.
- **Simulation adapter** (design family field): which solver a family's
  SIMULATION step must use — `NEC2` for wire-antenna families,
  `PALACE_FLOQUET` for periodic-unit-cell families. Necessary because
  `_handle_simulation`'s data shape (an arbitrary `geometry` dict) looks
  solver-agnostic but is hardwired to call NEC2, which cannot represent a
  periodic/Floquet boundary — a family that needs one and doesn't declare
  `PALACE_FLOQUET` would silently get a wrong-but-plausible answer.
- **Element/Coding-Alphabet library**: a persistent, cross-run store of
  characterized symbol-alphabet elements (Tier B design families only, see
  #130), keyed by `(element family, substrate stack, frequency band,
  incidence-angle range)` — the same accumulate-once-and-reuse shape as the
  **Material-property library**, holding each symbol's characterized
  response so it is looked up rather than re-solved by every design that
  shares its band and substrate. A pitch or validity-box change
  invalidates the whole alphabet's entries, not one symbol's.
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
