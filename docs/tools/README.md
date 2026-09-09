# External tool capabilities

This repo hands scoring and iteration to `orchestration/solver.py`, but the numbers it
scores come from somewhere: a set of external EM/circuit simulators, a curved-geometry
generator, component-distributor APIs, and literature/standards-ingestion clients, each
wired up behind a Python adapter under `simulation/`, `geometry/`, or `knowledge/`. Those
adapter modules document *how* a tool is wired up — which command runs, which file gets
parsed — but not what the underlying tool can *actually do*, in full, versus what this
repo currently asks of it.

Each file in this directory is a per-tool research report, written from the tool's own
primary sources (official docs, GitHub repos, license files — not memory or secondhand
summaries), covering: what the tool is, its full capability set, how to integrate with it,
licensing and cost, exactly how this repo's adapter uses it today (with citations into the
code), and — the point of the exercise — what the tool can do that this repo doesn't yet
ask it for. "Not yet used" is a plain inventory, not a to-do list: some gaps are worth
closing (a periodic boundary condition nobody wired up yet), others are correctly out of
scope (an order-placement endpoint this program's one hard stop — nothing spends money
without a human saying yes — should never reach on its own).

In plain language: this is a shopping list of what each free (mostly) or paid tool this
program leans on is actually capable of, so a future decision to wire up more of one — or
to stop paying for one that offers nothing the free alternatives don't already cover —
starts from a real answer instead of institutional memory.

## EM/circuit simulators & geometry (14)

