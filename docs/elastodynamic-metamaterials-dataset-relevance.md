# Does the UCI "2D Elastodynamic Metamaterials" dataset help this program?

**Date:** 2026-09-10
**Trigger:** unsolicited research request to evaluate a candidate external dataset — [UCI ML Repository, dataset 692](https://archive.ics.uci.edu/dataset/692/2d+elastodynamic+metamaterials) — against this program's use of ML for pixel-bitmap inverse design (CLAUDE.md: *"Symbol placement, continuous dimensions, pixel bitmaps, ML inverse design — the method is chosen per requirement and the choice recorded with its reason"*).
**Scope:** the UCI dataset page, its source paper, and that paper's code repository. No ticket opened yet — this is a scouting note, not a decision record.

---

## Bottom line up front

**This dataset cannot be used as training or validation data for this program's RF/electromagnetic surface designs, and the primary sources confirm rather than complicate that.** It is built entirely from the *elastodynamic wave equation* for mechanical vibration in a polymer/steel composite — a different physical regime, different governing equation, and (most importantly for any quantitative reuse) frequencies and wave speeds that are roughly **five to six orders of magnitude** away from anything relevant to an RF surface. No band-gap number, geometry-to-property mapping, or trained model weight in this dataset carries any numeric meaning for a radio-frequency structure. The paper itself never mentions electromagnetics, photonics, or Maxwell's equations at all (verified by full-text search of the retrieved paper, §2 below) — this is not a case where the authors drew a bridge we're declining to use; there is no bridge stated in the source.

**What does transfer, and only as a pattern, not as data:** the paper's *method* — encode a unit cell as a binary pixel bitmap, exploit the cell's geometric symmetry to shrink the design space, train an interpretable model (not a black-box network) to map bitmap → target property, and report the result as human-readable rules rather than only a prediction — is a clean, documented example of exactly one of the design methods this program's charter already names as legitimate ("pixel bitmaps, ML inverse design"). It is worth keeping as a methodology reference for whoever eventually builds an analogous RF pixel-bitmap tool, and only once this program has its own measured RF unit-cell data to train on — this dataset can never substitute for that, because ADR-0027 admits a letter to the element library only after it is printed and measured, and nothing in this dataset was printed or measured on an RF part.

This confirms the framing given at the start of this task; nothing in the primary sources contradicts it.

---

## 1. What's actually in the dataset — verified against the UCI page and the source paper

### 1.1 The UCI dataset page itself

Retrieved from [archive.ics.uci.edu/dataset/692](https://archive.ics.uci.edu/dataset/692/2d+elastodynamic+metamaterials):

- **One input feature**, named `CondensedBinary2DGeometry`: an integer-typed field holding a **binary number encoding 15 pixel constituents** of a stated "10×10 pixel" unit-cell design space.
- **Two continuous targets**: `BandGapLocation` (Hz) and `BandGapWidth` (Hz).
- **20,521 instances**, no missing values, associated ML task labelled **Regression**, subject area **Engineering**, distributed as a 717.6 KB CSV.
- **Formal citation**: Ogren et al. (2021), UCI Machine Learning Repository, DOI [10.24432/C5ZS5D](https://doi.org/10.24432/C5ZS5D). Creators listed: Alexander Ogren, Zhi Chen, L. Catherine Brinson (Duke), Mary Bastawrous (University of Colorado), Cynthia Rudin (Duke), Chiara Daraio (Caltech). Licensed CC BY 4.0.
- **Funding**: DOE grant **DE-SC0021358** (confirms the background brief).
- **Introductory paper named on the page**: "How to See Hidden Patterns in Metamaterials with Interpretable Machine Learning," Chen, Ogren, Daraio, Brinson & Rudin.

**What the UCI page does *not* explain:** how the 15 "irreducible" pixels map onto the stated 10×10 grid, or what symmetry is being exploited. That detail is absent from the dataset page and had to be pulled from the paper (§1.2).

### 1.2 The source paper

The paper is on arXiv as [arXiv:2111.05949](https://arxiv.org/abs/2111.05949) ("How to See Hidden Patterns in Metamaterials with Interpretable Machine Learning," Chen, Ogren, Daraio, Brinson, Rudin) and was subsequently peer-reviewed and published as **Chen et al., *Extreme Mechanics Letters* 57, 101895 (2022), DOI [10.1016/j.eml.2022.101895](https://doi.org/10.1016/j.eml.2022.101895)** — the published venue and DOI were confirmed via the paper's own PDF hosted by the Daraio Research Group at Caltech ([daraio.caltech.edu/publications/Chen_et_al_EMS_2022.pdf](https://www.daraio.caltech.edu/publications/Chen_et_al_EMS_2022.pdf)) and corroborated by Duke's Scholars@Duke publication record. The arXiv preprint's technical content — read via the arXiv HTML rendering at [ar5iv.labs.arxiv.org/html/2111.05949](https://ar5iv.labs.arxiv.org/html/2111.05949) — is what the quotes below are drawn from; it is the authors' own primary-source text, not a secondary write-up.

**The symmetry that turns a 10×10 grid into 15 numbers.** The paper states the unit cell has **"four axes of symmetry (x, y and ±45°)"**, and that as a result **"the coarsest resolution (10×10) unit-cell has only 15 irreducible pixels."** The raw feature vector fed to the models is a **"15-dimensional binary vector: 0 means the soft constituent material in that location, and 1 means stiff constituent material."** *Plain-language reading: a 10×10 cell (100 squares) would need 2¹⁰⁰ possible patterns to describe in full, an astronomically large number. But this design is forced to be symmetric across a vertical line, a horizontal line, and both diagonals — mirror it four ways and it must look the same — so only one eighth-wedge of the grid (15 independent squares) is free to vary; the rest is filled in by reflection. That collapses the design space to 2¹⁵ = 32,768 distinct unit cells,* which the paper states explicitly: **"the full coarse space can be characterized, having 2¹⁵ total states."** The 20,521 instances in the UCI CSV are consistent with this — they are a subset of those 32,768 possible 15-bit patterns (my inference: the paper does not itself state how many of the 32,768 states exhibit a band gap, so I cannot confirm the exact gap between 32,768 and 20,521 from the retrieved text — most plausibly the UCI file keeps only the states that produced a detectable band gap, since a design with no forbidden frequency band would have nothing to put in `BandGapLocation`/`BandGapWidth`, but this specific reconciliation is my assessment, not a quoted fact).

**How the data was generated (simulation method).** The paper solves the **"harmonic elastic wave equation … with Bloch-Floquet periodic boundary conditions"** using **"the Finite Element method using bilinear quadrilateral elements,"** implemented in an in-house MATLAB solver, with **COMSOL Multiphysics** used separately to validate finite-tile (as opposed to infinite-periodic) behaviour. The periodicity condition is stated in Bloch form, u(x + a_n) = u(x)·e^(−i·γ·a_n) — plain-language reading: rather than modelling an infinite sheet of repeating tiles directly, the solver models one tile and tells the mathematics that whatever happens at one edge must reappear at the opposite edge with a phase shift, which is the standard trick (also used in this program's own EM unit-cell work, see `docs/element-library-prior-art.md` §1) for turning an infinite periodic problem into a single-cell calculation.

**Wave regime.** In-plane 2D elastic waves — the paper states displacements are **"confined to the same 2-D plane that contains the metamaterial."** This is neither a purely longitudinal (pressure) nor purely shear wave in isolation; it is the coupled in-plane elastodynamic problem, which is the standard regime for 2D phononic-crystal band-gap work.

**Material properties.** Two constituent materials, explicitly given as mechanical (not electromagnetic) properties:
- **"soft and lightweight, with elastic modulus E = 2 GPa and density ρ = 1,000 kg/m³"** — described as representing a polymer.
- **"stiff and heavy with E = 200 GPa, and ρ = 8,000 kg/m³"** — described as representing steel.

No electrical permittivity, permeability, or conductivity is given anywhere in the paper, because none is needed for an elastic-wave calculation — a fact worth stating plainly since it is the crux of §2's non-transferability finding.

**Geometry and frequency scale.** The unit cell is **"a square with side length a = 0.1 m"** (10 cm), and the paper's primary experiments sweep **"five frequency ranges ([0, 10], [10, 20], [20, 30], [30, 40] and [40, 50] kHz)"** — i.e. band gaps are sought and reported somewhere within 0–50 kHz, audio-to-ultrasonic range, not RF.

---

## 2. Physical regime comparison — elastodynamics vs. electromagnetics, and whether any legitimate bridge exists

### 2.1 What governs each

- **This dataset:** the elastic wave equation (the elastodynamic/Navier-Cauchy equation) for a linear elastic solid, governing mechanical displacement u(x,t) under the material's stiffness (Young's modulus, here isotropic and stated only as a scalar E per constituent) and density. This is the equation the paper solves, per §1.2 above.
- **This program:** Maxwell's equations, governing the electric and magnetic fields E and H, with the surface's behaviour set by permittivity, permeability, and conductivity rather than stiffness and density. This is asserted here as domain-standard physics, not sourced to the paper — the paper never engages with electromagnetics at all (see below).

**These are different equations, of different physical fields, driven by different material properties.** A "stiff" pixel in this dataset (steel, E = 200 GPa) has nothing to do with a "conductive" or "high-permittivity" pixel in an RF unit cell; there is no unit conversion between elastic modulus and permittivity, because they describe unrelated physical responses.

### 2.2 Frequency and wave-speed scale — the number that rules out any numeric reuse

Elastic (sound/vibration) waves in the solids this dataset uses travel at speeds set by √(E/ρ): order **1,000–5,000 m/s** for typical polymers and metals (a plain consequence of the E and ρ values the paper states, §1.2 — this specific comparison is my calculation from the paper's own stated properties, not a number the paper itself computes). Electromagnetic waves travel at the speed of light, **≈3×10⁸ m/s**, roughly **100,000× faster**. Because a Bloch/Bragg band gap sits at a frequency set by (wave speed) / (unit-cell size), the same geometric unit cell that produces a mechanical band gap at kilohertz frequencies would, if you naively swapped in electromagnetic wave speeds, produce a photonic band gap in the hundreds-of-gigahertz-to-terahertz range for the same 0.1 m cell — and conversely, an RF unit cell sized to resonate in an X-band-relevant range (GHz) is centimeters to millimeters, not because of any transferable geometry rule but because the two wave speeds force completely different length-to-frequency relationships. *Plain-language reading: this dataset's cells are 10 cm across and ring at kilohertz frequencies because sound in steel and polymer is slow; a radio surface that needs to resonate at gigahertz frequencies must be sized around a wave that is a hundred thousand times faster, so nothing about "this pixel pattern gives this frequency" carries over — the ruler and the clock are both different.* This is a straightforward consequence of well-established wave physics, not a finding requiring a citation, and it is the reason the dataset's `BandGapLocation`/`BandGapWidth` values (kHz, mechanical) have no numeric bearing on an RF requirement (GHz, electromagnetic).

### 2.3 Is there a legitimate qualitative/structural bridge, and does the paper or literature discuss it?

**The source paper itself: no.** A full-text search of the retrieved paper for "photonic," "electromagnetic," "microwave," "RF," "radio," "Maxwell," and "frequency selective surface" returned **no matches** — none of these terms appear anywhere in the paper. The authors frame their work entirely within phononic/elastic metamaterials and never gesture at an electromagnetic analogue, so there is no "the paper claims a transfer" finding to report here at all — the paper is simply silent on electromagnetics.

**The broader literature: yes, a real but narrow bridge exists, and it does not license reusing this dataset's numbers.** Both phononic (elastic) and photonic (electromagnetic) band-gap engineering are, independently, Bloch-periodic eigenvalue problems on a periodic unit cell — the same *mathematical machinery* (Bloch's theorem, a periodic lattice, a dispersion relation with forbidden frequency bands) applied to two different physical fields. This structural analogy is explicit enough in the literature that a named sub-field exists for it: **"phoxonic crystals"** — structures engineered to exhibit *simultaneous* phononic and photonic band gaps on one lattice. An arXiv paper on the topic states that **"periodic structures with properly tuned dimensions can act simultaneously as phononic and photonic — phoxonic — crystals"** ([Ortiz et al., arXiv:2003.01777](https://arxiv.org/abs/2003.01777), abstract). The qualifier *"properly tuned dimensions"* is doing the same work as §2.2's wave-speed argument: hitting both a phononic and a photonic band gap on one geometry requires deliberately re-scaling the design for each physics, precisely because the wave speeds differ by orders of magnitude — it is not that one geometry naturally serves both. I was not able to retrieve full text discussing the vector/scalar and dispersion differences between the two eigenvalue problems in more depth (the ScienceDirect review "Phononic and photonic band gap structures: Modelling and applications" and the PubMed-indexed phoxonic-crystal papers returned 403/cookie-wall responses and could not be read past their abstracts within this session — noting this as a retrieval gap rather than a claim about their content).

**What this means for the "does an ML architecture transfer even if the data can't" question:** plausible in principle — a model architecture built to map a periodic pixel bitmap to *some* scalar band-gap property is agnostic to which wave equation produced the training labels, so the shape-frequency-feature / decision-tree pipeline this paper built (§3) could structurally be retargeted at an RF property (e.g. reflection-phase band or absorption band) if trained on RF-appropriate data. But **this is architecture-level reuse of a method, not "ML transfer learning" from this dataset in any technical sense** — nothing in the retrieved sources describes fine-tuning a phononic-trained model on photonic data, transferring trained weights, or any quantitative technique for carrying numeric predictions across the two domains. I found no literature — in the paper's own citations or in general search — that runs such a transfer and reports it working (or failing); the "phoxonic crystal" literature builds and analyzes each physics separately on a shared lattice rather than transferring one trained model into the other's domain. **Absence of evidence is not evidence of absence here**, and this is a narrower claim than "no bridge exists" — it is "no bridge was found in the sources reachable in this session," which should be read as a gap to note rather than a settled negative.

---

## 3. The ML method — is it a usable methodology template?

**Explicitly not a black-box deep net — that is the paper's stated point.** The abstract states: *"past work has usually relied on black box deep neural networks, whose reasoning processes are opaque and require enormous datasets that are expensive to obtain. In this work, we develop two novel machine learning approaches to metamaterials discovery that have neither of these disadvantages"* (arXiv:2111.05949 abstract, retrieved via [ar5iv](https://ar5iv.labs.arxiv.org/html/2111.05949)).

The two named methods:
1. **"Shape-frequency features"** feeding **sparse decision trees trained via GOSDT** (Generalized Optimal Sparse Decision Trees) — produces threshold-style, human-readable rules over the pixel geometry.
2. **"Unit-cell templates"** — a coarser structural pattern (a template that leaves some pixels free and fixes others) selected by **integer/mixed-integer linear programming (MIP/ILP)**, optimised to guarantee a target band gap regardless of how the free pixels are filled in.

Both are described as producing **"logical rule-based conditions on metamaterial unit-cells that allow for interpretable reasoning processes"** and generalising **"well across design spaces of different resolutions"** — i.e. rules learned at coarse pixel resolution are claimed to carry over to finer pixel grids of the same cell.

**Code repository:** the paper states *"the code and data for replicating our results are available on"* **[github.com/zhiCHEN96/interpretable_ml_metamaterials](https://github.com/zhiCHEN96/interpretable_ml_metamaterials)**, which I fetched directly. Its contents (per the repo's own README and file listing):
- `gosdt/` — the GOSDT sparse-decision-tree implementation
- `create_bin_datasets.py`, `run_gosdt_sff.py` — shape-frequency-feature pipeline
- `preselect_templates.py`, `choose_templates.py` — the unit-cell-template pipeline; `choose_templates.py` requires a **CPLEX** solver (a commercial MIP solver) for the ILP step
- `trainCNN.py` — a convolutional-neural-network baseline, presumably the "black box" comparison point the paper argues against
- `compare_bacc.py`, `utils.py`
- MIT license
- **The repository does not include the raw simulation/FEM data or the FEM generation scripts** — it expects a pre-computed `bandgap_data.mat` file (10×10 unit cells plus FEA-simulated dispersion curves) downloaded separately from a Google Drive link and placed in a `/data` folder. No UCI Machine Learning Repository reference or CSV-format dataset code was found in the repository.

**Is it reproducible as a methodology template?** Yes, in shape, with two caveats. The paper plus repo together document the full pipeline shape — binary pixel-bitmap encoding exploiting cell symmetry → an interpretable model (sparse decision tree or MIP-selected template) mapped from bitmap to a scalar physical target → a rule-based interpretability read-out — clearly enough that someone could follow the same shape for a different physical target (e.g. RF reflection phase or absorption bandwidth) without needing anything from the elastic-wave physics. The caveats: (1) the FEM/simulation-generation code that produced the labels is **not** in the repository — only the downstream ML pipeline is, so "reproduce the pipeline shape" means re-implementing the physics-appropriate simulator yourself, which for this program means the existing EM full-wave tooling, not anything borrowed from this repo; and (2) one stage (unit-cell templates) depends on a commercial MIP solver (CPLEX), which is a real adoption cost if that stage were copied as-is.

---

## 4. Existing prior art in this repo — confirmed absent

I read `/home/user/Principle_RF_Engineer_Agent/docs/element-library-prior-art.md` in full (reproduced in the tool context above). It is a thorough survey of reflectarray, FSS, coding-metasurface, and closed-form equivalent-circuit prior art for element libraries, and covers ML-adjacent territory only tangentially (phase-quantisation penalties, supercell coupling). **It contains no reference to this UCI dataset, to Chen/Ogren/Daraio/Brinson/Rudin, to phononic or elastodynamic metamaterials, or to GOSDT/interpretable-ML band-gap work.** A repo-wide grep for `elastodynamic`, `UCI Machine Learning`, `phononic`, and `archive.ics.uci.edu` returned no matches anywhere in the codebase. This confirms the prior check the task cites still holds.

**That file's citation conventions, for any future entry:**
- A markdown table row per source, with the retrieved/verified claim in one column and a markdown-linked citation in the last column (e.g. `[Cui, Qi, Wan, Zhao & Cheng, arXiv:1407.8442](https://arxiv.org/abs/1407.8442)`).
- A **Provenance summary** table at the end classifying every claim as `LITERATURE-SUPPORTED` (retrieved and read), `UNVERIFIED` (recalled or secondary only), `CALCULATED`/`INFERRED` (this document's own arithmetic from a source's stated numbers), or `STRANDED` (known to exist, not reachable).
- A **What is stranded** table listing sources that could not be fetched and what is lost by their absence.
- A numbered **Retrieved sources** list at the end with full author/title/venue/identifier, matching how this document's own citations are written inline.
- Quotes are pulled verbatim in blockquotes with page/section pointers where available, and every "plain English" gloss is marked as such immediately following the technical statement — the same convention CLAUDE.md's Communication section requires and this document follows throughout.

This document follows that same structure and provenance discipline; it has not modified `element-library-prior-art.md` itself, per the task instruction.

---

## 5. Conclusion and recommendation

**Confirmed, not corrected:** the dataset is **not usable as training or validation data** for this program's RF/electromagnetic designs. The physics does not transfer numerically — different governing equations (elastodynamic/Navier-Cauchy vs. Maxwell), different material properties (elastic modulus and density vs. permittivity/permeability/conductivity), and a frequency/wave-speed gap of roughly five to six orders of magnitude between kilohertz mechanical vibration in centimeter-scale polymer/steel cells and gigahertz electromagnetic behaviour in millimeter-scale printed cells. `BandGapLocation` and `BandGapWidth` as stored in this dataset carry no numeric meaning for any RF requirement this program evaluates. The source paper itself never engages with electromagnetics — this isn't a case of over-claimed transfer needing correction, it's a case of no claimed transfer existing to begin with.

**What is worth keeping, and how:** the paper is a clean, well-documented (paper + partial code) instance of the "pixel bitmap + interpretable ML inverse design" method CLAUDE.md already lists as a legitimate, non-privileged design method. It's a good methodology reference — pixel-bitmap symmetry reduction, sparse-decision-tree / template-based interpretable modelling as an alternative to black-box deep nets, MIT-licensed code showing the pipeline shape — for whoever eventually builds an analogous RF tool that maps a printed pixel-bitmap unit cell to an electromagnetic target (reflection phase, absorption bandwidth, etc.). That has two hard prerequisites this dataset cannot shortcut: (1) RF-appropriate training labels, generated by this program's own Maxwell-equation solvers rather than borrowed from anywhere in this dataset or paper, and (2) per ADR-0027, no shape or pattern enters this program's element library as a claimed, usable letter until it has actually been printed and measured on real RF hardware — a simulated elastodynamic dataset cannot be swapped in as a substitute for that measurement gate, no matter how good its interpretability story is.

**Recommendation, left for a human/follow-up decision:** if/when this program builds a pixel-bitmap ML tool for an RF target, add a short entry to `docs/element-library-prior-art.md` citing this paper (Chen et al., *Extreme Mechanics Letters* 57, 101895, 2022) under a new "methodology precedent, different physics" heading — distinct from that file's existing EM-specific prior art — making clear it is cited for its *method*, not its *numbers*. I have not made that edit here, per the task instruction to leave existing files untouched.

---

## Sources

1. UCI Machine Learning Repository, "2D Elastodynamic Metamaterials" dataset — [archive.ics.uci.edu/dataset/692/2d+elastodynamic+metamaterials](https://archive.ics.uci.edu/dataset/692/2d+elastodynamic+metamaterials), DOI [10.24432/C5ZS5D](https://doi.org/10.24432/C5ZS5D).
2. Z. Chen, A. Ogren, C. Daraio, L. C. Brinson, C. Rudin, "How to See Hidden Patterns in Metamaterials with Interpretable Machine Learning," [arXiv:2111.05949](https://arxiv.org/abs/2111.05949) (preprint text retrieved via [ar5iv.labs.arxiv.org/html/2111.05949](https://ar5iv.labs.arxiv.org/html/2111.05949)); published as *Extreme Mechanics Letters* **57**, 101895 (2022), DOI [10.1016/j.eml.2022.101895](https://doi.org/10.1016/j.eml.2022.101895) — venue/DOI confirmed via the [Caltech Daraio Research Group's hosted copy](https://www.daraio.caltech.edu/publications/Chen_et_al_EMS_2022.pdf) and Duke's [Scholars@Duke record](https://scholars.duke.edu/individual/pub1560353).
3. Z. Chen ("zhiCHEN96"), code repository for the above paper — [github.com/zhiCHEN96/interpretable_ml_metamaterials](https://github.com/zhiCHEN96/interpretable_ml_metamaterials), MIT licensed.
4. C. Ortiz et al., on "phoxonic crystals" (simultaneous phononic/photonic band-gap structures) — [arXiv:2003.01777](https://arxiv.org/abs/2003.01777), abstract only retrieved.
5. `/home/user/Principle_RF_Engineer_Agent/docs/element-library-prior-art.md` — this repo's existing EM element-library prior-art survey, read in full for citation-convention matching and to confirm no existing reference to this dataset.

**Not retrieved / stranded:** L. Dobrzynski et al. (and related Pennec/Djafari-Rouhani/Laude group authors), "Phononic and photonic band gap structures: Modelling and applications," *Comptes Rendus Physique* — [ScienceDirect record](https://www.sciencedirect.com/science/article/pii/S1875389210000489) and a [ResearchGate copy](https://www.researchgate.net/publication/243652785_Phononic_and_photonic_band_gap_structures_Modelling_and_applications) both returned HTTP 403 in this session; a PubMed-indexed companion paper, "Simultaneous existence of phononic and photonic band gaps in periodic crystal slabs" ([PubMed 20588565](https://pubmed.ncbi.nlm.nih.gov/20588565/)), returned only a cookie-consent wall. These would be the next sources to open for a deeper first-hand statement of the phononic/photonic analogy's mathematical limits, beyond what arXiv:2003.01777's abstract offers.
