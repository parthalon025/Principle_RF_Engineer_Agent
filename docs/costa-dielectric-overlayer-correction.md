# A dielectric layer of finite height above a printed grid: the closed form exists, and it is general

**Date:** 2026-09-13
**Ticket:** [#446](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/446) — part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104).
Blocks the implementation half of T1 ([#445](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/445)).
Sibling of [`costa-thin-spacer-correction.md`](costa-thin-spacer-correction.md), whose §8 named the
target, and of [`encapsulation-em-coupling.md`](encapsulation-em-coupling.md), whose §3 ansatz and §8
gap this document closes.
**Question:** is there a published closed form for a finite-thickness dielectric layer *above* a
printed grid? If so, is it one-sided (grounded substrate only) or general?

---

## Bottom line up front

**Yes, it is published, it is general, and it is reachable without a library login.** Three
open-access sources carry it. The ticket's target — ACES eq (5) — is real and was read; but the
same author generalised it in 2021, and **that later form is the one to implement.**

```
    ε_eff-right(1)  =  ε_r1  +  ( 1 − ε_r1 ) · e^( −α · d₁ / D )
    ε_eff-left(1)   =  ε_rM  +  ( 1 − ε_rM ) · e^( −α · d_M / D )

    ε_eff           =  [ ε_eff-right(N)  +  ε_eff-left(M) ] / 2
```

Costa, *IEEE Trans. Antennas Propag.* **69**(8), 2021, eqs (12), (13) and (9).
`LITERATURE-SUPPORTED`

**Answer to the ticket's question, stated plainly.** The formula is **general, not one-sided.** It
is written for a metasurface sitting anywhere inside an arbitrary stack of dielectric layers with
free space at both far ends. **No ground plane appears anywhere in its derivation, its figures, or
its verification.** Each side of the grid is walked outward layer by layer and the two sides are
then averaged. A single thin coat on top of an otherwise bare grid is the simplest case it covers,
not an extrapolation from it.

*In plain terms: the printed pattern's capacitance depends on what material is sitting against it,
but a coating only counts to the extent it is thick enough to hold the field that leaks out of the
pattern. This formula says exactly how much of it counts — the coating's permittivity gets weighted
by `1 − e^(−α·thickness/period)`, so a very thin coat behaves almost like air and a coat thicker
than about a third of the cell spacing behaves like an infinite block of the stuff.*

**Four things this settles and one it does not:**

| | Answer |
|---|---|
| Does a published closed form exist? | **Yes.** Three independent open-access statements, §1 |
| One-sided (grounded) or general? | **General.** Arbitrary layers on both sides, no ground plane. §3 |
| What is the decay constant `α`? | **12.5 – 16** across published fits; **13.2** digitised for a patch array. §4 |
| Does the repo's own §3 ansatz survive? | **It is the published formula, exactly.** Its `4π` = 12.566 sits at the bottom of the published range. The "good to about 2×" band collapses to **−1% / +27%**. §5 |
| Can this be combined with Costa eq (10) on a ground-backed cell? | **Not established by any source.** The two describe different boundaries and no publication composes them. §6 |

---

## 1. The formula, and the three places it is published

The result originates in a **closed-access** paper — Costa, Monorchio & Manara, *"Efficient Analysis
of Frequency-Selective Surfaces by a Simple Equivalent-Circuit Model"*, *IEEE Antennas and
Propagation Magazine* **54**(4), pp. 35–48, 2012, doi
[10.1109/MAP.2012.6309153](https://doi.org/10.1109/MAP.2012.6309153). That paper was **not**
obtained (§9 records the evidence that no free copy exists). It did not need to be: **three later
open-access papers restate it**, two of them by the same lead author.

### 1a. The ticket's target — ACES eq (5), recovered

Costa, Monorchio & Manara, *"An Overview of Equivalent Circuit Modeling Techniques of Frequency
Selective Surfaces and Metasurfaces"*, *Applied Computational Electromagnetics Society Journal*
**29**(12), pp. 960–976, December 2014.
**Open access.** Galley PDF:
`https://journals.riverpublishers.com/index.php/ACES/article/download/10793/9015`
(17 pages; the landing page at `.../article/view/10793` exposes no PDF link — the galley id `9015`
has to be read out of the page source. `element-library-prior-art.md` records this PDF as
"stranded"; **it is not stranded, and that entry is now stale.**)

The sentence introducing it, page 964, verbatim:

> "The presence of thin dielectric substrates involves a relevant number of Floquet modes [62], and
> given the complexity of the problem, a closed formula which relates the capacitance to the
> dielectric thickness and permittivity is hard to find. A good solution can be the derivation of a
> simple interpolating formula which exactly matches the variation of the effective permittivity as
> a function of the dielectric thickness. To this aim, the variation of capacitance as a function of
> thickness and dielectric constant of the substrate is analyzed for **a patch array embedded within
> two dielectric substrates**. The optimal capacitance values obtained with the retrieving procedure
> are normalized to the **freestanding** values to obtain a thickness dependent effective
> permittivity. An expression that fits very well, the effective permittivity reads [58]:"

And the equation, read off a 8× render of page 5 (PDF page 6):

```
                    av        (  av      ) ⎡    −1     ⎤
    ε_eff  =  ε_r      +      ( ε_r  − 1 ) ⎢ ───────── ⎥ ,          (5)
                                           ⎣  exp^N(x) ⎦

                        av     ( d₁ ε_r1  +  d₂ ε_r2 )
    where  x = 10·d/D,  ε_r  = ─────────────────────────
                                     ( d₁ + d₂ )
```

> "and N is an exponential factor that takes into account the slope of the curve. This parameter can
> vary for different cell shapes depending on the unit cell filling factor [58]."

`exp^N(x)` means `[e^x]^N = e^(Nx)`; the two readings coincide, so there is no ambiguity in the
exponent. Rearranged, eq (5) is `ε_eff = ε_r^av − (ε_r^av − 1)·e^(−N·10·d/D)`.

Its **[58] is the closed 2012 APM paper**, verified from the ACES reference list. Its **[59] is
Callaghan, Parker & Langley 1991** — the ticket's second named route — cited by Costa alongside [58]
for the validity limit of the thick-substrate approximation, not as a source of a competing formula.

### 1b. The per-side restatement — Borgese & Costa 2020

Borgese & Costa, *"A Simple Equivalent Circuit Approach for Anisotropic Frequency Selective Surfaces
and Metasurfaces"*, *IEEE Trans. Antennas Propag.*, doi
[10.1109/TAP.2020.3008658](https://doi.org/10.1109/TAP.2020.3008658), preprint
[arXiv:2008.00530](https://arxiv.org/abs/2008.00530) (clean extractable text). Their eqs (9)–(10),
verbatim:

> "The effective permittivity can be computed by averaging the effective permittivity towards upper
> and lower dielectrics:
>
> `ε_reff = (ε_reff−up + ε_reff−down) / 2`   (9)
>
> If the substrate and superstate are enough thick, the effective permittivity can be computed by
> simply averaging the dielectric permittivity of the two dielectrics. However, if the substrates
> are thinner than 0.3D [15], where D is the periodicity of the periodic surface, the effective
> permittivity depends also on the thickness of the layers. The expression given in [15] can used in
> this case:
>
> `ε_reff−up = ε_r−up + (1 − ε_r−up) e^(−γ d_up / D)`   (10)
>
> where `d_up` represents the thickness of the **upper layer** and `γ` is a coefficient which takes
> into account the shape of the element [15]. `ε_reff−down` is computed with the same approach of
> eq. (10)."

Their **[15] is the same closed APM 2012 paper**, verified from their reference list. *This is the
missing formula in the ticket's own words — a finite-thickness dielectric layer above a printed
grid, with the layer above and the layer below treated separately.*

### 1c. The generalised form — Costa 2021, and the one to implement

Costa, *"A Simple Effective Permittivity Model for Metasurfaces within Multilayer Stratified
Media"*, *IEEE Trans. Antennas Propag.* **69**(8), pp. 5148–5153, August 2021, doi
[10.1109/TAP.2021.3060493](https://doi.org/10.1109/TAP.2021.3060493).
**Green open access** — author manuscript at the University of Pisa repository,
[hdl.handle.net/11568/1134368](https://hdl.handle.net/11568/1134368) (6 pages, LaTeX-produced, real
font encodings). *Note: Unpaywall/Semantic Scholar report this one as closed; **OpenAlex found the
green copy**. Three indexes are not interchangeable — see §9.*

The base relation, its eq (7), verbatim:

```
    ε_eff  =  ε_r  +  ( 1 − ε_r ) e^( −α (d/D) )                    (7)
```

> "where d is the thickness of the two substrates and D is the FSS periodicity. α is called
> shapefactor since its value is a function of the geometry of the FSS unit cell."

Its eq (8) replaces the vacuum outside with an arbitrary external medium:

```
    ε_eff  =  ε_r  +  ( ε_r−ext − ε_r ) e^( −α (d/D) )              (8)
```

And the generalisation to `N` layers on one side and `M` on the other — the form T1 should
implement — its eqs (9)–(13), verbatim (visually verified at 7× render):

```
    ε_eff  =  [ ε_eff−right(N) + ε_eff−left(M) ] / 2                (9)

    ε_eff−right(n) = ε_rn + ( ε_eff−right(n−1) − ε_rn ) e^(−α (d_n / D))              (10)

    ε_eff−left(m)  = ε_r(N+M−m+1)
                     + ( ε_eff−left(m−1) − ε_r(N+M−m+1) ) e^(−α (d_(N+M−m+1) / D))    (11)

    ε_eff−right(1) = ε_r1 + ( 1 − ε_r1 ) e^(−α (d₁ / D))            (12)

    ε_eff−left(1)  = ε_rM + ( 1 − ε_rM ) e^(−α (d_M / D))           (13)
```

> "For the most external substrates the effective permittivity `ε_eff−right(n−1)`,
> `ε_eff−left(m−1)` is the permittivity of the vacuum which is the most external dielectric"

*In plain terms: start at the outside of the stack, where there is only air, and walk inward one
layer at a time toward the printed pattern. Each layer pulls the running answer toward its own
permittivity, and how far it pulls depends on how thick it is compared with the cell spacing.
Do that on both sides and average the two.*

**Costa 2021 supersedes ACES eq (5) and says so.** Verbatim:

> "Relation (7) is very accurate for the two substrates case but it fails for more complex stackups.
> This work aims at generalizing the formulation."

and

> "The results of the two approaches start diverging when the thicknesses of the substrates are
> different."

That is exactly the repo's case — a 1.5 mm spacer below and a 25 µm coat above are not equal
thicknesses — so ACES eq (5)'s thickness-weighted `ε_r^av` is **the wrong tool for T1** and the 2021
per-side recursion is the right one. `LITERATURE-SUPPORTED`

---

## 2. Every symbol

| Symbol | Meaning | Source of the definition |
|---|---|---|
| `ε_eff` | Effective relative permittivity multiplying the freestanding grid capacitance: `C = C₀ · ε_eff`. Dimensionless | Costa 2021 eqs (1), (2), verbatim |
| `C₀` | The **freestanding** (both sides vacuum) grid capacitance | Costa 2021, verbatim |
| `ε_rn` | Relative permittivity of the *n*-th layer, counted **outward** from the metasurface on the right side | Costa 2021 Fig. 1(a) |
| `d_n` | Thickness of the *n*-th layer, same units as `D` | Costa 2021 Fig. 1(a) |
| `D` | **Cell periodicity** of the metasurface — the lattice repeat distance. Same `D` as Costa eq (10)'s | Costa 2021, verbatim |
| `α` | **Shape factor** — the decay constant of the transition, dimensionless. Fitted, geometry-dependent. §4 | Costa 2021, verbatim |
| `N`, `M` | Number of dielectric layers on the right and left of the metasurface | Costa 2021, verbatim |
| `N` (ACES eq 5) | *Different symbol, same role* — ACES writes the exponent against `x = 10 d/D`, so `α = 10·N_ACES`. §4 | derived, §4 |
| `x` | ACES's plotting variable, `x = 10 d/D`. Dimensionless | ACES, verbatim |
| `ε_r^av` | ACES's thickness-weighted mean, `(d₁ε_r1 + d₂ε_r2)/(d₁+d₂)`. **Superseded** by eqs (9)–(13) | ACES, verbatim |
| `γ` (Borgese 2020) | Same quantity as `α` | Borgese & Costa 2020, verbatim |

**A minor indexing slip in the source, recorded so a later reader does not trip on it.** Costa
2021's eq (13) writes `ε_rM` where the recursion's own convention (`N+M−m+1` at `m=1`) gives
`ε_r(N+M)`. The intent is unambiguous from the sentence introducing it — *"the most external
substrates"* — and from eq (12)'s symmetric statement. `INFERRED`, not load-bearing.

---

## 3. It is general, not one-sided — the evidence

The ticket asks precisely this. Five independent pieces of evidence, all pointing the same way:

1. **No ground plane appears in the geometry.** Costa 2021 Fig. 1(a) is a metasurface inside a stack
   of `N+M` layers with a plane wave arriving from free space; Fig. 1(b) is the transmission-line
   equivalent, terminated in `Z_v0` (free space) at *both* ends. `LITERATURE-SUPPORTED`
2. **The outermost medium is explicitly vacuum, on both sides.** Eqs (12) and (13) seed the
   recursion with `ε = 1` at each end — the definition of "not backed by anything".
3. **ACES Fig. 3, which introduces the same section, is captioned** *"Transmission line model for
   the analysis of an embedded FSS"* — free space at both ends.
4. **The verification is two-sided and asymmetric.** Costa 2021 §IV verifies against MoM for a
   metasurface between two *different* substrates (`ε_r1 = 10.2`, `ε_r2 = 4.4`) and for
   three-substrate stackups with the inner layer both denser and less dense than the outer. None has
   a ground plane. `LITERATURE-SUPPORTED`
5. **Borgese & Costa apply it as an ABCD cascade** `M_diel1 · M_FSS · M_diel2` — a pass-through
   stack, not a short-circuited one.

**The mechanism is the opposite of a mirror's, which is why it cannot be a grounded-only result.**
Costa 2021 states it verbatim:

> "The physical reason of the change of effective permittivity is that the electric field around the
> periodic surface is not entirely contained within the substrate, thus the FSS capacitance
> **decreases** proportionally to the substrate thickness."

*In plain terms: a thin layer holds less of the pattern's leaking field than a thick one, so the
pattern behaves as if it were sitting in something weaker than the layer's own material. A metal
mirror does the reverse — it bounces the leaked field straight back and makes the capacitance
larger. Same distance, opposite sign, different physics.*

### Sign, limit and consistency checks

Costa 2021 states three constraints for eq (7) and the recursion satisfies all three: `CALCULATED`

| Check | Result |
|---|---|
| `d → 0` | `e⁰ = 1`, so `ε_eff = ε_r + 1 − ε_r = 1` — freestanding. ✓ (Costa states this constraint explicitly) |
| `d/D → ∞` | `e^(−∞) = 0`, so `ε_eff = ε_r` — the bulk value. ✓ (stated explicitly) |
| `ε_r = 1` | `ε_eff = 1 + 0 = 1` for any `d`. ✓ (stated explicitly) |
| Monotonic in `d` | `dε_eff/dd = α(ε_r − 1)e^(−αd/D)/D` — positive for `ε_r > 1`, so thicker always means more. ✓ |
| Thick, one-sided | Eq (9) with `ε_eff-right → ε_r` and `ε_eff-left → 1` gives `(ε_r+1)/2` — **the classical half-average the repo already uses.** ✓ |
| ACES eq (5) ↔ Costa 2021 eq (7) | Set `d₁ = d₂ = d`, `ε_r1 = ε_r2 = ε_r`: ACES gives `ε_r − (ε_r−1)e^(−10N·d/D)`; eq (7) gives `ε_r − (ε_r−1)e^(−α·d/D)`. **Identical iff `α = 10·N`.** ✓ §4 shows the numbers agree |

---

## 4. The shape factor `α`, with numbers

`α` is the one thing the formula does not supply from first principles. Costa: *"α is called
shapefactor since its value is a function of the geometry of the FSS unit cell"* and *"proportional
to the filling factor of the unit cell"*. Three independent readings:

### 4a. Square loops — read off a legend

Costa 2021 Fig. 5 plots MoM-extracted effective permittivity against the model for a square-loop
FSS, `D = 10 mm`, `ε_r = 5` both sides, at three loop trace widths. The legend gives the fitted
values directly: `LITERATURE-SUPPORTED`

| Loop trace width | Fitted `α` |
|---|---|
| `w_loop = 1/16 D` | **16** |
| `w_loop = 3/16 D` | **13.5** |
| `w_loop = 7/16 D` | **12.5** |

The pairing was confirmed at 14× magnification: the diamond markers (`1/16 D`) lie on the solid
`α = 16` curve, the circles (`3/16 D`) on the dashed `α = 13.5`, the stars (`7/16 D`) on the dotted
`α = 12.5`. `INFERRED` (read off a drawing, but the marker-on-curve overlay is unambiguous).

**A tension worth recording:** this ordering means `α` *decreases* as the metal trace widens, which
reads against the paper's own prose that `α` is *"proportional to the filling factor"*. Either the
prose is loose or "filling factor" means something other than metal fraction. **The range is robust;
the trend direction is not, and nothing below leans on the trend.**

### 4b. A patch array — digitised, and this is the one the repo's cell resembles

ACES Fig. 4 plots `C/C₀ = ε_eff` against `x = 10 d/D` for a **patch array**, `D = 10 mm`,
`w = 2.5 mm`, symmetrically embedded, at three permittivities. 79 markers were located by pixel
analysis of an 8× render, calibrated against the plot's own gridlines, and fitted to
`ε_eff = ε_r − (ε_r − 1)e^(−Nx)`: `CALCULATED` (fit) over `INFERRED` (digitisation)

| Curve | `N` fitted | `α = 10N` | R² |
|---|---|---|---|
| `ε_r = 2` | 1.3172 | **13.17** | 0.99981 |
| `ε_r = 4` | 1.3122 | **13.12** | 0.99995 |
| `ε_r = 5` | 1.3228 | **13.23** | 0.99981 |

**Three curves at three different permittivities give the same exponent to within 0.8%, at
R² > 0.9998.** A free-intercept version of the same fit returns intercepts of 0.008–0.042 against a
predicted zero — so the `d → 0 ⇒ ε_eff = 1` constraint is satisfied by the data, not just by the
algebra. **This is a quantitative confirmation of the transcription in §1a**: the exponent is a pure
exponential in `d/D`, the prefactor is `(ε_r − 1)`, and `α ≈ 13.2` for this patch array.

It is also an **independent cross-check between two of the three papers** — the digitised `α = 13.2`
from the 2014 ACES figure sits inside the 12.5–16 range printed in the 2021 legend.

**Reading the source's own figures needs one caution.** ACES Fig. 4's curve labels are transposed:
the arrow marked `ε_r = 2` points at the curve saturating at 5 and vice versa. The saturation values
settle it (`ε_eff → ε_r`), and the fit above assigns each curve by its asymptote, not by its label.
Costa 2021's Fig. 4 caption and body text likewise disagree about which panel is which. Neither
affects anything used here. `INFERRED`

### 4c. What to use

**`α = 13.2` for a patch-type element, with 12.5–16 as the honest band.** `LITERATURE-SUPPORTED` for
the band, `CALCULATED` for the central value. Nothing in the literature gives `α` for a
lossy-bridge patch cell specifically; the band is the answer until a Floquet sweep on the actual
cell says otherwise.

---

## 5. The repo's own ansatz *is* this formula

[`encapsulation-em-coupling.md`](encapsulation-em-coupling.md) §3 constructed, from first principles
and without having seen any of these three papers, the following:

```
    w(t)     = 1 − exp( −4π t / D )
    ε_above  = 1 + ( ε_c − 1 ) · w(t)
    ε_eff    = ( ε_above + ε_substrate ) / 2
```

Expand the middle line: `ε_above = ε_c + (1 − ε_c)·e^(−4π t/D)`.

**That is Costa 2021 eq (12), character for character, with `α = 4π`.** And the third line is Costa
2021 eq (9). `CALCULATED` — this is algebra, not a claim about a source.

*In plain terms: the repository worked out the shape of the answer on its own, from the way a
periodic pattern's field dies away above it, and it landed on the published formula exactly. The
only thing it had to guess was how fast the field dies, and it guessed `4π`. The literature's fitted
values are 12.5 to 16. `4π` is 12.566.*

This is worth naming for what it is. `CLAUDE.md` says *"re-deriving a published, measured result
without being shown it first is how the method earns trust."* This is an instance of it, and the
guessed constant landed inside the published range at the low edge.

### The "good to about 2×" band collapses

`encapsulation-em-coupling.md` §3 carries the ansatz with a stated 2× uncertainty, and §14 propagates
that band into every regime-2 number. **That band is now a factor of `α/4π`, nothing more.**
`CALCULATED`

| `α` | Ratio to the repo's `4π` | Effect on the predicted shift at 25 µm |
|---|---|---|
| 12.5 (widest published loop) | 0.995 | **−0.5%** |
| 13.2 (patch array, §4b) | 1.050 | **+5.0%** |
| 16 (narrowest published loop) | 1.273 | **+27%** |

At thicker coats the spread narrows further, because the exponential saturates: at 1.0 mm on a
6.0 mm period the `α = 16` and `α = 4π` answers differ by 6%, not 27%.

**So the honest uncertainty on T1's thin-coat estimate is about `−1% / +27%`, not "a factor of two",
and the two remaining sources of error the ansatz listed — keeping only one harmonic, and weighting
by field energy rather than partial capacitance — are exactly what `α` absorbs empirically.**

---

## 6. Which correction goes on which side — the part T1 has to get right

**Costa's eq (10) and this formula are not competitors and must not be applied to the same
boundary.** They describe two different things that both scale with the same ratio `d/D`:

| | `costa-thin-spacer-correction.md` eq (10) | This document, eqs (9)–(13) |
|---|---|---|
| What is at distance `d` | A **metal ground plane** | **Free space**, beyond a dielectric layer |
| What happens as `d` shrinks | Capacitance **rises** (evanescent modes bounce off the PEC and add patch-to-ground capacitance) | Effective permittivity **falls** toward 1 (less of the field is held by the layer) |
| Sign of the resonance shift | **Down** | **Up** |
| Acts on | `C₀`, additively | `C₀`, multiplicatively |

*In plain terms: a mirror under the pattern makes it more capacitive; a coating that runs out before
the field does makes it less capacitive. Both are governed by how the pattern's spacing compares
with the distance, and it is easy to apply the wrong one.*

**For ADR-0033's cell — silicone spacer over a ground plane, coating on top — the split is:**

- **Below**: a PEC at `d = 1.5 mm`. This is Costa eq (10)'s regime. **Do not** apply eqs (12)/(13)
  to the substrate side: eq (12) would return `ε_eff-down = 2.83` instead of 2.9, a −2.4%
  correction in the wrong direction, because it assumes free space beyond the silicone and there is
  metal there instead. `CALCULATED`
- **Above**: air beyond the coat. This is eq (12)'s regime exactly, with `ε_r1 = ε_coat`,
  `d₁ = coat thickness`.

**What no source states, and this document will not invent:** whether the two corrections simply add
— eq (9)'s average over a mirror-corrected lower side and a (12)-corrected upper side, plus eq (10)
on top — is not written down anywhere reachable. Costa 2021's model has no ground plane; Costa's
2013 eq (10) has no superstrate. **The composition is `INFERRED`, and it is the residual open
question this ticket leaves behind.** It is also small: at 25 µm the two corrections are 1.0% and
2.2% of the capacitance respectively, so any cross-term between them is a second-order effect on a
few-percent quantity.

---

## 7. Numbers at ADR-0033's cell

Period `D = 6.0 mm`, silicone `ε_r = 2.9` below, coating of permittivity `ε_c` and thickness `t`
above. Baseline (thick air above) `ε_eff = 1.95`. Resonance shift from
`Δf/f ≈ −½ · Δε_eff/ε_eff`. `CALCULATED`

**Coating `ε_c = 2.4`** (ABS-class, matching Case 3's encapsulant in
[`literature-validation-cases.md`](literature-validation-cases.md)):

| `t` | `α = 4π` (repo) | `α = 13.2` (patch) | `α = 16` (upper) |
|---|---|---|---|
| 25 µm | −0.92% | **−0.96%** | −1.16% |
| 50 µm | −1.78% | **−1.87%** | −2.24% |
| 100 µm | −3.39% | **−3.54%** | −4.20% |
| 250 µm | −7.32% | **−7.59%** | −8.73% |
| 500 µm | −11.65% | **−11.97%** | −13.22% |
| 1.00 mm | −15.74% | **−15.96%** | −16.70% |

**Coating `ε_c = 3.2`** (Kapton-class):

| `t` | `α = 4π` | `α = 13.2` | `α = 16` |
|---|---|---|---|
| 25 µm | −1.44% | **−1.51%** | −1.82% |
| 50 µm | −2.80% | **−2.94%** | −3.52% |
| 100 µm | −5.33% | **−5.57%** | −6.60% |
| 250 µm | −11.50% | **−11.93%** | −13.72% |
| 500 µm | −18.31% | **−18.82%** | −20.77% |
| 1.00 mm | −24.73% | **−25.08%** | −26.25% |

**The ticket's "intermediate ~0.1–1 mm encapsulation regime" now has a closed form, and it is not a
small effect: −3.5% to −16% at `ε_c = 2.4`, −5.6% to −25% at `ε_c = 3.2`.** At 10 GHz that is
0.35–1.6 GHz and 0.56–2.5 GHz respectively.

*In plain terms: a coating thicker than about a tenth of a millimetre is not a trim. Half a
millimetre of a common plastic drags a 10 GHz design down past 8.8 GHz. The thin end — anything
under about 50 µm — stays inside a couple of percent and remains a retune rather than a redesign.*

These reproduce `encapsulation-em-coupling.md` §5's regime-2 band (−0.70% to −2.75% for 20–50 µm)
from the published formula rather than from the repo's own ansatz, which is the same thing said
twice — as §5 above explains, it *is* the same formula.

**One caveat carried forward unchanged from that document:** above roughly 1 mm the coating is also
an electrical-thickness transmission-line section in front of the whole stack, and these numbers are
a **resonance estimate, not an absorption prediction**. The effective-permittivity model handles the
capacitance loading; it says nothing about the layer acting as a matching transformer. Costa 2021
makes the same split verbatim — *"A multilayer stackup affects the frequency response … in a twofold
way"* — and handles the second effect with the ABCD cascade, which this repo already has.

---

## 8. The successor: a physically-derived version, also open access

Howard, Hunt & Allen (Georgia Tech Research Institute), *"Multimodal Effective Permittivity Model
for Metasurfaces Embedded in Layered Media"*, [arXiv:2410.17981](https://arxiv.org/abs/2410.17981),
2024. **Open access, clean text.**

It restates Costa 2021 as the *"single-parameter exponential decay model"* and replaces it with a
sum over Floquet harmonics. Their eq (44), the per-harmonic recursion:

```
                  (i−1)     (  (i)     (i−1)  )     1 − e^(−2α_h d_i)
    ε_rh,in^(i) = ε_rh,in  + ( ε_r   − ε_rh,in ) · ─────────────────────
                                                    1 + r_i e^(−2α_h d_i)
```

with `r = (ε_r^(2) − ε_r^(1))/(ε_r^(2) + ε_r^(1))` and `α_h` the **evanescent decay constant of
Floquet harmonic `h`**, defined verbatim: *"their amplitude decays away from the surface as
`exp(−α_mn z)`."*

**This closes the loop on where the repo's `4π` came from.** For the first evanescent harmonic on a
square lattice of period `D`, well below the grating-lobe onset, `α_10 ≈ 2π/D`, so
`2α_h d = 4π d/D` — the repo's own exponent, arrived at by the same reasoning. Howard et al. say so
directly about Costa's fitted constant: *"the shape factor α is related to the fill factor of metal
in the unit cell, which can be tied to the decay rate of underlying harmonic amplitudes."*
`LITERATURE-SUPPORTED`

**Why the fitted `α` runs a little above `4π`.** Costa's single term is standing in for a sum over
many harmonics, the higher ones decaying faster. A sum of decays fitted by one decay comes out
steeper than the slowest term alone — which is exactly the direction observed (13.2 against 12.566).
`INFERRED`, but it is the reading Howard et al.'s §3.1 argues for.

They also note something T1 should not lose: **the model has no frequency in it at all**, and that
is deliberate. Verbatim:

> "nowhere in (35) is there a term for the frequency of operation of the metasurface … Effective
> permittivity in reality is unrelated to the frequency of operation."

*In plain terms: this correction depends on how thick the coating is compared with the spacing
between the printed shapes, and not at all on the radio frequency. That is counter-intuitive and it
is the same point `costa-thin-spacer-correction.md` §4 already established for eq (10).*

**One discrepancy, recorded not resolved.** Howard et al.'s eq (35), their restatement of Costa
2021, reads `ε_r,eff = ε_r^(1) + (ε_r^(2) − ε_r^(1))e^(−αd₂/P)`, whose limits are inverted relative
to both Costa's own eq (8) and to Howard's own eq (43). It looks like an index transposition in the
restatement. **Costa's primary statement governs** — it is the one with the three physical
constraints written out and checked. `INFERRED`

**Recommendation:** implement Costa 2021 eqs (9)–(13). The multimodal model is the upgrade path if
the single-term fit is ever shown to be the limiting error, and it needs a per-harmonic amplitude
weighting the repo does not currently compute.

---

## 9. Every route tried

**Succeeded:**

| Route | Result |
|---|---|
| **ACES Journal 29(12) 2014 galley PDF**, `journals.riverpublishers.com/index.php/ACES/article/download/10793/9015` | **Eq (5) recovered.** The landing page exposes no PDF link; the galley id has to be read out of the page source. This corrects `element-library-prior-art.md`'s "PDF stranded" entry |
| `pymupdf` text layer of that PDF | All eq (5) tokens present, scrambled in reading order but complete and font-encoded (not OCR) |
| 8× and 12× raster render of ACES p. 5, eye-read | **Decisive.** `ε_eff = ε_r^av + (ε_r^av − 1)[−1/exp^N(x)]`, `x = 10*d/D`, `ε_r^av = (d₁ε_r1+d₂ε_r2)/(d₁+d₂)` |
| **ACES Fig. 4 pixel digitisation** — 79 markers, three curves, gridline-calibrated | **α = 13.12–13.23, R² > 0.9998 on all three.** Quantitative confirmation of the transcription and the first patch-array number |
| **arXiv:2008.00530** (Borgese & Costa 2020) | **Independent per-side restatement**, clean text, attributed to the same closed APM 2012 paper |
| **Costa 2021 TAP, green OA at Pisa IRIS** `hdl.handle.net/11568/1134368` | **The generalised model, eqs (7)–(13).** Text layer + 7×/9× render agree character for character |
| Costa 2021 Fig. 5 legend, confirmed at 14× | `α` = 16 / 13.5 / 12.5 for loop widths `1/16 D` / `3/16 D` / `7/16 D` |
| **arXiv:2410.17981** (Howard, Hunt & Allen 2024) | Independent restatement by a **different group**, plus the physically-derived successor model |
| ACES reference list | `[58]` = the closed APM 2012 paper; `[59]` = Callaghan, Parker & Langley 1991 — both the ticket's named candidates pinned |
| OpenAlex, on the Costa 2021 DOI | **Found the green copy that Unpaywall and Semantic Scholar both missed.** Worth remembering: three OA indexes are not interchangeable |

**Failed, and why:**

| Route | Outcome |
|---|---|
| **Costa, Monorchio & Manara, IEEE APM 54(4) 2012**, doi `10.1109/MAP.2012.6309153` — the ticket's target | **Closed access, no free copy exists.** Unpaywall: `is_oa: false`, `oa_status: closed`, `has_repository_copy: false`, `oa_locations: []`. Semantic Scholar: `status: CLOSED`, empty PDF URL. OpenAlex: `is_oa: false`, `any_repository_has_fulltext: false`. **Three independent indexes agree.** The University of Pisa's own repository — the authors' institution — holds the record at `hdl.handle.net/11568/158260` and reports *"Non ci sono file"* ("there are no files"). → `RUNNING-LISTS.md` §1. **It did not need to be reached:** three later open-access papers restate its result |
| **IEEE Xplore** | Not attempted. `RUNNING-LISTS.md` §1 records HTTP 418 from this environment, and the ticket explicitly says not to retry |
| **Callaghan, Parker & Langley 1991**, *IEE Proc. H* **138**(5), pp. 448–454, doi `10.1049/ip-h-2.1991.0075` — the ticket's second named route | **Closed access, no repository copy.** Unpaywall: `is_oa: false`, `has_repository_copy: false`, `oa_locations: []`. Semantic Scholar: `status: CLOSED`. Kent Academic Repository holds a record at `kar.kent.ac.uk/38670/` which OpenAlex reports as `is_oa: false` with no PDF; direct fetch failed on TLS and then HTTP 503, so the record was not read — but two indexes independently report no free copy. **Its role is now scoped:** the ACES paper cites it as `[59]`, alongside `[58]`, for the *validity limit* of the thick-substrate approximation, not as a source of a competing closed form. → `RUNNING-LISTS.md` §1 |
| **Munk**, *Frequency Selective Surfaces: Theory and Design* (Wiley, 2000) — the ticket's third route | **Not read. No absence claim is made about it.** One web search for a restatement of its dielectric-loading treatment returned nothing usable. It is a book, not indexed by the OA APIs, and the question it was named to answer is now answered by three reachable papers, so it drops off the critical path rather than being closed out |
| **CORE.ac.uk API** | HTTP 429, rate-limited. Not retried — OpenAlex covered the same ground |
| **academia.edu**, *"Numerical Model of the Effective Permittivity for Square-Loop Frequency Selective Surfaces"* | HTTP 403. Would have been a useful **independent, non-Costa** cross-check on the exponential form; Howard et al. 2024 serves that role instead |
| **ResearchGate** | Not attempted — unnecessary once the three primary sources were in hand |

---

## 10. Provenance summary

| Claim | Provenance |
|---|---|
| ACES eq (5) as transcribed in §1a | `LITERATURE-SUPPORTED` — text layer + two render magnifications, plus the §4b fit to the paper's own Fig. 4 at R² > 0.9998 |
| Costa 2021 eqs (7)–(13) as transcribed in §1c | `LITERATURE-SUPPORTED` — LaTeX-produced text layer + 7×/9× render, in agreement |
| Borgese & Costa 2020 eqs (9)–(10) | `LITERATURE-SUPPORTED` — clean arXiv text |
| **The formula is general, not grounded** | `LITERATURE-SUPPORTED` — five independent lines of evidence, §3 |
| The three limit constraints on eq (7) | `LITERATURE-SUPPORTED` — stated verbatim by Costa and verified by algebra |
| `α = 12.5 / 13.5 / 16` for square loops | `LITERATURE-SUPPORTED` (legend values); the **width↔α pairing** is `INFERRED` (read at 14×) |
| `α ≈ 13.2` for a patch array | `CALCULATED` (fit, R² > 0.9998) over `INFERRED` (pixel digitisation of a published figure) |
| `α = 10 · N_ACES` | `CALCULATED` — algebraic identity between the two published parameterisations |
| The repo's §3 ansatz is Costa 2021 eq (12) with `α = 4π` | `CALCULATED` — algebra |
| The 2× band becomes −1% / +27% | `CALCULATED` |
| §7's shift tables | `CALCULATED`, at `α = 13.2` central with the 12.5–16 band shown |
| Eq (10) below / eq (12) above split for a ground-backed cell | `INFERRED` — follows from the stated mechanisms; **no source composes them** |
| `4π` is the first-harmonic decay constant | `LITERATURE-SUPPORTED` (Howard et al. 2024 define `α_mn` as the evanescent decay constant); the arithmetic `α_10 = 2π/D` is `CALCULATED` |
| APM 2012 has no free copy | `LITERATURE-SUPPORTED` — three OA indexes plus the authors' own institutional repository |
| Callaghan 1991 has no free copy | `LITERATURE-SUPPORTED` — two OA indexes agree |
| Munk 2000 | **Unread. No claim, absent or otherwise** |
| ACES Fig. 4 / Costa 2021 Fig. 4 label transpositions | `INFERRED` — read off the drawings; not load-bearing |

---

## 11. Register updates

**Opens, for `RUNNING-LISTS.md` §1** — the existing APM 2012 row should be **upgraded from "needs
institutional access" to "closed-access confirmed, and no longer needed"**, and a Callaghan row
added. Proposed text is in the ticket comment; this document does not write that file.

**Closes:** #446, in full. The closed form exists, is general, is transcribed here with a symbol
table and limit checks, and has a numerical shape factor.

**For T1 (#445):** implement Costa 2021 eqs (9)–(13), not ACES eq (5) — the 2021 paper says
explicitly that eq (5)'s thickness-weighted average *"fails"* for unequal layer thicknesses, which
is the repo's case. The seam is
`grid_effective_permittivity(eps_r)` at **`rf_tools/sheet_impedance.py:51`** — verified by opening
the file; note that `encapsulation-em-coupling.md` cites this as `rf_tools/calculations.py:1055`,
which does not exist in the tree today. It takes one argument and hardcodes
air above, and its own docstring already flags the gap. The change is to take a list of `(ε_r, d)`
layers per side plus `D` and `α`, and default
`α = 13.2` with the 12.5–16 band exposed as an uncertainty. **The residual open question is §6's
composition with Costa eq (10) on a ground-backed cell, and it is worth a Floquet sweep, not another
literature search.**

**What this does not close:** nothing here is measured. Every number is a fit to somebody else's
simulation, or arithmetic on top of one. The cap stays at `SIMULATED`, and the cheapest thing that
would move it is the bare / +25 µm / +1.8 mm sweep `encapsulation-em-coupling.md` §13 already
specifies — now with a published prediction to be wrong against, which is worth more than a sweep
with no prediction attached.
