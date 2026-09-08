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
**about 0.11 GHz from 10 GHz**. Under a competing published form of the same
equation — see §3, this is the one genuine unresolved point — it is **+6.3%**
and **0.30 GHz**.

*In plain terms: the model has been drawing the cell's resonance about one to
three percent too high. To land back on 10 GHz the gap between the metal
plates has to open by 28–85 µm, roughly the width of a human hair. The
programme's conclusions from #186 survive this; the direction was already
flagged correctly, and the size turns out to be a trim, not a redesign.*

**Three things this settles and one it does not:**

| | Answer |
|---|---|
| The equation | Recovered verbatim, §1 |
| Period or wavelength? | **Cell period**, unambiguously. §4 |
| Does the inductance need correcting too? | **No formula for it has ever been published.** The claim is repeated in three Costa papers and never once accompanied by an equation. §5 |
| Which permittivity is in the prefactor — ε₀ or ε₀ε_r? | **Unresolved.** Two papers by the same lead author disagree. §3 |

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

| Form of eq (10) | Correction `ΔC` | As % of `C₀` |
|---|---|---|
| **2013, `2Dε₀/π`** | +1.494 fF | **+2.17%** |
| **2021, `2Dε₀ε_r/π`** | +4.333 fF | **+6.28%** |

### The frequency bias

Solving Costa's own resonance condition — his §V, `X = −B`, the FSS reactance
cancelling the grounded slab's — anchored so the **uncorrected** model sits at
exactly 10.000 GHz, then applying the correction at that same geometry:
`CALCULATED`

| Form of eq (10) | Resonance | Shift | Gap needed to hold 10 GHz |
|---|---|---|---|
| uncorrected | 10.000 GHz | — | 0.6158 mm |
| **2013, `ε₀`** | **9.893 GHz** | **−0.107 GHz (−1.07%)** | 0.6439 mm (**+28 µm**, +4.6%) |
| **2021, `ε₀ε_r`** | **9.699 GHz** | **−0.301 GHz (−3.01%)** | 0.7009 mm (**+85 µm**, +13.8%) |

Cross-check against the rule of thumb `Δf/f ≈ −½·ΔC/C`: predicts −1.21% and
−3.50%. The solved values are slightly smaller because the slab's reactance
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
  tiny: the required gap moves from 0.1639 mm to 0.1654 mm (`ε₀`) or 0.1682 mm
  (`ε₀ε_r`). Still below 0.2 mm. **#186's "the feature floor sets a minimum
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
