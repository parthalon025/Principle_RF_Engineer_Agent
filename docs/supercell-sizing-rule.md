# A super-cell sizing rule, derived from a coupling error budget

**Date:** 2026-09-04
**Ticket:** [#130](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/130) — serves [#111](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/111), part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104).
**Question:** How large should a block of identical symbols be, given that placing unlike symbols side by side breaks the assumption each symbol was characterised under?

[#131](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/131)'s survey established there is **no convention to inherit** — every block size in the literature is set by beam geometry, control-line count, fabrication tolerance or compute cost, never by an error budget. This document derives one. It is item 3 on the research agenda in [`RUNNING-LISTS.md`](./RUNNING-LISTS.md) §5.

---

## Bottom line up front

**The rule is not "make the block bigger until the error is acceptable." Bigger blocks do reduce the coupling error — but for a backscatter-reduction objective they destroy the thing the design exists to do, and they do it faster than they fix the error.**

The two constraints move in opposite directions and pin the block size to a window that is usually **exactly one value, N = 2**, and is often **empty**:

| Element family | Pitch | Δφ_max | N_min (coupling) | N_max (scattering) | Window |
|---|---|---|---|---|---|
| **Fixed-edge, interior-tuned** | 0.5 λ | 12° | 2 | 2 | **{2}** |
| Minkowski fractal | 0.5 λ | 21° | 2 | 2 | **{2}** |
| Variable-size square patch | 0.5 λ | 25° | 3 | 2 | **empty** |
| **Fixed-edge, interior-tuned** | 0.4 λ | 20° | 2 | 3 | **{2, 3}** |
| Minkowski fractal | 0.4 λ | 45° | 7 | 3 | **empty** |
| Variable-size square patch | 0.4 λ | 85° | 15 | 3 | **empty** |

**Three of six cases have no feasible block size at all** — and one of the three is the variable-size square patch, the workhorse of the entire reflectarray field.

So the practical form of the rule is a **gate on the alphabet, not a sizing calculation**:

> **A one-bit coding metasurface is feasible only if the alphabet's worst-case unlike-neighbour phase error, at the design pitch, is at or below the phase budget on its own — because N = 2 is usually the only block size the scattering requirement allows, and at N = 2 every cell is a boundary cell, so the block earns no averaging at all.**

That makes the interior-tuning criterion recorded on #130 a **hard admission gate** rather than a preference. It is also why this rule could not be borrowed from the beam-forming literature: there, large blocks are free.

---

## 1. The two constraints, in plain English

**A metamaterial skin is a grid of small printed shapes.** To find out what one shape does, you simulate a single copy and tell the solver to pretend it repeats forever — "local periodicity." The answer you get is for a surface made entirely of *that* shape.

Real coded designs mix shapes. A shape sitting next to a different shape behaves differently from the same shape sitting in a field of its own kind, because at these spacings the shapes are inside each other's near field. That difference is the **coupling error**.

**Constraint 1 — the coupling error pushes block size up.** Group identical symbols into N × N blocks and the cells in the middle of a block see only their own kind, so their characterised response is right. Only the cells on the block's edge have foreign neighbours. Bigger block, smaller fraction of edge cells, smaller average error.

**Constraint 2 — the scattering requirement pushes block size down.** The point of a chessboard of two symbol types is that the two reflect out of phase, so the returned energy cancels straight back at the radar and reappears as lobes off to the side. *How far* off to the side is set by how coarse the chessboard is: **coarse pattern, shallow angle.** Make the blocks big enough and the "redirected" energy comes back within a few degrees of where it started, which is not redirection at all.

The first constraint sets a floor. The second sets a ceiling. The design is only possible if the floor is below the ceiling.

---

## 2. The floor: how error falls with block size

In an N × N block of identical symbols, the cells that touch a neighbouring block are the outer ring. There are N² cells in total and (N−2)² strictly interior ones, so the **boundary fraction** is

```
f(N) = (N² − (N−2)²) / N²  =  (4N − 4) / N²
```

| N | 2 | 3 | 4 | 5 | 6 | 8 | 10 | 15 | 20 |
|---|---|---|---|---|---|---|---|---|---|
| f(N) | 1.000 | 0.889 | 0.750 | 0.640 | 0.556 | 0.438 | 0.360 | 0.249 | 0.190 |

Bound the block's average phase error by assuming every boundary cell carries the full worst-case error and every interior cell carries none:

```
Δφ_block  ≤  Δφ_max · f(N)
```

`Δφ_max` is a **property of the alphabet at a given pitch**, not of any one letter. It is measured by Costanzo's protocol: simulate the element with all eight neighbours identical, then again with its two E-plane neighbours swapped for the alphabet's largest and smallest members, and take the largest gap between the two phase curves.

**This decays as 1/N — slowly.** Halving the error costs a doubling of the block in both directions. That is the crux: the floor moves reluctantly, while the ceiling (below) moves fast.

`N_min` is the smallest N satisfying `Δφ_max · f(N) ≤ Δφ_budget`.

**Note what happens at N = 2:** f(2) = 1.0. Every cell in a 2 × 2 block touches a foreign block, so the block averages nothing and `Δφ_block = Δφ_max` exactly. Since N = 2 turns out to be the only size the ceiling usually permits, **the whole rule collapses to a test on the alphabet itself.**

### The budget

**±22.5°**, adopted from Costanzo, Venneri, Borgia & Di Massa (*IJAP* 2019), who use it as the acceptable phase-error margin. It is the half-step of a 3-bit, 8-level phase quantisation — the point at which a phase error is big enough to move a symbol into the neighbouring quantisation bin. Provenance **LITERATURE-SUPPORTED**; it is a convention, not a physical limit, and a requirement may override it.

---

## 3. The ceiling: how block size sets the scattering angle

A chessboard of N × N blocks alternating between the two symbols has a pattern period of **2 N p** in each direction, where `p` is the cell pitch. Writing the pattern as `sign(cos(πx/a)·cos(πy/a))` with block side `a = N·p`, its dominant spatial-frequency content sits at `(k_x, k_y) = (±π/a, ±π/a)`, so the transverse wavenumber is `|k_t| = √2 π/a` and the scattered lobes appear along the diagonals at

```
sin θ  =  |k_t| / k₀  =  λ / (a√2)  =  λ / (N · p · √2)
```

At the two pitches of interest:

| N | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| **p = 0.5 λ** | evanescent | **45.0°** | 28.1° | 20.7° | 16.4° | 13.6° |
| **p = 0.4 λ** | evanescent | **62.1°** | 36.1° | 26.2° | 20.7° | 17.1° |

Two readings:

**N = 1 gives no propagating lobe at all.** With `sin θ > 1` there is no diffraction order to carry the energy away. A cell-by-cell checkerboard therefore does not redirect anything — which is why the literature does not build them, and it supplies an independent floor of **N ≥ 2** that happens to coincide with the coupling floor.

**The angle collapses fast.** Going from N = 2 to N = 6 at half-wavelength pitch takes the lobe from 45° to 13.6°. Thirteen degrees off broadside is, for most monostatic measurements, still the main lobe.

`N_max` is the largest N with `θ(N) ≥ θ_min`. Taking **θ_min = 30°** as a default — a reasonable "outside the specular cone" threshold, and a per-requirement input rather than a constant — gives **N_max = 2 at 0.5 λ pitch and N_max = 3 at 0.4 λ.**

---

## 4. The window, and what falls out of it

Combining §2 and §3 gives the table in the summary. Three things are worth stating plainly.

**The square patch is out.** The variable-size square patch fails at both pitches. Its `Δφ_max` of 25° (at 0.5 λ) already exceeds the budget on its own, and no block size rescues it because the only block sizes allowed are the ones that average nothing. At 0.4 λ pitch it needs N = 15 and is allowed N = 3 — a factor of five apart, in a quantity that only improves as 1/N.

**Bigger blocks are not the escape hatch,** which is the intuition this derivation exists to kill. The reflex when told "unlike neighbours cause error" is to group symbols into larger patches. That reflex is right for beam-forming, where the block size is set by the phase ramp and a large aperture is wanted anyway. It is wrong here, because the coding pattern's *coarseness* is the mechanism, and coarsening it past a few cells returns the energy to where it came from.

**The fix is the alphabet, not the layout.** Interior-tuned elements — shapes whose tuning parameter changes the inside of the shape while leaving its outline fixed, so the gap to the neighbour never moves — are the only family with a non-empty window at either pitch. That is the criterion already recorded on #130 from a different direction, and this derivation turns it from a preference into a gate.

### When the window is empty

In order of preference:

1. **Change the alphabet** to an interior-tuned family. This is the real answer and the only one that does not cost performance.
2. **Widen the pitch.** Coupling falls sharply as cells separate — but pitch above ~0.5 λ risks grating lobes, so this buys little.
3. **Relax `θ_min`**, if the requirement genuinely permits a shallower scattering angle. A per-requirement input, so this is the customer's call, not the loop's.
4. **Abandon the one-bit chessboard** for a multi-level phase gradient, which has a different geometry — the super-period is set by the phase ramp, not by the block, so the ceiling formula in §3 does not apply. Note this trades into the regime where Costanzo measured a **0.75 dB gain loss and up to 6.6 dB of sidelobe violation** for the square patch, so it does not evade the coupling problem, only relocates it.

---

## 5. Scope — where this rule does and does not apply

**Applies to:** one-bit (and by extension few-bit) **coding metasurfaces** whose objective is redirecting scattered energy — the patent's Example 7, and Tier B families generally.

**Does not apply to the broadband super-cell.** Putting several slightly-detuned resonators in one block to widen an absorber's bandwidth (the [#110](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/110)/[#129](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/129) idea) uses a block for a completely different reason: it is not steering anything, so **the §3 ceiling does not exist and blocks may be as large as is useful.** Only the §2 floor applies there. This distinction matters — the same word, "super-cell", covers two constructions with opposite sizing pressures.

**Does not apply to Tier A uniform surfaces** (Example 3, the anchor), which repeat one cell and have no unlike neighbours to couple to.

---

## 6. Provenance and honest limits

| Claim | Provenance |
|---|---|
| Δφ_max values (12° / 21° / 25° at 0.5 λ; 20° / 45° / 85° at 0.4 λ) | **LITERATURE-SUPPORTED** — Costanzo, Venneri & Di Massa, *IJAP* 2019, [10.1155/2019/4890710](https://doi.org/10.1155/2019/4890710), Table 3 and Figs. 5–7. Method-of-moments, so `SIMULATED` at source |
| ±22.5° phase budget | **LITERATURE-SUPPORTED** — a convention, overridable per requirement |
| Boundary fraction f(N) = (4N−4)/N² | **CALCULATED** — counting |
| Chessboard diffraction angle | **CALCULATED** — Fourier content of the coding pattern; standard result |
| The composition `Δφ_block ≤ Δφ_max · f(N)` | **INFERRED** — our model, see limits below |
| The feasibility windows | **CALCULATED** from the above |

**Four limits, stated rather than buried:**

- **The error model is binary per cell.** It assumes a boundary cell carries the full worst-case error and an interior cell carries none. Coupling is not that sharp — An et al. ([arXiv:2102.01761](https://arxiv.org/abs/2102.01761)) show accounting for one ring of neighbours captures most of the error but four rings still matter, so this **understates** the error for blocks of N ≥ 4. It is exact at N = 2, where all cells are boundary cells, and N = 2 is where every feasible answer lands.
- **Δφ_max is a worst case by construction.** Costanzo deliberately swaps in the alphabet's two extreme members along the E-plane, the strongest-coupling direction. A typical design does not place extremes adjacent, so real errors will be lower. The rule is therefore conservative — it may reject an alphabet that would have worked.
- **The scattering formula assumes an infinite periodic chessboard.** A finite coupon has broadened lobes and the angle is less sharply defined. On a 6 λ coupon this is not a small correction.
- **Nothing here is measured.** Every input is simulated or calculated. Confirming Δφ_max for our own alphabet, on our own machine, is [#132](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/132)'s work and needs the bench access [#133](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/133) does not yet have.

**What would falsify it:** an alphabet with `Δφ_max` above the budget that nonetheless produces a working coded surface at N = 2. That would mean the worst-case protocol is too pessimistic to gate on, and the gate should move to a typical-case figure instead.

---

## 7. Sources

1. S. Costanzo, F. Venneri, G. Di Massa, "Modified Minkowski Fractal Unit Cell for Reflectarrays with Low Sensitivity to Mutual Coupling Effects", *IJAP* 2019, Art. 4890710. [10.1155/2019/4890710](https://doi.org/10.1155/2019/4890710). Retrieved in full. Table 3 and Figs. 5–7 supply every Δφ_max above.
2. S. Costanzo, F. Venneri, A. Borgia, G. Di Massa, *IJAP* 2019, Art. 9479010. Retrieved. Source of the ±22.5° margin and of the E-plane coupling anisotropy.
3. S. An, B. Zheng, M. Y. Shalaginov *et al.*, "Deep Convolutional Neural Networks to Predict Mutual Coupling Effects in Metasurfaces", [arXiv:2102.01761](https://arxiv.org/abs/2102.01761). The only published error-versus-neighbour-count curve; bounds the binary-cell approximation.
4. M. Zhou *et al.*, "Analysis of printed reflectarrays using extended local periodicity", *EuCAP* 2011. Establishes that the coupling error lives in the scattered field rather than the main beam — which is why it lands on this project's objective.

Full coupling background: [`local-periodicity-coupling-error.md`](./local-periodicity-coupling-error.md).
