# EM field visualization: architecture panel

Output of a design panel run against the question *"can a 3D visual representation of
the final simulation be represented with real physics and real modeling"*, which became
issue #337. Four recon agents, then six architects designing independently from
deliberately different angles, then judges.

**Status: judging was cut short.** One judge agent failed at 23 of 24 and the run was
stopped, so there is no machine ranking and no machine synthesis. The merge that reached
#337 was done by hand from these visions. That is worth stating because the panel's
single most useful output is not any one design — it is the *convergence*, and a
convergence found by hand across six independent agents is a weaker claim than a scored
one. Read it as six informed opinions that happened to agree, not as a ranked result.

Excerpts are trimmed for length; full agent transcripts are in the session workflow
directory under run `wf_9322167c-5b0`.

## The convergence

Two things every architect arrived at independently, with no shared context beyond the
brief and the recon:

1. **The same hero view** — the same antenna over bare metal beside the same antenna
   over the candidate surface, one camera, one clock, one numerically stated shared
   colour scale, plus a difference pane. Over metal the field collapses into a null
   exactly where the antenna sits and the antenna is deaf; over the metasurface that
   same point is an antinode. Several independently reached for the same published
   numbers to anchor it: −24.2 dB return loss for a dipole over a Jerusalem-cross AMC
   against −0.8 dB for the same dipole over plain metal.

2. **The same hardest problem** — that view is precisely what a Bloch-periodic unit-cell
   solve cannot compute, and several cited the same paper for it (EPJ Applied
   Metamaterials 2019, DOI 10.1051/epjam/2019014). A periodic cell is the exact answer
   to an infinite, flat, uniform sheet and carries no information about a lone antenna,
   an edge, a finite array or curvature.

The resolution adopted in #337 came from the panel rather than from the audit: do not
caption the gap, simulate across it — run the finite counterfactual as a genuinely
finite problem on the GPU, and keep the periodic run and the finite run as separate,
separately labelled objects.

A third, weaker convergence worth recording: every architect independently proposed
binding evidence tier to a **non-colour** visual channel (texture, hatch, stipple,
lattice etching) so that colour stays reserved for physics, and every one of them
proposed defining a MEASURED material and applying it to nothing — turning the empty
Element/Coding-Alphabet library into a hole visible in every session.

---

## Recon

### corpus

The standing coverage-gap note is out of date in an important way. `F:\data\arxiv-chunks` behaved exactly as predicted — metamaterial/FDTD hits are all Nov–Dec 2007 (`arxiv_07XX.XXXX`) plus unrelated 2026 CS files — but that is not the whole corpus. There is a separate, dedicated **`F:\data\rf_metamaterials` corpus: 19,641 records, 18,145 with extracted full text, 2.3 GB of PDFs, spanning 2003–2026**, harvested from OpenAlex + arXiv on the queries "metamaterial antenna" (18,796), "reconfigurable intelligent surface" (693), "metasurface antenna" (99), "frequency selective surface" (30). It contains exactly the `physics.app-ph` and `eess.SP` arXiv content the gap note said was absent (e.g. `arxiv_2608.15821`, 2026, physics.app-ph). For the *physics* of this program — AMC, high-impedance surfaces, FSS, absorbers, flexible/conformal printed structures — the local corpus is deep and current, and every substantive claim can be refereed against primary sources on disk. For the *visualization* question this recon was run to inform, the corpus is empty: 0 files mention ParaView/VTK/WebGL/interactive visualization, 3 mention volume rendering or scientific visualization (all incidentally), and arxiv-chunks holds only 5 cs.GR papers total, all 2007, none EM-related. That is a genuine coverage gap, not a negative finding. The one directly usable local visualization source sits outside the […]

- **A dedicated RF metamaterials corpus exists and supersedes arxiv-chunks for this domain — the standing coverage-gap note does not describe it** — 19,641 index records, 18,145 with chunk files, 190 MB of extracted text and 2.3 GB of PDFs. Year distribution is heavily current, not 2007: 2019 (1,459), 2020 (1,482), 2021 (1,618), 2022 (1,734), 2023 (1,788), 2024 (1,467), 2025 (1,467), 2026 (542). Sources: openalex 18,790, arxiv 849, nasa_ntrs 2. Contains eess.SP and physics.app-ph arXiv […]
  <br>Source: F:\data\rf_metamaterials\index.json; F:\data\rf_metamaterials\chunks\ (18,145 files); F:\data\rf_metamaterials_pipeline.py
- **Physics coverage is deep enough to referee essentially every claim this program makes** — Match counts across F:\data\rf_metamaterials\chunks: 'reflection phase' 403 occurrences in 197 files; 'flexible|conformal' 2,732 in 1,196 files; 'metamaterial absorber|RCS reduction' 2,052 in 797 files; 'surface current distribution' 251 in 129 files; 'artificial magnetic conductor' and 'high-impedance surface' each hit the 40-file result cap […]
  <br>Source: F:\data\rf_metamaterials\chunks\ (ripgrep counts)
- **Visualization coverage is effectively nil across the entire F:\data corpus — this is a coverage gap, not evidence that the literature is absent** — In rf_metamaterials: 'volume rendering|scientific visualization|isosurface|field visualization' returns 3 files, all incidental; 'WebGL|interactive visualization|web-based|browser-based' returns 0 files; 'colormap|color map|rainbow' returns 4 files, all ordinary figure captions (e.g. 'Color map showing the peak value of the FOM'). In arxiv-chunks […]
  <br>Source: F:\data\rf_metamaterials\chunks\; F:\data\arxiv-chunks\cs.GR\
- **The strongest local evidence against a persuasive 3D render: unit-cell simulation does not compute what a finite panel with a real antenna on it does** — 'FDTD modeling of nonperiodic antenna located above metasurface using surface impedance boundary condition', EPJ Applied Metamaterials 2019, DOI 10.1051/epjam/2019014. Verbatim: 'This paper investigates an FDTD modeling method for precisely calculating the characteristics of a single, that is, a nonperiodic antenna located above a metasurface that […]
  <br>Source: F:\data\rf_metamaterials\chunks\10.1051_epjam_2019014.json
- **The AMC ±90° reflection-phase bandwidth convention, with a citable worked example — and a vivid honesty fact attached** — DOI 10.1088/2053-1591/ab0683 (Materials Research Express, 2019): 'The concern of low gain is rectified using left-handed AMC having reflection phase −90° to +90° from 2.31 GHz to 2.4 GHz. The same reflector provides around 180° reflection phase from 3.4 GHz to 3.72 GHz, thus acting as PEC. The design principle is based on the placement of AMC at a […]
  <br>Source: F:\data\rf_metamaterials\chunks\10.1088_2053-1591_ab0683.json
- **Conformality is not free — bending detunes the design, and the corpus says so plainly** — DOI 10.1109/access.2022.3160825, 'Analysis on Bending Performance of the Electro-Textile Antennas With Bandwidth Enhancement for Wearable Tracking Application' (2022): 'Under deformed conditions such as during bending, the antenna might not operate at the desired frequency, causing performance degradation. Therefore, a 1.575 GHz textile antenna […]
  <br>Source: F:\data\rf_metamaterials\chunks\10.1109_access.2022.3160825.json; also 10.1109_access.2019.2891208.json, 10.1109_lawp.2014.2370254.json
- **Open-source-solver validation precedent in the literature is thin — only 3 of 18,145 files name any of the repo's solvers** — Searching 'MEEP|openEMS|gprMax|NEC-2|Palace' across the corpus returns 3 files. The most useful is DOI 10.1109/iceaa.2013.6632281 (7-Tesla traveling-wave MRI B1 field tailoring), which states: 'The electromagnetic modeling is carried out with our equivalent-circuit (EC) FDTD simulation platform openEMS.' So openEMS does appear as a published […]
  <br>Source: F:\data\rf_metamaterials\chunks\10.1109_iceaa.2013.6632281.json; 10.3390_sym14091942.json; 10.1109_aicaps68631.2026.11452649.json
- **The only directly usable local visualization guidance is a research note, not a paper — and it carries quantified perceptual rankings** — F:\data\research\2026-03-02-data-visualization-design-research.md contains: (1) the Cleveland & McGill (1984) encoding-accuracy hierarchy with error figures — position on common scale ±1.3%, position on non-aligned scale ±2.1%, length ±4.8%, angle/slope ±8.6%, area ±12%, color saturation ±18%, color hue categorical-only — with the rule 'Encode the […]
  <br>Source: F:\data\research\2026-03-02-data-visualization-design-research.md
- **arxiv-chunks confirmed the documented 2007 window exactly, and its content includes disputed claims** — Every metamaterial and FDTD hit in F:\data\arxiv-chunks carries an arxiv_07XX.XXXX id (Jul–Dec 2007), concentrated in physics.optics and cond-mat.mtrl-sci, plus two unrelated arxiv_2606 CS files. Representative titles retrieved: 'Unified Homogenization Theory for Magnetoinductive and Electromagnetic Waves in Split Ring Metamaterials' (0711.4215) […]
  <br>Source: F:\data\arxiv-chunks\physics.optics\; F:\data\arxiv-chunks\cond-mat.mtrl-sci\; F:\data\arxiv-chunks\physics.class-ph\arxiv_0712.0351.json

**Implications.**

