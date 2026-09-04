# What Unknowns Does Each of US12089385B2's Seven Examples Require?

**Research date:** 2026-09-03
**Ticket:** [#107](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/107), child of the wayfinder map [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104)
**Question:** for each of the seven examples in US12089385B2, enumerate the quantities a
design loop would have to know — design variables, material properties (and the
provenance rung each realistically arrives at), success criterion, implied simulation
setup, and any quantity that is inherently a human input. The deliverable is a table,
not a recommendation. The point is to find the boundary between what is common to all
seven and what is per-family, because **that boundary is the registry seam**.

Provenance tags throughout are `CONTEXT.md`'s ladder — `MEASURED` → `SIMULATED` →
`CALCULATED` → `MANUFACTURER-SPECIFIED` → `LITERATURE-SUPPORTED` → `INFERRED` →
`ASSUMED` → `UNKNOWN`. No parallel scale is introduced.

---

## Bottom line up front

1. **The seven examples' full numeric geometries were recovered.** The ticket, and
   `docs/HANDOFF-metamaterial-printing-grill.md` before it, assumed the dimensions were
   unreachable because the patent's description text says only "specific dimensions …
   are included in the table of FIG. 5C / 6C / 7F / 8D / 9C / 10C / 11C" and there are
   **zero `<table>` elements in the Google Patents description**. Those tables are in
   the *drawings*. Google Patents publishes the drawing sheets, and they are legible.
   Every design variable, period, and material constant for all seven is in §2 below.
   Nothing in this document depends on the un-OCR'd repo scan.

2. **The `εr = 310` figure in the ticket's summary table is not the number Example 1
   was simulated with.** εr = 310 appears in the *prose* as an illustrative property of
   strontium titanate. FIG. 5C — the table for the embodiment actually simulated and
   measured — gives **ε₁ = 250 − 1.25j**. Example 2's is **294 − 0.5j**. Neither is 310,
   and both carry a loss term the prose omits entirely.

3. **The seam is the simulation setup, and it splits 4 / 3.** Examples 1, 2, 3 and 6 are
   *uniform* surfaces: one Floquet unit-cell solve is the whole analysis, and the success
   criterion is read straight off it. Examples 4, 5 and 7 are *aperture* surfaces: the
   unit-cell solve produces only a **phase-vs-parameter lookup table**, and the function
   being designed for (a steered beam, a suppressed backscatter lobe) does not exist at
   the unit-cell level at all. For Example 7 this is not a refinement — a primary source
   shows the 10 dB RCS-reduction bandwidth *changes with array size* (§5).

4. **Corrected 2026-09-04 (#108).** This item previously said "two of the seven are not
   buildable on the stated process," blaming Example 5 on "the NOVA's 40 °C ceiling."
   That conflated the printer's own ink-viscosity warmer with the real cure step — an
   *external* oven, already used at 120–135 °C for this programme's other inks (#105).
   Re-derived per example: **Examples 1 and 2 are the only ones genuinely unbuildable on
   this process** — they need a solid 3D ceramic piece (Mie-resonance cubes), and no
   printing or lamination route produces a solid 3D block, in any material. **Example 4**
   needs a host of **εr = 100**; researched directly (`docs/flexible-high-permittivity-
   composites.md`) — no published material combines that permittivity with real
   flexibility at microwave frequency, a materials-physics conflict with the pliable-skin
   premise, likely permanent rather than a sourcing gap. **Example 5** needs a BST film;
   a pre-crystallised BST particulate ink cured externally at ~150 °C is a real, published,
   oven-compatible route (15% tunability measured at 10 GHz) — excluded only because it
   hasn't been sourced yet, not because the process can't reach it. **Example 6**'s
   εr = 10.4 substrate looked like the same problem but isn't: permittivity is a free,
   rescalable design parameter for its polarization-conversion function, confirmed against
   published, measured low-εr converters (`docs/example6-polarization-converter-
   permittivity.md`) — it redesigns cleanly onto this programme's flexible substrate
   shortlist. Net: **2 hard-excluded (process, 1/2), 1 excluded likely-permanently
   (materials-physics, 4), 1 excluded-for-now (materials-sourcing, revisable, 5), 3
   buildable today (3, 6, 7).**

5. **Minimum feature sizes are more comfortable than the handoff feared.** The tightest
   printed feature across all seven is **w = 0.2 mm** (Example 6's meander line); Example
   3's tightest is **0.6 mm**. The handoff's worry that cells land "right at the machine's
   floor" does not hold for these specific geometries — they sit 2–6× above the NOVA's
   100 µm floor and above MXene's best-demonstrated 120 µm line.

---

## 1. Sources and method

| Source | What was taken from it | Provenance of its numbers |
|---|---|---|
| **US12089385B2** description text, via [Google Patents](https://patents.google.com/patent/US12089385B2/en) | Function statements, film thicknesses, bands, material names, ground-plane discussion, bend radius, conformity | `LITERATURE-SUPPORTED` (`CONTEXT.md` maps source type `patent` → `LITERATURE-SUPPORTED`, ranked below a peer-reviewed paper) |
| **US12089385B2 drawing sheets**, rendered from the [Google Patents PDF](https://patentimages.storage.googleapis.com/f5/d9/73/7d2e4472adfcb1/US12089385.pdf) at 170–600 dpi and read visually | All seven dimension tables (FIG. 5C, 6C, 7F, 8D, 9C, 10C, 11C) and all seven performance plots | `LITERATURE-SUPPORTED`, with a transcription caveat — see §7 |
| Liu, Wang, Wang, Zhao, Jin, Li, Wen & Zhou, "Electrically tunable transmissive dielectric metamaterial based on SrTiO₃ Mie resonators," *Microstructures* **6** (2026), [DOI 10.20517/microstructures.2025.37](https://doi.org/10.20517/microstructures.2025.37) | SrTiO₃ ceramic εr = 325 measured at room temperature, falling to 234 at 200 °C; simulation used εr = 280, tanδ = 0.0025; Mie relation f ≈ c/(2r√ε) | `LITERATURE-SUPPORTED` |
| Paquay, Iriarte, Ederra, Gonzalo & de Maagt, "Thin AMC Structure for Radar Cross-Section Reduction," *IEEE Trans. Antennas Propag.* **55**(12), 3630–3638 (2007), [DOI 10.1109/TAP.2007.910306](https://doi.org/10.1109/TAP.2007.910306) | The AMC/PEC chessboard cancellation principle underlying Example 7 | `LITERATURE-SUPPORTED` (bibliographic record confirmed via the Semantic Scholar API; **abstract elided by the publisher, full text not fetched** — see §7) |
| Haji-Ahmadi, Nayyeri, Soleimani & Ramahi, "Pixelated Checkerboard Metasurface for Ultra-Wideband Radar Cross Section Reduction," *Sci. Rep.* **7**, 11437 (2017), [DOI 10.1038/s41598-017-11714-y](https://doi.org/10.1038/s41598-017-11714-y), read via [PMC5595835](https://pmc.ncbi.nlm.nih.gov/articles/PMC5595835/) | "a phase difference of 180 ± 37° between the reflections from two region provides at least 10 dB monostatic RCS reduction"; and the two-stage method — Floquet unit cell for the optimisation, then a full finite 4×4-tile solve for validation | `LITERATURE-SUPPORTED` |
| Murugesan & Selvan, "On the effect of array size on the radar cross section reduction bandwidth of checkerboard metasurfaces," *Frequenz* **77**, 273–279 (2023), [DOI 10.1515/freq-2022-0021](https://doi.org/10.1515/freq-2022-0021) | "The 8 and 10 dB RCS reduction bandwidths drop as array size increases… attributable to mutual coupling" | `LITERATURE-SUPPORTED` (abstract via the Crossref API; the publisher's HTML returned HTTP 405 to a direct fetch) |
| `docs/mxene-voltera-nova-printability.md`, `docs/HANDOFF-metamaterial-printing-grill.md` | MXene conductivity, NOVA line width/viscosity/thermal limits, skin depths | as tagged in those documents |

**Method note.** The repo's own copy of the patent is a 32-page scan with no text layer,
and poppler is unavailable — the ticket is right about that, and this document did not
use it. The Google Patents PDF is *the same scan* (also zero extractable characters,
verified). What made the drawings readable was rendering its pages to raster with
PyMuPDF and reading them visually, rather than trying to extract text. Anyone re-checking
these numbers should do the same; the Google Patents *thumbnail* PNGs are 120 px tall
and useless.

---

## 2. Design variables — what a solver actually varies

Symbols are the patent's own, from the drawing tables. "Patent's value" is the one
embodiment the inventors simulated or built; a design loop would treat these as the
*parameterisation*, not as fixed.

| # | Element | Design variables (patent symbol) | Patent's values | Period | Tightest feature |
|---|---|---|---|---|---|
| **1** | Dielectric cube, embedded | cube side `a`; lattice period `p`; film thickness | `a` = 1.65 mm; `p` = 3.3 mm; T = 1.65 mm | 3.3 mm square | 1.65 mm (cube) |
| **2** | Dual cube (two sizes), embedded | small cube `a₁`; large cube `a₂`; period `p`; film thickness | `a₁` = 1.5 mm; `a₂` = 2.0 mm; `p` = 4.2 mm; T = 2.00 mm | 4.2 mm square | 1.5 mm (cube) |
| **3** | I-shaped ERR on top, rectangular wire on bottom | cell `a₁`×`a₂`; I-bar thickness `t`; gap `G`; I width `W`; wire width `L`; wire length `H`; dielectric `h`; second layer `h₁` | `a₁` = 4.2 mm, `a₂` = 12 mm, `t` = 0.6 mm, `G` = 0.6 mm, `W` = 4 mm, `L` = 1.7 mm, `H` = 11.8 mm, `h` = 0.72 mm, `h₁` = 0.15 mm | **4.2 × 12 mm — rectangular, not square** | 0.6 mm |
| **4** | Cylindrical hole in a high-εr slab, ground-backed | **hole radius `r`** (the knob); period `s`; slab thickness `h` | `r` swept **0.2 → 1 mm**; `s` = 2.125 mm; `h` = 1 mm | 2.125 mm square | 0.2 mm (hole) |
| **5** | Square self-phased patch over a BST-loaded layer, metal-backed | patch side `l`; period `p`; layer thickness `h`; **and the bias-controlled layer permittivity ε₁** | `l` = 4 mm; `p` = 6 mm; `h` = 1 mm; ε₁ swept **3.5 → 5.0** | 6 mm square | 1 mm (patch–patch gap, = `p` − `l`) |
| **6** | Meander line at 45°, ground-backed | cell `d1`×`d2`; line width `w`; meander offset `b`; substrate `t`; **and the 45° orientation** | `d1` = 4 mm; `d2` = 6 mm; `w` = 0.2 mm; `b` = 0.7 mm; `t` = 1.6 mm | 4 × 6 mm rectangular | **0.2 mm** |
| **7** | Circular inter-digitated ring pair with meandered slot, metal-backed, **two variants in a checkerboard** | inner/outer radii `r₁`, `r₂`; substrate `h`; slot width `w`; slot length `l`; period `p`; **plus the checkerboard tile size and the aperture extent** | `r₁` = 0.8 mm; `r₂` = 1.7 mm; `h` = 1 mm; `w` = 0.3 mm; `l` = 0.4 mm; `p` = 6 mm | 6 mm square | 0.3 mm |

Two things to notice. First, **only Example 4 has a single scalar knob**; every other
example has a 4–9-dimensional geometry vector, so "cylinder diameter is the knob" is a
description of Example 4 alone and is not a template. Second, **Examples 5 and 7 have a
design variable that is not a length**: for #5 it is the substrate permittivity the bias
voltage controls, and for #7 it is *which of two element variants goes in which tile* —
a discrete, spatial assignment.

---

## 3. Material properties and the rung each realistically arrives at

| # | Property the model needs | Patent's value | Rung as the patent gives it | Rung a real loop would get, and why |
|---|---|---|---|---|
| **1** | Insert complex permittivity ε₁ | **250 − 1.25j** (FIG. 5C); prose separately cites SrTiO₃ "εr = 310" | `LITERATURE-SUPPORTED` | `LITERATURE-SUPPORTED` at best. Independent measurement of SrTiO₃ ceramic gives **325 at room temperature falling to 234 at 200 °C** (*Microstructures* 2026) — a ~28 % swing over a plausible skin operating range. Without a temperature spec this is `ASSUMED`. |
| | Insert µ₁ | 1 | `LITERATURE-SUPPORTED` | Same; safe. |
| | Host film εr, tanδ | **not given for this example** | `UNKNOWN` | The prose's "εr 2–5, tanδ < 0.2" is far too loose to design a resonance with → `ASSUMED` until a specific film is chosen (`MANUFACTURER-SPECIFIED` from a datasheet) or characterised (`MEASURED`). |
| **2** | Insert complex permittivity ε₁ | **294 − 0.5j** (FIG. 6C) | `LITERATURE-SUPPORTED` | As #1. Note ε and µ resonances must *coincide*, so this example is far more sensitive to an ε₁ error than #1 is. |
| | Host film εr, tanδ | not given | `UNKNOWN` | As #1. |
| **3** | Substrate εr, tanδ | **FR4, εr = 4.8, tanδ = 0.017** (prose) | `LITERATURE-SUPPORTED` | A named laminate's datasheet → `MANUFACTURER-SPECIFIED`. But FR4 is a weave-dependent composite rarely specified at 10 GHz, so an X-band value is realistically `ASSUMED` until `MEASURED`. **This is the anchor example's dominant loss mechanism** (per the handoff's Correction 1), so its rung caps the whole reproduction's trustworthiness. |
| | Conductor σ (or Rs) | "copper or gold" — **no σ, no thickness** | `UNKNOWN` | MXene: `LITERATURE-SUPPORTED` at 6.26–6.9×10⁵ S/m until the coupon run, then `MEASURED`. Rs = 1/(σt) is then `CALCULATED`. |
| | Conductor thickness | `h₁` = 0.15 mm, **if** `h₁` is the metal (ambiguous, §7) | `UNKNOWN` | `MEASURED` post-coupon. 0.15 mm is ~6× a normal 1 oz etched copper foil, so this reading is suspect. |
| **4** | Host slab εr, µr | **εr = 100, µr = 1** (FIG. 8D), **material unnamed, no loss term** | `LITERATURE-SUPPORTED` for the value, `UNKNOWN` for the material | A lossless εr = 100 host is a *simulation idealisation*. Any real εr ≈ 100 ceramic-loaded composite has tanδ ≫ 0 and is neither pliable nor printable → `ASSUMED`, and flagged as a hard manufacturability conflict. |
| | Ground plane σ | "ground plane 853", material unstated | `UNKNOWN` | PEC is the usual `ASSUMED` stand-in; matters little at 10 GHz. |
| **5** | Tunable layer ε₁ vs bias | **ε₁ = 3.5 – 5.0** (FIG. 9C/9D); BST film "~20 µm", bias "< 40 V" | `LITERATURE-SUPPORTED` | The **ε₁(V) mapping is nowhere in the patent** — only the endpoints of a permittivity sweep. Deriving the bias needed for a given phase requires BST film data that is deposition-process-specific → `UNKNOWN` here, `LITERATURE-SUPPORTED` at best from elsewhere, and `MEASURED` only per-process. |
| | BST loss tangent | not given | `UNKNOWN` | Ferroelectric loss at X-band is the usual reason tunable reflectarrays underperform; its absence is a real gap. |
| | Metal backing | "copper or gold" | `UNKNOWN` (no σ) | As #3. |
| **6** | Substrate εr, tanδ | **εr = 10.4, tanδ = 0.0028** (FIG. 10C) | `LITERATURE-SUPPORTED` | This is a ceramic-filled laminate signature, not a pliable polymer. A named product → `MANUFACTURER-SPECIFIED`. **It contradicts the patent's own "host polymer εr 2–5" statement.** |
| | Meander conductor σ | not given | `UNKNOWN` | As #3; at `w` = 0.2 mm, conductor loss matters more here than in the wider-trace examples. |
| **7** | Two tile permittivities | **εr = 3.5 and 4.5** (prose); FIG. 11C reads "3.5, 4.4" | `LITERATURE-SUPPORTED`, with an internal inconsistency | The whole function is a *phase difference* between two tiles, so the **difference** 4.5 − 3.5 = 1.0 is the load-bearing quantity, not either value. A 4.4-vs-4.5 discrepancy is a 10 % error in the design driver. `ASSUMED` until resolved. |
| | µr | 1 | `LITERATURE-SUPPORTED` | Safe. |
| | Ring conductor σ | not given | `UNKNOWN` | As #3. |

**Common to all seven, and absent from all seven:** every example needs a **conductor
model** (σ or surface impedance) or a **loss term for the dielectric**, and the patent
supplies neither consistently. Examples 1, 2 and 6 give a loss term (`−1.25j`, `−0.5j`,
`tanδ = 0.0028`); Examples 4, 5 and 7 give none at all; Example 3 gives the substrate's
loss but never the conductor's. So **conductor loss enters the loop as `UNKNOWN` for all
seven** — which is exactly the gap the handoff already flagged ("no model of conductor
loss anywhere").

---

## 4. Success criterion — what "working" means, per example

| # | Function | Quantity scored | Passing condition | Where the patent shows it | Reported as |
|---|---|---|---|---|---|
| **1** | Magnetic mirror / high-impedance surface | **reflection phase ∠S₁₁** — and, separately, retrieved **µ_eff** | ∠Γ ≈ 0° over the band. The conventional AMC bandwidth is the span where ∠Γ lies within ±90° of 0°. Patent's own claim: µ_eff ≈ 5 rising to ≈ 20 at resonance | FIG. 5D (|S|), 5E (∠S), 5F (µ_eff) | **SIMULATED *and* MEASURED** (both curve sets are labelled) |
| **2** | Impedance match to free space | **ε_eff and µ_eff coincidence** → η = √(µ/ε) ≈ η₀ | ε_eff ≈ µ_eff at the same frequency, with resonances overlapping; no refraction | FIG. 6D (simulated), 6E (measured) | **SIMULATED *and* MEASURED** |
| **3** | Absorber | **absorptivity A = 1 − \|S₁₁\|² − \|S₂₁\|²** | A → 1 at the design frequency. Peak at ≈ 9.2 GHz; the patent's own words are "complete absorption, along with no reflection and no transmission" | FIG. 7G, three traces: Reflectance, Transmission, Absorbance, 8.5–10.5 GHz | **SIMULATED only** |
| **4** | Steered reflection | **∠Γ as a function of `r`** — i.e. a *phase-coverage curve*, not a single number | The curve must span enough phase to synthesise the wanted aperture distribution. Patent's curve spans ≈ 0° → 305° for `r` = 0.2 → 1 mm at 10 GHz — **not a full 360°** | FIG. 8E, phase vs hole radius | **SIMULATED only** |
| **5** | Electrically tunable steering | **∠Γ tuning range at fixed frequency**, driven by ε₁(V) | Patent claims "close to π phase-tuning range" | FIG. 9D, ∠Γ vs 10–20 GHz for ε₁ = 3.5 … 5.0 | **SIMULATED only** |
| **6** | Polarisation converter, LP ↔ CP | **axial ratio (dB)**, versus frequency *and* incidence angle θ | AR ≤ 3 dB is the standard CP criterion. Patent's curves dip below ≈ 0.5 dB near 13.85 and 16.6 GHz at θ = 0°, and stay under ≈ 4.2 dB out to θ = 40° | FIG. 10D, AR vs 13–17 GHz for θ = 0/10/20/30/40° | **SIMULATED only** |
| **7** | Backscatter reduction | **scattered power relative to a metal reference**, in dB | Reduction vs a same-size copper plate. Patent's measurement shows ≈ 8 dB at ≈ 14.3 GHz. The design-time proxy from the literature is the **180 ± 37° reflection-phase difference between the two tiles**, which guarantees ≥ 10 dB monostatic RCS reduction | FIG. 11D, two traces vs 13–15 GHz | **MEASURED only** |

**Four different criterion *shapes*, not seven.** They are: (a) a retrieved
effective-medium parameter (#1, #2); (b) a scalar power fraction at a frequency (#3);
(c) a phase *curve* over a swept parameter (#4, #5); (d) a ratio against a reference
structure (#7). Example 6's axial ratio is a fifth shape — a polarisation-ellipse
figure of merit derived from co- and cross-polarised reflection coefficients — but it
behaves like (b), a scalar to be minimised over a band.

Note the asymmetry that matters most for [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104):
**Example 3, the chosen anchor, is the one with a fully specified substrate but only a
SIMULATED result.** Examples 1, 2 and 7 have measured data; Example 3 does not. The
"blind fixed test goal" is therefore a target curve produced by someone else's simulator,
with an unstated mesh, unstated conductor model, and — per §7 — an ambiguous y-axis.

---

## 5. Implied simulation setup — where the seam actually falls

| # | Ports / boundaries | Does a periodic Floquet unit-cell solve suffice? | What else is required |
|---|---|---|---|
| **1** | **Two-port**, Floquet on both faces (transmission exists — FIG. 5D plots S₂₁), no ground plane | **Yes, and it is the whole analysis** | An S-parameter → µ_eff/ε_eff **retrieval** post-process (NRW-class). The retrieval, not the solve, is where this example's difficulty lives. |
| **2** | **Two-port**, Floquet both faces, no ground plane | **Yes** | Same retrieval, but of *both* ε_eff and µ_eff, and the criterion is their coincidence — so retrieval error enters twice. |
| **3** | **Two-port**, Floquet both faces, no ground plane (FIG. 7G plots a non-zero Transmission trace, so the structure is not metal-backed) | **Yes** | Nothing beyond A = 1 − \|S₁₁\|² − \|S₂₁\|². Rectangular 4.2 × 12 mm cell means the two lattice periods are independent variables. |
| **4** | **One-port**, Floquet on the illuminated face, PEC backing | **No — it produces a lookup table only** | The unit cell yields ∠Γ(`r`) under *local periodicity*: each cell is solved as if infinitely repeated with its own `r`. The steered beam then requires assigning `r` per cell across a **finite aperture** and computing the pattern (array-factor / aperture-integration, then optionally a full-wave check). The function does not exist in the unit cell. |
| **5** | **One-port**, Floquet + PEC backing, **plus a bias-state parameter** | **No — lookup table only**, and now two-dimensional | ∠Γ(ε₁, f) across the tunable range, then the same finite-aperture stage as #4, and additionally a *control* layer: what bias each cell gets. |
| **6** | **One-port**, Floquet + PEC backing, swept over **oblique incidence angles and both polarisations** | **Yes — but only with an oblique-incidence-capable Floquet setup** | Co- and cross-polarised reflection coefficients under 45° element rotation; AR derived from their magnitude ratio and phase difference. The patent sweeps θ to 40°, so a normal-incidence-only solver cannot reproduce FIG. 10D. |
| **7** | **One-port Floquet per tile type** for design; **finite full-wave** for the answer | **No — and here the shortfall is quantified** | Two Floquet solves give the two tiles' ∠Γ, checked against the 180 ± 37° criterion. Then a finite checkerboard must be solved: the Haji-Ahmadi *et al.* (2017) pixelated-checkerboard work runs "periodic boundary conditions with Floquet port excitation … during the optimization routine" and then "the complete finite metasurface (4×4 alternating tiles, 224×224 mm) … using CST's time-domain solver, which accounts for edge effects and finite-size interactions absent in periodic assumptions." Murugesan & Selvan (*Frequenz* 2023) then show the reduction bandwidth is **not scale-invariant**: "The 8 and 10 dB RCS reduction bandwidths drop as array size increases… attributable to mutual coupling." So **aperture size is a design variable for #7 in a way it is not for #1–#3 and #6.** |

**This is the seam.** The registry does not need seven simulation back-ends. It needs
**two tiers plus three axes**:

- **Tier A — uniform surface.** One periodic solve *is* the evaluation. Examples 1, 2, 3, 6.
- **Tier B — aperture surface.** A periodic solve is a *characterisation* step that
  populates a phase-vs-parameter table; a second, aperture-level stage computes the
  scored quantity. Examples 4, 5, 7.

The three axes that vary *within* both tiers:

1. **Port count** — two-port/transmissive (1, 2, 3) vs one-port/ground-backed (4, 5, 6, 7).
   This is not the same split as the tier split, which is why it has to be its own field.
2. **Post-processing** — none (4, 5, 7 read phase directly), power arithmetic (3),
   effective-medium retrieval (1, 2), or polarisation-ellipse arithmetic (6).
3. **Excitation sweep** — frequency only (1, 2, 3), frequency × geometry (4),
   frequency × material state (5), frequency × incidence angle (6), frequency ×
   tile-assignment × aperture size (7).

Concretely, a registry entry needs at minimum: `tier`, `port_count`,
`backing` (`pec` | `none`), `sweep_axes`, `postprocess`, `objective`, `objective_sense`.
Example 3 alone would only ever have exercised `tier: A`, `port_count: 2`,
`backing: none`, `sweep_axes: [frequency]`, `postprocess: absorptivity` — every one of
those fields would have looked like a constant.

---

## 6. What is common to all seven, and what is per-family

### 6.1 Common to all seven — the fixed spine

| Quantity | Why it is common | Typical rung |
|---|---|---|
| Operating band / centre frequency | All seven are band-specific; nothing in the patent is broadband | human input (see §6.3) |
| Host film thickness `T` | Every example states it (0.87 / 1.0 / 1.0 / 1.0 / 1.6 / 1.65 / 2.0 mm) and it sets the electrical thickness | `LITERATURE-SUPPORTED` from patent; a design variable in a loop |
| Unit-cell period(s) — **two of them, not one** | Every example is "arranged in a regular repeating pattern"; #3 and #6 have rectangular cells, so px ≠ py must be representable | design variable |
| Lattice type | Square in 1, 2, 4, 5, 7; rectangular in 3, 6; patent also contemplates hexagonal/circular/elliptical | discrete human or search choice |
| Host / substrate εr and tanδ | Needed by every solve, whatever the element is | `MANUFACTURER-SPECIFIED` at best, `ASSUMED` in practice |
| Conductor σ or surface impedance | Needed by 3, 5, 6, 7 directly, and by the ground plane in 4 and 5 | `LITERATURE-SUPPORTED` → `MEASURED` (MXene coupon) |
| Incident polarisation + incidence-angle set | Every reflection/absorption criterion is polarisation- and angle-dependent | human input |
| Ground-plane presence | The patent makes it explicitly conditional on the host platform: "if we know that the platform is a ground plane, there would be no need to repeat it"; claim 11 covers a skin *without* one | human input about the platform |
| Minimum bend radius `R = 3T` and conformity `< 10–20 µm` | Claims 20 and 21; applies to the skin regardless of function | `CALCULATED` from a human-supplied worst-case radius |
| Thickness ceiling `T ≤ 2 mm` | Claim 7 | hard constraint |
| Fabrication constraints — min line width, min gap, thickness/pass, cure ceiling | Not in the patent; imposed by the NOVA and the ink | `MANUFACTURER-SPECIFIED` (NOVA) + `LITERATURE-SUPPORTED` (MXene) → `MEASURED` |

### 6.2 Per-family — what the registry must vary

| Axis | Values observed across the seven |
|---|---|
| **Element parameterisation** | cube side (1); two cube sides (2); 7-dimension printed bilayer (3); hole radius (4); patch side (5); meander width + offset (6); two ring radii + slot (7) |
| **Element constitutive class** | bulk high-εr dielectric insert (1, 2); *absence* of material — a hole in a high-εr host (4); printed conductor pattern (3, 5, 6, 7); ferroelectric tunable layer (5) |
| **Number of patterned layers, and registration between them** | one (1, 2, 4, 6, 7); **two, front-to-back registered** (3 — "the columns … on the front and back surfaces correspond to each other"); one plus a continuous backing (5, 7) |
| **Whether an external control variable exists** | bias voltage, in #5 only |
| **Whether a spatial gradient / assignment across the aperture is a design variable** | yes for 4, 5, 7; no for 1, 2, 3, 6 |
| **Objective shape** | µ_eff (1); ε_eff ≈ µ_eff (2); absorptivity (3); ∠Γ coverage curve (4, 5); axial ratio (6); dB reduction vs a reference (7) |
| **Simulation tier** | A: 1, 2, 3, 6 — B: 4, 5, 7 |
| **Temperature sensitivity of a design-critical property** | acute for 1, 2 (SrTiO₃ εr falls 325 → 234 from RT to 200 °C) and 5 (ferroelectric BST); second-order for 3, 4, 6, 7 |
| **Manufacturability on the stated process** | printable today: 3, 6, 7 (min features 0.2–0.6 mm; 6's high-εr substrate is not load-bearing, redesigns onto this programme's flexible shortlist — #108); excluded, process, no route in any material: 1, 2 (need bulk ceramic pick-and-place); excluded, materials-physics, likely permanent: 4 (needs an unnamed εr = 100 host — no flexible material at that permittivity exists in the microwave-characterised literature, #108); excluded, materials-sourcing gap, revisable: 5 (needs a pre-crystallised BST particulate ink, not yet sourced — the earlier "NOVA's 40 °C ceiling" reasoning was wrong, #108) |

### 6.3 Inherently human inputs — not derivable by any loop

**Common to all seven:**

- **Operating band and centre frequency.** A customer requirement, full stop.
- **Incidence-angle and polarisation envelope.** Nothing in the physics selects it.
- **Whether the host platform is a ground plane.** The patent states this is a property of
  the vehicle, not of the skin.
- **Worst-case bend radius of the target surface.** Feeds `R = 3T` and prunes substrates.
  This is the handoff's open **Q20**, and it is a human input for every one of the seven.
- **Coverage area / aperture extent** — and for #7 it is also a *design variable* (§5).
- **Which of two conflicting objectives wins** — depth vs bandwidth for #3 (the handoff's
  **Q17**), phase range vs loss for #4/#5, AR minimum vs angular coverage for #6.
- **Whether the MXene premise is a constraint or a candidate** (#104's own open question).

**Per-family human inputs:**

| # | Additional human input |
|---|---|
| 1 | The antenna the mirror exists to support — its footprint and standoff decide how much bandwidth is enough |
| 2 | (none beyond the common set — this is the most self-contained of the seven) |
| 3 | Peak-depth vs bandwidth preference; substrate choice, since tanδ *is* the mechanism |
| 4 | **The wanted steering angle**, or equivalently the target aperture phase distribution |
| 5 | Wanted steering angle *plus* the available bias supply and per-cell control wiring budget |
| 6 | **The sense of circular polarisation** (RHCP vs LHCP) — determined by which way the meander is rotated, and not derivable from an axial-ratio objective, which is sense-blind |
| 7 | The **reference surface** that "reduction" is measured against, and the observation geometry (monostatic vs bistatic, and which bistatic angles count as acceptable places to send the energy) |

Item #7's last entry deserves emphasis. A checkerboard does not absorb; it *redirects*.
"Backscatter reduction" is only a success if the redirected lobes land somewhere the
customer does not care about. **No solver can know that.** It is the clearest example in
the set of a criterion that cannot be closed without a human, and it is per-family — no
other example has it.

---

## 7. What could not be verified

1. **Whether `h₁` = 0.15 mm in Example 3 is the conductor thickness or a second dielectric
   layer.** `h` = 0.72 mm + `h₁` = 0.15 mm = 0.87 mm, exactly the stated total, which
   argues for a second layer. But FIG. 7D marks `h` across the slab and `h₁` as a small
   edge dimension, which argues for metallisation. 0.15 mm of copper is ~6× a 1 oz foil,
   so the metal reading is physically odd. **Unresolved, and it matters** — it is the
   difference between a 0.72 mm and a 0.87 mm dielectric in the anchor reproduction.
2. **Example 7's second tile permittivity: 4.5 or 4.4?** The description says "3.5 and
   4.5"; FIG. 11C reads "3.5, 4.4" to my eye at 600 dpi, but the halftone makes the final
   digit genuinely ambiguous. Since the design driver is the *difference*, this is a 10 %
   uncertainty on the load-bearing quantity.
3. **FIG. 7G's y-axis convention.** The three traces (Reflectance, Transmission,
   Absorbance) share one axis running 0–1. If R and T are plotted as field magnitudes
   \|S₁₁\|, \|S₂₁\| then A = 1 − \|S₁₁\|² − \|S₂₁\|² ≈ 0.98 at the peak, consistent with
   the plotted Absorbance and with the prose. If they are powers, the arithmetic does not
   close. The physically coherent reading is field magnitudes, but **the patent never says
   so**, and #104's blind reproduction will be scored against this curve.
4. **Example 5's "close to π phase-tuning range" claim.** Reading FIG. 9D, the eight ε₁
   curves span roughly 300° *across the 10–20 GHz sweep*, but at any fixed frequency the
   spread between ε₁ = 3.5 and ε₁ = 5.0 looks closer to 30–50°. If that reading is right,
   the tuning range claimed is the frequency-swept range, not the bias-tunable range at a
   fixed operating frequency — which is the number a steering design actually needs. I am
   reading a scanned plot, so I flag this as an **apparent tension, not a finding**.
5. **The Paquay 2007 abstract and full text.** The bibliographic record was confirmed via
   the Semantic Scholar API, but the abstract is publisher-elided and IEEE Xplore was not
   fetched. The 180 ± 37° criterion in this document is therefore attributed to the
   open-access *Sci. Rep.* 2017 paper that states it verbatim, **not** to Paquay, which is
   cited only for the AMC/PEC chessboard principle.
6. **The `freq-2022-0021` full text.** The publisher returned HTTP 405 to a direct fetch;
   the quoted sentences come from the Crossref-deposited abstract, which is publisher-supplied
   and complete, but the paper's figures were not seen.
7. **MDPI-hosted sources were not consulted at all** — MDPI returns HTTP 403 to automated
   fetches from this environment (theirs, not a proxy problem, per the handoff). A large
   fraction of the metamaterial-absorber and polarisation-converter literature lives in
   *Materials*, *Micromachines* and *Applied Sciences*, so anything those would have added
   to Examples 3 and 6 is **stranded and needs a human with a browser**.
8. **No independent replication of any of the seven** was searched for. This document
   characterises the patent's own claims and their internal consistency; whether anyone
   outside DEVCOM has reproduced Example 3 is a separate question and is not answered here.
9. **The measurement setup behind FIG. 11D** (Example 7's only data) is not described —
   the traces are labelled "S₂₁ copper plate" and "S₁₁ BR surface", which mixes transmission
   and reflection parameters in one comparison. Whether that is a labelling slip or two
   genuinely different measurements is unknowable from the patent.
10. **No temperature, humidity or ageing spec exists anywhere in the patent.** Given the
    SrTiO₃ and BST temperature sensitivities in §3, this is a substantive omission for
    Examples 1, 2 and 5, and it means those three examples' stated permittivities are
    implicitly room-temperature values that the patent never labels as such.

---

## 8. Consequences for #104 that fall out of this table

Stated as findings, not recommendations — the ticket asked for a table.

- **The registry seam is `tier` (uniform vs aperture), not `element_shape`.** Designing the
  seam around Example 3's shape parameters would have produced a registry that cannot
  express Examples 4, 5 or 7 at all, because those need a second evaluation stage that
  Example 3 has no analogue for.
- **`port_count` and `backing` cross-cut `tier`** and so cannot be folded into it. Example
  3 (Tier A) is two-port and unbacked; Example 6 (Tier A) is one-port and backed.
- **Example 3's reproduction target is now fully specified geometrically** — the nine
  dimensions in §2 plus FR4 εr = 4.8 / tanδ = 0.017 — subject only to the `h₁` ambiguity
  in §7. Whether a blind loop should be *given* those dimensions or asked to rediscover
  them from FIG. 7G is a design question this table does not settle, but the second framing
  is now available, which it was not before.
- **Three of the seven contradict the patent's own host-material statement** (εr 2–5):
  Example 4 at εr = 100, Example 6 at εr = 10.4, and Examples 1–2 whose host is never
  specified at all. A registry that validates candidate hosts against "εr 2–5" would
  reject the patent's own examples.
- **Claim 6 and the description disagree about who εr ≥ 2.9 applies to.** Claim 6 says
  "the **pliable thin film** has a dielectric constant or relative permittivity εr of at
  least 2.9"; the description says the host polymer's εr is 2–5. The handoff records this
  as "metamaterial insert εr ≥ 2.9", which is a third reading and is not what the claim
  says. Worth correcting there.
