# KiCad + gerber2ems

KiCad is a free, open-source electronic-design suite for drawing a circuit
(schematic capture), laying out the copper on a printed-circuit board (PCB
layout), and exporting the manufacturing files a fab needs (Gerber photo-plot
files, drill files, a "stackup" description of each copper/dielectric layer's
thickness and material). gerber2ems is a separate, small Python tool, built by
Antmicro, that reads exactly those manufacturing files back in and turns them
into 3D voxel geometry for openEMS -- the same finite-difference time-domain
(FDTD) electromagnetic solver this repo already drives directly
(`simulation/openems.py`) -- so it can compute how signals actually behave on
the *real, as-drawn* copper (impedance, reflections) rather than on a
hand-typed geometry description. This repo chains the two together
(`simulation/kicad_gerber2ems.py`) to check the signal-integrity of a real PCB
antenna feed trace or via transition, not to compute how the antenna radiates.

## What it is

**KiCad**: a cross-platform EDA (electronic design automation) suite --
schematic editor (Eeschema), PCB editor (Pcbnew), 3D board viewer, Gerber
viewer, and an integrated SPICE circuit simulator -- maintained by the KiCad
Development Team (started by Jean-Pierre Charras in 1992; project lead Wayne
Stambaugh) [1][2]. Current stable release is KiCad 10.0.0 (March 20, 2026;
patched through 10.0.5), with KiCad 11 targeted for February 2027 [3].

**gerber2ems**: a Python command-line tool maintained by Antmicro (copyright
2023-2026) that "takes PCB production files as input... and simulates trace
[signal integrity] performance using openEMS" [4][5]. It is not itself a
solver -- it is a geometry builder and results post-processor wrapped around
openEMS.

## Full capabilities

KiCad, beyond what this pipeline touches: schematic capture and
netlisting; PCB layout with autorouting/interactive routing and a graphical
Design Rule Check (DRC) editor new in 10.0; a built-in ngspice-based circuit
simulator; a 3D board viewer with STEP/3D-PDF export; symbol/footprint/3D-model
library management with a package repository; Gerber, drill, and IPC-2581
manufacturing-file export; import of Cadence Allegro, Mentor PADS, and gEDA
designs; and two generations of Python scripting -- the legacy `pcbnew` SWIG
bindings (deprecated in KiCad 9, scheduled for removal in KiCad 11) and the
newer IPC API (stable, language-agnostic, used via the `kicad-python`/`kipy`
package) [3][6][7][8].

gerber2ems, beyond a single trace-impedance run: builds full 3D FDTD mesh
geometry from copper, drill, and stackup files; supports single-ended traces
and differential pairs with configurable port impedance/width/length; computes
S-parameters, port driving-point impedance, and per-port group delay across a
frequency sweep; and can render Smith charts, S-parameter plots, and
field-visualization output (via Paraview) [5][9]. It has **no far-field, gain,
or radiation-pattern computation of any kind** -- confirmed both by reading its
own source (`postprocess.py` writes only S-parameter/impedance/delay columns;
see `simulation/kicad_gerber2ems.py`'s module docstring for the exact class and
file citations) and independently, by its own README, which describes only
signal-integrity outputs and never mentions far-field, gain, or radiation
pattern [5].

## Integrations & interfaces

gerber2ems is invoked as a CLI (`gerber2ems -a`) reading a hardcoded `./fab`
directory and `./simulation.json` relative to its working directory, and
itself drives openEMS through openEMS's own Python bindings [5]. KiCad is
scripted here through `kicad-python` (PyPI package `kicad-python`, imported as
`kipy`), the official Python client for KiCad's IPC API: it launches a headless
`kicad-cli api-server` pre-loaded with a board file and exposes Gerber/drill/
position export and stackup queries over that connection [6][10]. The IPC API
requires KiCad 9.0+ and, as of KiCad 9-10, covers only the PCB editor -- KiCad's
own developer docs state schematic-editor and library-editor IPC support is
still planned for a future release [8].

## Licensing & cost

KiCad's source is GPL-3.0-or-later (with some MIT-licensed code), its
documentation is dual GPL-3.0-or-later / CC-BY 3.0, and its libraries are
CC-BY-SA 4.0 [2]. `kicad-python` is MIT-licensed, currently at v0.8.0
(August 30, 2026) [6]. gerber2ems is Apache-2.0 [4]. All are free, community
software with no purchase price; none is on PyPI as `gerber2ems` itself
(installed from source), per this module's own docstring.

## How this repo uses it today

`simulation/kicad_gerber2ems.py` wires up exactly one path end-to-end:
`export_kicad_fab_assets()` connects to a headless KiCad instance and exports
Gerber, drill, and position files plus a translated `stackup.json`;
`generate_gerber2ems_config()` builds gerber2ems's `simulation.json`;
`KicadGerber2emsSimulator.run()` subprocess-invokes `gerber2ems -a`; and
`parse_gerber2ems_port_csv()`/`parse_gerber2ems_results()` parse the resulting
`Port_<n>_data.csv` files into S-parameters, impedance, and trace delay. The
orchestrating function `run_kicad_gerber2ems_simulation()` returns a result
dict explicitly scoped as `"PCB signal-integrity only... NOT antenna
far-field/gain"` and capped at `SIMULATED` provenance -- nothing here has been
run against real installed tools yet (per the module's own honest-caveats
section). No schematic capture, DRC, 3D viewer, SPICE simulation, or library
management is touched.

## Capabilities not yet used here

The single most consequential gap: **KiCad's DRC and its graphical Rule Editor
are never invoked**, so a board this pipeline simulates could be electrically
unbuildable (shorts, clearance violations) with nothing in this repo catching
it before a human commits fab time or money -- relevant given this program's
"warn before spending real material or machine time" principle. Also unused:
KiCad's SPICE simulator (useful for the lumped-element matching-network side of
a feed design before laying out copper); its 3D/STEP export (useful for
checking conformal/curved-mount fit); and gerber2ems's differential-pair and
multi-trace batch modes, which this adapter's config passthrough supports but
nothing in this repo yet exercises for periodic/unit-cell array feed networks.

## Sources

- [1] https://www.kicad.org/about/kicad/
- [2] https://www.kicad.org/about/licenses/
- [3] https://www.kicad.org/blog/2026/03/Version-10.0.0-Released/ (via search summary; blog category index https://www.kicad.org/blog/categories/Release-Notes/)
- [4] https://raw.githubusercontent.com/antmicro/gerber2ems/main/LICENSE
- [5] https://github.com/antmicro/gerber2ems and https://raw.githubusercontent.com/antmicro/gerber2ems/main/README.md
- [6] https://pypi.org/project/kicad-python/
- [7] KiCad SWIG/pcbnew deprecation: https://dev-docs.kicad.org/en/apis-and-binding/pcbnew/index.html and https://dev-docs.kicad.org/en/apis-and-binding/index.html
- [8] https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/for-addon-developers/index.html
- [9] gerber2ems repo structure/README (see [5])
- [10] https://gitlab.com/kicad/code/kicad-python (project metadata; README fetched via raw path https://gitlab.com/kicad/code/kicad-python/-/raw/main/README.md)

Note: WebFetch on the plain GitLab project page returned only metadata (no
README text); the raw README path was fetched separately for capability
details. All URLs above were fetched directly during this research pass
(2026-09-09); none of the claims are drawn from model memory.
