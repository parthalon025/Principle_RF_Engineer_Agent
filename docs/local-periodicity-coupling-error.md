# How wrong is superposition? The local-periodicity coupling error, quantified

**Research date:** 2026-09-03
**Ticket:** [#111](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/111) — fills the gap left open by [#131](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/131), serves [#130](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/130), part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104).
**Question:** If a design is evaluated by superposing elements that were each characterised alone — surrounded by infinite copies of *themselves* — how much error does that introduce once the real neighbours are *different* elements?

Every citation below is either **retrieved** (the primary source was downloaded and read in this session; quoted text and figure/table detail follow from that text) or explicitly marked **UNVERIFIED** or **STRANDED**. Nothing recalled is presented as checked.

---

## Bottom line up front

**The error bar exists, it is published, and #131 was wrong to conclude otherwise — but #131 was wrong for an understandable reason: it was chasing the wrong paper, and the paper it did read has been misquoted.** Three corrections and one answer:

1. **A quantified error bar exists, in degrees, at X-band, on a table.** Costanzo, Venneri & Di Massa (*IJAP* 2019) publish **maximum reflection-phase error against element pitch, at 10 GHz, for three element shapes** — from **12°** (best case) to **85°** (worst case), measured as the shift in an element's phase curve when two of its neighbours are swapped for the largest and smallest members of the same alphabet. This is the number #111 asked for, in the band #104 works in.
2. **The DOI in #111 was wrong, and the right paper was reachable all along.** #111 cites `10.1155/2019/9479010`. The paper that carries the number is `10.1155/2019/**4890710**` — same authors, same journal, same year, different article. It was retrieved this session (Wiley and Hindawi both 403, but a full-text mirror served it).
3. **Cole et al.'s "11% frequency error" is not the unlike-neighbour number.** #131 and #104 both record it as the cost of ignoring dissimilar neighbours. Reading the source: the 0.89 THz-versus-1.0 THz shift is caused by near-field coupling **between the three metal layers stacked inside one cell**, against a transmission-line model — an *intra-cell*, model-versus-full-wave error. Cole et al.'s statement about unlike neighbours is real, prominent, and correct, but it is **qualitative** ("some evidence that the optimal frequency is shifted"). No number attaches to it. **This correction should propagate to #104's decision log and #130's body text.**
4. **A supercell sizing rule derived from an error budget still does not exist.** #131's finding stands and is now confirmed against a wider set of sources. Every block size found in this pass was set by beam geometry, by fabrication limits, or by "we tried it and stopped when the improvement got small."

**The one-line answer for a fast superposition evaluator:** at roughly half-wavelength pitch with an ordinary variable-size-patch alphabet, expect **peak phase errors of tens of degrees — 20–45° typical, 85° worst case** — and expect the error to be **worst where the design's phase gradient is steepest**, not uniformly spread. The error grows sharply as pitch drops below λ/2 and shrinks to near-nothing if the alphabet is built so that letters differ *without* changing the gap between neighbouring elements.

---

## The numbers, on one table

Read "phase error" as: *how far off the phase is, in degrees of a full 360° cycle, when you assume an element behaves as it did in isolation.* 360° is one whole wave cycle, so 45° is an eighth of a cycle.

| Error | Conditions | What was compared to what | Source |
|---|---|---|---|
| **Max Δφ = 85°** | 10 GHz, variable-size **square patch**, pitch 0.4λ (12 mm), Diclad870 ε_r = 2.33, h = 0.762 mm | Element's phase curve with **identical** neighbours vs. with two E-plane neighbours at the alphabet's **largest and smallest** sizes | [Costanzo, Venneri & Di Massa, *IJAP* 2019, Fig. 5(c)](https://doi.org/10.1155/2019/4890710) |
| **Max Δφ = 45°** | Same, **Minkowski fractal** cell, pitch 0.4λ | Same | ibid., Fig. 6(c) |
| **Max Δφ = 20°** | Same, **modified-Minkowski cell with fixed radiating edges**, pitch 0.4λ | Same | ibid., Fig. 7(c) |
| **Max Δφ: 25° / 21° / 12°** at 0.5λ; **>45° / ≅45° / 20°** at 0.4λ; **>45° / ≅45° / 34°** at 0.3λ | 10 GHz, square / Minkowski / proposed cell | Same, tabulated against pitch | ibid., **Table 3** |
| **Phase MAE = 59.14°, amplitude MAE = 0.33** | λ = 1.55 µm, silicon nanoblocks on fused silica, 800 nm pitch (0.516λ), **randomly chosen** neighbours | Periodic-boundary prediction vs. the same element with **10 differing neighbours each side** (treated as ground truth) | [An et al., arXiv:2102.01761, §"Data collection", Fig. 2(e)](https://arxiv.org/abs/2102.01761) |
| **Average phase error 30.3°** (4-element beam deflector) and **65.3°** (200-element high-NA metalens) | Same platform, **real designs** rather than random arrangements | Periodic-boundary design's *intended* phase vs. each element's *actual* phase in the assembled device | ibid., Figs. 5(c), 7 |
| **Efficiency 41.3% → 68.8%** (deflector); focal-spot power **+65.6%** (metalens) | Same | Design built from periodic characterisation vs. the same design re-optimised with true local responses | ibid. |
| **Peak directivity error ≈ 0** — LP and ELP both predict D₀ = 25.6 dB; measured 26.1 dB | 10 GHz, **30 × 30** rectangular patches, 435 × 435 mm (0.483λ pitch), RO4350B ε_r = 3.66 / tanδ 0.0037, beam deliberately steered to θ = 35°, φ = 135° to *exaggerate* aperiodicity | Local periodicity vs. extended local periodicity vs. **measurement** at the DTU-ESA spherical near-field facility | [Zhou et al., EuCAP 2011, §III-B](https://www.ticra.com/wp-content/uploads/2018/03/Analysis-of-Printed-Reflectarrays.pdf) |
| **Qualitative total failure** — locally-periodic design "fails to perform wide-angle reflection" | 10 GHz, **λ/10 pitch** (3 mm), 54 interdigitated-capacitor cells over foam, 70° anomalous reflection | Cladding patterned by locally-periodic extraction vs. by an aperiodic method, both simulated in COMSOL | [Budhu & Grbic, arXiv:2211.11588, §IV](https://arxiv.org/abs/2211.11588) |

---

## 1. What the assumption is, in plain English

A metamaterial surface is a grid of small printed shapes. To find out what one shape does, you put a single copy in a simulator and tell the solver "pretend this tile repeats forever in both directions" — periodic, or Floquet, boundaries. The solver then gives you the reflection or transmission of an infinite sheet of *that one tile*.

That is cheap and it is standard practice. The catch is that it answers a question about a surface made of one tile, and real designs are made of *many different* tiles. Each tile's electrical behaviour depends on what its neighbours are doing, because the tiles are close enough together — typically half a wavelength or less apart — to be sitting inside each other's near field. Swap a neighbour for a different shape and the tile's own response moves.

The literature calls the assumption **local periodicity (LP)**, the **locally periodic approximation (LPA)**, or the **infinite array approach**. The fix, when anyone bothers, is **extended local periodicity (ELP)**: enlarge the simulated cell to include the element *and its eight real neighbours*, apply the periodic boundaries to that 3 × 3 block, and read out only the centre element's contribution. ELP is the technique that measures the error, because you can run both and difference them.

> "In the local periodicity approach, the presence of neighboring elements are accounted for in an inaccurate way since these array elements are not identical. … we propose an infinite approach where periodicity is applied on an extended unit cell, which includes the actual surrounding elements."
> — [Zhou et al., EuCAP 2011, §II-B](https://www.ticra.com/wp-content/uploads/2018/03/Analysis-of-Printed-Reflectarrays.pdf)

ELP is not free. Zhou et al. give the cost ratio directly: the LP calculation of a whole realistic reflectarray "only takes a couple of seconds", where **ELP requires 30–45 minutes**. That is roughly a thousandfold, and it is stated as the reason ELP is unsuitable for optimisation loops — which is exactly #111's two-tier problem, stated by someone else fifteen years ago.

---

## 2. The primary numbers

### 2.1 Costanzo, Venneri & Di Massa 2019 — the X-band answer

**S. Costanzo, F. Venneri, G. Di Massa, "Modified Minkowski Fractal Unit Cell for Reflectarrays with Low Sensitivity to Mutual Coupling Effects", *International Journal of Antennas and Propagation* 2019, Article ID 4890710, 11 pp. DOI [10.1155/2019/4890710](https://doi.org/10.1155/2019/4890710).** Open access (CC-BY). Retrieved in full this session.

This is the paper #111 was looking for. Its whole purpose is to measure the local-periodicity error and then design a cell that does not suffer from it.

**Setup.** 10 GHz. Diclad870 substrate, ε_r = 2.33, thickness 0.762 mm. Method-of-moments full-wave code. Cell pitch swept from 0.6λ down to 0.3λ (18 mm down to 9 mm). Three element families compared: a plain **variable-size square patch** (the workhorse of the field), a **Minkowski fractal patch**, and their new **modified-Minkowski patch whose upper and lower edges are held at fixed length** while the phase is tuned by the fractal indentation.

**How the error is measured.** ELP with the nearest eight neighbours. Two configurations of the same extended cell:

- **Config A** — all nine elements identical. This is exactly what infinite-array characterisation assumes.
- **Config B** — the two E-plane neighbours replaced by the **largest and the smallest** elements in the alphabet.

Config B is chosen deliberately as the worst case, and the E-plane is chosen because coupling between microstrip patches is strongest along it. Δφ is the gap between the two phase-versus-size curves.

> "To assess the worst case, two fixed elements are considered, having, respectively, the maximum and the minimum patch lengths … and the maximum/minimum scaling factor S. … only the results relative to E plane nonidentical elements are illustrated, as they give higher mutual coupling levels and consequently higher phase errors with respect to the H plane case."

**The result — Table 3, verbatim:**

| Cell pitch | Square patch: phase range / **max Δφ** | Minkowski: range / **max Δφ** | Proposed cell: range / **max Δφ** |
|---|---|---|---|
| **0.5λ** | 336° / **25°** | 342° / **21°** | 345° / **12°** |
| **0.4λ** | 330° / **>45°** | 332° / **≅45°** | 340° / **20°** |
| **0.3λ** | 288° / **>45°** | 310° / **≅45°** | 326° / **34°** |

and from the figures, the actual peak for the square patch at 0.4λ is **Max(Δφ) = 85°** (Fig. 5(c)); Minkowski **45°** (Fig. 6(c)); proposed cell **20°** (Fig. 7(c)). Table 3's ">45°" is a truncated entry; the text later quotes the square-patch range as "20° ≤ Δφ ≤ 85°".

**Two precisions that matter.** These are **peak** errors over the phase curve, not averages — the paper notes the proposed cell's 20° "occurs only in correspondence of a very small neighborhood" of one particular size ratio. And the whole analysis is **SIMULATED** (MoM), not measured.

**Why the square patch is so much worse — and this is the actionable part.** A variable-size square patch tunes its phase by *changing its own size*, which changes the **gap** to its neighbour. The paper spells this out: for the 0.4λ cell, the gap varies from **0.009λ up to 0.19λ** across the alphabet — a twentyfold swing in the spacing that sets the coupling capacitance.

> "the heavy variations in the gap distance between adjacent patches … cause very dissimilar mutual coupling levels that make unreliable periodic boundary conditions for reflectarray cell simulations."

Their circuit extraction quantifies it: **"the capacitance variation exhibited by the variable square-based cells is about 20 times larger than that provided by the corresponding fractal cells."** Plain English: if the letters in your alphabet all present the same edge to their neighbours, they barely notice each other changing, and superposition works. If they change their edges, they do.

**What the error costs, at system level.** Three 15 × 15 reflectarrays at 0.3λ spacing, beam steered to θ = 48°, synthesised from the LP phase curves and then simulated (the proposed cell's prototype was also measured; the caption labels the square-based and proposed-configuration curves as full-wave simulations and the fractal-based curve as measurements):

- Proposed cell (Δφ ≤ 20°) — sidelobes stay below −13 dB. Spec met.
- Minkowski (Δφ ≅ 45°) — sidelobe constraint **exceeded by 2.5 dB** at the first sidelobe.
- Square patch (20° ≤ Δφ ≤ 85°) — sidelobes reach **≅−8 dB** at θ = 0° and **≅−6.4 dB** at θ = −18°, exceeding the constraint **by up to 6.6 dB**, plus a **0.75 dB gain reduction** and "an aperture efficiency reduction of about 15%".

That last block is the closest thing in the literature to an error budget: it maps a phase error in degrees onto a performance penalty in dB. It is for a **beam-forming** objective, not an absorption one — see §6.

### 2.2 An et al. 2021/2022 — the only published error-versus-neighbour-count curve

**S. An, B. Zheng, M. Y. Shalaginov *et al.*, "Deep Convolutional Neural Networks to Predict Mutual Coupling Effects in Metasurfaces", [arXiv:2102.01761](https://arxiv.org/abs/2102.01761); published as *Adv. Optical Mater.* **10**(3), 2102113 (2022).** Both the preprint and the published PDF retrieved this session.

This is optical (1.55 µm, silicon nanoblocks on fused silica, 800 nm pitch = 0.516λ, 270 nm tall) rather than microwave, so its absolute numbers do not transfer. What does transfer is the **shape** of the error, because the mechanism is the same near-field coupling.

**The convergence experiment (§"Data collection", Fig. 2(e)).** They take 1,000 target elements, each surrounded by 10 *different* random elements on each side, treat the 10-neighbour result as ground truth, and then re-simulate with N = 0, 1, 2, … neighbours accounted for.

> "the simulation results of target meta-atoms with a periodic boundary … have significant amplitude and phase mean absolute error (MAE) of 0.33 and 59.14 degrees compared to when the number of neighboring meta-atoms (N) is 10. As the number of neighboring meta-atoms increases, the error gradually decreases. The large error values … are caused by the abrupt changes in phase gradients that can occur in randomly arranged meta-atoms. … even considering only the single nearest meta-atom on each side of the target would largely improve its EM response's accuracy."

They settle on **N = 4 neighbours each side** as the accuracy/cost balance. On a second platform (5.45 µm, higher-index n = 5 freeform elements) **N = 2 sufficed for the same accuracy**, because higher-index elements confine their fields more tightly and leak less into their neighbours.

Three things to take from this:

- **59.14° is a worst case by construction.** Neighbours are *random*, so adjacent phases can jump arbitrarily. It is the "how bad can it get" bound, not a design figure.
- **Real designs sit lower, and the error tracks the phase gradient.** For an actual 4-element beam deflector the average phase error was **30.3°**; for a 40-element metalens **30.4°**; for a 200-element high-NA metalens **65.3°**, with individual elements "almost 100 degrees" off near the steep-gradient edges. Bigger, faster-varying device → bigger error.
- **The device-level cost is large.** Beam-deflector efficiency **41.3% → 68.8%** on re-optimisation; metalens focal-spot power **+65.6%**; and across 1,000 randomly-assembled 4-element deflectors whose elements had "almost identical" periodic responses, measured efficiency ranged **50% to almost 90%** purely from which neighbours happened to sit together.

The 59.14° figure sits in the preprint's main text; in the published *Adv. Optical Mater.* version the convergence study was moved to Supporting Information §I, with only the N = 4 choice retained in the body.

### 2.3 Zhou et al. 2011 — the measured X-band counterweight

**M. Zhou, S. B. Sørensen, E. Jørgensen, P. Meincke, O. S. Kim, O. Breinbjerg, "Analysis of printed reflectarrays using extended local periodicity", *Proc. 5th EuCAP*, Rome, 2011, pp. 1494–1498.** Retrieved from TICRA's own copy. This is the paper that *defines* the ELP method Costanzo et al. use.

30 × 30 rectangular patches, 435 × 435 mm (14.5 mm pitch = 0.483λ), RO4350B, 10 GHz, offset feed, and the design was **deliberately chosen to exaggerate aperiodicity** by steering the beam to θ = 35°, φ = 135°. Built at DTU, measured at the DTU-ESA Spherical Near-Field Antenna Test Facility.

The result is a genuinely useful negative:

> "Both methods, LP and ELP, predict the maximum directivity to D₀ = 25.6 dB whereas the measured is D_meas = 26.1 dB. It is seen that the ELP approach is generally more accurate in the side lobe regions … However, there are a few regions where the LP approach yields a better prediction."

**The local-periodicity error does not show up in the main beam.** On a deliberately aperiodic X-band reflectarray, LP and ELP give the *same* peak directivity, and both are within 0.5 dB of measurement. The error lives in the **sidelobes and the scattered field**.

That has a sharp consequence for #104: the objective this map optimises is **absorption and backscatter reduction**, which *is* a scattered-field quantity. So this project sits squarely in the regime where the error shows up — not in the regime where it politely cancels.

Zhou et al. are also honest that ELP is not uniformly better: in some angular regions LP wins, and they attribute this to a truncation artefact in how ELP integrates the aperture field over less than a full period. **ELP is a better estimator, not a ground truth.**

### 2.4 Budhu & Grbic — the regime where LP does not merely err, it fails

**J. Budhu, N. Ventresca, A. Grbic, "Unit Cell Design for Aperiodic Metasurfaces", [arXiv:2211.11588](https://arxiv.org/abs/2211.11588).** Retrieved. Successor to Budhu & Grbic's *IEEE T-AP* **69**(1):122–134 (2021) paper, which is Xplore-stranded.

10 GHz. 54 interdigitated-capacitor cells at **1.5λ/10 pitch** (≈4.5 mm), on λ/20 Rohacell foam over a ground plane, designed to reflect normal incidence to **70°**.

> "the metasurface designed using locally periodic based extractions … fails to perform wide-angle reflection, whereas the metasurface designed using the aperiodic unit cell design technique … does."

No number is attached — it is a field-plot comparison — so this is a **qualitative** data point. But it marks the far end of the scale: at λ/10 pitch with a fast-varying reactance profile, the local-periodicity error is not a tens-of-degrees correction, it is a design that does not work. Their second example (80 cells, λ/10 pitch, 30° collimation) reports the same: local periodicity "fails to recreate the sidelobes of the homogenized design."

### 2.5 Supporting mechanism sources

- **[Deshpande, Zenin, Ding, Mortensen & Bozhevolnyi, arXiv:1809.10052](https://arxiv.org/abs/1809.10052)** (*Nano Letters*, 2018) — measures near-field coupling *directly*, with phase-resolved scattering-type near-field microscopy, on gold gap-plasmon metasurfaces. Their framing is the same as ours: "the performance of densely-packed metasurfaces is reduced, often quite significantly, in comparison with simple analytical predictions… mainly because of the near-field coupling between metasurface elements, which results in response from each element being different from the one anticipated by design simulations, which are commonly conducted for each individual element being placed in an artificial periodic arrangement." Their coupling figure-of-merit **rises steeply above an element length of ≈300 nm** and reaches ≈0.5 for the largest elements — i.e. coupling error is a strong function of how much of the cell the metal fills. Optical regime; **mechanism corroboration only**.
- **[Skarda, Trivedi, Su et al., arXiv:2107.09879](https://arxiv.org/abs/2107.09879)** (distributed T-matrix simulation) — compares LPA against a full scatterer-interaction solve and finds the split runs on **element aspect ratio**: "for high aspect ratio scatterers … the field stitching method does not [deviate]. However, for small aspect-ratio scatterers, which are expected to have larger inter meta-atom interactions, both the LPA approximations significantly deviate." Tall, strongly-confining elements tolerate LPA; flat, thin ones do not. **Printed metamaterial skins on thin substrates are the flat kind.** No number in the text; the comparison is a figure.
- **[Elineau et al., arXiv:2401.00858](https://arxiv.org/abs/2401.00858)** — an 8 GHz, 27 × 27-cell gradient metasurface with a 3-cell supercell, designed by supercell Floquet optimisation and **measured**: predicted 6.80 dB RCS reduction against **measured 6.85 dB** in the parasitic direction. It is a demonstration that *supercell-level* Floquet (which does include the unlike neighbours inside the block) predicts measured RCS well. The authors then name their own assumption stack — "local periodicity, infinite environment, description with only a phase response, phase response computed at only one frequency" — and observe the optimised surface correlates *less* well with measurement than the initial one, because its cells moved closer together and coupled more. Directionally supports §3; carries no LPA error figure of its own.

---

## 3. Do the numbers agree?

Yes, once you stop comparing them as if they were the same measurement. Three variables set the magnitude, and every source agrees on all three directions:

**a) Pitch — how close the elements are.** Costanzo et al. give this cleanly at fixed frequency and shape: max Δφ roughly **doubles going from 0.5λ to 0.4λ** for the square patch (25° → 85°) and keeps climbing to 0.3λ. Budhu & Grbic at 0.1λ get outright failure. Zhou et al. at 0.48λ get a peak-directivity error of zero. **Below about λ/2, the assumption starts to cost real degrees; below about λ/4 it stops being an approximation and becomes a mistake.**

**b) How different the neighbours are, and how fast the design varies.** An et al. separate this most cleanly on one platform: random neighbours **59°**, a gentle 4-element deflector **30°**, a steep high-NA metalens **65°** with individual elements near **100°**. Costanzo et al. build their Config B out of the two extreme members of the alphabet precisely to bound this. **Error is a property of the design's phase gradient, not just of the element.**

**c) How much the element leaks into its neighbour.** Three independent statements of the same thing: An et al. need N = 4 neighbours for silicon-on-silica but only N = 2 for higher-index freeform elements; the T-matrix work splits on aspect ratio; Costanzo et al.'s circuit extraction shows a 20× difference in capacitance variation between a shape that changes its edges and one that does not.

Where the sources appear to disagree — Zhou et al.'s zero peak-directivity error against Costanzo et al.'s 85° — they are measuring different things, and both are right. A tens-of-degrees per-element phase error, spread quasi-randomly over 900 elements, largely averages out in the coherent main-beam sum and re-appears as raised sidelobes and scattered power. **Peak forgives; scatter does not.**

---

## 4. Correction: Cole et al.'s 11% is not the unlike-neighbour number

**M. A. Cole, A. Lamprianidis, I. V. Shadrivov, D. A. Powell, "Refraction efficiency of Huygens' and bianisotropic terahertz metasurfaces", [arXiv:1812.04725](https://arxiv.org/abs/1812.04725).** Re-retrieved and read in full this session.

Two distinct findings in that paper have been conflated in #131's resolution comment and in #104's decision log.

**The 11% is intra-cell.** Their cell is three metal layers separated by dielectric, designed from a transmission-line model layer by layer. When the assembled cell is simulated:

> "It is clear that the transmission magnitude is not equal to the designed value of 1.0 … at the target frequency of 1 THz. Instead there is a transmission maximum at a frequency of 0.89 THz. … **This frequency shift is caused by near-field coupling between the layers, which is not accounted for in the transmission-line model.**"

0.89 vs 1.0 THz is the 11%. It is the cost of stacking three layers and modelling them as an ideal circuit — an error of *composition within one letter*, which for #104 maps onto the multi-layer stack of Example 3, not onto neighbour coupling at all.

**The unlike-neighbour statement is separate and unquantified.** Later, discussing the assembled supercell:

> "the efficiency of these supercells is generally lower than that of the individual cells … Furthermore, **there is some evidence that the optimal frequency is shifted away from the designed frequency.** We attribute this to the coupling between neighboring cells… once the cells are placed next to non-identical neighbors, the coupling coefficient will change… To mitigate this frequency shift, we perform a numerical optimization of the entire supercell."

"Some evidence" is as precise as it gets. The before/after efficiencies are plotted (Fig. 5) but never tabulated; the only efficiency numbers in the text — 93.5% and 94.0% at 55°, 76.4% and 91.4% at 70° — are all **post-optimisation**, so they cannot be differenced to recover the penalty.

**Net effect on the project.** #111's starting magnitude of "11%" should be retired as a coupling figure and re-filed as an intra-cell stack-modelling figure. The coupling error bar should instead be the numbers in §2. Cole et al. remain the best plain statement of the *mechanism* and of the supercell-as-unit remedy — that part of #131 stands unchanged.

---

## 5. A supercell sizing rule from an error budget: still nowhere

#131 concluded no such convention exists. **Confirmed, against a wider search.** Every block-size rationale found in this pass:

| Block size | Set by | Source |
|---|---|---|
| 3 cells per supercell, 27 × 27 array, 8 GHz | "the lowest number of cells" that produces the required linear phase variation — a beam-geometry floor | [Elineau et al., arXiv:2401.00858](https://arxiv.org/abs/2401.00858) |
| Extended unit-cell period **u_x = λ₀ / sin θ_D** | Pure grating geometry: the period that puts the diffracted order at the wanted angle | [Donda & Hegde, *PIER M* **77**:83–92 (2019), Eq. (2)](https://www.jpier.org/issues/volume.html?paper=18092801) |
| 4 cells per supercell (THz Huygens/bianisotropic) | "largely determined by fabrication constraints… but a higher number of cells better approximates the continuous impedance functions" — a tolerance-versus-fidelity trade, not an error budget | [Cole et al., arXiv:1812.04725, §II](https://arxiv.org/abs/1812.04725) |
| 3 × 3 extended cell (8 neighbours) | Convention of the ELP method itself — the nearest ring, chosen because it is the nearest ring | [Zhou et al., EuCAP 2011](https://www.ticra.com/wp-content/uploads/2018/03/Analysis-of-Printed-Reflectarrays.pdf); [Costanzo et al. 2019](https://doi.org/10.1155/2019/4890710) |
| 7 × 7 identical elements per lattice, 35 mm pitch | Scattering angle | Cui et al. 2014 (established in [#131](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/131)) |
| N = 4 neighbours each side (silicon), N = 2 (high index) | Empirical convergence: "to strike a balance between simulation accuracy and optimization difficulty (as well as data collection costs)" | [An et al., arXiv:2102.01761](https://arxiv.org/abs/2102.01761) |

The last row is the closest anyone comes. An et al. actually **have** the error-versus-block-size curve (Fig. 2(e)) — it is the only published one this search found — and they use it to pick a number. But they pick it by eye against compute cost, not against a stated performance requirement. **Nobody writes "the block must be N elements because the design's phase budget is ±X°."**

So #130's super-cell sizing question remains derive-not-look-up. What has changed is that the *method* for deriving it is now fully documented and cheap to reproduce: build the ELP extended cell, sweep the number of accounted-for neighbours, plot the phase error, and stop where the error drops below the budget. That is An et al.'s Fig. 2(e) procedure, applied to our shapes on our substrate.

---

## 6. What a superposition-based evaluator can honestly say about itself

This section is **derived by this document**, not quoted from a source. It combines two `LITERATURE-SUPPORTED` numbers into a statement neither source makes. Provenance: **CALCULATED / INFERRED**. It should be confirmed against our own Floquet solves before it is relied on.

Cui et al. publish the only acceptance band this project has found at system level: **10 dB RCS reduction is guaranteed while the phase difference between the two coded tile types stays between 145° and 215°** — that is **±35° about the nominal 180°** (established in #131, from arXiv:1407.8442). Plain English: a one-bit checkerboard works as long as the two tile types stay within about a tenth of a wave cycle of being exactly opposite.

Set that ±35° budget against §2's error bar and the picture is immediate:

| Alphabet and pitch | LP phase error | Against a ±35° budget |
|---|---|---|
| Coupling-insensitive cell, 0.5λ | 12° | Comfortable — superposition is safe |
| Variable-size square patch, 0.5λ | 25° | Marginal — most of the budget spent on modelling error |
| Coupling-insensitive cell, 0.4λ | 20° | Workable |
| Minkowski, 0.4λ | 45° | **Budget blown by the modelling error alone** |
| Variable-size square patch, 0.4λ | 85° | **Budget blown 2.4×** |
| Variable-size square patch, 0.3λ | >45° (85° peak) | **Not evaluable by superposition** |

Three consequences for #111 and #130:

1. **The fast tier's error bar is a function of the alphabet, not a constant.** A single "±X°" attached to the evaluator would be dishonest. It has to be attached to the alphabet-and-pitch pair, in the Marcuvitz style #131 recommended: a number *plus the box it holds in*.
2. **Alphabet design can buy the error bar down, and that is the cheapest lever available.** Costanzo et al.'s whole result is that a letter which changes its phase *without changing the gap it presents to its neighbours* has ~4× less coupling error than one that changes size. For #130 this converts into a **selection criterion on candidate shapes** that costs nothing at design time: prefer shape families whose tuning parameter is interior to the element. The patent's I-shaped ring resonators are worth checking against exactly this test — an I-shape tuned by its interior slot keeps its outer edge fixed; one tuned by overall scale does not.
3. **Keeping pitch at or above λ/2 is worth real accuracy.** Every source agrees the error accelerates below half a wavelength. Against this, #131 recorded Munk's warning that solid patches force pitch *above* λ/2 and bring early grating lobes. Those two pressures bracket the design from both sides and the window between them is narrow — that tension belongs in #130's decision, not in a footnote.

**One translation that does *not* work.** The classical route from phase error to performance is Ruze's equation — random aperture phase errors of RMS σ cost gain by roughly exp(−σ²) ([Welch, NASA/TP—2008-214953](https://ntrs.nasa.gov/api/citations/20080018466/downloads/20080018466.pdf), which also cautions that Ruze *overstates* the loss for its own test case). That is a **gain** result for a beam-forming aperture. #104's objective is absorption and backscatter reduction, where the figure of merit is scattered power in unwanted directions — the quantity Ruze's formulation treats as the *loss channel* rather than the output. **Do not use Ruze to size the absorber's error budget.** Cui's 145°–215° band is the right shape of tool; #104 will need its own equivalent for absorption, which #131 already listed as an item with no prior art.

---

## 7. Checked and found nothing; stranded

**Searched and genuinely empty:**

- **A supercell sizing rule derived from a coupling-error budget.** Six independent sizing rationales found (§5); none is an error budget.
- **An error bar published *as* an error bar for a superposition-based evaluator.** Nobody states "superposition of independently characterised elements is accurate to ±X° at block size N." The numbers in §2 all exist as *motivation for a better method*, extracted here and repurposed. That repurposing is ours.
- **Any per-letter measured library, or measured LP-versus-ELP element phase.** Zhou et al. measure the assembled reflectarray's pattern; Costanzo et al. measure one assembled prototype. Every element-level error number in §2 is **SIMULATED**. #131's finding that measurement in this field validates the assembled article and never the individual letters is reconfirmed.
- **Anything at all on LP error for *absorbers* specifically** — as opposed to reflectarrays, beam deflectors and metalenses. Absorber papers run finite-array-size convergence studies (N × N from 1 to 9 was the pattern seen in search summaries) but those study **edge truncation**, which is a different error: it is about the array *ending*, not about neighbours *differing*. For a Tier A uniform absorber the neighbours genuinely are identical and this whole question does not arise; it arises for Example 7's checkerboard and the Tier B aperture surfaces.

**Stranded (reported, not guessed at):**

| Source | Why | What it likely holds |
|---|---|---|
| Rodríguez-Trujillo et al., "Phase Smoothing for Mutual Coupling Mitigation in Multifunctional Metasurfaces Designed with Diffractive Neural Networks", *Adv. Optical Mater.* 2026, DOI 10.1002/adom.202502746 | Open access, but Wiley 403s every automated route | **W-band (86 GHz) transmissive metasurface** — the nearest thing found to our frequency regime with a coupling-error treatment. Its "phase smoothing via Laplacian convolution" is a *design-side* remedy: limit how fast neighbours may differ, so local periodicity stays valid. That is directly relevant to #130's placement rules. **Worth a manual pull.** |
| Murugesan & Selvan, "On the effect of array size on the radar cross section reduction bandwidth of checkerboard metasurfaces", *Frequenz* **77**(5–6):273–279 (2023), DOI 10.1515/freq-2022-0021 | De Gruyter returns a bot challenge | Already carried in #107/#130. Search-result summary states three array sizes (120, 240, 480 mm², plus 600 mm² for one structure) on Rogers and FR4, and that "the 8 and 10 dB RCS reduction bandwidths drop as array size increases." **UNVERIFIED at primary level in this pass** — retrieved only as a search summary, not as text. |
| Zhou, "Phase error analysis for reflectarray antennas based on study of quasi-periodic effect", IEEE conf. 7928485 | Xplore 403 | Title suggests exactly this question; contents unknown |
| Budhu & Grbic, *IEEE T-AP* **69**(1):122–134 (2021) | Xplore 403 | The journal version of §2.4; the arXiv companion was retrieved instead |
| Choi et al., "Realization of high-performance optical metasurfaces over a large area", *npj Nanophotonics* (2024), DOI 10.1038/s44310-024-00029-2 | nature.com redirects to an auth endpoint | A review; its quoted 59.14° traces to An et al., which was retrieved directly, so nothing is lost |

**Route note for future passes:** `web.archive.org` was unreachable from this environment for the whole session (tunnel reset at the proxy on every attempt, including via a reader proxy). Hindawi/Wiley open-access PDFs *were* reachable through a full-text mirror when the publisher and the archive both refused. `api.unpaywall.org`, `api.openalex.org` and `api.semanticscholar.org` all worked and are the fastest way to find where an open-access PDF actually lives.

---

## Provenance summary

| Claim | Provenance |
|---|---|
| Costanzo et al. Table 3 phase errors (12°–85°), conditions, and the sidelobe/gain consequences | **LITERATURE-SUPPORTED** (full text retrieved); the underlying analysis is `SIMULATED` (MoM), one prototype measured |
| An et al. 59.14° / 0.33 MAE, N-convergence, 30.3°/65.3° design errors, efficiency figures | **LITERATURE-SUPPORTED** (preprint and published PDF both retrieved); `SIMULATED` (CST) |
| Zhou et al. LP = ELP = 25.6 dB vs 26.1 dB measured; ELP cost 30–45 min vs LP seconds | **LITERATURE-SUPPORTED** (full text retrieved); directivity comparison is `MEASURED` |
| Budhu & Grbic qualitative LP failure at λ/10 | **LITERATURE-SUPPORTED** (retrieved); qualitative only, no number published |
| Cole et al.'s 11% is intra-cell layer coupling, not unlike-neighbour coupling | **LITERATURE-SUPPORTED** — negative/corrective finding from re-reading the retrieved full text |
| Cole et al. publish no number for the unlike-neighbour shift | **LITERATURE-SUPPORTED** (exhaustive term search of retrieved full text) |
| #111's cited DOI 10.1155/2019/9479010 is wrong; the paper is 10.1155/2019/4890710 | **LITERATURE-SUPPORTED** (both DOIs resolved via Unpaywall/OpenAlex/Semantic Scholar) |
| No supercell sizing rule from an error budget exists | **LITERATURE-SUPPORTED negative finding** — absence across every source reachable in this pass, not proof of absence in the field |
| The ±35° budget vs. §2 error-bar comparison in §6, and the three consequences drawn from it | **CALCULATED / INFERRED** — this document's own synthesis of two literature numbers; confirm against our own Floquet solves |
| "Prefer letters whose tuning parameter is interior to the element" as an alphabet design rule | **INFERRED** from Costanzo et al.'s gap/capacitance mechanism; the mechanism is theirs, the rule is ours |
| Ruze's equation is the wrong translation for an absorption objective | **INFERRED** — reasoning from what Ruze's derivation treats as signal and as loss |
| Murugesan & Selvan array-size result | **UNVERIFIED** in this pass (search summary only); carried from #107 |

---

## Retrieved sources

1. S. Costanzo, F. Venneri, G. Di Massa, "Modified Minkowski Fractal Unit Cell for Reflectarrays with Low Sensitivity to Mutual Coupling Effects", *International Journal of Antennas and Propagation* **2019**, Art. 4890710, DOI [10.1155/2019/4890710](https://doi.org/10.1155/2019/4890710). Open access (CC-BY). **The X-band error table.**
2. S. An, B. Zheng, M. Y. Shalaginov, H. Tang, H. Li, L. Zhou, Y. Dong, M. Haerinia, A. M. Agarwal, C. Rivero-Baleine, M. Kang, K. A. Richardson, T. Gu, J. Hu, C. Fowler, H. Zhang, "Deep Convolutional Neural Networks to Predict Mutual Coupling Effects in Metasurfaces", [arXiv:2102.01761](https://arxiv.org/abs/2102.01761); *Adv. Optical Mater.* **10**(3):2102113 (2022), DOI 10.1002/adom.202102113. **The error-versus-neighbour-count curve.**
3. M. Zhou, S. B. Sørensen, E. Jørgensen, P. Meincke, O. S. Kim, O. Breinbjerg, "Analysis of printed reflectarrays using extended local periodicity", *Proc. 5th European Conference on Antennas and Propagation (EuCAP)*, Rome, 2011, pp. 1494–1498. [Author copy](https://www.ticra.com/wp-content/uploads/2018/03/Analysis-of-Printed-Reflectarrays.pdf). **The ELP method and the measured X-band counterweight.**
4. J. Budhu, N. Ventresca, A. Grbic, "Unit Cell Design for Aperiodic Metasurfaces", [arXiv:2211.11588](https://arxiv.org/abs/2211.11588). Successor to Budhu & Grbic, "Perfectly Reflecting Metasurface Reflectarrays: Mutual Coupling Modeling Between Unique Elements Through Homogenization", *IEEE Trans. Antennas Propag.* **69**(1):122–134 (2021) — that journal paper is Xplore-stranded.
5. M. A. Cole, A. Lamprianidis, I. V. Shadrivov, D. A. Powell, "Refraction efficiency of Huygens' and bianisotropic terahertz metasurfaces", [arXiv:1812.04725](https://arxiv.org/abs/1812.04725). **Re-read to correct the 11% attribution.**
6. M. Elineau, R. Loison, S. Méric, R. Gillard, P. Pagani, G. Mazé-Merceur, P. Pouliguen, "RCS angular control with gradient metasurfaces: design and measurement", [arXiv:2401.00858](https://arxiv.org/abs/2401.00858).
7. K. D. Donda, R. S. Hegde, "Optimal Design of Beam-Deflectors Using Extended Unit-Cell Metagratings", *Progress In Electromagnetics Research M* **77**:83–92 (2019). [Open PDF](https://www.jpier.org/issues/volume.html?paper=18092801).
8. R. Deshpande, V. A. Zenin, F. Ding, N. A. Mortensen, S. I. Bozhevolnyi, "Direct characterization of near-field coupling in gap plasmon-based metasurfaces", [arXiv:1809.10052](https://arxiv.org/abs/1809.10052); *Nano Letters*, DOI 10.1021/acs.nanolett.8b02393.
9. J. Skarda, R. Trivedi, L. Su, D. Ahmad-Stein, H. Kwon, S. Han, S. Fan, J. Vučković, "Low-overhead distribution strategy for simulation and optimization of large-area metasurfaces", [arXiv:2107.09879](https://arxiv.org/abs/2107.09879).
10. M. Zhou, E. Jørgensen, O. S. Kim, S. B. Sørensen, P. Meincke, O. Breinbjerg, "Accurate and Efficient Analysis of Printed Reflectarrays With Arbitrary Elements Using Higher-Order Hierarchical Legendre Basis Functions", *IEEE AWPL* **11**:814–817 (2012). [DTU Orbit copy](https://backend.orbit.dtu.dk/ws/files/10144602/22C4Cd01.pdf).
11. B. W. Welch, "Application of Ruze Equation for Inflatable Aperture Antennas", NASA/TP—2008-214953, NASA Glenn Research Center, April 2008. [NTRS PDF](https://ntrs.nasa.gov/api/citations/20080018466/downloads/20080018466.pdf).
