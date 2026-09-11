# Example 7 Scoring Recipe — Circular Inter-Digitated Ring Pair, AMC-Checkerboard Backscatter Reduction

**Serves:** [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104)'s wayfinder map, "Not yet specified" item 1.

**Scope note:** This write-up covers **Example 7 only** (one of four parallel per-example dispatches resolving NYS1). It builds on, and does not re-litigate, `docs/seven-example-design-unknowns.md` (#107, design variables/criterion), `docs/supercell-sizing-rule.md` (#130, the δ_budget mechanism), `docs/ai-metasurface-survey-against-the-seven-examples.md` (#202-adjacent ML-surrogate cost data), and ADR-0047/#129 (the physical_bound table). New literature verified in this session is marked **[verified this session]**; everything else is marked as reused from the existing docs.

---

## 1. Primary objective

### 1.1 The five-step recipe

A tile-assignment candidate is an `Nx × Ny` matrix `c(m,n)` assigning each lattice position to one of the family's characterized element variants (the patent's own two ring-pair geometries, or a larger GA-searched library). Turning that into a score:

**Step 1 — per-tile Floquet lookup (cheap, done once per element in the library).** One one-port, PEC-backed Floquet solve per tile type `k` gives `∠Γ_k(f)` across the requirement band. This is exactly `docs/seven-example-design-unknowns.md` §5's own characterization of Example 7 ("Two Floquet solves give the two tiles' ∠Γ").

**Step 2 — per-frequency phase-error budget, combining two distinct error sources that #130 keeps separate but Example 7's score needs summed.** `docs/supercell-sizing-rule.md` §2 derives `Δφ_max` as *coupling error* — how far a real neighbor perturbs a cell from its Floquet-characterized value — and treats it as a constant, alphabet-level number. Example 7's actual band-dependent problem has a **second** source #130 never had to add in: the two tiles' own `∠Γ_k(f)` naturally drift apart from exactly 180° away from the design frequency — that drift *is* what "RCS-reduction bandwidth" means. The honest worst-case phase error at frequency `f` is therefore

```
δ(f) = |180° − (∠Γ₁(f) − ∠Γ₂(f))| + Δφ_max·f(N)
```

— dispersion plus coupling error, not either alone. **Nothing in the existing docs combines these two terms; this addition is new synthesis for this write-up, not an adopted formula**, flagged as such rather than presented as settled.

**Step 3 — aperture-level score, closed form, no full-wave.** For a *plain 1:1 alternating* checkerboard, `docs/supercell-sizing-rule.md`'s own two-term aperture average applies directly:

```
RCS_reduction_dB(f) = 20·log10( sin(δ(f)/2) )
```

For a **non-1:1, GA/PSO-searched coding sequence** — which is the entire point of running an optimizer — this two-term formula does not apply, because it assumes equal-area alternating tiles. The general form is the far-field superposition **Cui, Qi, Wan, Zhao & Cheng (2014)** derive for an arbitrary `N×N` lattice of "0"/"1" (or, extended, higher-bit) elements: a far-field function built from each lattice's own phase `φ(m,n) ∈ {0°, 180°}` (their Eq. 1), a directivity `Dir(θ,φ)` computed from it (Eq. 2), and an RCS-reduction figure relative to a same-size metal plate computed from that directivity (Eq. 3) — **[verified this session, firsthand]**: the arXiv preprint (1407.8442; published as *Light: Science & Applications* **3**, e218 (2014), DOI [10.1038/lsa.2014.99](https://doi.org/10.1038/lsa.2014.99)) was fetched and extracted page-by-page with `pdftotext`/PyMuPDF after the initial WebFetch returned only a binary summary. **Honest caveat: Eq. 3's exact algebraic arrangement did not survive the extraction intact** — the math-typesetting characters render out of their fraction/exponent positions in both extraction tools tried, so no reconstructed formula that cannot be verified character-for-character is presented here. What *did* survive cleanly, and is directly useful, is the paper's own worked, checkable numeric anchor — **Table I**, their own optimized-code search results:

| N (lattices/side) | Code | RCS reduction |
|---|---|---|
| 6 | 001011 | −12.08 dB |
| 7 | (not extracted intact) | −14.64 dB |
| 8 | 00110101 | −15.82 dB |
| 10 | 0001010110 | −18.39 dB |
| 12 | 001001110101 | −19.75 dB |
| 14 | (not extracted intact) | −21.41 dB |
| 16 | 0011110110101010 | −22.37 dB |
| 20 | 01000100110000110101 | −23.58 dB |

