# Literature validation cases (issue #386)

Four published metasurfaces, each reconstructed from a paper that carries
**both** a fully specified fabricated geometry **and** a measured curve, and
posed to this repository's own solvers so the prediction can be scored against
somebody else's bench.

The cases live in `verification/simulator_reference_cases.py` alongside the
existing closed-form ones, not in a parallel harness. This document is the
write-up they are required to have.

---

## What this closes, and what it does not

The reference cases that came before these check a solver against **algebra** —
a half-wave dipole's 73 + j42.5 Ω, a matched resistive sheet's exact one half.
Those prove the plumbing works: that we write the input file correctly, that
the solver runs, that we read the answer back without dropping a factor.

They prove nothing about the question that actually matters here. *No free
solver has ever been shown, in this repository, to reproduce a **measured**
printed metasurface.* Until one is, every `SIMULATED` number this program emits
rests on an untested assumption about the solver itself.

*In plain terms: we have checked that the calculator adds up. We have never
checked that when somebody built the thing and pointed a radar at it, we would
have predicted what came back.*

**This ticket does not close that.** It builds the four cases, executes the one
this repository can actually pose, and names precisely what is missing on the
other three. Read the status table before reading anything else.

---

## Status at a glance

| # | Case | Paper | Status | Why |
|---|---|---|---|---|
| 1 | Cross-polarisation converter, RCS reduction, FR4, 4–20 GHz | arXiv:2607.10687v1 | **UNRESOLVED** | The seven optimised dimensions are printed as a bare value list; which symbol labels which feature exists only as leader lines on Fig. 1(d). The pattern cannot be reconstructed uniquely. |
| 2 | Bianisotropic Huygens' metasurface, RT/duroid 6010, 20 GHz | arXiv:1812.05084v1 | **UNRESOLVED** | Table I fixes three numbers per cell; every other dogbone and loaded-dipole dimension is Fig. 10-only. Separately, the substrate permittivity is not stated in the paper at all. |
| 3 | Band-pass FSS, silver paste dispensed on 3D-printed ABS, ~10 GHz | arXiv:2511.16777v1 | **EXECUTED → FAIL** | Runs today. Stop-band lands where the paper says; passband is ~1.3 dB too shallow, against the paper's own 1 dB gap. Named suspect: the paste's own loss, which the paper does not publish enough to reconstruct. |
| 4 | Varactor-tuned RIS unit cell, WR-28 waveguide simulator, 28 GHz | arXiv:2608.06541v1 | **UNRESOLVED** | No adapter here can pose it. It needs a discrete R–L–C element inside a periodic cell, and those two capabilities live in different adapters. |

Three of the four have **not been run**, and this document does not pretend
otherwise. `verification/README.md` records the repository making exactly that
mistake before — registering scaffolding for a test nobody executed and writing
it up as though it were a result — and the whole outcome vocabulary here exists
so it cannot recur silently.

---

## Scope limits — what passing all four would license

Even if all four passed tomorrow, the claim earned would be narrow and it is
worth writing down before anybody quotes a green result:

- **Passive** surfaces only. Nothing here has gain, and case 4 — the only one
  with an active component in it — is the one no solver here can pose.
- **Planar** surfaces only. Flat sheets. Case 3's paper also builds a
  hemispherical version and that curve is deliberately excluded (see below).
- **Periodic** unit cells only, repeating infinitely in both directions. Real
  parts have edges; edges diffract; none of that is in any of these models.
- A **known substrate**. Every case takes the dielectric constants as given —
  and two of the four had to take them from a datasheet because the paper never
  printed them.
- **Normal incidence**. Waves arriving head-on. Case 1's paper is the only one
  of the four with measured oblique-incidence data, and case 1 is unresolved.
- Roughly **4 GHz to 30 GHz**. Case 1 spans 4–20 GHz, case 3 sits around
  10 GHz, case 2 at 20 GHz and case 4 at 28 GHz.

Outside that box a `SIMULATED` label means what it meant before this document
existed: a solver ran and produced a number that looked reasonable.

### The gap that matters most: no artificial magnetic conductor

**There is no usable artificial-magnetic-conductor case among the four, so the
magnetic-mirror physics has zero validation coverage.**

*An artificial magnetic conductor is the surface that reflects a radio wave
back the right way up instead of upside down — the thing that lets an antenna
lie flat against metal and still work, instead of going deaf.* That is the
physics `CONTEXT.md` opens with as this program's motivating example, and it is
the behaviour most of the designs this program is meant to propose will depend
on.