| Tool | What it is, and why this repo uses it | Biggest capability not yet wired up |
|---|---|---|
| [ANSYS HFSS](hfss.md) | The commercial, market-leading full-wave 3D EM solver, driven via PyAEDT on a licensed workstation only — the highest-fidelity solver available here, at a real license cost. | Native Floquet/periodic-port boundaries for a reflection-only metasurface unit cell are now wired up (issue #273); a two-port transmissive Floquet setup, non-rectangular lattices, and SBR+/hybrid FEM-IE for an element mounted on an electrically large host (this repo's core vehicle/aircraft-skin scenario) are not. |
| [NEC2++](nec2.md) | Free, open-source thin-wire method-of-moments solver — the cheapest, fastest cross-check for wire antennas and simple arrays. | Plane-wave excitation exists in the underlying binary but the adapter only ever emits a voltage-source excitation, blocking the direct route to a surface's reflection phase — this program's central question. |
| [openEMS](openems.md) | Free, open-source FDTD full-wave solver (via CSXCAD) for arbitrary 3D dielectric/lossy geometry. | Dispersive/anisotropic materials — CSXCAD's XML already supports per-axis tensors and openEMS supports Drude/Lorentz/Debye dispersion, but the adapter only ever emits isotropic, non-dispersive values. |
| [OpenParEM](openparem.md) | A young, free FEM solver that produces antenna far-field gain/directivity/efficiency from the same solve as its S-parameters — a cheaper alternative to HFSS for that one number. | The adapter can now generate its own mesh (via `simulation.elmer`'s geometry-to-`.geo` reuse) and materials file (issue #278), but only for the single box/excitation split `generate_gmsh_geo_script()` supports — curved or multi-material geometry still has no path to a mesh. |
| [Elmer FEM](elmer.md) | A free, general multiphysics FEM suite; this repo uses its `VectorHelmholtz` EM module, now coupled to its `Heat Equation` solver for thermal runs. | No periodic/Floquet unit-cell boundary condition is wired up, so — unlike this repo's Palace adapter — Elmer cannot characterize a metasurface/FSS unit cell, this repo's core use case. |
| [Palace](palace.md) | Free, open-source parallel FEM solver — the first tool here with native Floquet/periodic-port boundaries, i.e. the one built specifically to characterize a metasurface unit cell. | Non-rectangular lattices are unsupported (a single rectangular unit cell only) — embedded PEC conductor patches (issue #252) and a real, finite-conductivity sheet (issue #289) are both wired up now, closing this row's own former "embedded metal conductors unimplemented" claim, stale as of this writing. |
| [MEEP](meep.md) | Free, open-source FDTD solver from MIT, driven as a Python library; used as an independent cross-check against openEMS. | Near-to-far-field transformation is now wired up as an opt-in `far_field_monitor` key (#270), but only at caller-named directions (no full-sphere scan) and not yet independently verified against a real pymeep run the way the reflectance/transmittance recipe has been. |
| [gprMax](gprmax.md) | Free, open-source Python-driven FDTD solver, originally built for ground-penetrating radar. | Dispersive material models (Debye/Lorentz/Drude) were wired up in issue #277; `#soil_peplinski`+`#fractal_box` realistic (non-uniform) soil, GPU/MPI acceleration, and multi-port/`#hertzian_dipole` excitation remain unexposed. |
| [ngspice](ngspice.md) | Free, open-source circuit-level SPICE simulator for matching-network/bias/filter sub-circuits. | `.TF` (transfer function) analysis is unused — `.NOISE`/`.DISTO`/`.PZ`/`.SENS` (noise-figure and distortion analysis for an amplifier/LNA behind an EM surface, plus pole-zero/sensitivity analysis) were wired up in issue #283. |
| [Xyce](xyce.md) | Free, open-source (Sandia) circuit simulator built for large, MPI-parallel circuits. | Harmonic Balance (`.HB`) analysis — periodic nonlinear steady-state — is unexposed; only `.op`/`.ac`/`.tran` are wired up. |
| [LTspice](ltspice.md) | The one non-open-source item in this batch — free-of-charge circuit simulator, valued mainly for vendor device-model familiarity. | `.net` two-port S/Y/Z/H-parameter extraction is now templated (`generate_ltspice_net_netlist()`), but the exact `.raw` trace-name strings it reads back are corroborated only by community sources, not a real LTspice run. |
| [Qucs-S / qucsator_rf](qucs.md) | Free/GPL circuit simulator with its own native RF engine (S-parameters, harmonic balance) alongside SPICE backends. | Only one analysis (`.SP`) and four component types are wired up out of qucsator_rf's full documented set. |
| [KiCad + gerber2ems](kicad-gerber2ems.md) | Free, open-source PCB design suite piped through gerber2ems into an openEMS signal-integrity solve on real as-laid-out copper geometry. | KiCad's own DRC (design rule check) is never invoked, so a board this pipeline simulates could be electrically unbuildable with nothing here catching it before fab time is spent. |
| [FreeCAD](freecad.md) | Free, open-source parametric CAD suite, used here only to map a flat unit-cell array onto a curved/conformal host surface. | FreeCAD's own FEM workbench (meshing + driving Elmer/CalculiX/etc.) is unused — this repo drives Gmsh/Elmer directly instead, but FreeCAD could generate the curvature-conforming mesh itself. |

## Component-sourcing APIs (3)

| Tool | What it is, and why this repo uses it | Biggest capability not yet wired up |
|---|---|---|
| [Digi-Key Product Information API v4](digikey.md) | OAuth2 REST API to Digi-Key's own distributor catalog. | `Substitutions`/`RecommendedProducts`/`Associations` (alternate-part discovery) is unused — `ProductDetails`/parametric and pricing data was the biggest gap until ticket #275 wired it into a new `lookup_digikey_product_details()`. |
| [Mouser Search API](mouser.md) | Flat-API-key REST API to Mouser's own distributor catalog. | `search/keyword` free-text discovery is unused — a part must already be known by exact MPN; pricing/availability/lead-time/compliance fields were the biggest gap until ticket #274 wired them into `lookup_mouser_datasheet()`'s result. |
| [Nexar API (Octopart data)](nexar.md) | OAuth2 GraphQL API aggregating stock/pricing across *many* distributors at once (Mouser and Digi-Key included). | Multi-distributor pricing/availability aggregation and parametric `specs` — the traits that most distinguish Nexar from the other two — were unqueried until ticket #276 wired them into a new `lookup_nexar_part_data()`; still unused: per-part ECAD footprint data. |

## Knowledge & standards ingestion (5)

| Tool | What it is, and why this repo uses it | Biggest capability not yet wired up |
|---|---|---|
| [arXiv API](arxiv.md) | Free, no-auth preprint search/metadata API — pulls RF/EM papers in as `LITERATURE-SUPPORTED` evidence. | `search_query` (field/boolean/date discovery) was wired up as `search_arxiv_papers` (issue #257) — candidates only, never auto-ingested. Still unused: per-field (title/author/category-only) query construction beyond a caller building the field-prefixed string by hand. |
| [ETSI standards](etsi.md) | Free, no-registration direct-PDF download of published European telecom/RF standards. | An undocumented `data.php` search endpoint would resolve a bare standard number to its download URL automatically, closing the adapter's one manual-lookup gap — flagged as unofficial, so used cautiously if at all. |
| [FCC rules via eCFR Title 47 API](fcc-ecfr.md) | Free, no-auth REST API to the authoritative, continuously updated US Code of Federal Regulations. | The Search Service (full-text search across Title 47) is unused — there's no way to ask "which sections mention EIRP" without already knowing the part number. |
| [3GPP specifications](3gpp.md) | Free, no-login FTP archive of every cellular-standard spec/version as a zip file. | No way to resolve "what is the current version of spec X" — the free DynaReport metadata surface that could answer that is unused. |
| [USPTO patent PDFs and patent search](uspto-patents.md) | Free, no-auth PDF download of any US patent/publication by number — this repo cites patents (e.g. US12089385B2) as primary sources for metasurface physics. Full-text search against the Open Data Portal (issue #280, `search_uspto_patents`) is now wired up too, candidates only, never auto-ingested. | ODP's own `filters`/`rangeFilters`/`sort`/`fields` request parameters (structured search by date range, applicant, or classification, or a caller-chosen field projection) beyond the bare full-text query and result count this repo sends are unused, and so is its Patent File Wrapper prosecution-history/continuity/documents data for an application already found. |

## Cross-cutting patterns

A few gaps repeat across categories, not just within one tool:

- **Discovery was the recurring hole in the knowledge-ingestion tier — mostly closed now.**
  arXiv (issue #257, `search_arxiv_papers`), FCC eCFR (issue #279, `search_fcc_rules`),
  and USPTO patents (issue #280, `search_uspto_patents`) all now expose "find me
  documents about X," returning candidates for review that a caller must still choose
  to ingest deliberately — none auto-writes to the knowledge base. ETSI and 3GPP still
  expose only "fetch a document whose identifier I already know": prior research for
  both found no public search API to build one against (see their own docs/tools
  files).
- **Periodic/Floquet unit-cell characterization** — this program's central metamaterial
  need — exists natively in HFSS and Palace, and both adapters now use it (Palace since
  its own ticket, HFSS since issue #273's one-port reflection-only Floquet path). Palace's
  own embedded-metal-conductor gap (the common real case) is closed; HFSS's periodic path
  still lacks a two-port transmissive Floquet setup and non-rectangular lattices. NEC2++,
  openEMS, and Elmer have no periodic-boundary path at all.
- **Far-field/antenna pattern output** is a real capability in openEMS, HFSS, Meep, and
  OpenParEM. openEMS's and OpenParEM's adapters return it (openEMS via issue #269's NF2FF
  wiring), and Meep's adapter now does too (issue #270, opt-in with caller-named directions
  only) — HFSS's adapter still reports S-parameters only.
- **Data already fetched but discarded**: this was Mouser's pricing/availability/compliance
  fields, arriving in the one response this repo's adapter already makes but dropped before
  reaching scoring — a zero-additional-API-cost gap, unlike everything above it. Ticket #274
  closed it for Mouser; Digi-Key's `ProductDetails` turned out to be the same shape — one GET
  call already returns both parametric attributes and pricing — and ticket #275 closed it too,
  adding a separate `lookup_digikey_product_details()` rather than folding it into the existing
  datasheet lookup.

## Methodology

Each report was researched independently (primary sources fetched live via WebSearch/
WebFetch, cross-checked against this repo's own adapter code) and is self-contained — read
one without needing this index. Where a claim couldn't be verified against the tool's own
docs (a page blocked by a bot-wall, a 403, a JS-rendered page this environment couldn't
execute), the report says so explicitly rather than filling the gap from memory or a
secondary source; several files above (Mouser, Nexar, HFSS, 3GPP, USPTO) name exactly
which pages that happened on.