- State the provenance asymmetry on the face of whatever gets built: the physics claims can be traced to 18,145 local full-text papers, but the visualization design decisions cannot be traced to anything local. Do not let a well-sourced physics layer lend borrowed authority to an unsourced presentation layer.
- The single highest-value warning the tool can carry is the finite-vs-infinite one, and it now has a peer-reviewed citation (10.1051/epjam/2019014). A unit-cell simulation computes one cell under periodic boundaries — mathematically, an infinitely repeating sheet. A 3D render of a finite patch on a vehicle silently […]
- Cleveland & McGill gives a quantified argument against leading with a 3D render for a decision audience. A 3D field visualization encodes magnitude in colour saturation (±18% read error) and in area/volume (±12%); a reflection-phase-versus-frequency line plot encodes it in position on a common scale (±1.3%). The […]
- Show the ±90° reflection-phase band as an explicit shaded region with the numeric span and fractional bandwidth spelled out (e.g. '2.31–2.40 GHz, 90 MHz, 3.8% of centre frequency'), because that is the field's own definition of the metric and it is much narrower than a render implies. Pair it with the fact from the […]
- Uncertainty must be a first-class visual element, not a footnote. The corpus note ranks confidence-interval bands above error bars above ensembles; for a SIMULATED-capped result the honest analogue is a band showing solver/mesh/material-tolerance spread around the nominal curve, with the SIMULATED label attached to […]
- Colour must never be the only encoding. Use the Okabe-Ito palette (#E69F00, #56B4E9, #009E73, #F0E442, #0072B2, #D55E00, #CC79A7, #000000) for candidate series and add redundant line pattern or marker shape, since ~8% of males have some colour-vision deficiency and one of the two named readers may be among them. For […]
- Bending deserves a warning slot of its own, but a carefully bounded one: the corpus states plainly that bending causes frequency detuning, yet only 13 of 18,145 files quantify it. So the tool can honestly say 'conforming this to a curved surface will move the operating frequency' and honestly say 'we cannot yet tell […]
- Do not claim solver credibility the literature does not grant. Only 3 papers in the whole corpus name any of the repo's open-source engines, and none cross-validate them against measurement for a metasurface problem. If a number comes out of MEEP or openEMS, the provenance label should say which engine produced it […]
- Before any visualization-design choice is finalised, run a real web search — the null result here is a harvesting gap in F:\data, not an absence in the literature. IEEE VIS/TVCG work on uncertainty visualization, scientific-visualization colour maps, and the persuasive-realism problem in 3D rendering all exist and […]
- Recommend updating the standing corpus note in CLAUDE.md: the documented 2007/CS-only gap is accurate for F:\data\arxiv-chunks but wrong as a description of F:\data as a whole. Left uncorrected it will keep causing agents to skip a 19,641-record, 2003–2026 RF metamaterials corpus that is directly on-topic for this […]

---

### sota-viz

Surveyed the state of the art in EM field visualization across (1) the five commercial solvers, (2) the open-source stack, (3) what browsers can actually do now, and (4) the handful of genuinely great explanatory EM visualizations — then identified five things nobody does well that this project is uniquely positioned to do.

The headline: the entire commercial stack (CST, HFSS, COMSOL, Lumerical, XFdtd) is built for an expert who already knows what to look at, and it converges on the same vocabulary — a cut-plane |E| contour, arrow/vector overlays, surface current (Jsurf) on the metal, a 3D far-field lobe, and a phase-swept animation. Every one of those views renders a wild guess and a bench measurement with identical pixels. None of them compares N candidate designs on one shared clock and one shared color scale. None of them shows manufacturing tolerance. None of them is viewable without a licence (CST's own web viewer needs 3DEXPERIENCE credentials). And the trust literature is explicit that a polished 3D render manufactures authority the underlying model has not earned — "viewers assume that a highly resolved image represents a highly resolved design."

The browser is now a legitimate target: WebGPU hit Baseline across Chrome/Edge/Firefox/Safari as of Nov 2025–Jan 2026, and a 2017 paper already demonstrated interactive GPU FDTD running in a browser tab. Combined with the […]

- **CST Studio Suite: the field-monitor vocabulary is the industry template — 2D cut-plane or full 3D domain, frequency or time monitors, and monitors must be declared BEFORE the solve** — CST offers 2D/3D visualization of electric fields, magnetic fields, power flows and surface currents, animation of field distributions, and far-fields (fields, gain, directivity, RCS) in xy-plots, polar plots, scattering maps and 3D radiation plots. Electric field results present as arrow plots and contour plots. A '2D monitor' records on a plane […]
  <br>Source: https://www.3ds.com/fileadmin/PRODUCTS-SERVICES/SIMULIA/PRODUCTS/CST/SIMULIA-CST-Studio-Suite-Brochure.pdf […]
- **CST has a web-based results viewer — but it is gated behind 3DEXPERIENCE platform credentials, not open sharing** — The 'Web-Based Results Viewer & Reporting' feature shows geometry, 1D results, far-field plots and 3D field plots from a browser. It sits inside the 3DEXPERIENCE cloud ecosystem alongside Cloud Preprocessor and Cloud Compute. Public documentation does not state that a recipient can view results without platform credentials, and the Learning […]
  <br>Source: https://www.goengineer.com/cst-studio-suite ; https://www.technia.com/en/advanced-simulation/software/cst-studio-suite/
- **Ansys HFSS: 'field overlays' plotted onto a point, line, surface, plane, cutplane or object — Mag_E and Mag_Jsurf are the two workhorses** — Workflow: enable Save Fields at setup, then Project Manager > Field Overlays > Plot Fields > E > Mag_E for a 3D contour of |E|; Mag_Jsurf for surface current density on the metal. Plot Type is Magnitude or Vector; quantities include E, H, and the Poynting vector E×H*. Phase animation via HFSS > Fields > Animate, but you must first select a base […]
  <br>Source: https://ansyshelp.ansys.com/public/Views/Secured/Electronics/v252/en/Subsystems/HFSS/Content/ReportsandPostProc/PlottingFieldOverlays.htm […]
- **Lumerical FDTD: the movie monitor cannot show energy flow, and the workaround reveals why animating power is hard** — The movie monitor records field components over time (or |E|², |H|²) and can superimpose an outline of the refractive-index profile ('draw structure outline') so you can see where radiation sits inside the dielectric. But it does NOT output the Poynting vector — frequency-domain monitors record P as time-averaged data, so the CW-movie technique […]
  <br>Source: https://optics.ansys.com/hc/en-us/articles/360034902373-Movie-monitor-Simulation-object ; https://optics.ansys.com/hc/en-us/articles/360034915793-Maki […]
- **Remcom XFdtd: the richest sensor taxonomy, and animation lives in a 'Sequence Tab' — everything exports to MATLAB/CSV** — Near-field sensor types: planar, point, surface (rectangular), part-face, box, volume, and surface-current sensors 'for viewing electrical current on metal'. Far-zone sensors compute radiation and RCS patterns via a near-to-far-field transform. A Huygens surface saves E and H near the boundary for export to a ray-tracer (Wireless InSite). SAR […]
  <br>Source: https://support.remcom.com/xfdtd/reference/sensors.html ; https://support.remcom.com/xfdtd/reference/results.html […]
- **COMSOL's phase-animation trick is the single most reusable technique found in this entire survey — synthesize the animation from one complex field** — COMSOL auto-produces a slice plot of |E|. To animate a propagating wave from a frequency-domain (time-harmonic) solve, you do NOT store frames: you plot the expression `Er*exp(-j*rev1phi)` with color table 'Wave', and sweep the phase parameter. COMSOL plots the real part by default — equivalent to `real(Er*exp(-j*rev1phi))`. A Deformation node […]
  <br>Source: https://www.comsol.com/blogs/visualization-2d-axisymmetric-electromagnetics-models/ ; https://www.comsol.com/blogs/get-arrow-plots-comsol-multiphysics
- **What RF engineers actually look at, in order — and why each step exists** — (1) S11 first, because it's the cheapest gate on whether the structure resonates where intended. Its shape is diagnostic, not just its depth: a non-smooth trace indicates internal reflections in the substrate; permittivity (εr) variation shifts the resonant frequency while loss tangent variation changes the magnitude — a tanδ change from 0.02 to […]
  <br>Source: https://interferencetechnology.com/evaluating-patch-antenna-printed-circuit-boards-utilizing-rf-absorber-and-s11-measurements/ […]
- **Metasurface/AMC papers have their own fixed figure grammar — reflection magnitude AND reflection phase vs frequency, paired** — The convention is a magnitude plot beside a phase plot swept over frequency, with phase normalized 0–360°. AMC operating bandwidth is defined as the frequency range where reflection phase stays within ±90° (one example: zero crossing at 5.75 GHz, ±90° band 4.9–7 GHz). For reconfigurable designs the acceptance criterion is visual: phase curves at […]
  <br>Source: https://arxiv.org/pdf/2009.13369 ; https://arxiv.org/pdf/1404.5570 ; https://www.nature.com/articles/s41598-024-82993-5
- **The single best quantitative hook for the magnetic-mirror story already exists in the literature and is begging to be animated** — A dipole over a Jerusalem-cross FSS AMC shows −24.2 dB return loss versus −0.8 dB for the same dipole over a PEC ground — i.e. the metal-backed dipole is essentially short-circuited by its own image. Reported AMC-backed profiles: 0.045λ, 0.05λ_L, 0.088λ₀. This is exactly the CLAUDE.md charter framing ('metal makes an antenna lying on it deaf; a […]
  <br>Source: https://ieeexplore.ieee.org/abstract/document/1377590/ ; https://www.academia.edu/25108186/Low_profile_dipole_antenna_backed_by_isotropic_Artificial_M […]
- **Open source: Meep's matplotlib house style is the de facto look of open FDTD output, and it encodes a good habit** — `Simulation.plot2D` draws geometry, simulation bounds, PML boundary layers (green hatch), sources (red) and monitors (blue) — i.e. it renders the *setup assumptions* on the same axes as the result, so you can see what was actually simulated. `Animate2D(fields=mp.Ez, realtime=True, field_parameters={'cmap':'RdBu', ...})` records frames as PNGs in […]
  <br>Source: https://github.com/NanoComp/meep/blob/master/doc/docs/Python_User_Interface.md ; https://github.com/NanoComp/meep/blob/master/python/visualization.py
- **PyVista + trame gives three deployment modes, and only one produces a shareable file — with real limits** — `PyVistaLocalView` renders entirely in the browser via vtk.js; `PyVistaRemoteView` renders server-side and streams images; `PyVistaRemoteLocalView` is hybrid. `plotter.export_html('scene.html')` writes a self-contained vtk.js scene — but client-side rendering only: no server callbacks, no widgets, and NO volume rendering. Exporting a whole […]
  <br>Source: https://docs.pyvista.org/user-guide/jupyter/trame.html ; https://docs.pyvista.org/api/plotting/trame.html
- **vtk.js / ParaView Glance: real browser volume rendering, with a documented performance cliff** — vtk.js is a full rewrite of VTK in ES6 keeping the same vocabulary (vtkVolume, vtkVolumeMapper, vtkColorTransferFunction, vtkPiecewiseFunction); `mapper.setSampleDistance()` is the main quality/speed knob. Volume rendering works on WebGL1 and improves on WebGL2. ParaView Glance v3.5 added a transfer-function editor with multiple colormaps and […]
  <br>Source: https://github.com/Kitware/vtk-js ; https://www.kitware.com/paraview-glance-release-v3-5-in-browser-scientific-visualization-and-annotation/ […]

**Implications.**

- Deliver as a published browser Artifact, not a desktop app. The audience is a CEO and a systems engineer with no EM licence; CST's own web viewer requires 3DEXPERIENCE credentials, PyVista's export_html cannot do volume rendering, and ParaView is a non-starter for this reader. The Artifact CSP allows scripts from […]
- Store one complex frequency-domain field and synthesize the animation in the shader as Re(E·e^{-iωt}). This is COMSOL's own internal trick (real(Er*exp(-j*phi)) with the phase parameter swept) and it converts an N-frame movie into a single static dataset plus one uniform. It is the difference between a 16MB budget […]
- Precompute in Python and ship raw binary straight to the GPU. The repo already has MEEP/openEMS/Palace adapters and geometry/unit_cell.py; the load path must do zero parsing at page load — the one team that got animated scientific data working in a browser did it by importing binary buffers the engine hands directly […]
- Target WebGL2 as the baseline and WebGPU as an enhancement, with feature detection. WebGPU is Baseline as of Nov 2025/Jan 2026 but is still flagged off in Chromium on Linux, absent in Firefox on Linux and Android, and in progress on Intel Macs. A three.js Data3DTexture raymarch path works everywhere today; a WebGPU […]
- Modify the stock three.js volume shader before relying on it. VolumeRenderShader1 samples only the red channel through a colormap — a complex E-field (Re/Im, or three vector components) needs a shader change, not just a different texture.
- Fix the colormap policy up front: a cyclic perceptually-uniform map (twilight, or a Kovesi CET `c`-series map) for phase; a diverging map (RdBu, matching Meep's house style) for signed instantaneous field; a sequential map for magnitude. Never HSV. If amplitude drives alpha or lightness, the hue map must be […]
- State the color normalization on every comparison view and share it across panels. Per-panel autoscale is the near-universal default and it silently makes a weak candidate look as strong as a good one — which is precisely the failure mode this program's doctrine exists to prevent.
- Give time a dedicated, always-visible, shared control. The digital-twin design critique is blunt that teams which fail treat time as just another filter, and Nicky Case names reader control of time as a core explorable pattern. One scrubber drives every pane.
- Choose a flat, diagrammatic, obviously-synthetic visual language and hold it as long as everything is capped at SIMULATED. The empirical finding is that photorealism activates the realism heuristic and that viewers assume a highly resolved image represents a highly resolved design; the prescription is a softer visual […]
- Read provenance from the existing modules; do not invent new labels in the viz layer. knowledge/provenance.py holds the source-type tiers and MEASURED; designs/provenance.py maps tool name to CALCULATED/SIMULATED; designs/success_score.py carries target_status (PROPOSED/CONFIRMED) — and its docstring is explicit that […]
- Keep warnings rare and specific in the visual layer too, per the charter. Uncertainty display is not free: measured trust rose with more forecasts shown and then declined as visual complexity grew, and calibration cues can degrade into 'trust junk' that nudges without grounding. A tolerance ensemble is worth animating […]
- Order the default views the way an engineer reads them, but explain each in the charter's plain terms: reflection/S11 first as the cheap gate (and say out loud that it cannot distinguish loss from radiation, so a deep dip is not proof), surface currents second as the causal layer (LIC or OLIC, since 'iron filings' is […]

---

### construction-cad

A printed metasurface is not "a pattern on a sheet" — it is a 4–6 layer stack roughly 0.1–2.5 mm thick in which the electromagnetically active conductor is 0.5–25 µm, and the adhesive holding it to the host is often thicker than the substrate carrying it. The single most important visualization finding is that the honest failure mode here is not exaggeration itself but *unlabelled* exaggeration: geology has a quantitative convention for this (vertical exaggeration, stated as "VE = N×" with both scale bars), and there is hard evidence it gets neglected and misleads — Stewart (2011) surveyed 1,437 papers and found 75% used VE > 2× while only 12% showed 1:1. Materials-science and semiconductor practice is weaker, not stronger: it uses qualitative "not necessarily to scale" boilerplate with no numeric multiplier, so importing the geology convention is an upgrade rather than a copy. The deepest honesty problem is separate and sharper: the solvers this program uses never contained the conductor's thickness at all. openEMS's `AddConductingSheet` "has no physical thickness" and the repo's own adapter emits zero-thickness Box primitives; thickness enters only as a loss parameter. A 3D render showing a solid 10 µm silver slab therefore depicts geometry no simulation in this program has ever meshed — the render would be more authoritative than the physics behind it, which is exactly the […]

- **The part is a stack of 4–6 layers, and the layer that does the electromagnetic work is the thinnest thing in it** — A representative real stack: host surface → adhesive (3M 468MP acrylic transfer tape is 5 mil ≈ 127 µm; the same family runs 2 mil ≈ 50 µm and 10 mil ≈ 250 µm) → substrate (PET 125 µm, or Kapton HN available 7.5–125 µm) → printed conductor (0.5–25 µm) → sometimes a second printed layer and a cover coat. Two consequences a truthful model must show […]
  <br>Source: https://multimedia.3m.com/mws/media/1581295O/3m-adhesive-transfer-tape-468mp.pdf ; https://cshyde.com/Asset/Data%20Sheet%2018-__F%20Dupont%20Kapton%C2 […]
- **Substrate numbers, measured at microwave frequencies (already in this repo, LITERATURE-SUPPORTED)** — Kapton/polyimide is the strongest-sourced: εr = 3.37 and tanδ = 0.008 (fit to 3 GHz) rising to 0.013 (fit to 12 GHz) at 297 K, from copper microstrip tee resonators on DuPont Pyralux AP-8555R (5 mil ≈ 127 µm Kapton) swept 0.05–20 GHz on an Agilent 8722D — Harris et al., arXiv:1206.1461. DuPont's own datasheet gives εr 3.4 (25/50 µm), 3.5 (75/125 […]
  <br>Source: E:\Principle_RF_Engineer_Agent\docs\material-property-literature-research.md ; https://arxiv.org/abs/1206.1461 […]
- **The adhesive has NO published microwave loss tangent — only a 1 kHz number, and 3M's own documents disagree with each other** — 3M 468MP datasheet: dielectric constant 3.32 (ASTM D150, 23 °C, 1 kHz). Dissipation factor is reported as 0.011 in an older 3M bulletin and 0.0253 in the current TDS — a 2.3× disagreement inside one vendor's own literature, at a frequency four to seven decades below where this program operates. At 10 GHz a 127 µm adhesive is 0.004 λ₀, deep in the […]
  <br>Source: https://multimedia.3m.com/mws/media/1581295O/3m-adhesive-transfer-tape-468mp.pdf
- **Skin depth arithmetic, computed here from δ = √(2/ωµ₀σ) — this is the number that decides whether a printed layer is a conductor or a leaky film** — At 10 GHz: bulk silver (6.30×10⁷ S/m) δ = 0.634 µm; best reported inkjet silver (1.05×10⁷ S/m) δ = 1.553 µm; laser-sintered silver (1×10⁶ S/m) δ = 5.03 µm; a poor UHF-RFID-grade ink (1×10⁵ S/m) δ = 15.9 µm; MXene (6.9×10⁵ S/m) δ = 6.06 µm. At 2.45 GHz those become 1.281 / 3.138 / 10.17 / 32.15 / 12.24 µm; at 24 GHz, 0.409 / 1.003 / 3.25 / 10.27 / […]
  <br>Source: Computed (CALCULATED) from σ values in https://www.sciencedirect.com/science/article/pii/S2468217924001096 and […]
- **Printed conductor thickness by process — and the case where the print is under one skin depth** — Inkjet single pass: ~0.5 µm (one paper reports a uniformly deposited 480 nm silver pattern). Three-pass inkjet: 3.15 µm at 1.05×10⁷ S/m, with measured insertion loss −2.9 dB and −2.1 dB at 17 GHz and 8.85 GHz on 5,000 and 10,000 µm microstrip lines. Screen printing: 25–100 µm typical deposit; Micromax/DuPont CB028 through a 200SS mesh gives ~10 µm […]
  <br>Source: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6444987/ ; E:\Principle_RF_Engineer_Agent\docs\fabrication-capability-and-ink-library-spec.md
- **Sheet resistance spans five orders of magnitude, and a single part usually needs two different inks at opposite ends of that range** — Silver screen ink: Micromax CB028 is specified 7–10 mΩ/sq/mil, i.e. roughly 0.007–0.010 Ω/□ at ~25 µm, with measured resistivity ~110 nΩ·m (≈6× bulk silver) after 160 °C/30 min. A commercial flexible silver paste on 125 µm PET gives 15–20 mΩ/□ at 25 µm and 30–45 mΩ/□ at 10 µm — halving thickness roughly doubles sheet resistance. A textile FSS […]
  <br>Source: https://www.pp.dupont.com/electronic-materials/screen-printed-inks-for-pcb.html ; https://www.nature.com/articles/s41528-019-0057-1 […]
- **Cure/sinter is a design variable worth a 5× swing in conductivity — not a process footnote** — A commercial low-cure screen Ag ink specifies, per 25 µm on PET: ≤1 mΩ/□ at 200 °C/5 min, ≤3 mΩ/□ at 120 °C/5 min, ≤4 mΩ/□ at 80 °C/5 min, ≤5 mΩ/□ at 60 °C/5 min. Broader literature: 120 °C for 30–60 min lands around 10–20% of bulk silver conductivity on PET; 150 °C on polyimide reaches 30–55%; 100 °C/30 min with a nanoparticle/nanoplate blend […]
  <br>Source: https://www.sigmaaldrich.com/US/en/product/aldrich/901090 ; https://pmc.ncbi.nlm.nih.gov/articles/PMC10015222/ […]
- **A cure/substrate conflict that a truthful construction view should surface as a warning** — Micromax CB028's specified cure is 160 °C for 60 minutes. Melinex 238 PET has an RTI of 125–130 °C depending on thickness. The Voltera NOVA's material-temperature ceiling is 40 °C — and that is the dispensing warmer, not an oven, so cure is a separate machine entirely (the repo's #108 decision already makes print / cure / laminate three […]
  <br>Source: https://www.pp.dupont.com/electronic-materials/screen-printed-inks-for-pcb.html ; https://www.tekra.com/products/films/polyester-films/polyester-pet/m […]
- **Minimum feature size by process, with the caveat that the floor is a property of the ink, not the machine** — Aerosol jet: ~10 µm standard, 5–6 µm demonstrated with a 5.8 MHz annular acoustic field plus modified nozzle (line width 60 ± 5% of unfocused, conductivity up 180 ± 5%, overspray <0.1 µm); production mm-wave work targets 20 µm with ≥5 µm dimensional accuracy. Inkjet: 20–50 µm typical; pushing to 10 µm brings satellite droplets and spreading […]
  <br>Source: https://www.nature.com/articles/s41467-024-50789-w ; https://iopscience.iop.org/article/10.1088/2058-8585/ace3d8 […]
- **Line-edge roughness and overspray — the most visible way a real print differs from the CAD ideal** — Aerosol jet: typical non-optimised line-edge roughness and overspray fall within 25 µm, i.e. 8% of a nominal 315 µm centre trace width. Loading the sheath gas with solvent vapour reduced overspray extent by up to 70 ± 2.3% for a water-based polyimide ink and lowered a solvent-based silver ink's resistivity by 34 ± 13%. The field's own metrology […]
  <br>Source: https://iopscience.iop.org/article/10.1088/2058-8585/aa5af9 ; https://pmc.ncbi.nlm.nih.gov/articles/PMC12257901/
- **Ink spreading: line width is set by the droplet's wetted footprint, not by the nozzle bore — and there are exactly four line regimes** — Final line width follows from volume conservation plus the equilibrium contact angle. Worked example: on PVB-coated substrate at 85° contact angle the spread diameter was 66 ± 2 µm versus 72 ± 2 µm as-received. Sweeping drop spacing from 50 µm down to 20 µm walks a printed line through four distinct morphologies: isolated drops → scalloped […]
  <br>Source: https://doi.org/10.3390/ma13030704 ; https://pmc.ncbi.nlm.nih.gov/articles/PMC9437868/ ; https://www.nature.com/articles/s41528-022-00187-3
- **Layer-to-layer registration: the number for the machine this program owns does not exist, and the industry numbers are the same size as the features** — Voltera publishes NO layer-to-layer registration figure anywhere — the repo verified zero registration figures across Voltera's documentation, white papers, blog and spec sheet, and Voltera's marketing claim 'Eliminate registration errors' is stronger than anything it substantiates. The ±20 µm figure is single-layer in-plane positioning, not […]
  <br>Source: E:\Principle_RF_Engineer_Agent\docs\voltera-multilayer-capability.md ; https://link.springer.com/article/10.1007/s00170-022-08717-z […]

**Implications.**

- Draw the conductor as a SHEET, not a slab — and label it with sheet resistance, not thickness. This is the one change that keeps the render from being more authoritative than the physics: openEMS's conducting sheet has no physical thickness, and this repo's own openEMS adapter emits zero-thickness boxes. Show the […]
- Adopt the geology convention verbatim, because it is the only quantitative one that exists: state 'VE = N×' on the figure, show BOTH a horizontal and a vertical scale bar so the reader can verify it independently, and provide a 1:1 companion panel. Stewart's 1,437-paper survey (75% exaggerated, 12% honest, and trained […]
- Prefer the exploded view over the compressed-stack view as the default. It is simultaneously the more honest depiction (each layer gets its own labelled thickness at true relative scale within the layer, with the gaps obviously artificial) and the rendering that sidesteps z-fighting, since near-coplanar micron layers […]
- Show the adhesive at full thickness and colour it as an unknown. At 127 µm it is often thicker than the 125 µm substrate, sits directly in the field, and has no published microwave loss tangent — 3M's own documents disagree by 2.3× on a 1 kHz dissipation factor. A stack diagram that omits or thins the adhesive is […]
- Render two inks as visibly different materials. A magnetic-mirror conductor at ~0.01 Ω/□ and an absorber's resistive layer at 377 Ω/□ are the same colour and thickness on a real part; if the visualization does not distinguish them the reader cannot see which behaviour the design is buying.
- Make print-process reality visible as a toggle: draw the CAD-ideal edge as a ghost line and the achievable print on top of it — scalloped or bulged line edges, an overspray halo (25 µm, ~8% of a 315 µm trace for aerosol jet), line width set by droplet footprint rather than nozzle bore, and a registration offset […]
- Gate the conformal view on Gaussian curvature before showing anything electromagnetic. Cylinder or cone: wrap it, no in-plane distortion, and show only the local incidence angle θ(s) = s/R walking off-normal along the arc, with the usable arc length S ≤ 2·θ_max·R marked. Sphere or compound curve: refuse to draw a […]
- Keep STEP as the source of truth and add only the two missing hops: a Gerber writer (gdsfactory is the one Python tool with native Gerber output) so a design can actually be printed, and a GLB export for the browser. Do NOT try to round-trip glTF or 3MF back into FreeCAD — triangulated-to-exact conversion cannot be […]
- Carry the provenance label onto every visual element, not just the numbers. Substrate εr at 10 GHz is LITERATURE-SUPPORTED; the Voltera ~10 µm minimum film is INFERRED from one worked example; the skin-depth ratios are CALCULATED; the resonance is SIMULATED; NOTHING in the render is MEASURED. A per-layer provenance […]
- One warning worth firing, by the charter's own rare-and-specific test: 'the ink you can buy may need a cure the substrate cannot survive.' Assumption — that the specified ink cures on the specified substrate (Micromax CB028 wants 160 °C/60 min; Melinex 238 PET's RTI is 125–130 °C; the NOVA's own warmer stops at 40 °C […]

---

### meep-export

Both solvers can export everything needed for external 3D visualization, but they export it very differently, and the honest answer to "can we render the 3D fields" is: yes for geometry and for single-frequency (steady-state) field volumes, no for full time-domain 3D vector fields at any resolution that actually resolves a printed metasurface. MEEP's menu is the richer one — in-memory NumPy arrays with index-aligned coordinate metadata (get_array + get_array_metadata → (x,y,z,w)), HDF5 step-function dumps for E/H/D/B/S/energy-density/epsilon, frequency-domain DFT arrays, near-to-far transforms to arbitrary points, and a documented h5 → h5tovtk → ParaView path. openEMS wins decisively on export ergonomics — the solver writes ParaView-native .vtr time series directly during the run, with write-time spatial decimation (SubSampling/OptResolution) that MEEP has no equivalent of — but openEMS has no periodic/Bloch boundary condition at all (only PEC/PMC/MUR/PML), so metasurface unit cells in openEMS are restricted to normal incidence. The file-size arithmetic is the decisive constraint: the "30x30x10 mm at 10 GHz, 20 cells/wavelength, 3000 timesteps" case as literally posed is only a 21x21x7 = 3,087-cell grid and 445 MB — but that mesh cannot represent a printed pattern at all (a 0.2 mm gap is 0.13 of a cell). At a mesh that can (0.05 mm cells), the same volume is 72,000,000 cells […]

- **MEEP in-memory array export is the primary path, and get_array_metadata removes all array-ordering guesswork** — sim.get_array(component=..., center=..., size=..., where=..., cmplx=False) returns a NumPy array of any field component over any sub-volume; cmplx=True returns complex. sim.get_array_slice_dimensions(...) pre-sizes it. The ordering question answers itself: sim.get_array_metadata(vol=...) returns a 4-tuple (x, y, z, w) where x/y/z are 1D coordinate […]
  <br>Source: https://meep.readthedocs.io/en/latest/Python_User_Interface/ ; https://github.com/NanoComp/meep/pull/552 ; https://github.com/NanoComp/meep/pull/655 […]
- **MEEP's full HDF5 step-function output menu, including the Poynting vector and energy densities** — Field dumps are generated from a macro: output_Xfield_{x,y,z,r,p} where X is e, h, d, b, or s (electric, magnetic, displacement, magnetic-flux, Poynting/S). output_Xfield writes all components of field X. Complex fields write two datasets in the same file, e.g. ex.r and ex.i. Energy densities are thin wrappers on output_component: output_dpwr → […]
  <br>Source: https://meep.readthedocs.io/en/latest/Scheme_User_Interface/ ; https://meep.readthedocs.io/en/latest/Python_User_Interface/ […]
- **Output plumbing: in_volume, to_appended, use_output_directory, at_every** — in_volume(vol, step_fn) restricts an output step function to a sub-volume — the documented way to avoid dumping the whole cell (the docs say to use this rather than setting output_volume directly). to_appended("name", at_every(dt, output_efield_z)) stacks every dumped timestep into ONE HDF5 file with time as an additional array dimension, e.g […]
  <br>Source: https://meep.readthedocs.io/en/latest/Python_Tutorials/Basics/ ; https://meep.readthedocs.io/en/latest/Field_Functions/
- **The documented MEEP → ParaView route is h5utils' h5tovtk, and it has real constraints** — MEEP's own docs state the pipeline explicitly: write with output_epsilon (or any field output), then convert the HDF5 to VTK with h5tovtk from the h5utils package, then view in Mayavi or ParaView. Constraints from the h5tovtk man page: a single .h5 can hold multiple datasets and h5tovtk takes the FIRST by default — select with -d or the […]
  <br>Source: https://meep.readthedocs.io/en/latest/Python_Tutorials/Basics/ ; https://github.com/NanoComp/h5utils/blob/master/doc/h5tovtk-man.md […]
- **MEEP's grid is uniform Cartesian, which means a field volume IS a 3D texture with no mesh needed** — Unlike openEMS's non-uniform rectilinear mesh, MEEP time-domain output sits on a uniform grid at a single resolution. Combined with get_array_metadata's tics arrays (origin + constant spacing + dims), a 3D field volume can be handed straight to a WebGL2 3D texture (gl.TEXTURE_3D / texImage3D) or written as a VTK ImageData .vti with no geometry […]
  <br>Source: https://meep.readthedocs.io/en/latest/Chunks_and_Symmetry/ ; https://meep.readthedocs.io/en/latest/Python_User_Interface/
- **Chunk and parallel gotchas: fewer than expected, but the ones that exist are sharp** — MEEP subdivides the grid into chunks — 'a contiguous region of space... assigned, in its entirety, to precisely one process — that is, no chunk exists partly on one processor and partly on another.' The good news: in a parallel run the OUTPUT functions (output_epsilon, output_efield, ...) automatically write a SINGLE HDF5 file; you do not stitch […]
  <br>Source: https://meep.readthedocs.io/en/latest/Parallel_Meep/ ; https://meep.readthedocs.io/en/latest/Chunks_and_Symmetry/ […]
- **TRUTHFULNESS HAZARD: output_epsilon does NOT show the discretized geometry the way you'd expect — it is smoothed twice and it hides a tensor** — This matters enormously and cuts against the assumption in the task. Three separate effects: (1) MEEP applies anisotropic subpixel smoothing by default — 'even if the structure consists entirely of isotropic materials, the discretized structure will use anisotropic materials', built from a projection matrix P_ij = n_i n_j onto the interface […]
  <br>Source: https://meep.readthedocs.io/en/latest/FAQ/ ; https://meep.readthedocs.io/en/latest/Subpixel_Smoothing/ ; https://github.com/NanoComp/meep/issues/764 […]
- **MEEP frequency-domain (DFT) export is the right-sized alternative to time-domain dumps** — sim.add_dft_fields([mp.Ez, ...], fcen, df, nfreq, where=vol) or with an explicit freq list accumulates Fourier transforms during the run; sim.get_dft_array(dft_obj, component, k) returns the complex array. Documented gotcha: the third argument is the frequency INDEX (0-based), not a count — with 10 frequencies, index 5 gives the 6th […]
  <br>Source: https://meep.readthedocs.io/en/latest/Python_User_Interface/ ; https://meep.readthedocs.io/en/latest/Python_Tutorials/Frequency_Domain_Solver/ […]
- **MEEP animation: Animate2D + to_gif/to_mp4/to_jshtml, with a normalize flag that changes what is stored** — Animate2D(sim=None, fields=None, f=None, realtime=False, normalize=False, plot_modifiers=None, update_epsilon=False, nb=False, **customization_args). output_plane=mp.Volume(center=..., size=...) slices a 3D sim to a plane. By default each frame is rendered to a PNG held in memory (more memory-efficient than the fields); normalize=True instead […]
  <br>Source: https://github.com/NanoComp/meep/blob/master/python/visualization.py ; https://github.com/NanoComp/meep/pull/872 […]
- **MEEP precision default is float64, not float32 — this doubles every file-size estimate unless the build is changed** — In meep.hpp: '#if MEEP_SINGLE // set to 1 via configure --enable-single / typedef float realnum; #else typedef double realnum;'. So by default time-domain field arrays, material arrays AND DFT field arrays are double precision. Building with --enable-single makes them float32, gives up to ~2x faster timestepping (memory-bandwidth bound), and the […]
  <br>Source: https://meep.readthedocs.io/en/latest/Build_From_Source/ ; https://github.com/NanoComp/meep/blob/master/src/meep.hpp
- **VOLUMETRIC 3D ARITHMETIC, case A — the stated case as literally posed is tiny, and physically useless** — lambda_0 = c/f = 299,792,458 / 10e9 = 29.9792 mm. 20 cells per free-space wavelength → dx = 1.49896 mm. A 30 x 30 x 10 mm volume is then ceil(30/1.499) x ceil(30/1.499) x ceil(10/1.499) = 21 x 21 x 7 = 3,087 cells. Six components (Ex,Ey,Ez,Hx,Hy,Hz) x 8 bytes (MEEP default double) = 148,176 bytes = 0.148 MB per timestep. x 3000 timesteps = […]
  <br>Source: Arithmetic from lambda_0 = c/f and MEEP's documented default Courant of 0.5; precision default from […]
- **VOLUMETRIC 3D ARITHMETIC, case B and C — at a mesh that resolves the printed pattern, the numbers explode** — Case B, dx = 0.25 mm (resolves a 1 mm printed feature with 4 cells; lambda_0/120): 120 x 120 x 40 = 576,000 cells → 6 comps x 4 bytes = 13.824 MB per timestep → 41.47 GB for 3000 steps (82.9 GB at float64). And dt = 417 fs, so 3000 steps is only 1.25 ns = 12.5 RF periods — too short for a resonant AMC to ring down. Case C, dx = 0.05 mm (resolves a […]
  <br>Source: Arithmetic; Courant 0.5 and float32/float64 sizes per MEEP docs (https://meep.readthedocs.io/en/latest/Build_From_Source/)

**Implications.**

- Do not build a 'watch the wave propagate through the part in 3D' feature. The arithmetic kills it: 1.728 GB per timestep at a mesh that resolves a 0.2 mm printed gap, 5.18 TB for 3000 steps. Any 3D time-domain animation that IS deliverable has been decimated to the point where it is an artist's impression, and the […]
- Build the deliverable around three exports that ARE honestly sized: (1) the discretized epsilon volume, 0.86 MB as uint8 for a realistic unit cell — this is the highest-value 3D asset because it shows the reader what was actually simulated versus what they think they drew; (2) one complex DFT field snapshot per […]
- Since MEEP's grid is uniform Cartesian, ship field volumes as raw uint8 3D textures plus an (origin, spacing, dims) header and render with a WebGL2 gl.TEXTURE_3D volume renderer — no mesh, no library, nothing to fetch past the CSP. get_array_metadata's tics arrays give you the header for free. This makes the browser […]
- Label the epsilon render as 'the structure after MEEP's subpixel smoothing and centre-of-pixel interpolation', never as 'the discretized geometry'. The task brief assumed output_epsilon shows the true staircase construction; it does not, and cannot be made to. If the goal is genuinely to show the reader the difference […]
- If energy-flow streamlines are built, use the time-averaged (1/2)Re(E x H*) from get_dft_array at one frequency, not instantaneous Sx/Sy/Sz. Two reasons: the instantaneous version is only first-order accurate unless every output is wrapped in synchronized_magnetic, and the time-averaged version is divergence-free in […]
- A tiled visual of a unit cell is legitimate at normal incidence (k_point = 0) and a fabrication at oblique incidence unless the Bloch phase exp(i k.p) is applied per cell. If tiling is offered at all, the renderer must carry the Bloch phase, and the tiled region must stop short of any depiction of a real part's edge […]
- The one warning that meets the 'rare, specific, load-bearing' bar here is the periodicity one, and it has all three parts. Assumed: an infinite, flat, uniform array of identical cells, with only the 0th diffraction order propagating (pitch below lambda/(1+sin theta)). Cost if wrong: edge truncation, curvature […]
- openEMS should be positioned as the ParaView/desktop path and MEEP as the everything-else path, and the split is forced, not stylistic. openEMS writes .vtr time series natively during the run with write-time decimation (SubSampling='4,4,4') and needs no conversion step — it is strictly better for a systems engineer […]
- Budget the far-field sphere as cheap to ship (65 kB) and expensive to compute (3.76 billion Green's-function evaluations per frequency for a 1-degree sphere off a 57,600-point near box). Compute it once at 2-degree resolution (0.95 billion evaluations, still 16 kB shipped) and interpolate for display, rather than […]
- Report the far-field pattern NORMALIZED unless the absolute-scale assumption has been verified. MEEP's docs say interpreting the overall scale and phase of near2far output is tricky, and simulation/meep.py already carries an unverified flag saying near2far and the flux monitors are ASSUMED to share one scale. Until […]

---

## Visions

### Two Mirrors — the decision's design

**Thesis.** The decision is "which surface, and what does its thinness cost" — so the hero view is the counterfactual pair (antenna on bare metal, deaf, versus the same antenna on the candidate, loud) locked to one clock, one camera and one colour scale, sitting directly above a reflection-phase plot where the analytic thickness-bandwidth sum rule is drawn as a wall you can drag and the simulated result is drawn as something you cannot.

**Killer feature.** The height slider on the counterfactual pair.

One drag. The dipole rises from 0.9 mm to 7.5 mm — a quarter wavelength at 10 GHz. On the left pane, over bare metal, a dead cancelled field slowly wakes up as the standoff finally reaches the quarter-wave condition, and the readout climbs from 0.8 dB toward 20 dB. On the right pane, over the metasurface, the field was already at maximum at 0.9 mm and does not change for the entire drag.

One sentence updates live underneath: "At this height, bare metal delivers 0.8 dB and the metasurface delivers 24.2 dB. To match the metasurface, the metal version must be 6.6 mm thicker."

That is the whole company in one gesture, and it requires no RF vocabulary whatsoever. The CEO does not need to know what a reflection phase is to understand "this makes the antenna work while staying 6.6 mm thinner." The numbers are the published dipole-over-Jerusalem-cross-AMC result (24.2 dB return loss versus 0.8 dB over PEC) and the geometry is the charter's own opening paragraph, animated.

And then, immediately below and on the same screen, the drag has a price. The trade-off band shows the reflection-phase curve with the plus/minus 90 degree window shaded […]

**What the user sees.** A single page. Top strip: up to four candidate chips — name, family, thickness in mm and in wavelengths ("0.87 mm = 0.028 lambda"), the in-phase band as a plain number ("9.1-9.9 GHz, 800 MHz, 8.4% of centre"), each number wearing a small tier badge.

Below that, the hero: two 3D panes, side by side, identical camera, identical scrubber, identical colour scale printed in the corner as "+/-1.00 V/m, same scale, same clock". Left: a printed dipole 0.9 mm above a bare aluminium panel. Right: the identical dipole at the identical height above candidate A. Each pane is a half-open box — solid geometry for the dipole and the layer stack, two orthogonal cut planes carrying the field as a red-white-blue diverging texture, and a pale ribbon floating above showing the standing-wave envelope so the node is a shape, not a claim. Press play and the wave crawls at 60 fps.

The comprehension arrives in […]

**Physics pipeline.** Solver: MEEP (Bloch-periodic unit cell, the only one of the two FDTD adapters with a k_point, so the only one that can answer oblique incidence at all), refereed at normal incidence by openEMS, which already produces complex S11 and writes a .s1p at E:\Principle_RF_Engineer_Agent\simulation\openems.py lines 1051-1061.

STEP 1, THE MISSING NUMBER. E:\Principle_RF_Engineer_Agent\simulation\meep.py today computes power reflectance only; its own text at line 954 says "NO phase is extracted". That […]

**Construction pipeline.** The 2D printed pattern already exists in the tree: E:\Principle_RF_Engineer_Agent\geometry\unit_cell.py builds it with gdstk and emits simulator-agnostic primitive dicts ("shape": "box"/"polygon" with p1_m/p2_m/points_m/normal_axis/elevation_m). E:\Principle_RF_Engineer_Agent\geometry\freecad_curved.py already extrudes and writes STEP for the curved array. The only missing hop is the browser.

NEW MODULE, geometry/gltf_stack.py. Walks those same primitive dicts plus the layer stack pulled from […]

**Hardest problem.** The hardest problem is that the most persuasive view on the page is the one the solver never computed.

The hero comparison — a finite dipole over a finite panel — is not what MEEP runs. MEEP runs one Bloch-periodic unit cell, which is mathematically an infinite, perfectly flat, perfectly uniform sheet. It contains literally zero information about the panel's edges, its finite element count, its curvature, or the feed antenna's near field. And this is not my inference: EPJ Applied Metamaterials 2019 (DOI 10.1051/epjam/2019014, full text on disk at F:\data\rf_metamaterials\chunks\10.1051_epjam_2019014.json) states in a peer-reviewed abstract that bridging periodic unit-cell results to a […]

**Honesty design.** SEVEN MECHANISMS, all visual, none a caption.

1. TWO RENDERING MATERIALS AND ONLY TWO. Everything the solver computed is drawn smooth and fully opaque. Everything extrapolated, assumed or analytic is drawn hatched at 45 degrees, 60% opacity, with a 1-pixel dashed border. No third style exists on the page. You can sort every pixel into "computed" or "not" from across the room.

2. A THIRD MATERIAL, DEFINED AND DELIBERATELY UNUSED. Measured data would render bright, saturated and crisp. The legend shows that swatch greyed out with the line "no design has earned this yet — 0 letters in the alphabet." Because everything here is capped at SIMULATED and ADR-0027 admits a letter only by printing […]

**Stack.** Python 3.12 exporter: MEEP via sim.add_dft_fields / get_dft_array / get_dft_array_metadata / get_epsilon_grid / […]; openEMS as the normal-incidence referee: E:\Principle_RF_Engineer_Agent\simulation\openems.py already builds complex […]; NumPy for the time-averaged Poynting 0.5*Re(E x H*) and for uint8 quantization of complex field volumes (Re/Im as two […]; gdstk (already used in E:\Principle_RF_Engineer_Agent\geometry\unit_cell.py) for the printed pattern and for the […]; pygltflib for a new geometry/gltf_stack.py — GLB in millimetres, origin rebased in float64, no Draco, no […]; FreeCAD macro path (E:\Principle_RF_Engineer_Agent\geometry\freecad_curved.py) unchanged: STEP stays the […]

---

### GLASS CELL — the physicist's design

**Thesis.** Ship the solver's stored complex phasor volume at its native grid and reconstruct time, H, energy flow and surface current from it exactly in the shader — so every pixel on screen is a solved Maxwell quantity or a closed-form operator applied to one, and the picture itself can be made to fail when the physics is wrong.

**Killer feature.** **The Standing Wave Ruler.**

Two panes side by side, one clock, one colour scale, both from real finite 7×7 simulations with a real dipole in them. Left: the dipole 1.5 mm above bare aluminium. Right: the same dipole 1.5 mm above the metasurface. Beside each pane, a vertical strip plots |E| against height above the surface — the standing-wave envelope, read straight off the solved field — with the null and the antinode ticked in millimetres, and a red mark showing where the antenna actually sits.

Over metal, the null is *on* the metal, and the antenna is sitting in it. The trace at the antenna's height reads near zero, and one number underneath reads **−0.8 dB return loss** — the plain-language line beside it says "almost everything the antenna transmits comes straight back; it is talking into a wall." Over the metasurface, the antinode is on the surface, the same trace reads maximum, and the number reads **−24.2 dB** — "the surface hands the signal back in step, and it adds instead of cancelling."

Then the CEO drags one slider: antenna height. As the dipole lifts off the metal, its red mark climbs the envelope, and at 7.5 mm it hits the metal case's first antinode — and the […]

**What the user sees.** A flat, diagrammatic dark page. Centre: a 6 × 6 × 3 mm glass box containing 864,000 visible cubes — the actual MEEP grid at 0.05 mm, no smoothing, voxels deliberately hard-edged. A chip reads "864,000 COMPUTED VOXELS · 2.0 samples/cell · NEAREST — nothing between you and the solver." Inside, a plane wave breathes: red-blue signed Ez sloshing at a scrubber-controlled phase, exact because it is Re(Ẽ·e^{-iωt}) from the stored phasor, not stored frames.

Left rail toggles the quantity, and each changes the story. **E** shows a standing wave in the air above; **H** (recomputed live from the Yee curl of E) shows its antinodes offset a quarter wavelength; **S** launches 100,000 particles that dive at the surface and — over the metasurface — turn around and stream back out, while over the absorber they funnel into the resistive sheet and die at a rate you can read against the absorbed-power […]

**Physics pipeline.** MEEP, Bloch-periodic unit cell, driven through the repo's existing `simulation/meep.py` (`periodic_axes=["x","y"]` → `k_point=Vector3()`, PML on z only). A new `simulation/field_export.py` attaches `sim.add_dft_fields([mp.Ex,mp.Ey,mp.Ez], freqs, where=mp.Volume(...), decimation_factor=0)` to the same run that already produces S-parameters, so the fields and the numbers come from one solve and cannot disagree.

After the run: `sim.get_dft_array(obj, mp.Ex, k)` → complex128 (120,120,60) […]

**Construction pipeline.** `geometry/unit_cell.py` already composes the printed pattern with gdstk booleans and emits simulator-agnostic primitive dicts. Two new modules close the loop.

`geometry/stack.py` defines a LayerStack: an ordered list of layers, each carrying thickness_m, role (host / adhesive / substrate / conductor / coverlay), εr, tanδ, sheet_resistance_ohm_sq, a provenance tier read from `knowledge/provenance.py`, and a citation string. The representative stack it models is real: host → 3M 468MP adhesive at […]

**Hardest problem.** The finite-versus-infinite gap, and it is worse than it looks because the feature I most want to build sits directly on top of it. A Bloch-periodic unit cell is the exact answer to an infinite, flat, uniform sheet of identical cells. It contains literally zero information about edges, cell count, curvature, or a real antenna sitting above it. And the killer feature — a dipole over metal versus the same dipole over the metasurface — is *precisely* the non-periodic-source-over-periodic-surface problem that EPJ Applied Metamaterials 2019 (10.1051/epjam/2019014) says is unsolved enough to warrant its own paper: brute force needs enormous resources, and the array-scanning alternative has […]

**Honesty design.** **Provenance is a material, not a caption.** Every panel showing a solved quantity is painted with a 4px diagonal hatch at 12% opacity and bordered with a 1px dash. A MEASURED panel would be solid with a clean border. The legend shows that solid swatch permanently greyed out, captioned "no panel on this page has earned this" — so the empty element alphabet is a visible absence a CEO can see, not a line in a doc.

**The interpolation chip.** Persistently docked at the 3D view's top right: "864,000 COMPUTED VOXELS · 2.0 samples per solver cell · FILTER: NEAREST". Default rendering is nearest-neighbour, so you see the solver's actual cubes with hard edges. Switching to linear turns the chip […]

**Stack.** MEEP (Bloch-periodic unit cell) via the repo's existing simulation/meep.py and its _run_in_meep_interpreter delegation […]; gprMax CUDA FDTD on the RTX 5080 via the repo's existing simulation/gprmax.py, for the 28.2 M-cell finite 7×7 array + […]; New simulation/field_export.py — add_dft_fields / get_dft_array / get_dft_array_metadata / get_epsilon_grid / […]; New .rfscene/1 container: JSON manifest + gzipped typed-array blobs, base64-inlined, inflated by the browser-native […]; three.js r16x from cdnjs: Data3DTexture, RawShaderMaterial, custom GLSL ES 3.0 single-pass raymarcher (the stock […]; WebGL2 baseline: gl.TEXTURE_3D, framebufferTextureLayer for the one-time Yee-curl H pass, transform feedback for 100k […]

---

### Deposition Twin — the manufacturing's design

**Thesis.** Simulate and render the geometry the print head will actually deposit — beads, scallops, overspray, edge-thinning, cure-dependent conductivity — instead of the CAD polygon nobody can print, because on a part whose working layer is 10 µm of silver ink the difference between the drawing and the deposit is the whole engineering problem.

**Killer feature.** THE NOZZLE SLIDER. One control, three positions, labelled with the actual nozzles Voltera ships with the NOVA: 100 µm, 150 µm, 225 µm.

Drag it and three things move at once, on one screen, on the same clock:

(1) The printed pattern coarsens in Station 2. Beads get fatter, the drawn 100 µm gap narrows toward closed, the scallop period stretches, the overspray halo grows. The Nordson 1.5x-tip-ID rule floors the achievable trace at 229 µm for the 150 µm tip and 305 µm for the 225 µm tip, and the verdict bar flips from green to red mid-drag with the number that did it.

(2) The reflection-phase curve in Station 4 slides. The +/-90 degree shaded band — the field's own definition of AMC bandwidth — narrows and walks off the required frequency, with its span rewritten in plain words each frame: "2.31 to 2.40 GHz, 90 MHz wide, 3.8% of centre frequency" becomes "no crossing in band."

(3) The yield counter drops. 68% of manufacturing draws in spec at the 100 µm nozzle, 11% at 225 µm.

Nothing else on the page has to be understood for that gesture to land. A CEO who knows nothing about Floquet modes or reflection phase watches a hardware choice — which metal tube is screwed into the […]

**What the user sees.** One page, four stations, one shared time scrubber, one shared color normalization, no photorealism anywhere.

STATION 1 — THE STACK. An exploded edge-on cross-section, rotated maybe 20 degrees, four labelled slabs floating apart with obviously-artificial gaps between them. Top-left corner carries a monospace chip: `VE = 40x`, and both a horizontal and a vertical scale bar so you can check it yourself. Top layer is the printed conductor, drawn as a translucent membrane with NO thickness, chipped `ACI SS1109 silver · 10 µm cured · Rs 0.015 Ω/□ · 6.4x skin depth @ 10 GHz`. Beside it a red-ruled note: "the solver never contained this thickness — openEMS's conducting sheet has no geometry; thickness enters only as 1/(σt)." Below it Melinex 238 PET at 125 µm, εr 3.2, drawn in fine diagonal hatch (LITERATURE-SUPPORTED). Below that, drawn *thicker than the substrate because it is*, 3M 468MP […]

**Physics pipeline.** Two solves per candidate, on two geometries, one shared post-processing path.

(1) GEOMETRY IN. `fabrication/deposition.py` (new) produces the as-printed raster: a float32 thickness field t(x,y) and a derived sheet-resistance field Rs(x,y) = 1/(sigma(cure,thickness) * t) on a 5 µm grid (1200x1200 over a 6x6 mm cell). Inputs are the ideal primitive dicts from `geometry/unit_cell.py:combine_shapes()` plus a real Process record from `designs/element_alphabet.py:add_process_record` (machine, ink […]

**Construction pipeline.** The layer stack, the printed pattern, the curvature and the materials all come from library rows this repo already defines, and reach the screen through three new modules and two new writers.

LAYER STACK. A stack is an ordered list of layer dicts, each resolved through `designs/material_properties.py:resolve_material_property` so every number arrives with its provenance tier and citation attached, never inline. Real rows today: Melinex 238 PET 125 µm / eps_r 3.2 @ 10 GHz […]

**Hardest problem.** The as-printed geometry's most distinctive features live two orders of magnitude below any FDTD mesh you can afford, so "run the simulation on the as-manufactured geometry" is only half-true if you naively hand the solver a fine raster. Edge roughness is ~5 µm and the overspray tail is ~25 µm; a mesh that resolves 5 µm over a 6x6x3 mm cell is 1200x1200x600 = 864 million cells, which is not a run, it is a fantasy. Meanwhile a mesh that IS affordable (25 µm cells, 240x240x120 = 6.9 million cells) simply does not contain the roughness at all — so a page that shows scalloped edges next to a field computed on a mesh that never saw them is exactly the persuasive-but-wrong render this program […]

**Honesty design.** Seven mechanisms, all visual, all structural rather than caption-shaped.

1. VERTICAL EXAGGERATION IS A NUMBER, STAMPED AND DEFEATABLE. Geology's convention imported verbatim — `VE = 40x` in a monospace chip on the figure, BOTH a horizontal and a vertical scale bar so the reader can verify it independently, and a one-click `VE = 1x` companion that collapses the stack to true aspect ratio. The justification is citable in one sentence: Stewart 2011 surveyed 1,437 papers, 75% used VE > 2x, only 12% showed 1:1, and the follow-up showed trained specialists drawing wrong structural conclusions from exaggerated sections. Materials-science practice ("not necessarily to scale") is weaker, so this is […]

**Stack.** Python 3.12 — new modules fabrication/deposition.py and fabrication/as_printed_to_solver.py, extending existing […]; gdstk 1.0.1 — ideal unit-cell polygon boolean composition (already in tree, already exercised against the real library […]; shapely — toolpath offset-infill generation and contour simplification for the Rs region decomposition; scikit-image — measure.find_contours for marching-squares band extraction; filters.gaussian for the overspray kernel; numpy (float32 rasters, seeded default_rng for line-edge-roughness random fields); MEEP (Python) — Bloch-periodic k_point unit cell, material_function for the spatially varying as-printed conductor […]

---

### Ghost Bench — the bench you don't have yet — the skeptic's design

**Thesis.** Render every pixel in the visual material of its evidence tier — solver-lattice ghost for SIMULATED, flat line-art for CALCULATED, stipple-fog for UNKNOWN, opaque solid for MEASURED (which nothing has earned) — so the most ambitious thing on screen is also the thing that can never be mistaken for a photograph of a working part.

**Killer feature.** **The Deafness Dial.** One frequency slider under three synchronized field panes on one shared scale — dipole on bare metal, the same dipole on the metasurface, and the difference.

At 2.35 GHz the metal pane is a dead grey nothing (`|S11| = −0.8 dB` — the antenna is shouting into its own echo) and the metasurface pane is throwing huge red and blue lobes (`|S11| = −24.2 dB`). That alone explains the whole company.

Then you drag. The lobes shrink. By 3.4 GHz the metasurface pane is *pixel-identical* to the metal pane and a line fires: **at this frequency this panel is just metal again.** Same physical part. Same antenna. The magic has a range of 90 MHz — 3.8% of centre — and the CEO watches it run out.

The second half is the same picture with a different knob. Switch the slider to "manufacturing lottery" and each 400 ms pull draws a new ticket from the tolerance ensemble: the band slides left and right under the fixed requirement line, and the tally in the corner reads `in spec: 143 / 200 draws (71.5%)`. So the trade-off arrives whole and without a word of jargon: *this works, it works over a narrow band, and it works 71.5% of the time unless somebody measures the plastic.*

That […]

**What the user sees.** A single dark page. Across the top, not a disclaimer banner but a live status rail: `EVIDENCE — 0 MEASURED · 3 SIMULATED (MEEP 1.29, 0.05 mm grid, Bloch k=0) · 11 LITERATURE-SUPPORTED · 2 UNKNOWN`. Click "0 MEASURED" and the whole page flashes to show you what highlights: nothing does.

**Band 1 — the Deafness Dial.** Three viewports on one clock and one shared scale. LEFT, "BARE METAL": a thin white dipole rod floating 1.35 mm over a mirror-flat conductor, and around it the electric field animating in red/blue — except there is almost nothing to see. The wave leaves the rod, bounces back inverted, and erases itself. A readout: `|S11| = −0.8 dB`. Plain caption: *the antenna is shouting into its own echo*. CENTRE, "PRINTED METASURFACE": identical rod, identical 1.35 mm, now over the printed pattern — and enormous red and blue lobes balloon outward and detach, breathing at 60 fps. `|S11| […]

**Physics pipeline.** MEEP is the solver, run in Docker/WSL2 on the 16-thread host via the existing `simulation/meep.py` adapter, because openEMS has no Bloch boundary at all and therefore cannot answer a single oblique-incidence question in this program.

**Run A — the deliverable curve.** 3D Bloch-periodic unit cell, 6 mm pitch (λ0/5 at 10 GHz, below the λ/(1+sinθ) grating onset at every angle), `resolution=20` with a=1 mm so dx = 0.05 mm → 120×120×60 = 864,000 cells; dt = 83.4 fs at Courant 0.5; 60,000 steps = […]

**Construction pipeline.** `geometry/unit_cell.py` already builds the printed pattern with gdstk booleans and emits simulator-agnostic primitive dicts (`box`/`polygon` + `p1_m`/`points_m`/`normal_axis`/`elevation_m`). That is the fork point, and three branches leave it:

**(1) The exact ideal outline.** gdstk `Polygon.points` (float64, (N,2), metres) is written straight to JSON and drawn in the browser as a 1-pixel gold hairline over the voxel render. This is the *drawing*, and it is the only thing on screen with no […]

**Hardest problem.** **The scene that sells the idea is the exact scene a unit-cell simulation cannot compute.** The counterfactual pair — one dipole over bare metal versus the same dipole over the metasurface — is a single, non-periodic radiator over a finite structure. A Bloch-periodic unit cell computes an infinite, flat, perfectly uniform array under one plane-wave harmonic, and contains literally zero information about a lone antenna, an edge, or a finite array. This is not a modelling preference; a 2019 EPJ Applied Metamaterials paper (DOI 10.1051/epjam/2019014) exists specifically because bridging that gap is unsolved enough to warrant its own publication. Brute force is out: a 10×10 array at 0.05 mm is […]

**Honesty design.** **Evidence is the rendering material — a non-color channel, so it survives greyscale, colorblindness, and a bad projector.**
- MEASURED → opaque, smooth-shaded, crisp-edged, fully saturated. Present in the legend as a swatch. Applied to nothing, ever, today. The legend line reads `MEASURED — 0 elements qualify (designs/element_alphabet.py: 0 rows)`.
- SIMULATED → a translucent ghost with the **actual 0.05 mm solver lattice etched into every surface** and a slow scanline. It looks computed because it was. Crucially, this etching is baked into the pixels, so a screenshot pasted into a slide deck carries the label with it.
- CALCULATED → flat vector line-art, unshaded, no volume — closed form […]

**Stack.** Python 3.12 + MEEP 1.29 (Docker on WSL2, MPI across 16 threads) — extends the existing simulation/meep.py adapter; MEEP […]; MEEP APIs: add_flux (complex 0th-order r), add_dft_fields + get_dft_array + get_dft_array_metadata (complex field […]; NumPy + h5py + SciPy (Lorentzian fit of surface impedance Z_s(omega); response-surface regression for the tolerance […]; gdstk (already in geometry/unit_cell.py) — exact ideal polygon, float64, metres; FreeCAD via geometry/freecad_curved.py -> STEP (source of truth); trimesh + pygltflib -> GLB (browser, one-way) […]; New module visualization/export_web.py: VOLPACK v1 (JSON header {dims, origin_m, spacing_m, scale, offset, provenance} […]

---

### PHASOR — the frameless field — the graphics's design

**Thesis.** A time-harmonic field is not a movie you have to store — it is a single complex volume plus one cosine, so the entire animation can be evaluated analytically in the shader at 60fps, which means every frame the reader scrubs to is exactly what the solver computed rather than an interpolation between decimated keyframes; that one fact makes the gorgeous interactive thing and the honest thing the same thing.

**Killer feature.** **The draggable wipe.**

One 3D scene, one camera, one clock, one stated colour scale, split by a vertical hairline you drag with the mouse. Left of it: a dipole 2.1 mm above bare metal. Right of it: the identical dipole 2.1 mm above the designed metasurface. Same source, same frequency, same instant of time.

On the left, the reflected wave comes back inverted and collides with the outgoing wave at the antenna. The shells cancel. The region around the dipole is a dead grey null that breathes and never brightens. On the right, the reflection comes back in phase and the same region blooms into a hard antinode twice per cycle.

Drag the hairline across the antenna and you *watch the metasurface leave*. The antinode collapses into the null under your hand, in real time, at 60fps, at whatever point in the RF cycle you have the scrubber parked at. Drag it back and the field returns.

Pinned beside it, two numbers from the literature: **−0.8 dB return loss over metal, −24.2 dB over the AMC**, at a profile of 0.045λ. In plain language on the same line: *on bare metal the antenna reflects almost all its power straight back into itself — it is effectively deaf. On this surface it […]

**What the user sees.** A dark slate viewport, edge to edge. Floating in it: a dipole antenna 2.1 mm above a surface, seen at a shallow orbit. A vertical hairline splits the scene. Left of the hairline the surface is bare aluminium; right of it, the designed metasurface. It is one camera, one scene, one clock — you orbit and both halves orbit together.

The field is alive. Nested luminous shells of electric field pulse outward from the dipole, hit the surface, and come back. On the left they come back inverted and collide with the outgoing wave right at the antenna — the shells there visibly cancel into a dead grey null that breathes but never brightens. On the right they come back in step, and the same region blooms into a hard blue-white antinode twice a cycle. Drag the hairline left and you watch the metasurface slide out from under the antenna and the antinode die in real time. That single gesture is the […]

**Physics pipeline.** **Solver: MEEP** (not openEMS — openEMS has no Bloch boundary at all, so every oblique-incidence question is MEEP-only; export ergonomics do not get to decide this).

**Run.** Bloch-periodic unit cell via the repo's existing `_boundaries_and_k_point` in `simulation/meep.py` (extended to accept a non-zero `k_point`, which it currently refuses). Cell 6×6 mm pitch × 3 mm tall, `resolution` from `mesh_cell_size_m = 5e-5` → 120×120×60 = 864,000 Yee cells. Gaussian-pulsed plane-wave source […]

**Construction pipeline.** **STEP stays the source of truth.** `geometry/freecad_curved.py` already emits a STEP solid via `TopoShape.exportStep()`. Nothing in this design round-trips a triangulated format back into CAD — that conversion cannot be automated and pretending otherwise corrupts the design record.

**New hop: `viz/glb_export.py`.** FreeCAD tessellates the STEP → trimesh → glTF 2.0 binary (`.glb`) for the browser. Two rules, both non-negotiable at this aspect ratio: (1) rebase the origin in **float64 before** […]

**Hardest problem.** **Direct volume rendering is a path integral, and a path integral is quantitatively unreadable — so the most beautiful view is the one most likely to lie.**

A raymarched DVR accumulates colour and opacity along the ray. A long dim region and a short bright region produce identical pixels; the brightness you perceive carries an unstated path-length term you cannot invert by eye. Layer on Cleveland & McGill's measured encoding errors — colour saturation reads at ±18%, area/volume at ±12%, versus ±1.3% for position on a common scale — and the honest conclusion is that a gorgeous glowing field volume is a persuasion device with no readable magnitude in it. The audience is a CEO and a systems […]

**Honesty design.** **The core structural honesty is that the animation is exact.** Every scrub position is Re(Ê·e^{−iωt}) evaluated from the solver's own complex output — not a keyframe, not a decimated dump, not an interpolation. The banner says *this animation has no frames*. That is the opposite of the usual situation where a smooth 3D animation is a decimated artist's impression the audience cannot distinguish from data.

**Evidence tier is a material property in the shader, not a caption.** Colour is reserved for physics; provenance gets non-colour channels, which is exactly the established cartographic practice:

- **MEASURED** → smooth, opaque, crisp specular. **Nothing in the scene qualifies.** The […]

**Stack.** MEEP (pymeep 1.34+) under WSL2 or the repo's existing Dockerfile — add_dft_fields / get_dft_array / […]; NumPy 2.2 + h5py 3.16 (already in the env) for DFT post-processing: ½Re(E×H*), J = n̂×H, log-magnitude/phase […]; New repo modules: viz/dft_export.py, viz/phasorpack.py (writer), viz/poynting.py, viz/tolerance.py, viz/stack.py […]; PhasorPack container — a plain .zip of manifest.json + raw .bin planes, Neuroglancer-'precomputed' philosophy: static […]; WebGPU / WGSL — compute-shader raymarch writing to a storage texture, trivial blit pipeline; RK4 streamline compute […]; three.js r17x pinned from cdnjs — scene graph, OrbitControls, GLTFLoader, and a WebGL2 fallback raymarch. NOT the stock […]

---

### WAVE TUNNEL — the instrument that shows you what the solver actually knows — the moonshot's design

**Thesis.** Ship one browser URL containing a real MEEP frequency-domain field, animated forever from a single static complex dataset by the shader identity Re{E·e^{-iωt}}, presented as a continuous zoom from a vehicle panel down to a printed droplet in which trustworthiness is a *function of scale* and the render's own material changes to say so — peaking at the one unit cell that was actually computed, and visibly degrading in both directions.

**Killer feature.** **The split-screen counterfactual with a frequency scrubber — where the CEO breaks the product himself.**

Left half: the antenna on bare metal. Right half: the same antenna, same wave, same clock, same colour scale, on the metasurface. At 10.0 GHz the difference is impossible to miss — a dead black null pinned against the metal on the left, a bright standing antinode against the printed surface on the right, with −0.8 dB and −24.2 dB return loss printed beneath, and the profile at 0.045 wavelengths.

Then he drags the frequency slider. 10.4 GHz: the right side dims. 10.9 GHz: the right side goes as dead as the metal. Same part. Same picture. Nothing changed but one number.

That is the entire trade-off of this program — **thin and loud, but only over a narrow band, and only if the part is big and flat** — delivered in four seconds without a word of RF vocabulary, and delivered by the reader's own hand rather than by a caption he has to take on faith. The ±90° band shades in beneath as he drags, labelled in full: "310 MHz wide, 3.0% of centre frequency." Everything else on the page exists to be trustworthy; this one view exists to be *understood*, and it is the only one that has […]

**What the user sees.** You open a link. No install, no licence, no account.

A dark field. Centre screen, a single 6 mm square tile of printed silver on a pale substrate, floating, lit flatly like a technical drawing rather than a photograph. A plane wave is arriving from the upper left — not a cartoon arrow but a real computed field, rendered on a vertical slice through the cell as bands of red and blue (RdBu, MEEP's own house colours) that slide continuously toward the surface at 60 fps. The bands hit the printed pattern and stand still: a standing wave, with a bright antinode pinned exactly at the surface.

Down the middle of the world runs a draggable divider. Grab it and pull left: the same antenna, the same wave, the same clock — but the surface underneath is bare metal. On that side the antinode is gone. In its place a dead black null sits flat against the metal, and the dipole floating a millimetre […]

**Physics pipeline.** **Solver.** MEEP 1.29 (FDTD), built `--enable-single` for float32, in Docker under WSL2 on the RTX 5080 box. MEEP and not openEMS because openEMS has no Bloch/Floquet boundary at all — only PEC/PMC/MUR/PML — so every oblique-incidence and angular-stability question in this program is MEEP-only. Physics decides the solver; export ergonomics do not.

**Setup.** Cell 6 × 6 mm (pitch = λ₀/5 at 10 GHz, λ₀ = 29.98 mm) × 3 mm tall. `a = 1 mm`, `resolution = 20` → dx = 0.05 mm, which puts 4 cells […]

**Construction pipeline.** **One geometry, provably.** `geometry/unit_cell.py` composes the printed pattern with gdstk booleans and emits simulator-agnostic primitive dicts (`shape:"box"` + `p1_m`/`p2_m`, or `shape:"polygon"` + `points_m`/`normal_axis`/`elevation_m`). Those exact dicts are what `simulation/meep.py::_primitive_to_meep` and `simulation/openems.py::_primitive_xml` consume. The bake hashes that primitive list (SHA-256, first 8 hex) and prints the hash in the burned-in stamp bar — so the render and the solve […]

**Hardest problem.** **The screenshot.** Every honesty mechanism I have described — the trust gauge, the hover provenance cards, the warning objects, the empty MEASURED swatch, the plain-language captions — lives in the chrome. The moment someone crops the pretty part of the canvas and pastes it into a board deck, all of it is stripped, and what reaches the decision is a beautiful field render implicitly asserting an infinite-periodic result about a real, finite, curved vehicle panel. That is exactly the failure this program exists to prevent, propagating at the speed of PowerPoint, and no caption can follow the image.

The solution is that **the honesty has to be in the pixels, not around them**, in three […]

**Honesty design.** **The trust gauge is inverted and it is the first thing you learn.** One gauge, top-right, 40 px. It fills as you zoom *in* and drains as you zoom *out* — and drains again if you zoom past the cell to the print. It peaks at exactly one scale, the 6 mm unit cell, because that is the only thing MEEP computed. Every other station is extrapolation in one direction or manufacturing model in the other. A CEO learns the entire epistemology of this program by scrolling a wheel, before reading a sentence.

**Five materials, one of them empty.** MEASURED (polished, specular) is applied to zero surfaces and its legend swatch says so out loud. That empty swatch makes "fill the alphabet — print and […]

**Stack.** MEEP 1.29 (FDTD), built --enable-single for float32, in Docker under WSL2 on the RTX 5080 — chosen over openEMS because […]; Python 3.12 bake pipeline: numpy, scipy.ndimage (resampling), h5py (raw archive), Pillow (colormap LUT PNGs) — […]; MEEP export APIs specifically: add_dft_fields / get_dft_array / get_dft_array_metadata (tics arrays give […]; geometry/unit_cell.py (gdstk) — the SAME primitive dicts consumed by simulation/meep.py::_primitive_to_meep, hashed […]; geometry/freecad_curved.py → STEP → trimesh → GLB (origin-rebased in float64, exported in metres, Draco and […]; gdsfactory → Gerber (the only Python tool with native Gerber output) so the part on screen can actually be printed […]

---

## Judge notes (incomplete — 23 of 24, unranked)

Scores are not aggregated because the run never completed. Kept for the ideas the
judges flagged as worth stealing and the flaws they caught.

- **truth** 7/10 — *steal:* Making the interaction affordance itself the provenance encoding: the analytic bound is draggable and stays crisp, the simulated curve ghosts out the instant you leave the thickness it was run at […] — *flaw:* The killer feature's headline is a category error the design's own safeguards cannot detect. "24.2 dB delivered" and "0.8 dB delivered" are return loss -- impedance match -- not delivered signal […]
  <br>Error caught: "24.2 dB delivered" / "0.8 dB delivered" mislabels return loss as delivered signal. RL 0.8 dB -> 16.8% delivered (-7.74 dB); RL 20 dB -> 99.0% (-0.04 dB). True delivered-power improvement across the […]
- **decide** 7/10 — *steal:* The nozzle slider, specifically its COUPLING: one physical, purchasable object driving three readouts that move together on one screen — the printed pattern coarsening, the reflection-phase band […] — *flaw:* It is a single-candidate instrument built for an audience whose stated job is choosing among candidates. The repo already has the ranking layer — `orchestration/solver.py` […]
  <br>Error caught: Station 1's headline chip is internally inconsistent: Rs 0.015 ohm/sq at 10 um cured implies sigma = 1/(Rs*t) = 6.67e6 S/m, giving skin depth 1.95 um at 10 GHz and a ratio of 5.1x, not the stated […]
- **decide** 7/10 — *steal:* The frequency slider applied to the wipe — "the same physical panel is a magnetic mirror inside its ±90° band and ordinary metal outside it." Drag to 3.5 GHz and the right half of the scene collapses […] — *flaw:* The thing it makes gorgeous is not the decision. The entire product is built to answer "metasurface versus bare metal" — a question with a known answer that nobody in the room disputes — while "which […]
  <br>Error caught: Conductor label is self-inconsistent: σ = 1.05×10⁷ S/m at t = 10 µm gives Rs = 0.0095 Ω/□, not the stated 0.012 Ω/□ (0.012 implies σ = 8.3×10⁶ S/m). A 26% discrepancy on the one label whose stated […]
- **ambition** 7/10 — *steal:* THE NOZZLE SLIDER — specifically, the principle that the control the decision-maker turns should be a purchasable part number, not a simulation parameter.

Every EM tool ships parameter sweeps. None […] — *flaw:* IT STOPS AT DIAGNOSIS WHERE THE FIELD IS ALREADY AT CORRECTION — AND THEN ARCHITECTURALLY LOCKS ITSELF OUT OF THE FIX.

Having built a full forward model of deposition (toolpath, bead crown […]
  <br>Error caught: WRONG, and it changes the architecture: 'MEEP with k_point Bloch periodic (openEMS has no periodic BC at all, so every oblique-incidence and angular-stability question is MEEP-only)' and 'the ONLY […]
- **decide** 6/10 — *steal:* Bind the interactive control to the ENGINEERING CONSEQUENCE, not to the RF quantity. The antenna-height slider whose readout is a caliper snapping from 1.5 mm to 7.5 mm is the whole method in one […] — *flaw:* The killer feature's two headline numbers are matching numbers wearing a loudness label, and the plain-language gloss teaches an actively wrong causal model. −24.2 dB and −0.8 dB are return loss: how […]
  <br>Error caught: WRONG AGAINST THE REPO: 'the repo's existing simulation/gprmax.py adapter reaches a CUDA FDTD solver.' E:/Principle_RF_Engineer_Agent/simulation/gprmax.py, module docstring ~line 298, states plainly […]
- **build** 5/10 — *steal:* The two-tier split with the residual PRINTED AS A NUMBER — "Tier 1 says 4.2 degrees at 10.0 GHz, Tier 2 says 5.1 degrees, delta 0.9 degrees against a +/-90 degree band." It converts an unavoidable […] — *flaw:* Tier 2 — the sole mechanism that makes the ambitious claim ("the simulation ran on the as-manufactured geometry") honest — cannot execute on this hardware, and the document contradicts itself about […]
  <br>Error caught: Tier 2 is self-contradicted: the document calls 1200x1200x600 = 864M cells at 5 µm 'not a run, it is a fantasy', then specifies Tier 2 as exactly that (a 6x6 mm cell at 5 µm, MEEP only). MEEP's […]
- **ambition** 8/10 — *steal:* **Provenance rendered as a non-colour material channel, with the empty MEASURED swatch as its punchline.** Colour is spent entirely on physics; evidence tier is carried in surface character — […] — *flaw:* **The ambition is entirely spent on how honestly the picture is drawn, and none of it on what the reader can do — it is a magnificent read-only post-mortem for a decision that requires exploration.** […]
  <br>Error caught: `decimation_factor=0` does not mean 'no decimation' — it is Meep's sentinel for AUTOMATIC decimation, computed from the Nyquist rate of the sources and monitor (introduced in NanoComp/meep PR #1732 […]
- **build** 6/10 — *steal:* The frameless phasor: store the solver's complex field Ê(x) once as a static texture and evaluate E(x,t) = Re(Ê·e^{−iωt}) in the fragment shader — one cosine, no stored frames.

This is correct […] — *flaw:* The hero scene cannot come out of the described simulation, and the design never notices.

The physics pipeline is a Bloch-periodic 6x6x3 mm unit cell under plane-wave illumination. The killer […]
  <br>Error caught: "64 complex volumes = 663 MB" is ~8x low. 864,000 cells x 6 components x complex128 (16 B) x 64 frequencies = 5.31 GB (2.65 GB if complex64). The design then re-quotes 663 MB as "the full 663 MB […]
- **truth** 6/10 — *steal:* The ideal-vs-solver epsilon difference view (key G): render `get_epsilon_grid(...)` — the geometry as drawn, at arbitrary resolution — against `get_array(component=mp.Dielectric)` — what MEEP […] — *flaw:* The hero image and the killer feature depict a problem the described solver run does not solve.

"WHAT THE USER SEES" and "KILLER FEATURE" both show a single dipole 2.1 mm above the surface, with […]
  <br>Error caught: "64 complex volumes = 663 MB" is wrong by 8x. 864,000 cells x 6 components x complex128 (16 B) x 64 frequencies = 5.31 GB. 663 MB is exactly 864,000 x 12 B x 64 - i.e. the uint8 magnitude + uint8 […]
- **ambition** 7/10 — *steal:* The finite-vs-infinite divergence as the headline number, backed by a real second simulation instead of a caption: "the infinite-array model says the reflection phase is +12°; the 7×7 finite patch […] — *flaw:* The ambition is aimed at the wrong axis: it is a magnificently instrumented viewer for a solve that has already finished. Nothing on the page lets the reader change the design and watch the physics […]
  <br>Error caught: FALSE REPO CLAIM (verified): 'the repo's existing simulation/gprmax.py adapter reaches a CUDA FDTD solver' is contradicted three times by E:\Principle_RF_Engineer_Agent\simulation\gprmax.py itself […]
- **truth** 7/10 — *steal:* Provenance as a surface treatment, with MEASURED defined in the legend and deliberately left empty — "MEASURED — not yet earned." Three properties make it the strongest idea here. It is read from […] — *flaw:* Station 3 renders sub-mesh structure as if it were solved. The line-integral-convolution surface current comes from the Tier-1 25 µm solve but is convolved through the 5 µm as-printed raster's […]
  <br>Error caught: Station 1's chip 'Melinex 238 PET at 125 µm, εr 3.2, LITERATURE-SUPPORTED' contradicts the repo on grade, value, tier and — critically — band. designs/material_properties.py:829-846 carries PET only […]
- **build** 6/10 — *steal:* Co-export the field volume from the *same* MEEP solve that already produces the S-parameters — attach `add_dft_fields` to the existing run rather than a second one. It is a small diff to a module […] — *flaw:* The 8-bit block-float quantization and the "derive everything in the shader" architecture are arithmetically incompatible, and this takes out most of Phase 3 plus one of the three named failure […]
  <br>Error caught: `decimation_factor=0` does not mean 'no decimation'. MEEP documents 0 as the default meaning the value is automatically determined from the Nyquist rate of the bandwidth-limited sources and the DFT […]
- **truth** 7/10 — *steal:* The permanently greyed-out MEASURED swatch captioned "no panel on this page has earned this," sitting in the legend beside the hatched SIMULATED swatch that every panel actually wears. It costs […] — *flaw:* The flagship failure detector is structurally incapable of failing, and the design's entire claim to truth rests on it. The ∇·(εE) view is promised to go black except at element tips, with "if the […]
  <br>Error caught: 'H = ∇×E/(iωμ₀) exactly' is false as specified. `add_dft_fields` defaults to `yee_grid=False`, and MEEP's docs state the DFT array is bilinearly interpolated to the centre of each voxel. A […]
- **build** 6.5/10 — *steal:* STEP 3 — ship one complex frequency-domain DFT volume and synthesize every animation frame in the fragment shader as Re(E(x,y,z) * e^{-i*omega*t}) with t as a single float uniform. It is exact for a […] — *flaw:* The Phase 1 cross-validation gate — the entire de-risking premise, the thing that is supposed to prove the page's central number in week one — compares two quantities that are not the same quantity […]
  <br>Error caught: 'MEEP ... the only one of the two FDTD adapters with a k_point, so the only one that can answer oblique incidence at all' is wrong about the adapter. simulation/meep.py's _boundaries_and_k_point […]
- **ambition** 8/10 — *steal:* Draggability as the encoding of epistemic status — "law drags; result does not." Analytic relationships respond continuously to interaction because they are valid everywhere; computed results visibly […] — *flaw:* The hero — the precise thing the user asked for — is the least ambitious element in the design, and the two halves of their ask never appear in the same picture. The user said "I want to see the EM […]
  <br>Error caught: Return loss is conflated with delivered signal strength, and this corrupts the killer feature's headline number. The page reads '0.8 dB delivered. The antenna is talking into a wall' versus '24.2 […]
- **decide** 7/10 — *steal:* The frequency scrubber as a self-inflicted failure: the reader drags one slider and watches the product stop working, so bandwidth stops being a spec line and becomes something he did with his own […] — *flaw:* It is built to win the argument "should we use metasurfaces at all" — a question asked once — while the selection question it was actually commissioned to serve ("which of these candidates, with how […]
  <br>Error caught: Internal contradiction on the killer feature: the demo opens 'bright' at 10.0 GHz and dims at 10.4, but the stated ±90° AMC band is 10.31–10.62 GHz (centre 10.465 GHz, consistent with 310 MHz / […]
- **ambition** 7/10 — *steal:* The render-level refusal, paired with tier-as-material. Rather than warning that an infinite-periodic result does not describe a finite curved panel, the scene graph is built so that no camera angle […] — *flaw:* It refuses to show the EM field in 3D — the thing the user asked for three times, escalating — and justifies that refusal with arithmetic that contradicts its own design. The 1.728 GB/instant and […]
  <br>Error caught: Solver-choice rationale is inverted for its own stated deciding factor. MEEP's Bloch boundary fixes k, not angle: MEEP's docs state that with a pulsed source an oblique planewave 'is incident at a […]
- **decide** 7/10 — *steal:* The frequency drag that ends in the metasurface pane becoming pixel-identical to the bare-metal pane — "at this frequency this panel is just metal again — reflection phase 180°." Narrow bandwidth is […] — *flaw:* The killer feature's headline number is the wrong physical quantity, and the audience is defined as unable to notice. |S11| = −0.8 dB versus −24.2 dB measures how well the antenna's feed is […]
  <br>Error caught: |S11| is presented as the measure of antenna loudness ('the antenna is shouting into its own echo' at −0.8 dB versus huge radiating lobes at −24.2 dB). S11 is feed-port impedance match, not radiated […]
- **ambition** 8/10 — *steal:* Provenance baked into the pixels: render every surface in the material of its evidence tier, and for SIMULATED specifically, etch the solver's *actual* 0.05 mm voxel lattice into the surface rather […] — *flaw:* The ambition is spent entirely on the epistemics layer while the compute layer stays conservative — and the single most ambitious move actually available is explicitly demoted to a "cartoon" in the […]
  <br>Error caught: Oblique incidence is set up wrongly. 'k_point set per incidence angle' plus one broadband Gaussian pulse yielding 401 fixed-angle frequency points is not how Bloch-periodic FDTD works: a fixed […]
- **build** 6/10 — *steal:* The Re{E·e^{-iωt}} shader identity over a static complex DFT field — and specifically its second-order consequence, which the vision states but undersells. One broadband GaussianSource run with […] — *flaw:* The killer feature's headline numbers cannot come from the described pipeline, and the design does not notice. Everything specified is a Bloch-periodic unit cell driven by a plane wave — which yields […]
  <br>Error caught: MEEP has no GPU support — the FAQ states plainly it does not support CUDA/OpenCL, and NanoComp/meep discussion #2121 explains why the port hasn't happened. 'Weeks of GPU time' for 500 MEEP runs and […]
- **decide** 6/10 — *steal:* "Law drags; result does not" — encoding epistemic status in the interaction affordance itself rather than in a label.

The thickness slider moves the analytic Gustafsson/Brewitt-Taylor ceiling live […] — *flaw:* The killer feature is physically backwards, and the number it burns into the CEO's memory is the wrong kind of decibel — so the single gesture designed to be repeated in meetings teaches a falsehood […]
  <br>Error caught: KILLER FEATURE INVERTED. 'On the right pane, over the metasurface, the field was already at maximum at 0.9 mm and does not change for the entire drag' to 7.5 mm is wrong. A horizontal dipole over a […]
- **build** 6/10 — *steal:* Shader phase synthesis: ship ONE complex DFT field and animate it as Re(E * exp(-i*omega*t)) with omega*t as a fragment-shader uniform, so an N-frame movie costs one static dataset and one float.

It […] — *flaw:* The 864,000-cell domain (120x120x60 = 6x6x3 mm) is not a viable FDTD domain for the 2-14 GHz sweep it claims, and MEEP's uniform grid means it cannot be rescued cheaply.

Three millimetres of z must […]
  <br>Error caught: 'k_point set per incidence angle' with a broadband Gaussian does NOT yield r(f, theta) at constant theta. Bloch boundaries fix the transverse wavevector k_x, not the angle; since |k| = omega/c, one […]
- **truth** 7/10 — *steal:* The invariant "render only what the solver actually meshed; everything else goes on a detached tether explicitly marked not in the simulation" — instantiated as the zero-thickness conductor membrane […] — *flaw:* A priority inversion in the honesty accounting: the framework is meticulous about small, cheap, disclosable errors and silent about the two large ones that carry all the persuasion — both inside the […]
  <br>Error caught: The advertised ±90° band of 2.31–2.40 GHz (90 MHz, 3.8% of centre) is not physically producible from the stated stack. AMC fractional bandwidth ≈ ω0·µ0·h/η0; with h = 125 µm PET at 2.35 GHz that is […]

