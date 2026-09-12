# The horseshoe sample in Ludvig-Osipov et al. (2020) is not the Fig. 6 optimised design — and nothing published says why

**Date:** 2026-09-12
**Ticket:** [#552](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/552) (horseshoe half; cross-potent half done in [#554](https://github.com/parthalon025/Principle_RF_Engineer_Agent/pull/554)); follows [#547](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/547). Companion to `docs/bandpass-fss-physical-bound-primary-source.md`.
**Question:** The paper's manufactured horseshoe sample (Sec. VI: `l = 6.57 mm, a = 3.43 mm, w1 = 0.3 mm, w2 = 0.06 mm`) has different normalised proportions from its Fig. 6 optimised design (`l = 1.43a, w1 = 0.049a, w2 = 0.0047a`). Does the paper, its journal version, an erratum, or any follow-up by the same group explain this? And is a static polarizability `γ` for the horseshoe stated anywhere?

*In plain terms: the paper designs one slot shape on the computer, then builds and measures a slot of the same shape but noticeably different proportions, and reports the built one as confirming the designed one. This note checks whether anyone — the authors, the journal, a later thesis — ever said why the two differ.*

---

## Bottom line up front

1. **The mismatch is real, and no published source explains it.** The arXiv v3 text, the journal reprint carried in Lundgren's 2021 Lund thesis (word-for-word identical in every load-bearing sentence, §4.1), Crossref's record (no correction relations), arXiv's version history (v3 is the last, no v4), and every citing work findable contain **no sentence** giving a reason for the manufactured dimensions. The closest the paper comes is one sentence in its Conclusions: *"The choice of frequency band was selected to fully utilize the range of the experimental equipment"* (p. 8) — which explains the absolute *scale* (`a = 3.43 mm` puts the resonance at 13.5 GHz, inside the 12.4–18 GHz horns), not the changed *proportions*.

2. **The paper's two headline percentages are about two different designs and two different references, and the paper juxtaposes them without saying so.** "96% of the attainable bandwidth" (p. 6) is the Fig. 6 *optimised* design versus the Eq. (12) *sum-rule bound*. "98% of the available bandwidth of a PEC-based structure" (p. 7) is the *measured* sample versus a *PEC simulation of the same sample* (Fig. 8/11) — **not** versus the bound. The fraction of the sum-rule bound that the manufactured sample achieves is **never stated**, and no `γ` for any horseshoe is stated anywhere in the paper (§5).

3. **The manufactured sample is a materially narrower-band design than either Fig. 6 curve.** Read off Fig. 6 (pixel-calibrated, §3.2): optimised main band ≈ 10.2 % fractional bandwidth at `λ/l ≈ 4.67`; non-optimised ≈ 8.1 % at `λ/l ≈ 3.28`. The measured sample: **5.83 %** at `λ0/l = 3.375` (stated 13.52 GHz, stated `l`). It is not the optimised design scaled; it is a third design point.

4. **A quantitative reconstruction exists, but it is this note's inference, not the paper's statement** (§6, labelled `INFERRED`/`CALCULATED`): at `a = 3.43 mm` the optimised `w2 = 0.0047a` is **16 µm** — thinner than the 18 µm foil (`w2/d = 0.9`, the regime the paper's own Sec. V says makes the bound "not tight") and at the LPKF ProtoLaser U3's 15 µm focused-beam diameter. Widening the slots to buildable widths (`0.3 / 0.06 mm`) and then re-choosing the period to hold the paper's `α = 5 %` constraint lands at `l = 6.68 mm` — within 2 % of the stated 6.57 mm. This *fits*; it is not *confirmed*.

5. **Consequence for #552:** the horseshoe reproduction as originally specified (paper-stated absolute bandwidth + paper-stated fraction-of-bound for one geometry) is **not possible from this paper** — no such pair of numbers exists for any single horseshoe design. Two weaker but honest checks are available (§7). Separately, `tests/test_physical_bounds.py:424` currently paraphrases the "98 %" as *"98% of the Eq. (12) bound"*; the primary text does not say that, and the docstring should be corrected (§7).

---

## 1. What was read, and what was not

House rule (`CLAUDE.md`): a claim attributed to a source must be something actually read and quotable, never a search-engine paraphrase.

| Source | Status |
|---|---|
| Ludvig-Osipov et al., arXiv:1810.07669v3 (5 Aug 2019), all 10 pages | **READ IN FULL** — page renders `perf_p1..p10.png` re-read for this note; Fig. 6 and its inset re-rendered at 300 dpi and pixel-calibrated |
| Same paper, IEEE TAP 68(2):773–782, doi:10.1109/TAP.2019.2943430 — the typeset journal version | **NOT READ** — IEEE Xplore (document 8852810, confirmed via the DOI redirect) renders empty to the fetcher and its REST metadata endpoint returns the site shell; paywalled. **Nothing below is attributed to the typeset journal text** |
| Crossref record for the DOI | **READ** — bibliographic fields; no `update-to`/`updated-by`/erratum relation present |
| arXiv abstract page (submission history) | **READ** — v1 17 Oct 2018, v2 22 May 2019, v3 5 Aug 2019 ("Updated Introduction and Conclusions"); no later version |
| J. Lundgren, *Design of Functional Structures and Measurement Techniques for Electromagnetic Waves*, PhD thesis, Lund University, 2021 (LUP record `fa6ec3eb-…`, open PDF, 281 pp.) | **READ IN PART** — Part I §3 (pp. 21–23, incl. Fig. 8), Part I pp. 30, 43, 116; and the full reprint of Paper I (thesis pp. 113–~130) headed *"Published as: … IEEE Transactions on Antennas and Propagation, Vol. 68, No. 2, pp. 773–782, 2020."* Ten load-bearing sentences compared verbatim against arXiv v3 (§4.1) |
| A. Ludvig-Osipov, *Fundamental Bounds on Performance of Periodic Electromagnetic Radiators and Scatterers*, PhD thesis, KTH, 2020 (DiVA `diva2:1386207`) | **STRANDED** — DiVA reset the connection on every attempt (curl ×3, fetcher ×2, URN resolver ×1) this session. Bot-walled or transient, not paywalled; retrievable by a human in one click |
| Y. Ivanenko, *Optimization and Physical Bounds for Passive and Non-passive Systems*, PhD thesis, Linnaeus University, 2019 (DiVA `diva2:1372058`) — the only same-group citing work Semantic Scholar lists | **STRANDED** — same DiVA failure |
| LPKF, *Micro-Material Processing with the LPKF ProtoLaser U3* (8-page product brochure, solectro.se mirror) | **READ** — specification table and application notes; used only for §6's inference |
| Semantic Scholar graph API record + citations; OpenAlex work record `W2964608939` | **READ** — Semantic Scholar lists 2 citing works (Schab 2021; Ivanenko thesis 2019); OpenAlex reports `cited_by_count: 3` but its citing-works query hit the API's daily budget before returning the list |
| Web search for an erratum / corrigendum / follow-up horseshoe measurement by any of the eight authors | **SEARCHED, NOT FOUND** — five queries; nothing beyond the paper itself, ar5iv mirror, ResearchGate stub, and the two theses above |

## 2. What the paper says, verbatim

Page numbers are arXiv v3's. Emphasis added.

**The optimised design (Sec. IV, p. 6):**
> "Figure 6 shows the results of optimization of the horseshoe perforation geometry with α₀ = 5%. We start with a non-optimized design given by the size a, and l = 1.69a, w₁ = w₂ = 0.049a. Optimization (13) yields the design given by l = 1.43a, w₁ = 0.049a, and w₂ = 0.0047a. We observe that the bandwidth is improved approximately twice, and the main peak contains **96% of the attainable bandwidth, according to (12)**."

The Fig. 6 inset (re-rendered, `horseshoe_inset_zoom.png`) defines the symbols: `l` is the unit-cell period (dashed square), `a` the outer height of the U-shaped slot, `w₂` the width of the top (closed) bar, `w₁` the width of each vertical arm. The slot is a "U"; the two arms are open at the bottom.

**Thickness validity (Sec. V, p. 6):**
> "For w/d = 1, we observe a noticeable bandwidth reduction in comparison with the infinitely thin case. However, when w/d = 10, the difference … is negligible, resulting in a bandwidth reduction of about 2% … **However, when the slot width becomes comparable to the slot thickness, the bound is not tight.**"

**Fig. 8's geometry is the sample's (Sec. V, p. 6):**
> "Figure 8 shows the simulated transmittance for a perforated screen made of PEC or aluminum. **The geometrical parameters of the screen are the same as of the manufactured sample**, to be discussed in the next section."

**The manufactured sample (Sec. VI, p. 6):**
> "The final manufactured sample had the unit cell geometry given by the inset in Figure 6 with l = 6.57 mm, a = 3.43 mm, w₁ = 0.3 mm, and w₂ = 0.06 mm. The aperture array was laser milled by a ProtoLaser U3 machine in a sheet of aluminum foil of thickness d = 0.018 mm. The array consisted of 34 × 45 = 1530 apertures, and α = 5%"

> "Standard gain horn Satimo SGH1240 antennas were used, with the nominal frequency range 12.4 − 18.0 GHz."

**The two percentages, back to back (Sec. VI, p. 7):**
> "The optimized PEC-bandwidth of the lowest-frequency peak, **as shown in Section IV**, reaches 96% of the available physical bandwidth, based on the sum rule utilizing the polarizability of the perforation (12). …
> By comparing **the measured result with the PEC-simulated results** at the 80% transmittance threshold level, we find that the time-gated measured transmission peak has **98% of the available bandwidth of a PEC-based structure**. The measured transmission peak is centered at the frequency of 13.52 GHz with the fractional bandwidth of 5.83%."

**The only sentences that touch on *why* (Sec. VII, p. 8):**
> "We have experimentally validated our results by showing that the transmission characteristics of the first transmission window of a horseshoe design, **optimized with the use of the sum rule**, fabricated in a 0.018 mm thick highly conducting aluminum foil … accurately matches the corresponding simulations. … **The choice of frequency band was selected to fully utilize the range of the experimental equipment.**"

> "**The foil was also thinner than the smallest slot in the design.** This meant that there was no waveguide-like phenomenon occurring in the slots."

That is the complete inventory. There is no sentence about fabrication tolerance, minimum feature size, re-optimisation, or scaling.

## 3. The mismatch, checked

### 3.1 Arithmetic on the paper's stated numbers (`CALCULATED`)

| Quantity | Fig. 6 non-optimised | Fig. 6 optimised | Manufactured (Sec. VI) |
|---|---|---|---|
| `l/a` | 1.69 | 1.43 | 6.57/3.43 = **1.915** |
| `w₁/a` | 0.049 | 0.049 | 0.3/3.43 = **0.0875** |
| `w₂/a` | 0.049 | 0.0047 | 0.06/3.43 = **0.0175** |
| `w₂/w₁` | 1 | 0.096 | 0.20 |
| `α = S_p/l²` (slot area `a·w₂ + 2(a−w₂)·w₁`) | 4.98 % | 5.00 % | 5.16 % (paper: "5%") |
| `w₂/d` at `d = 18 µm` | — | 0.90 if `a = 3.43 mm` | 3.33 |

*In plain terms: the built slot is the same letter of the alphabet — a U — but its arms are ~1.8× wider, its top bar ~3.7× wider, and its neighbours ~34 % further apart than in the design the paper optimised. The only proportion the two agree on is the 5 % open-area budget.*

### 3.2 Where each design's main band sits (`CALCULATED`, from a pixel-calibrated read of Fig. 6 — plot-reading, not a stated number; `±0.03` in `λ/l`)

Fig. 6 was re-rendered at 300 dpi; the x-axis was calibrated from the six tick-label centroids (linear fit residuals ≤ 0.002 in `λ/l`); the `T₀² = 0.8` dotted line located from its red pixels; crossings found where each curve intersects it.

| | Band edges `λ/l` at `T₀² = 0.8` | Fractional bandwidth `B` | Centre `λ₀/l` | Centre `λ₀/a` |
|---|---|---|---|---|
| Fig. 6 optimised (black) | 4.43 – 4.91 | **≈ 10.2 %** | 4.67 | 6.7 |
| Fig. 6 non-optimised (blue dashed) | 3.15 – 3.41 | **≈ 8.1 %** | 3.28 | 5.5 |
| Manufactured, measured (stated) | — | **5.83 %** | 22.17 mm / 6.57 mm = **3.375** | 6.46 |
| Manufactured, PEC-simulated (implied by "98 %") | — | 5.83/0.98 ≈ 5.95 % | | |

Cross-checks: the absolute widths `Δ(λ/l)` are 0.48 vs 0.27, ratio 1.8 — consistent with the paper's "improved approximately twice" (so "twice" is absolute width, not fractional). Lundgren's thesis Fig. 8 (p. 23) redraws the optimised curve with dashed markers at ≈ 4.43 and ≈ 4.9, matching this read. The centre `λ₀/a ≈ 6.5–6.7` for both the optimised and the manufactured design says the slot's resonance is set by `a` as expected — the built horseshoe resonates where a horseshoe of that size should; what changed is the period and the widths.

**So the measured 5.83 % is not "the 96 % design's bandwidth, measured". It is roughly 57 % of the optimised design's bandwidth and 72 % of the non-optimised one's.** Whether that is because the sample is further from its own bound, or because its bound is lower (larger `A = l²` in Eq. (12)), the paper does not say and this note cannot settle without `γ` (§5).

## 4. Is it explained anywhere else?

### 4.1 Journal version vs arXiv v3

The typeset IEEE text could not be read (paywalled; §1). The next-best evidence is the reprint of Paper I in Lundgren's 2021 thesis, headed *"Published as: … IEEE Transactions on Antennas and Propagation, Vol. 68, No. 2, pp. 773–782, 2020"*. A whitespace-normalised search found all ten load-bearing sentences **present verbatim in both** the arXiv v3 text and the thesis reprint:

- "l = 1.69a, w1 = w2 = 0.049a" · "l = 1.43a, w1 = 0.049a, and w2 = 0.0047a" · "main peak contains 96% of the attainable bandwidth"
- "l = 6.57 mm, a = 3.43 mm, w1 = 0.3 mm, and w2 = 0.06 mm" · "centered at the frequency of 13.52 GHz with the fractional bandwidth of 5.83%" · "98% of the available bandwidth of a PEC-based structure"
- "the slot width for the cross potent, horseshoe and split ring was fixed at w = a/17" · "when the slot width becomes comparable to the slot thickness, the bound is not tight"
- "The choice of frequency band was selected to fully utilize the range of the experimental equipment" · "The foil was also thinner than the smallest slot in the design"

A thesis reprint is normally the accepted manuscript, not the publisher's typeset file, so this is strong-but-not-conclusive evidence that the journal version carries the same numbers and the same silence. Crossref lists no correction relation; arXiv lists no v4; the v3 comment says only "Updated Introduction and Conclusions".

### 4.2 Erratum / corrigendum

**Not found.** Crossref: none. arXiv: none. Web: none.

### 4.3 Follow-ups and the group's own later summaries

**No follow-up horseshoe paper or re-measurement was found.** The only same-group citing work located is Ivanenko's 2019 thesis (stranded, §1). Ludvig-Osipov's 2020 KTH thesis (stranded) very likely reprints the paper; it could not be checked.

Lundgren's 2021 thesis, the one same-group document that *was* read, **repeats the conflation rather than resolving it.** Its Fig. 8 (Part I, p. 23) places a photograph of the manufactured foil beside the *optimised* Fig. 6 curve (peak at `λ/l ≈ 4.65`, "96%" marker) and captions them as one thing: *"Manufactured functional structure in an aluminum foil of dimensions 238 mm×320 mm (left) and simulation of the squared absolute value of the transmission coefficient of the design, solid, with 96% of the attainable bandwidth captured in the first transmission peak [151]."* The text (p. 23) adds: *"The design had 96 % of the total available sum rule predicted bandwidth in the first transmission peak. The simulations and measurements agree well."* The curve shown is not the manufactured geometry's (that one peaks at `λ/l = 3.375`, §3.2). The thesis's one relevant design remark is generic: *"the mechanical stability of the laser milled design in Paper I"* is listed (p. 30) among constraints "not based on electromagnetic constraints" that shaped material choices.

*In plain terms: two years later, the group's own thesis still presents the built sample and the optimised design as the same object. Nobody has published a reconciliation.*

## 5. Is a `γ` for the horseshoe stated anywhere?

**No.** Every occurrence of `γ` in the paper was checked (pp. 3, 4, 5, 8, 9; Appendix A on p. 9 is the derivation). Horseshoe polarizability appears only as **curves** — Fig. 4 (`γ/l³` vs `(l−a)/l` at three spacings `l ∈ {1.1a, 1.47a, 2.29a}`) and Fig. 5 (`γ/l³` vs `α` on a log axis) — both computed with the slot width **"fixed at w = a/17"** (p. 5), i.e. `w₁ = w₂ = 0.0588a`, which is *neither* the optimised (`0.049a / 0.0047a`) nor the manufactured (`0.0875a / 0.0175a`) proportions. No table, no numeric value, no units-conversion sentence. The 96 % figure is stated as a ratio only; the `γ` behind it is not given.

Two numbers *can* be back-solved from Eq. (12) with `Δ = √(1−T₀²)/T₀ = 0.5` at `T₀² = 0.8` (`CALCULATED`):

- **Fig. 6 optimised design:** `B_bound = 10.2 % / 0.96 ≈ 10.6 %` (the 10.2 % is plot-read, §3.2), so `γ/l³ = B_bound·(λ₀/l)/(πΔ) ≈ 0.106 × 4.67 / 1.571 ≈ 0.32` — with perhaps ±5 % from plot reading. A stated ratio times a read bandwidth.
- **Manufactured sample:** the paper gives *no* fraction-of-bound, so Eq. (12) yields only the one-sided `γ/l³ ≥ B·(λ₀/l)/(πΔ) = 0.0583 × 3.375 / 1.571 = 0.125` (measured) or `≥ 0.128` (PEC-simulated, 5.95 %). This 0.128 is exactly the value `tests/test_physical_bounds.py:449` asserts — but that test's docstring calls it the paper's "98% of the Eq. (12) bound", which the paper does not say (§7).

## 6. A reconstruction that fits — labelled as inference, not finding

Nothing here is stated by the paper. It is offered because, per the charter's warning triad, it names *what is assumed* and *the cheapest way to find out*.

**Step 1 — scale.** The horns' nominal band is 12.4–18.0 GHz (p. 6). A horseshoe resonates at `λ₀ ≈ 6.5a` (§3.2, both designs), so `a = 3.43 mm` puts it at ≈ 13.5 GHz. This is what the Conclusions' "fully utilize the range of the experimental equipment" plausibly refers to. (`INFERRED`)

**Step 2 — the optimised widths are unbuildable at that scale.** At `a = 3.43 mm` the optimised proportions give `l = 4.90 mm, w₁ = 0.168 mm, w₂ = 0.016 mm`. A 16 µm slot in 18 µm foil is `w₂/d = 0.9` — the paper's own Sec. V (p. 6) regime where "the bound is not tight", and contradicting its Conclusions' "the foil was also thinner than the smallest slot". It is also at the cutting tool's limit: the LPKF ProtoLaser U3 brochure's specification table gives *"Diameter of focussed laser beam 15 µm (0.6 mil)"*, and its worked figures for 18 µm copper are *"Even with 18-µm copper coating, a pitch of 100 µm is possible (line 70 µm / gap 30 µm)"* and *"line/space 50/25 µm"* — the narrowest quoted gap is 25–30 µm. (`LITERATURE-SUPPORTED` for the specs; `INFERRED` that this drove the choice.)

**Step 3 — widen, then re-satisfy `α = 5 %`.** With `w₁ = 0.3 mm, w₂ = 0.06 mm` (`w₂/d = 3.3`, and `w₂` ≈ 2× the brochure's minimum gap) the slot area is 2.23 mm². Keeping the optimised period `l = 4.90 mm` would give `α = 9.3 %`, violating the paper's `α₀ = 5 %` constraint (Eq. 13). Solving `l = √(2.23 mm² / 0.05) = 6.68 mm` — the stated `l = 6.57 mm` is within 1.7 % of it (and gives `α = 5.16 %`, "5%"). (`CALCULATED`)

So the manufactured sample is consistent with: *fix `a` for the horns, open the slots to what the foil and the laser can make, then spread the cells until the 5 % budget is met again.* Wider slots and a larger period both change `γ/A`, which is why its bandwidth (5.83 %) is not the optimised design's (≈ 10 %). Whether the authors also re-ran the optimisation (13) under these constraints is unknown.

**Cheapest way to find out:** one email to the corresponding author (Ludvig-Osipov, KTH) asking (i) why the sample's proportions differ from Fig. 6, and (ii) the `γ` value behind the 96 %. Second cheapest: retrieve the two stranded DiVA theses (§1) in a browser and search their summary chapters. Neither has been done.

## 7. What this changes for #552 and the repo

**Status of the ticket.** #552 is already **closed** (state `completed`, closed by PR #554 at 21:02 UTC on 2026-09-12) even though its last comment narrows it to the horseshoe and says "Left open". If the horseshoe half is to be tracked, it needs a fresh ticket; there is nothing to reopen cleanly.

**Is the horseshoe reproduction tractable as specified?** **No — and this is now confirmed by the primary source rather than suspected.** #552 asked for the paper's own reported absolute fractional bandwidth *and* its own reported fraction-of-bound for one geometry, so that Eq. (12) could be checked end-to-end. For the horseshoe the paper provides:

| Design | Geometry stated? | Absolute `B` stated? | Fraction of Eq. (12) bound stated? | `γ` stated? |
|---|---|---|---|---|
| Fig. 6 optimised | yes (normalised) | **no** (plot only, ≈ 10.2 %) | yes (96 %) | no |
| Manufactured | yes (mm) | yes (5.83 %) | **no** (98 % is vs PEC simulation) | no |

No single design has all of the first three. That is the gap, and no erratum, journal version, or later group document fills it.

**Two honest, weaker checks remain**, should a horseshoe `γ` solver ever be built (it is out of scope per #547 and, as #552's comment notes, needs a full-domain solve because the U has only one mirror plane):

- **(a)** Compute `γ/l³` for the Fig. 6 optimised proportions (`l = 1.43a, w₁ = 0.049a, w₂ = 0.0047a`) and compare to ≈ 0.32 (§5) with a tolerance no tighter than ±10 %, because one factor is plot-read. `CALCULATED` provenance, never `LITERATURE-SUPPORTED`.
- **(b)** Compute `γ/l³` for the manufactured geometry and check the **inequality** `γ/l³ ≥ 0.128` — a one-sided test built only from stated numbers. It cannot fail loudly (any large `γ` passes) but it can catch an under-predicting solver.

**One correction to make now, independent of any solver.** `tests/test_physical_bounds.py:424–449` (`test_perforated_screen_bound_reproduces_the_papers_horseshoe_design`) documents the sample as *"reported as 98% of the Eq. (12) bound at T0^2 = 0.8"* and its `fraction_of_bound = 0.98`. The paper's 98 % compares the measurement to *"the PEC-simulated results"* / *"a PEC-based structure"* (p. 7), i.e. to Fig. 8's simulation of the same geometry, not to the sum-rule bound. The arithmetic the test performs is still valid — it back-solves the *minimum* `γ` consistent with a 5.95 % band via the inequality, and the forward direction is an identity — but the docstring and the variable name assert a paper claim that does not exist. Reword it as the one-sided check (b) above and drop "98% of the Eq. (12) bound". The `0.1278` value itself is fine as `CALCULATED`.

**Recommendation, in one line:** confirm the gap as unresolved by the primary source; do not re-open #552; file the docstring correction as a small ticket; if anyone wants the horseshoe closed for real, the cheapest path is the email in §6, not more reading.

---

## 8. An independent derivation, tried after this research landed — `CALCULATED`

Rather than stop at "the paper doesn't say", this section reports actually building a horseshoe polarizability solver and running both of §7's "weaker checks" against it, to see whether physics-based derivation could get further than literature archaeology alone. It could not, but it landed on the same conclusion from a completely different direction, which is itself worth recording.

**The shape, read from the PDF's own vector paths, not pixels.** Fig. 6's inset in the source PDF (`perf.pdf`, page 6) is vector art. Extracting its drawing objects directly (`pymupdf`'s `page.get_drawings()`) rather than reading the raster render gives exact corner coordinates: the horseshoe is a "U" — three connected straight segments (left arm, bottom bar, right arm), open at the top, with the left arm and bottom bar sharing one wall thickness (`w2`, confirmed by the `w2` dimension arrow's exact pixel span landing on the bottom bar) and the right arm a second, independent thickness (`w1`, likewise confirmed by its own arrow). Both arms run the full height `a`; only the top is open. This resolved an ambiguity a first look at the raster image could not (whether the right arm was foreshortened).

**The solver reuses this repository's own machinery, adding nothing new to it.** The U decomposes into 3 non-overlapping axis-aligned rectangles (no new geometry primitive), meshed with `rf_tools/aperture_polarizability.py`'s existing `_graded_nodes_1d`/`_rect_cells`, and solved with the *test file's own* general full-domain solver (`_solve_alpha_full_domain` in `tests/test_aperture_polarizability.py`, built for the cross-potent isotropy check) — this shape has no mirror symmetry at all (`w1 != w2`), so the quadrant-reduced solver the square-loop and cross-potent use does not apply, but the already-existing general solver does, unmodified. No shape solver was added to production code; this lived entirely in a scratch script.

**Field direction is an assumption, stated as one.** The paper never states which linear polarization excites the horseshoe's resonance for either design. A scan over 0-180 degrees on the manufactured geometry finds the response is anisotropic (22.5 to 32.7, in mm^3, over the sweep) with a broad maximum near the axis connecting the two open arm-tips across the gap (`x` in this note's coordinates) — physically the expected excitation axis for a split-ring-like resonator — so `gamma_xx` is used throughout. `ASSUMED`.

**Results, both checks:**

| Check | Geometry | This solver's `gamma/l^3` (periodic-corrected, `gamma_xx`) | Target (Sec. 5/7) | Shortfall |
|---|---|---|---|---|
| (a) Fig. 6 optimised | `a=1, l=1.43a, w1=0.049a, w2=0.0047a` | 0.256 | ~0.32 (+/- 10%, plot-read) | ~20% low |
| (b) Manufactured (one-sided, `>=`) | `a=3.43mm, l=6.57mm, w1=0.3mm, w2=0.06mm` | 0.119 | >= 0.128 | ~7.6% low -- fails the inequality |

Neither check passes. Mesh convergence was checked directly (both cases converge smoothly under refinement to <0.5% residual by the resolution used) and is not the cause. Two candidate explanations, and no way to pick between them without more information:

1. **The geometry or field-direction assumption is still not quite right** — an off-diagonal tensor term, a corner treatment, or an excitation axis this note has not found.
2. **The manufactured sample's stated `w2 = 0.06 mm` really is off**, exactly as Sec. 6's independent reconstruction already suspected from fabrication-tolerance grounds alone (a 16 um design width against an 18 um foil and a 15 um laser beam). A too-small `w2` directly under-predicts `gamma`, and check (b)'s ~7.6% shortfall is the same order of magnitude Sec. 6 already flagged as plausible from unrelated evidence (LPKF brochure minimum feature size). Check (a) uses the *design* dimensions, not the built ones, so this explanation does not obviously extend to its larger 20% shortfall — the two checks' different-sized gaps argue against a single simple correction factor covering both.

**What this changes:** nothing about Sec. 7's recommendation. It was already "do not reproduce this as a passing test" before this derivation was tried, and an independent physics-based attempt reaching the same shortfall from a different direction is corroborating evidence for that conclusion, not a reason to revisit it. The solver and its results are recorded here, not committed to the repository as a test, because a test built to require a >=20%+ tolerance to pass is exactly the kind of test the earlier #547/#552 code reviews already flagged as too loose to be meaningful.

**Files:** `jerusalem_cross_check.py` (unrelated, the earlier cross-potent solver), `horseshoe_check.py` (this section's solver and mesh), both in this session's scratchpad, not the repository.

## 9. Provenance summary

| Claim | Provenance |
|---|---|
| The two geometries, the 96 % / 98 % sentences, the Sec. V thickness statements, the Conclusions' two sentences | `LITERATURE-SUPPORTED` — verbatim from arXiv v3, page-referenced |
| The manufactured proportions differ from Fig. 6's (`l/a` 1.915 vs 1.43, etc.) and both satisfy `α ≈ 5 %` | `CALCULATED` — arithmetic on stated numbers |
| The "98 %" is measured-vs-PEC-simulation, not vs the bound | `LITERATURE-SUPPORTED` — the sentence's own referents, p. 7, quoted |
| Fig. 6 optimised `B ≈ 10.2 %` at `λ/l ≈ 4.67`; non-optimised ≈ 8.1 % at 3.28 | `CALCULATED` — pixel-calibrated plot read, ±0.03 in `λ/l`; cross-checked against Lundgren thesis Fig. 8 markers |
| The journal text carries the same numbers and no explanation | `INFERRED` (strong) — ten sentences verbatim-identical between arXiv v3 and the thesis's "Published as … IEEE TAP 2020" reprint; the typeset IEEE file itself **not read** |
| No erratum, no v4, no follow-up measurement | `LITERATURE-SUPPORTED` (Crossref, arXiv history) + `SEARCHED, NOT FOUND` (web, Semantic Scholar) |
| Lundgren's thesis restates the sample as the 96 % design | `LITERATURE-SUPPORTED` — verbatim, thesis p. 23 |
| No horseshoe `γ` is stated in the paper; Figs. 4–5 use `w = a/17` | `LITERATURE-SUPPORTED` — exhaustive check of every `γ` occurrence; p. 5 quoted |
| Implied `γ/l³ ≈ 0.32` (optimised) and `≥ 0.128` (manufactured) | `CALCULATED` — Eq. (12) with `Δ = 0.5`; the former inherits plot-reading error |
| ProtoLaser U3: 15 µm focused beam; 70/30 µm line/gap in 18 µm Cu | `LITERATURE-SUPPORTED` — LPKF brochure specification table, quoted |
| The §6 reconstruction (scale for horns → widen for foil/laser → re-space for `α = 5 %` → `l ≈ 6.68 mm`) | `INFERRED` + `CALCULATED` — fits the stated numbers to 2 %; **not stated by any source**; falsifiable by one email |
| `tests/test_physical_bounds.py:424` misattributes the 98 % | `LITERATURE-SUPPORTED` (what the paper says) vs the file as read |
| The horseshoe's exact geometry (a 3-segment "U", `w1`/`w2` on separate arms) | `LITERATURE-SUPPORTED` — read from the source PDF's own vector drawing paths (`pymupdf`), not a pixel estimate |
| §8's derived `gamma/l³` (0.256 optimised, 0.119 manufactured) and their shortfall against §5/§7's targets | `CALCULATED` — this session's own BEM solve, reusing existing repository machinery on a new mesh; field direction `ASSUMED` |
