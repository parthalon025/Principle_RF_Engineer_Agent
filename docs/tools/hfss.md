# ANSYS HFSS

HFSS ("High Frequency Structure Simulator") is a commercial, full-wave 3D
electromagnetic solver — it solves Maxwell's equations directly on a 3D mesh
of the actual geometry, the same category of physics as this repo's free
NEC2++/openEMS/Palace/Meep adapters, but from the long-established market
leader, with a much larger solver/postprocessing feature set and a price tag
that comes with it. This repo wires it up (`simulation/hfss.py`) via
**PyAEDT**, Ansys's own Python automation library, but — unlike every other
simulator this repo calls — HFSS cannot run without a paid seat license and a
real installed copy of Ansys Electronics Desktop (AEDT). That is why this
adapter is the only one in the repo gated behind a "licensed-workstation
confinement" check rather than just a missing-binary check: a stray
environment flag must never make the system quietly believe it solved
something in HFSS when it did not.

## What it is

HFSS is Ansys's 3D high-frequency EM simulation product, used to "validate and
sign off complex electronic designs" — antennas, RF/microwave components, IC
packages, connectors, and PCBs [1]. It was originally developed by Ansoft
(acquired by Ansys in 2008); Ansys itself was acquired by Synopsys, completing
17 July 2025, so HFSS is now a Synopsys-owned product sold as part of the
Ansys electronics portfolio [2][3]. PyAEDT is maintained by Ansys/Synopsys as
part of the "PyAnsys" initiative and currently supports AEDT 2022 R1 and
newer; its own release cadence is active, with v1.5.0 tagged 2 September 2026
[4][5].

## Full capabilities

HFSS offers several solution types, chosen per problem: **Driven Modal** and
**Driven Terminal** (S-parameters from waveguide-mode or terminal
voltage/current excitations, respectively), **Eigenmode** (a structure's
resonant frequencies and fields with no excitation at all), **Transient**
(time-domain, e.g. pulsed/lightning-strike excitations), **SBR+** (Shooting
and Bouncing Rays, an asymptotic ray-tracing solver for electrically huge
scenes), and **Characteristic Mode Analysis** [6]. Numerically it mixes the
Finite Element Method (FEM), Integral Equation (IE/MoM) methods, and a
**hybrid FEM-IE** mode that solves geometrically detailed regions with FEM and
large surrounding structure with IE/MoM in one coupled run — useful for an
antenna mounted on an electrically large platform [7]. It has native
**Floquet-port / master-slave periodic boundaries** for simulating one
repeating unit cell of an infinite array, metasurface, or frequency-selective
surface [8] — exactly the periodic/unit-cell metamaterial capability this
repo also gets (partially) from Palace. Postprocessing includes full
far-field antenna quantities — gain, directivity, radiation pattern, axial
ratio, LHCP/RHCP components — computed without re-solving [9]. **Optimetrics**
provides parametric sweeps plus gradient/genetic optimization, sensitivity,
and statistical (tolerance) analysis, and **Distributed Solve/HPC** options
spread parametric variations or a single large solve across many cores or
machines [10][11].

## Integrations & interfaces

HFSS is normally driven through the AEDT desktop GUI, but Ansys's own
automation path is **PyAEDT**, a Python client library that talks directly to
the AEDT API rather than replaying brittle recorded macros [4]. PyAEDT
automates not just HFSS/HFSS 3D Layout but the wider AEDT suite — Maxwell
2D/3D, RMXprt, Icepak, Q3D/2D Extractor, Mechanical, Nexxim (circuit), Twin
Builder, EMIT, and the EDB layout database [4] — none of which this repo's
adapter touches today.

## Licensing & cost

PyAEDT itself is **MIT-licensed** (confirmed by fetching its `LICENSE` file
directly) [12], but PyAEDT is only a remote control for AEDT: its own docs
state plainly, "To run PyAEDT, you must have a local licenced copy of AEDT"
[4] — the free library is worthless here without the paid product it drives.
Ansys does not publish HFSS list pricing; third-party reseller/comparison
sites report commercial quotes in the rough range of **~$5,000-$10,000/year
for a single named-user seat**, scaling to tens or hundreds of thousands of
dollars/year for multi-seat or floating licenses [13][14] — cited here as
third-party estimates, not an Ansys-confirmed number, matching this repo's own
citation-confidence discipline (`simulation/hfss.py` module docstring).

## How this repo uses it today