None of these four papers builds one. Case 1 is a polarisation converter over a
ground plane, which is a different mechanism entirely; cases 2 and 3 are
transmissive; case 4 is a tunable phase surface. Completing this ticket leaves
the magnetic mirror exactly as unvalidated as it was before, and a green result
on any of the four must not be read as saying otherwise.

Closing that gap needs a published AMC with a fabricated geometry and a
measured reflection-phase curve, added here as a fifth case.

---

## How a pass band is set here

Never by choosing a tolerance. Each expected value's band is

> `max(digitization error, the paper's own published simulated-versus-measured gap)`

and both inputs are recorded on the case so a reader can argue with either.

**Digitization error** is how accurately the number can be recovered from the
paper at all — a fraction of a gridline interval where a curve has to be read
off a figure, or the rounding of the quoted digits where the paper prints the
value in its text. It is never recorded as zero; `PassBand` refuses that
outright. *In plain terms: how blurry the published number is.*

**Published gap** is how far the paper's own simulation missed the paper's own
measurement — an accuracy bar taken from the literature instead of one we
invented. Where a paper publishes no such comparison for a quantity, the
digitization error alone sets the band and `PassBand.set_by` reports
`"digitization"` so nobody has to guess which input did the work.

Two consequences worth stating plainly rather than burying:

- **Some of these bands are very wide.** Case 1's C-band band is 1.14 GHz on a
  7.8 GHz feature. That is what the authors' own simulation-versus-measurement
  offset was, so it is what the literature entitles us to demand. A band that
  wide can only catch a gross error. Inventing something tighter would make the
  check circular, so the width stands and this paragraph is the warning.
- **Reflection and transmission are scored separately and never summed.** Two
  errors of opposite sign cancel inside a total: a surface that reflects far too
  much and transmits far too little posts a perfectly respectable absorbed
  fraction while being wrong twice. `CaseScore` deliberately carries no total,
  no mean and no aggregate error.

### UNRESOLVED is a real outcome

`PASS`, `FAIL`, `UNRESOLVED`. The third is not a euphemism for failure. It is
returned when the paper's information is insufficient, the reconstruction is
ambiguous, or no solver here can pose the problem — and when it is returned,
nothing is scored at all, however well a provisional result happens to line up.

Forcing every case into pass/fail would turn missing information into a verdict.
A pass would flatter a guessed geometry; a failure would indict a solver for our
own drawing. Neither is a fact about the world.

---

## Case 1 — cross-polarisation converter for RCS reduction

**arXiv:2607.10687v1** — Chaudhry, Abdullah, Liaquat, Haider, Khan and Hasan,
*Design and Experimental Validation of a Multiband Cross-Polarization
Conversion (CPC) Metasurface for Radar Cross Section (RCS) Reduction.*

*A cross-polarisation converter reflects a wave back with its orientation
rotated by a quarter turn. A radar listening for its own polarisation then
hears very little, which is one route to making an object harder to see.*

**Scored against** Fig. 6, the measured co- and cross-polarised reflection
magnitudes, at the three conversion frequencies section III-D names in its text.

**Deliberately excluded**: Fig. 7(b)'s monostatic RCS curves. Those are a
144 mm × 144 mm finite panel measured against a 10 cm × 10 cm metal plate, and
every periodic solver here models an infinite repeating cell. The
finite-aperture edge diffraction the paper itself blames for its shortfall is
not in our model at all.

**Reconstruction.** FR4, εᵣ = 4.4, tan δ = 0.02, 1.6 mm thick, over a copper
ground plane (so the structure transmits nothing — everything it does happens in
reflection). Copper 5.8 × 10⁷ S/m, 0.035 mm. Unit cell period 7 mm both ways.
The paper prints its seven optimised dimensions: a = 6, s = 2.5, m = 1.5,
b = 0.58, p = 1, z = 7, d = 2 mm.

**Why it is unresolved.** It never says which symbol labels which feature. That
mapping is on Fig. 1(d) as leader lines and nowhere else. Two split rings and a
corner circular ring have well over seven independent dimensions between them,
so the values cannot be attached to features from the text alone. Anything drawn
and solved here would be a plausible guess scored against somebody else's
measurement. Closing it needs Fig. 1(d) read by eye against the value list, or
the authors asked.

