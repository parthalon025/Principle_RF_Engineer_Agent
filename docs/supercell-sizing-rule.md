# A super-cell sizing rule, derived from what the surface is for

**Date:** 2026-09-04 (rewritten the same day — see §7)
**Ticket:** [#130](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/130) — serves [#111](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/111), part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104).
**Question:** How large should a block of identical symbols be, given that placing unlike symbols side by side breaks the assumption each was characterised under?

[#131](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/131)'s survey established there is **no convention to inherit** — every block size in the literature is set by beam geometry, control-line count, fabrication tolerance or compute cost, never by an error budget. This document derives one. It is item 3 on the research agenda in [`RUNNING-LISTS.md`](./RUNNING-LISTS.md) §5.

---

## Bottom line up front

**The block size is not a number. It is a function of the requirement.**

A coded surface exists to reduce what a radar sees. It does that by
**cancellation**: two block types reflect out of phase, the returns subtract,
and what is left goes off to the side. Every constraint below falls out of that
one sentence, and nothing below is meaningful without it.

**The floor.** Coupling error perturbs the phase difference away from the ideal
180°, so some of the return survives. The surviving fraction is exactly
`sin(δ/2)`, which converts a phase error straight into decibels of lost
reduction — and inverts to give the budget the requirement actually implies:

```
    RCS reduction (dB)  =  20 · log₁₀( sin(δ/2) )
    phase budget  δ     =  2 · arcsin( 10^(−RCSR_dB / 20) )
```

| Required reduction | 6 dB | 10 dB | 15 dB | 20 dB | 30 dB |
|---|---|---|---|---|---|
| **Phase budget it implies** | 60.2° | **36.9°** | 20.5° | 11.5° | 3.6° |

**The ceiling.** The redirected energy has to miss the receiver — which means
clearing the panel's *own* specular lobe, whose half-width is about `λ/(2L)`
for an aperture of side `L`. That is **4.8°** for a 6 λ coupon and **0.95°**
for a 30 λ panel.

**And the two together are far more permissive than a first pass suggested.**
At a 10 dB requirement every element family surveyed has a workable block size.
The rule bites at demanding reduction levels, not at ordinary ones:

| Element family | Pitch | Δφ_max | at 10 dB | at 20 dB |
|---|---|---|---|---|
| **Fixed-edge, interior-tuned** | 0.5 λ | 12° | N ≥ 2 | N ≥ 3 |
| Minkowski fractal | 0.5 λ | 21° | N ≥ 2 | N ≥ 7 |
| Variable-size square patch | 0.5 λ | 25° | N ≥ 2 | N ≥ 8 |
| **Fixed-edge, interior-tuned** | 0.4 λ | 20° | N ≥ 2 | N ≥ 6 |
| Minkowski fractal | 0.4 λ | 45° | N ≥ 4 | N ≥ 15 |
| Variable-size square patch | 0.4 λ | 85° | N ≥ 9 | **no N works** |

So the honest statement of what interior tuning buys is **not** "the difference
between possible and impossible." It is:

> **Headroom, and spatial resolution.** At an ordinary 10 dB requirement an
> interior-tuned alphabet works with 2-cell blocks where a size-tuned square
> patch needs 9 — four and a half times coarser control over the surface. At
> 20 dB the square patch at 0.4 λ pitch runs out of feasible block sizes
> entirely, and interior tuning is what keeps the design available at all.

**Two corrections are folded in.** An earlier version claimed three of six
families were infeasible outright — an artefact of two borrowed constants; §7
records that. And the "no N works" entry above is **conditional on panel size**:
it holds on a 6 λ coupon and fails on a 30 λ panel, because what binds there is
not the scattering angle but a **panel-fit constraint the first version omitted
entirely**. See §5.5.

**And every formula below assumes a square cell on a square lattice.** The
project's own anchor violates that. §5.5 gives the two-index generalisations,
verified to reduce to the square case.

---

## 1. What the surface is for

Everything here is downstream of the objective, so it is worth stating plainly
before any arithmetic.

A radar sends out a pulse and listens for the echo. **Radar cross-section** is
how big that echo is — how visible the object is. The skin's job is to make the
echo smaller, and there are only two ways to do it:

- **Absorb it.** Turn the energy into a small amount of heat, so nothing comes
  back. This is the patent's Example 3, and it is a *uniform* surface — one cell
  repeated. Nothing in this document applies to it.
- **Redirect it.** Send the energy somewhere other than back at the radar. This
  is the patent's Example 7 and every coding metasurface, and it is what this
  document is about.

The second works by cancellation. Pave the surface with two kinds of block whose
reflections are **half a cycle out of step**, and in the straight-back direction
the two returns subtract to nothing. The energy is not destroyed — it reappears
as lobes off to the side, which is fine, because the radar is not there.

**Two things can therefore go wrong, and they are the floor and the ceiling.**
The cancellation can be imperfect, so some echo survives. Or the redirected
lobes can come off at too shallow an angle and land back in the radar's ear
anyway. The first pushes block size up; the second pushes it down.

---

## 2. The floor: from coupling error to decibels

### 2.1 Why the phase drifts

Each letter is characterised alone — simulated as though surrounded by copies of
itself, which is standard practice and exact for a surface made of one letter.
Real coded surfaces mix letters, and at these spacings neighbouring shapes sit
inside each other's near field, so a letter beside a *different* letter does not
behave as its record says. That discrepancy is `Δφ_max`, measured by Costanzo's
protocol (the same cell solved twice, once among its own kind and once with its
two strong-coupling neighbours swapped for the alphabet's extremes).

Blocking helps, because a cell in the middle of a block *does* see its own kind.
In an N × N block the cells touching a foreign block are the outer ring, so the
**boundary fraction** is

```
    f(N) = (N² − (N−2)²) / N²  =  (4N − 4) / N²
```

| N | 2 | 3 | 4 | 6 | 9 | 12 | 16 |
|---|---|---|---|---|---|---|---|
| f(N) | 1.000 | 0.889 | 0.750 | 0.556 | 0.395 | 0.306 | 0.234 |

and the block's phase error is bounded by `Δφ_block ≤ Δφ_max · f(N)`. This decays
as **1/N** — slowly. Halving the error costs a doubling of the block in both
directions.

### 2.2 What a phase error costs, in the units the requirement uses

This is the step the first version of this document skipped, and skipping it is
what let a borrowed number in.

Two block types with reflection coefficients `e^{jφ₁}` and `e^{jφ₂}` cover equal
area. Averaged over the aperture, the specular return is proportional to

```
    | e^{jφ₁} + e^{jφ₂} | / 2  =  | cos( (φ₂ − φ₁) / 2 ) |
```

which is zero when the difference is exactly 180° — perfect cancellation. Write
the difference as `180° − δ`, where δ is the error, and the identity
`cos(90° − δ/2) = sin(δ/2)` gives the surviving amplitude directly. So

```
    RCS reduction (dB)  =  20 · log₁₀( sin(δ/2) )
```

Plain English: **δ is how far out of step the two blocks are, and `sin(δ/2)` is
the fraction of the echo that fails to cancel.** A 37° error leaves about 32 % of
the amplitude, which is 10 dB — a tenfold cut in power.

Inverting gives the budget a stated requirement implies:

```
    δ_budget  =  2 · arcsin( 10^(−RCSR_dB / 20) )
```

| Requirement | 6 dB | 10 dB | 15 dB | 20 dB | 30 dB |
|---|---|---|---|---|---|
| δ_budget | 60.2° | **36.9°** | 20.5° | 11.5° | 3.6° |

The 10 dB row is the familiar **"180° ± 37°"** criterion of the chessboard
RCS-reduction literature, which is reassuring: the derivation reproduces a rule
of thumb that field already uses, rather than inventing one.

`N_min` is then the smallest N with `Δφ_max · f(N) ≤ δ_budget`.

> **Where the previous budget came from, and why it was wrong.** It used
> **±22.5°**, the half-step of a 3-bit phase quantisation. That is a
> **beam-forming** convention: it keeps quantisation lobes acceptable when
> steering a beam. This surface is not steering a beam. `RUNNING-LISTS.md` §3
> item 13 already recorded that phase quantisation is characterised for
> beam-forming only "not for absorption or backscatter reduction, which is what
> this effort actually optimises" — and the first version imported it anyway.
> ±22.5° happens to correspond to 14.2 dB, so the old rule was silently
> enforcing a requirement nobody had stated.

---

## 3. The ceiling: the lobe has to actually miss

A chessboard of N × N blocks has a pattern period of `2Np`. Writing the pattern
as `sign(cos(πx/a)·cos(πy/a))` with block side `a = N·p`, its dominant spatial
frequency sits at `(±π/a, ±π/a)`, so the diagonal lobes leave at

```
    sin θ  =  λ / (N · p · √2)
```

| N | 1 | 2 | 3 | 4 | 6 | 9 |
|---|---|---|---|---|---|---|
| **p = 0.5 λ** | evanescent | 45.0° | 28.1° | 20.7° | 13.6° | 9.0° |
| **p = 0.4 λ** | evanescent | 62.1° | 36.1° | 26.2° | 17.1° | 11.3° |

`N = 1` produces no propagating diffraction order at all, which is why nobody
builds cell-by-cell checkerboards, and it sets a hard floor of **N ≥ 2**.

### How far off is far enough?

Not an arbitrary threshold. **The redirected lobe has to fall outside the
panel's own specular lobe** — the beam the flat panel would return by itself.
For an aperture of side `L`, that lobe's first null is at roughly `λ / (2L)`
radians:

| Panel size | 6 λ (a coupon) | 12 λ | 30 λ | 100 λ (a real part) |
|---|---|---|---|---|
| Specular lobe half-width | **4.8°** | 2.4° | 0.95° | 0.29° |

Two consequences, and the second is the useful one:

- **The ceiling is generous.** At 4.8° and 0.5 λ pitch, blocks up to N = 16 keep
  the lobe clear. The earlier version used θ_min = 30°, which pinned N to 2 —
  but 30° was picked, not derived from anything.
- **The coupon is the hard case; the real part is easy.** A bigger panel has a
  *narrower* specular lobe, so a shallower redirection still misses. A rule
  validated on a 180 mm coupon is being validated under a tighter angular
  constraint than the aircraft panel it is meant for. That is the right
  direction for a test to err, and worth knowing before anyone reads a coupon
  result as pessimistic.

`N_max` is the largest N with `θ(N) ≥ θ_min`, and **θ_min is a per-requirement
input** — bounded below by the panel's specular lobe, and raised by anything the
requirement says about bistatic angles or a moving threat.

---

## 4. The windows

Floor from §2, ceiling from §3, at a 10 dB requirement on a 6 λ coupon
(δ_budget = 36.9°, θ_min = 4.8°):

| Element family | Pitch | Δφ_max | N_min | N_max | Window |
|---|---|---|---|---|---|
| Fixed-edge, interior-tuned | 0.5 λ | 12° | 2 | 16 | **2 – 16** |
| Minkowski fractal | 0.5 λ | 21° | 2 | 16 | **2 – 16** |
| Variable-size square patch | 0.5 λ | 25° | 2 | 16 | **2 – 16** |
| Fixed-edge, interior-tuned | 0.4 λ | 20° | 2 | 21 | **2 – 21** |
| Minkowski fractal | 0.4 λ | 45° | 4 | 21 | **4 – 21** |
| Variable-size square patch | 0.4 λ | 85° | 9 | 21 | **9 – 21** |

**Everything is feasible at 10 dB.** Raise the requirement to 20 dB
(δ_budget = 11.5°) and the picture separates:

| Element family | Pitch | N_min at 20 dB | Verdict |
|---|---|---|---|
| Fixed-edge, interior-tuned | 0.5 λ | 3 | comfortable |
| Fixed-edge, interior-tuned | 0.4 λ | 6 | workable |
| Minkowski fractal | 0.5 λ | 7 | coarse |
| Variable-size square patch | 0.5 λ | 8 | coarse |
| Minkowski fractal | 0.4 λ | 15 | very coarse |
| Variable-size square patch | 0.4 λ | 21+ | **no feasible N** *(on a 6 λ coupon — see §5.5)* |

**So the rule is a sliding scale, not a gate**, and the useful way to read it is
as *how much surface resolution a given alphabet costs you at a given
requirement*. Blocks are the unit of spatial control: an N = 2 design can vary
its pattern twice as finely in each direction as N = 4, which matters for
shaping where the energy goes and for working on a curved host.

**What survives from the first version:** the two-constraint structure, the 1/N
decay, the scattering-angle collapse, and the physical mechanism behind
interior tuning — a size-tuned patch changes its own outline and therefore the
gap to its neighbour, 0.009 λ to 0.19 λ across one published alphabet, a 20×
swing in coupling capacitance. That measurement is real and is why `Δφ_max`
differs so much between families.

---

## 5. Scope — where this does and does not apply

**Applies to** one-bit (and by extension few-bit) **coding metasurfaces** whose
objective is redirecting scattered energy — the patent's Example 7, and Tier B
families generally.

**Does not apply to the absorber.** Example 3, the project's anchor, is a
*uniform* surface: one cell repeated, no unlike neighbours, no cancellation
between block types. None of this governs it.

**Does not apply to the broadband super-cell.** Putting several slightly
detuned resonators in one block to widen an absorber's bandwidth
([#110](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/110)/[#129](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/129))
uses a block for a different reason: it steers nothing, so the §3 ceiling does
not exist. Same word, opposite sizing pressure.

**Assumed a square cell on a square lattice.** Both the boundary-count in §2.1
and the diffraction geometry in §3 do. Example 3's cell is **4.2 × 12 mm** —
0.14 λ by 0.40 λ at 10 GHz, an aspect ratio of 2.86 — which violates it.
**Answered by [#138](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/138): the rule does not survive unamended.** §5.5 carries the four
amendments, and the failure runs *against* this document's headline conclusion.

## 5.5 Amendments for non-square cells and finite panels

From [`ishape-interior-tuning.md`](./ishape-interior-tuning.md) §5, re-derived
and checked here. Each reduces exactly to the square-cell form above, so these
are generalisations rather than replacements.

**Amendment 1 — the boundary fraction takes two indices.**

```
    f(Nx, Ny) = 1 − (Nx−2)(Ny−2)/(Nx·Ny)      for Nx, Ny ≥ 2
              = 1                              if either is 1
```

Verified identical to `(4N−4)/N²` for Nx = Ny = 2…10.

**Amendment 2 — the lobe is not on the diagonal.**

```
    sin θ = (λ/2)·√( 1/ax² + 1/ay² )        tan φ = ax / ay
```

with `ax = Nx·px`, `ay = Ny·py`. Reduces to `λ/(a√2)` when `ax = ay` (checked:
both give 1.4142 at half-wavelength pitch). **The azimuth term is new and is not
cosmetic** — at Example 3's 4.2/12 aspect ratio a 1 × 1 block throws its lobes at
**φ = 19.3° from the long axis, not 45°.** Anyone measuring a coupon needs to
know where to point the receiving horn.

**Amendment 3 — small blocks can be forbidden outright, and here they are.**
Requiring `sin θ ≤ 1` for a propagating lobe at all, on Example 3's cell:

| Block | sin θ | Result |
|---|---|---|
| 2 × 2 | 1.891 | **evanescent — redirects nothing** |
| 3 × 2 | 1.344 | evanescent |
| 4 × 2 | 1.089 | evanescent |
| **5 × 2** | 0.949 | **71.5°** — the smallest that radiates |
| 4 × 3 | 0.985 | 79.9° |

In the tall-block limit the condition is simply `ax ≥ λ/2` = **14.99 mm = 3.57
cells** on the `a₁` axis: *a coding block must be at least half a wavelength
across on the coding axis, however small the cell.* The square-cell case hides
this, because at 0.5 λ pitch `N = 2` already satisfies it.

> **This runs opposite to §4's headline.** Because blocks of 4–5 cells and up are
> *forced* by the physics here, `f(N)` is no longer pinned at 1 and **the block
> genuinely averages.** "N = 2 is the only size allowed, so grouping averages
> nothing" is a property of a half-wavelength square cell, not a general truth
> about coding metasurfaces.

**Amendment 4 — the block has to fit on the panel, twice per axis.** The first
version omitted this, and on a coupon it is the **binding** constraint:

```
    2·Nx·px ≤ L        and        2·Ny·py ≤ L
```

A chessboard needs at least one full period per axis. On #106's 180 mm (6 λ)
coupon that caps `Ny` at **7** and `Nx` at **21** for Example 3's cell — and
`Ny` = 7 is already an 84 mm block.

**This is what makes §4's "no N works" conditional.** The square patch at 0.4 λ
needing N = 29 fails on a 6 λ coupon because 29 blocks do not fit twice, not
because the scattering angle forbids them; on a 30 λ panel the same alphabet has
a workable block. **The verdict depends on the size of the part**, which is a
per-requirement input — and, once again, the coupon is the hard case.

---

## 6. Provenance and honest limits

| Claim | Provenance |
|---|---|
| Δφ_max values (12° / 21° / 25° at 0.5 λ; 20° / 45° / 85° at 0.4 λ) | **LITERATURE-SUPPORTED** — Costanzo, Venneri & Di Massa, *IJAP* 2019, [10.1155/2019/4890710](https://doi.org/10.1155/2019/4890710), Table 3 and Figs. 5–7. Method-of-moments, so `SIMULATED` at source |
| Cancellation identity `RCSR = 20 log₁₀ sin(δ/2)` | **CALCULATED** — two-term aperture average. The 10 dB case is **confirmed at primary level**: Haji-Ahmadi, Nayyeri, Soleimani & Ramahi, *Sci. Rep.* **7**:11437 (2017), [PMC5595835](https://pmc.ncbi.nlm.nih.gov/articles/PMC5595835/), state *"a phase difference of 180 ± 37° … provides at least 10 dB monostatic RCS reduction"*. The formula returns **36.87°** — agreement to 0.13°, by two independent routes |
| Boundary fraction `(4N−4)/N²` | **CALCULATED** — counting |
| Chessboard diffraction angle | **CALCULATED** — Fourier content of the coding pattern; standard result |
| Specular lobe half-width ≈ λ/(2L) | **CALCULATED** — standard uniform-aperture result |
| `Δφ_block ≤ Δφ_max · f(N)` | **INFERRED** — our model, see below |
| The windows | **CALCULATED** from the above |

**Six limits, stated rather than buried:**

- **The error model is binary per cell** — full error on a boundary cell, none
  inside. Coupling is not that sharp: An et al. show one ring of neighbours
  captures most of the error but four rings still matter, so this
  **understates** for N ≥ 4. It is exact at N = 2 only.
- **δ and Δφ_block are not quite the same quantity.** Δφ_max is the worst-case
  shift of *one* cell. If the two block types are perturbed in opposite
  directions the phase *difference* error could approach twice that. Taking
  δ = Δφ_block is therefore optimistic by up to a factor of two, and a
  worst-case reading should double it.
- **Δφ_max is a worst case by construction** — the alphabet's two extreme
  members, swapped in along the strongest-coupling axis. Real designs rarely
  place extremes adjacent, so this pulls the other way.
- **The scattering formula assumes an infinite chessboard.** On a 6 λ coupon the
  lobes broaden and the angle is less sharply defined — not a small correction
  at that size, and it interacts with the specular-lobe threshold in §3.
- **Lossless reflectors are assumed** in the cancellation algebra (|Γ| = 1 for
  both block types). Printed MXene and carbon are lossy, which *helps* the RCS
  number but means the two blocks' amplitudes differ, leaving a residual the
  phase-only treatment does not capture.
- **Nothing here is measured.** Every input is simulated or calculated.
  Measuring Δφ_max for our own alphabet is
  [#132](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/132)'s
  work and needs bench access
  [#133](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/133)
  does not have.

**What would falsify it:** a coded surface whose measured RCS reduction differs
markedly from `20 log₁₀ sin(δ/2)` at its known phase error — which would mean
the two-term aperture average is too crude for real, finite, lossy panels.

---

## 7. Correction notice — what the first version of this document said

Published 2026-09-04 and rewritten the same day, before merge.

**It claimed:** the block size is pinned to N = 2; at N = 2 grouping averages
nothing; therefore an alphabet whose Δφ_max exceeds the budget "cannot be
rescued by grouping"; and **three of six element families have no feasible block
size at all**, the variable-size square patch among them.

**Why that was wrong.** Both of its constraints were borrowed conventions rather
than derived from the objective:

1. **The ±22.5° budget** is a beam-forming quantisation half-step, imported into
   a backscatter-reduction problem — the exact error `RUNNING-LISTS.md` §3
   item 13 warns against. Derived from the objective, a 10 dB requirement
   allows **36.9°**.
2. **θ_min = 30°** was picked, not derived. The physical requirement is that the
   lobe clear the panel's own specular lobe, which for a 6 λ coupon is **4.8°**.

Together those two made the rule roughly six times stricter than the objective
warrants, and the "three of six are infeasible" headline was an artefact of
them. At 10 dB every family surveyed is feasible.

**What was right and is kept:** the structure — a floor that falls as 1/N
against a ceiling that collapses much faster — the two formulae, the
interior-tuning mechanism and its measured 20× gap swing, and the scoping in §5.

**The methodological lesson, which is the durable part:** *define failure
against the purpose, not against an internal metric.* A budget in degrees is
not a requirement; a requirement is in decibels of RCS reduction over a band and
an angular window. Every threshold in this loop should be traceable to something
a customer would actually write down, and a constant that cannot be traced that
way is a smuggled assumption.

---

## 8. Sources

1. S. Costanzo, F. Venneri, G. Di Massa, "Modified Minkowski Fractal Unit Cell for Reflectarrays with Low Sensitivity to Mutual Coupling Effects", *IJAP* 2019, Art. 4890710. [10.1155/2019/4890710](https://doi.org/10.1155/2019/4890710). Retrieved in full; Table 3 and Figs. 5–7 supply every Δφ_max.
2. S. Costanzo, F. Venneri, A. Borgia, G. Di Massa, *IJAP* 2019, Art. 9479010. Retrieved. Source of the ±22.5° margin — retained here only as the counter-example in §7.
3. S. An, B. Zheng, M. Y. Shalaginov *et al.*, [arXiv:2102.01761](https://arxiv.org/abs/2102.01761). The only published error-versus-neighbour-count curve; bounds the binary-cell approximation.
4. M. Zhou *et al.*, "Analysis of printed reflectarrays using extended local periodicity", *EuCAP* 2011. Establishes that the coupling error lives in the scattered field rather than the main beam — which is why it lands on this project's objective.

Full coupling background: [`local-periodicity-coupling-error.md`](./local-periodicity-coupling-error.md).
