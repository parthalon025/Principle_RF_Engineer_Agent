# An AI-metasurface survey, read against all seven patent examples

**Date:** 2026-09-07
**Ticket:** part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104). Opened [#202](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/202) (§4's comparison, as a decision to take); commented onto [#184](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/184) (§5) and [#191](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/191) (§3, §7). Also bears on [#132](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/132) and [#168](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/168).
**Source:** M. H. Boulaich, S. Ohamouddou, M. A. Ennasar & A. El Afia, *"AI-Assisted Metasurface Antennas Design/Optimization and Performance Enhancement Techniques: A Comprehensive Survey,"* IEEE Access **14**, 29803–29836 (2026), [doi 10.1109/ACCESS.2026.3667812](https://doi.org/10.1109/ACCESS.2026.3667812). Open access, CC-BY. ENSIAS, Mohammed V University in Rabat.

**Provenance ceiling.** This is a **survey**. Almost every number below is a result the survey reports from someone else's paper, so it is `LITERATURE-SUPPORTED` *at one remove* — weaker than a first-hand reading, and no figure here should be relied on for a design decision without opening the cited paper. Where this document does arithmetic of its own it says so.

---

## Why read it against all seven

The obvious reading is "what does AI say about absorbers," because Example 3 is #104's anchor. That reading throws away most of the paper's value. The patent has **seven** examples doing seven different things to a wave, the survey covers most of those things, and the interesting findings only appear when the seven are lined up — the data-cost pattern in §3 and the phase-budget headroom in §4 are both invisible if you read only the absorber section.

---

## 1. The survey's organising split, and where our loop sits

Everything in the paper divides into two:

- **Forward design** — you have a geometry, you simulate it, you score it, you mutate and repeat. Genetic algorithms, PSO, ant colony.
- **Inverse design** — you state the response you want and a trained model returns a geometry. ML/DL.

*In plain terms: forward design is guess-and-check made smart about the guessing. Inverse design is asking a model that has seen thousands of worked examples to skip to the answer.*

**Our loop is forward design** and, per #191, currently forward design of the wrong variable — it still tunes patch length. Nothing in this survey changes that; it does price what inverse design would cost if we ever wanted it (§3).

---

## 2. The seven examples, and what the survey has for each

Example numbering and function per `docs/seven-example-design-unknowns.md` §4; tier per `CONTEXT.md`.

| # | Function | Tier | Survey coverage | The number it gives |
|---|---|---|---|---|
| **1** | Magnetic mirror / high-impedance surface | A | **almost none** — HIS named once, in passing, and not as an AI problem | — |
| **2** | Impedance match to free space | A | **oblique** — nearest analogue is electromagnetic **cloaking**, same "make the wave behave as if nothing is there" goal | Bayesian optimization driving an EM solver directly; **no large dataset** |
| **3** | Absorber *(our anchor)* | A | **extensive** — its own section plus Table 4 | ACDL reaches **94 %** prediction accuracy on **7,000 samples** for a 10-parameter absorber |
| **4** | Steered reflection (phase vs. hole radius) | B | **moderate** — inside the beam-steering and coding-metasurface material | — |
| **5** | Electrically tunable steering | B | **moderate** — the survey's "reconfigurable metasurface antennas" (PIN diodes, varactors, liquid crystals) | a Nyquist metasurface steering in two angular dimensions at **10 GHz** on standard PCB; an autoencoder setting element states from a far-field map in real time |
| **6** | Polarisation converter, LP↔CP | A | **extensive** — its own section | DC-GAN **90 %** but **0.2 dB / 4° error**; a DNN **92 %** generating a cell with no optimiser at all |
| **7** | Backscatter reduction (two-tile checkerboard) | B | **extensive, and previously missed** — the survey's "anisotropic digital coding metasurfaces" *are* this family | **70,000** training + **10,000** validation patterns → **90.5 %**, **2° phase error**, demonstrated on 1-bit dual- and triple-beam scattering |

**Example 7 is the find.** A search for "absorber" returns nothing on it; the field files it under *coding metasurface*, which is the vocabulary #130 already uses. Anyone searching this literature for our Example 7 work needs that word.

---

## 3. The data-cost pattern — and it matches our own tier split

Line the three quantified cases up by how much of the surface has to act together:

| What is being learned | Scope | Training set |
|---|---|---|
| Cloak parameters (≈ Example 2) | a few continuous parameters | **none** — Bayesian optimization queries the solver directly |
| Absorber cell (Example 3) | one cell, ~10 parameters | **7,000** |
| Coding pattern (Example 7) | an assignment across many cells | **80,000** |

**"An order of magnitude per step up in scope" — the mechanism this line gave is falsified; the primary source was retrieved and read.** The original wording read: *"An order of magnitude per step up in scope... teaching a model about one tile is far cheaper than teaching it about a whole quilt, because the quilt has vastly more distinct arrangements."* That explanation treats the 80,000 figure as the cost of learning *arrangements across an aperture*. It is not.

**Primary source:** C. Zhang, C. Zou, S. Guo, Y. Zhao & T. Shen, "Deep Learning-Based Inverse Design of Stochastic-Topology Metamaterials for Radar Cross Section Reduction," *Materials* **18**(21):4841 (2025). DOI [10.3390/ma18214841](https://doi.org/10.3390/ma18214841). Open access; **retrieved** ([PMC12609193](https://pmc.ncbi.nlm.nih.gov/articles/PMC12609193/)). Verbatim: *"The process was fully automated, generating a dataset of 70,000 samples. The full-wave simulation for each unit cell required approximately 1 min, amounting to a total computational time of around 70,000 min."* That is **~1,167 solver-hours** (~48.6 days serial), `CALCULATED` (70,000/60 = 1,166.7 h). Report it as **solver-hours, not CPU-hours** — no core count is given, and the solver is identified only as *"a time-domain solver"*, not by name.

**Every one of the 70,000 is a one-minute single-unit-cell periodic solve.** What is enumerated is single-cell **topologies**, not arrangements over an aperture: verbatim, *"the impedance layer structure is encoded using '1' and '0' to represent the presence or absence of the impedance film"* over a **40×40 binary encoding matrix, expanded to 80×80 under p4m symmetry**, with **unit cell period P = 8 mm** — each of the 70,000 samples is one such topology, solved with periodic boundary conditions, not one aperture-scale arrangement.

*In plain terms: the 70,000-solve, ~48.6-day training bill was not spent teaching a model every way a quilt of tiles could be arranged — it was spent teaching it every way one single tile's own internal pattern (a 40×40 grid of "metal here / no metal here" pixels) could look. The quilt itself, once the tile is learned, still only needs two tile types stitched into a hand-drawn chessboard.*

**Two consequences.** First, a five-figure Tier B corpus is far cheaper than the original "quilt" wording implies — it is not paying for combinatorial arrangements across a macroscopic surface, it is paying for combinatorial *topologies within one periodic cell*. Second, the lever that shrinks the bill is **constraining the geometry encoding** (a smaller binary matrix, a coarser symmetry group), not shrinking the array the pattern is later tiled across.

**State the causal limit honestly: "encoding dimensionality sets the bill" is the leading candidate, not established.** The 7,000-sample case (Example 3, above) is a ~10-parameter *discriminative* absorber surrogate that reaches this repo only through a secondary survey; the 70,000-sample case here is a *generative* CBAM-VAE + Transformer architecture targeting 100% relative bandwidth (>10 dB RCS reduction, 6–18 GHz). Model class and target bandwidth are **uncontrolled confounds** between the two data points — this is `n = 1` on each side, not a controlled comparison of encoding size against sample count.

**Settling the bookkeeping: two different papers, both near 70,000, must not be merged.** The 70,000-solver-hour figure above belongs to Zhang, Zou, Guo, Zhao & Shen (2025) — the source for the mechanism correction, above. The survey's own Example 7 entry — **"70,000 training + 10,000 validation patterns → 90.5%, 2° phase error"** — is a **different** paper: Q. Zhang, C. Liu, X. Wan, L. Zhang, S. Liu, Y. Yang & T. J. Cui, "Machine‐Learning Designs of Anisotropic Digital Coding Metasurfaces," *Advanced Theory and Simulations* **2**, 1800132 (2019). DOI [10.1002/adts.201800132](https://doi.org/10.1002/adts.201800132). Verified by search against the primary source: *"only 70,000 training coding patterns are used to train the network... another 10,000 randomly chosen coding patterns are employed to validate the neural network, showing an accuracy of 90.05% of phase responses with 2° error in the 360° phase"* — matching the survey's 90.5%/2° figures. **The two papers coincidentally share a "70,000" figure with different meanings (training-only for Zhang et al. 2025; training-plus-separate-10,000-validation for Zhang et al. 2019) and must not be merged into one number.**

**Device details for the map's "third geometry-representation shape,"** filling a gap the map previously left open, all from Zhang, Zou, Guo, Zhao & Shen (2025), verified directly against the retrieved paper: **8 mm unit cells**, **dual-layer F4B(T)M300 substrate** (`εr = 3.0`), **NiCr (Ticer TCR®) resistive film at 100 Ω/sq**, a **1-bit coding layout** — two learned unit-cell topologies arranged as **6×6-cell supercells**, tiled into an **8×8 chessboard of supercells**, for a **384 × 384 × 7 mm** fabricated panel — where the macroscopic chessboard arrangement is **hand-designed** (a conventional supercell/chessboard layout), **not learned**; only the individual unit-cell topology came from the trained model. **Measured in a compact antenna test range (CATR) chamber** over **6–18 GHz**, mounted on radar-transparent foam supports.

**Two adjacent leads noted but not read in this pass:** ACS Appl. Nano Mater., DOI [10.1021/acsanm.4c03822](https://doi.org/10.1021/acsanm.4c03822), and an iScience paper at [PMC13018978](https://pmc.ncbi.nlm.nih.gov/articles/PMC13018978/).

This lands exactly on #107's **Simulation tier** distinction, arrived at independently and from the opposite direction. Tier A is "the unit-cell solve is the answer"; Tier B is "the unit-cell solve only populates a lookup an aperture-level evaluation consumes." **Tier B is where the data bill explodes** — 80,000 versus 7,000 — which is a cost consequence of that split nobody had priced. That headline number stands; only the *reason* it explodes is corrected above — it is encoding-dimensionality cost, not aperture-arrangement cost.

**Consequence for #191 and #132.** Any proposal to put an ML surrogate inside OPTIMIZATION for a Tier B family carries a four-to-five-figure simulation bill *before* the first design. For a Tier A family it is four figures. Neither is free, and #111's fast tier (one Floquet solve per shape plus closed-form algebra) exists precisely so we do not have to pay it.

---

## 4. The headline: an ML surrogate's phase error is well inside our phase budget

`docs/supercell-sizing-rule.md` derives the phase error a backscatter-reduction requirement tolerates, `δ = 2·arcsin(10^(−RCSR_dB/20))`:

| Required reduction | 6 dB | 10 dB | 15 dB | 20 dB | 30 dB |
|---|---|---|---|---|---|
| **Phase budget** | 60.2° | **36.9°** | 20.5° | 11.5° | 3.6° |

**Correction: the "4° (DC-GAN)" figure does not belong to this family.** An earlier revision of this section read *"the survey's two reported phase errors for this family are 2° (coding metasurface, 80,000 samples) and 4° (DC-GAN)"* — treating both as Example 7 evidence. Checked against this document's own §2 table: the **4° / DC-GAN** figure is filed there under **Example 6, polarisation conversion** (*"DC-GAN 90% but 0.2 dB / 4° error"*), not Example 7. Polarisation conversion and backscatter reduction are different families answering different questions — a 4° error in a polarisation converter's own target (an axial-ratio or differential-phase figure for LP↔CP conversion) is not the same physical quantity as a 2° error in a coding metasurface's predicted two-cell reflection-phase difference, which is what the ±37° criterion in the table above actually governs. **Only the 2° figure genuinely belongs to Example 7's phase budget.**

Compared (`CALCULATED` here, from the survey's figures and the repo's own budget), with the 4° figure kept for reference only — it remains informative about ML surrogate accuracy generally, but it is Example 6's number, not this family's:

| | 6 dB | 10 dB | 15 dB | 20 dB | 30 dB |
|---|---|---|---|---|---|
| **2° error (Example 7, this family)** | ✓ 30× margin | ✓ 18× | ✓ 10× | ✓ 5.8× | ✓ 1.8× |
| **4° error (Example 6 — reference only, not this family)** | ✓ 15× | ✓ 9.2× | ✓ 5.1× | ✓ 2.9× | ✗ over budget |

**So for Example 7 an ML phase surrogate is not marginal — on its own 2° figure, it has one to two orders of magnitude of headroom at ordinary reduction levels**, comfortably clear even at 30 dB. Independently, the same comparison is a sanity check on the literature: a claimed 2° surrogate error is a strong claim, and it is strong *in the units our requirement is written in*.

**Two cautions before this is used.** The 180 ± 37° criterion is `LITERATURE-SUPPORTED` from Haji-Ahmadi *et al.* (2017), and `docs/seven-example-design-unknowns.md` §7 records that its full text was not fetched. And the survey's 2° figure's primary source has now been **identified** — Zhang, Liu, Wan, Zhang, Liu, Yang & Cui, *Advanced Theory and Simulations* **2**, 1800132 (2019), §3 above — and its 90.05%/2° headline corroborated via independent search results quoting the paper directly, but the full paper itself is Wiley-paywalled (HTTP 403 to automated fetch from this environment) and has **not** been read first-hand. This comparison is a reason to open that paper, not a substitute for opening it.

---

## 5. Direct corroboration for #184

[#184](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/184) asks whether `optimization/bayesian.py`'s existing Gaussian-process/Expected-Improvement machinery should be repointed from a cheap closed-form objective at the genuinely expensive full-wave one, noting that "EGO's actual payoff (minimizing costly evaluations) is banked, not realized, until it's pointed at something expensive."

The survey's cloak result is that architecture, already working: Qin *et al.* use **Bayesian optimization in combination with an electromagnetic solver** to find conformal mantle-cloak parameters — and, uniquely among the quantified cases here, with **no training corpus at all**. That is the point of BO: it is sample-efficient because it chooses each next evaluation from what the previous ones taught it.

The survey also states the honest cost, which #184 should carry: *"the integration of BO with electromagnetic simulations presents a significant computational challenge for real-time or large-scale applications,"* with Gaussian-process or NN surrogates named as the mitigation. So the answer BO gives is "fewer expensive evaluations," never "cheap."

The survey's third and final recommendation is the same architecture stated generally — *"hybrid frameworks in which AI models interact dynamically with full-wave solvers to accelerate optimization while maintaining physical accuracy"* — which is #111's two-tier plan from the outside. Its second recommendation, *"physical laws were integrated into AI models to improve interpretability,"* is what `rf_tools/physical_bounds.py` now provides: a hard physics gate in front of any search.

---

## 6. What the survey covers that is not an antenna

The paper's title says antennas and much of it is: gain, directivity, radiation pattern. Those are the `PATCH` family's quantities, governed by a radiation-Q bound, and importing them into an absorber problem is the exact category error `docs/patch-q-factor-bound-primary-source.md` documents.

But a large part is not antennas at all, and that is the part we can use: **frequency-selective surfaces** (§IV.A), **absorbers** (§IV.B), **polarisers** (§IV.C), **cloaks**, and **coding metasurfaces**. Flat lenses, holograms, vortex plates, beam splitters and reflectionless refractors are named without treatment.

Its own FSS contribution is a forward design: a constrained multi-objective GA (population fixed at 10) driving CST, reaching **S₂₁ = −42 dB** at 10 GHz as a bandstop. Its inverse design compares seven classifiers on precision/recall/F1 — **Random Forest best**, ahead of MLP, SVM, decision tree, K-NN, gradient boosting and logistic regression.

---

## 7. Two warnings the survey gives, and our answers

**Non-uniqueness, and it is structural.** From its Challenges section: inverse design *"faces significant challenges owing to the complex, non-unique relationship between the structure and electromagnetic response, where multiple geometries can yield similar responses."* Many shapes give one response, so "predict the shape from the response" is ill-posed. **This is not a data-volume problem** and cannot be spent away — which is a reason to prefer forward search with a cheap surrogate (#111) over inverse design, independent of cost.

**A shot at our alphabet, which we should answer before someone else quotes it.** Criticising Guoqing *et al.*, the survey writes that the method *"does not perform a true full inverse design because it **selects meta-atoms from an existing library**, rather than exploring broader design spaces."*

That describes #130's symbol alphabet. **The critique does not transfer, and the reason should be on the record:** the survey treats library restriction as a shortcut taken for tractability, whereas ours is a hard admission gate — every letter must be printability-admitted on a real machine with a real feature floor (#115), and a geometry outside it is not a design we declined to explore, it is a design that cannot be fabricated. The survey's own Challenges section concedes the gap from the other side, listing fabrication as unsolved: *"high-precision large-area metasurface fabrication remains difficult owing to the trade-offs between resolution, cost, and scalability."* On that axis this programme is ahead of the surveyed field, not behind it.

**A metric critique worth carrying to #168.** On Vijay *et al.*: *"predicting an FSS unit-cell image is not a standard classification problem; accuracy is an inadequate metric compared with intersection over union (IoU), structural similarity index (SSIM), and mean squared error."* [#168](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/168) specs Feature Selective Validation for the Example 3 reproduction check, and this is the same concern in a different field: a single scalar score over two curves hides *where* they disagree. Corroboration for FSV's premise, from outside the EMC literature FSV comes from.

---

## 8. What this does not support

- **It is not evidence for any of our numbers.** No result here was reproduced, and the survey reports rather than derives.
- **It says nothing about Example 1.** The magnetic-mirror / high-impedance-surface family is effectively absent, so "AI has been applied across the metasurface field" is not true uniformly across our seven.
- **It does not make inverse design available to us.** §3 is a price list, not a purchase. We have no full-wave tier wired in and therefore no way to generate the corpus any of these results assumes.
- **Its own contributions are `PATCH`-family.** CSRR-loaded microstrip patch antennas at 2.4/3.6/5.2 GHz — a different family with a different bound from our skin.

---

## 9. Where this went

| Finding | Landed on |
|---|---|
| §4 — an ML phase surrogate's error sits inside Example 7's phase budget, but its corpus costs 80,000 solves | **[#202](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/202)**, opened as a decision ticket: is it admissible, and at which reduction levels? |
| §5 — Bayesian optimization driving an EM solver, with no corpus, plus the survey's own statement of its cost | commented onto [#184](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/184) |
| §3 — the data-cost ladder, and its match to #107's Tier A/B split | commented onto [#191](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/191) |
| §7 — non-uniqueness makes inverse design ill-posed, not merely expensive | commented onto [#191](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/191) |
| §7 — the metric critique (a scalar score hides *where* two curves disagree) | corroborates [#168](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/168)'s premise for FSV; no ticket opened, the premise was already settled |
| §7 — our answer to the library-restriction critique | recorded here, so it exists before the critique is quoted at us |

**No ADR.** Per #104's standing preference, a *finding about the world* goes to `docs/`, `CONTEXT.md` and `RUNNING-LISTS.md`; an ADR is for a choice that constrains future work. Nothing here decides anything — #202 is where the deciding happens.
