# Costa's thin-spacer capacitance correction (eq 10), recovered

**Date:** 2026-09-08
**Ticket:** [#190](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/190) — surfaced by the [#128](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/128) prototype ([PR #186](https://github.com/parthalon025/Principle_RF_Engineer_Agent/pull/186)); model adopted by [#111](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/111); part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104).
**Question:** What is equation (10) of Costa, Genovesi, Monorchio & Manara, and how big is the bias the fast tier has been carrying by omitting it?

---

## Bottom line up front

**The equation is recovered, and the bias at #128's design point is smaller
than the caveat implied — between −1.1% and −3.0% in resonant frequency.**

```
                     2 D ε₀        (        −4πd/D )
    C₀^thin  =  C₀ − ────── · ln   ( 1 − e         )
                        π          (               )
```

At #128's cell (period 6.0 mm, spacer 1.50 mm, d/p = 0.25) the correction
raises the grid capacitance by **+2.2%**, which drags the resonance down by
**about 0.11 GHz from 10 GHz**.

> **CORRECTED twice — read §10 for the current answer.** This paragraph
> originally continued *"Under a competing published form of the same equation
> — see §3, this is the one genuine unresolved point — it is +6.3% and
> 0.30 GHz."* Both figures were retracted on 2026-09-08 by §7's correction note
> (the composition double-counted the permittivity; the competing form is
> **+3.2%** and **0.157 GHz**, not +6.3% and 0.30 GHz), and the "unresolved"
> framing was retired on 2026-09-13 by **§10**, which settles the prefactor as
> **`ε₀ε_r`** — so the `+3.2%` / `−1.57%` / `9.843 GHz` row is now *the*
> answer, not the upper end of a bracket.

*In plain terms: the model has been drawing the cell's resonance about one to
three percent too high. To land back on 10 GHz the gap between the metal
plates has to open by 28–85 µm, roughly the width of a human hair. The
programme's conclusions from #186 survive this; the direction was already
flagged correctly, and the size turns out to be a trim, not a redesign.*

**Four things this settles** (the fourth was open until 2026-09-13):

| | Answer |
|---|---|
| The equation | Recovered verbatim, §1 |
| Period or wavelength? | **Cell period**, unambiguously. §4 |
| Does the inductance need correcting too? | **No formula for it has ever been published.** The claim is repeated in three Costa papers and never once accompanied by an equation. §5 |
| Which permittivity is in the prefactor — ε₀ or ε₀ε_r? | **`ε₀ε_r`**, added to the already-`ε_eff`-loaded capacitance — the Costa & Borgese 2021 form. Settled by deriving eq (10) from the Floquet/image problem, corroborated by the 2013 paper's own Figure 2(b). **§10** (§3 stated this as unresolved and is superseded) |

---

## 1. Equation (10), verbatim

From Costa, Genovesi, Monorchio & Manara, *"A Circuit-based Model for the
Interpretation of Perfect Metamaterial Absorbers"*, accepted-for-publication
preprint, [arXiv:1211.1902](https://arxiv.org/abs/1211.1902), page 3
(PDF page 4), section IV. Published as *IEEE Trans. Antennas Propag.* **61**(3),
pp. 1201–1209, 2012, doi [10.1109/TAP.2012.2227923](https://doi.org/10.1109/TAP.2012.2227923).

The sentence that introduces it, quoted exactly:

> "The calculation of the unloaded capacitance can be accomplished by
> retrieving the reflection coefficient of a full-wave simulation [37].
> Alternatively, in case of a patch FSS, it can be calculated through the
> closed-form expression available in [35]. As the substrate thickness is
> reduced (which is the case of thin metamaterial absorbers) the influence of
> higher-order (evanescent) Floquet modes reflected by the ground plane must be
> taken into account by adequately correcting the capacitance and the
> inductance values. In particular, the value of the capacitor increases
> exponentially as the spacer thickness is reduced below 0.3 D [35], [37]. The
> influence of the evanescent modes can be taken into account by the following
> substitution [35]:"

And the equation itself:

```latex
C_0^{thin} \;=\; C_0 \;-\; \frac{2 D \varepsilon_0}{\pi}\,
                 \log\!\left( 1 - e^{-\frac{4\pi d}{D}} \right)
```

followed, verbatim, by:

> "where d represents the thickness of the dielectric substrate."

### Every symbol

| Symbol | Meaning | Source of the definition |
|---|---|---|
| `C₀^thin` | The corrected **unloaded** (free-space) grid capacitance, per unit area, F/m². Superscript *thin* = the thin-spacer case | Costa eq (10) |
| `C₀` | The uncorrected unloaded grid capacitance — what the standard closed form gives. §2 | Costa eq (5), (6) |
| `D` | **Cell periodicity** — the repeat distance of the FSS lattice. Costa: *"D, which represents the repetition period"*, p. 3 | Costa, p. 3, verbatim |
| `d` | Thickness of the dielectric substrate — the spacer between the printed pattern and the ground plane | Costa, immediately after eq (10), verbatim |
| `ε₀` | Permittivity of free space, 8.8541878128×10⁻¹² F/m | standard |
| `log` | **Natural** logarithm. Not base 10 — established numerically in §2 | derived, §2 |

**Sign and direction.** For any finite `d`, the quantity `e^(−4πd/D)` is
between 0 and 1, so `1 − e^(−4πd/D)` is less than 1 and its logarithm is
**negative**. Subtracting a negative number **adds**. So `C₀^thin > C₀`
always, and the gap widens as `d` shrinks — matching Costa's own prose
("the value of the capacitor increases exponentially"). As `d → ∞` the
exponential vanishes, `ln(1) = 0`, and the correction disappears, as it must.

*In plain terms: the closer the pattern sits to the metal behind it, the more
extra capacitance appears between the two — and that extra capacitance is what
this term adds back in. Push the spacer to zero and the term blows up to
infinity, which is the honest answer: at zero spacing the pattern is shorted
to the mirror.*

### Provenance of this transcription

**Reading maths off a rasterised page is `INFERRED`, and one render read once
would deserve no better.** This transcription earns more than that only because
**four independent routes were run and all four agree**. The distinction
matters: everything downstream in §7 inherits this equation's correctness, so
the grounds are set out rather than asserted.

1. **The PDF's own text layer** (`pymupdf`). Extracted every token of eq (10) —
   scrambled in reading order, but complete and **machine-readable, not OCR**:
   `4 0 0 0 2 log 1 d thin D D C C e π ε π −`. Every symbol in the
   transcription above appears there, and no symbol appears there that is not
   in the transcription. This is what the ticket's "did not survive text
   extraction" actually was: the tokens survive, their *layout* does not.
   Because these are font-encoded characters rather than recognised pixels,
   this route cannot make a shape-confusion error such as `ε₀` for `ε_r`.
2. **A 22× render via `pymupdf`, eye-read.** Unambiguous at that
   magnification: the numerator is `2Dε₀`, subscript zero, no `ε_r`; the
   exponent is `−4πd/D`.
3. **A 600 dpi render via `pdftoppm` (poppler)** — a completely separate
   rasterisation codebase from pymupdf's, so a renderer bug cannot be common to
   both. Character for character identical to route 2.
4. **An independent published restatement** of the same equation attributed to
   this same paper — Costa & Borgese 2021, §3 — which is plain extractable text
   and carries the identical functional form.

A fifth, quantitative check is in §6: the paper's own Figure 2(b) data points
fit this functional form to **R² = 0.99902**.

**Tagging.** The **functional form** — `C₀ − (2D·ε/π)·ln(1 − e^(−4πd/D))` — is
`LITERATURE-SUPPORTED`: it is corroborated by a machine-readable text layer, two
independent renderers, a separate publication, and a numerical fit to the
source's own figure. The **prefactor's permittivity** (`ε₀` vs `ε₀ε_r`) is
**unresolved between two published sources** and is carried as a bounded
uncertainty throughout — §3. Figure 2(b)'s digitised slope in §6 is `INFERRED`
and is recorded but not relied on.

**What would upgrade this further** is the published IEEE version or the
original in ref [35]. Neither is reachable — §8 records the evidence that
ref [35] has no free copy in existence, not merely that we could not fetch it.

---

## 2. `C₀` itself, and why `log` is the natural logarithm

Costa does not restate the closed form for `C₀`; he points to his ref [35].
The form actually in use throughout this literature — and already implemented
in this repo's bench at `geometry/prototype_lossy_cell_fit.html:685` — is the
Luukkonen/Tretyakov patch-grid capacitance:

```
    C₀ = ε₀ · (2D/π) · ln[ 1 / sin( π g / (2D) ) ]
```

where `g` is the **gap** between adjacent patches. Luukkonen et al.
([arXiv:0705.3548](https://arxiv.org/abs/0705.3548), eq (4)) state the grid
parameter as `α = (k_eff D/π) ln[1/sin(πw/2D)]` and refer to it in the
following sentence as *"the natural logarithm in relation (4)"* — verbatim.

**Numerical confirmation that Costa's `log` is `ln`.** Costa & Monorchio's
ACES overview (§8, route 2) prints a table of "averaged" capacitances for a
patch array at `D = 10 mm`. Recomputing them: `CALCULATED`

| Patch width | ACES Table 2 "C₀ Averaged" | Recomputed with `ln` | Recomputed with `log₁₀` |
|---|---|---|---|
| w = 12/16 D | 54.12 fF | **54.14 fF** | 23.51 fF |
| w = 14/16 D | 90.28 fF | 92.12 fF | 40.01 fF |
| w = 15/16 D | 130.9 fF | **130.92 fF** | 56.86 fF |

Two of three rows reproduce to four significant figures with the natural
logarithm; base 10 is wrong by a factor of 2.303 throughout. The middle row is
2% out, which is a rounding or typesetting discrepancy in the source table, not
a change of log base. **`log` means `ln`.**

---

## 3. The unresolved point: ε₀ or ε₀ε_r?

> **SUPERSEDED 2026-09-13 by §10 — this section is kept as the record of the
> question, not of the answer.** The prefactor is **`ε₀ε_r`**, added to the
> already-`ε_eff`-loaded capacitance. Everything below is still accurate as a
> statement of the two published forms and of the physical argument between
> them; only the closing verdict ("Resolving it needs the original") is
> retracted. §10 resolves it without the original, by deriving eq (10).

The same equation, attributed to the same paper, is published by the same lead
author with an extra factor of `ε_r`.

Costa & Borgese, *"Electromagnetic Model of Reflective Intelligent Surfaces"*,
*IEEE Open Journal of the Communications Society* **2**, pp. 1577–1589, 2021,
doi [10.1109/OJCOMS.2021.3092217](https://doi.org/10.1109/OJCOMS.2021.3092217),
preprint [arXiv:2102.10666](https://arxiv.org/abs/2102.10666), their eqs (9)
and (10), verbatim:

> "The aforementioned averaged expressions of the capacitance refer to cases in
> which the dielectric thickness is sufficiently thick so that high-order
> Floquet harmonics can be neglected [45]. In order to take into account the
> effect of higher-order Floquet harmonics the capacitance of the periodic
> surface can be corrected as [45]:
>
> `C^{TE/TM}_patch = C^{TE/TM}_patch − C_patch−ground`   (9)
>
> where `C_patch−ground` is a correction terms which takes into account the
> capacitance between the patch and the ground plane:
>
> `C_patch−ground = (2 D ε₀ ε_r / π) ln(1 − e^{−4πd/D})`   (10)
>
> when `Dx = Dy = D`."

Their **[45] is our paper** — "F. Costa, S. Genovesi, A. Monorchio, and
G. Manara, 'A circuit-based model for the interpretation of perfect
metamaterial absorbers,' IEEE Transactions on Antennas and Propagation,
vol. 61, no. 3, pp. 1201–1209, 2012." So this is a restatement of eq (10),
not a different result — but it carries `ε₀ε_r` where the 2013 paper carries
`ε₀` alone.

**Which is right is not settled by anything retrievable.** Arguments both ways:

- **For `ε₀` (the 2013 form).** Eq (10) corrects the *unloaded* capacitance —
  the vacuum quantity, before Costa's eq (6) multiplies by the effective
  permittivity `(εr′+1)/2`. A vacuum quantity taking a vacuum permittivity is
  internally consistent, and the correction inherits `ε_r` afterwards through
  eq (6).
- **For `ε₀ε_r` (the 2021 form).** Costa & Borgese name the term
  *"the capacitance between the patch and the ground plane"*. The medium
  physically between patch and ground plane **is** the substrate, so that
  capacitance ought to carry `ε_r`. Their eqs (7)–(8) also apply the correction
  to an already-loaded capacitance, so no later `ε_r` arrives.

**Figure 2(b) leans toward the 2021 form but does not settle it.** §6.

**Consequence for this repo:** carry both. The recomputation in §7 reports
both, and they bracket the answer. The `ε₀` form is the conservative floor and
the `ε₀ε_r` form the ceiling; the true bias is one of the two, not between them.
**The bracket is narrower than first reported** — the forms differ by
`ε_r/ε_eff` = 1.487, not by `ε_r`, because the 2021 correction bypasses the
`ε_eff` loading rather than compounding with it (see §7's correction note).
That also strengthens the physical argument above: a patch-to-ground
capacitance whose field lies wholly inside the substrate *should* carry `ε_r`
where the air-straddling gap capacitance carries `ε_eff`, and the two entering
at different points is exactly what that asymmetry predicts.
Resolving it needs the original — §5, §8.

---

## 4. Cell period, not wavelength — settled

The threshold is stated against the **cell periodicity**, three times, and
never against wavelength. Verbatim, all from arXiv:1211.1902:

> "If the hypothesis of a sufficiently thick substrate is verified (thicker
> than 0.3 D, where **D is FSS periodicity** [35], the effective permittivity,
> ε_reff , simply corresponds to the average between the relative permittivity
> of the substrate … and the relative permittivity of free space"
> — p. 2, introducing eq (6)

Costa's eq (6) then carries the condition **inside the equation itself**:

```
    C = C₀ [ (ε_r′ + ε_r″)/2 + 1/2 ]     if  d > 0.3 D
```

> "It is evident that a reduction of the substrate thickness below 0.3 D
> determines an exponential growth of the lumped capacitor which is physically
> ascribed to the capacitance formed from the metallic array and the ground
> plane. This capacitance is negligible with respect to the capacitance formed
> between adjacent patches **if the substrate is thicker than 0.3 D**."
> — p. 3

And `D` is defined on the same page, verbatim: *"where D, which represents the
repetition period, is equal to 20 µm."*

The secondary reading in the ticket is therefore correct, and the units are
unambiguous. **The ratio that matters is `d/D` — spacer thickness over cell
period — and it is dimensionless.** Wavelength does not enter the correction
at all; eq (10) has no frequency in it.

*In plain terms: the question is not "is the spacer thin compared to the radio
wave" but "is the spacer thin compared to how far apart the printed shapes
are". Those are very different tests, and this programme's cells pass the first
and fail the second.*

**A second, stricter limit from the same author.** Costa & Monorchio's ACES
overview states the threshold differently, verbatim:

> "The effect of substrates is generally taken into account by multiplying the
> FSS capacitance through the averaged permittivity of the dielectrics
> enclosing the FSS [51]. This approximation is acceptable only for thick
> dielectric substrates (**thicker than an half of the cell periodicity**) or
> when the FSS periodicity is much lower than the operating wavelength [58],
> [59]."

That is `d > 0.5 D`, stricter than the `0.3 D` of the 2013 paper. Both are
against the **cell periodicity**. #128's cell at `d/D = 0.25` is inside both.

---

## 5. The inductance: asserted three times, never published

**Finding: no inductance correction has ever been printed in any accessible
source, by Costa or anyone else in this chain.** The claim that one is needed
is boilerplate carried verbatim across three papers, each time immediately
followed by a capacitance formula only.

| Paper | The claim | What follows it |
|---|---|---|
| Costa et al. 2013, arXiv:1211.1902, p. 3 | *"…correcting the capacitance and the inductance values"* | eq (10). **Capacitance only.** |
| Costa & Monorchio, *Advanced Electromagnetics* **1**(3), 2012, [open access](https://www.aemjournal.org/index.php/AEM/article/view/22) | *"…correcting the capacitance and the inductance values [25], [26]"* | **No formula at all.** |
| Costa & Borgese 2021, arXiv:2102.10666, eqs (9)–(10) | Reframed as *"the capacitance between the patch and the ground plane"* — the inductance is **not mentioned** | eq (10). **Capacitance only.** |

A full-text search of arXiv:1211.1902 for every occurrence of "induct" returns
six hits; none is a correction formula. The word appears in: the grounded slab
behaving "as an inductor" (§III), the FSS being "inductive after" resonance
(§IV), the sentence above, and three passages in the discussion about element
shape.

**Why there is probably nothing to correct, for this programme's cells.** Costa
models a patch array as a **pure capacitor**, verbatim from eq (5)'s
introduction:

> "The impedance can be represented through a series LC circuit or more simply
> by a single capacitor if the inductive component is low (e. g. patch
> element)"

For a patch FSS the grid inductance is taken as zero, so there is no grid
inductance to correct. The inductance in the absorber circuit is the grounded
slab, `Z_d = (ζ₀/√ε_r) tan(k₀ d √ε_r)` (Costa eq (2)), which is an **exact**
transmission-line result, not an approximation with a thin-substrate limit.

*In plain terms: for the patch-and-mirror stack this programme is building,
there is no inductance term in the model to correct in the first place. The
sentence is written for the general case — loops, crosses, and other shapes
that do have real inductance — and for those the correction was apparently
never written down.*

**Where it would be, if it exists.** Costa attributes eq (10) to his ref [35]:

> "[35] S. A. Tretyakov and C. R. Simovski, 'Dynamic model of artificial
> reactive impedance surfaces,' J. of Electromagn. Waves and Appl., vol. 17,
> no. 1, pp. 131–145, 2003."

**That paper is closed access with no repository copy anywhere.** Unpaywall
(queried 2026-09-08, DOI `10.1163/156939303766975407`) returns
`"is_oa": false`, `"oa_status": "closed"`, `"has_repository_copy": false`,
`"oa_locations": []`, and `"best_oa_location": null`. Semantic Scholar returns
`"status": "CLOSED"` with an empty PDF URL. This is not "we failed to fetch
it" — it is a positive result from two independent open-access indexes that no
free copy exists. **It goes to `RUNNING-LISTS.md` §1.**

---

## 6. Figure 2(b) validates the functional form

> **PARTLY SUPERSEDED 2026-09-13 by §10.3.** This section's fit is sound and
> was independently reproduced, but its conclusion — that the unknown `C₀`
> normalisation stops the figure settling the prefactor — is wrong: that
> unknown **cancels** in the ratio of slope to plateau. Read that way the
> figure does discriminate, and it points at `ε_r`. §10.3 also corrects this
> section's statement of the figure's geometry.

The paper's Figure 2(b) plots `C^thin/C₀` against `d/D` from 0 to 0.5, for a
gold patch array with `D = 20 µm`, `L = 15 µm` on Mylar (`ε_r = 2.89`),
comparing "Averaged — according to (10)" markers against a MoM full-wave
solve. Digitising the markers by pixel analysis of a 6× render: `INFERRED`
(read off a drawing)

Fitting the nine uncontaminated markers to `v = a + b·L` where
`L = −ln(1 − e^(−4πd/D))`:

```
    v  =  1.7173  +  2.4661 · L          R² = 0.99902
```

**An R² of 0.99902 against exactly the functional form of eq (10) confirms the
transcription** — the exponent `4πd/D` and the logarithm are right, and the
markers are that function and nothing else.

The fitted slope is less conclusive about the prefactor. Normalised by the
analytic `C₀`, the slope implies a prefactor multiplier of **2.369**, against
1.945 for `ε_eff = (1+ε_r)/2` and 2.890 for `ε_r`. It sits between them,
nearer `ε_r`. The plateau `a = 1.7173` is below `ε_eff = 1.945`, which means
the figure's `C₀` normalisation is not the analytic free-standing value —
likely a MoM-retrieved capacitance, which the ACES table shows runs 10–19%
below the analytic one. With that unknown in the loop the figure **leans**
toward the `ε₀ε_r` form of §3 but cannot settle it. Recorded, not relied on.

---

## 7. The recomputation at #128's design point

**The design point**, from PR #186 and `geometry/PROTOTYPE-lossy-cell-fit.md`:

| Parameter | Value | Source |
|---|---|---|
| Cell period `p` (= Costa's `D`) | 6.0 mm | PR #186 |
| Gap between plates `g` | 0.498 mm | PR #186 |
| Spacer thickness `d` | 1.50 mm | PR #186 |
| Spacer | Silicone 60 ShA, `ε_r = 2.9`, `tanδ = 0.10` | `PROTOTYPE-lossy-cell-fit.md:72` |
| Target frequency | 10 GHz | PR #186 |
| **`d/p`** | **0.25** | — |

At `d/p = 0.25` the exponent is exactly `−4π(0.25) = −π`, a pleasant
coincidence that makes the arithmetic checkable by hand: `CALCULATED`

```
    e^(−π)                    =  0.0432139
    L = −ln(1 − 0.0432139)    =  0.0441753
    C₀ = ε₀(2p/π)ln[1/sin(πg/2p)]  =  69.00 fF
```

### The capacitance bias

> **CORRECTED 2026-09-08.** The `ε₀ε_r` row below previously read **+6.28%**,
> and every figure derived from it (a `−3.01%` frequency shift, a `+85 µm` gap,
> and the claim that the 2021 form **"triples"** the bias) was wrong. The error
> was **not** in the transcription — it was in the composition, and §3 of this
> very document already had it right: *"Their eqs (7)–(8) also apply the
> correction to an already-loaded capacitance, so no later `ε_r` arrives."*
> §7 then divided the 2021 correction by the **unloaded** `C₀` anyway, which
> double-counts the permittivity. Settled from the 2021 paper's **LaTeX
> source** (arXiv:2102.10666, `paper_arxiv_v2.tex`) — its `C_patch` already
> carries `ε_eff`, and `eq_C_refined` subtracts the correction from *that*.
> **The two published forms differ by `ε_r/ε_eff` = 1.487 at `ε_r` = 2.9, not
> by `ε_r` = 2.9.** `LITERATURE-SUPPORTED` (read from the authors' own source).

Two reference capacitances matter, and the earlier error came from mixing them:
`C₀` **unloaded** = 69.00 fF, and `C₀ · ε_eff` **loaded** = 134.55 fF at
`ε_eff` = 1.95. The 2013 correction enters *before* the `ε_eff` loading; the
2021 correction enters *after* it.

| Form of eq (10) | Enters | `ΔC` on the loaded capacitance | As % of loaded `C₀·ε_eff` |
|---|---|---|---|
| **2013, `2Dε₀/π`** | before `ε_eff` loading | +2.913 fF (= `ε_eff·δ`) | **+2.17%** |
| **2021, `2Dε₀ε_r/π`** | after `ε_eff` loading | +4.333 fF (= `ε_r·δ`) | **+3.22%** |

where `δ = (2pε₀/π)·[−ln(1−e^(−4πd/p))]` = **1.4940 fF** is the base term,
independent of `ε_r`. The 2013 row's percentage is unchanged from the original
table because numerator and denominator both scale by `ε_eff`.

### The frequency bias

Solving Costa's own resonance condition — his §V, `X = −B`, the FSS reactance
cancelling the grounded slab's — anchored so the **uncorrected** model sits at
exactly 10.000 GHz, then applying the correction at that same geometry:
`CALCULATED`

| Form of eq (10) | Resonance | Shift | Gap needed to hold 10 GHz |
|---|---|---|---|
| uncorrected | 10.000 GHz | — | 0.6158 mm |
| **2013, `ε₀`** | **9.893 GHz** | **−0.107 GHz (−1.07%)** | 0.6439 mm (**+28 µm**, +4.6%) |
| **2021, `ε₀ε_r`** | **9.843 GHz** | **−0.157 GHz (−1.57%)** | ≈ 0.658 mm (**≈ +42 µm**) |

The 2021 gap figure is a **first-order scaling** from the 2013 row
(`42 ≈ 28 × 3.22/2.17`), not an independent solve — flagged rather than
presented as exact, since the exact value comes out of the implementation
(#245). The conclusion it feeds is unaffected: the correction still widens the
gap, still moves *away* from the 0.2 mm feature floor, and still does not
rescue the 4 mm cell.

Cross-check against the rule of thumb `Δf/f ≈ −½·ΔC/C`: predicts −1.08% and
−1.61%. The solved values are slightly smaller because the slab's reactance
`tan(k₀d√ε_r)` rises faster than a pure inductor's, which stiffens the
resonance. The two agree to within a quarter of a percentage point, so neither
is a blunder.

### What this means for #186's conclusions

**They stand.** Specifically:

- **The bias is a trim, not a redesign.** #186's UI flagged the direction
  correctly and the magnitude is 1–3% in frequency. Nothing in that document's
  five findings turns on 1–3%.
- **The correction makes the gap *wider*, which moves *away* from the printer's
  0.2 mm feature floor.** #186's tightest margin is the 0.245 mm carbon bridge,
  which this does not touch; the gap goes from 0.498 mm to roughly 0.53–0.57 mm
  at the drawn geometry. The floor risk gets slightly better, not worse.
- **It does not rescue the 4 mm cell.** #186 found that at `p = 4.0 mm` the gap
  the physics wants is 0.120 mm, below the floor. At `p = 4.0, d = 1.50` the
  ratio is `d/p = 0.375` — **outside** eq (10)'s regime — so the correction is
  tiny: the required gap moves from 0.1639 mm to 0.1654 mm (`ε₀`) or ≈0.1661 mm
  (`ε₀ε_r`). Still below 0.2 mm. *(The `ε₀ε_r` figure read 0.1682 mm until
  2026-09-08: it carried the superseded ×`ε_r` scaling that §7's correction
  note retracts. ×`ε_r/ε_eff` gives 0.1661 mm. The conclusion is unchanged —
  both are below the floor — which is exactly why the stale number survived
  the first pass over this document.)* **#186's "the feature floor sets a minimum
  cell size, and hence a minimum spacer thickness" finding survives intact.**
  `CALCULATED`

### Implementing it

The bench's `gridC` at `geometry/prototype_lossy_cell_fit.html:682-687`
computes `A = ε₀(2p/π)ln(1/sin(πg/2p))` and then applies Costa's eq (6). The
correction inserts between those two steps — add `−(2pε₀/π)·ln(1−e^(−4πd/p))`
to `A` before the eq (6) loading. It needs `d`, which `gridC` does not
currently take as an argument.

---

## 8. Every route tried

**Succeeded:**

| Route | Result |
|---|---|
| `pymupdf` text layer of arXiv:1211.1902 | **All eq (10) tokens present**, scrambled in order. The ticket's premise that extraction failed is half right — layout was lost, tokens were not |
| 9× and 22× raster render (`pymupdf`) + visual read | **Decisive.** `2Dε₀`, no `ε_r`; exponent `−4πd/D` |
| 600 dpi render (`pdftoppm`, poppler) + visual read | **Independent confirmation** — different rasteriser, identical result |
| arXiv:2102.10666 (Costa & Borgese 2021) | **Independent restatement** of eq (10) in clean text, attributed to this paper — but with `ε₀ε_r` |
| ACES overview PDF, direct download | Confirms the `0.5 D` threshold and supplies Table 2, which pins `log = ln` |
| arXiv:0705.3548 (Luukkonen et al. 2008) | Confirms `C₀`'s closed form and states "the natural logarithm" |
| AEM 1(3) 2012 (Costa & Monorchio), open access | Third instance of the "capacitance and inductance" claim, with no formula |
| Figure 2(b) pixel digitisation | R² = 0.99902 fit to eq (10)'s functional form |

**Failed, and why:**

| Route | Outcome |
|---|---|
| **arXiv e-print tarball**, `https://arxiv.org/e-print/1211.1902` | **Does not exist.** HTTP 200, but `content_type: application/pdf`, 892,550 bytes, `file` reports "PDF document, version 1.5, 10 page(s)". The authors submitted camera-ready PDF, **not LaTeX**. This is a claim about the world, not about our fetching |
| **ar5iv HTML render** | Follows from the above — ar5iv renders from LaTeX source, and there is none to render. **Not worth re-trying.** The same fact explains the subset-font extraction problem: the PDF came from the authors' own toolchain with no machine-readable maths behind it |
| **Tretyakov & Simovski 2003** (ref [35], the original statement) | **Closed access, no free copy exists.** Unpaywall: `is_oa: false`, `has_repository_copy: false`, `oa_locations: []`. Semantic Scholar: `status: CLOSED`. Two independent indexes agree. → `RUNNING-LISTS.md` §1 |
| **Costa, Monorchio & Manara, IEEE APM 54(4) 2012** (the ticket's most-likely-home candidate, ACES ref [58]) | DOI `10.1109/MAP.2012.6309153`. Unpaywall reports not open access, no OA locations. Behind IEEE. **Note: this was probably never the right target anyway** — the 2013 paper attributes eq (10) to [35] (Tretyakov & Simovski), not to the APM paper. The APM paper is the source of a *different*, later interpolating formula (ACES eq (5), an effective-permittivity fit in `x = 10 d/D`), which is an alternative to eq (10), not a restatement of it |
| **IEEE Xplore published version** | Not attempted for full text — the preprint proved sufficient, and Xplore is recorded as HTTP 418 in `RUNNING-LISTS.md` §1 |
| **`pdftotext` / poppler** | Not installed at the start of the session; `pymupdf` installed cleanly via `pip` and did the job. Poppler was installed mid-session and used afterwards as the independent cross-check above. `pdftotext -layout` still does **not** recover eq (10) — the subset font defeats it where `pymupdf`'s token extraction succeeds, so **`pymupdf` is the better tool for this class of PDF** and is worth reaching for first |

---

## 9. Register updates

**Opens, for `RUNNING-LISTS.md` §1:**

> **Tretyakov & Simovski (2003)**, "Dynamic model of artificial reactive
> impedance surfaces," *J. Electromagn. Waves Appl.* **17**(1), pp. 131–145 —
> Closed access, **confirmed by Unpaywall and Semantic Scholar that no
> repository copy exists anywhere**. It is the original statement of Costa's
> eq (10) and the only place an **inductance** correction could be found if one
> was ever written. Also the only way to settle whether eq (10)'s prefactor is
> `ε₀` or `ε₀ε_r` — a factor of `ε_r` on the size of the bias the fast tier
> carries. Bears on #190, #128, #111.

**Closes:** #190's three questions, with the `ε₀`/`ε₀ε_r` ambiguity carried
forward as a bounded uncertainty rather than an unknown.

**Note for `docs/BUILD_PLAN.md` / whoever implements the fast tier:** the
correction is three lines of arithmetic and needs the spacer thickness plumbed
into the grid-capacitance function. The `ε₀` form is the conservative choice
until the original is read.

---

## 10. Resolution of §3 (2026-09-13) — the prefactor is `ε₀ε_r`

**Ticket:** [#234](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/234).
This section closes the one question §3 left open. It **supersedes §3's verdict
of "unresolved"** and **§6's verdict of "leans but cannot settle"**. Nothing
else in this document changes; §1–§9 stand as written except where flagged
below.

> **SUPERSEDES §3.** §3 said *"Which is right is not settled by anything
> retrievable"* and carried both forms as a bracket. That is no longer the
> position. Route 2 — the dimensional/physical analysis the ticket flagged as
> cheap and mandatory — turns out not to be a tie-breaker between two
> plausible readings but a **derivation of eq (10) from scratch**, and the
> derivation hands back the prefactor. §3's own physical argument for the 2021
> form was right, and it is now backed by the calculation rather than by
> intuition.

### 10.1 Bottom line

**Costa eq (10) carries `ε₀ε_r`, and the correction is added to the
already-`ε_eff`-loaded capacitance — the Costa & Borgese 2021 form, exactly as
that paper states it.** The `ε₀` printed in the 2013 paper is an incomplete
statement of the same result; the 2013 paper's **own Figure 2(b) was plotted
with `ε_r`**, not with the `ε₀` its text prints.

Three independent lines agree, and none of them is the one route that stayed
shut (the closed-access original):

| Line of evidence | What it says | Tag |
|---|---|---|
| **Derivation from the Floquet/image boundary-value problem** (§10.2) | Reproduces eq (10) *exactly* — the `2D/π`, the `1/n` series, the `4π` in the exponent — and the prefactor that falls out is `ε₀ε_r` | `CALCULATED` |
| **Costa 2013's own Figure 2(b), re-digitised and read normalisation-free** (§10.3) | Implies a prefactor multiplier of **2.72**, against `ε_r` = 2.89 (−5.7%) and `ε_eff` = 1.945 (+40.1%) | `INFERRED` |
| **Costa & Borgese 2021 LaTeX source** (§10.4) | `\frac{2D \varepsilon_0\varepsilon_{r}}{\pi}` verbatim, three lines after the same authors write `\varepsilon_0\varepsilon_{eff}` for the gap capacitance — a deliberate distinction, not a slip | `LITERATURE-SUPPORTED` |

*In plain terms: we worked out the physics from first principles instead of
trying to read the unreadable original, and the answer came out matching the
newer of the two papers. Then we went back to the older paper's own graph and
found the graph agrees with the newer paper too — the old paper's picture and
its printed formula disagree with each other, and the picture is the one that
matches the physics.*

**Effect on the fast tier.** The bias at #128's design point is the **larger**
of the two figures this document has been carrying: `+3.22%` on the loaded
capacitance, a resonance shift of about **−1.57%** (9.843 GHz against a drawn
10.000 GHz), and a gap that must open by roughly **+42 µm** rather than
+28 µm to hold 10 GHz. §7's table is unchanged — the 2021 row is now the
answer rather than the ceiling of a bracket.

### 10.2 Route 2, done as a derivation

The ticket asked whether the correction enters before or after eq (6)'s
`ε_eff = (ε_r+1)/2` loading, and whether applying `ε_r` would double-count.
Working it through does not just answer that — it produces eq (10).

**Step 1 — what permittivity one Floquet harmonic sees.** Take the grid's
surface charge as a Fourier series over the lattice, harmonic `n` having
transverse wavenumber `k_n = 2πn/D`. Solve the quasi-static problem for one
harmonic: air (`ε₀`) filling `z > 0`, substrate (`ε₀ε_r`) filling `z < 0`, and
a PEC ground at `z = −d`. The potential below must vanish at the ground, so it
is `∝ sinh(k_n(z+d))/sinh(k_n d)`. Matching `D_z` across the sheet gives

```
    σ_n = k_n φ_n [ ε₀ + ε₀ ε_r coth(k_n d) ]
```

Normalise to `f_n = [1 + ε_r coth(k_n d)] / 2`. With the ground taken away
(`d → ∞`, `coth → 1`) this is `f_n = (1+ε_r)/2 = ε_eff` for **every** harmonic
— which is exactly *why* the substrate loading is a single multiplicative
factor in eq (6), and confirms the formalism is the right one before it is
used for anything new. `CALCULATED`

**Step 2 — the ground plane's increment is pure substrate.** Subtract the
no-ground case:

```
    f_n − ε_eff  =  ε_r · x^n / (1 − x^n),        x = e^(−4πd/D)
```

verified to 10 decimal places against the boundary-value expression at
`d/D` = 0.05, 0.25 and 0.5. **The `1` — the air half-space — does not appear.**
The ground plane sits inside the lower medium, so putting it there changes only
the lower medium's response, and that response carries `ε_r` alone. This is the
whole answer to the ticket's double-counting worry: there is no double count,
because the increment is not a re-loading of the original capacitance, it is a
separate additive term with its own permittivity.

*In plain terms: the printed pattern's near field splits half into the air above
and half into the rubber below — that is where the `(ε_r+1)/2` average comes
from. Putting metal behind the pattern changes nothing about the air half. It
only changes the rubber half, so the extra capacitance it creates is all-rubber
and gets rubber's full number.*

**Step 3 — sum over harmonics and eq (10) appears.** The grid capacitance in
this family of models is a weighted harmonic sum, `C = (2Dε₀/π) Σ_n w_n f_n`.
The weights are fixed by the known closed form: the identity

```
    ln[1 / sin(πg/2D)]  =  ln 2  +  Σ_{n≥1} cos(πng/D) / n
```

was checked numerically (agreement to six decimals at `g/D` = 0.01, 0.083, 0.25
and 0.5), so `w_n = cos(πng/D)/n`. Therefore

```
    ΔC  =  (2Dε₀ε_r/π) · Σ_{n≥1} [cos(πng/D)/n] · x^n/(1 − x^n)
```

Take the narrow-gap limit (`cos → 1`) and keep only the first image
(`x^n/(1−x^n) → x^n`), and since `Σ_{n≥1} x^n/n = −ln(1 − x)`:

```
    ΔC  =  −(2 D ε₀ ε_r / π) · ln(1 − e^(−4πd/D))
```

**That is eq (10), factor for factor** — the `2D/π`, the natural logarithm, and
the `4π` in the exponent (which is just the round trip, `2 × k_1 d`, of the
lowest Floquet harmonic `k_1 = 2π/D`). The prefactor the derivation produces is
`ε₀ε_r`, and the term is additive to the `ε_eff`-loaded capacitance — the 2021
composition point, not the 2013 one. `CALCULATED`

**Why this is stronger than a plausibility argument.** The derivation was not
tuned to land on eq (10); the weights came from an independently-verified
series identity and the permittivity factor from a textbook boundary-value
problem. It then reproduced a published closed form exactly, including two
details it had no way to fit — the `4π` and the `1/n`. A calculation that
recovers the functional form it was not aimed at is entitled to be believed
about the prefactor it produces at the same time. It also explains something
the published equation never states: **why eq (10) has no `g` in it** (it is
the `g → 0` limit of the weights).

**What eq (10)'s two approximations cost**, at #128's `d/p = 0.25` and
`g/p = 0.083` (`S_corr` is the bracketed sum, `ε_r` = 2.9): `CALCULATED`

| | `S_corr` | vs eq (10) |
|---|---|---|
| eq (10) as published (`cos → 1`, first image) | 0.128109 | — |
| all images, `cos → 1` | 0.133774 | +4.4% |
| all images **and** the real gap factor | 0.128962 | **+0.67%** |

The two approximations very nearly cancel: dropping the further images
under-counts by 4.4%, and pretending the gap is infinitesimal over-counts by
about the same. **eq (10) as published is within 0.7% of the full sum at this
programme's design point** — so there is no case for replacing it with the
series. Use it as printed, with `ε₀ε_r`.

### 10.3 Route 4, redone — the figure does settle it

§6 could not use Figure 2(b) because the figure normalises by an unknown `C₀`
("likely a MoM-retrieved capacitance"). **That unknown cancels**, and §6 missed
that it does.

Write `ρ = C₀_figure / C₀_analytic`, whatever it is. The figure plots
`v = C^thin/C₀`, and under either candidate

```
    intercept  a = ε_eff / ρ                (thick-spacer plateau)
    slope      b = m / (ρ · S_g)            m = the disputed multiplier
    ---------------------------------------------------------------
    b / a  =  m / (S_g · ε_eff)             ρ cancels
```

where `S_g = ln[1/sin(πg/2D)]`. So the **ratio of slope to plateau** is immune
to the normalisation, and `m = (b/a) · S_g · ε_eff`.

**Re-digitised independently this session** (900 dpi render of the panel,
`pymupdf`; blue eq-(10) marker pixels separated from the red MoM curve by hue,
legend band excluded, regressed on `L = −ln(1−e^(−4πd/D))`): `INFERRED`

| | intercept `a` | slope `b` | source |
|---|---|---|---|
| §6 (#190) | 1.7173 | 2.4661 | marker centroids |
| this session | **1.7154** | **2.5013** | full pixel cloud |

The two digitisations agree to 0.1% on the plateau and 1.4% on the slope, which
is the main thing worth having: **§6's numbers are independently reproduced.**

With `ε_r` = 2.89 (Mylar — the paper's own value for its `D` = 20 µm,
`L` = 15 µm examples, stated in the Figure 3 caption and the Figure 4 text) and
`g/D` = 0.25, so `S_g` = 0.9605:

| | implied `m` | vs `ε_r` = 2.890 | vs `ε_eff` = 1.945 |
|---|---|---|---|
| this session's digitisation | **2.724** | **−5.7%** | +40.1% |
| §6's digitisation | 2.683 | −7.2% | +37.9% |

**The figure lands within 6% of `ε_r` and 40% away from `ε_eff`.** For the
`ε_eff` reading to be right, the slope-to-plateau ratio would have to be wrong
by 28% — not credible for a fit two independent digitisations agree on to 1.4%.

*In plain terms: the old paper's graph has an unknown scale factor on its
vertical axis, which is what stopped the last attempt. But the graph's flat
part and its steep part are both scaled by that same unknown, so their ratio
does not depend on it. Read that way, the graph says the authors used rubber's
full number when they drew it — even though the formula printed two inches
below the graph does not.*

> **CORRECTION to §6.** §6 states the figure's geometry as *"`D` = 20 µm,
> `L` = 15 µm"*. That is the **caption's** value and it is the right one to use,
> but the paper is **internally inconsistent**: the prose introducing Fig. 2
> says the patches have *"a side length of 14/16 D"*, which is 17.5 µm, not
> 15 µm. This matters — at `g/D` = 0.125 the same test gives `m` = 4.64, which
> matches neither candidate. The caption is preferred because Figure 3's
> caption independently uses the same `D` = 20 µm / `L` = 15 µm patch array on
> Mylar, and because only that reading makes the figure consistent with any
> physical hypothesis at all. Recorded because a reader checking this section
> against the paper will hit the same discrepancy. `LITERATURE-SUPPORTED`

### 10.4 The 2021 source, re-read for intent

The arXiv LaTeX source was pulled again (`arxiv.org/e-print/2102.10666`,
`paper_arxiv_v2.tex`) and read around the equations rather than at them. The
correction, verbatim from line 267:

```latex
C_{patch-ground}= \frac{2D \varepsilon_0\varepsilon_{r}}{\pi} \ln{(1- e^{-4\pi d/D})}
```

`LITERATURE-SUPPORTED`. §3's transcription is confirmed exactly.

**The new observation is what sits fifteen lines above it** (line 252):

```latex
C^{TM}_{patch}= \frac{2D_x\varepsilon_0\varepsilon_{eff}}{\pi}\ln{...}
```

with `\varepsilon_{eff}=(1+\varepsilon_r)/2` defined in the prose between the
two. **The same authors write `ε_eff` for the gap capacitance and `ε_r` for the
patch-to-ground correction, three equations apart, in one subsection, having
just defined the difference between them.** That is not a symbol dropped in
transcription — it is a distinction drawn on purpose, and the prose names the
reason: the term *"takes into account the capacitance between the patch and the
ground plane"*, which is the region that contains no air. The 2021 paper is the
same lead author restating his own earlier equation with the permittivity made
explicit, which is what the derivation in §10.2 says it should be.

No prose in either paper *justifies* the placement physically — that was worth
checking and the answer is no. The justification is §10.2.

### 10.5 Routes that returned nothing (recorded so they are not re-run)

| Route | Outcome |
|---|---|
| **A later Costa restatement, 2021–2026** | **None found.** Searches for a follow-up by Costa or collaborators restating or correcting the prefactor returned no third statement of eq (10). The disagreement was never resolved in print by its authors |
| **Tretyakov & Simovski 2003** (ref [35]) | Unchanged — closed access, no free copy in existence (§5, §8). Still the only thing that would make this `LITERATURE-SUPPORTED` end to end. Stays in `RUNNING-LISTS.md` §1, now as confirmation of a settled answer rather than the only way to settle it |
| **Web-search summarisation of arXiv:2102.10666** | **Returned the wrong prefactor** — a search summariser reported `C_patch-ground = (2D·ε₀/π)·ln(1−e^(−4πd/D))`, silently dropping the `ε_r`. Caught only by pulling the LaTeX. **Do not take an equation from a search summary in this repo**; fetch the source |

### 10.6 What follows for the code — and what has *not* been changed

This section is research. **No code was changed by it**, deliberately; the
implementation is a separate piece of work.

The change, when someone makes it, is the one-line default the ticket
describes — but note the ticket names the wrong file. The implementation lives
in **`rf_tools/sheet_impedance.py`**, not `rf_tools/calculations.py`:

- **`rf_tools/sheet_impedance.py:165`** — `COSTA_EQ10_FORM = "eps0"` should
  become `"eps0_epsr"`. The composition point is already handled correctly:
  `_compose_thin_spacer_capacitance` applies `eps_eff * C0 + dC` for that form,
  which is the 2021 placement §10.2 derives.
- **`rf_tools/absorber.py:342`** — the `thin_spacer_prefactor_disputed`
  validity flag should be removed. Under the charter's "warn, never block", a
  warning must fire only where the assumption is load-bearing *and* uncertain;
  this one is no longer uncertain.
- Tests pinning the old default (`tests/test_sheet_impedance.py:337`,
  `tests/test_absorber.py:124`) move with it.

The `costa_eq10_form` field on every `absorber_band_response` result should
**stay**. It is cheap, and it records which form produced a number — worth
keeping precisely because this document has now revised the answer once.

**Residual uncertainty, stated plainly.** The verdict rests on a derivation
done here plus a figure read off a rasterised page, not on the original source.
`ASSUMED` → `CALCULATED` is a real upgrade but it is not `MEASURED`. Two things
would close it completely, in cost order:

1. **Route 3, a full-wave cross-check** — no longer "unspecified fog": PR #227
   landed a Meep path with Bloch-periodic boundaries. Sweep `d/D` from 0.05 to
   0.5 at one `ε_r`, extract the sheet capacitance, fit the slope against
   `−ln(1−e^(−4πd/D))`. The two candidates differ by 1.487× in that slope,
   far outside solver noise. This would move the finding to `SIMULATED`.
2. **Tretyakov & Simovski 2003**, if a human with library access ever gets it.

Neither blocks the default change. The evidence already points one way by a
wide margin, and continuing to ship the `ε₀` form means knowingly shipping the
number the physics says is wrong by a third.