**Accuracy bar, from the authors.** Section III-D: *"A frequency offset of
approximately 0.5–3 GHz is observed between simulated and measured CPC
frequencies, with the deviation being most prominent in the Ku-band."* The
per-band number used is that same comparison done arithmetically on the paper's
own two sets of figures — simulated 6.66 / 9.75 / 15.1 GHz against measured
7.8 / 11.7 / 18 GHz — giving bands of 1.14, 1.95 and 2.90 GHz. They widen
towards the Ku band, exactly as the sentence says they should.

**Digitization error**: 0.2 GHz. The measured frequencies are quoted in the body
text to 0.1 GHz (worth ±0.05 GHz on its own); recovering the same peaks from
Fig. 6, whose frequency axis spans 4–20 GHz with 2 GHz major divisions, is good
to about a tenth of a division. The larger is used. In every band the published
gap is the wider of the two, so the published gap sets the band.

**Not scored**: the polarisation conversion ratio. The paper states it as a
bound ("exceeding 95%"), not a point, and a two-sided band around a bound
rejects correct answers on the permitted side of it.

**Pinned at**: `simulation/meep.py` @ `127c8a5`, pymeep 1.34.0 — the
Bloch-periodic path the case is written against. Not yet run.

---

## Case 2 — bianisotropic Huygens' metasurface

**arXiv:1812.05084v1** — Chen, Abdo-Sánchez, Epstein and Eleftheriades, *Theory,
design, and experimental verification of a reflectionless bianisotropic
Huygens' metasurface for wide-angle refraction.*

*A Huygens' metasurface bends a beam by giving each patch of the sheet its own
phase delay. The "bianisotropy" is the extra ingredient that stops the sheet
reflecting while it bends — without it, a sheet asked to bend a wave this far
throws a lot of it straight back.*

**Scored against** Fig. 18's measured specular reflection (0th reflected mode)
for the reflected share, and section IV-B's measured scattered refraction
efficiency at 20.6 GHz for the transmitted share. **Two quantities, two
buckets, never summed** — this surface is meant to reflect nothing and refract
everything, so it is exactly the shape where a combined total would hide a
double error.

**Reconstruction.** Three 18 µm copper layers on two 0.635 mm RT/duroid 6010
substrates bonded with a 0.0508 mm Rogers 2929 bondply; 1.3208 mm overall. Unit
cell 1.58 × 1.58 mm, ten cells to a 15.8 mm macro-period. Table I's Ltop, Wmid
and Lbot for each of the ten cells. Design: normal incidence refracted to
+71.8° at 20 GHz.

**A stated assumption, not a fact.** *The paper never states RT/duroid 6010's
permittivity or loss tangent anywhere.* This case supplies εᵣ = 10.2 and
tan δ = 0.0023 — the Rogers datasheet figures, **characterised at 10 GHz,
applied unchanged at this case's 20 GHz**.

- *What it costs if wrong*: every electrical length in the stack scales as the
  square root of the permittivity, so a few percent of error moves the resonance
  by a few hundred megahertz — the same size as the 0.8 GHz shift this case is
  scoring. A wrong permittivity could account for the entire quantity being
  measured, and a pass would then mean nothing.
- *Cheapest way to find out*: measure a bare 0.635 mm 6010 coupon in a resonant
  cavity or stripline resonator near 20 GHz, or ask Rogers for the 20 GHz
  characterisation. Either settles it without solving anything.

**Why it is unresolved.** Table I fixes only Ltop, Wmid and Lbot per cell. Every
other dimension of the two dogbones and the loaded dipole — including the trace
widths that set how sharply each element resonates — appears only as labelled
leader lines on Fig. 10. Ten cells' worth of guessed elements is not a
reconstruction. The permittivity gap above compounds it.

**Accuracy bars, from the authors.**

- Reflection: Fig. 18 annotates the simulated null at 19.8 GHz and the measured
  null at 20.6 GHz — a published gap of **0.8 GHz**, against a 0.1 GHz cost of
  reading that figure (17.5–22.5 GHz axis, 0.5 GHz divisions, broad null).
- Transmission: section IV-B, *"the scattered refraction efficiency at 20.6 GHz
  is calculated to be approximately 80%. While it is lower than the simulated
  result of 93%…"* — a published gap of **0.13**, against 0.04 for reading
  Fig. 15's 0-to-1 axis.

**A correction to the ticket that commissioned this.** Issue #386 describes this
case as "−27 dB measured against −26 dB simulated, plotted on the same axes".
What the paper actually says is *"the measured G11 at the resonant frequency
indicates that less than 0.2% of the incident power is back-reflected, which is
in agreement with simulations"* — 0.2% is about −27 dB, and it is a **bound**.
The paper never prints a numeric simulated trough depth. So the null's depth is
**not** used as an expected value here: there is no published depth gap to build
a band from, and inventing one is precisely what these bands exist to prevent.
The resonance **frequency**, which the paper does publish for both, is scored
instead.

