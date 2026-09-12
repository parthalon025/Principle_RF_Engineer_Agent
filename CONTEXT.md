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
  `LITERATURE-SUPPORTED`, `INTERNAL-HISTORY`, `INFERRED`, `ASSUMED`,
  `UNKNOWN`. A closed set, and the only confidence vocabulary in the
  project: there is no parallel "provisional"/"draft" tag, and no path by
  which an LLM-estimated confidence becomes a `CALCULATED` one. Never
  state a value without one once the agent produces it. A knowledge-base
  chunk cited by the agent inherits its provenance from the source
  document's **source type**:
  `datasheet`/`application_note` → `MANUFACTURER-SPECIFIED`;
  `standard`/`textbook`/`paper`/`patent` → `LITERATURE-SUPPORTED`;
  `design_record` → `INTERNAL-HISTORY`, which sits below published
  authority because it is the team's own prior write-up rather than an
  outside source (`knowledge/provenance.py`). An
  automatically extracted **component** specification field is
  `MANUFACTURER-SPECIFIED` when the extraction was unambiguous, `INFERRED`
  when the read was ambiguous or low-confidence, and `UNKNOWN` when it
  violates a physical-plausibility bound (e.g. a negative noise figure)
  regardless of the extractor's own confidence — there is no human review
  step, so provenance and physical bounds are the only signal a downstream
  user gets that a value should be double-checked.
  _Avoid_: Provenance ladder as a name in its own right — the ladder
  metaphor is fine and "rung" is used throughout, but the phrase blurs two
  things this glossary keeps apart: Provenance is the closed set of nine
  labels, and **Evidence hierarchy** is the order they are compared in.
  Name whichever one you mean.
- **Evidence hierarchy**: measured > validated simulation > deterministic
  calculation > manufacturer spec > authoritative reference > internal
  engineering history > general web material > LLM inference. Higher wins
  when evidence conflicts. Its ranks name Provenance values in order —
  `MEASURED`, `SIMULATED`, `CALCULATED`, `MANUFACTURER-SPECIFIED`,
  `LITERATURE-SUPPORTED`, `INTERNAL-HISTORY`, then `INFERRED` — with two
  deliberate gaps at the join: **general web material** is a rank with no
  Provenance value, because no source type ingests it, and `ASSUMED` and
  `UNKNOWN` are values with no rank, because both mark the *absence* of
  evidence rather than a kind of it. So the hierarchy orders seven of the
  nine values, and a conflict involving `ASSUMED` or `UNKNOWN` is not
  settled by rank.
  *In plain terms: this is the tie-breaker for "two sources disagree, which
  do we believe?" — and two of the nine labels mean "we have no source at
  all," which is why they are not in the running.*
- **Source type**: the classification of an ingested knowledge document —
  `datasheet`, `application_note`, `standard`, `textbook`, `paper`,
  `patent`, `partner_research`, or `design_record`. Fixed at ingest time;
  determines the document's default provenance and authority rank.
