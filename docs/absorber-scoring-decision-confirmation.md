# Checking the #110 Scoring Decisions Against the Literature

**Research date:** 2026-09-04
**Serves:** [#110](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/110) — what the success score rewards for an absorber
**Builds on:** `docs/absorber-scoring-conventions.md` (2026-09-03) — read that first; this document does not repeat its findings, only extends them
**Method:** #110 was resolved through a human interview (a "grilling" session). This document is the requested literature check on five decisions made in that interview — confirming or overturning them, not restating the reasoning already used to justify them. Four of the five decisions get an explicit verdict: **CONFIRMED**, **CONTRADICTED**, or **NO CONVENTION FOUND, STILL A JUDGMENT CALL**.

---

## Bottom line up front

| # | Decision | Verdict |
|---|---|---|
| 1 | Objective metric = worst-in-band absorptivity, not mean or peak | **CONFIRMED** — but with a domain split worth knowing about |
| 2 | −10 dB/90% is a reversible default when the customer is silent, never hardcoded | *(no verdict format requested — internal policy, see §2)* |
| 3 | Off-band gets its own separate score, ±10% of bandwidth past each edge | **NO CONVENTION FOUND, STILL A JUDGMENT CALL** — for a specific, checkable physical reason, not just an empty search |
| 4 | Incidence angle scored as a continuous sliding scale over a curvature-derived range | **CONTRADICTED** |
| 5 | Example 3's reproduction judged by RMS error in dB against Landy et al.'s measured curve | **CONTRADICTED** |

One of the four graded decisions is confirmed outright (1), one has no literature to check it against either way (3), and two are contradicted (4, 5) — but read past the labels, because neither "CONTRADICTED" verdict is a simple reversal. In both cases the literature agrees the instinct behind the decision is right; it just does the thing differently than "RMS error in dB" or "continuous angle sweep" describes — item 4's real precedent is deriving *design* zones from curvature, not *scoring* continuously across it; item 5's real precedent is a formal standard (Feature Selective Validation) built to do a better job than RMS error at exactly this problem, not a confirmation that RMS error is what the field already does. Item 3 is the one place research came back empty in a documented, not merely absent, way. The detail matters more than the label in every case.

---

## 1. Objective metric = worst-in-band absorptivity — CONFIRMED

**What was decided:** score a candidate on the single worst-absorbing frequency inside the required band (a minimax formulation), not the mean and not the peak.

**What the prior pass already found:** one published combined figure-of-merit (Huynen 2022) uses worst-case in-band reflectivity (`maxR`), against a field that otherwise mostly reports peak absorption. That was called "reasoned, not inherited" because it rested on one paper's convention plus a documented critique of peak-chasing (§3.1 of the prior document), not on optimizer practice.

**What this pass found, pushing into RAM/RCS-reduction (radar-absorbing-material / radar-cross-section-reduction — RCS is how much signal bounces back to a radar) *design-optimization* papers specifically:** minimax absorptivity is an explicit, recurring, named objective function in the metaheuristic-optimization literature for radar-absorbing materials — genetic algorithm, particle-swarm, and artificial-bee-colony (ABC) design of multilayer absorbers. This is a different and stronger kind of evidence than a single combined FOM: it is what optimizers are actually told to minimize, across multiple independent research groups over three decades.

### 1.1 The clearest hit: an explicit minimize-the-maximum objective, with an explicit argument against averaging

> "minimize OF1 = *maximum* {20log10(RTE)}
> minimize OF2 = *maximum* {20log10(RTM)}
> minimize OF3 = TT"
> — Yiğit, E. & Duysak, H., *"Fully Optimized Multilayer Radar Absorber Design Using Multi-Objective ABC Algorithm,"* International Journal of Engineering and Geosciences 6(3):136–145 (2021), [doi:10.26833/ijeg.743661](https://dergipark.org.tr/en/pub/ijeg/issue/59600/743661), Eq. 1 (verbatim, extracted directly from the PDF)

`RTE`/`RTM` are the reflection-coefficient matrices swept over 2–18 GHz and 0–60° incidence; `TT` is total thickness. This is a literal minimize-the-maximum-reflectivity objective — the same shape as this project's "score on the worst-absorbing frequency in the band" — used to drive a triple-objective Artificial Bee Colony optimizer, confirmed independently by a web search that reproduced the same equation in different words: "minimize both the total thickness (TT)... and the maximum reflection coefficients for transverse electric (RTE) & transverse magnetic (RTM) polarizations at any oblique angle of incidence" (search-engine synthesis of the same paper, cross-checked against the verbatim PDF quote above — they agree).

The same paper explicitly argues against averaging, which is the direct literature answer to "why not mean-in-band":

> "it is not a consistent method to give the average values of the reflection coefficients relative to the all frequency band and angle of incidence. Because, if the design has a very low reflection coefficient at any angle or frequency, it significantly reduces the average value and affects the general information about other values."
> — same source, §4.2 (verbatim)

**In plain terms:** if you average, one lucky deep null can drag the average down and make a design that fails badly everywhere else look good on paper — exactly the "sharp resonance passes, broad-but-uneven design fails" failure mode #110's worst-in-band choice was designed to avoid, described independently by a group of RAM-optimization researchers making the same argument for the same reason. `LITERATURE-SUPPORTED`.

### 1.2 The lineage this traces to

The minimax framing is not new to 2021. It traces to the foundational GA-optimization papers for broadband microwave absorbers:

> Weile, D. S., Michielssen, E. & Goldberg, D. E., *"Genetic algorithm design of Pareto optimal broadband microwave absorbers,"* IEEE Trans. Electromagnetic Compatibility 38(3):518–525 (1996), [doi:10.1109/15.536085](https://doi.org/10.1109/15.536085) — **IEEE-paywalled, read only via consistent secondary-source description** (§6, Stranded). Per multiple independent secondary sources, poses the optimization as minimizing the **maximum reflection coefficient** across the target band against minimizing total thickness — a two-objective Pareto trade — and explicitly compares against "the weighted Tchebycheff method," a classical minimax scalarization technique from multi-objective optimization theory. `LITERATURE-SUPPORTED`, exact wording unverified (same epistemic status as the prior document's treatment of the Rozanov citation).

A predecessor paper, Michielssen, Sajer, Ranjithan & Mittra, *"Design of lightweight, broad-band microwave absorbers using genetic algorithms,"* IEEE Trans. MTT 41(6):1024–1031 (1993) — also paywalled, not independently read — is reported by the same secondary sources to cast the problem as reflection-coefficient minimization at a swept set of frequencies/angles under a thickness bound, the same shape again.

Corroborating sibling papers (author-group lineage, all IEEE-paywalled, abstract-level only):
- Toktas, A., Ustun, D. & Tekbas, M., *"Multi-Objective Design of Multi-Layer Radar Absorber Using Surrogate-Based Optimization,"* IEEE Trans. MTT 67(8):3318–3329 (2019), [doi:10.1109/TMTT.2019.2922600](https://doi.org/10.1109/TMTT.2019.2922600) — "minimize both the total thickness (TT)... and the maximum reflection coefficients."
- Toktas, A., Ustun, D., Yigit, E., Sabanci, K. & Tekbas, M., Proc. DIPED (2018), [doi:10.1109/DIPED.2018.8543261](https://doi.org/10.1109/DIPED.2018.8543261).
- Toktas, A. & Ustun, D., IEEE Trans. Antennas Propag. 68:5603–5612 (2020).

**A genuine complication, not smoothed over.** A related dual-objective variant from the same author cluster was described (secondary-source only, not independently verified) as using a "Mean Oblique Incidence (MOI)" term — averaging over incidence *angle* while apparently still maxing over *frequency*. This project's own #110 decision keeps angle and frequency as separate scored dimensions (worst-in-band on the frequency axis; a continuous sliding scale on the angle axis, see §4 below), so this does not contradict the choice — but it means even the minimax-favoring author cluster does not apply minimax uniformly across every axis, and the exact split in that variant could not be pinned down from available sources. `INFERRED`, flagged as unresolved rather than glossed over.

### 1.3 The domain split — where minimax is *not* the choice, and why that does not undercut the verdict

Not every GA/optimization absorber paper uses minimax. In a metamaterial (as opposed to bulk-composite RAM) unit-cell optimization aimed at solar/thermal energy harvesting, the fitness function is explicitly the **mean**:

> "The objective function to be maximized (also called fitness or figure of merit) will be the integrated absorptance for normally incident radiations with wavelengths comprised between 420 and 1600 nm. It is formally defined by η(%) = 100 × ∫λmin^λmax A(λ)dλ / (λmax−λmin)"
> — Mayer, A., Bi, H., Griesse-Nascimento, S., Hackens, B., Loicq, J., Mazur, E., Deparis, O. & Lobet, M., *"Genetic-algorithm-aided ultra-broadband perfect absorbers using plasmonic metamaterials,"* [arXiv:2108.09377](https://arxiv.org/abs/2108.09377) (2021); Optics Express, [doi:10.1364/OE.442405](https://doi.org/10.1364/OE.442405), verbatim, extracted directly from the PDF

**In plain terms:** this is not a hedge — it is a real design-optimization paper (the GA explored more than 10^17 candidate configurations), and its fitness function is the opposite pole from minimax: total captured energy across the band, averaged, not the worst point. A secondary corroborating signal points the same way: a PSO-optimized solar-thermal absorber paper (ScienceDirect, full text paywalled) explicitly names and compares two different fitness functions, "FFad" and "FFavg" — the exact naming shows this sub-field treats averaging-versus-worst-case as a deliberate, named choice, not a default either way.

**Why the split does not weaken the verdict for #110.** The split tracks *application*, not algorithm class or "metamaterial vs. RAM" as such. Solar/thermal absorbers want to maximize total energy captured across a broad, forgiving band — a mean genuinely is the right quantity, because a photon absorbed at any in-band wavelength is equally useful. Stealth/RCS-reduction absorbers exist to satisfy a hard band-compliance requirement — "reflectivity below −10 dB across 8.5–10.5 GHz" is a threshold that must hold *everywhere* in the band, not on average — and that is exactly #110's Example 3 situation. The RAM/RCS-reduction sub-literature, which is the analogous problem, explicitly confirms worst-in-band with a stated mechanism-level argument (§1.1). The solar-absorber literature optimizing for something else is evidence that the *choice* is deliberate and application-dependent in this field, not evidence that #110 chose the wrong one for its own application.

**Equiripple/equal-ripple — checked, dead end.** No paper was found importing equiripple/equal-ripple terminology (a classical minimax concept from filter synthesis) into absorber design. The closest tie is Weile et al. 1996's "weighted Tchebycheff method," which is mathematically in the same minimax-approximation family as equiripple filter theory, but no direct citation linking the two was found. Report as a plausible-but-unconfirmed connection, not a finding.

### 1.4 Local corpus check

`grep -ri "radar absorbing"` in `F:\data\arxiv-chunks\` returned exactly one hit — Acher & Dubourg, *"A generalization of Snoek's law to ferromagnetic films and composites,"* Phys. Rev. B 77:104440 (2007), [arXiv:0710.2980](https://arxiv.org/abs/0710.2980) — a permeability-bandwidth sum-rule paper with no optimization-objective content. `"RCS reduction"` returned zero hits. `"minimax"`/`"min-max"`/`"worst-case"` matched only the corpus's pre-documented 2007-era math/CS batch and the unrelated 2026 CS/ML batch, never in an RF/absorber context. **Genuine coverage-gap null, not a negative literature finding**, consistent with what the prior pass documented about this corpus.

---

## 2. −10 dB/90% as a reversible default — no verdict needed, brief note only

This is mostly the internal project policy already settled on the sibling ticket [#117](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/117), not a literature question. Confirmed by re-reading #117's resolution comment directly:

> "**Silence is permissive.** No stated host surface means no bend-radius threshold, so no substrate pruning, so every conductor stays in play. That is the correct default and it follows from threshold-only-prunes: no threshold, no pruning."
> — [#117 resolution comment](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/117) (verbatim)

The −10 dB/90% default is the same shape of rule applied to a different threshold: absent a customer-stated absorption threshold, fall back to the field's dominant default (§2 of the prior document established −10 dB/90% as that default, and also that the field is inconsistent enough — 70–99%, −6.99 to −20 dB all appear in practice — that the threshold must always be carried explicitly with every bandwidth number, never assumed). Nothing in this pass's literature search bore on this decision beyond what the prior pass already established; it is a policy-consistency question, answered by #117, not a literature question. No further search was conducted per the task's explicit low-priority instruction.

---

## 3. Off-band behaviour gets its own separate score — NO CONVENTION FOUND, STILL A JUDGMENT CALL

**What was decided:** off-band absorption (a candidate absorbing frequencies outside the required band, e.g. eating a friendly communications band sitting just past the stealth band's edge) gets its own separate score — not lumped into the main ranking, not simple pass/fail, not ignored — checked by default over a margin of 10% of the required band's width past each edge.

**What the prior pass already found:** off-band behaviour is "never thresholded, tabulated, or scored anywhere" in absorber literature — plotted, but not judged (§7.3 of the prior document).

**What this pass found, pushing in the two directions the task specifically asked for:** filter and frequency-selective-surface (FSS) design has a real, quantitative, decades-old vocabulary for out-of-band behaviour — but it scores a different physical quantity than an absorber's off-band problem, for a precise and checkable reason, not a superficial one. A fresh, separate search of RAM papers for an informal off-band margin still comes back essentially empty, with one genuine near-miss worth recording so nobody re-finds it and mistakes it for a hit.

### 3.1 Thread A — filter/FSS "skirt" and "roll-off" are real, quantitative, and score the wrong physical quantity

Filter theory has a long-established, quantitative vocabulary for how sharply a passband gives way to a stopband: **roll-off rate**, conventionally `20n dB/decade` (`6n dB/octave`) for an *n*th-order filter (standard filter-design textbook result; found via a general reference, [analogictips.com, "An overview of filters and their parameters, Part 3"](https://www.analogictips.com/an-overview-of-filters-and-their-parameters-part-3-key-parameters-faq/) — secondary-source-level confidence, not a primary paper). A frequency-selective-surface paper gives a directly quotable, primary-source version of the same idea applied to a real device:

> "the transition bandwidth [is] the bandwidth of the transition band for judging the roll-off performance when the transmission coefficient drops sharply from −3 dB to −20 dB"
> — as summarized from a quad-band highly-selective FSS paper, [Micromachines 15(1), 126 (2024)](https://doi.org/10.3390/mi15010126), [PMC10821369](https://pmc.ncbi.nlm.nih.gov/articles/PMC10821369/) — a quad-band FSS with two stopbands suppressed below −20 dB across 1–5.5 GHz and 14–40 GHz — *retrieved via WebSearch synthesis of the paper, not independently re-verified against the primary PDF; secondary-source-level confidence.*

**This is real, quantitative, and it is the wrong quantity for #110's problem, precisely rather than approximately.** What roll-off rate and transition bandwidth score is **transmission** (`S₂₁`) — how much power a radome or filter lets *through* outside its intended passband, which matters when something (an antenna, a receiver) sits behind the structure and needs to be shielded from out-of-band energy. A ground-backed absorber (one that prints its own reflector, so nothing gets through it) has `S₂₁ = 0` at every frequency, in-band or out — true of this project's own designs by default (`docs/adr/0017-printed-reflector-default-not-host-ground-plane.md`) — so there is no transmitted wave for a roll-off-rate calculation to be *about*. The physical question #110's off-band decision is actually asking is different: **does the candidate reflect (correctly) or absorb (incorrectly) the frequencies just outside its required band** — a reflectivity/absorptivity question, not a transmission-rejection one. Roll-off rate and transition bandwidth are well-posed for the quantity filters and rasorbers care about; nothing found in this search applies that math, or anything resembling it, to an absorber's off-band absorptivity. The resemblance between "skirt" and "off-band absorption behaviour" is a resemblance of vocabulary, not of physics.

### 3.2 Thread B — informal off-band margins in RAM literature: one real data point, one near-miss, no convention

One RAM paper reports a specific, if unintended and informal, degradation zone between two design bands:

> "The absorption band of the fabricated 5 mm thick nanocomposite covers the full measured frequency band (2–18 GHz, 26.5–40 GHz) below −10 dB, except for the range of 5.7–7.6 GHz (below −9 dB)"
> — as summarized from Q. F. Fan, X. Z. Yang, H. S. Lei, Y. Y. Liu, Y. X. Huang & M. J. Chen, *Gradient nanocomposite with metastructure design for broadband radar absorption*, [Composites Part A 129, 105698 (2020)](https://www.sciencedirect.com/science/article/abs/pii/S1359835X19304476) — *ScienceDirect, paywalled; retrieved via WebSearch synthesis only, not independently verified against the primary PDF.*

This is the closest thing found anywhere to a real, published off-band number — but it is a **gap between two intended absorption bands falling slightly short of the same −10 dB threshold**, not a scored margin *outside* a single required band, and it was not designed as a metric; it is one reported fact in one paper's characterization, not a convention anyone else has repeated.

**A genuine near-miss, worth recording precisely so the resemblance is not mistaken for a hit.** Multi-band terahertz absorber design has a real, quantitative, percentage-based frequency-separation metric:

> "△ = 2(f₂ − f₁)/(f₁ + f₂)"
> — B. X. Wang, C. Tang, Q. Niu, Y. He & T. Chen, *Design of Narrow Discrete Distances of Dual-/Triple-Band Terahertz Metamaterial Absorbers*, [Nanoscale Research Letters 14, 64 (2019)](https://doi.org/10.1186/s11671-019-2876-3), [PMC6386755](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6386755/), verbatim (with `f₁`, `f₂` the frequencies of two neighbouring absorption peaks), reported as **13.33%** for their dual-band design and **6.57%/7.22%** for their triple-band design

This "relative discrete distance" is mathematically the same *shape* as #110's proposed margin — a frequency difference normalized to a reference frequency, expressed as a percentage — which is exactly why it is worth being precise about the mismatch: **it measures the gap between two bands the design *wants* to absorb in, and the paper explicitly optimizes to make it *smaller*** ("Δ can be tuned... compared favourably against previous minimum values"). #110's off-band margin is the opposite goal — a region the design does *not* want to absorb in, where a *larger* margin of correctly-low absorptivity is better. Same formula shape, opposite objective. This is not adoptable, but it is worth naming precisely, because "a percentage-of-frequency margin exists in multi-band absorber literature" is true and misleading in the same sentence unless the sign is made explicit.

### 3.3 A related null: "isolation between bands" is not a defined quantity either

Searching directly for a dB-defined "isolation between absorption bands" — the antenna-engineering analogue of skirt selectivity — returned nothing standardized. What multi-band absorber papers report instead is **shielding effectiveness (dB)** *at* each resonant peak (e.g. "49.02 dB and 56.65 dB" at two peaks in one dual-band EMI-shielding design) and **reflection-loss dip depth (dB)**, also *at* each peak — never a quantity characterizing the region *between* peaks or past a band's edge. This reinforces, rather than duplicates, §3.2's finding: the field instruments its bands, not its gaps.

### 3.4 What was searched and came up empty

Beyond §3.1–3.3: `"guard band"` and `"transition band"` directly against RAM design papers (returned nothing using that terminology in an absorber context — only the filter/FSS usage in §3.1); `"out-of-band"` scoring specifically for frequency-selective *absorptive* surfaces (rasorbers), which combine absorption and transmission in one structure and so seemed like the most likely bridge — found only transmission-side roll-off numbers (§3.1), never an absorptivity-side out-of-band number; and a direct search for any RAM paper stating a percentage-of-bandwidth or fixed-frequency-offset margin used when characterizing (not just plotting) absorber performance outside a stated band, which returned nothing beyond the two data points in §3.2.

### 3.5 Local corpus check

`F:\data\arxiv-chunks\` grep for `"skirt selectivity"` and `"roll-off rate"` co-occurring with `"absorber"` returned **zero hits**. `"guard band"` and `"transition band"` co-occurring with `"radar absorbing"` or `"frequency selective surface"` also returned **zero hits**. Consistent with the documented coverage gap — no genuine negative literature finding available from this corpus, only the expected null.

### 3.6 What this means for #110

The instinct behind the decision — off-band behaviour deserves a real, separate accounting, not silence — has no literature convention to either confirm or borrow from, and now for a specific reason worth carrying forward: **the one field with a mature, quantitative off-band vocabulary (filters/FSS/rasorbers) is measuring a different physical quantity (transmission) than the one #110 cares about (absorptivity)**, so importing its math would be importing the wrong formula dressed in the right-sounding words. The one genuinely close mathematical shape found (§3.2's relative discrete distance) optimizes in the opposite direction from what #110 wants. This remains a decision, not a lookup — but it is now a decision made with the dead ends mapped, which is what the task asked for.

---

## 4. Incidence angle as a continuous sliding scale over a curvature-derived range — CONTRADICTED

**What was decided:** score incidence angle as a continuous sliding scale across a swept range of angles, with the range derived from the actual curvature of whatever surface the absorber mounts on — replacing the field's usual pass/fail-at-a-couple-of-benchmark-angles convention.

**What this pass found, searching conformal/curved/flexible/wearable absorber papers specifically** (the subfield most likely to have precedent, since a curved host inherently sees a continuous range of local incidence angles rather than a couple of discrete test points): **the conformal-absorber literature still uses discrete benchmark-angle testing and discrete threshold-retention reporting, the same convention the prior document found in flat-panel work (§7.1).** No paper found treats an absorption-vs-angle curve as a scored (integrated or averaged) quantity, and no paper found derives its test-angle range from an explicit curvature-to-angle formula.

### 4.1 The closest partial precedent — curvature informs the *design*, not the *score*

> "we have designed three different unit cells, which are optimized at 0°, 30°, and 45° incident angles" placed in "three different zones (zones A, B, and C) on the curved surface"
> — Jang, Y., Yoo, M. & Lim, S., *"Conformal metamaterial absorber for curved surface,"* Optics Express 21(20):24163–24170 (2013), [doi:10.1364/OE.21.024163](https://doi.org/10.1364/OE.21.024163), verbatim, extracted directly from the PDF

This paper explicitly maps unit-cell design targets to physical zones on a surface bent to a stated radius (R = 15 cm, a 41×10 unit-cell array) — a genuine link between physical curvature and what gets designed. **But the design targets inside each zone are still the conventional discrete benchmarks (0°/30°/45°), not a continuum, and no equation relating radius to a swept angle range appears anywhere in the paper.** The zone map is presented as a picture, not an algebraic derivation.

More tellingly, the paper's headline scored result reduces a fully continuous bistatic-RCS sweep (bistatic means the receiver measuring the reflection sits off to the side of the transmitter, not looking straight back the way a normal radar return does — so the sweep is over receiver angle, not just illumination angle) it already has in hand (θ from −80° to 80°, Fig. 4) down to single broadside (θ=0°) point comparisons: "the RCS of the proposed absorber is 11.4 dB lower [than a flat metal plate] at 0°" and "4.6 dB lower [than a uniform-cell absorber] at 0°." The continuous curve is plotted and discussed in prose ("the uniform unit cell has slightly better RCS reduction effect... for the angles from 30° to 50°") but never reduced to an integrated or averaged score. Its measured angular sweep is likewise reported at discrete points (0°, 10°, 20°, ..., 60°): "The reflection coefficient is less than −10 dB from 0° to 60° except for 20° and 40°" — a discrete-angle retention statement, identical in form to the flat-panel convention already documented.

### 4.2 Two more curved-surface papers checked, same result

> "The electric field distribution and power loss density for the incident angles of 10°, 30° and 60° at 220 GHz are shown in Figs. 9 and 10."
> — Norouzi, M. et al., *"3D metamaterial ultra-wideband absorber for curved surface,"* Scientific Reports 13:1043 (2023), [doi:10.1038/s41598-023-28021-4](https://doi.org/10.1038/s41598-023-28021-4), PMC9852439, verbatim

This paper validates on a "copper semi-cylinder with a radius of 10 cm" but never connects that radius mathematically to the oblique angles it tests (10°/30°/60°, conventional benchmarks, disconnected from the stated radius).

> "maintains over 90% absorption efficiency... near 50° oblique incidence at 8 GHz" ... "up to 50° for TE polarization and 60° for TM polarization"
> — Tan, R., Zhou, J. & Chen, P., *"Chainmail-inspired conformable and switchable microwave metamaterial absorber,"* Nature Communications 17 (2026), [doi:10.1038/s41467-026-68694-9](https://doi.org/10.1038/s41467-026-68694-9), PMC12923583

The most recent and most squarely on-topic paper found — 2026, explicitly framed around angular sensitivity in curved conformal applications as a named problem it solves — and it still reports angular performance only at discrete points/thresholds, and does not derive its angle-test range from the bending radius used in its own cylindrical/saddle-surface validation (that validation is empirical — measure before and after conformal shaping — not geometry-derived). Its one genuinely "averaged" headline number ("average absorptivity decreased by only 0.049" after conformal shaping) is a **frequency-band average**, not an angle-integrated score — a different axis entirely. *Caveat: this figure was retrieved via an AI-summarized fetch of the PMC page rather than direct PDF extraction, so treat the exact wording, though not the substance (corroborated across two independent search-result summaries), as secondary-source-level confidence.*

### 4.3 A genuinely continuous angular curve exists — but it is off-topic

> "Figure 6 shows the average absorbance of the optimized absorber made by W over the wavelength range 400–1,200 nm as a function of incident angles θ. The averaged absorbance is above 90.0% over the incident angle range 0-66 degree. The averaged absorbance sharply drops by increasing θ beyond 66 degree."
> — Tapsanit, P. & Ruttanapun, C., *"Quasi-analytical solutions of wide-angle and broadband insulator-metal grating-metal metamaterial absorber in visible to near-infrared bands,"* [arXiv:1707.06515](https://arxiv.org/abs/1707.06515), §D, verbatim, extracted directly from the PDF

This is the one source found anywhere in this pass where a continuous θ-sweep is genuinely computed and plotted, not just sampled at a handful of points. But it disqualifies itself from being precedent for #110's decision on two counts: **(1)** it is a flat, planar absorber, not conformal or curved — the wide-angle requirement comes from solar-collection angle diversity (the sun moves), not from mounting on a curved host; **(2)** even here, the headline claim is reduced right back to a threshold-retention sentence ("above 90% over 0–66°"), not an integrated or averaged score. It is useful negative evidence in a specific sense: it shows continuous angular *reporting* is not physically or conventionally impossible in this literature — the field simply never does it for curvature reasons, and never turns it into one scored number even when the continuous curve is already sitting right there in the plot.

### 4.4 Adjacent methodology that does compute continuous local angle from curvature — wrong problem, though

Ray-tracing / physical-optics hybrid methods for RCS prediction of RAM-coated curved bodies (e.g. a hybrid PO/ray-tracing method, IEEE Xplore document 8568234; the "pRediCS" GO-PO ray-launching simulator) genuinely compute local incidence angle as a continuous function of position across a curved target via ray geometry, feeding it into a scattered-field/RCS prediction. This is the closest real-world engineering analog to "derive the angle range from curvature" found anywhere in this pass — but it belongs to system-level RCS prediction for a whole target shape, not to absorber-material scoring, and it does not produce anything resembling an absorber success score. Noted for completeness, not adopted as precedent.

### 4.5 Local corpus check

`F:\data\arxiv-chunks\` grep for `"conformal absorber"`, `"flexible metamaterial"`, `"metamaterial absorber"` returned **zero hits**. `"angular stability"` returned 3 hits, all unrelated 2007-era particle-physics papers. **Genuine coverage-gap null**, consistent with the documented absence of `physics.app-ph`/`eess.SP` categories.

### 4.6 What was searched and came up empty (for the next person)

Beyond the papers above: resistor-loaded conformal absorber work (ScienceDirect, paywalled, only a search snippet available: "wrapped on different cylindrical curved surfaces... above 90% absorptivity... demonstrating angle/curvature-dependent robustness" — secondary summary only, exact wording unverified), and a Wiley conformal dual-band absorber paper (Kalraiya et al. 2019, referenced only via search snippet, not fetched). Neither changes the verdict; both would need primary-text access to check, and neither snippet suggests a continuous scoring convention.

**Honesty check on the verdict.** What was found (Jang et al. 2013) is real curvature-informed *design* — zone placement tied to physical position on a bent surface — but not curvature-derived continuous *scoring*. The design still targets the same 0°/30°/45° conventional benchmarks as flat-panel literature, and every reported performance number in every curved-surface paper checked is a discrete point or a discrete-threshold retention statement, never an integrated or averaged angular figure of merit. **The decision to score angle as a continuous sliding scale over a curvature-derived range remains a genuinely novel choice — nothing found in this pass gives #110 a citation for "score = integral of absorption over swept incidence angle."**

---

## 5. Example 3's reproduction judged by RMS error in dB — CONTRADICTED

**What was decided:** judge the reproduction of the patent's Example 3 (matched against Landy et al. 2008's measured published curve, [arXiv:0803.1670](https://arxiv.org/abs/0803.1670), PRL 100:207402) by a curve-agreement statistic — specifically RMS error in decibels across the matched frequency band — as a mechanism entirely separate from real-design scoring.

The prior document (§8) already searched the broad "simulated vs. measured absorber" literature and found nothing quantitative — prose only ("in good agreement"), no correlation coefficient, no RMS error, no tolerance, anywhere. This pass narrowed to two things the prior pass did not check: (A) papers whose specific point is reproducing someone else's already-published design — the project's actual situation — and (B) the broader EM-solver-validation/reproducibility literature, to establish whether "RMS error in dB" has *any* real precedent even outside absorber papers specifically.

### 5.1 The narrow question: nobody reproduces Landy 2008's curve with a statistic

No paper was found whose whole point is reproducing Landy et al. 2008's specific published curve with a quantitative agreement statistic. Every citing paper checked either uses Landy 2008 purely as historical motivation with zero quantitative comparison (e.g. [arXiv:2504.14901](https://arxiv.org/html/2504.14901v1), "Inverse design of ultrathin metamaterial absorber," confirmed by direct fetch — cites Landy only in the introduction, its own validation compares against its own baseline, not Landy's curve), or repeats exactly the isolated-scalar-point pattern the prior document already found. Two more such isolated point comparisons on the Landy paper itself turned up (secondary-source synthesis, not independently re-verified against the primary PDF per the task's instruction not to repeat that search): "the measured reflectance is consistently 8% lower than the simulated R(ω) at low frequencies," and "both curves reach a minimum near 11.5 GHz, but experimentally the minimum is 11%, against a simulated 3%." **This confirms and extends the prior pass's finding rather than contradicting it — there is still nothing in this specific literature to adopt.**

### 5.2 The broadened question: what does the field actually use when it does report a number — and it directly contradicts "RMS error in dB" as a default

**A real, formal standard exists for exactly this comparison problem, and it is not RMS error.**

> IEEE Std 1597.1-2008 (revised 2022), *"Standard for Validation of Computational Electromagnetics Computer Modeling and Simulations,"* with companion practice IEEE Std 1597.2-2010 — the standard embodying the **Feature Selective Validation (FSV)** method, "applicable to a wide variety of electromagnetic applications including electromagnetic compatibility, radar cross section, signal integrity, and antennas, with validation achieved by comparison to data sets obtained by measurements, alternative codes, canonical methods, or analytic methods."
> — corroborated consistently across independent secondary sources (ResearchGate abstracts of the original Duffy & Orlandi "FSV Parts I & II" papers, IEEE Xplore standard listings, an MDPI abstract, an ARMMS industry paper); confirmed to exist and be correctly characterized by an independent verification search run for this document. **`LITERATURE-SUPPORTED` — the primary standard text is IEEE-paywalled and was not read; the method's structure is corroborated across five-plus independent sources describing it consistently, the same evidentiary bar the prior document used for the Rozanov citation.**

FSV works by **decomposing each curve into a trend component and a feature component, and scoring the two separately, rather than averaging the pointwise gap into one number the way RMS error does:**

- **ADM (Amplitude Difference Measure)** — from the low-pass-filtered ("trend") component of each curve, "the normalized difference of the low pass data... can be represented as a point-by-point graph or as a single goodness-of-fit value by taking an average over the domain."
- **FDM (Feature Difference Measure)** — from the high-frequency ("feature," i.e. rapidly-varying/resonant) component, via wavelet or Fourier decomposition, capturing "differences related to fast-moving features in the data."
- **GDM (Global Difference Measure)** = √(ADM² + FDM²), an overall goodness-of-fit.
- Each is then binned into a six-level qualitative descriptor (Excellent/Very Good/Good/Fair/Poor/Very Poor) and summarized as **GRADE** (quality) and **SPREAD** (confidence in that judgment).

**In plain terms.** RMS error in dB averages the gap between two curves at every frequency point into one number. FSV deliberately splits the question in two instead: "do the two curves have the same overall shape" (ADM) and "do the sharp resonant dips line up in the right place" (FDM) — because a small frequency shift in a sharp resonance (exactly the kind of shift a reproduced absorber curve is likely to show, per the prior document's own §8 finding of frequency-shift discrepancies in the Landy comparison) can produce a large pointwise RMS number even when an engineer looking at the two curves would call them "basically the same shape, just shifted a bit." FSV was built specifically because naive point-by-point differencing does not track that engineering judgment for oscillatory, resonance-shaped EM data — which is precisely the shape of a reflection/absorption curve near a resonance, i.e. precisely Example 3's situation.

**Where informal reproduction papers report a number at all, it is a simple percent difference at one or two discrete points — not a whole-band statistic of any kind, RMS or otherwise.** The clearest same-shape analog found (a numeric model reproducing someone else's already-published curve, no fresh measurement — the same situation as Example 3, though in acoustics rather than RF) reports resonance frequency and absorption-coefficient percent differences separately, not a combined whole-band error: 164 Hz vs. 166 Hz (1.2%) and 0.82 vs. 0.99 (16.9%) ([arXiv:2309.09852](https://arxiv.org/abs/2309.09852), "Investigations of Helmholtz Resonators with Curved Tapered Embedded Neck Extension" — *numbers reported via search-engine synthesis of the paper, not independently confirmed against a clean PDF extraction; treat as secondary-source-level confidence*). This matches the "band-edge and depth agreement" option the prior document's §12 already named as an alternative to inventing a whole-curve metric — not RMS error, but not nothing either.

**RMS error in dB is not fabricated from nothing — it has real precedent, just not for this kind of curve.** A separate solver-validation paper in EM propagation modeling does report RMS error in dB: 43.4 dB reduced to 9.9 dB between simulated and measured path loss ([arXiv:2406.08082](https://arxiv.org/abs/2406.08082), "Bridging Simulation and Measurements through Ray-Launching Analysis" — *numbers reported via search-engine synthesis, not independently confirmed*). That confirms RMS-in-dB is a real, used metric somewhere in electromagnetics — but applied to received-signal/path-loss data in urban propagation modeling, a smoothly-varying quantity with none of a resonance's sharp features, and comparing a fresh measurement against a fresh simulation rather than reproducing someone else's already-published design. It does not transfer cleanly to a reflection-coefficient curve with a resonant dip in it.

A separate solver-vs-solver validation ([arXiv:2407.10273](https://arxiv.org/html/2407.10273), "Quantized Inverse Design for Photonic Integrated Circuits," confirmed by direct fetch: "Our solver is able to predict the field distribution to a normalized L1 error of 2.1%") shows a whole-field percentage-error convention exists too — again neither RMS nor expressed in dB, and applied to a field distribution rather than an S-parameter curve.

Several other adjacent validation papers checked report no quantitative metric at all beyond "good agreement" prose (ARTEMIS solver validation, [arXiv:2208.04371](https://arxiv.org/abs/2208.04371); the WIPL-D benchmark suite, which explicitly never specifies a comparison metric on its own benchmark page) — reinforcing that the field genuinely treats this as unsettled or problem-dependent, not that a hidden standard was missed. One review paper comparing open-source and commercial EM solvers explicitly declines to commit to a single comparison metric, stating (per search-engine synthesis of an MDPI paper, Electronics 8(12):1506) that solver comparison "should be primarily compared based on computational or result quality merits, which are often problem-dependent" — itself informative: even a paper devoted to solver comparison treats the choice of agreement metric as inherently problem-dependent, not standardized.

### 5.3 Local corpus check

Grepped `F:\data\arxiv-chunks\` directly and inspected matches, not just counted them: `"Landy"` returned 44 hits, but every one inspected is the unrelated **Landy & Szalay (1993)** two-point correlation-function estimator from astrophysics — a surname coincidence, not Nathan Landy's 2008 metamaterial absorber paper. `"metamaterial absorber"` and `"perfect metamaterial"` returned **zero hits**. `"root mean square"` co-occurring with `"reflectivity"`/`"S11"`/`"S-parameter"` returned 7 hits, all unrelated physics (astro-ph, cond-mat, gr-qc, hep-ph). A search for reproduction-of-absorber phrasing matched only the unrelated 2026 CS/ML batch (verified by inspection: one hit was "...to **absorb** knowledge about diagnoses..." in a medical-ML paper — a different sense of the word "absorb" entirely). **Genuine, verified coverage-gap null** — Landy 2008 sits right at the edge of the corpus's 2007-heavy window but is not actually present, and the corpus has no `physics.app-ph`/`eess.SP` category to catch its citing literature either.

### 5.4 What this means for #110

**Two known follow-ups landed after this pass was written, neither folded into the verdict below — read them before acting on it.**

1. **Example 3 itself is two-port, not ground-backed.** A 2026-09-05 research pass (`docs/grilling-pass-2026-09-05.md` §3, map #104's Notes) found that Example 3 lets some signal pass through rather than fully blocking it — unlike this project's own designs, which really are ground-backed by default (`docs/adr/0017-printed-reflector-default-not-host-ground-plane.md`). This document was written before that correction landed. Whichever curve-agreement method §5.4 recommends has to compare the full absorption quantity `A = 1 − |S₁₁|² − |S₂₁|²` (both the reflected *and* the transmitted power) for Example 3's reproduction check specifically — never a bare reflectance curve, which is only valid for a ground-backed design.
2. **FSV's own justification for being preferred over RMS still needs checking, not just implementing.** Issue #168 already exists to pin down FSV's exact implementation (the ADM/FDM/GDM formulas, the six-level grading bins, how GRADE/SPREAD fits the rest of `success_score.py`). But issue #116's 2026-09-05 research pass raised an uncountered challenge to the *reason* FSV was chosen at all: Landy's own resonance is only 4% wide (FWHM — full width at half maximum, the standard way to state how narrow a resonance peak is), so the ~20–25% frequency offset between the patent and Landy's curve is roughly **five resonance-widths apart** — the two curves barely overlap. A feature-matching method like FSV may report near-total disagreement just as bluntly as RMS error would in that situation, which would undercut the stated reason for preferring it over RMS in the first place. This needs resolving on #168 before an implementation is built on the assumption that FSV is settled.

With those two caveats on record: do not present "RMS error in dB" as something the literature already does, because it is not — neither in the narrow Landy-reproduction literature (confirmed empty, same as the prior pass) nor in the broader solver-validation literature this pass added (which is not empty, and what it contains is not RMS-in-dB). Three honest options, in order of how literature-grounded they are:

1. **Adopt FSV (IEEE Std 1597.1/1597.2).** The actual standard for exactly this problem — but its primary text is paywalled and unread here, and it is considerably more complex to implement than RMS error (wavelet/Fourier decomposition into trend and feature components, six-level qualitative binning, a GRADE/SPREAD summary rather than one number).
2. **Adopt the informal convention that actually shows up when reproduction papers report anything at all.** Percent difference at the resonant frequency and at the peak/minimum depth, reported separately — matching the prior document's §12 "band-edge and depth agreement" alternative.
3. **Keep RMS error in dB, but as a disclosed engineering decision, not a literature-derived one.** It is defensible on its own merits (simple, matches the project's dB-native reflection data, and has genuine — if indirect — precedent in adjacent RF-propagation solver validation), but the honest label is "decision," exactly as the prior document's §12 already framed this whole area: must be decided, not looked up. The one caution worth carrying forward from §5.2: a pointwise RMS-in-dB statistic can penalize a small resonance-frequency shift heavily even when an engineer would call the two curves a good match, which is the specific failure mode FSV was built to avoid.

---

## 6. Stranded — paywalled or unreachable sources, and what was tried

- **IEEE Xplore.** Weile, Michielssen & Goldberg 1996 (the foundational GA-minimax absorber paper, §1.2); Michielssen, Sajer, Ranjithan & Mittra 1993; Toktas, Ustun & Tekbas 2019; Toktas & Ustun 2020; and — separately — **IEEE Std 1597.1-2008/2022 and IEEE Std 1597.2-2010 themselves** (the FSV standards, §5.2), plus the original Duffy & Orlandi "Feature Selective Validation (FSV) for Validation of Computational Electromagnetics (CEM), Part I and Part II" theory papers. All read only through consistent secondary-source description, never the primary text — the same pattern as the prior document's treatment of Rozanov 2000 and IEEE Std 1128.
- **academia.edu.** HTTP 403 on an "Optimised design of Jaumann RAM using a GA" paper, a reposted copy of Weile 1996, and the Duffy & Orlandi FSV papers.
- **ResearchGate.** HTTP 403 on ABC-algorithm and PSO-RAM full-text PDF links, and on a Jang et al. 2013 mirror (not needed — the primary Optics Express PDF was fetched successfully instead).
- **ScienceDirect / Elsevier.** A resistor-loaded conformal absorber paper (§4.6) and the FFad/FFavg Ti-pyramid PSO solar-absorber paper (§1.3) — abstract/search-snippet level only.
- **Wiley.** A conformal dual-band absorber paper, Kalraiya et al. 2019 (§4.6) — search-snippet level only.
- **MDPI.** *Photonics*, an inverse-electromagnetic-parameter RAM design paper (NSGA-II-based) — returned HTTP 403 directly and, unlike the MDPI journals the prior document relied on, has **no PubMed Central mirror** found. Also, Bongiorno & Mariscotti, *"Uncertainty and Sensitivity of the Feature Selective Validation (FSV) Method,"* MDPI Electronics 11(16):2532 (2022) — downloaded successfully via an institutional-repository mirror, but its PDF text layer is compressed in a way the fetch tooling could not extract (a technical extraction failure, not a paywall; no local PDF-image fallback was available in this environment).
- **NASA NTRS.** Hall (2004), NASA/CR-2004-212669, *"A Novel, Real-Valued Genetic Algorithm for Optimizing RAM"* — PDF downloaded but its objective function could not be extracted from the garbled text layer.
- **ScienceDirect / Elsevier (item 3).** Q. F. Fan et al., *Gradient nanocomposite with metastructure design for broadband radar absorption*, Composites Part A 129, 105698 (2020) (§3.2) — abstract/search-snippet level only, not independently verified against the primary PDF.
- **General filter-theory reference (item 3).** The `20n dB/decade` roll-off-rate formula (§3.1) is standard filter-design textbook material, sourced here from a general engineering-reference site rather than a primary paper — flagged at secondary-source-level confidence, not because the fact is in doubt but because the specific source consulted is not primary literature.
- **Nature.com.** Direct URLs for both curved-surface absorber papers in §4.2 redirected to an authentication wall; both were reached instead through their open-access PMC mirrors (PMC12923583, PMC9852439) — consistent with the prior document's finding that Nature/Scientific Reports content is generally recoverable through PMC.
- **A general PDF-extraction note for future passes.** Several downloads in this pass (an ARMMS conference paper on FSV, an IBIS/APEMC 2010 FSV session paper, a Semantic Scholar-hosted solver-comparison review, ARTEMIS solver validation) failed to yield readable text even after a successful download — a binary/compressed-stream extraction failure distinct from a 403 paywall block. Where this happened, re-fetching and re-reading the saved local file directly (rather than relying on the web-fetch tool's built-in summarizer) sometimes recovered the text and sometimes did not; no local PDF-to-image renderer was available in this environment as a further fallback.

---

## Sources

**New in this pass — optimization objective (item 1)**
- E. Yiğit & H. Duysak, *Fully Optimized Multilayer Radar Absorber Design Using Multi-Objective ABC Algorithm*, [IJEG 6(3):136–145 (2021)](https://dergipark.org.tr/en/pub/ijeg/issue/59600/743661), doi:10.26833/ijeg.743661 — minimax objective, Eq. 1; explicit argument against averaging.
- D. S. Weile, E. Michielssen & D. E. Goldberg, *Genetic algorithm design of Pareto optimal broadband microwave absorbers*, IEEE Trans. EMC 38(3):518–525 (1996), doi:10.1109/15.536085 — cited, not read.
- E. Michielssen, J.-M. Sajer, S. Ranjithan & R. Mittra, *Design of lightweight, broad-band microwave absorbers using genetic algorithms*, IEEE Trans. MTT 41(6):1024–1031 (1993) — cited, not read.
- A. Toktas, D. Ustun & M. Tekbas, *Multi-Objective Design of Multi-Layer Radar Absorber Using Surrogate-Based Optimization*, IEEE Trans. MTT 67(8):3318–3329 (2019), doi:10.1109/TMTT.2019.2922600.
- A. Mayer et al., *Genetic-algorithm-aided ultra-broadband perfect absorbers using plasmonic metamaterials*, [arXiv:2108.09377](https://arxiv.org/abs/2108.09377) (2021), doi:10.1364/OE.442405 — the mean/integrated counter-example.

**New in this pass — angular scoring (item 4)**
- Y. Jang, M. Yoo & S. Lim, *Conformal metamaterial absorber for curved surface*, Optics Express 21(20):24163–24170 (2013), doi:10.1364/OE.21.024163 — closest partial precedent.
- M. Norouzi et al., *3D metamaterial ultra-wideband absorber for curved surface*, [Scientific Reports 13:1043 (2023)](https://doi.org/10.1038/s41598-023-28021-4), PMC9852439.
- R. Tan, J. Zhou & P. Chen, *Chainmail-inspired conformable and switchable microwave metamaterial absorber*, [Nature Communications 17 (2026)](https://doi.org/10.1038/s41467-026-68694-9), PMC12923583.
- P. Tapsanit & C. Ruttanapun, *Quasi-analytical solutions of wide-angle and broadband insulator-metal grating-metal metamaterial absorber*, [arXiv:1707.06515](https://arxiv.org/abs/1707.06515) — genuine continuous angular curve, off-topic (flat, not curved).

**New in this pass — curve-agreement statistic (item 5)**
- IEEE Std 1597.1-2008/2022 & IEEE Std 1597.2-2010, *Standard/Recommended Practice for Validation of Computational Electromagnetics Computer Modeling and Simulations* (Feature Selective Validation) — cited, not read.
- [arXiv:2504.14901](https://arxiv.org/html/2504.14901v1), *Inverse design of ultrathin metamaterial absorber* — checked, no quantitative Landy comparison.
- [arXiv:2309.09852](https://arxiv.org/abs/2309.09852), *Investigations of Helmholtz Resonators with Curved Tapered Embedded Neck Extension* — same-shape replication-study analog (acoustics).
- [arXiv:2406.08082](https://arxiv.org/abs/2406.08082), *Bridging Simulation and Measurements through Ray-Launching Analysis* — RMS-in-dB precedent, different context.
- [arXiv:2407.10273](https://arxiv.org/html/2407.10273), *Quantized Inverse Design for Photonic Integrated Circuits* — whole-field L1-error precedent, confirmed by direct fetch.
- [arXiv:2208.04371](https://arxiv.org/abs/2208.04371), ARTEMIS solver-validation paper — checked, no quantitative comparison metric beyond "good agreement" prose.
- WIPL-D benchmark suite (public benchmark page, no formal citation available) — checked, explicitly never specifies a comparison metric on its own page.
- MDPI *Electronics* 8(12):1506 (open-source vs. commercial EM solver comparison review) — *numbers reported via search-engine synthesis, not independently confirmed* — explicitly declines to commit to one comparison metric, treating the choice as problem-dependent.

**New in this pass — off-band scoring (item 3)**
- Quad-band highly-selective FSS paper, [Micromachines 15(1), 126 (2024)](https://doi.org/10.3390/mi15010126), [PMC10821369](https://pmc.ncbi.nlm.nih.gov/articles/PMC10821369/) — transition-bandwidth definition (−3 dB to −20 dB); the real quantitative filter/FSS concept, scoring the wrong physical quantity for an absorber (§3.1).
- Q. F. Fan, X. Z. Yang, H. S. Lei, Y. Y. Liu, Y. X. Huang & M. J. Chen, *Gradient nanocomposite with metastructure design for broadband radar absorption*, [Composites Part A 129, 105698 (2020)](https://www.sciencedirect.com/science/article/abs/pii/S1359835X19304476) — the one informal off-band-adjacent data point found (§3.2), Stranded.
- B. X. Wang, C. Tang, Q. Niu, Y. He & T. Chen, *Design of Narrow Discrete Distances of Dual-/Triple-Band Terahertz Metamaterial Absorbers*, [Nanoscale Research Letters 14, 64 (2019)](https://doi.org/10.1186/s11671-019-2876-3), [PMC6386755](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6386755/) — the "relative discrete distance" near-miss, verbatim formula confirmed by direct fetch, §3.2.

**Carried forward from `docs/absorber-scoring-conventions.md`** — see that document's own Sources section for the full list (Rozanov bound, Huynen 2022, Landy et al. 2008, IEEE Std 1128, and the RAM/metamaterial reporting-convention papers).
