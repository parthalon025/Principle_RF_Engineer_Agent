# Principle_RF_Engineer_Agent

## What this is

An agent intended to act as a principal-level RF (radio-frequency) engineer:
reviewing designs, running RF engineering calculations, and answering
questions the way a senior RF engineer would. The repo now contains an
initial reference implementation (see `README.md` for the layout and quick
start) alongside the process scaffolding (issue tracker, triage labels,
domain-doc conventions) installed via the Matt Pocock Claude Code skills.

## Surface and scope (as implemented)

- **Surface**: a Python application — an `openai-agents` SDK agent
  (`agent/main.py`) with a principal-engineer system prompt
  (`prompts/principal_engineer.md`), backed by deterministic RF tools
  (`rf_tools/`) and an equivalent standalone MCP server (`mcp_server/`)
  exposing the same tools for other MCP clients.
- **Core capabilities implemented so far**: the full deterministic RF
  calculation suite (`rf_tools/calculations.py`: wavelength, VSWR, return
  loss, cascaded gain, cascaded noise figure/Friis, S/Z/Y/ABCD conversions,
  stability/noise/gain circles, matching networks, link budget, IP2/IP3/
  P1dB) and Touchstone (`.sNp`) network analysis/interpolation/de-embedding/
  cascading/comparison (`rf_tools/touchstone.py`); a knowledge-ingestion
  pipeline (`knowledge/`: parse → chunk → provenance-tag → embed → index →
  hybrid lexical/semantic search, plus automatic per-field-provenanced
  component extraction from datasheets, plus component-identity resolution
  across the Digi-Key/Mouser/Nexar distributor clients (`knowledge/
  digikey.py`/`mouser.py`/`nexar.py`/`component_resolution.py` — all three
  need a registered free-tier API credential and outbound network access,
  neither is live in this environment) and free/no-auth standards/
  literature clients for arXiv, ETSI, FCC/eCFR, and 3GPP (`knowledge/
  sourcing/`)); a design/decision/verification layer (`designs/`:
  `create_design`, `record_decision`, `verify_requirement`, design/
  decision-record retrieval); full-wave EM simulation dispatch across seven
  engines — NEC2++ (MoM), openEMS (FDTD), Palace (FEM; the only one with
  native Floquet/periodic-boundary ports, for actually characterizing a
  periodic metamaterial unit cell), MEEP (FDTD via the `meep` Python
  library, run as an independent-method cross-check against openEMS),
  gprMax (FDTD, ground-coupled/lossy-half-space), Elmer/VectorHelmholtz
  (general multiphysics FEM; EM is one module among many, included for
  future multiphysics needs rather than as an RF-focused tool), and
  OpenParEM3D (FEM; the only one that also computes far-field gain/
  directivity/efficiency from the same solve) — all seven open source and
  runnable in this environment (Palace/MEEP/gprMax/Elmer/OpenParEM need a
  manual/binary install, documented in README.md, not a pyproject extra);
  plus HFSS/PyAEDT (`simulation/hfss.py` — code is written and
  citation-sourced against the real PyAEDT API, but gated behind a
  workstation-confinement check that requires a real licensed AEDT
  install; it cannot execute, and has never been exercised against real
  HFSS, in this or any unlicensed environment); five circuit-level
  simulators positioned as free Keysight-ADS alternatives — ngspice, Xyce,
  Qucs-S/qucsator, and LTspice (proprietary freeware, the one non-open-
  source item in this batch, kept only for vendor-model-library
  familiarity) share SPICE-card-generation plumbing via
  `simulation/spice_netlist.py`; a KiCad-Gerber-to-openEMS signal-integrity
  pipeline (`simulation/kicad_gerber2ems.py`, needs a real KiCad +
  gerber2ems + gerbv install); geometry generators — `geometry/
  unit_cell.py` (gdstk-based flat unit-cell/array tiling, simulator-
  agnostic) and `geometry/freecad_curved.py` (flat-to-curved-host-surface
  mapping in pure Python, plus an optional headless FreeCAD/`FreeCADCmd`
  path for an exact 3D STEP export); simulation/measurement correlation
  (`rf_tools/correlation.py`); optimization (`optimization/`: parameter
  sweep, grid search, Bayesian, genetic, gradient); SCPI/VISA instrument
  adapters for VNA, spectrum analyzer, signal generator, and power meter
  (`measurement/`, approval-gated per `orchestration/approval.py` for real
  hardware — never exercised against a real instrument — plus a hardware-
  free `pyvisa-sim` backend, selected via pyvisa's own resource-manager
  string/`PYVISA_LIBRARY`, that exercises the same adapter parsing logic
  against a simulated instrument for testing; `pyvisa-sim` output is not a
  substitute for `MEASURED` provenance, which still requires real
  hardware); and an opt-in controlled autonomous design-iteration loop
  (`orchestration/design_loop.py`, Phase 12; see ADR-0009/0010/0011). All
  of the above are exposed as tools in both `agent/main.py` and
  `mcp_server/server.py`. See `docs/FREE_AND_OPEN_SOURCE_TOOLING.md` for a
  sourced survey of free/open-source alternatives to paid solvers, lab
  instruments, and data subscriptions (the source of most of this wave).
- **Inputs**: plain numeric parameters for calculations; local Touchstone
  files for network analysis; uploaded documents (PDF datasheets,
  standards, textbooks, papers) for knowledge ingestion; a manufacturer
  part number for distributor-client lookup; structured geometry dicts
  (hand-built, or produced by `geometry/unit_cell.py`/`freecad_curved.py`,
  or derived from real KiCad PCB files via `kicad_gerber2ems.py`) for
  simulator jobs.
