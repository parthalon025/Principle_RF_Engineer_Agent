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
| [ANSYS HFSS](hfss.md) | The commercial, market-leading full-wave 3D EM solver, driven via PyAEDT on a licensed workstation only — the highest-fidelity solver available here, at a real license cost. | Native Floquet/periodic-port boundaries for metasurface unit cells, and SBR+/hybrid FEM-IE for an element mounted on an electrically large host (this repo's core vehicle/aircraft-skin scenario) — neither exposed by the adapter today. |
| [NEC2++](nec2.md) | Free, open-source thin-wire method-of-moments solver — the cheapest, fastest cross-check for wire antennas and simple arrays. | Plane-wave excitation exists in the underlying binary but the adapter only ever emits a voltage-source excitation, blocking the direct route to a surface's reflection phase — this program's central question. |
| [openEMS](openems.md) | Free, open-source FDTD full-wave solver (via CSXCAD) for arbitrary 3D dielectric/lossy geometry. | Far-field/gain (NF2FF) is a real openEMS capability the adapter never invokes — antenna pattern results are unavailable, only S-parameters. |
| [OpenParEM](openparem.md) | A young, free FEM solver that produces antenna far-field gain/directivity/efficiency from the same solve as its S-parameters — a cheaper alternative to HFSS for that one number. | The adapter can't generate its own mesh or materials file; both must be hand-built outside this codebase first. |
| [Elmer FEM](elmer.md) | A free, general multiphysics FEM suite; this repo uses only its `VectorHelmholtz` EM module. | Coupled EM+thermal multiphysics — solving electromagnetics and heat transfer on the same mesh in one run — is Elmer's actual reason for being here and is not yet built. |
| [Palace](palace.md) | Free, open-source parallel FEM solver — the first tool here with native Floquet/periodic-port boundaries, i.e. the one built specifically to characterize a metasurface unit cell. | Embedded PEC conductor support inside the periodic unit cell is unimplemented, which blocks the most common real case (patterned metal on dielectric, not an all-dielectric grating). |
| [MEEP](meep.md) | Free, open-source FDTD solver from MIT, driven as a Python library; used as an independent cross-check against openEMS. | Near-to-far-field transformation — the machinery to predict antenna radiation patterns — is documented in Meep but unused here. |
| [gprMax](gprmax.md) | Free, open-source Python-driven FDTD solver, originally built for ground-penetrating radar. | Dispersive material models (Debye/Lorentz/Drude) exist in gprMax but the adapter only exposes constant, non-dispersive materials — real absorber/ferrite substrates are frequency-dependent by nature. |
| [ngspice](ngspice.md) | Free, open-source circuit-level SPICE simulator for matching-network/bias/filter sub-circuits. | `.NOISE`/`.DISTO`/`.PZ`/`.SENS` analyses are unused — noise-figure and distortion analysis would matter for an amplifier/LNA behind an EM surface. |
| [Xyce](xyce.md) | Free, open-source (Sandia) circuit simulator built for large, MPI-parallel circuits. | Harmonic Balance (`.HB`) analysis — periodic nonlinear steady-state — is unexposed; only `.op`/`.ac`/`.tran` are wired up. |
| [LTspice](ltspice.md) | The one non-open-source item in this batch — free-of-charge circuit simulator, valued mainly for vendor device-model familiarity. | `.net` two-port S/Y/Z/H-parameter extraction is reachable in principle but nothing templates the netlist for it the way the Xyce adapter does. |
| [Qucs-S / qucsator_rf](qucs.md) | Free/GPL circuit simulator with its own native RF engine (S-parameters, harmonic balance) alongside SPICE backends. | Only one analysis (`.SP`) and four component types are wired up out of qucsator_rf's full documented set. |
| [KiCad + gerber2ems](kicad-gerber2ems.md) | Free, open-source PCB design suite piped through gerber2ems into an openEMS signal-integrity solve on real as-laid-out copper geometry. | KiCad's own DRC (design rule check) is never invoked, so a board this pipeline simulates could be electrically unbuildable with nothing here catching it before fab time is spent. |
| [FreeCAD](freecad.md) | Free, open-source parametric CAD suite, used here only to map a flat unit-cell array onto a curved/conformal host surface. | FreeCAD's own FEM workbench (meshing + driving Elmer/CalculiX/etc.) is unused — this repo drives Gmsh/Elmer directly instead, but FreeCAD could generate the curvature-conforming mesh itself. |

## Component-sourcing APIs (3)

| Tool | What it is, and why this repo uses it | Biggest capability not yet wired up |
|---|---|---|
| [Digi-Key Product Information API v4](digikey.md) | OAuth2 REST API to Digi-Key's own distributor catalog. | `ProductDetails`/parametric data is unused — only enough is fetched to find a datasheet; no frequency/impedance/tolerance parametric matching. |
| [Mouser Search API](mouser.md) | Flat-API-key REST API to Mouser's own distributor catalog. | `search/keyword` free-text discovery is unused — a part must already be known by exact MPN; pricing/availability/lead-time/compliance fields were the biggest gap until ticket #274 wired them into `lookup_mouser_datasheet()`'s result. |
| [Nexar API (Octopart data)](nexar.md) | OAuth2 GraphQL API aggregating stock/pricing across *many* distributors at once (Mouser and Digi-Key included). | Multi-distributor pricing/availability aggregation — the trait that most distinguishes Nexar from the other two — is never queried; also unused: per-part ECAD footprint data. |

## Knowledge & standards ingestion (5)

| Tool | What it is, and why this repo uses it | Biggest capability not yet wired up |
|---|---|---|
| [arXiv API](arxiv.md) | Free, no-auth preprint search/metadata API — pulls RF/EM papers in as `LITERATURE-SUPPORTED` evidence. | `search_query` (field/boolean/date discovery) is entirely unused; every call already needs a known paper ID, so the tool can't answer "find prior art on X" on its own. |
| [ETSI standards](etsi.md) | Free, no-registration direct-PDF download of published European telecom/RF standards. | An undocumented `data.php` search endpoint would resolve a bare standard number to its download URL automatically, closing the adapter's one manual-lookup gap — flagged as unofficial, so used cautiously if at all. |
| [FCC rules via eCFR Title 47 API](fcc-ecfr.md) | Free, no-auth REST API to the authoritative, continuously updated US Code of Federal Regulations. | The Search Service (full-text search across Title 47) is unused — there's no way to ask "which sections mention EIRP" without already knowing the part number. |
| [3GPP specifications](3gpp.md) | Free, no-login FTP archive of every cellular-standard spec/version as a zip file. | No way to resolve "what is the current version of spec X" — the free DynaReport metadata surface that could answer that is unused. |
| [USPTO patent PDFs](uspto-patents.md) | Free, no-auth PDF download of any US patent/publication by number — this repo cites patents (e.g. US12089385B2) as primary sources for metasurface physics. | USPTO's free, key-authenticated Open Data Portal search API (structured search by inventor/assignee/classification/keyword) is entirely unused — today a patent must already be known by number; there is no path to *discovering* one. |

## Cross-cutting patterns

A few gaps repeat across categories, not just within one tool:

- **Discovery is the recurring hole in the knowledge-ingestion tier.** arXiv, ETSI, 3GPP,
  and USPTO patents all expose only "fetch a document whose identifier I already know" —
  none is wired up for "find me documents about X." Closing that would change what kind
  of question the agent's own literature search can answer without a human supplying an
  ID first.
- **Periodic/Floquet unit-cell characterization** — this program's central metamaterial
  need — exists natively in HFSS and Palace, but only Palace's adapter uses it, and even
  there embedded metal conductors (the common real case) aren't supported yet. NEC2++,
  openEMS, and Elmer have no periodic-boundary path at all.
- **Far-field/antenna pattern output** is a real capability in openEMS, HFSS, Meep, and
  OpenParEM, but only OpenParEM's adapter currently returns it — the others report
  S-parameters only.
- **Data already fetched but discarded**: this was Mouser's pricing/availability/compliance
  fields, arriving in the one response this repo's adapter already makes but dropped before
  reaching scoring — a zero-additional-API-cost gap, unlike everything above it. Ticket #274
  closed it; Digi-Key's `ProductDetails`/parametric data (row above) is the same pattern,
  still open.

## Methodology

Each report was researched independently (primary sources fetched live via WebSearch/
WebFetch, cross-checked against this repo's own adapter code) and is self-contained — read
one without needing this index. Where a claim couldn't be verified against the tool's own
docs (a page blocked by a bot-wall, a 403, a JS-rendered page this environment couldn't
execute), the report says so explicitly rather than filling the gap from memory or a
secondary source; several files above (Mouser, Nexar, HFSS, 3GPP, USPTO) name exactly
which pages that happened on.
