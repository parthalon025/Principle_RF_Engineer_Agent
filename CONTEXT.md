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
- **Core capabilities implemented so far**: wavelength, VSWR, return loss,
  cascaded gain, cascaded noise figure (Friis), and Touchstone (`.sNp`)
  network analysis (port count, frequency range, S11/S21 extrema). See
  `docs/ROADMAP.md` for the much larger list of RF functions (S/Z/Y/ABCD
  conversions, stability/noise/gain circles, matching networks, link
  budget, IP2/IP3/P1dB, etc.) still to be added.
- **Inputs**: plain numeric parameters for calculations; local Touchstone
  files for network analysis. Datasheets, schematics, and simulator inputs
  (NEC2++/openEMS/HFSS job files) are handled by the simulation adapters in
  `simulation/` but the adapters themselves are thin (NEC2++/openEMS shell
  out to the real tool via `subprocess`; HFSS is an intentionally
  unimplemented boundary pending a licensed AEDT host — see
  `simulation/hfss.py`).
- **Correctness bar**: the design principle is that the LLM is never
  trusted to do RF arithmetic itself — it calls a deterministic tool
  (`rf_tools/calculations.py`, `rf_tools/touchstone.py`) and every
  significant result carries a `provenance` tag (`MEASURED`, `SIMULATED`,
  `CALCULATED`, `MANUFACTURER-SPECIFIED`, `LITERATURE-SUPPORTED`,
  `INFERRED`, `ASSUMED`, `UNKNOWN`). `tests/` currently covers the
  calculation and Touchstone-analysis functions; there is no verification
  corpus yet for the simulator adapters or the agent's end-to-end behavior.

## What's still open

This is a foundation, not a finished system. `docs/BUILD_PLAN.md` and
`docs/ROADMAP.md` lay out the build order (deterministic math → Touchstone
→ knowledge base → simulators → measurement correlation → optimization).
Notably not yet implemented: the RF knowledge base / pgvector ingestion
pipeline (schema exists in `db/schema.sql`, no ingestion code yet),
component/manufacturer intelligence, antenna geometry generators, HFSS/ADS
adapters, instrument (VISA/SCPI) integration, and simulation/measurement
correlation. Treat anything not listed under "implemented" above as not
yet built, regardless of what the docs describe as the eventual system.

Originally tracked as a `needs-info` scope question in issue #3; that issue
is resolved by this implementation landing — see the PR that introduced it
for history.

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
  `datasheet`, `application_note`, `standard`, `textbook`, or `paper`.
  Fixed at ingest time; determines the document's default provenance and
  authority rank.
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