**Pinned at**: `simulation/palace.py` @ `0f6db66`, Palace commit 43a5483
(schema 1-6-0) — the Floquet-port path the case is written against. Not yet run;
no `palace` binary was on `PATH` in the session that wrote it, and the
reconstruction is incomplete regardless.

---

## Case 3 — band-pass FSS, silver paste dispensed on 3D-printed ABS

**arXiv:2511.16777v1** — Tehranian, Budhu, Perkowski, Sookdeo, Church, Harris
and Pfeiffer, *Design, Fabrication, and Measurement of a Hemispherical
Multi-Layer Band-Pass Frequency Selective Surface.*

*A frequency selective surface is a patterned sheet that lets some frequencies
through and blocks others — a filter made of geometry rather than of components.*

**This is the case closest to this programme's own manufacturing route**:
conductive paste dispensed through a nozzle, not copper etched off a laminate.
If any of the four was going to expose a discrepancy specific to printed
conductors, it was this one. It did.

**Scored against Fig. 17's PLANAR curve — the flat sample.**

**Deliberately excluded: Fig. 17's hemispherical curve, and Fig. 16 entirely.**
The paper's headline result is the same unit cell wrapped onto a 150 mm dome.
The model here is a flat, infinitely repeating cell. Scoring one against the
other would compare two different physical problems and could return either a
false pass or a false fail — which is the single mistake most likely to be made
on this case. Fig. 16 is the same measurement *before* the Gaussian-beam
post-processing, and its ripple is diffraction off the sample edges rather than
anything the surface does.

**Reconstruction — and why a circuit model is legitimate here.** The paper does
not merely leave a circuit model implicit: it *designs* the surface with one,
publishes the two element values the geometry was sized to realise
(**C = 78 fF** per capacitive layer, **L = 1.66 nH** for the inductive layer
between them), and prints its own circuit model against its own full-wave
result in Fig. 3. The wheel-spoke pattern that realises those values appears
only in Fig. 2(c) and is not reconstructible from the text — but it does not
need to be, because the quantity it was drawn to produce *is* published.

The stack, in the order the wave meets it (ABCD matrices do not commute, so the
order is the part):

| Layer | Value |
|---|---|
| ABS encapsulation | 1.00 mm, εᵣ = 2.4, tan δ = 0.006 |
| Capacitive FSS layer | shunt 78 fF (lossless — see below) |
| ABS spacer | 1.25 mm |
| Inductive FSS layer | shunt 1.66 nH (lossless) |
| ABS spacer | 1.25 mm |
| Capacitive FSS layer | shunt 78 fF (lossless) |
| ABS encapsulation | 1.00 mm |
| **Total** | **4.50 mm** — the paper's own figure |

**The result — executed.**

| Quantity | Reconstruction | Paper | Band | Outcome |
|---|---|---|---|---|
| Transmission at 10 GHz | **−0.393 dB** | −1.7 dB | ±1.0 dB (published gap) | **FAIL by 1.31 dB** |
| Transmission at 20 GHz | **−15.692 dB** | ≤ −15 dB | 0.5 dB (digitization) | PASS |
| −1 dB passband (reported, not scored) | 6.42–12.81 GHz | "7–13 GHz" | — | — |

**The failure is the finding.** The paper states its silver paste's conductivity
— 10⁶ S/m, roughly sixty times worse a conductor than copper — but never how
thick the dispensed traces are. Without a thickness there is no sheet resistance
to put in, so the shunt elements above are **lossless**. *In plain terms: our
model gave the surface free wiring, and the real one was made of something
closer to pencil lead.* The stop-band, set by the reactances rather than the
losses, lands where the paper says it does. The passband, where the loss shows
up, is about 1.3 dB too shallow.

**The band was not widened to make it pass.** What this buys the programme: a
lossless circuit model of a paste-printed surface will flatter its passband, and
this is the first measurement here of by how much. Cheapest way to close it:
section a single dispensed trace and measure it, or ask the authors for the
deposited thickness. A sheet resistance follows directly and the model re-runs
in under a second.

**A limit on the stop-band pass.** `−15 dB` is scored as a **floor**
(`AT_MOST`), because the paper gives 15–20 dB as a band-wide spread rather than
a value at 20 GHz. A reconstruction rejecting 30 dB would also pass this check
and should **not** be read as agreeing with the measurement.

