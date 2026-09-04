# Prior art for element libraries: what can #130's symbol alphabet adopt instead of derive?

**Research date:** 2026-09-03
**Ticket:** [#131](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/131) — serves [#130](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/130) (symbol alphabet), [#111](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/111) (two-tier EM modelling), part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104).
**Scope:** What established fields already publish as an "element library" — reflectarrays, frequency selective surfaces, coding metasurfaces, closed-form equivalent-circuit models — and what #130 must derive because nobody has published it.

Every citation below is either **retrieved** (a primary source was actually downloaded and read in this session — quoted text and page-level detail follow from that text) or explicitly marked **UNVERIFIED / STRANDED**. Nothing here is a recalled citation presented as checked.

---

## Bottom line up front

**Three of the six areas have strong, directly adoptable prior art. Two have partial prior art that answers a different question than the one #130 is asking. One has essentially none.**

- **Element-library-as-lookup is real and forty years old.** A reflectarray is designed by solving *one* unit cell inside an infinite array of copies of itself and tabulating reflection phase against a dimension. Plain English: you simulate one tile, pretend the whole surface is made of that tile, and write down the phase it bounces back — then repeat for each tile size. That is exactly #130's alphabet, and it is textbook practice. **Adoptable as-is.**
- **Closed-form equivalent-circuit models are real, verified, and a better fast tier than Maxwell-Garnett — but they cover far fewer shapes than the ticket hoped.** Plain English: for a few simple shapes there are algebra formulas that give you the tile's electrical behaviour straight from its dimensions, with no simulation at all. The verified formulas cover **strip gratings, square-patch arrays, and post arrays — and nothing else.** No closed form was found for the patent's I-shaped ring resonators, for loops, or for crosses. The right architecture is therefore a **hybrid**: closed form for the layer stack, one full-wave solve per *shape* to extract that shape's capacitance, then algebra for every size and substrate variation of it.
- **Ligature (characterising a block as a unit) has clear precedent, and the literature reaches for it for exactly the reason #130 does.** When cells are placed next to unlike neighbours the per-cell characterisation stops holding, and the published fix is to full-wave-optimise the whole block. **Adoptable as a pattern.** What is *not* published is a rule for choosing the block size from a coupling-error budget — every block size found in the literature was set by something else entirely.
- **The response band — #130's central proposal — has almost no prior art.** Element libraries publish a **nominal curve**. Tolerance appears, when it appears at all, as a separate per-design perturbation study run after the fact, not as a band travelling with the element. #130's "each letter carries a band, and the requirement's threshold is checked against the pessimistic edge" is genuinely new work.

---

## The table

| What exists | What it covers | Directly adoptable? | Source (retrieved unless noted) |
|---|---|---|---|
| **Reflectarray phase-vs-dimension lookup** (unit cell in infinite array of copies, sweep one dimension, tabulate reflection phase) | Patch, ring, dipole, cross-dipole, split loop, fractal (Minkowski), slotted patch. Phase range, incidence angle, phase quantisation are the named sweep axes | **Yes — the pattern is the alphabet.** #130 is re-deriving standard practice | [Yang, EuCAP 2013 tutorial slides](https://www.eucap2013.org/files/EuCap2013%20FanYang.pdf), pp. 6, 9, 11, 22 |
| **Limited-phase-range problem and its published fixes** | Single-layer variable-size elements give **under one full 360° cycle**; multilayer / aperture-coupled stub / multi-resonant elements exceed it (2 cycles demonstrated, 4+ cycles cited) | **Yes — adopt the diagnosis and the fixes** | [Ozturk & Saka, arXiv:2009.12343](https://arxiv.org/abs/2009.12343), §I, §III–IV |
| **Phase-curve *linearity* as an explicit design objective** | An error function scoring how far the phase-vs-dimension curve departs from a constant-slope line, minimised during element optimisation | **Yes — this is the field's sensitivity proxy** (see §6) | [Ozturk & Saka, arXiv:2009.12343](https://arxiv.org/abs/2009.12343), Eq. (2), Fig. 3 |
| **Munk's four-group FSS element taxonomy** | Group 1 centre-connected (dipole, tripole, anchor, Jerusalem cross, square spiral); Group 2 loops (three/four-legged loaded, circular, square, hexagonal); Group 3 solid interior / plate; Group 4 combinations | **Yes, with a caveat** — the split is by **shape**, annotated with response (see §2) | Munk 2000 **STRANDED**; classification retrieved verbatim from [Elzwawi, INRS thesis, pp. 8–9](https://espace.inrs.ca/id/eprint/12049/1/Elzwawi,%20Ghada%20Hussain.pdf), citing Munk as its ref. [10] |
| **Coding metasurface 1-bit / 2-bit formalism** | Two cells at 0/π, or four at 0/π/2/π/3π/2; far-field by array-factor summation over blocks; optimised code tables for N = 6…20; RCS-reduction formula | **Yes — citation VERIFIED, conventions adoptable** | [Cui, Qi, Wan, Zhao & Cheng, arXiv:1407.8442](https://arxiv.org/abs/1407.8442); published as *Light: Sci. Appl.* **3**, e218 (2014) |
| **Super-cell / "lattice" of identical elements as the coded unit** | Cui's experimental article: 8×8 lattices, 280 mm edge, **35 mm lattice pitch, 7×7 identical elements per lattice** | **Yes as a pattern; NO as a sizing rule** — D is set by the target scattering angle, not by coupling | [Cui et al., arXiv:1407.8442](https://arxiv.org/abs/1407.8442), main text and Appendix Fig. S1 |
| **Explicit statement of the local-periodicity failure and the supercell fix** | "periodic boundary conditions … fully accounts for coupling between identical neighbors. However, once the cells are placed next to non-identical neighbors, the coupling coefficient will change" — fix is numerical optimisation of the whole supercell | **Yes — this is #130's catch, stated and quantified by others** | [Cole, Lamprianidis, Shadrivov & Powell, arXiv:1812.04725](https://arxiv.org/abs/1812.04725), §I, §III |
| **Closed-form grid impedance: square-patch arrays and strip grids, oblique incidence, on a substrate** | Grid parameter α = (k_eff·D/π)·ln[1/sin(πw/2D)]; ε_eff = (ε_r+1)/2; separate TE/TM forms; full HIS input impedance over a grounded slab | **YES — highest-value item. Better fast tier than Maxwell-Garnett for these shapes** | [Luukkonen, Simovski, Granet, Goussetis, Lioubtchenko, Räisänen & Tretyakov, arXiv:0705.3548](https://arxiv.org/abs/0705.3548); IEEE T-AP **56**(6):1624–1632, 2008 |
| **Closed-form absorber model** (patterned FSS on a lossy grounded substrate) | Analytic Re{Z_in}; substrate impedance A, B; dielectric loss resistor R_D; ohmic resistor R_O; evanescent-mode capacitance correction for thin spacers | **YES — this is the Example 3 topology.** Needs one full-wave extraction per *shape* for C₀ | [Costa, Genovesi, Monorchio & Manara, arXiv:1211.1902](https://arxiv.org/abs/1211.1902) (author copy of IEEE T-AP paper) |
| **Marcuvitz, *Waveguide Handbook*, gratings in free space** | **Only four free-space structures: §5.18 capacitive strips, §5.19 inductive strips, §5.20 capacitive posts, §5.21 inductive posts.** Explicit validity limits and a stated ≤10% error | **Partially** — the accuracy discipline is exemplary; the shape coverage is far narrower than hoped | [Marcuvitz, *Waveguide Handbook*, MIT Rad Lab Series vol. 10, pp. 280–288](http://www.introni.it/pdf/10%20-%20Waveguide%20Handbook.pdf) (scanned copy; title page and TOC verified) |
| **Tolerance handled as a per-design perturbation study** | Vary each dimension by ±Δs and ±2Δs around nominal (Δs = 25 µm laser resolution), re-simulate, inspect S₁₁ family | **Partially** — the *method* is adoptable; it is not a band attached to a library entry | [Parellada-Serrano et al., arXiv:2307.07224](https://arxiv.org/abs/2307.07224), §III-A |
| **A system-level tolerance band on the coding phase** | "10-dB RCS reduction is achieved when the phase difference varies from 145° to 215°" — a stated acceptance band around the nominal 180° | **Yes — closest published thing to #130's response band**, but it is a *system* band, not a *letter* band | [Cui et al., arXiv:1407.8442](https://arxiv.org/abs/1407.8442), main text and Appendix §2 |
| **Element libraries carrying a MEASURED response per letter** | — | **NO PRIOR ART FOUND** (see §"What must be derived") | — |
| **Super-cell size chosen from a stated coupling-error budget** | — | **NO PRIOR ART FOUND** | — |
| **Element admitted to a library only after successful fabrication** | — | **NO PRIOR ART FOUND** | — |

---

## 1. Reflectarray element libraries — CONFIRMED, and older than the ticket assumed

### What the practice is

A reflectarray is a flat panel of printed tiles that mimics a curved dish: each tile bounces the feed's wave back with a chosen phase delay so the reflected wavefronts line up into a beam. The design method is exactly a letter-with-a-response-curve:

> "Full-wave analysis of unit cell: **Infinite array approach** … Incident angle, phase range, phase quantization, quasi-periodic FDTD model"
> — [Yang, EuCAP 2013](https://www.eucap2013.org/files/EuCap2013%20FanYang.pdf), p. 11

Plain English: you build one tile in the simulator, wrap it in mirrors so the solver believes it is surrounded by infinitely many identical copies, and record what comes back. Repeat for each tile dimension. The result is a curve, and the design is then "read off" that curve tile by tile.

The three named phasing mechanisms — the alphabets in use — are **variable element size, element rotation, and phase/time-delay lines** ([Yang, p. 6](https://www.eucap2013.org/files/EuCap2013%20FanYang.pdf)). Catalogued shapes across the retrieved sources: **square and rectangular patch, circular ring, cross dipole, split square loop, Minkowski fractal patch, H-slotted patch, double/triple rings**.

Yang's own tri-band demonstrator is a concrete element inventory: one 0.566 m aperture carrying **692 cross dipoles (C band, 7.1 GHz), 685 square rings (X band, 8.4 GHz), and 10,760 circular rings (Ka band, 32 GHz)** on a single 62-mil, ε_r = 2.33 layer ([Yang, p. 23](https://www.eucap2013.org/files/EuCap2013%20FanYang.pdf)). Three letters, three bands, one sheet. Provenance: **LITERATURE-SUPPORTED**.

### Origin of the practice

Pozar & Metzler, "Analysis of a reflectarray antenna using microstrip patches of variable size", *Electronics Letters*, April 1993, is cited on Yang's own reference slide as one of the three founding works ([Yang, p. 5](https://www.eucap2013.org/files/EuCap2013%20FanYang.pdf)), alongside Munson & Haddad's US patent 4,684,952 (1987) and Huang's JPL Publication 90-45 (1990). **The 1993 paper itself is STRANDED** — IET Digital Library returns a paywall to automated fetches. Its *existence, date, and role* are LITERATURE-SUPPORTED via Yang's slide; the claim that it introduced the phase-vs-patch-size design curve is **UNVERIFIED** at primary-source level. The ticket's belief that this is standard practice since the 1990s is confirmed; the specific attribution is not.

### Phase range and phase wrap — the honest numbers

This is the part that matters for #130, because it is the alphabet's *reachable set*.

- **A single-pole resonator can contribute at most 180° of phase shift.** But in a reflectarray the wave passes the tile twice (in and back out off the ground plane), so "a single-pole resonator is all that is required to produce nearly 360° of phase shift in a reflectarray" — [Hum & Perruisseau-Carrier, arXiv:1308.4593](https://arxiv.org/abs/1308.4593), §III. Plain English: reflection gets you two bites of the same resonance, which is why reflectarrays are easier to phase than lenses.
- **In practice single-layer variable-size designs still fall short of a full cycle.** "phase ranges occur less than a full cycle for single layer designs" — [Ozturk & Saka, arXiv:2009.12343](https://arxiv.org/abs/2009.12343), §I. Their survey of single-layer Minkowski elements: "maximum phase range provided by the unit cell designs are insufficient (lower than one cycle)".
- **The published fixes are all "add poles or add layers":** two- and three-layer stacked patches; aperture-coupled phasing stubs beneath the reflector (Ozturk & Saka achieve **greater than two full cycles with S₁₁ amplitude better than −1 dB** at 10 GHz on a 0.4λ × 0.4λ cell, Rogers RO4003C); Carrasco et al. cited for **more than 4-cycle phase range at less than 0.8 dB reflection loss**. An H-shaped slot cut into a square patch reaches **>480°** on a single layer ([Ali, Ahmad & Choi, *Nanomaterials* 14(18):1495, 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11434495/), retrieved via PMC — the phase curve is produced in HFSS with "Floquet mode excitation with a master–slave boundary condition").
- **The trade is range against slope.** Achieving more than 360° from ringed elements comes "with a sharp slope"; a gentler slope (which buys bandwidth and tolerance immunity) can be had from thicker substrates "at the expense of an inadequate phase range of less than 300°". Provenance **LITERATURE-SUPPORTED, secondary** — this trade-off statement was surfaced in search results attributed to single-layer broadband reflectarray papers whose full texts sit behind ScienceDirect; treat the *direction* of the trade as solid and the exact 300° figure as **UNVERIFIED**.

**How they handle wrap:** they do not unwrap — they *reach*. The phase requirement is modulo 360°, so the design problem is to make the element span a full 360° with a workable slope, and the entire multilayer / multi-resonator / stub literature exists to buy that span. Provenance: **LITERATURE-SUPPORTED**.

**How the libraries are published:** as **curves** (phase versus one swept dimension, one curve per frequency or per incidence angle), sometimes as the underlying tables. No source retrieved here published a fitted closed-form phase-versus-dimension formula for a resonant element. The ticket's guess of "tables, curves, fitted formulas" is confirmed for the first two and **not found** for the third.

### Direct read-across to #130

- The **letter-carries-a-response-curve** model is standard. Adopt it; do not derive it.
- The letter's response must be recorded **against incidence angle as well as frequency** — Yang lists incident angle alongside phase range as a primary axis. A letter characterised only at normal incidence is under-specified.
- **Phase quantisation is a known, costed effect**, not a novelty: "phase errors made at each element due to the finite number of available phase states result in reduced gain and rising side lobe levels" — [Hum & Perruisseau-Carrier, arXiv:1308.4593](https://arxiv.org/abs/1308.4593), §II-A. A finite alphabet has a *known kind* of penalty. That penalty is well characterised for beam-forming (gain loss, sidelobes); it is **not** characterised for absorption or backscatter reduction, which is what #104 needs.

---

## 2. FSS element taxonomies — the classification is by SHAPE, annotated with RESPONSE

Munk's *Frequency Selective Surfaces: Theory and Design* (Wiley, 2000) is confirmed as the canonical reference, and **is STRANDED** — no reachable full text. The four-group classification was retrieved verbatim from an open-access doctoral thesis that reproduces it and cites Munk as its reference [10]:

> **Group-1:** The centre connected or N-poles, such as the simple straight element, three-legged element; anchor elements; the Jerusalem cross; and the square spiral. … At the first dominant resonance, the length of these elements is about a half wavelength. These elements produce moderate bandwidth, but because of their shapes, they can be backed together to produce a broadband response, as when the spacing element becomes smaller the bandwidth increases. This also contributes to pushing the grating response to higher frequencies.
>
> **Group 2:** The loop types such as the three- and four-legged loaded elements; the circular loops; the square and hexagonal loops … The length of this type is about a wavelength. This type of element is the most recommended element for both stop and band-pass applications, as it is characteristic by its ability to offer broadband. it is a small element with stable resonant frequency in response to different angles of incident.
>
> **Group 3:** Solid interior or plate types of various shapes … The element dimension of this group is about half wavelength, this leads to inter element spacing larger than half wavelength, this increases the sensitivity to the incident angle and causes early onset of grating lobes. This group is used for a certain purpose application.
>
> **Group 4:** Combination elements. This group constructed by a combination of other types and it is the biggest one.
>
> — [Elzwawi, INRS thesis, pp. 8–9](https://espace.inrs.ca/id/eprint/12049/1/Elzwawi,%20Ghada%20Hussain.pdf), citing B. A. Munk, *Frequency Selective Surfaces Theory and Design*, Wiley, 2000

Provenance: **LITERATURE-SUPPORTED (secondary source faithfully citing the primary; the primary itself is unreachable here).**

### The boundary #131 asked about

**The partition is by shape. The description of each partition is by response.** Groups 1–3 are geometry classes — centre-connected, closed loop, solid plate — and Group 4 is "combinations", which is a geometric statement too. But every group is *characterised* by three response properties:

| Group | Resonant size | Bandwidth | Angular stability | Grating-lobe onset |
|---|---|---|---|---|
| 1 — centre-connected / N-pole | ~λ/2 | moderate; improves as spacing tightens | (not stated) | pushed higher by tighter spacing |
| 2 — loops | ~λ (circumference) | broad — "most recommended" for stop- and band-pass | **stable with incidence angle** | small element ⇒ late onset |
| 3 — solid plate | ~λ/2 dimension | (not stated) | **sensitive to incidence angle** | **early onset** — spacing forced above λ/2 |
| 4 — combinations | — | tailorable | — | — |

This is the useful part for #130. The taxonomy says: **which shape family you pick determines your bandwidth, your angular stability, and how tightly you can pack — before any dimension is chosen.** A loop is a fundamentally better-behaved letter than a patch of the same resonant frequency, because a loop resonates on its *perimeter* and so is physically smaller for the same frequency, which lets you space the cells closer, which pushes the grating lobes (unwanted extra beams) out of band and keeps the response steady as the wave arrives off-axis.

### Read-across to #130's alphabet organisation

- **Organise the alphabet by shape family, and make the response properties attributes of the family, not of each letter.** That is what the field does, and it is the cheaper structure: a family-level statement ("loops are angularly stable") prunes candidates before any letter is characterised.
- **Group 3 is a warning for the patent's aperture examples.** Solid patches force inter-element spacing above λ/2, which brings early grating lobes and incidence-angle sensitivity. If a Tier B family's alphabet is patch-based, angular stability must be checked, not assumed.
- The four groups are a **shape vocabulary the repo can adopt directly** rather than inventing names for element classes.

---

## 3. Coding metasurfaces — citation VERIFIED; coupling is NOT addressed; super-cell sizing answers a different question

### Citation status: **VERIFIED**

Cui, Qi, Wan, Zhao & Cheng, "Coding metamaterials, digital metamaterials and programmable metamaterials". The **arXiv preprint (arXiv:1407.8442) was retrieved and read in full**, author list and content confirmed. The journal record — *Light: Science & Applications* **3**, e218, published online 24 October 2014 — is confirmed by [the Nature LSA article page](https://www.nature.com/articles/lsa201499) metadata and the [NASA ADS record](https://ui.adsabs.harvard.edu/abs/2014LSA.....3.e218C/abstract). The article body itself sits behind an idp.nature.com redirect and could not be fetched; **the arXiv preprint stands in for it and its content is what is quoted below.**

### The scheme

- **1-bit:** two cells, phase responses 0 and π, coded "0" and "1".
- **2-bit:** four cells at 0, π/2, π, 3π/2, coded "00", "01", "10", "11".
- **Realisation:** square metallic patches on a dielectric board. For the 2-bit case, patch side **w = 5, 4.68, 4.4 and 3.6 mm** gives "00"/"01"/"10"/"11" respectively — one shape, four sizes, four letters.
- **Evaluation is arithmetic, not a solve.** The far field is an array-factor sum over lattices, each carrying its own phase φ(m,n) ∈ {0, 180°} and a shared per-lattice pattern function f_e(θ,φ). The directivity expression eliminates f_e entirely. **This is precisely #130's "superposing known responses" fast tier, published and experimentally validated.**

### (a) Mutual coupling between unlike neighbours: **the paper does not address it at all**

A full-text search of the retrieved preprint for "coupling" returns **no discussion of mutual coupling between adjacent unlike cells**. The far-field model assumes each lattice radiates independently with its designed phase. Provenance of this negative finding: **retrieved primary source, exhaustive term search.**

The convention the ticket hoped to inherit does not exist in the founding paper. What *does* exist, elsewhere and stated bluntly:

> "the response of these individual elements is typically characterized within an infinite lattice of identical elements. Due to coupling effects, the response may shift when placed in a super-lattice of non-identical elements."
>
> "In simulating each individual cell, periodic boundary conditions were used, which fully accounts for coupling between identical neighbors. However, once the cells are placed next to non-identical neighbors, the coupling coefficient will change, and the electromagnetic response of each cell will shift from its designed value. **To mitigate this frequency shift, we perform a numerical optimization of the entire supercell.**"
>
> — [arXiv:1812.04725](https://arxiv.org/abs/1812.04725), §I and §III

That is #130's catch, named by the field, with a stated remedy: **re-solve the block.** The same paper reports the consequence: supercell efficiency "is generally lower than that of the individual cells", with the optimum frequency shifted away from design, and recovers it only by full-wave optimisation of the assembled block. Provenance: **SIMULATED (their work), LITERATURE-SUPPORTED (for us).**

### (b) Super-cell sizing: the field's rule answers a *different* question

Every block size found in the retrieved literature was set by something other than coupling error:

| Source | Block | What set the size |
|---|---|---|
| [Cui et al. 2014](https://arxiv.org/abs/1407.8442), RCS experiment | 8×8 lattices, lattice pitch **D = 35 mm**, **7×7 identical elements per lattice** (element pitch 5 mm) | The optimised code tables are computed with **D fixed to λ**; D also sets the scattering angles via sin θ ∝ λ/D. **Beam geometry, not coupling.** |
| [Cui et al. 2014](https://arxiv.org/abs/1407.8442), programmable demonstrator | 30×30 cells, **every five adjacent columns share one control voltage** | **Control-line count.** |
| [Hum & Perruisseau-Carrier, arXiv:1308.4593](https://arxiv.org/abs/1308.4593), §II | Reflectarray cells "gathered by pairs", 122 sub-arrays in a full demonstrator | **Cost and control complexity**, "without significant reduction in the performance". |
| [arXiv:1812.04725](https://arxiv.org/abs/1812.04725), §II | **4 cells per supercell** (90° step), giving ~91 µm cells at 55° and ~80 µm at 70° | "largely determined by **fabrication constraints**, since meta-atoms with large dimensions are more tolerant to errors in fabrication, but a higher number of cells better approximates the continuous impedance functions". |
| [Liu, Kwon & Tretyakov, arXiv:2202.09029](https://arxiv.org/abs/2202.09029) | Period **D = λ/sin θ** containing N elements | **Diffraction-grating geometry** — the period is chosen so a harmonic lands in the wanted direction. |

**Conclusion:** the field sizes super-cells by beam geometry, control-line budget, or fabrication tolerance — never by a coupling-error budget. **#130's proposed rule ("larger blocks mean less coupling error and coarser spatial control; that trade needs a stated rule") has no published rule to adopt.**

### One genuinely adoptable convention: the robustness band

Cui et al. do publish something #130 can use directly:

> "the optimized codes are approximately valid when the phase difference between '0' and '1' elements is apart from 180° … For all cases, **when the phase difference varies from 145° to 215°, at least 10-dB RCS reduction is guaranteed.**"

and

> "the RCS reduction remains nearly invariant when the lattice dimension **D changes from 0.6λ to 3.0λ**."

Plain English: the two tile types are supposed to differ by exactly half a wavelength of phase (180°), which is impossible to hold across a band; the paper measures how far off you can drift before the 10 dB target breaks, and the answer is **±35°**. And it measures how far the block size can wander before the result degrades, and the answer is **a factor of five**. Their own 8×8 prototype records a real deviation — "at 10 GHz, the small peak (below −10 dB) in the direction of incident wave is caused by the relatively large phase difference (about 203°)".

That is a **published acceptance band around a nominal, with a threshold checked against the edge** — structurally exactly #130's proposal, one level up. It is a *system-level* band on the code's phase contrast, not a *letter-level* band on each element's response. See §6.

---

## 4. Closed-form equivalent-circuit models — HIGHEST VALUE, and the news is mixed

This is the item that could replace Maxwell-Garnett as #111's fast tier. #111 flags Maxwell-Garnett as a poor fit because it assumes small, dilute, non-interacting inclusions, and a resonant printed metamaterial is none of those. The models below make **no such assumption** — they are derived *for* dense, strongly interacting periodic metal arrays, which is exactly the regime in play.

### 4a. Verified: patch arrays and strip grids, on a substrate, at oblique incidence

**Source: [Luukkonen, Simovski, Granet, Goussetis, Lioubtchenko, Räisänen & Tretyakov, arXiv:0705.3548](https://arxiv.org/abs/0705.3548), published as IEEE T-AP 56(6):1624–1632, June 2008. Full text retrieved and read.**

The model, verbatim from the source:

- **Grid parameter** (the one number that carries the geometry):
  α = (k_eff·D / π) · ln[ 1 / sin(πw / 2D) ]
  where **D** is the period, **w** the strip width, **k_eff = k₀√ε_eff** the wavenumber in the effective host medium. For w ≪ D the logarithm reduces to ln(2D/πw).
- **Substrate loading** is handled by a single averaging step: a grid printed on the surface of a substrate of relative permittivity ε_r behaves as if immersed in a uniform medium of
  **ε_eff = (ε_r + 1) / 2**
  — the arithmetic mean of substrate and air. Plain English: half the tile's electric field lives in the board and half in the air above it, so it "feels" the average.
- **Grid impedances**, TE and TM, for an inductive strip mesh:
  Z_g^TM = j (η_eff / 2α) · [1 − (k₀²/k_eff²)·(sin²θ / 2)] ,  Z_g^TE = j η_eff / 2α
- **Patch arrays** come from these by the approximate Babinet principle, Z_g^TE · Z_g'^TM = η_eff²/4, giving
  Z_g'^TM = −j η_eff / 2α ,  Z_g'^TE = −j η_eff / { 2α [1 − (k₀²/k_eff²)(sin²θ / 2)] }
  The minus sign is the whole point: a mesh of connected strips is **inductive**; its complement, an array of isolated patches, is **capacitive**.
- **A high-impedance surface** — patches over a grounded slab, which is the reflectarray/absorber topology — is the grid impedance in parallel with the grounded-slab impedance Z_s = jωµ·tan(βd)/β, giving closed-form input impedances (their Eqs. 20, 21, 23) and hence a **closed-form reflection phase**.

**Stated accuracy and its limits:**

| Limit | What the source says |
|---|---|
| Density | Grid parameter derived for an **electrically dense** array, k_eff·D ≪ 2π |
| Feature ratio | Derivation restricted to **w ≪ D** (strip width much smaller than the gap) |
| Verification | Compared against **HFSS, a Fourier modal method, and MoM**. "The agreement between the analytical and numerical results is very good for all angles of incidence." HFSS at 0° and 60° showed "excellent agreement" |
| Angle | "very accurate for **all angles of incidence up to nearly grazing incidence**" |
| Frequency ceiling | For their worked example (**D = 2 mm, w = 0.2 mm, d = 1 mm, ε_r = 10.2**): "For frequencies higher than **20 GHz** the HIS with the chosen parameters cannot be homogenized and we cannot expect our model to be adequate in this range." |
| Higher resonances | "we cannot predict higher-order surface impedance resonances with our model" — **first resonance only** |
| Losses | Substrate loss enters by making ε_r complex, but "the effect of losses have been considered to be out of the scope of this paper" — **loss handling is stated but not validated there** |

**What that ceiling means in X-band, for this repo** (provenance: **CALCULATED**, from the source's own stated example): their ceiling of 20 GHz with D = 2 mm and ε_eff = (10.2+1)/2 = 5.6 corresponds to a period of about **λ_eff/3.2**, i.e. the model holds while the cell period is under roughly a third of a wavelength *inside the effective medium*. Translating to a printed X-band skin at 10 GHz on a substrate of ε_r ≈ 3 (ε_eff = 2, λ_eff ≈ 21 mm), the model would be expected to hold for **cell periods up to roughly 7 mm**. That covers the sub-wavelength cell sizes the patent's examples use. **This is an extrapolation from one worked example, not a validated bound — treat as CALCULATED / INFERRED and confirm against one Floquet solve before relying on it.**

### 4b. Verified: the absorber topology — directly Example 3's problem

**Source: [Costa, Genovesi, Monorchio & Manara, arXiv:1211.1902](https://arxiv.org/abs/1211.1902) (IEEE-copyright author copy of "A Circuit-based Model for the Interpretation of Perfect Metamaterial Absorbers", IEEE T-AP). Full text retrieved.**

A "perfect metamaterial absorber" here is a metal pattern printed on a thin lossy grounded substrate — structurally the same family as the patent's Example 3. The model gives closed formulas for:

- **Grounded lossy slab impedance**, real and imaginary parts A and B, from ε_r', ε_r'', k₀ and thickness d.
- **FSS impedance** as a series LC, "or more simply by a single capacitor if the inductive component is low (e.g. patch element)".
- **Substrate loading of the capacitance:** C = C₀·[(1 + ε_r')/2 + j ε_r''/2] — the same (ε_r+1)/2 averaging — **valid only if the substrate is thicker than 0.3 D**, where D is the FSS periodicity.
- **Thin-spacer correction.** Below d = 0.3 D the ground plane's evanescent Floquet modes start to matter and the capacitance grows exponentially; an explicit correction C_thin = C₀ − (2ε₀D/π)·log(1 − e^(−4πd/D)) is given, and validated against MoM.
- **Two loss resistors:** a dielectric one R_D ≃ (1 + ε_r'/ε_r'')·(1/ωC₀) and an ohmic one R_O ≈ (2/δσ)(1/L)(D²) [as printed in the source]. **Directly relevant finding for a printed-ink skin:** "Ohmic losses can be neglected in microwave range since the resistor in (8) is generally one or two orders of magnitude lower than the dielectric resistor (7). **Conversely, if the metal is replaced by a resistive paint, the resistor assumes considerably higher values than the dielectric resistor.**" A printed MXene or thin silver trace is closer to "resistive paint" than to cladding copper — so for this repo's inks the **ohmic term may dominate, inverting the usual assumption.**
- **Stated limit:** "the model is of first order and it is valid **up to the first resonance**. The total resistance of the real structure tends to increase again as the second resonance is approached."
- **The escape hatch that makes this practical:** "The calculation of the unloaded capacitance can be accomplished by retrieving the reflection coefficient of a **full-wave simulation**. Alternatively, in case of a patch FSS, it can be calculated through the closed-form expression available in [35]" — where [35] is the Luukkonen model above.

### 4c. Verified: Marcuvitz — and its coverage is much narrower than the ticket assumed

**Source: Marcuvitz (ed.), *Waveguide Handbook*, MIT Radiation Laboratory Series vol. 10 (1951). A scanned full copy was retrieved at [introni.it](http://www.introni.it/pdf/10%20-%20Waveguide%20Handbook.pdf); title page and complete table of contents verified against the known work.**

The "Gratings and Arrays in Free Space" part of Chapter 5 contains **exactly four structures** (TOC, p. 280 ff.):

- §5.18 **Capacitive Strips** (strips with edges parallel to H)
- §5.19 **Inductive Strips** (strips with edges parallel to E)
- §5.20 **Capacitive Posts**
- §5.21 **Inductive Posts**
- (plus §5.22/§5.23, arrays of semi-infinite planes)

**There are no patches, no loops, no crosses, no Jerusalem crosses, no ring resonators.** The rest of the handbook's several hundred equivalent circuits are waveguide discontinuities — irises, posts, bends, junctions — not free-space periodic surfaces.

What is exemplary, and worth copying as a *discipline* rather than as content, is how each entry states its own validity. Verbatim from §5.18:

> **Restrictions.** — The equivalent circuit is valid for wavelengths and angles of incidence θ in the range **a(1 + sin θ)/λ < 1**. The quantity B/Y₀ has been computed by an integral equation method in which the first two diffraction modes are correctly treated to order λ². **Equation (1a) is estimated to be in error by less than 10 per cent** for the range of values plotted…

and from §5.19's numerical results:

> …an approximation for small apertures and **agrees with Eq. (1a) to within 10 per cent in the range d/a < 0.2, a/λ < 0.5, and θ < 0.5** [radians].

**Every entry in Marcuvitz publishes a stated error bound and the parameter box it holds over.** That is the single most transferable idea in this entire document for #130: a letter should carry its validity box and its error bound, not just its value. Provenance: **retrieved primary source** (formulas themselves are OCR-degraded in this scan and were not transcribed; the restrictions and accuracy statements above are legible and quoted verbatim).

### 4d. Stranded, but confirmed to exist

- **Tretyakov, *Analytical Modeling in Applied Electromagnetics* (Artech House, 2003).** **UNVERIFIED / STRANDED** — not reachable. However, the Luukkonen paper above is co-authored by Tretyakov and builds directly on the same averaged-boundary-condition machinery (attributed there to M. I. Kontorovich, 1950s), so the *method* the ticket wanted from that book is captured by a retrieved source.
- **Costa, Monorchio & Manara, "An Overview of Equivalent Circuit Modeling Techniques of Frequency Selective Surfaces and Metasurfaces", ACES Journal 29(12):960–976.** Citation and abstract **verified** from the [publisher record](https://journals.riverpublishers.com/index.php/ACES/article/view/10793); the PDF itself returned an HTML landing page rather than the file. Its abstract states the division that matters: **"dense non-resonant periodic surfaces (grids, patch arrays) can be analyzed using homogenization theory to derive inductor and capacitor values. For resonant elements or larger lattice periods, simple circuit methods can still apply with lumped parameters derived through preprocessing."** That is the boundary — **closed-form for non-resonant dense grids; full-wave preprocessing for resonant elements.** **STRANDED for detail; the boundary statement is LITERATURE-SUPPORTED from the abstract.**
- **Costa, Monorchio & Manara, IEEE Antennas & Propagation Magazine 54(4):36–48, 2012.** Citation confirmed via multiple secondary records; **full text STRANDED** (IEEE Xplore 403).

### 4e. What this means for #111's fast tier — the recommendation

**Closed-form equivalent-circuit models are a strictly better fast tier than Maxwell-Garnett for this problem, but they are not a drop-in replacement for a full element library.** Concretely:

| Shape | Closed-form L/C available? | Source |
|---|---|---|
| Square patch array (incl. on a substrate, oblique incidence, over a ground plane) | **Yes, validated** | Luukkonen et al. |
| Strip grid, inductive and capacitive | **Yes, validated** | Luukkonen et al.; Marcuvitz §5.18–5.19 |
| Post arrays | Yes (Marcuvitz §5.20–5.21) | Marcuvitz |
| Patterned FSS on a lossy grounded substrate (absorber stack) | **Yes for the stack**; the element's own C₀ needs a full-wave extraction unless it is a patch | Costa et al. |
| Loops, crosses, Jerusalem crosses, tripoles | **Not found** in any retrieved source | — |
| **I-shaped ring resonator over wire resonator (patent Example 3)** | **NO** | — |

**The architecture that follows:** a **hybrid tier**, not a pure analytic one.

1. **One Floquet solve per *shape*** to extract that shape's lumped C₀ (and L₀ where it is not negligible), as Costa et al. explicitly permit.
2. **Algebra thereafter** for every size, substrate, thickness, incidence angle and loss variation of that shape, via the transmission-line stack.
3. Cost model: **O(number of shapes) full-wave solves**, not O(number of letters). If the alphabet is 4 sizes × 3 shapes, that is 3 solves, not 12.

This is cheaper than characterising each letter separately, honest about where the approximation lives, and — unlike Maxwell-Garnett — derived for dense, interacting, resonant metal arrays rather than for dilute inclusions.

---

## 5. Ligature prior art — the pattern exists; the sizing rule does not

**Yes, the literature characterises blocks of elements as single units, and does so for #130's exact reason.**

The clearest statement of both problem and remedy is [arXiv:1812.04725](https://arxiv.org/abs/1812.04725), quoted in §3(a) above: individual cells are characterised in an infinite array of identical copies, that characterisation fails when neighbours differ, and the fix is **numerical optimisation of the entire supercell**. Their own results quantify the cost of *not* doing it: the assembled supercells were less efficient than their constituent cells and had drifted off the design frequency; block-level optimisation recovered the performance ("significantly improved in all cases"). They also note the cost of doing it: "this is computationally expensive when applied to the entire supercell."

They further show the failure is not only *between* cells but *within* one: their three-layer cell design used a transmission-line model that "includes only the influence of the fundamental Floquet harmonic, neglecting near-field interaction", and the assembled cell's transmission peak landed at **0.89 THz instead of the designed 1.0 THz** — an **11% frequency error** from near-field coupling alone, corrected only by re-optimising the assembled cell. Provenance: **SIMULATED (their work).** Plain English: modelling the layers as if they only talk to each other through the one "official" wave, and ignoring the fringing fields that leak directly between them, moved the resonance by more than a tenth of the design frequency.

### Block sizes actually used

| Block | Elements per block | Context |
|---|---|---|
| Cui et al. coding metasurface lattice | **7×7 identical elements**, 35 mm pitch, X-band | RCS reduction, 8×8 lattices |
| Cui et al. programmable demonstrator | **5 columns per control bit**, 30×30 cell array | FPGA-driven 1-bit surface |
| Hum & Perruisseau-Carrier (reviewing others) | **pairs** of reflectarray cells, 122 sub-arrays | Control-complexity reduction |
| THz Huygens/bianisotropic metasurface | **4 cells per supercell** (90° phase step) | Refraction at 55° and 70° |
| Liu, Kwon & Tretyakov | N elements in a period **D = λ/sin θ** | Diffraction-grating formulation |

**Range in practice: 2 to 49 elements per block.** No source justified its choice by a coupling-error budget. Provenance: **LITERATURE-SUPPORTED.**

### One structural warning for the alphabet

[Liu, Kwon & Tretyakov, arXiv:2202.09029](https://arxiv.org/abs/2202.09029) argue that the whole locally-periodic, phase-gradient design philosophy — which is what an alphabet-plus-placement *is* — has a ceiling:

> "phase-gradient reflectors (reactive impedance boundaries with a linearly-varying phase of the local reflection coefficient) have a **fundamentally limited efficiency**, which degrades when the desired performance significantly deviates from that of uniform mirrors or retroreflectors … because of excitation of parasitic propagating waves that scatter some part of the incident power into unwanted directions."

Plain English: when you ask a surface built from independently-designed tiles to send a wave somewhere far from where a plain mirror would send it, some power always leaks into directions you did not ask for, and no amount of tile-library refinement removes it — it is a property of the design *method*. The paper does not quantify the loss numerically in the retrieved text, so treat the magnitude as **UNKNOWN** and the direction as **LITERATURE-SUPPORTED**. This is a real bound on how good an alphabet-built design can be, and it bites hardest for the aperture-surface (Tier B) families that #130 targets.

---

## 6. Tolerance and sensitivity practice — the weakest prior art, and the biggest opening

**The question:** does an element library publish a nominal value, a range, or a sensitivity?

**The answer, from every source retrieved: a nominal curve.** Not a range, and not a published sensitivity.

Where tolerance appears at all, it appears in one of three forms, none of which is a band attached to a library entry:

**(a) A post-hoc perturbation study on one finished design.** The most explicit retrieved example: dimensions are varied by ±Δs and ±2Δs about nominal, where **Δs = 25 µm** is "a nominal laser resolution", and the resulting family of S₁₁ curves is inspected. The conclusion is a qualitative robustness verdict — "no specific resonator exhibits a significant effect due to manufacturing tolerances … the resonators at the ends are comparatively less sensitive" — followed by a check that the actual process beats the assumed spread ("the trimming tolerances are ≤30 µm, far below 2Δs"). ([Parellada-Serrano et al., arXiv:2307.07224](https://arxiv.org/abs/2307.07224), §III-A.) **This is a per-design study, run once, on the assembled structure. It does not travel with the element.**

**(b) A slope proxy, folded into the element's design objective.** Reflectarray element design explicitly optimises the *linearity* of the phase-vs-dimension curve. Ozturk & Saka define an error function Δ = Σₖ √|s_k² − s_k^i²| measuring the departure of the phase curve from "the line having constant slope which begins and ends at the same points with the phase curve", and minimise it alongside phase range and return loss ([arXiv:2009.12343](https://arxiv.org/abs/2009.12343), §III, Eq. 2 and Fig. 3). Plain English: a steep or kinked phase curve means a small etching error becomes a large phase error, so the field designs for a gentle, straight curve rather than publishing how sensitive the curve is. **Sensitivity is treated as something to design away, not something to record.**

The direction of the trade is well known — a slower phase slope buys bandwidth and tolerance immunity at the cost of phase range — but the retrieved sources state it qualitatively. A frequently repeated quantitative form (phase changing ~100° over ~0.6 mm of patch size against typical fabrication tolerances of 0.07–0.20 mm) surfaced only in search-result summaries of paywalled papers and is recorded here as **UNVERIFIED**.

**(c) A system-level acceptance band around a nominal.** Cui et al.'s **145°–215° phase-difference window for ≥10 dB RCS reduction** (§3 above) is the only retrieved example of a published band with a pass threshold checked against its edge. It is exactly the *shape* of #130's proposal — and it is applied to the *code's* phase contrast, not to any individual letter's response.

### Read-across to #130

- **The field's practice is: nominal curve in the library, tolerance study on the finished design.** #130's proposal inverts that — band in the library, and the requirement's threshold checked against the pessimistic edge before anything is assembled.
- **That inversion is not published anywhere found here.** It is also *better suited to this repo than to the literature's situation*, for a reason specific to #104: an etched copper laminate has a tolerance the fabricator can quote and hold. A direct-ink-write printed trace on a NOVA does not — the spread is a property of the ink, the nozzle, the substrate and the pass count, and this repo already has evidence that per-process spread is large (Kapton 500HN measuring tanδ 0.012 ± 0.004 against a ~0.002 datasheet figure, per #104). **The literature can get away with a nominal curve because its process is tight. This repo cannot.**
- **Cui's band is the precedent to cite and the shape to copy** — a stated window around nominal, with the pass criterion evaluated at the window's edge. Push it down one level, from the code to the letter.

---

## What has no prior art and must be derived

This is the point of the ticket. Eight items, each checked against every source retrieved above, ordered by how much work they represent.

### 1. A letter that carries a RESPONSE BAND rather than a curve — **NO PRIOR ART**
Every retrieved element library publishes a nominal response. Cui's 145°–215° window is a system-level band on the code contrast, not a letter-level band on an element. **Must derive:** how a band is constructed (from what spread, at what confidence), what "pessimistic edge" means for a complex reflection coefficient where magnitude and phase both vary, and how bands compose when letters are superposed. That last sub-question is the hard one and nothing in the literature touches it — the field superposes *nominal* responses.

### 2. A super-cell sizing rule derived from a coupling-error budget — **NO PRIOR ART**
Published block sizes range 2–49 elements and are set by scattering geometry, control-line count, or fabrication tolerance. The one paper that names the coupling problem fixes it by full-wave-optimising the block, which sidesteps sizing entirely. **Must derive:** the error-versus-block-size curve for *these* elements on *this* process, and the rule that reads a block size off it. This is a coupon/simulation campaign, not a literature lookup.

### 3. An error bar on the superposition fast tier — **NO PRIOR ART**
#111 asks what the fast tier gets wrong and by how much. The literature states the mechanism (coupling shifts when neighbours differ) and demonstrates consequences on individual designs (an 11% frequency shift within a cell; supercell efficiency below constituent-cell efficiency; #107's already-found result that Example 7's 10 dB backscatter bandwidth *falls* as the array grows). **Nobody publishes "superposition of independently characterised letters is accurate to ±X° of phase at block size N."** Must derive.

### 4. A per-letter MEASURED element library — **NO PRIOR ART**
Every library retrieved is **SIMULATED** — HFSS, CST, MoM, FDTD, Fourier modal method, all under Floquet/periodic boundaries. Measurement in this literature validates the **assembled article** (Cui's 8×8 prototype; Ozturk & Saka's 221-element array; the 20×20 FSS filter), never the individual letters. #130's proposal — print the symbols on coupons, measure them on the real machine with the real ink, and let every design inherit measured building blocks — is **without precedent in anything found here.** It is also the proposal's strongest single claim, precisely because nobody has done it.

### 5. Admission-by-printability ("a symbol enters the alphabet only after it has printed successfully") — **NO PRIOR ART**
The literature admits an element to a library when a simulation converges. Fabrication constraints enter as a downstream check (tolerance studies) or as a soft influence on cell count ("meta-atoms with large dimensions are more tolerant to errors in fabrication"). **The inversion #130 proposes — printability as an admission gate, making every alphabet-built design printable by construction — was not found anywhere.** Must derive: what "printed successfully" means as a pass/fail test, and who runs it.

### 6. A re-characterisation / invalidation policy — **NO PRIOR ART**
Published element libraries are implicitly bound to a named laminate (Rogers RO4003C, F4B, Rogers 5880) with no stated rule for what invalidates an entry. This repo's process variables — ink, substrate, cure schedule, pass count, ink age and MXene oxidation — have no analogue in etched-copper practice, so no analogue policy exists to copy. Must derive.

### 7. Closed-form models for the patent's actual element shapes — **NO PRIOR ART**
Verified closed forms cover strip gratings, square-patch arrays, and post arrays. **No closed form was found for the I-shaped ring resonator over wire resonator of Example 3, nor for loops, crosses or Jerusalem crosses.** Must derive — or, per §4e, sidestep by extracting one lumped C₀ per shape from a single Floquet solve and using the verified stack algebra thereafter. **The sidestep is strongly recommended over deriving new closed forms.**

### 8. A combinatorial optimiser over a discrete alphabet with a manufacturability guarantee — **PARTIAL PRIOR ART, insufficient**
Cui et al. publish optimised 1-bit code tables for N = 6…20 with achieved RCS reductions (−12.08 dB at N=6 rising to −23.58 dB at N=20), so the "search over discrete codes" problem is solved *for that objective*. What is absent: any optimiser that searches an alphabet whose letters carry **bands**, under a **printability admission constraint**, against a **threshold/objective** requirement of the kind #117 settled. The pieces exist; the combination does not.

### One thing #130 should stop worrying about
**Phase quantisation is not an open question.** The penalty from a finite alphabet is well characterised for beam-forming — reduced gain, raised sidelobes ([Hum & Perruisseau-Carrier, arXiv:1308.4593](https://arxiv.org/abs/1308.4593)) — and 1-bit surfaces are a deliberate, accepted engineering choice in large arrays, not a compromise. What is *not* characterised is the quantisation penalty for **absorption** and **backscatter reduction**, which is what #104 actually optimises. That specific gap belongs on the derive list too, but the general worry does not.

---

## What is stranded

Reported rather than guessed at, per the ticket's instruction.

| Source | Why unreachable | What is lost |
|---|---|---|
| Munk, *Frequency Selective Surfaces: Theory and Design*, Wiley 2000 | Textbook, no reachable full text | The primary statement of the four-group taxonomy, and Munk's own equivalent-circuit treatment. Classification recovered verbatim from a thesis that cites it |
| Tretyakov, *Analytical Modeling in Applied Electromagnetics*, Artech 2003 | Textbook | Its shape coverage for closed-form models. Partly compensated by the Tretyakov-co-authored arXiv:0705.3548 |
| Pozar & Metzler, *Electronics Letters*, April 1993 | IET Digital Library paywall | Primary confirmation that this paper introduced the phase-vs-patch-size design curve. Existence and role confirmed from Yang's citation slide |
| Costa, Monorchio & Manara, *IEEE APM* 54(4):36–48, 2012 | IEEE Xplore 403 | Detailed per-shape equivalent-circuit formulas |
| Costa, Monorchio & Manara, *ACES Journal* 29(12):960–976 | PDF link returned a landing page | Per-shape closed-form coverage. **Abstract retrieved**, and it states the key boundary (homogenisation for dense non-resonant grids; full-wave preprocessing for resonant elements) |
| Costanzo et al., "Modified Minkowski Fractal Unit Cell for Reflectarrays with Low Sensitivity to Mutual Coupling Effects", *IJAP* 2019 | Wiley returned 403 despite being open access | Quantified phase error from dissimilar neighbours under extended local periodicity — **this is the single most valuable stranded item for #130's coupling error bar**. Worth a manual retrieval |
| Cui et al., *Light: Sci. Appl.* 3, e218 (2014), journal version | nature.com redirects to an identity-provider endpoint | Nothing material — the arXiv preprint was retrieved in full and carries the same content, tables and appendix |
| MDPI, ScienceDirect, IEEE Xplore, incose.org generally | 403 to automated fetches, as the ticket warned | Several single-layer broadband reflectarray papers carrying the phase-range-versus-slope numbers |

---

## Provenance summary

| Claim class | Provenance |
|---|---|
| Reflectarray element-library practice; element shapes; phase-range limits and fixes | **LITERATURE-SUPPORTED** (retrieved open sources) |
| Pozar & Metzler 1993 as originator of the phase-vs-size curve | **UNVERIFIED** (secondary citation only) |
| Munk's four-group classification, verbatim text and per-group response properties | **LITERATURE-SUPPORTED**, secondary (thesis citing Munk); primary **STRANDED** |
| Cui et al. 2014 citation, coding scheme, lattice sizes, code tables, 145°–215° band | **LITERATURE-SUPPORTED** (arXiv preprint retrieved in full) |
| Cui et al. do not discuss mutual coupling between unlike neighbours | **LITERATURE-SUPPORTED** (negative finding from exhaustive term search of retrieved full text) |
| Luukkonen grid-impedance formulas, validity conditions, accuracy statements | **LITERATURE-SUPPORTED** (retrieved full text) |
| Costa absorber circuit model, thin-spacer correction, resistive-paint caveat | **LITERATURE-SUPPORTED** (retrieved author copy) |
| Marcuvitz free-space grating coverage (four structures only) and stated ≤10% error bounds | **LITERATURE-SUPPORTED** (retrieved scan; TOC and §5.18–5.19 restrictions read directly) |
| Luukkonen model holding to ~7 mm cell period at 10 GHz on ε_r ≈ 3 | **CALCULATED / INFERRED** — extrapolated from one worked example in the source; confirm against a Floquet solve |
| Published super-cell sizes and what set each of them | **LITERATURE-SUPPORTED** |
| Local-periodicity failure statement and supercell-optimisation remedy; 0.89 vs 1.0 THz shift | **LITERATURE-SUPPORTED** |
| Tolerance practice = nominal curve plus post-hoc perturbation study | **LITERATURE-SUPPORTED** (across all retrieved sources) |
| "Phase changes ~100° over 0.6 mm against 0.07–0.20 mm tolerances" | **UNVERIFIED** (search-result summary of a paywalled source) |
| Phase-gradient reflectors have a fundamental efficiency ceiling | **LITERATURE-SUPPORTED** for the direction; magnitude **UNKNOWN** |
| The eight "must be derived" items | **LITERATURE-SUPPORTED negative findings** — each checked against every source retrieved here; absence of prior art in *reachable* sources, not proof of absence in the field |

---

## Retrieved sources

1. T. J. Cui, M. Q. Qi, X. Wan, J. Zhao, Q. Cheng, "Coding Metamaterials, Digital Metamaterials and Programming Metamaterials", [arXiv:1407.8442](https://arxiv.org/abs/1407.8442) — published as *Light: Science & Applications* **3**, e218 (2014), 24 Oct 2014.
2. O. Luukkonen, C. Simovski, G. Granet, G. Goussetis, D. Lioubtchenko, A. V. Räisänen, S. A. Tretyakov, "Simple and Accurate Analytical Model of Planar Grids and High-Impedance Surfaces Comprising Metal Strips or Patches", [arXiv:0705.3548](https://arxiv.org/abs/0705.3548) — *IEEE Trans. Antennas Propag.* **56**(6):1624–1632, June 2008, DOI 10.1109/TAP.2008.923327.
3. F. Costa, S. Genovesi, A. Monorchio, G. Manara, "A Circuit-based Model for the Interpretation of Perfect Metamaterial Absorbers", [arXiv:1211.1902](https://arxiv.org/abs/1211.1902) — IEEE T-AP author copy.
4. N. Marcuvitz (ed.), *Waveguide Handbook*, MIT Radiation Laboratory Series vol. 10, McGraw-Hill 1951 — §5.18–5.23, pp. 280–295. [Scanned copy](http://www.introni.it/pdf/10%20-%20Waveguide%20Handbook.pdf).
5. S. V. Hum, J. Perruisseau-Carrier, "Reconfigurable Reflectarrays and Array Lenses for Dynamic Antenna Beam Control: A Review", [arXiv:1308.4593](https://arxiv.org/abs/1308.4593).
6. E. Ozturk, B. Saka, "Multilayer Minkowski Reflectarray Antenna with Improved Phase Performance", [arXiv:2009.12343](https://arxiv.org/abs/2009.12343).
7. M. A. Cole, A. Lamprianidis, I. V. Shadrivov, D. A. Powell, "Refraction efficiency of Huygens' and bianisotropic terahertz metasurfaces", [arXiv:1812.04725](https://arxiv.org/abs/1812.04725) — supercell design, near-field coupling, and the local-periodicity failure statement.
8. F. Liu, D.-H. Kwon, S. A. Tretyakov, "Reflectarrays and metasurface reflectors as diffraction gratings", [arXiv:2202.09029](https://arxiv.org/abs/2202.09029).
9. I. Parellada-Serrano, M. Pérez-Escribano, C. Molero, P. Padilla, V. de la Rubia, "Three-Dimensional Fully Metallic Dual Polarization Frequency Selective Surface Design Using Coupled-Resonator Circuit Information", [arXiv:2307.07224](https://arxiv.org/abs/2307.07224) — tolerance-analysis methodology.
10. G. H. Elzwawi, doctoral thesis, INRS — [open PDF](https://espace.inrs.ca/id/eprint/12049/1/Elzwawi,%20Ghada%20Hussain.pdf), pp. 8–9, reproducing and citing Munk's four-group FSS element classification.
11. F. Yang, "Progress in Reflectarray Antenna Research", EuCAP 2013 tutorial — [slides PDF](https://www.eucap2013.org/files/EuCap2013%20FanYang.pdf).
12. J. Ali, A. Ahmad, D.-y. Choi, "Single-Layer Metasurface-Based Reflectarray Antenna with H-Shaped Slotted Patch for X-Band Communication", *Nanomaterials* **14**(18):1495, 2024, DOI 10.3390/nano14181495 — [PMC11434495](https://pmc.ncbi.nlm.nih.gov/articles/PMC11434495/).
13. F. Costa, A. Monorchio, G. Manara, "An Overview of Equivalent Circuit Modeling Techniques of Frequency Selective Surfaces and Metasurfaces", *ACES Journal* **29**(12):960–976 — [publisher record](https://journals.riverpublishers.com/index.php/ACES/article/view/10793) (abstract retrieved; full PDF stranded).
