# How Published Microwave-Absorber Work Reports and Optimises Performance

**Research date:** 2026-09-03
**Serves:** [#110](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/110) — what the success score rewards for an absorber
**Method:** the same move as [#117](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/117) — before inventing a scoring rule, find out whether the field already has one and adopt it wholesale.
**Scope:** X-band / microwave metamaterial, FSS and radar-absorbing-material (RAM) literature. Reporting and optimisation conventions, not absorber physics.

---

## Bottom line up front

**Four things are genuinely settled conventions and can be adopted without argument:**

1. **Absorptivity is defined identically everywhere:** `A(ω) = 1 − |S₁₁|² − |S₂₁|²`, collapsing to `A(ω) = 1 − |S₁₁|²` **only where transmission is zero** — which a ground-backed absorber guarantees and an unbacked one does not. Every source checked uses the definition; no decision is needed about *it*. **Which form applies to a given structure is a decision, and the reproduction anchor takes the two-port form** — see §1.
2. **The threshold is 90% absorption, equivalently −10 dB reflectivity.** These are *the same number*, not two conventions — see §2. It is the field's default and it is what "effective bandwidth" means.
3. **Bandwidth is reported two ways together:** absolute (GHz) and fractional (`FB = BW/f₀`, as a percent). Fractional bandwidth is what lets designs at different centre frequencies be compared.
4. **Angle and polarisation are reported as retention statements** — "absorptivity stays above X% out to θ°, for TE and TM separately" — not as scored quantities.

**The headline finding, and the direct answer to #110's central question.** The peak-versus-bandwidth trade is not a heuristic in this field. It is a **sum rule** with a proof: the Rozanov bound states that the integral of log-reflectivity over wavelength is capped by the absorber's thickness. In plain terms: **for a given thickness you have a fixed budget of "absorption × bandwidth," and deep-and-narrow versus shallow-and-wide are two ways of spending the same budget.** "Broader but shallower" is exactly what the physics says damping must do. #110 does not need to invent a way to express the trade — it needs to adopt the sum rule, which also supplies the fair-comparison metric that raw bandwidth cannot.

**A thickness-normalised, dimensionless figure of merit does exist**, published as `FOM_norm = FB / (h_norm × maxR)` (Huynen 2022, §6). It is well-posed and directly adoptable. But it is **thinly used, and the paper that defines it mis-tabulates its own values** — recomputing its Eq. 7 from its own inputs reverses its ranking (§6.3). Adopt the *definition*; recompute every *number*.

**What has no convention at all — and so must be decided, not looked up:**
- How simulated and measured curves are compared. The field says "in good agreement" and stops. There is **no quantitative agreement metric** (§8). This is precisely what #110's reproduction-scoring question needs, and the literature does not supply it.
- Whether in-band performance is scored as a worst case or as a mean. The one published combined FOM uses **worst case in band**; most papers report the peak, which is the opposite end. Nobody argues the choice (§7.2).
- Off-band behaviour. Essentially never reported or scored (§7.3).

**Caution on the method.** Unlike #117, there is **no doctrine to inherit here.** IEEE Std 1128 is the only standards-body document in this space; its published scope stops at **5 GHz**, below X-band, it is a *non-mandatory* recommended practice, and it standardises **how to measure** reflectivity, not **how to score** an absorber (§9). So #110 is adopting *journal convention* — real and consistent, but weaker evidence than MIL-STD-961E was for #117. The Rozanov bound is the one exception: it is a theorem, and it is the strongest thing in this document.

---

## 1. The one universal definition

Every source checked defines absorptivity the same way:

> "A(ω) = 1 − R(ω) − T(ω) = 1 − |S11|2 − |S21|2"
> — [MATEC Web Conf. 398, 01021 (2024), "Design and analysis of X-band metamaterial absorber"](https://doi.org/10.1051/matecconf/202439801021), Eq. 1 (verbatim, extracted from the PDF)

Identically in [PMC10489010](https://pmc.ncbi.nlm.nih.gov/articles/PMC10489010/) ("A(ω) = 1 − R (ω) − T(ω)= 1 − |S11|2 − |S21|2"), [PMC4464061](https://pmc.ncbi.nlm.nih.gov/articles/PMC4464061/), [PMC12900087](https://pmc.ncbi.nlm.nih.gov/articles/PMC12900087/) and [PMC9962083](https://pmc.ncbi.nlm.nih.gov/articles/PMC9962083/).

**In plain terms.** `S₁₁` is the fraction of the wave's *voltage* that bounces back; `S₂₁` the fraction that passes through. Squaring converts voltage to power. Whatever power neither bounces nor passes through must have been turned into heat — that is the absorption. So absorptivity is not measured directly; it is what is left over.

**The simplification that matters for us.** With a solid ground plane behind the absorber, nothing gets through, so `S₂₁ = 0` and:

> "A(ω) = 1 − |S11|2"
> — [PMC12900087](https://pmc.ncbi.nlm.nih.gov/articles/PMC12900087/) (verbatim)

**US12089385B2's Example 3 is *not* ground-backed, so this is the wrong form for it.**
`docs/seven-example-design-unknowns.md` records the anchor as two-port, Floquet on both faces,
no ground plane, and gives the reason from the patent's own drawing: FIG. 7G plots a non-zero
**Transmission** trace, which a metal-backed structure cannot produce. Landy *et al.*'s device —
which Example 3 reproduces symbol for symbol — suppresses transmission with a **cut wire**, not a
ground plane, which is why that trace exists at all.

> **This error regenerates — read before reapplying the one-port form.** ADR-0017 makes skins
> *this programme builds* print their own reflector, so **our own** designs genuinely are
> one-port and `A = 1 − |S₁₁|²` is right for them. Example 3 is **somebody else's device**, used
> as a blind reproduction target. Applying the programme's default to it is a category error, not
> a slip, and it has already been made once (`RUNNING-LISTS.md` §3 correction 25).

**So the loop needs both forms, selected by whether the structure being evaluated has a
reflecting backing — not one form adopted as universal.** The two-port definition is
`LITERATURE-SUPPORTED` and genuinely unanimous; the one-port collapse is `CALCULATED`, exact
only when `S₂₁ = 0`.

**This is now enforced in the design family registry, not just stated in prose (issue #216).**
`designs/design_families.py`'s `ABSORBER` family had `requires_ground_plane=True` while carrying
Example 3 — the ground-less, two-port structure this section describes — as its assigned anchor,
which is exactly the contradiction this document warns against. The fix was to split the family:
`ABSORBER` stays the ground-backed, one-port family this programme's own designs default to
(ADR-0017), and `ABSORBER_TRANSMISSIVE` is the new, ground-less, two-port sibling that Example 3
actually is. `DesignFamily.__post_init__` now refuses to construct a family whose
`requires_ground_plane` flag and `port_count` disagree, so this particular error cannot regenerate
silently in code the way it did in this document.

---

## 2. The threshold: −10 dB and 90% are the same number

This was worth checking rather than assuming, and the arithmetic confirms the equivalence the ticket suspected.

`−10 dB` reflectivity means `20·log₁₀|S₁₁| = −10`, so `|S₁₁| = 0.3162` and `|S₁₁|² = 0.100`. With zero transmission, `A = 1 − 0.100 = 0.90`. `CALCULATED`, exact.

> "A reflection loss of −10 dB attenuates approximately 90% of the incident wave."
> "the frequency range that meets this condition is called effective absorption bandwidth (EAB)"
> — as stated across the RAM review literature (see §3)

**So "−10 dB bandwidth", "90% absorption bandwidth" and "effective absorption bandwidth" are three names for one quantity**, provided transmission is zero. For a ground-backed absorber it always is; **for an unbacked one it is not, and the reproduction anchor is unbacked** (§1). This is the most useful simplification in this document: it collapses what looked like competing conventions into one.

**Conversions worth having in the code** (`CALCULATED`):

| Absorption | Reflectivity |S₁₁|² | |S₁₁| (dB) |
|---|---|---|
| 80% | 0.20 | −6.99 dB |
| 90% | 0.10 | **−10.0 dB** |
| 95% | 0.05 | −13.0 dB |
| 99% | 0.01 | −20.0 dB |

### 2.1 The threshold is dominant but not universal — and the outliers are instructive

- **90% / −10 dB** — the default. Used by [PMC12900087](https://pmc.ncbi.nlm.nih.gov/articles/PMC12900087/) ("A ≥ 0.9 (90%)"), [PMC4464061](https://pmc.ncbi.nlm.nih.gov/articles/PMC4464061/) ("absorption above 90% in the frequency range from 3.9 to 26.2 GHz"), [PMC10489010](https://pmc.ncbi.nlm.nih.gov/articles/PMC10489010/), [PMC7483420](https://pmc.ncbi.nlm.nih.gov/articles/PMC7483420/), and the whole RAM/EAB tradition.
- **−15 dB and −20 dB** appear where a paper wants a stiffer claim. The MATEC literature survey cites a design "with reflectivity below -15 dB and absorption exceeding 90%", and [PMC11751355](https://pmc.ncbi.nlm.nih.gov/articles/PMC11751355/) works at "maximum allowable reflection ρ₀ = 0.1" while noting ρ₀ = 0.316 (−10 dB) as the standard.
- **95% / R < 5%** is used by Huynen 2022 as the design target ("reflectivity below 5%, corresponding to R < -13 dB").
- **70%** — a genuine outlier. [PMC7316865](https://pmc.ncbi.nlm.nih.gov/articles/PMC7316865/) states bandwidth was "calculated for frequencies with more than 70% absorption (for ensuring −10dB value of S11 and S21 parameters)." **That justification does not compute.** If both `|S₁₁|² ≤ 0.1` and `|S₂₁|² ≤ 0.1`, then `A ≥ 1 − 0.1 − 0.1 = 0.80` — 80%, not 70% (`CALCULATED`). The stated rationale and the stated number disagree.

**What this means for #110.** The threshold is a **parameter of the metric, not a property of the field.** Papers state it, and are inconsistent about it. So the loop must *carry the threshold explicitly alongside every bandwidth number* rather than hard-coding 90% — otherwise two candidates scored under different thresholds become silently incomparable. This maps cleanly onto #117's machinery: **the threshold is the requirement's threshold value**, and it must be recorded, not assumed.

---

## 3. Two reporting traditions, one physics

The literature splits into two vocabularies. Both are correct; they belong to different communities, and **#110 touches both** — the metamaterial tradition because Example 3 is a patterned surface, the RAM tradition because MXene absorber work is published almost entirely in it.

| | **Metamaterial / FSS tradition** | **RAM / composite tradition** |
|---|---|---|
| Object | patterned surface, unit cell, Floquet solve | bulk lossy composite slab |
| Primary quantity | **Absorptivity A(ω)**, in % | **Reflection Loss RL**, in dB (negative) |
| Peak metric | peak absorptivity (e.g. "99.96%") | `RL_min` (e.g. "−38.20 dB") |
| Band metric | absorption bandwidth where A ≥ 90% | `EAB`, range where RL < −10 dB |
| Thickness | reported, rarely normalised | **always reported as "matching thickness" `t_m`** |
| Typical claim | "99% at 10.2 GHz, 90% bandwidth 2.1 GHz" | "RL_min −38.2 dB at 2.40 mm; EAB 7.36 GHz at 1.95 mm" |

**The RAM tradition's habit is the better one, and #110 should steal it.** It never quotes a performance number without the thickness that produced it, because RL genuinely depends on thickness — the same material at 1.95 mm and 2.40 mm is two different absorbers. Note in the example above that **the thickness maximising bandwidth is not the thickness minimising reflection.** That is the peak-versus-bandwidth trade showing up as a hard, published fact, in the very material family #110 cares about.

### 3.1 The RAM tradition's own critique of `RL_min` — directly relevant to #110

There is a live methodological argument in this literature that bears on the ticket's "peak or bandwidth?" question, and it comes down hard on the side of *not* scoring the peak:

> "One cannot simply evaluate microwave absorbing materials by concluding that an RL value of −30 dB outperforms −20 dB … nor can it be straightforwardly asserted that −50 dB is better than −40 dB."
> "The value of reflection loss from conventional calculations can be artificially adjusted by sample thickness."
> "any magnetic or dielectric material can theoretically and practically achieve perfect matching, resulting in an RL value of negative infinity."

— as summarised across the critique literature, principally Yang et al., *"On the Quality Criteria for Microwave Absorbing Materials,"* Advanced Electronic Materials (2025), [doi:10.1002/aelm.202500239](https://advanced.onlinelibrary.wiley.com/doi/full/10.1002/aelm.202500239) — **paywalled, see §11 (stranded)** — and Ref. [AIP Advances 8, 015223 (2018)](https://pubs.aip.org/aip/adv/article/8/1/015223/991187/A-theoretical-and-practical-clarification-on-the), also unreachable. `LITERATURE-SUPPORTED`, but read through secondary summary rather than the primary text; **treat the exact wording as unverified.**

**In plain terms:** a very deep absorption null is not evidence of a good absorber. A null that deep is a *coincidence of perfect impedance matching at one frequency and one thickness*, and you can manufacture one for almost any lossy material by tuning the thickness to a fraction of a millimetre. It is sharp, fragile, and says nothing about how the thing behaves across a band or after fabrication tolerance.

**Consequence for #110.** Scoring on **peak absorption is the choice the field itself warns against**, on the explicit grounds that the peak is tunable to arbitrary depth and therefore not discriminating. This is not a preference; it is a documented objection with a mechanism. It also means the ticket's worry — that choosing "peak" quietly biases toward silver — is a *double* problem: it would bias the loop *and* score on the metric the literature considers least meaningful.

---

## 4. The bandwidth conventions

Four are in use. Only the first two matter for #110.

**(a) Absolute bandwidth (GHz)** above a stated threshold. Universal. Meaningless on its own without both the threshold and the centre frequency.

**(b) Fractional bandwidth `FB`** — the dimensionless one.

> "the fractional bandwidth as FB = BW / fo, where fo is the center frequency of the absorption bandwidth BW"
> — [Huynen, *Front. Mater.* 9:1040753 (2022)](https://doi.org/10.3389/fmats.2022.1040753), Eq. 6 (verbatim from the PDF)

Reported as a percentage. This is what makes designs at different centre frequencies comparable. The MATEC survey shows how routine it is: "a fractional bandwidth of 170% (1.4 to 17.31 GHz)", "fractional bandwidth of 114.40%", "fractional bandwidth of 112%", "a wide fractional bandwidth of 137%".

*Note the values above 100%.* `FB = (f₂−f₁)/f₀` with `f₀` the arithmetic centre can exceed 100% for very wide bands — it is a ratio, not a proportion, and does not saturate at 1. Do not "sanity-check" it by clamping to 100%.

**(c) FWHM** — full width at half maximum. The narrowband-resonator convention, from the founding paper of the field:

> "a simulated full width at half maximum (FWHM) absorbance of 4%"
> — [Landy et al., *A Perfect Metamaterial Absorber*, arXiv:0803.1670](https://arxiv.org/abs/0803.1670)

Half-maximum of a 99% peak is ~50% absorption — far too permissive to be a requirement threshold. **Do not use FWHM for scoring**; it describes resonance sharpness, not useful band. It also underlies the Q-factor convention (`Q = f/FWHM`, [PMC9962083](https://pmc.ncbi.nlm.nih.gov/articles/PMC9962083/)), which belongs to sensing applications, not absorbers.

**(d) EAB at a stated matching thickness** — the RAM form of (a). See §3.

---

## 5. The peak-versus-bandwidth trade: it is a sum rule, not a heuristic

**This is the most important section for #110.**

### 5.1 The Rozanov bound

For any metal-backed absorber of thickness `d_RL`:

> "d_RL ≥ 1/(2π²µ_s) · |∫₀^∞ ln |r̃(λ)| dλ| ≡ d_R"
> where "µ_s = Re{µ}|_{λ→∞} is the static permeability of the absorber"
> — Deng, Khatib, Tarokh & Padilla, *Fundamental absorption bandwidth to thickness limit for transparent homogeneous layers*, [arXiv:2308.14839](https://arxiv.org/abs/2308.14839), Eq. 2 (verbatim, extracted from the PDF), attributing the result to Rozanov 2000

Independently stated by Huynen 2022, Eq. 3 (verbatim from the PDF): `∫_{λ1}^{λ2} ln|R(λ)| dλ ≤ 2π² d_R`.

Original: **K. N. Rozanov, "Ultimate thickness to bandwidth ratio of radar absorbers," *IEEE Trans. Antennas Propag.* 48(8):1230–1234, 2000.** The citation is verified from the reference lists of both papers above; **the original is IEEE-paywalled and was not read** (§11). What is verified is its *restatement* in two independent open-access sources that agree.

### 5.2 What it actually says, in plain terms

`ln|r̃(λ)|` is negative wherever the absorber works (reflection below 1), and more negative the better the absorption. Integrating it across wavelength adds up "how much absorption, over how much band." The theorem says **that total is capped by the thickness** — and by nothing else. No amount of cleverness in the pattern, the material or the layer stack raises the cap.

So:

> **For a fixed thickness, absorption depth and bandwidth are the same resource. Spending more on one necessarily spends less on the other.**

That is the ticket's "damping the resonance: broader band, shallower peak," derived rather than observed. MXene is not doing something unusual to the design; it is moving along a boundary that thickness alone sets. **The trade is real, it is quantitative, and it is not a matter of taste.**

Three consequences follow immediately, and they settle questions #110 raises:

1. **"Peak or bandwidth?" is a malformed question at fixed thickness.** They are one quantity viewed from two ends. The well-formed question is *where on the trade curve the requirement sits*, which is exactly what a threshold/objective pair from #117 expresses.
2. **A candidate can only be beaten fairly by another of the same thickness** — unless the score normalises for thickness (§6).
3. **The bound gives an absolute reference.** Any candidate can be scored as a fraction of the best physically possible absorber of its thickness. That is a meaningful zero-to-one scale, not an arbitrary one.

### 5.3 The engineering shortcut — and a worked number for a *ground-backed* skin

Take the idealised case: reflectivity is flat at `ρ₀` across the band `λ₁…λ₂` and unity elsewhere. Then `(λ₂−λ₁)·ln(1/ρ₀) ≤ 2π²µ_s d`, so:

> **d ≥ Δλ · ln(1/ρ₀) / (2π² µ_s)**

`CALCULATED` from the verbatim inequality above. For a non-magnetic absorber (`µ_s = 1`):

| Threshold | ρ₀ | Minimum thickness |
|---|---|---|
| −10 dB (90%) | 0.3162 | `d ≥ Δλ / 17.15` |
| −15 dB | 0.1778 | `d ≥ Δλ / 11.43` |
| −20 dB (99%) | 0.1000 | `d ≥ Δλ / 8.57` |

The `1/17` recovers Rozanov's best-known result — for a broadband absorber (where `λ₁ ≪ λ₂`, so `Δλ ≈ λ_max`) the minimum thickness is about **one-seventeenth of the longest operating wavelength**. It also matches the engineering form quoted in the review literature, `f_L = cΓ₀/(172·d)` with `Γ₀` in dB: at `Γ₀ = 10 dB` that is `λ_L = 17.2·d`. Two independent routes agreeing to three significant figures.

> **Two corrections govern what follows; the arithmetic below is unchanged but what it is
> *about* is not.**
>
> **Rozanov does not apply to the reproduction anchor at all.** The bound's own opening fixes a
> slab *"overlying a **perfectly reflecting plane**"*, and Eq. (6) is stated for *"any
> **metal-backed** magnetodielectric layer"* (`rozanov-bound-primary-source.md`;
> `RUNNING-LISTS.md` §3 correction 26). Example 3 is unbacked (§1), so the derivation's
> bookkeeping does not close for it — energy has a third place to go, straight through.
>
> **And `8.5–10.5 GHz` is a plot axis, not a requirement.** The patent says only that FIG. 7G
> *"shows simulated scattering performance … over select frequencies ranging from
> 8.5-10.5×10⁹ Hz"*. Nothing states the device must absorb across it (§3 correction 27).
> **Rozanov is linear in Δλ**, so every figure below scales one-for-one with that axis label —
> which is exactly why reading a requirement off a plot is not a harmless shorthand.

**Worked for a ground-backed skin over an 8.5–10.5 GHz span** — `CALCULATED`. This is a valid
calculation for a design **this programme builds**, since ADR-0017 makes those one-port by
construction; the span is carried over from FIG. 7G as an illustrative X-band sub-band, not as
anyone's stated requirement:

- λ at 8.5 GHz = 35.27 mm; λ at 10.5 GHz = 28.55 mm; **Δλ = 6.72 mm**
- −10 dB across the whole span requires **d ≥ 0.392 mm**
- −20 dB across the whole span requires **d ≥ 0.784 mm**

**Read this carefully, because it is good news and a trap at once.** A sub-2 mm build is comfortably above both bounds, so **the Rozanov limit is not binding at this thickness over a span this narrow.** (It was previously stated here as a fact about Example 3. It is not one: the bound does not govern an unbacked structure, and the span it was evaluated over was a plot axis. The conclusion below holds for a ground-backed skin the programme builds, which is where it is useful.) A 2 GHz band at X-band is narrow, and narrow bands are cheap in thickness. So the bound will *not* discriminate between candidates here — it will report every candidate as sitting well below its ceiling.

That is still worth computing, for two reasons. It tells the loop that **thickness is not the constraint for this requirement**, so a candidate failing to meet the band is failing on design or material, not on physics. And it makes the metric *ready* for the wideband requirements the loop is eventually pointed at, where it will bind hard.

---

## 6. The thickness-normalised figure of merit — it exists

This answers task item 4 directly: **yes, a dimensionless FOM accounting for thickness exists in the published literature.**

### 6.1 The definitions

From [Huynen, *Front. Mater.* 9:1040753 (2022)](https://doi.org/10.3389/fmats.2022.1040753), all verbatim from the PDF:

> Eq. 6 — "the fractional bandwidth as FB = BW / fo"
> Eq. 7 — "FOM = FB / (h_tot × max R)" — "Where h_tot is the total height of the structure and maxR is the maximum value as reported in Table 1, but expressed in natural value, not in %."
> Eq. 8 — "h_tot norm = h_tot · fo / co"
> Eq. 9 — "**FOM_norm = FB / h_tot norm**"

and the design intent, stated plainly by the author:

> "This definition (7) indicates that we are interested in having the lowest magnitude of reflectivity R over the highest possible relative bandwidth and for the lowest thickness."

### 6.2 Why this is the right shape for #110

`h_tot,norm = h_tot·f₀/c₀` is **thickness measured in wavelengths** — the "electrical thickness" the ticket asked about. `FB` is dimensionless, `maxR` is dimensionless, so **`FOM = FB/(h_norm × maxR)` is a pure number.** Two candidates of different physical thickness, at different centre frequencies, can be ranked against each other on it. Raw bandwidth cannot do that.

It also folds all three of #110's competing criteria into one scalar with the correct signs: **more bandwidth is better, less thickness is better, lower worst-case reflectivity is better.** That is the "stated combination" the ticket asks whether it should adopt — and it is published, not invented.

**Note carefully what `maxR` is.** It is the **maximum (worst) reflectivity within the absorption band** — not the peak absorption. So this FOM scores the *worst point in the band*, not the best. That is a minimax formulation, and it is the opposite of the peak-absorptivity habit of the metamaterial papers. It is also the choice consistent with §3.1's critique. See §7.2.

### 6.3 An arithmetic audit — adopt the definition, not the numbers

Recomputing the paper's own Eq. 7 from the inputs tabulated in its own Table 4 (`CALCULATED`):

| Profile | FB (%) | h_tot (mm) | maxR | FOM recomputed | FOM as published | ratio |
|---|---|---|---|---|---|---|
| Uniform | 13.3 | 1.75 | 0.26 | 29.2 | 29 | 0.99 ✓ |
| Dot | 57.9 | 2.75 | 0.16 | 131.6 | 132 | 1.00 ✓ |
| Triangular | 67.9 | 2.75 | 0.60 | 41.2 | 411 | 9.99 ✗ |
| Sinusoidal | 128 | 2.75 | 0.44 | 105.8 | 1162 | 10.98 ✗ |
| Optimized | 126 | 3.75 | 0.30 | 112.0 | 1115 | 9.96 ✗ |

Two rows reproduce exactly; three are larger than Eq. 7 gives by a factor of ~10. Because two rows match exactly, this is a transcription error, not a different definition.

**It changes the paper's conclusion.** The paper states "the sinusoidal profile and its optimized version exhibit the best performances in terms of FOM." On the recomputed values the ranking is **Dot (131.6) > Optimized (112.0) > Sinusoidal (105.8)** — the Dot profile wins.

Separately, the paper's Table 5 (its comparison against seven published absorbers) has a column headed `h_tot norm` that does **not** contain `h_tot·f₀/c₀`. It contains `c₀/f₀` — the free-space wavelength in mm (`CALCULATED`: Zhou 41.4 vs 41.3 published; Abdullahi 29.8 vs 29.8; Chang 23.1 vs 23.0; Sun 24.0 vs 24.0). So **Eq. 9, the dimensionless FOM, is defined in this paper but never actually applied in it.**

**Verdict.** `FOM_norm` is a sound, well-posed, adoptable *definition* with essentially **no track record of correct use**. That is an honest and useful thing to know: #110 would be adopting a published definition, not a validated practice, and should recompute every literature value it compares against rather than quoting published FOMs.

### 6.4 The other normalisation: percentage of the Rozanov limit

The more rigorous normalisation is against the bound itself. Both sources do this:

> "the sinusoidal profile has the best compactness performance since its thickness value is closest to the corresponding Rozanov thickness limit, the difference being less than 10%"
> — Huynen 2022 (verbatim), tabulating physical thickness against `d_R` side by side

> "achieves 95.5% of the fundamental limit"
> — [PMC11751355](https://pmc.ncbi.nlm.nih.gov/articles/PMC11751355/), on a dispersive-grid absorber

**This is the cleanest dimensionless score available:** `η = d_R / d_actual`, a number in (0, 1] where 1 means "at the physical limit for this thickness." It is defensible, it has a meaningful zero and a meaningful one, and unlike `FOM_norm` it is grounded in a theorem rather than a convention. Its weakness for #110 is §5.3: at Example 3's narrow band it will not discriminate.

---

## 7. Angle, polarisation, and off-band

### 7.1 What is reported

**Angle.** Universally reported as a **retention statement**: absorptivity stays above a stated level out to a stated angle, TE and TM given separately. Sampling is coarse and discrete.

- [PMC12900087](https://pmc.ncbi.nlm.nih.gov/articles/PMC12900087/): evaluated at "0°, 15°, 30°, 45°, 60°, 75°, and 80°" for both TE and TM.
- [PMC9962083](https://pmc.ncbi.nlm.nih.gov/articles/PMC9962083/): "0° to 45°" for TE and TM.
- [PMC10489010](https://pmc.ncbi.nlm.nih.gov/articles/PMC10489010/): 0°–50°, with TM degrading — "frequency deviation…about 1 GHz".
- Huynen 2022 designs to "incidence angles up to 60°".
- [PMC7483420](https://pmc.ncbi.nlm.nih.gov/articles/PMC7483420/): "absorptivity above 90% in the widest incident angle up to 87°".

**45° and 60° are the common benchmarks.** TE and TM diverge at angle and are never averaged — TM typically holds better in these results.

**Polarisation.** Reported as a **binary property justified by symmetry**, not a measured spread. The standard argument is four-fold rotational symmetry of the unit cell:

> "maintains stable absorption performance for varying polarization states" due to its "four-fold symmetric geometry"
> — [PMC12900087](https://pmc.ncbi.nlm.nih.gov/articles/PMC12900087/) (verbatim)

Review-level tables record it as literally "Yes/No" ([Front. Phys. 10:893791](https://www.frontiersin.org/journals/physics/articles/10.3389/fphy.2022.893791/full)).

### 7.2 Pass/fail or scored? — the field treats both as pass/fail, and #110 should not follow blindly

In the comparison tables that decide whether a paper claims novelty, angle and polarisation appear as **qualifiers, not as scored dimensions.** The tabulated columns are performance and geometry:

- [PMC12900087](https://pmc.ncbi.nlm.nih.gov/articles/PMC12900087/): `Ref | No. of Absorption Bands | Resonance Freq (GHz) | Unit Cell Size (mm) | Thickness of Unit Cell (mm) | Absorptivity (%)`
- [PMC9962083](https://pmc.ncbi.nlm.nih.gov/articles/PMC9962083/): `Reference | Size (mm) | Frequency Range (GHz) | Design | Absorption (%) | Other Factors`

Angle and polarisation are relegated to prose or to "Other Factors." **No paper found scores them.** Polarisation insensitivity in particular is asserted from geometry and then not quantified at all.

**In #117's vocabulary this is exactly a threshold with no objective** — a hard floor ("must hold to 45°") with no credit for exceeding it. That is a legitimate and well-precedented shape, and it is what the field does. But note the field's version is *weaker than it looks*: "polarisation-insensitive because four-fold symmetric" is an `INFERRED` claim from geometry, not a `SIMULATED` or `MEASURED` one. If the loop is going to admit non-symmetric cells at all, it must actually sweep polarisation rather than inherit the symmetry argument.

### 7.3 Off-band: no convention exists

**Nothing found reports out-of-band behaviour as a metric.** Papers plot the full simulated range, so it is visible, but it is never thresholded, tabulated or scored. A design that absorbs strongly outside the required band is not penalised anywhere in this literature.

This is a genuine gap rather than a consensus that it does not matter — an absorber that also absorbs a friendly communications band is a real problem, and the literature simply does not address it. **#110's question about off-band behaviour has no answer to look up.** See §10.

---

## 8. Simulated versus measured: there is no agreement metric

Task item 6, and the answer is a clean negative.

Papers with both simulated and measured curves compare them **qualitatively and then stop**:

> "the simulation results are consistent with the test results whether the TE wave or TM wave is incident vertically"
> — [PMC10489010](https://pmc.ncbi.nlm.nih.gov/articles/PMC10489010/) (verbatim)

> "The simulated and measured data are quite similar except few deviations from resonance frequencies at the higher range"
> — [PMC7316865](https://pmc.ncbi.nlm.nih.gov/articles/PMC7316865/) (verbatim)

Landy et al.'s founding paper compares "a peak absorbance greater than 88%" measured against "96%" predicted, and describes the difference in words.

Where discrepancy is quantified at all, it is reported as **isolated scalar differences at chosen points** — a frequency shift ("5.6 GHz measured vs 5.8 GHz simulated"), or a peak-value gap ("98% measured vs 99.9% simulated") — never as a metric over the curve. No correlation coefficient, no RMS error, no band-limited residual, no agreement tolerance. Causes are attributed narratively: fabrication tolerance, material property mismatch, measurement conditions.

**Consequence for #110's fourth bullet.** The ticket asks whether reproducing Example 3 scores differently from designing to a requirement, and suspects reproduction wants "a correlation metric, not a success score." **The literature confirms the suspicion and supplies nothing to adopt.** There is no field convention for curve agreement. This is the clearest "must be decided, not looked up" item in this document.

Two honest observations to carry into that decision:

- The repo already has vocabulary for it. `CONTEXT.md` and ADR-0013 describe correlation as a distinct activity, and the map lists `CORRELATION` as its own gated step alongside `SIMULATION` — **the loop's own model already separates the two mechanisms.** The literature's silence is not an argument for merging them.
- Per the map and #133, there is no VNA, so the comparison for Example 3 is **simulated-versus-published-curve**, not measured-versus-simulated. That is a *different and easier* problem than the one the papers are doing badly — both curves are numerical, so a genuine curve metric (RMS error in dB over the band, or band-edge and depth agreement) is available in a way it is not when one side is a noisy measurement.

---

## 9. Is there a standard to adopt, as #117 had?

**Partly, and not for scoring.**

**IEEE Std 1128-1998**, *"Recommended Practice for RF Absorber Evaluation in the Range of 30 MHz to 5 GHz"* — verbatim title from [Chen, Rodriguez & Foged, "Progress on the Development of IEEE Std 1128," NSI-MI technical paper (2023)](https://www.nsi-mi.com/-/media/project/oneweb/oneweb/nsi/files/technical-papers/2023/progress-on-the-development-of-the-isss-std-1128.pdf) (extracted from the PDF).

Three facts, all verbatim from that paper, decide its relevance:

1. **Its published scope stops at 5 GHz — below X-band.** The revision in progress will change the title to "in the Range of 30 MHz to 40 GHz," but as of that 2023 paper the working group was "in the final stage of collecting inputs" and had not produced a draft for balloting. **X-band is not covered by the published standard.**
2. **It is not mandatory.** "The IEEE Std 1128 falls under the recommended practice category; therefore, the application of the test methods is not mandatory."
3. **It standardises measurement, not scoring.** Its content is methods — "the NRL arch method and coaxial reflectometer method," waveguide methods, and a focused-beam free-space method. It tells you how to obtain a reflectivity number. It does not define a figure of merit, a threshold, or a way to rank absorbers.

It also targets **anechoic chamber lining** — thick pyramidal absorber — not thin conformal skins. Different application, different constraints.

**So the #117 move does not fully repeat here.** #117 found binding doctrine (MIL-STD-961E, JCIDS) that could be adopted wholesale. #110's field has a non-mandatory measurement practice that does not reach X-band and does not address scoring at all. What #110 can adopt is **journal convention plus one theorem.** The theorem (Rozanov) is the strongest evidence in this document; the conventions are consistent and worth adopting, but they are practice, not doctrine — and §6.3 shows practice is not always executed carefully.

*Useful side note for the map's open item on measurement.* The **NRL arch** — two horns on a non-reflective arch, a metal plate as the 0 dB reference, sample laid on the plate, ratio taken — is the standard free-space reflectivity fixture, and it is a **reflection-only, single-quantity measurement**, not a 2-port S-parameter set. That is consistent with #106's free-space horn coupons and bears on the map's open question about how free-space reflection data enters MEASUREMENT.

---

## 10. The conventions table

| Convention | Exact definition | How commonly used | Directly adoptable for #110? |
|---|---|---|---|
| **Absorptivity** | `A(ω) = 1 − \|S₁₁\|² − \|S₂₁\|²`; **ground-backed only** → `A = 1 − \|S₁₁\|²` | **Universal.** Every source checked. | **Adopt the two-port definition as-is.** The one-port collapse is a per-structure choice, **not** a default — the reproduction anchor is unbacked (§1). Enforced in code as two families, `ABSORBER` (ground-backed) and `ABSORBER_TRANSMISSIVE` (Example 3's shape) — see §1 and issue #216. |
| **90% absorption threshold** | Band where `A ≥ 0.90` | **Dominant default.** | **Yes**, but store the threshold as a requirement value, don't hard-code it. |
| **−10 dB reflectivity threshold** | Band where `20log₁₀\|S₁₁\| ≤ −10` | **Dominant** in FSS/circuit-analog work. | **Yes — same quantity as above.** `CALCULATED` identity, exact when `S₂₁=0`. |
| **Effective Absorption Bandwidth (EAB)** | Frequency range where `RL < −10 dB`, quoted **with the thickness that produced it** | **Universal in RAM/composite work**, incl. MXene. | **Yes**, and adopt its discipline: never quote a band without its thickness. |
| **Absolute bandwidth (GHz)** | `f₂ − f₁` at the stated threshold | Universal. | Report, but **do not rank on it** — not comparable across thicknesses or bands. |
| **Fractional bandwidth `FB`** | `FB = BW/f₀`, `f₀` = centre of the absorption band; as % (can exceed 100%) | **Very common**, standard cross-design comparator. | **Yes — adopt.** |
| **FWHM / Q-factor** | Width at half-maximum absorbance; `Q = f/FWHM` | Common in narrowband and sensing work. | **No.** Half of 99% is ~50% — far too permissive as a requirement threshold. |
| **Peak absorptivity / `RL_min`** | Best single point in band | **Very common**, and **explicitly criticised** (§3.1) as tunable to arbitrary depth. | **Report, do not rank on it.** The field's own critique says the peak is not discriminating. |
| **`maxR` — worst in-band reflectivity** | Maximum reflectivity across the absorption band | **Rare** — found only in Huynen 2022's FOM. | **Yes, prefer it to peak.** Minimax matches a "≥90% across the whole band" requirement. |
| **Rozanov bound** | `d ≥ (1/2π²µ_s)·\|∫₀^∞ ln\|r̃(λ)\|dλ\|`; rectangular case `d ≥ Δλ·ln(1/ρ₀)/(2π²µ_s)` | **The field's one theorem.** Restated consistently in independent sources. | **Yes — adopt as the statement of the peak/bandwidth trade.** Note: won't bind at Example 3's narrow band. |
| **% of Rozanov limit** | `η = d_R / d_actual`, in (0,1] | Used as a comparator by at least two independent groups. | **Yes** — best-grounded dimensionless score. Weakly discriminating for narrow bands. |
| **`FOM_norm`** | `FB / (h_norm × maxR)`, `h_norm = h_tot·f₀/c₀` | **Defined once; not correctly applied even in its source paper** (§6.3). | **Yes, with eyes open.** Adopt the definition; recompute all literature values. |
| **Angular stability** | "A stays above X% out to θ°," TE and TM reported separately; 45°/60° benchmarks | **Universal as a statement**, never scored. | **Yes as a threshold** (#117 shape). Not as a scored term without a decision. |
| **Polarisation insensitivity** | Binary Yes/No, argued from four-fold symmetry | **Universal as a claim**, essentially never quantified. | **As a threshold only.** Note the field's version is `INFERRED` from geometry. |
| **Thickness in wavelengths** | `h·f₀/c₀` | **Surprisingly rare** — papers claim "ultra-thin" without computing it ([PMC9962083](https://pmc.ncbi.nlm.nih.gov/articles/PMC9962083/), [PMC12900087](https://pmc.ncbi.nlm.nih.gov/articles/PMC12900087/) both omit it). | **Yes — adopt, and note the field mostly doesn't.** |
| **Sim-vs-measured agreement** | — | **No convention exists.** Qualitative prose only. | **No. Must be decided (§8).** |
| **Off-band behaviour** | — | **No convention exists.** Never thresholded or scored. | **No. Must be decided (§7.3).** |
| **IEEE Std 1128** | Recommended practice, absorber **measurement** methods, 30 MHz–5 GHz | Real standard, but below X-band, non-mandatory, chamber-absorber oriented. | **Not for scoring.** Relevant to MEASUREMENT, not to the success score. |

---

## 11. Recommendation for #110

**Adopt this set. It is coherent, it is the field's, and it maps onto the machinery #117 already put in place.**

**1. Score on band-limited worst case, not on the peak.** For a requirement of the form "≥90% absorption across a stated band" — the band being whatever the customer asked for, never a figure read off a plot (§5.3) — the natural score is the **worst absorptivity anywhere in the band** (equivalently `maxR`, the worst reflectivity). This is what Huynen's FOM uses, it is what a "across the whole band" requirement literally means, and it sidesteps §3.1's documented objection to `RL_min`. It also answers the ticket's "threshold or gradient?" question in the cleanest available way: **worst-in-band is simultaneously both** — thresholded it prunes, un-thresholded it grades, and it can never reward a solver for a deep null at one frequency while failing elsewhere, which is exactly the failure mode the ticket names.

**2. Express the requirement as a threshold/objective pair on that quantity (#117).** *Threshold* `A ≥ 0.90 across the requirement's band` — below it, reject; *objective* a stated deeper value. **No band is stated for the reproduction anchor**: the patent gives FIG. 7G's 8.5–10.5 GHz plot range and no requirement (§5.3), so reproducing Example 3 is a curve-comparison exercise, not a threshold test, and #168's Feature Selective Validation is the shape that fits it. The trade space between them is where the solver works. No new mechanism is needed; absorption depth was already named as a first-class threshold/objective quantity in #117's resolution.

**3. Carry the threshold and the band with every bandwidth number.** §2.1 shows the field is inconsistent about the threshold (70%, 80%, 90%, 95%, −15 dB, −20 dB all appear). A bandwidth without its threshold is not a number, and two candidates scored under different thresholds are silently incomparable. This is a `requirement_targets.py` concern, and it fits the `ONE_OF`/second-value model changes #117 already identified.

**4. Report — and probably score — thickness-normalised.** Record `h_norm = h·f₀/c₀` for every candidate, and compute both `η = d_R/d_actual` (fraction of the Rozanov limit) and `FOM_norm`. This is what lets a 1.2 mm and a 1.8 mm candidate be compared honestly, which the ticket's MXene-versus-silver question ultimately requires. Recompute any literature value used for comparison (§6.3).

**5. Treat angle and polarisation as thresholds, not scored terms — for now.** That is what the field does, and #117's vocabulary already expresses it: a threshold with no objective. But record that the field's polarisation claim is `INFERRED` from four-fold symmetry, so if the loop admits non-symmetric cells it must actually sweep polarisation rather than inherit the argument. `45°` and `60°` are the defensible benchmark angles; TE and TM must be kept separate and never averaged.

**6. Keep the Rozanov bound in the loop as a diagnostic even though it will not bind for Example 3.** It reports whether a candidate's failure is a *design* failure or a *physics* failure. For Example 3 (§5.3: `d ≥ 0.392 mm` at −10 dB, against a sub-2 mm build) the answer will always be "design," which is itself worth stating plainly in a report. It becomes load-bearing the moment the loop is pointed at a wideband requirement.

**7. Keep reproduction scoring separate from requirement scoring.** §8 finds no convention to unify them, the repo's own model already separates `CORRELATION` from `SIMULATION`, and the two questions are genuinely different — "does this curve match that curve" is not "is this design good." Merging them would be inventing, not adopting.

### What this recommendation does to the ticket's MXene worry

The ticket fears that choosing "peak" biases toward silver and choosing "bandwidth" biases toward MXene. **The recommended set does neither, and the reason is principled rather than convenient.** Worst-in-band across a *stated* band is indifferent to how the candidate got there: a damped, broader, shallower response passes if its shallowest point in 8.5–10.5 GHz clears the threshold, and a sharp, deep resonance fails if it clears the threshold only at its centre. Neither material is advantaged by the choice of metric — they are advantaged or not by whether they meet the requirement as written. That is what "no thumb on the scale" looks like when the metric is chosen well, and it is a stronger position than picking peak or bandwidth and disclosing the bias.

---

## 12. What has no convention, and must be decided

Four items. The literature was searched for each and came back empty; these are decisions, not lookups.

1. **How to score agreement between a reproduced curve and the patent's published curve.** No metric exists in the field (§8). The loop must choose one — RMS error in dB across the band, band-edge agreement, depth-and-centre-frequency agreement, or a combination — and choose a tolerance. Note the favourable circumstance: with no VNA (per #133), both curves are numerical, which makes a real curve metric easier than the measured-versus-simulated case the papers handle badly.
2. **Whether off-band absorption is scored, constrained, or ignored.** Never addressed in the literature (§7.3). A real requirement often cares; the field does not. Silence here is the field's, not an answer.
3. **Whether worst-in-band or mean-in-band is the scored quantity.** §11 recommends worst-in-band, and the only published combined FOM agrees, but **the field does not argue the point** — most papers simply report the peak, which is the opposite end. Treat the recommendation as reasoned, not as inherited.
4. **Whether angle and polarisation ever become scored rather than pass/fail.** The field is unanimous that they are pass/fail, but it is unanimous by omission rather than by argument. If a requirement genuinely trades angular coverage against depth, there is no precedent to follow.

A fifth, noted for the map rather than for #110: **`FOM_norm` has no validated usage.** Adopting it means being the careful user of a definition its own author mis-applied.

---

## 13. What is stranded

Publishers returning 403 to automated fetching, with what was lost:

- **IEEE Xplore.** **Rozanov (2000), the primary source for the central theorem in this document, was not read.** Its citation is verified from the reference lists of two independent open-access papers, and its result is verified through their restatements, which agree with each other and with my own reduction (§5.3). But the original is unread, and any exact wording of Rozanov's own claims should be treated as second-hand. Also stranded: IEEE Std 1128-1998 itself (a full-text copy was found on a non-publisher host and deliberately not used).
- **Wiley.** Yang et al., *"On the Quality Criteria for Microwave Absorbing Materials,"* Adv. Electron. Mater. (2025), [doi:10.1002/aelm.202500239](https://advanced.onlinelibrary.wiley.com/doi/full/10.1002/aelm.202500239). **This is the most significant loss** — a 2025 paper explicitly about the field's scoring criteria and their replacement, i.e. exactly this document's subject. §3.1 rests on secondary summaries of it and should be re-checked against the original if access is obtained.
- **AIP.** *"A theoretical and practical clarification on the calculation of reflection loss for microwave absorbing materials,"* AIP Advances 8, 015223 (2018) — the other primary critique of `RL_min`.
- **ScienceDirect / Elsevier.** Several relevant reviews, including the systematic review of EM wave absorbers and the X-band polymer-composite RAM review.
- **MDPI.** Largely *recovered*, not stranded — much MDPI content is mirrored in PubMed Central, which fetches fine. Most of the per-paper evidence in §§1–7 came through PMC.

**Method note.** Where a summarising fetch and a direct PDF extraction disagreed, the PDF was taken (this happened twice, both times on Huynen 2022's equations — the summariser returned `c₀/π` and then `c₀/4π` for a constant that the PDF shows is neither, the actual equations being the integral forms of §6.1). **Every equation quoted verbatim in this document was extracted from the source PDF directly, not from a model summary.** Numbers labelled `CALCULATED` are my own arithmetic from those quoted equations and are reproducible from the inputs shown.

---

## Sources

**Primary — theory and figures of merit**
- Y. Deng, O. Khatib, V. Tarokh, W. J. Padilla, *Fundamental absorption bandwidth to thickness limit for transparent homogeneous layers*, [arXiv:2308.14839](https://arxiv.org/abs/2308.14839) (Nanophotonics, [doi:10.1515/nanoph-2023-0920](https://www.degruyterbrill.com/document/doi/10.1515/nanoph-2023-0920/html)) — Rozanov bound, Eq. 2, verbatim.
- I. Huynen, *Investigation of corrugated profiles in thin lossy dielectric slabs for wideband absorption up to 100 GHz*, [Front. Mater. 9:1040753 (2022)](https://doi.org/10.3389/fmats.2022.1040753) — Eqs. 3, 6, 7, 8, 9; Tables 3, 4, 5. **The FOM and normalised-FOM definitions.**
- K. N. Rozanov, *Ultimate thickness to bandwidth ratio of radar absorbers*, IEEE Trans. Antennas Propag. 48(8):1230–1234 (2000) — **cited, not read** (§13).
- [PMC11751355](https://pmc.ncbi.nlm.nih.gov/articles/PMC11751355/) — Rozanov limit as `Δλ/d < 2π²µₛ|ln ρ₀|`; "95.5% of the fundamental limit".
- [arXiv:2305.07235](https://arxiv.org/abs/2305.07235), *Beyond the Rozanov bound on electromagnetic absorption*.

**Primary — reporting conventions**
- N. I. Landy et al., *A Perfect Metamaterial Absorber*, [arXiv:0803.1670](https://arxiv.org/abs/0803.1670) — founding paper; FWHM convention.
- *Design and analysis of X-band metamaterial absorber*, [MATEC Web Conf. 398, 01021 (2024)](https://doi.org/10.1051/matecconf/202439801021) — absorptivity Eq. 1; Floquet/master-slave setup; survey of fractional-bandwidth reporting across ~6 prior works.
- [PMC12900087](https://pmc.ncbi.nlm.nih.gov/articles/PMC12900087/) — hexa-band S/C/X/Ku absorber; `A ≥ 0.9`; angle sweep 0–80°; comparison-table columns.
- [PMC10489010](https://pmc.ncbi.nlm.nih.gov/articles/PMC10489010/) — ultra-wideband transparent absorber; −10 dB = >90% over 8.7–38.9 GHz; TE/TM to 50°.
- [PMC4464061](https://pmc.ncbi.nlm.nih.gov/articles/PMC4464061/) — wideband lightweight absorber; 90% threshold; FB 148.2%.
- [PMC7316865](https://pmc.ncbi.nlm.nih.gov/articles/PMC7316865/) — X/Ku symmetric absorber; the 70%-threshold outlier (§2.1).
- [PMC9962083](https://pmc.ncbi.nlm.nih.gov/articles/PMC9962083/) — ultra-thin triple-band; FWHM/Q; 0–45°; comparison-table columns.
- [PMC7483420](https://pmc.ncbi.nlm.nih.gov/articles/PMC7483420/) / [arXiv:2007.02348](https://arxiv.org/abs/2007.02348) — honeycomb absorber; 90% to 87° incidence.
- [PLOS ONE 13(11):e0207314](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0207314) — fractional-bandwidth usage.
- [Front. Phys. 10:893791 (2022)](https://www.frontiersin.org/journals/physics/articles/10.3389/fphy.2022.893791/full) — review; Yes/No polarisation and angle tabulation.

**Standards and measurement**
- Z. Chen, V. Rodriguez, L. Foged, *Progress on the Development of IEEE Std 1128 — Recommended Practice on Absorber Evaluation*, [NSI-MI technical paper (2023)](https://www.nsi-mi.com/-/media/project/oneweb/oneweb/nsi/files/technical-papers/2023/progress-on-the-development-of-the-isss-std-1128.pdf) — scope, non-mandatory status, revision to 40 GHz, NRL arch.
- IEEE Std 1128-1998, *Recommended Practice for RF Absorber Evaluation in the Range of 30 MHz to 5 GHz* — **cited, not read** (§13).

**Consulted for the RAM/MXene tradition** (EAB, `RL_min`, matching thickness): [PMC7481728](https://pmc.ncbi.nlm.nih.gov/articles/PMC7481728/), [PMC10608534](https://pmc.ncbi.nlm.nih.gov/articles/PMC10608534/), [PMC11935905](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11935905/), [R. Soc. Open Sci. 7:200456](https://royalsocietypublishing.org/doi/10.1098/rsos.200456).