(All eight rows of the paper's own table; the N=7 and N=14 code strings did not survive extraction intact and are omitted rather than reconstructed — the reduction figures for those two rows are transcribed directly from the paper.)

Verbatim: *"The best RCS reduction can be achieved through optimizing the coding sequences of '0' and '1' lattices... We notice that better RCS reduction is achieved for larger N."* This table is a fully independent, primary-source falsification target for any implementation of Step 3's array-factor evaluation on the special all-equal-magnitude, lossless-reflector case — an implementation that cannot reproduce these eight numbers on this input is wrong.

**Step 4 — the optimizer's fitness function *is* Step 3, and the physical_bound check is not part of it.** Cui et al. do not name their search algorithm for Table I (worth being precise: not every source here is literally a genetic algorithm). What the newly-verified literature *does* establish, directly on point for the task's ask, is that **optimizing the arrangement — not just the unit cell — beats a naive periodic/checkerboard baseline by a margin large enough to matter**, using several different named algorithms:

- **[verified this session, verbatim via WebFetch of the primary PMC record]** Ali, Li, Khan, Yi & Chen, *"Wideband RCS Reduction Using Coding Diffusion Metasurface,"* *Materials* **12**(17):2708 (2019), DOI [10.3390/ma12172708](https://doi.org/10.3390/ma12172708): a **"random optimization algorithm"** (their own term — not a GA) searches the coding sequence, and *"the traditional chessboard metasurface achieves RCS reduction from 13.8 GHz to 22.5 GHz with 60% bandwidth, while the coding diffusion metasurface has the RCS reduction within a wider bandwidth, i.e., from 8.6 GHz to 22.5 GHz"* — a self-computed "roughly 89%" fractional-bandwidth figure against the plain chessboard's 60% (this project's own arithmetic from the quoted band edges, not a quoted figure itself — a different fractional-bandwidth convention, e.g. centered-frequency normalization, could read closer to 92%; the 60%/89–92% comparison is directional, not a precision claim), same two unit cells, same 180°±37° criterion, arrangement is the only variable changed.
- **[verified this session via WebSearch, cross-checked against two independent listings]** Wu, Yu, Lin, Deng & Liu, *"Ultra-Wideband RCS Reduction Based on Non-Planar Coding Diffusive Metasurface,"* *Materials* **13**(21):4773 (2020), DOI [10.3390/ma13214773](https://doi.org/10.3390/ma13214773): a discrete particle-swarm algorithm (DPSO) reaches 10 dB monostatic reduction from 6.4–29.6 GHz (4.62:1 bandwidth ratio), explicitly reported as wider than the checkerboard baseline.
- **[secondary/AI-summarized, not independently re-verified against raw PDF — flagged at lower confidence]** Ullah, Latef, Othman et al., *Scientific Reports* (2025), DOI [10.1038/s41598-025-22248-z](https://doi.org/10.1038/s41598-025-22248-z): a genetic algorithm optimizes the *coding-sequence arrangement itself* (not the unit cell), ~20 dB reduction over 12–19.3 GHz.
- Already in `docs/ai-metasurface-survey-against-the-seven-examples.md`: Zhang, Liu, Wan, Zhang, Liu, Yang & Cui (2019), a DNN phase-prediction surrogate reaching 2° phase error — cheap enough (per that document's own §4 table) to sit inside a GA's per-candidate evaluation with 5–30× headroom against #130's own δ_budget at ordinary reduction levels.

So: the GA/PSO/random-search optimizer's fitness function is Step 3 (cheap, closed-form or ML-surrogate-accelerated, evaluated per candidate across the whole population) — never a full-wave solve per candidate, matching this project's own "evaluate cheap before expensive" method and matching how Cui et al. themselves generated Table I. **Physical_bound (§3 below) is not a function of the coding sequence at all** — it depends only on the tile's own thickness/geometry, which is fixed across the whole GA population for a given element library — so it is computed once, reported alongside the optimizer's best candidate, never wired into the fitness function and never used to cull the population mid-search (per ADR-0047's "advise, never gate").

**Step 5 — full-wave validation, once, on the finalist.** `docs/seven-example-design-unknowns.md` already quotes the field's own validated two-stage method — Haji-Ahmadi et al. (2017): Floquet optimization, then *"the complete finite metasurface (4×4 alternating tiles, 224×224 mm)... using CST's time-domain solver, which accounts for edge effects and finite-size interactions absent in periodic assumptions."* Note their own validation target is a **plain 4×4 alternating** checkerboard, i.e. the *naive* baseline the optimization literature above is improving on — worth flagging in §4.

### 1.2 Aggregation: minimax, by structural analogy to ADR-0041 — not independently literature-confirmed for this family

ADR-0041 (#110/Example 3) adopted worst-in-band minimax for absorbers with a *direct, explicit* citation arguing against averaging (Yiğit & Duysak 2021: *"if the design has a very low reflection coefficient at any frequency, it significantly reduces the average value..."*). **No equivalent paper making that argument explicitly for coding-metasurface RCS reduction was found** — so recommending minimax here is a **structural transfer of ADR-0041's reasoning**, not an independently confirmed literature finding of the same strength, and that gap should be stated plainly rather than dressed up as equivalent evidence.

What *does* corroborate the transfer, short of an explicit anti-averaging argument: the field's own headline convention for this exact function is phrased as a **guaranteed worst case**, not a mean, independently in four sources now — Haji-Ahmadi et al. (2017, already in the docs): *"a phase difference of 180 ± 37° ... provides **at least** 10 dB monostatic RCS reduction"*; Cui et al. (2014, **[verified this session, verbatim]**): *"For all cases, when the phase difference varies from 145° to 215°, **at least 10-dB RCS reduction is guaranteed**"*; Ali et al. (2019, **[verified this session]**) and Wu et al. (2020, **[verified this session]**) both restate 180°±37° as their own design criterion. All four converge on essentially the same ±37° figure, and #130's own derived `δ_budget = 2·arcsin(10^(−10/20)) = 36.9°` reproduces it independently — a fifth, first-principles confirmation. A field that reports its own criterion as "at least X dB, guaranteed" over an angular/phase window is a field implicitly treating the worst point in that window as the thing that must hold — the same logic ADR-0041 made explicit for absorbers, just not stated in as many words here.

**Objective:** `score = min over f ∈ [f_lo, f_hi] of RCS_reduction_dB(f)` from Step 3, worst-in-band minimax, for the reasons above — recommended, not literature-proven to the same evidentiary bar as ADR-0041 point 1.

---

## 2. Default when the customer is silent

**A numeric target reduction gets a reversible default; the reference geometry does not — and conflating the two is exactly the trap `docs/requirement-derived-thresholds.md` audits against.**

**10 dB monostatic RCS reduction** is a real, recurring, cross-paper reporting convention for this exact family — the same evidentiary shape `docs/absorber-scoring-decision-confirmation.md` accepted for the absorber's −10 dB/90% default, now independently checkable across the same four sources cited in §1.2 (Haji-Ahmadi 2017, Cui 2014, Ali 2019, Wu 2020) plus this project's own already-derived `δ_budget` formula reproducing it from first principles. Per ADR-0041's own point 2 and `docs/requirement-derived-thresholds.md`'s rule (*"a convention is a default, it is never a threshold"*), the recommendation is: **absent a customer-stated reduction figure, default the threshold to 10 dB, record that the gap was filled, and let any customer-stated figure override it without argument** — never a hardcoded prune, never used to redefine the band's own edges.

**What has no default at all, and must not be given one:** `docs/seven-example-design-unknowns.md` §6.3 already settled this for Example 7 specifically — *"the reference surface that 'reduction' is measured against, and the observation geometry (monostatic vs. bistatic, and which bistatic angles count as acceptable places to send the energy) ... No solver can know that... it is the clearest example in the set of a criterion that cannot be closed without a human."* Nothing in this session's research changes that. Likewise the **aperture extent / panel size** is a stated per-requirement human input, not a design default — `docs/requirement-derived-thresholds.md`'s own audit table is explicit that the coupon size this project can *measure* (6λ focused, per #106) must never migrate into a design *threshold*, and this rule is carried forward rather than inventing a default panel size to make Example 7's scoring self-contained.

---

## 3. Physical_bound

**Gustafsson & Sjöberg applies, already adopted at ADR-0047/#129** — Example 7 is explicitly named there alongside Examples 4 and 5 (beam steering by reflection phase) under the same bound, `B·λ₀/d ≤ 2.6` for a ±45° phase window, roughly 5× harsher than Rozanov at the same thickness. The physical reasoning transfers cleanly: both of Example 7's tile types are thin, ground-backed, resonant phase-agile reflectors — the same underlying object Gustafsson-Sjöberg bounds (how much bandwidth a thin resonant reflecting layer can support at a stated phase-agility requirement, independent of what pattern the phases are arranged into). Per ADR-0047: **report the fraction of the limit achieved, computed against the candidate's own realized bandwidth and thickness; never fail a candidate for appearing to beat it.**

**Implementation gap, not a physics gap — filed separately as [#465](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/465):** `rf_tools/physical_bounds.py`'s own module docstring names three bound families ("Rozanov for absorbers, Gustafsson & Sjöberg for reflection-phase steering, Nel/Skrivervik/Gustafsson for patch antennas") but the module itself implements only Rozanov (`rozanov_*`) and the patch-antenna bound (`patch_q_*`) — **no Gustafsson & Sjöberg function exists in code**, for Example 7 or for Examples 4/5. Every numeric application of the bound in this document, and in `docs/example4-5-beam-steering-scoring-recipe.md`, is presently hand-computed from the closed forms in `docs/absorber-thickness-bandwidth-bound.md` §7.1, not called from a tested function. This is a real, separately-tracked implementation gap, not a defect in the physics or the citation.

**How the tile-assignment optimizer interacts with it, mechanically (per §1's Step 4):** the bound is a function of tile thickness `d` and realized bandwidth, not of the coding sequence — so it sits *outside* the GA's fitness loop entirely. It is computed once per element-geometry choice (constant across the whole population for a fixed library) and reported alongside the optimizer's best-found candidate as a diagnostic, exactly as ADR-0047 already prescribes for every other family. It never culls candidates mid-search.

**A genuinely open question, named rather than papered over:** ADR-0047 applies the *same* ±45°-phase-window form of the bound to Examples 4/5 (a *continuously* swept reflection phase, the natural fit for a "±45° window" criterion) and to Example 7 (which needs only **two discrete phase states 180° apart**, never anything in between) without addressing whether the ±45°-window form is the right shape of the bound for a two-state design at all — a two-state surface's actual "phase agility" demand may be a much narrower ask than sweeping continuously across a window, in which case the true bound for Example 7 could be looser than what ADR-0047 currently charges it. No literature settling this either way was found in this session, and this is flagged rather than silently assuming ADR-0047's cross-family reuse is exact.

**A second precondition on the `NO_PHYSICAL_BOUND` exemption, contributed by a parallel research pass and not previously recorded anywhere in code or docs:** the diffuse/coding-metasurface exemption from a Rozanov-style absorption bound (redirecting energy elsewhere in space, rather than absorbing it, is exempt from an absorption sum rule) is conditional on the supercell actually being able to launch a **propagating diffracted order** — without one, there is no "elsewhere" for the redirected energy to go, and every dB of specular reduction must in fact come from absorption, which *is* fully Rozanov-bounded. For a checkerboard's two-tile supercell (period `D` = twice the individual tile size) at normal incidence, a propagating diffracted order requires `D ≥ √2·λ` — **42.4 mm at 10 GHz, 30.3 mm at 14 GHz** for this project's own band. `D` here is the supercell period, not a single tile's own dimension — reading it as one tile would be off by a factor of 2. This is a per-candidate check, not a constant: a coupon-scale or otherwise small supercell below this size is not exempt from Rozanov at all, and should be flagged as absorption-bounded rather than treated as a diffusive/redirecting design by default. This does not exist anywhere in this project's code today and is a genuine, separate gap from #465's implementation gap above.

---

## 4. Aperture size: the coupon-vs-panel tension, and what remains genuinely open

**This is the section where repeating the project's own documented failure mode is the biggest risk** (`docs/RUNNING-LISTS.md` corrections #20/#24: a borrowed constant standing in for a derived one, an unresolved tension smoothed into a headline). So stated plainly, not resolved falsely:

**Two array-size effects pull in opposite directions, and neither has a closed form for Example 7 yet.**

1. **`docs/supercell-sizing-rule.md` §3's specular-lobe-clearing ceiling favors *bigger* panels.** A bigger aperture has a *narrower* specular lobe (`≈ λ/(2L)`), so a shallower redirection angle still clears it — the coupon (6λ, 4.8° half-width) is the *hard* case here, the full panel the *easy* one. This is a derived, quantitative relationship that transfers directly.
2. **Murugesan & Selvan's finding pulls the opposite way.** Already in `docs/seven-example-design-unknowns.md` §5 (verbatim, from the Crossref-deposited abstract — full text stranded, HTTP 405, per that document's own §7 item 6): *"The 8 and 10 dB RCS reduction bandwidths drop as array size increases… attributable to mutual coupling."* A bigger array is *harder* here, not easier — more elements means more mutual coupling detuning the local-periodicity assumption each per-tile Floquet solve rests on.

**Consequence for scoring a coupon versus a full panel:** a coupon-sized finite-wave validation (Step 5) is **pessimistic on angle, optimistic on bandwidth** relative to the eventual full panel — an asymmetry in *opposite* directions on two different axes of the same requirement (where the energy goes vs. how much of the requested band achieves the threshold). Any reported coupon number must carry both directions explicitly, not be silently read as representative of the full panel in either direction. (This is also where §3's `D ≥ √2·λ` diffraction-order precondition bites hardest: a coupon-scale supercell is exactly the case most at risk of falling below the propagating-order threshold and losing its exemption from Rozanov entirely.)

**Does #130's panel-fit-constraint logic (`2·Nx·px ≤ L`, Amendment 4) transfer? Partially, and at a different level than the task's framing suggested.** #130's constraint governs how large an *interior-tuned block of identical cells* can be before it stops fitting twice per axis on a coupon — a question about grouping same-type cells to fight *coupling error*. Example 7's coding-sequence candidates (per Cui's own N×N-lattice-of-individually-assigned-tiles model) don't have that same "block" structure — each lattice position is already an individually chosen tile, no grouping decision exists at that level. What *does* transfer is the more general principle underneath Amendment 4 and #130 §3's `N=1` finding: **a coding pattern must repeat more than once across the aperture to do its job at all.** Cui's own Table I only tabulates `N ≥ 6`; their closed-form array-factor treatment implicitly assumes enough lattices to average over, and a coupon holding too few distinct tiles could fall outside where that approximation — or their own optimized-code library — is valid at all. No derived minimum-`N` threshold for when the array-factor treatment breaks down was found (unlike #130 §3's clean `sin θ ≤ 1` derivation for the specular-lobe ceiling); **this is a genuine gap, not a judgment call being declined** — deriving it would need Cui's Eq. (1)-(2) in an intact, non-garbled form, which is not available here.

**Full list of what remains open, stated without smoothing:**

1. **No closed-form model exists for how mutual-coupling bandwidth-narrowing scales with array size.** Murugesan & Selvan's finding is qualitative-only from an abstract; the full text remains stranded (HTTP 405, unchanged since the prior research pass). There is no `docs/supercell-sizing-rule.md`-style `Δφ_max·f(N)` analogue for *this* effect — an actual research gap, not a decision deferred.
2. **Whether Gustafsson-Sjöberg's ±45°-window form is the right bound shape for a two-discrete-phase-state surface** (§3) — unresolved, and ADR-0047 currently reuses the Examples-4/5 form for Example 7 without addressing it.
3. **The Gustafsson & Sjöberg bound has no implementation in `rf_tools/physical_bounds.py`** (§3) — tracked as #465, blocking any of this document's bound arithmetic from being called as tested code rather than hand-computed.
4. **The `D ≥ √2·λ` diffracted-order precondition on the `NO_PHYSICAL_BOUND` exemption (§3) exists nowhere in code today** and has not been checked against this project's own coupon dimensions.
5. **Cui et al. (2014)'s Eq. (3) could not be reconstructed in exact algebraic form** from either extraction tool tried in this session; only its qualitative behavior and Table I's numeric anchor are verified firsthand. Anyone implementing Step 3's general-case formula should re-fetch and re-render the primary PDF rather than trust a reconstruction from this pass.
6. **It is not established whether the patent's own Example 7 embodiment is a naive alternating checkerboard or something already optimized.** `docs/seven-example-design-unknowns.md` §2 records only "two variants in a checkerboard," no coding sequence. If the patent's own measured 8 dB @ 14.3 GHz result is already the naive baseline (which Haji-Ahmadi's own 4×4-alternating validation target suggests is the field's default assumption for "a checkerboard" absent other information), then GA-optimizing the arrangement is a live, literature-substantiated improvement opportunity over the patent's own result — squarely the charter's "new arrangement of letters already printed and measured" category of novelty. If the patent's embodiment is already optimized, that framing is wrong. This could not be settled from the patent text alone.
7. **The minimax-aggregation choice for Example 7 (§1.2) rests on structural analogy to ADR-0041 plus a convergent "at least X dB" phrasing across four sources — not an independent, explicit anti-averaging argument the way Yiğit & Duysak (2021) supplied for absorbers.** This is one evidentiary tier weaker than ADR-0041 point 1, and should be labeled as such wherever it's cited, not upgraded to "confirmed" by proximity to a confirmed absorber decision.
8. **The reference-surface and observation-geometry human input is, per #107, genuinely closed to a solver** — not attempted here, and any future pass proposing a default for it should be read skeptically.

---

## Sources

**Verified firsthand this session (primary text extracted and read):**
- T. J. Cui, M. Q. Qi, X. Wan, J. Zhao & Q. Cheng, "Coding metamaterials, digital metamaterials and programmable metamaterials," *Light: Science & Applications* **3**, e218 (2014), DOI [10.1038/lsa.2014.99](https://doi.org/10.1038/lsa.2014.99) — read via the arXiv preprint [1407.8442](https://arxiv.org/pdf/1407.8442) (titled "...Programming Metamaterials" on the preprint itself — a minor title-wording discrepancy from the published "...programmable metamaterials," noted for honesty, content otherwise consistent), extracted with `pdftotext -layout` and PyMuPDF after WebFetch's own PDF handling failed on the compressed content stream.

**Verified this session via WebFetch of the primary record (verbatim quotes obtained):**
- L. Ali, Q. Li, T. A. Khan, J. Yi & X. Chen, "Wideband RCS Reduction Using Coding Diffusion Metasurface," *Materials* **12**(17):2708 (2019), DOI [10.3390/ma12172708](https://doi.org/10.3390/ma12172708), via [PMC6747563](https://pmc.ncbi.nlm.nih.gov/articles/PMC6747563/).

**Verified this session via WebSearch (cross-checked against two independent listings, not raw-PDF-extracted — secondary confidence):**
- G. Wu, W. Yu, T. Lin, Y. Deng & J. Liu, "Ultra-Wideband RCS Reduction Based on Non-Planar Coding Diffusive Metasurface," *Materials* **13**(21):4773 (2020), DOI [10.3390/ma13214773](https://doi.org/10.3390/ma13214773).
- M. U. Ullah, T. A. Latef, M. Othman et al., "Polarization-controlled coding metasurface with phase cancellation and diffusion for enhanced radar cross section reduction," *Scientific Reports* (2025), DOI [10.1038/s41598-025-22248-z](https://doi.org/10.1038/s41598-025-22248-z) — AI-summarized retrieval, flagged as lower confidence than the two above.

**Reused, not re-fetched (already verified in cited project documents):**
- Haji-Ahmadi, Nayyeri, Soleimani & Ramahi, *Sci. Rep.* **7**, 11437 (2017) — via `docs/seven-example-design-unknowns.md` §1.
- Murugesan & Selvan, *Frequenz* **77**, 273–279 (2023) — via `docs/seven-example-design-unknowns.md` §1 (still stranded, HTTP 405).
- Zhang, Liu, Wan, Zhang, Liu, Yang & Cui, *Adv. Theory Simul.* **2**, 1800132 (2019) — via `docs/ai-metasurface-survey-against-the-seven-examples.md` §3–4.
- Yiğit & Duysak (2021), doi:10.26833/ijeg.743661 — via `docs/absorber-scoring-decision-confirmation.md` §1, reused by analogy in §1.2 above.
- Gustafsson & Sjöberg bound and its Example-7 assignment — ADR-0047 (`docs/adr/0047-...md`), #129, not re-derived here.
- `δ_budget = 2·arcsin(10^(−RCSR_dB/20))` — `docs/supercell-sizing-rule.md`, #130, reused as the special-case anchor for Step 3.
- The `D ≥ √2·λ` diffracted-order precondition on `NO_PHYSICAL_BOUND` (§3) — contributed by a parallel research pass against ADR-0050's ambit, not independently re-derived here.