**Pinned at**: `rf_tools/transmissive_absorber.py` @ `2823a9c`. There is no
external binary to name — the adapter commit *is* the version.

**Re-run it**: `uv run python -m verification.fss_bandpass_circuit_check`

---

## Case 4 — varactor-tuned RIS unit cell, WR-28 waveguide simulator

**arXiv:2608.06541v1** — Manna, Reher, El Isa, Al-Bassam and Heberling, *A
28-GHz Varactor-Based RIS With Continuous Phase Control: From Unit-Cell
Modeling to Programmable Wavefront Control and Synthesis.*

*A varactor is a diode whose capacitance changes with the voltage across it —
the mechanism that makes a surface electronically steerable instead of fixed.*

**Scored against** Fig. 5, the measured reflection magnitude and phase of the
four fabricated unit cells (UC1–UC4) in the modified WR-28 waveguide fixture,
read at 28 GHz.

**Deliberately excluded**: everything from section III onward — the 96-element
array, the beam-steering and wireless-link measurements. Those depend on the
horn illumination and the bias calibration at least as much as on the unit cell,
and every periodic model here is one cell.

**Reconstruction.** Unit cell 5.36 mm square (half a wavelength at 28 GHz); two
rectangular patches 1.90 × 2.19 mm separated by a 0.22 mm gap and bridged by the
varactor; 0.305 mm RO4003C (εᵣ = 3.55, tan δ = 0.0027, quoted by the paper
itself as 10 GHz figures) over ~0.1 mm TU-768P 1080 prepreg over 1 mm FR4;
bias vias 0.3 mm drill, 0.7 mm clearance. The MACOM MAVR-011020-1411 modelled as
Lser = 88.5 pH, Cpar = 9 fF, Rser = 5.5 Ω.

**Why it cannot be posed here.** It needs a discrete series R–L–C element
bridging a gap **inside** a Bloch-periodic unit cell, and those two capabilities
live in different adapters:

- `simulation/openems.py` emits openEMS `LumpedElement` properties — but exposes
  no periodic boundaries.
- `simulation/meep.py` (Bloch-periodic) and `simulation/palace.py` (Floquet
  ports) have the boundaries and no discrete lumped element. Palace's
  `LumpedPort` is a port *boundary condition*, not a component bridging a gap in
  a pattern.

**A second, independent blocker.** The paper's measured axis is **reverse-bias
voltage** (Fig. 5, 0–20 V); its simulated axis is **capacitance** (Fig. 3,
0.025–0.225 pF); and it publishes no C(V) curve for the diode. So even with a
solver, the two axes could not be laid over one another point by point. The
expected values here are consequently written as range-level and design-point
quantities, not per-capacitance ones.

**Accuracy bars.**

- Reflection magnitude at 28 GHz: value −4.6 dB, band **0.7 dB** — section II-C,
  *"the measured reflection magnitude closely follows the simulated
  waveguide-embedded response of −4.6 dB with a maximum deviation of less than
  0.7 dB."* Against 0.6 dB for reading Fig. 5 (−18…0 dB axis, 3 dB divisions).
  A genuinely tight bar, about a seventh of the value — which is why this case
  would have been worth running.
- Reflection phase coverage at 28 GHz: value 300°, band **24°**. The paper
  publishes no numeric simulated-versus-measured phase gap at 28 GHz (only that
  all four cells reach "phase coverage approaching 300°"), so the digitization
  error alone sets it: Fig. 5's 0–360° axis in 60° divisions, read at both ends
  of a span.

**Pinned at**: `simulation/openems.py` @ `a0939ba` — the only adapter here that
emits a discrete lumped R/C/L element, recorded so a later reader can check
whether the capability gap has since closed rather than re-deriving it.

---

## What this does not move

- **The provenance ceiling.** Every result here is `SIMULATED`, and
  `score_reference_case` refuses outright to score a result labelled `MEASURED`.
  Nothing in this document is a measurement of our own hardware. Two methods
  agreeing is still not a measurement.
- **Anything off normal incidence.** Case 1's paper has the only measured
  oblique data of the four and case 1 is unresolved.
- **Anything curved.** Case 3's hemispherical result is excluded on purpose.
- **Any other adapter.** `verification/README.md` enumerates the adapters with
  no reference case at all; this ticket does not shorten that list.
- **The magnetic mirror.** Zero coverage, as above. It remains the physics this
  program opens on and the physics nothing here has checked.