- **Correctness bar**: the design principle is that the LLM is never
  trusted to do RF arithmetic itself — it calls a deterministic tool and
  every significant result carries a `provenance` tag (`MEASURED`,
  `SIMULATED`, `CALCULATED`, `MANUFACTURER-SPECIFIED`,
  `LITERATURE-SUPPORTED`, `INFERRED`, `ASSUMED`, `UNKNOWN`). `tests/`
  covers the calculation, Touchstone, knowledge, and design-layer
  functions with real fixtures (Postgres integration tests for `knowledge/
  db.py`/`designs/db.py`, hand-built fakes for the simulator/instrument I/O
  seams) — but there is still no verification corpus (a golden-query
  fixture with expected results, and a recall/quality gate run before an
  embedding-model, chunking, or ranking change ships) for the knowledge
  pipeline, the simulator adapters, or the agent's end-to-end behavior. See
  `docs/KNOWLEDGE_PIPELINE_EXTERNAL_REVIEW.md` for a fuller gap analysis of
  the knowledge pipeline specifically (embedding-model/version tracking,
  chunk-level content-hash dedup, and a retrieval-feedback/citation log are
  also flagged there as not yet built).

## What's still open

This is a foundation, not a finished system. `docs/BUILD_PLAN.md` and
`docs/ROADMAP.md` lay out an intended build order, but the actual repo has
grown well past what either document names — see "Surface and scope"
above for what actually exists, including a whole second wave of simulators
(Palace/MEEP/gprMax/Elmer/OpenParEM/ngspice/Xyce/LTspice/Qucs-S/
kicad_gerber2ems), geometry generators, and knowledge-sourcing clients that
neither planning doc mentions by name. Do not infer "not yet built" from
`docs/ROADMAP.md`'s version numbering (e.g. its "0.6"/"0.7" labels), and do
not infer "built" from a doc naming something either — both docs describe
an intended sequence, not the actual implementation order or current
state; check the actual code before trusting either direction.

Genuinely not yet built, as of this revision: a verification/eval corpus
(a golden-query fixture with expected results and a recall/quality gate
for the knowledge pipeline; reference-case validation against independently
-sourced expected values for the simulator adapters — see "Correctness
bar" above) and the design-status transitions between `DRAFT` and the
later lifecycle states (see **Design** below). For HFSS, the real-hardware
SCPI/VISA instrument path, and the three distributor knowledge clients
specifically: the code is implemented and tested against fakes, but each
is gated on a resource this environment doesn't have (a licensed AEDT
workstation; real lab hardware; a registered distributor API credential)
and has never been exercised for real — see "Surface and scope" for which
is which.

Originally tracked as a `needs-info` scope question in issue #3; that issue
is resolved by this implementation landing — see the PR that introduced it
for history. Two prior revisions of this section have gone stale within
about an hour of being written (one claiming knowledge ingestion/
components/decision records/verification/instrument adapters were unbuilt
when they weren't; another, merged concurrently with this fix, that didn't
catch its own list going stale one PR later) — see
`docs/KNOWLEDGE_PIPELINE_EXTERNAL_REVIEW.md` for the session that caught
the first one. Cross-check "what's still open" against the actual code
before trusting it, every time — this section has now been wrong three
times in a row from taking a doc or a commit message at face value instead.

## Vocabulary

- **Provenance**: the evidence class of a stated RF result — see the list
  above. Never state a value without one once the agent produces it. A
  knowledge-base chunk cited by the agent inherits its provenance from the
  source document's **source type**: `datasheet`/`application_note` →
  `MANUFACTURER-SPECIFIED`; `standard`/`textbook`/`paper` →
  `LITERATURE-SUPPORTED`. An automatically extracted **component**
  specification field is `MANUFACTURER-SPECIFIED` when the extraction was
  unambiguous, `INFERRED` when the read was ambiguous or low-confidence,
  and `UNKNOWN` when it violates a physical-plausibility bound (e.g. a
  negative noise figure) regardless of the extractor's own confidence —
  there is no human review step, so provenance and physical bounds are the
  only signal a downstream user gets that a value should be double-checked.
- **Evidence hierarchy**: measured > validated simulation > deterministic
  calculation > manufacturer spec > authoritative reference > internal
  engineering history > general web material > LLM inference. Higher wins
  when evidence conflicts.
- **Source type**: the classification of an ingested knowledge document —
  `datasheet`, `application_note`, `standard`, `textbook`, `paper`, or
  `design_record`. Fixed at ingest time; determines the document's default
  provenance and authority rank.
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
  Touchstone file from bench/range testing) against the customer
  requirement it was built to meet, and recommending specific design
  revisions. Distinct from simulation — the input is real measured
  hardware data, not a simulated result.
- **Design**: a `designs` row — a named, revisioned unit of engineering work
  (`design_key`, `name`, `revision`, `status`) that `requirements`,
  `architecture`, engineering results, decisions, and verification all hang
  off of via `design_id`. `status` is `docs/OPERATIONS.md`'s existing
  workflow lifecycle, not a value set invented for this feature area:
  `DRAFT → ANALYSIS → SIMULATION → OPTIMIZATION → VERIFICATION →
  CONDITIONAL-PASS/PASS/FAIL/BLOCKED → RELEASED`, where `RELEASED` already
  requires human approval (see `docs/adr/0007`). A design is created in
  `DRAFT`; nothing yet builds the transitions between the other states.
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

`/domain-modeling` should keep extending this section as more terms and
decisions get resolved (see `docs/agents/domain.md`).
