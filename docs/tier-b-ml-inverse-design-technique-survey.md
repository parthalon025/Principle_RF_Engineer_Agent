# Which ML inverse-design technique survives Tier B's data drought — REFLECTION_PHASE and DIFFUSIVE

**Date:** 2026-09-12
**Ticket:** [#560](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/560), a child of the wayfinder map [#556](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/556) ("ML inverse design: from target response to candidate geometry"). Sibling ticket [#559](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/559) covers the same question for `ABSORBER` (Tier A).

**Provenance ceiling.** This is a research note, not a decision. Nothing here is an ADR — per #556's own map, this feeds a future locked ADR but does not write one. Claims traced to a primary source I opened and quoted directly are marked so; claims from a search-engine summary I could not get past a paywall are marked `LITERATURE-SUPPORTED, NOT FIRST-HAND` and should be re-read before anyone relies on the number.

---

## 1. The question, in plain terms

`REFLECTION_PHASE` and `DIFFUSIVE` are the two design families where nobody has written down a formula that predicts a cell's behavior from its shape — unlike `ABSORBER`, which has one (Costa/Luukkonen, `rf_tools/absorber.py`). For these two families, the only way to learn what a shape *does* is to either measure a physical sample or run a slow full-wave computer simulation. Training an ML model to invert that relationship (go from "the phase shift I want" to "the shape that gives it") needs many examples of (shape, behavior) pairs, and here those examples are expensive and there are almost none of them yet. The question is which flavor of ML inverse design copes with "almost no data, and each new datum costs real time" rather than needing the tens of thousands of examples most inverse-design demonstrations assume.

---

## 2. What is actually in the tree today (checked directly, not assumed)

**`REFLECTION_PHASE` and `DIFFUSIVE` both declare `UndeclaredAnalysisModel`, and the code says why in physical terms, not just "not built yet."** From `designs/design_families.py`:

- `REFLECTION_PHASE` (lines 1365–1376): *"a reflection-phase surface is designed by its per-cell reflection PHASE... and no closed form in rf_tools returns a phase (rf_tools.patch_synthesis returns a patch resonant frequency; rf_tools.absorber returns an absorbed fraction). The Tier B aperture-level step that would turn a per-cell phase lookup into a steered beam does not exist here either."*
- `DIFFUSIVE` (lines 1526–1534): *"a coding/diffusive cell is DEFINED by its reflection phase (a '0' and a '1' are cells 180 degrees apart), and no closed form in rf_tools returns a phase. Its figure of merit — monostatic backscatter reduction — is an aperture-level scattering pattern over an arrangement of those cells."*

**`DIFFUSIVE` is, in the code's own words, a two-state (0°/180°) binary coding metasurface.** This detail matters for §4 below: it is not an abstract "discrete design space," it is specifically the same binary-phase-cell representation used throughout the coding-metasurface literature.

**The two families do not sweep the same kind of variable, per the registry's own `sweep_axes` comment (lines 596–602):** `REFLECTION_PHASE` sweeps *cell geometry and external material state* (continuous-ish, single-cell parameters); `DIFFUSIVE` sweeps *tile assignment and aperture size* (a discrete/combinatorial placement problem on top of the same per-cell phase lookup). Both currently carry `optimizer_class="COMBINATORIAL"` (lines 1356, 1519) — a brute-force/discrete search, not the continuous Bayesian optimizer described next.

**The measured-Symbol corpus is not merely "very few" — it is currently zero in the running system.** `designs/element_alphabet.py` defines `add_symbol_entry`/`insert_symbol_entry` against the `symbol_alphabet_entries` table (`db/schema.sql:388`), and every entry it creates is stamped `provenance = MEASURED` by construction (ADR-0027) — there is no path to insert an entry with any other provenance. A repo-wide search for every call site of `add_symbol_entry(` and `insert_symbol_entry(` finds exactly three files: the module's own definition, `tests/test_element_alphabet.py`, and `tests/test_design_loop.py` — both test files, exercising the function against in-memory fixtures, never against a real measurement. **No seed data, no migration, no production call site inserts a real row.** So "currently very few" undersells it: the Element/Coding-Alphabet library that CLAUDE.md's charter calls the program's "first job" (*"Filling the alphabet is step one"*) has not yet produced its first letter in this codebase.

**`MEEP_FLOQUET` is real but deliberately made expensive to invoke casually.** `simulation/meep.py`'s own docstring: Meep is a Python library, not a CLI, and the container runs it in *"a conda environment... [while] the application runs under a separate uv venv,"* so the adapter subprocess-delegates to a separate interpreter (`python_executable`/`MEEP_PYTHON`) rather than importing in-process. That is a correct engineering choice (license and dependency isolation) but it means each training pair generated this way pays a process-boundary and full-wave-solve cost, not an in-memory function call.

**`optimization/bayesian.py` already exists and is a real precedent, not a green field.** It implements, from scratch and dependency-free, a squared-exponential-kernel Gaussian Process (`_gp_posterior`, `_fit_gp_hyperparameters`) with Expected Improvement acquisition (`_expected_improvement`), explicitly built (issue #41) for "minimizing costly evaluations" — the same sentence ADR-0039 §5 uses to describe what this family needs.

---

## 3. What this repo has already concluded, before any outside literature (docs/ai-metasurface-survey-against-the-seven-examples.md, ADR-0039)

The ticket asks to ground the answer in these two documents *first*. They already say most of what matters:

**§3 of the survey doc gives a three-point data-cost ladder, and it puts a name to the cheap end.** Lined up by scope: cloak parameters (a few continuous parameters) needed **no training corpus at all** — *"Bayesian optimization queries the solver directly"*; an absorber cell (Tier A, ~10 parameters) needed **7,000** solves; a coding pattern (Tier B, this family) needed on the order of **70,000–80,000** solves in the two papers the survey traces. The zero-corpus end of that ladder is exactly Bayesian active learning: Qin et al.'s cloak result, read in the survey's §5, uses *"Bayesian optimization in combination with an electromagnetic solver"* with, uniquely among the quantified cases, no training corpus at all, because *"it is sample-efficient because it chooses each next evaluation from what the previous ones taught it."*

**§5 of the survey doc already recommends repointing `optimization/bayesian.py` at the expensive solver, for exactly this reason, and already names the cost honestly.** It quotes the survey's own caveat: *"the integration of BO with electromagnetic simulations presents a significant computational challenge for real-time or large-scale applications,"* with Gaussian-process or neural-network surrogates named as the mitigation — i.e. "fewer expensive evaluations," never "cheap ones."

**§7 of the survey doc gives a structural warning that active learning does not remove.** Inverse design in general *"faces significant challenges owing to the complex, non-unique relationship between the structure and electromagnetic response, where multiple geometries can yield similar responses"* — and the survey doc is explicit that *"this is not a data-volume problem and cannot be spent away."* Any technique chosen here still has to evaluate candidates, not just interpolate a trained inverse map with false confidence.

**ADR-0039 already commits, in writing, to the shape of the answer this document ends up giving.** Decision item 8: *"An ML-direct inverse-design surrogate is a legitimate third tier... adopted once enough historical design data exists to train on, which is not yet the case,"* and separately: *"This ADR does not decide when the ML-direct third tier's data threshold is met, only that it activates once it is."* The "Still open" consequence names this exact ticket's tension: a 2° ML phase-surrogate error would fit inside the phase budget, *"but training costs ~80,000 solves,"* and whether that ever replaces a Floquet solve for this family "is a live, unresolved question... this ADR does not decide it." **This document does not resolve that either — it answers a narrower, prior question: given that an 80,000-solve corpus is not coming, what *is* buildable in the meantime.**

**Read together, the repo's own record already points at Bayesian-optimization-style active learning as the technique class that fits a near-zero-corpus, expensive-per-sample regime**, and at a from-scratch GP already sitting in the tree built for exactly that purpose. What it had not yet done — because #556/#560 are what asked the question — is check that recommendation against the literature specifically for *this* family's representation (a two-state coding cell, not a continuous cloak parameter), and against the two competing techniques the ticket names. That is §4.

---

## 4. Checking the recommendation against outside literature

### 4.1 Bayesian-optimization-style active learning — the closest structural match found

**P. Chittur Subramanianprasad, Y. Ma, A. A. Ihalage & Y. Hao, "Active Learning Optimisation of Binary Coded Metasurface Consisting of Wideband Meta-Atoms," *Sensors* 23(12):5546 (2023), DOI [10.3390/s23125546](https://doi.org/10.3390/s23125546). Open access; retrieved and quoted directly ([PMC10302143](https://pmc.ncbi.nlm.nih.gov/articles/PMC10302143/)).**

This is the single closest analog to `DIFFUSIVE` found in this pass, because the representation matches, not just the technique. The paper's coding cell is binary — *"code 0 acting as 0th element and code 1 acting as 1st element"* representing *"0 and π phase responses, respectively"* — which is the same two-state 0°/180° cell `designs/design_families.py` defines for `DIFFUSIVE`. The method is **Bayesian global optimization with a Gaussian-process regressor as the surrogate model and Expected Improvement as the acquisition function** — architecturally identical to `optimization/bayesian.py`'s `_gp_posterior` + `_expected_improvement` pair. Sample cost, quoted directly: an initial training set of **450 data points** bootstraps the 10×10-array case; from there, active learning finds an optimal 60×60 arrangement **24× faster** than a genetic algorithm reaching a comparable result, and at population size 10⁶ the wall-clock gap is **65 minutes (active learning) versus 13,260 minutes (GA)**. Four to five orders of magnitude below the 70,000–80,000-solve corpora the survey doc's §3 prices for generative/discriminative coding-metasurface models.

**A second Bayesian-active-learning paper was located but not verified first-hand** — S. et al., "Bayesian Active Learning for Accelerated Design of Broadband Polarization-Insensitive Metasurfaces," *Intelligent Computing* (2025), DOI [10.34133/icomputing.0135](https://doi.org/10.34133/icomputing.0135) — the publisher returned HTTP 403 to automated fetch. `LITERATURE-SUPPORTED, NOT FIRST-HAND`: flagged as a further lead, not relied on for any number here.

**Why this fits the regime the ticket names, in the ticket's own terms:** active learning does not need a corpus before it starts — it starts from a handful of points (here, 450, not 70,000) and *chooses its own next query* to run through the expensive oracle (here, that oracle is `MEEP_FLOQUET`) based on where the current GP is most uncertain or most promising. That is the mechanism, not a side effect: Expected Improvement is defined (`optimization/bayesian.py`'s own docstring, mirroring Rasmussen & Williams) to spend the next expensive evaluation where it is expected to matter most, which is exactly the discipline CLAUDE.md's iteration loop asks for — *"Evaluate cheap before expensive... kill weak candidates early."*

### 4.2 Physics-informed networks leaning on the periodic-unit-cell structure — a real, complementary lever, but not yet a quantified one for this exact problem

**R. Zhang, C. Liu, X. Wan, L. Zhang, S. Liu, Y. Yang & T. J. Cui, "Machine-Learning Designs of Anisotropic Digital Coding Metasurfaces," *Advanced Theory and Simulations* 2, 1800132 (2019)**, already read and cited in `docs/ai-metasurface-survey-against-the-seven-examples.md` §3, is the strongest coding-metasurface precedent in the repo's own record, and it is **not** physics-informed in the loss-function sense — it is a conventional supervised network trained on 70,000 + 10,000 labelled full-wave patterns.

Searching specifically for physics-informed networks that use the Floquet-Bloch periodic boundary condition as a training constraint (rather than only as a data-generation setting) finds a genuine and active sub-field, but the concrete numbers in it are thinner than §4.1's:

- L. Armbruster, V. Medvedev & A. Rosskopf, "Physics-Informed PointNets for Modeling Electromagnetic Scattering from All-Dielectric Metasurfaces with Inclined Nanopillars," arXiv:2507.23119 — retrieved directly. It embeds the Helmholtz equation as a physics-loss term over a point-cloud geometry encoding and reports near-field error of 1.69–3.04% MAPE, but this is a **forward** model (geometry → response), and the retrieved text does not give a quantified labelled-data-reduction number comparable to §4.1's or §4.3's below — the paper's abstract/body do not state "N% fewer simulations than a purely data-driven baseline" in the sections retrieved.
- Search results additionally surface a physics-informed PointNet encoding *"the 2D TE scalar Helmholtz equation and 3D vectorial Helmholtz equation with Floquet-Bloch periodic boundary conditions as loss constraints"* and U-Net architectures trained with *"the complete vector Maxwell equations under Floquet-Bloch periodic boundary conditions"* — both corroborating that periodic-cell physics is a live, used ingredient in this class of network, but these are search-engine summaries, not primary-source reads, and are flagged `LITERATURE-SUPPORTED, NOT FIRST-HAND`.
- "Physics-Informed Inverse Design of Programmable Metasurfaces," Xu et al., *Advanced Science* (2024), DOI 10.1002/advs.202406878, is the closest-titled match to this family (programmable/coding metasurface, inverse design, physics-informed) but returned HTTP 403 to fetch and was **not read**.

**Read honestly, this is a real lever, not a myth, but the evidence gathered in this pass does not let it be recommended as a standalone primary technique for this ticket's regime** — the papers that quantify it are forward surrogates with unquantified data savings, and the one paper whose title matches this problem exactly could not be opened. Where it does have a clear, defensible role is as an **enhancement bolted onto §4.1's active-learning loop**: encoding the family's own periodicity (a Floquet-Bloch loss term, or a periodicity-aware kernel/feature set in the GP) into the surrogate that active learning fits, so that each of the few expensive `MEEP_FLOQUET` queries is squeezed for more information than an unconstrained regressor would extract from it. That is additive to §4.1, not a competing alternative to it.

### 4.3 Transfer learning from the ABSORBER pilot's surrogate — real technique class, weak fit for *this specific* pairing

**R. Peng, S. Ren, J. Malof & W. J. Padilla, "Transfer learning for metamaterial design and simulation," *Nanophotonics* 13(13):2323–2334 (2024), DOI [10.1515/nanoph-2023-0691](https://doi.org/10.1515/nanoph-2023-0691). Retrieved and quoted directly.**

This is a genuine, well-quantified precedent for transfer learning's data-efficiency in exactly this domain, including an explicit discussion of periodic-array unit cells (their "local periodic response" approximation, used to model an element inside a random array — structurally the same simplification `docs/local-periodicity-coupling-error.md` and ADR-0039 item 6 wrestle with for this repo's own Tier B error budget). Method: pre-train a DNN on a *source* configuration (silicon spheres in a 50×50 array, one incidence angle/polarization), then fine-tune on a *target* configuration that changes one or two physical settings (angle, polarization, material, shape). Quoted directly: to reach 3% mean absolute relative error, the easiest target task needed only **D = 3** fine-tuning samples where the harder targets needed **D = (776, 924, 13,691, 17,353)** — the paper's own framing is a data reduction "by a factor of 1000" in the best case.

**Why this is the weakest fit of the three for *this* pairing specifically, and the paper's own numbers show why.** Every transfer in Peng et al. moves between tasks that share the same underlying wave-physics problem and geometry-encoding shape, differing only in a boundary parameter (angle, polarization, one material swap). `ABSORBER`'s surrogate (the sibling pilot, #559) would be trained against `rf_tools/absorber.py`'s Costa/Luukkonen closed-form model — a **continuous-dimension, Tier A, magnitude-only** target (an absorbed fraction). `REFLECTION_PHASE`/`DIFFUSIVE` are **Tier B, phase-valued, and for `DIFFUSIVE` explicitly combinatorial** (a tile-assignment problem, ADR-0045's own axis enumeration). That is a bigger jump than any pair Peng et al. tested — a different family, a different closed-form-vs-none status, and (per §4 of the survey doc, "the 4° figure does not belong to this family") a documented history in this repo's own research of conflating superficially similar phase/error figures across families that turn out to answer different physical questions. Transfer learning is not ruled out by this — the underlying representation-learning machinery (a network's early layers learning general electromagnetic-scattering features) is exactly the kind of thing the source and target tasks share in Peng et al. even across a material swap — but nothing found in this pass quantifies how well it transfers across a *closed-form-model-had → closed-form-model-lacks* and *continuous → discrete* jump this large. **Recommendation: worth testing empirically once #559's `ABSORBER` surrogate exists (cheap to try, since the surrogate will already exist), but not the primary technique to build around now, and not a substitute for §4.1's active-learning loop, which needs no such surrogate to exist first.**

---

## 5. Recommendation

**Primary: Bayesian-optimization-style active learning, built directly on `optimization/bayesian.py`'s existing GP + Expected Improvement machinery, using `MEEP_FLOQUET` (and, once any exist, measured Symbol entries) as the oracle it queries adaptively.** This is not a new idea introduced here — it is what ADR-0039 §5 and the survey doc's §3/§5 already point at, now corroborated by a literature precedent whose *representation* matches `DIFFUSIVE` exactly (a binary 0°/180° coding cell) rather than only its *technique*: Chittur Subramanianprasad et al. (2023) bootstrap a working GP-based active-learning loop for a binary coding metasurface from **450** samples, and reach a 60×60-array design **24× faster** than brute-force search — four to five orders of magnitude below the 70,000–80,000-solve corpora the survey doc prices for the generative/discriminative alternative. It is the only technique among the three the ticket named that has a documented example requiring **zero** pre-existing training corpus (Qin et al.'s cloak result, already in this repo's own §5) and a documented example requiring **hundreds, not tens-of-thousands** (§4.1) — both ends of exactly the regime this ticket describes.

**Complementary, not competing: bake the periodic-unit-cell structure into the active-learning loop's own surrogate**, via a Floquet-Bloch-aware loss term or periodicity-informed kernel/features, rather than standing up a separate physics-informed-network tier. The literature located in this pass (§4.2) supports this as a real, live technique family, but not yet with numbers strong enough, or a paper opened successfully enough, to recommend it as a freestanding alternative for this specific problem today.

**Deferred, not dismissed: transfer learning seeded from the ABSORBER pilot's surrogate**, once that surrogate exists under #559. Peng et al. (2024) is genuine, quantified evidence that transfer learning can cut required data by up to 1000× — but every case they measured stays within one physics regime and geometry encoding, and `ABSORBER → REFLECTION_PHASE/DIFFUSIVE` crosses more than that (continuous↔combinatorial, magnitude↔phase, closed-form↔none). Cheap to test once #559 lands; not the technique to build the pilot around.

**One caution that survives regardless of which technique is chosen**, from the survey doc's §7 and worth repeating because active learning does not remove it: non-uniqueness — many shapes can give the same reflection phase — is a structural property of inverse design, not a data-volume problem, and *"cannot be spent away."* Whatever is built here still needs a forward evaluator in the loop (which active learning already assumes) and should not be sold as "ask for a phase, get the one true shape."

---

## 6. What this does not settle

- **Not an ADR.** This document answers the technique-class question #560 asked; the `inverse_model` plug-in shape, its interface, and when it is adopted are #556's map to close, separately.
- **Not a corpus-size threshold.** ADR-0039 item 8 explicitly leaves "when enough historical data exists to train on" undecided; nothing here sets that number for Tier B.
- **Does not reproduce any cited figure.** Every external number above is either quoted directly from a retrieved primary source (marked as such) or explicitly flagged `LITERATURE-SUPPORTED, NOT FIRST-HAND` where the source could not be opened.
- **Does not address `REFLECTION_PHASE`'s and `DIFFUSIVE`'s different search-space shapes in implementation detail** — `REFLECTION_PHASE` sweeps continuous cell geometry/material state, `DIFFUSIVE` a discrete tile assignment (`designs/design_families.py` lines 596–602) — beyond noting that Chittur Subramanianprasad et al.'s GP regressor was applied to the discrete/binary case directly, which is evidence the technique class covers both, not a worked-out adapter design for either.

---

## Sources consulted

**Repo, read directly:**
- `designs/design_families.py` (`REFLECTION_PHASE`, `DIFFUSIVE`, `sweep_axes`, `optimizer_class`, `UndeclaredAnalysisModel`)
- `designs/element_alphabet.py`, `tests/test_element_alphabet.py`, `tests/test_design_loop.py`, `db/schema.sql` (`symbol_alphabet_entries`)
- `optimization/bayesian.py`
- `simulation/meep.py`
- `docs/ai-metasurface-survey-against-the-seven-examples.md`
- `docs/adr/0039-two-tier-em-modelling-hybrid-fast-tier-meep-and-emerge.md`
- GitHub issues [#556](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/556), [#559](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/559), [#560](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/560)

**External, retrieved and quoted directly:**
- Chittur Subramanianprasad, Ma, Ihalage & Hao, "Active Learning Optimisation of Binary Coded Metasurface Consisting of Wideband Meta-Atoms," *Sensors* 23(12):5546 (2023). DOI [10.3390/s23125546](https://doi.org/10.3390/s23125546) / [PMC10302143](https://pmc.ncbi.nlm.nih.gov/articles/PMC10302143/).
- Peng, Ren, Malof & Padilla, "Transfer learning for metamaterial design and simulation," *Nanophotonics* 13(13):2323–2334 (2024). DOI [10.1515/nanoph-2023-0691](https://doi.org/10.1515/nanoph-2023-0691) / [PMC11501712](https://pmc.ncbi.nlm.nih.gov/articles/PMC11501712/).
- Armbruster, Medvedev & Rosskopf, "Physics-Informed PointNets for Modeling Electromagnetic Scattering from All-Dielectric Metasurfaces with Inclined Nanopillars," arXiv:[2507.23119](https://arxiv.org/pdf/2507.23119).

**External, located but not opened first-hand (`LITERATURE-SUPPORTED, NOT FIRST-HAND`):**
- "Bayesian Active Learning for Accelerated Design of Broadband Polarization-Insensitive Metasurfaces," *Intelligent Computing* (2025). DOI [10.34133/icomputing.0135](https://doi.org/10.34133/icomputing.0135) — 403 on fetch.
- Xu et al., "Physics-Informed Inverse Design of Programmable Metasurfaces," *Advanced Science* (2024). DOI [10.1002/advs.202406878](https://doi.org/10.1002/advs.202406878) — 403 on fetch.