`simulation/hfss.py` implements `HfssSimulator(Simulator)` — the same
`run(job) -> SimulationResult` contract as the other adapters
(`simulation/base.py`). `check_hfss_workstation_confinement()` runs before
anything else and requires *all four* of: `HFSS_ENABLED=true`, a
`HFSS_WORKSTATION_ID` matching an operator-configured
`HFSS_ALLOWED_WORKSTATION_ID`, `ansys.aedt.core` actually importable, and an
`ANSYSEM_ROOT*` environment variable (the marker AEDT's own installer sets).
Given a pass, `_apply_hfss_geometry()` builds axis-aligned box
materials/conductors via `Modeler3D.create_box`, assigns materials, creates
one **lumped port**, and applies a length-based mesh operation;
`_create_setup_and_solve()` creates a **Driven Modal** setup and a linear
frequency sweep and calls `Analysis.analyze()`; `_extract_hfss_results()`
reads S(1,1) via `PostProcessorCommon.get_solution_data()` and exports a
Touchstone file via `export_touchstone()`; `_archive_hfss_run()` saves the
project and archives project + results JSON. Everything is tagged
`provenance: "SIMULATED"`. Per the module's own "HONEST CAVEAT": pyaedt is not
installed and no licensed AEDT exists in this environment, so none of this
has been exercised against a real HFSS run — only against a hand-written fake
in `tests/test_hfss.py`.

## Capabilities not yet used here

The adapter uses exactly one solution type (Driven Modal, single lumped
port, box-only geometry) out of HFSS's full set. Not wired up: **Eigenmode**
solves (would characterize an absorber/FSS unit cell's resonance directly);
**Floquet/periodic boundaries** for unit-cell metasurface characterization —
the single biggest gap for this repo's actual purpose, since HFSS is the most
mature tool available here for that job, yet the adapter currently only
models isolated, non-periodic geometry; **SBR+** and **hybrid FEM-IE** for an
element mounted on an electrically large host platform (a vehicle or
aircraft skin, this repo's own core scenario); **curved/non-box geometry**
(cylinders, conformal shells — noted as explicitly out of scope in the module
docstring); **Optimetrics** parametric sweep/optimization, which could drive
this repo's own candidate-scoring loop directly inside HFSS instead of only
sweeping externally; and **Distributed Solve/HPC**, relevant once solves get
large enough to need it. None of PyAEDT's non-HFSS automation (Maxwell,
Icepak, Q3D, Circuit/Nexxim, EDB) is used, which is appropriate since this
repo's scope is RF/EM surfaces, not thermal or power-electronics simulation.

## Sources

- [1] https://ansys.synopsys.com/products/electronics/ansys-hfss — Ansys HFSS product page (what it is, capability summary); note this page returned HTTP 403 to direct fetch, so the summary here is drawn from WebSearch result snippets of this same URL, not a full-page fetch
- [2] https://news.synopsys.com/2025-07-17-Synopsys-Completes-Acquisition-of-Ansys — Synopsys press release confirming acquisition completed 17 July 2025
- [3] https://investors.ansys.com/news-releases/news-release-details/synopsys-completes-acquisition-ansys — matching Ansys investor-relations release
- [4] https://raw.githubusercontent.com/ansys/pyaedt/main/README.md — PyAEDT README: description, MIT license statement, full list of automated AEDT applications, "you must have a local licenced copy of AEDT"
- [5] https://github.com/ansys/pyaedt/releases — PyAEDT release history (v1.5.0, 2 September 2026, and prior 1.x releases)
- [6] https://ansyshelp.ansys.com/public/Views/Secured/Electronics/v252/en/Subsystems/HFSS/Subsystems/An%20Introduction%20to%20HFSS/Content/SolutionTypes.htm — official Ansys Help "Solution Types" page (Driven Modal/Terminal, Eigenmode, Transient, SBR+, Characteristic Mode)
- [7] https://ansyshelp.ansys.com/public/Views/Secured/Electronics/v242/en/Subsystems/HFSS/Content/HFSS/AssigningFEBIHybridRegion.htm — official Ansys Help page on the FE-BI hybrid FEM/IE region
- [8] https://ansyshelp.ansys.com/public/Views/Secured/Electronics/v242/en/Subsystems/HFSS/Subsystems/HFSS%20Floquet%20Ports/Content/Introduction.htm — official Ansys Help "Introduction" to Floquet ports for planar-periodic structures/unit cells
- [9] https://ansyshelp.ansys.com/public/Views/Secured/Electronics/v252/en/Subsystems/HFSS/Content/ReportsandPostProc/ScalingSourcesforHFSS.htm and related Ansys Help far-field/postprocessing pages — far-field gain/directivity/axial-ratio/LHCP-RHCP postprocessing
- [10] https://ansyshelp.ansys.com/public/Views/Secured/Electronics/v251/en/Subsystems/HFSS/Content/Optimetrics/Optimetrics.htm — official Ansys Help "Optimetrics" overview (parametric, optimization, sensitivity, statistical analysis)
- [11] https://courses.ansys.com/wp-content/uploads/2021/07/HFSS_GS_2020R2_EN_LE7_OptimHPC-1.pdf — official Ansys training material on Optimetrics Distributed Solve / HPC
- [12] https://raw.githubusercontent.com/ansys/pyaedt/main/LICENSE — PyAEDT's LICENSE file, confirmed MIT License text
- [13] https://zoftwarehub.com/products/ansys-hfss/pricing — third-party pricing aggregator (not an Ansys source; cited only as a rough-order-of-magnitude estimate since Ansys publishes no public price list)
- [14] https://www.itqlick.com/ansys-hfss/pricing — second third-party pricing aggregator, same caveat
- `simulation/hfss.py` and `simulation/base.py` (this repo) — current adapter implementation, `Simulator` interface, and the workstation-confinement gate