- **Partner research** (a source type): unpublished technical work received
  from an outside research partner — a proposed design, a memo, an internal
  report someone shares. Resolves to `LITERATURE-SUPPORTED` like a `paper`
  or a `patent`, but ranks below both and above `design_record`
  (ADR-0029). Below, because nothing examined it: no peer review, no patent
  office. Above internal history, because it is genuinely outside work
  rather than the team's own prior write-up. The two obvious alternatives
  are both wrong in ways that propagate — filing it as a `paper` puts an
  unreviewed proposal ahead of a granted patent in every search, and filing
  it as a `design_record` makes the corpus claim a partner's work as ours.
  *In plain terms: a partner's good idea is worth more than our own old
  notes and less than something a journal or an examiner has checked.*
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
- **Host surface**: the surface an Adaptive EM skin is applied to, supplied
  by each Customer requirement and never a project constant. **Described by
  the properties it carries, never by what it is**: the range is unbounded —
  a sticker, a PET film, an aircraft wing, a hull, an sUAS body, or
  something living (`docs/mxene-voltera-nova-printability.md` records
  printing demonstrated "on curved substrates and even on leaves and
  fruit"). No closed list of host types is possible, so no design decision
  may key on one.
  Five properties gate a design, and each is supplied, not assumed: its
  **radius of curvature**, which drives bend radius, which drives substrate
  class; **whether the finished part can leave it and reach an external
  oven**, which is what actually decides which conductors survive the cure
  ceiling — not substrate class, a claim corrected on #105 — and is the
  cure stage's own gate (see Fabrication capability); **whether it is a reliable
  conductive backing**, which a requirement asserts and the loop never
  infers (ADR-0017); its **own εr/tanδ and thickness**, where it
  participates electromagnetically; and its **extent**, which bounds how
  much of a pattern fits.
  *In plain terms: the loop never asks whether it is looking at a wing or an
  animal. It asks how sharply the thing curves, how hot it may get, whether
  it conducts, and whether the part can come off to be baked.*
  _Avoid_: Substrate — the printed or laminated dielectric the elements sit
  on, which is a different layer; a skin has both a substrate and a host.
  Platform — names a vehicle class rather than a surface, and a host need
  not belong to one.
- **Geometry layer role**: the closed, five-value vocabulary (`HOST`,
  `SUBSTRATE`, `REFLECTOR`, `SPACER`, `PATTERN`) a materials/conductors
  geometry primitive's optional `role` field is validated against
  (`simulation/meep.py`'s `GeometryRole`, issue #485) — the code-level
  counterpart to this same Host surface/Substrate distinction, plus the
  Reflector/Spacer/Pattern layers ADR-0033's own recommended-cell table
  names. Purely additive metadata: a primitive with no `role` stays exactly
  as legal as before, and the tag is never read when building the actual
  simulated material — an untagged conductor and one tagged `REFLECTOR`
  simulate byte-for-byte the same object. At most one primitive across a
  geometry's combined materials and conductors may carry `REFLECTOR` — a
  design has one ground plane by construction — while `PATTERN` carries no
  such cap, since ADR-0033's own absorber design coplanar-prints two
  different-function inks in one pattern layer.
  *In plain terms: a label on one physical slab or wire saying which job in
  the stack it's doing — ground plane, spacer, antenna substrate, host, or
  printed pattern — checked against a fixed list of five, and never
  smuggled into the physics the simulator actually computes.*
  _Avoid_: inferring a primitive's role from its position or material
  properties — `role` is an explicit, optional tag, not something derived
  from `epsilon_r`/`center_m`/shape. Metamaterial unit cell — a role tags
  which job ONE primitive does in the stack; a unit cell is the repeating
  sub-wavelength structure that may itself be built from several
  role-tagged primitives (e.g. a `PATTERN` layer over a `REFLECTOR`).
- **Metamaterial unit cell**: the repeating element whose **sub-wavelength
  structure** produces an effective permittivity/permeability the bulk
  material does not have on its own. The base building block a
  metamaterial design starts from.
  The structure is usually a **patterned conductor** (US12089385B2's
  Example 3 is an I-shaped ring resonator over a cut wire), but it need not
  be: **Example 1 gets its magnetic response from Mie resonance in
  strontium titanate**, at a permittivity FIG. 5C gives as
  **ε₁ = 250 − 1.25j** (Example 2 is 294 − 0.5j), and **Example 5 uses a
  tunable BST film**. *In plain terms: most of these work by the shape you
  print, but some work by what the material itself is made of.* An earlier
  version of this entry said the effect came from geometry "not material
  composition," which three of the patent's own seven examples contradict
  (#113). Cite the drawings, not the prose: the prose figure of εr = 310
  is not what Example 1 was simulated with (#107).
  _Avoid_: Meta-atom — an optics-context term, not this project's.
- **Supercell**: a block of identical **Symbols** repeated side by side on a
  coded surface, so each symbol sits among neighbours like itself and
  behaves as it did when it was characterised. Its size is never a project
  constant — it is derived per **Customer requirement** from the
  RCS-reduction target, which sets a phase budget
  `δ = 2·arcsin(10^(−RCSR_dB/20))` that the coupling error at the block's
  edges must stay inside (`docs/supercell-sizing-rule.md`, #130).
  *In plain terms: identical tiles are laid in patches because a tile
  misbehaves when the tiles beside it are different, and how big a patch
  has to be falls out of how much radar reduction the customer asked for.*
  _Avoid_: super-cell — the hyphenated spelling is in live use (#187 and
  several docs), but the code and both filenames carry the unhyphenated
  one, so that is the spelling to write.
- **Customer requirement**: a stated design target for one antenna/EM-skin
  design — frequency band, gain or VSWR/bandwidth target, form factor,
  host-surface curvature, platform, and ground-plane presence (whether the
  host surface is asserted to be a reliable conductive backing) — that
  anchors a request for design guidance. Distinct from a Component's
  specification, which describes an existing manufactured part rather
  than a target for a new one.
- **Host ground-plane assertion**: the captured, confirmable claim that a
  Customer requirement's ground-plane-presence field carries — whether the
  Host surface is a confirmed, reliable conductive backing (`value` in the
  vocabulary this entry names is `True`/`False`, never inferred from what
  the host physically is). Stored at
  `requirements[requirement_id]["host_ground_plane"]`, `attach_target`'s
  and `attach_intent`'s third sibling, and tracked through the identical
  `PROPOSED` → `CONFIRMED` lifecycle a **Requirement target** uses
  (`confirmed_by`/`confirmed_at`, provenance always `ASSUMED` even once
  confirmed, for the same reason a Requirement target's is). This is what
  ADR-0017's "asserted, never inferred" rule needs a place to live: the
  design loop defaults every base printed layer to its own reflector, and
  may only rely on the host surface itself once this field reaches
  `CONFIRMED` — a `PROPOSED`, unconfirmed reading is not enough.
  _Avoid_: inferring this from the host surface's stated material or
  platform (a "solid aluminum wing" is not itself a `CONFIRMED` assertion
  until a human confirms the reading) — ADR-0017 forbids exactly that
  inference.
- **Requirements document**: a CDD-style artifact, one per **Design**,
  bundling every one of that design's **Customer requirement** rows into a
  single reviewed document — modelled on the DoD's JCIDS **Capability
  Development Document**, the same real-world framework this project
  already draws **Threshold/Objective** from. Produced by an interview
  with whoever speaks for the customer, then moves through
  `DRAFT → UNDER_REVIEW → REFINED → CONFIRMED`: a human reads it and
  pushes back, the interviewing agent revises, and the cycle repeats until
  the human confirms it. Every round is kept, never overwritten — the same
  instinct that keeps an ADR's own corrections dated and appended rather
  than silently rewriting the claim they correct. A **Requirement
  target** and an **Intended effect** are *extracted from* a `CONFIRMED`
  Requirements document rather than elicited as standalone answers; the
  document is what a human actually reads and argues with, and those
  fields are the small, structured, machine-read summary the design loop
  operates on. The ARCHITECTURE decision may not run until a design's
  Requirements document reaches `CONFIRMED` (ADR-0034) — you don't pick a
  physical approach before the customer's actual ask is locked in.
  _Avoid_: treating this as a replacement for `requirements[requirement_id]`
  — it produces the values that dict already carries; it doesn't hold them
  itself.
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
  _Avoid_: a `CONFIRMED` provenance tier — Provenance's nine-value set is
  fixed; confirmation is a trust signal about the reading, not a new kind
  of evidence.
- **Intended effect** (of a Customer requirement): what the requirement
  wants done to the wave — absorbed, reflected in phase, steered,
  transmitted, scattered diffusely, polarisation-converted, shielded
  against. Distinct from a **Design family**, which is a *mechanism* that
  might deliver it: one intended effect is typically servable by several
  families, and **that one-to-many mapping is the trade space a set of
  candidates is drawn from**. "Reduce radar return" is answered both by an
  absorber, bounded by Rozanov's thickness-versus-bandwidth inequality, and
  by a diffusive/coding surface, which carries no published bound at all —
  physically different routes with different costs and different
  confidence.
  Established by interview with whoever speaks for the customer rather than
  inferred silently — concretely, by producing and refining a
  **Requirements document** — and then tracked exactly like a
  **Requirement target**: provenance is always `ASSUMED`, because it is a
  reading of someone's words and not anybody's measurement, with
  confirmation carried on a separate status axis rather than a stronger
  provenance tier. Its
  vocabulary is **open, not a closed enum** — the same reasoning as
  **Optimizer class**, stored as an open value so an approach nobody needs
  yet has room to exist.
  **A requirement may legitimately have none, and saying so is an answer
  rather than a gap.** A bend radius, a mass budget or a cure ceiling asks
  nothing of the wave. Such a requirement still constrains the
  electromagnetic design and may remove a whole family from the trade space
  — a coding surface tolerates only `S ≤ 2·θ_max·R` of arc before its cells
  sit outside their **Validity box**'s incidence-angle range
  (`docs/curvature-effects-on-em-surfaces.md`) — and that exclusion is a
  `capability-verdict` in the **Considered-and-dropped ledger**, so it
  expires if the stated curvature changes.
  *In plain terms: what the customer wants to happen to the radio wave, as
  opposed to which trick you use to make it happen.*
  _Avoid_: Objective — taken, and means the desired value of a numeric
  target (**Threshold/Objective**). Function — taken as a loop
  `step_output` key naming the calculation that ran. Mechanism — ADR-0022's
  **Mechanism claim** is a predicted ordering, not a physical effect.
  Designed-for behaviour — describes a family's property, not a customer's
  wish.
- **Shielding effectiveness (SE)**: how much of an incident wave a material
  stops from passing *through* it, in dB, measured on a two-port
  transmission fixture. Not comparable with reflection loss (a one-port,
  metal-backed quantity) or with absorptivity — different quantities on
  different fixtures, and citing one as if it were another manufactures a
  comparison the data doesn't support. For a skin that prints its own
  reflector (ADR-0017), transmission is zero by construction, so SE is
  effectively infinite and carries no design information — there is
  nothing left for a design to trade off. `shielded against` is already a
  listed **Intended effect** value with no **Design family** behind it — a
  gap, not a synonym.
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
  material rather than about any one requirement
  (`docs/requirement-derived-thresholds.md`, #110/#112/#115;
  `designs/material_properties.py` names it as the contrast case).
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
- **Ink-property library**: a persistent store of what one purchasable ink
  is and what its datasheet says it becomes when printed a stated way
  (volume resistivity, recommended cured thickness, cure schedule,
  viscosity), keyed by `(ink, process state, property)`. That process axis
  is exactly what a **Material-property library** entry has no room for,
  and it is the reason this is a separate store: an ink's electrical
  behaviour is not a property of the ink alone — the same ink at 6 µm,
  12 µm and 24 µm is three different sheet resistances, and MXene's
  conductivity depends on whether it was cured and at what temperature.
  One of three libraries that split a single question between them:
  Ink-property is *what you buy*, **Fabrication capability** is *what a
  machine can lay down*, and Material-property is *what the cured film
  then is, electromagnetically, at frequency*. A printable candidate is
  therefore a `(machine, ink, material)` triple, and the loop enumerates
  triples rather than assuming one of each
  (`docs/fabrication-capability-and-ink-library-spec.md`, #106).
  _Avoid_: ink database, and folding ink into the Material-property library
  — the missing process axis is the whole reason the two are separate.
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
  a human still builds the prototype from it. This is the sense meant by
  the rule that a patent's claim language is never design guidance
  (`knowledge/provenance.py`, `agent/main.py`, `mcp_server/server.py`).
  _Avoid_: using the bare phrase for a *ticket's* implementation advice —
  several modules say "this ticket's own design guidance"
  (`optimization/gradient.py`, `simulation/hfss.py`, and others) meaning
  what the issue told the author to build, which is a different thing
  entirely. Say "the ticket's guidance" for that and keep Design guidance
  for what the agent hands the customer.
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
- **Prediction**: a stated expected value for the quantity a Success score
  will later measure, recorded *before* the evaluation that produces it —
  the fast tier's counterpart to the expected values the loop already
  compiles before a bench trip. Provenance is always
  `INFERRED`: it is an LLM's reading of the physics made before any
  evidence exists, and it never becomes `CALCULATED` because the solver
  later computed a matching number. Carries its own tolerance, which must
  be narrower than the decision it informs — a prediction whose band
  cannot separate a pass from a fail against the requirement's own
  Threshold is `UNSCOREABLE` by construction, never `CONFIRMED` (#194).
  *In plain terms: the machine writes down its guess before it looks, and
  a guess loose enough to be right either way does not count.*
  _Avoid_: estimate, guess, expectation — all three suggest something that
  may be revised once the answer is known, and a Prediction's entire value
  is that it was frozen first.
- **Prediction status**: whether a Prediction has been tested against the
  result it predicted — `PREDICTED` → `CONFIRMED`/`REFUTED`, plus
  `UNSCOREABLE` for a candidate that failed at an earlier step and never
  produced the number its prediction was about. A separate axis from
  Provenance, on the same reasoning as a Requirement target's
  `target_status`: Provenance says what kind of evidence a value is,
  status says whether anything has checked it. Display-only — it never
  affects ranking or `score_percent` (#112) — and it may steer which
  candidates get proposed next, never how any candidate is scored (#194).
  _Avoid_: a `REFUTED` provenance tier, or a "validated"/"unvalidated"
  confidence tag — Provenance's nine-value set is fixed and is the only
  confidence scale in the project.
- **Mechanism claim**: the single statement of *why this batch* that
  accompanies a batch of LLM-proposed candidates, written as a testable
  ordering over them ("the shortest candidate scores worst") rather than
  as prose. Carries its own Prediction status, tested against the ranking
  the batch actually produced rather than against any one value — so a
  batch whose every Prediction lands inside tolerance can still be
  `REFUTED` on its mechanism. *In plain terms: predicting the answer and
  being right about why are different things, and only the second one
  teaches you anything.* (#194)
  _Avoid_: hypothesis — too broad; a Mechanism claim is specifically about
  the ordering one batch expects, not about the design or the physics at
  large.
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
- **Letter**: a **Symbol** that has passed admission and is an entry in the
  **Element/Coding-Alphabet library**. Every letter is a symbol, but a
  symbol only described in a paper, with no run of its own here, is not a
  letter at any provenance — it stays a candidate in the
  **Considered-and-dropped ledger** (ADR-0027). Admission is by either of
  two routes (ADR-0027, ADR-0053): **printed and measured** (`MEASURED`
  provenance, always carries a **Process record**), or **simulated on a
  solver path with a passing Reference Case** for its problem class
  (`SIMULATED` provenance, no Process record — nothing was printed, and
  that absence is itself how a simulated letter is told apart from a
  measured one in the same table, with no extra field needed). A simulated
  letter states which Reference Case backed it, or that none exists yet
  for its problem class, and is never withheld for lacking one
  (ADR-0028). Provenance is never upgraded in place: a later print-and-
  measure of the same shape is a second, separate letter, not this one
  promoted, because identity already includes the process — *"the same
  outline printed in carbon and in MXene is two letters, not one letter
  under two conditions"* (#132) applies the same way to a simulated
  version and its later-printed twin.
  *In plain terms: a letter used to mean only a shape actually printed and
  measured. It now also covers a shape a validated simulator vouched for —
  but the record says which kind it is, and a printed letter still
  outranks a simulated one whenever the two disagree (Evidence hierarchy).*
  _Avoid_: treating a simulated letter as equivalent evidence to a printed
  one — Provenance and the Evidence hierarchy keep them ranked apart;
  nothing here promotes one into the other automatically. Also avoid using
  "letter" for a shape with no run of its own at all — that is a **Symbol**
  described elsewhere at best, and a candidate at worst.
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
- **Ligature**: characterising a whole **Supercell** as one unit — solving
  the block full-wave rather than assembling it from its symbols'
  individual characterised responses. The name and the pattern are adopted
  from published practice, which reaches for it for the same reason this
  project does: once a cell sits beside unlike neighbours, its own
  characterisation stops holding
  (`docs/element-library-prior-art.md` §5). **The pattern is adopted; the
  sizing rule is this project's own** — every block size found in the
  literature was set by something other than a coupling-error budget, so
  `docs/supercell-sizing-rule.md` derives it here from the requirement's
  RCS-reduction target instead.
  *In plain terms: when tiles misbehave next to unlike tiles, you stop
  modelling one tile and start modelling the whole patch.*
  _Avoid_: treating it as a synonym for **Supercell** — the supercell is
  the block of identical symbols; the ligature is the decision to
  characterise that block as a single object.
- **Design family**: the classification of a design's target physics and
  topology (e.g. absorber, reflection-phase steering surface, polarization
  converter, diffusive-backscatter surface, plain patch antenna) that
  determines which analysis/optimization functions, simulation setup, and
  physical bound apply (see `docs/adr/0018`). Declared as a required
  `design_family` string field on the ARCHITECTURE decision, alongside the
  existing free-form `decision`/`rationale` prose, not left implicit in
  which hardwired function the loop happened to call (`_handle_architecture`,
  #161). ARCHITECTURE itself may not run until the design's **Requirements
  document** reaches `CONFIRMED` (ADR-0034). The name is validated against the Design family registry
  (`designs/design_families.py`, #109/ADR-0018): an unrecognised family is
  rejected at the ARCHITECTURE step rather than persisted as a grouping key
  nothing downstream recognises. The caller's own spelling is kept verbatim,
  never silently rewritten, and the registry's canonical name is kept
  alongside it as its own field, so a run written as `patch_antenna` and one
  written as `PATCH` still group together (ADR-0037). #150 and #151 key off
  the canonical field, not the raw one. Selection stays human-authored: the
  loop does not attempt to infer a family from a requirement's prose.
  Both the raw spelling and the canonical name persist through the ADR-0011
  flush (#167, #408): `db/schema.sql`'s `decision_records` table has nullable
  `design_family`/`design_family_canonical` columns, and
  `orchestration/tooling.py`'s `_flush_target_for`/`_flush_decisions` write
  both for every `architecture_decision`/`redesign_decision` row --
  `design_family_canonical` carries the value `design_loop.py`'s
  ARCHITECTURE step already computed
  (`design_family_registry`/`canonical_name`) through the flush boundary
  rather than re-deriving it on read, so #150 and #151 can read a real
  grouping key back out via `read_design` rather than only seeing it in one
  design-loop session's in-memory state.
  `_handle_architecture` always states `design_family` (and, alongside it,
  the registry's canonical name), but `_handle_redesign_decision` never asks
  for either — `_flush_decisions` reconciles that by carrying forward the
  most recently stated value of each to every decision recorded after it,
  rather than persisting `NULL` for a redesign decision that is, in fact,
  about a perfectly well-known family (the one its iteration's own
  ARCHITECTURE step already declared); see that function's own docstring,
  "DESIGN_FAMILY CARRY-FORWARD," for the full reasoning.
- **Design family registry**: the open interface every design family
  implements — a thin common set of spine fields (band, host thickness,
  both cell periods, host εr/tanδ, conductor σ, incidence/polarisation
  envelope, ground-plane presence, `R = 3T`, `T ≤ 2mm`) plus family-specific
  fields that differ in *kind*, not just value, across families: design
  variables, analysis function, optimizer class, simulation adapter, and
  physical bound. See `docs/adr/0018` for why this is an open interface
  rather than one fixed schema with optional fields.
  Implemented in `designs/design_families.py`. It resolves the ambiguity
  ADR-0018 named as its reason for rejecting a fixed schema — a bare `None`
  could not distinguish "this family has no bound" from "we have not read
  the bound this family has" — by giving those two states distinct types.
  `DIFFUSIVE` genuinely has none; `REFLECTION_PHASE`'s Gustafsson & Sjöberg
  bound is named in #109 but unread, so calling it raises with the citation
  rather than returning a plausible number.
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
- **Analysis model** (design family field): the one closed-form calculation
  a family's ANALYSIS step runs to turn its geometry into a predicted
  response — a patch's resonant frequency; an absorber's worst-in-band
  absorbed fraction. Declared per family as an open value, required with no
  default: a family that forgets to state one cannot be constructed at all,
  rather than silently inheriting another family's model (#239 — the defect
  it replaces sent every family not named `"ABSORBER"` to the patch-antenna
  resonant-frequency formula). It is the **fourth** per-family plug-in,
  alongside **Physical bound**, **Optimizer class** and **Simulation
  adapter** (`designs/design_families.py`) — a fact recorded in no ADR and,
  until now, in no glossary entry, which is why ADR-0027 section 5's
  family-versus-letter test still names only three
  (`docs/RUNNING-LISTS.md` §3 correction 59). Its legal values include "no
  closed-form model exists here" (`UndeclaredAnalysisModel`), distinct from
  a bare `None`, for the same reason Physical bound's two non-bound states
  are kept apart: a family with no model and a family nobody has modelled
  yet are different facts.
  _Avoid_: treating `physical_bound`/`optimizer_class`/`simulation_adapter`
  as the complete set of what makes an imported shape a new family rather
  than a new letter — ADR-0027's own test omits this fourth plug-in.
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
- **Geometry model** (`geometry/ir.py`'s `Model`): one electromagnetic
  problem — domain, band, excitation, boundary, conducting and dielectric
  regions — stated once, independently of any solver. `geometry/translate.py`
  renders it into each adapter's own geometry dict. Deliberately carries **no
  mesh**: grid density is a numerical choice per solver, not a property of the
  object, and mixing the two lets a mesh setting masquerade as a design
  variable (#540).
  _Avoid_: "geometry dict" for this — that names an adapter's own
  solver-specific input, which is what a Geometry model is translated *into*.
- **Conductor kind** (`geometry/ir.py`'s `ConductorKind`): the closed
  three-value vocabulary — `PERFECT`, `BULK_CONDUCTIVITY`,
  `SHEET_RESISTANCE` — every conductor in a Geometry model must declare.
  Required rather than defaulted, because "a conductor" means an idealized
  lossless mirror in one adapter and a real lossy film in another; an
  optional field a translator could ignore is the exact shape of issue #230,
  where a resistive sheet was modelled as perfect metal and absorbed nothing.
- **Unrepresentable geometry** (`geometry/ir.py`'s `UnrepresentableGeometry`):
  raised when a target solver cannot express a Geometry model's physics — a
  lossy sheet bound for a PEC-only solver, an oblique wave bound for a
  normal-incidence-only one. Carries what could not cross, why, and what to do
  instead. Distinct from ADR-0028's "warn, never block", which governs
  withholding a *candidate* from a human reader who can weigh the warning:
  nothing reads a warning on the translation path, so a degraded geometry
  would reach a solver and return a confident `SIMULATED` number unchallenged.
- **Element/Coding-Alphabet library**: a persistent, cross-run store of
  characterized symbol-alphabet elements (Tier B design families only, see
  #130) — the same accumulate-once-and-reuse shape as the
  **Material-property library**, holding each symbol's characterized
  response so it is looked up rather than re-solved by every design that
  shares its band and substrate. Keyed by `(element family, symbol,
  band, incidence-angle range, process)`, where **process is present only
  for a printed entry** — a simulated entry has none, since nothing was
  printed, and that absence is part of how the two kinds are told apart.
  The **Process record** reference is what makes #132's rule expressible,
  that "the same outline printed in carbon and in MXene is two letters,
  not one letter under two conditions." **A letter enters the library by
  being printed and measured, or by being simulated on a solver path with
  a passing Reference Case for its problem class** (ADR-0027, ADR-0053);
  either way it states which route it took. A shape from the literature
  with no run of its own here still enters only as a candidate in the
  **Considered-and-dropped ledger**, never as an entry, since its
  published response was measured inside someone else's validity box.
  **Entries never expire; they stop matching** — a configuration that no
  longer exists simply never matches a lookup, and the measurement stays
  true about the ink and machine that produced it. An equipment change
  therefore orphans the whole alphabet at once, which is a known and
  accepted cost, not an oversight.
  _Avoid_: invalidating an entry — an earlier version of this entry said
  a pitch or validity-box change "invalidates the whole alphabet's
  entries." That contradicted #132 and is superseded by ADR-0027
  (`RUNNING-LISTS.md` §3 correction 42).
- **Process record**: the named, stored answer to "how was this artifact
  made" — machine, ink and grade, substrate stack, pass count, achieved
  film thickness, and cure schedule (ADR-0027). It is the *stated box*
  the standing preference means when it calls manufacturing and material
  figures "measurements valid inside a stated box (pitch, ink, pass
  count, cure, grade)" and warns that "quoted without their box they are
  assumptions" — so an **Element/Coding-Alphabet library** entry with no
  Process record reference is an assumption, not a measurement.
  Distinct from a **Validity box**, and the two must not merge: the
  validity box says where a response may be *used* (band, incidence
  angle, neighbours), the Process record says how the thing was *made*.
  One says what this is good for, the other says where it came from.
  Because the library keys on it, an equipment change mints a new
  Process record and leaves every prior entry intact and queryable,
  which is what makes "what did we measure on the old machine" a lookup
  rather than an archaeology exercise.
  _Avoid_: process parameters, run config — this is a stored, referenced
  identity, not a loose bag of settings.

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
  one is what lets `SIMULATED` mean *validated* simulation in the **Evidence
  hierarchy** above — but only for the specific problem family and solver
  path that case exercises. Validation does not generalise past what a case
  actually poses: a case built on a uniform, unpatterned sheet at normal
  incidence says nothing about a patterned unit cell, an oblique angle, or a
  different solver, and each of those needs its own case before `SIMULATED`
  means the same thing there. Current scope, case by case:
  `verification/README.md`.
  _Avoid_: benchmark — that measures speed, not correctness.

- **Run report**: what an unattended run hands the morning reviewer
  (ADR-0025). Leads with the **trade space** — where the best candidate
  sits against threshold and objective, which constraint is binding, and
  what relaxing it would buy — with the ranked candidate list as
  supporting detail, because a ranking is already legible in the numbers
  and is silent on what to change next. Persisted, but stores only what
  nothing else stores (predictions, the **Considered-and-dropped
  ledger**, **Handoff records**, the stop reason, the diagnosis) and
  references design/decision/engineering-result rows for the rest, so
  the two cannot drift apart. Written inside ADR-0011's all-or-nothing
  transaction, never appended after it. Cut by leverage on the result,
  never by a fixed top-N — an option that was never tried has no score
  and so could never rank into one.
  _Avoid_: log, digest — both suggest a rendering of what happened,
  where the load-bearing content is what *didn't*.
- **Considered-and-dropped ledger**: the record, written at the moment a
  batch is proposed and carried in ADR-0022's existing batch record, of
  which families were weighed and which were set aside — per entry a
  family, a kept/dropped flag, one free-text reason, and a **reason
  kind** (ADR-0025). Structured rather than prose so a later proposal
  call can look an entry up deterministically. The reason kind is what
  keeps a machine's verdict from hardening into a permanent one:
  `human-decision` carries forward under ADR-0026, `capability-verdict`
  never does and is re-evaluated every run against the requirement's own
  stated properties — a family excluded because the requirement's
  curvature puts it outside the family's characterized **Validity box**
  expires the moment that curvature changes — and `engineering-judgment`
  carries forward with its reasoning and stays overridable.
  **`capability-verdict` is never about equipment, ink or material the
  shop doesn't currently have loaded** — that is a **Capability warning**,
  a different mechanism that never drops a candidate, per the charter's
  "present equipment... shape the ranking and the warnings, never the
  search" and ADR-0021's rule that a candidate the configuration cannot
  build today is "reported... with its reason attached... not deleted
  from it." An earlier version of this entry pointed `capability-verdict`
  at "the current configured fabrication capability," citing ADR-0021 —
  that reading contradicted the very ADR it cited, since ADR-0021
  requires an unbuildable candidate to be reported, never dropped;
  superseded by ADR-0025's 2026-09-09 correction.
  It also makes the requirement-change worklist a query: every entry
  dropped as a `capability-verdict` is exactly what relaxing that
  requirement unlocks. It exists because `run_candidate_search`
  receives its candidates as an argument and prunes nothing: the
  narrowing happens in the LLM role that composes the list, upstream of
  every module, and is otherwise unrecorded — making a thorough night
  and a narrow one produce identical reports. No gate: a batch that
  writes nothing here still runs, and the silence is itself recorded.
- **Capability warning**: a warning attached to a design candidate stating
  that the currently configured **Fabrication capability**, or the
  currently selected **Ink-property library** or **Material-property
  library** entry, does not meet a stated need — e.g. "needs 0.2 mm
  features; the loaded printer achieves 0.5 mm." Stated in the same
  `value`/`comparator`/`unit` shape as a **Requirement target**, so the
  gap is a precise, actionable spec rather than descriptive prose. **Never
  removes the candidate from consideration** — a shop's equipment, ink or
  material on hand is expected to change, unlike a family's own physical
  validity box, which is why this is a wholly different mechanism from a
  `capability-verdict` exclusion rather than a variant of one (ADR-0025's
  2026-09-09 correction). Re-evaluated against the current configuration
  every run, the same cadence as a `capability-verdict` entry, but a
  Capability warning never converts into one and a `capability-verdict`
  never converts into a Capability warning — a shortfall in what the shop
  has loaded and a candidate being outside its own characterized validity
  box are different facts with different owners.
  _Avoid_: folding this into `capability-verdict` — that was tried
  (ADR-0025's 2026-09-08 correction) and contradicted ADR-0021's own rule
  that an unbuildable candidate is reported, not dropped.
- **Infeasibility verdict**: a headline the **Run report** carries when a
  requirement cannot be met, in one of two kinds (ADR-0052). A **`bound`**
  verdict fires when a published per-family **Physical bound** forbids the
  requirement, computed once `ARCHITECTURE` has named a family — its
  reading is "more search will not help; physics caps this." An
  **`exhaustion`** verdict fires when a run's stop reason is
  `evaluation_budget` or `score_plateau` and the **Considered-and-dropped
  ledger** shows more than one family or material was actually tried — its
  reading is "we searched hard and found nothing; more or different search
  might still help." **Advisory, never terminal**: a verdict never stops a
  run or withholds a candidate the run produced; it changes what the
  report leads with, not what it contains. Carries the binding constraint,
  a margin (a per-option reason list instead, for a categorical
  constraint with no numeric "by how much"), provenance, and the
  `assumed`/`costs`/`cheapest_test` triple CLAUDE.md's warning contract
  requires — `assumed` is the bound's own Validity box for a `bound`
  verdict. Scoped to one `(requirement, family)` pair, never "the" family
  for a requirement with more than one candidate family.
  _Avoid_: gating, refusing — an infeasibility verdict never removes a
  candidate or a run from what the reader sees; that is exactly the act
  ADR-0047 forbids for a different reason (a candidate's own apparent
  bound violation).
- **Unscorable**: the outcome when a family cannot be evaluated at all —
  no closed-form **Analysis model** (`UndeclaredAnalysisModel`) or a
  material with no in-band data — as distinct from evaluated-and-found-
  wanting. The one outcome with genuinely no candidates, since nothing
  ran. Never reported as an **Infeasibility verdict**: "cannot work" and
  "cannot be evaluated" are different facts a reader must be able to tell
  apart at a glance (#127).
  _Avoid_: infeasible, cannot be met — those claim something about
  physics; unscorable claims something about what the loop is currently
  equipped to check.
- **Field bundle**: the self-describing directory written after a SIMULATION
  step, holding the mesh the solver actually solved on, the complex fields it
  returned, and a manifest carrying that result's **Provenance**, its
  **Validity box**, any **Capability warnings**, and its **Claim limits**. It
  is the one seam every renderer reads, so nothing downstream reaches into a
  solver's own working files. Distinct from an **Engineering result**, which
  records the scalars a run reported: the bundle records what the solver was
  *given* and what it *computed*, which is what makes a picture checkable
  against it rather than merely captioned.
  _Avoid_: export, dump — both name it as a copy of solver output, where the
  load-bearing content is the manifest saying what that output may be shown as.
- **Claim limit**: a machine-readable statement that a **Field bundle**'s
  contents do not support one specific claim — that it is a finished part
  rather than one periodic cell, a measured result, a converged mesh, an
  arbitrary printed outline, or a solver path that has ever been run against a
  real binary. Populated by the exporter from facts it can establish and never
  hand-written per run, so every renderer inherits the same limits; a renderer
  that cannot honour one must refuse to render rather than render without it.
  Distinct from a **Capability warning** (the shop cannot build this today) and
  from a `capability-verdict` (the requirement falls outside a family's
  **Validity box**) — those two are about a candidate, while a Claim limit is
  only about what may be shown or said about a result, and so never adds,
  drops or ranks anything.
  _Avoid_: refusal — a **Rejection record** already stores "the refusal" in the
  sense of a human declining a proposal, and a Claim limit is a fact about what
  the evidence supports, not a decision anyone made.
- **Rejection record**: the stored fact that a human refused a specific
  proposal, with who, when and the stated reason (ADR-0026). A named
  exception to "a guess never becomes settled by repetition", on
  ADR-0015's grounds — it is a fact about what a person decided, so
  replaying it inherits no engineering guess. Stores the **refusal**,
  never the conclusion: a later run may read that something was refused
  and why, and must still re-derive the physics itself.
  _Avoid_: rejected value, ruled-out material — both name the conclusion
  this record deliberately does not carry.
- **Handoff record**: role, question, answer and timestamp for one
  Principal-to-specialist handoff (ADR-0025). Capture only: a
  specialist's answer is an LLM inference sitting at the bottom of the
  **Evidence hierarchy** and gets no provenance rung of its own, since
  minting one would quietly promote it against the closed set above.
  Exists because `SPECIALIST_HANDOFFS` transfers control one way and
  nothing persists that it happened, so an overnight answer shaped by
  six roles has no traceable author.

`/domain-modeling` should keep extending this section as more terms and
decisions get resolved (see `docs/agents/domain.md`).
