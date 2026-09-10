# The patch-antenna Q-factor bound, read from the original

**Date:** 2026-09-07
**Ticket:** [#109](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/109) — bears on [#187](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/187); part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104).
**Question:** What does the bound #109 assigns the `PATCH` design family actually say, and does it bear on #187's super-cell question?

[#109](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/109) settled that `physical_bound` is *"a genuinely different function per family — Rozanov for absorbers, Gustafsson & Sjöberg for reflection-phase steering, **Nel/Skrivervik/Gustafsson for patch antennas** — not one formula with a swapped constant."* The absorber's bound has been read first-hand (`docs/rozanov-bound-primary-source.md`). The patch family's had not.

**It has now been read.** Source: Nel, Skrivervik & Gustafsson, *"Q-factor Bounds for Microstrip Patch Antennas"*, IEEE Trans. Antennas Propag., [DOI 10.1109/TAP.2023.3243726](https://doi.org/10.1109/TAP.2023.3243726), 2023; preprint as Lund University TEAT-7275. All quotations verbatim.

---

## Bottom line up front

**The bound is real, it is severe, and it does not bear on #187 — which is itself the finding.**

It bounds **radiation** Q for a *radiating* patch on a **lossless** substrate. An absorber's bandwidth is set by **dissipated** power on a deliberately lossy substrate. Different denominator, different physics. #109's "genuinely different function per family" is not a filing convenience; these two bounds are not interchangeable, and this document is the demonstration.

What it does contribute to #187 is narrower and still useful: it **cannot forbid** a multi-resonance super-cell, because it assumes a single resonance and lists two-resonance widening as future work — and it independently corroborates, from the *antenna* literature, that recognised bandwidth enhancement in patch structures is overwhelmingly **vertical or topological** — not, as an earlier revision of this document claimed, "never" lateral detuning of coplanar elements; that absolute is refuted (§5, item 2) by a real, measured X-band counterexample. The comparative half is what survives and matters: **vertical integration has no ceiling on how many resonators can stack; horizontal integration does.**

---

## 1. What it bounds, precisely

The Q-factor is defined (eq. 3.3) as

> **Q = 2ω · max{W_e, W_m} / P_d**

with `W_e`, `W_m` the stored electric and magnetic energies. The denominator is **not** material dissipation:

> The dissipated power can then be divided into power radiated into free space (P_r) and power lost in the surface wave (P_sw) as **P_d = P_r + P_sw**.

So `P_d` is radiated power plus surface-wave leakage. The appendix is explicit that the MoM impedance matrix assumes **"no ohmic losses"**, and the model is stated as

> an infinite PEC ground plane and an infinite **lossless** dielectric substrate. On top of the substrate is a **PEC patch** confined to a design region Ω

*In plain terms: this counts energy that gets away — as radiation, or leaking sideways through the substrate. It does not count energy turned into heat, because in this model nothing turns into heat.*

**Q is the inverse of fractional bandwidth**, valid *"given a single dominant resonance over the bandwidth."*

---

## 2. The scaling rule — the number the repo cites but has never had

Below the half-wave resonance the bound scales as the **fifth power** (eq. 5.1):

> **Q̃_lb(f) = Q_hw · f⁵_hw / f⁵ = Q_hw · λ⁵_ε / λ⁵_ε,hw**

`Q_hw` is the Q of a simulated half-wavelength resonant patch on the same substrate and design region. The paper's own worked example:

> compute an approximation of lower Q-factor bounds at 2.45 GHz for relative permittivity εr = 4, dimensions ℓx = 20 mm, ℓy = 15.4 mm and h = 1 mm. Then … the half-wavelength resonance frequency is determined as approximately 3.665 GHz … the Q-factor is computed as 95.5 … **Q̃_lb(f) ≈ 95.5(3.665/2.45)⁵ ≈ 715**. This corresponds to a **−10 dB bandwidth of approximately 2.3 MHz**.

2.3 MHz at 2.45 GHz is **0.094 % fractional** (`CALCULATED`).

*In plain terms: shrinking a patch below its natural half-wavelength size costs bandwidth as the fifth power of how far you shrink it. Halve the size and roughly thirty times the bandwidth is gone.*

**Why fifth and not Chu's third:** the conclusion attributes it to the ground plane —

> The low-frequency lower Q-factor bounds scale differently from those of antennas in free space, **due to the ground plane**. Further, this bound is **orders of magnitude tighter than the Chu bound**.

A `(λ_ε/ℓx)³` scaling does exist but corresponds to *"monopole radiation [that] is not desired for patch antennas."*

**A cheaper lever, for contrast.** Width is roughly linear:

> The bounds are observed to scale roughly as ℓx/ℓy (**doubling ℓy reduces Q bounds by a factor 2**)

So widening buys bandwidth proportionally, while shortening costs it to the fifth power.

---

## 3. How much geometry has left to give: ≤ 10 %

Real designs sit *"within a margin of 10 % from the lower Q-factor bounds"* (Table 1, verbatim):

| Patch type | ℓx / mm | ℓy / mm | Q_lb,x | Q_Z′in |
|---|---|---|---|---|
| Half-wavelength | 38.5 | 50 | 45 | 45 |
| Half-wavelength | 38.9 | 30 | 66 | 67 |
| Half-wavelength | 39.4 | 20 | 90 | 91 |
| Slot loaded | 35.2 | 28 | 90 | 94 |
| Slot loaded | 36.7 | 18 | 118 | 121 |
| H-shaped | 25.9 | 20 | 274 | 297 |

Half-wavelength patches are **essentially at the bound** (45 vs 45, 66 vs 67, 90 vs 91). The most miniaturised case is 8 % off. And the bounds *"implicitly account for all possible patch geometries within the design region"* — computed by current optimisation over every admissible current distribution, not over a shortlist of shapes.

**So for a single-resonance patch on a given substrate, shape optimisation has at most ~10 % of Q left.** That is a real, quantified statement about how little headroom geometry holds — *within the bound's assumptions*.

---

## 4. Stated assumptions — the part that decides applicability

Four exclusions, all in the paper's own words:

1. **One resonance.** *"it is also assumed that there is only one dominant resonance over the bandwidth."*
2. **No vertical structure.** *"**shorting pins, stacked patches or miniaturized ground planes** [22, 37, 44] can be used to enhance the bandwidth, **they are not considered here**."*
3. **Lossless everything.** Lossless dielectric, PEC patch, PEC ground, no ohmic losses.
4. **Two-resonance widening is future work.** From the conclusion's own list of extensions: *"A further extension is **using two resonances to widen the bandwidth**."*

One further result worth carrying, because it touches this session's polarization thread:

> it shows that **circular polarization cannot enhance bandwidth** for the patch antennas considered here

And on dual resonance, §6.3 examines *orthogonally* polarised pairs — not co-polarised detuned resonators, which is what a #187 super-cell is.

---

## 5. Why this does not settle #187, and what it does contribute

**It does not settle it.** #187 asks whether laterally detuned coplanar resonators over one spacer buy absorption bandwidth. This bound governs radiation Q with no material loss anywhere. An absorber deliberately puts loss in the substrate (silicone tan δ 0.10) and in the pattern (#128); its bandwidth is a matching question, not a radiation question. Citing this bound against an absorber design would be the same category error as citing Rozanov against a patch antenna.

**Three things it does contribute:**

1. **It cannot forbid a multi-resonance super-cell.** Assumption 1 excludes exactly the case #187 proposes, and assumption 4 files it as unsolved future work. A possible objection — *"the bound already rules this out"* — is removed rather than confirmed.
2. **It corroborates a vertical-over-lateral *preference* from a second literature — not a vertical-only rule, which is a correction from an earlier revision of this document.** Assumption 2 lists what *this paper's own reading list* recognises as bandwidth enhancement: shorting pins, **stacked patches** (a second height — #187's class (b)), and modified ground planes (changing the inductance path). **Lateral detuning of coplanar elements appears nowhere in that reading list.**

   **Correction.** An earlier revision of this document — here and in "Bottom line up front" — stated this as an absolute: recognised bandwidth enhancement is "never lateral detuning of coplanar elements." That is refuted. **arXiv:1704.03032 §4.2 names horizontal supercell integration as a recognised bandwidth-enhancement method, citing three sources**, and **Ozden, Yucedag & Kocer, "Metamaterial based broadband RF absorber at X-band," *AEU – Int. J. Electron. Commun.* 70(8):1062–1070 (2016), DOI [10.1016/j.aeue.2016.05.002](https://doi.org/10.1016/j.aeue.2016.05.002), built and measured a horizontally-integrated design in X-band** — a real, measured counterexample to "never." It was a claim about two reading lists, not about the field.

   **The comparative half survives and is kept, because it is the part that actually matters for #187:** vertical/stacked integration has no structural ceiling on how many resonators can be added — each new one is a new layer, so the count is a fabrication question, not a coupling one. Horizontal/coplanar integration does have a ceiling, because lateral elements compete for aperture space and couple to their neighbours (this document's own #187 concern) in a way stacked layers do not.

   **A caveat to carry alongside the correction:** arXiv:1704.03032 is a review that recycles an earlier review sharing a co-author — one voice appearing twice, not two independent literatures — so its own "never" was already weaker evidence than it read as. `docs/five-paper-absorber-corpus-findings.md` §1's finding of the same revealed *preference* across four absorber groups is unaffected by this correction — it is a preference-in-practice finding, not an existence claim, and stands on its own evidence. See `docs/ozden-broadband-supercell-primary-source.md` (another agent's primary-source read of Ozden et al.) for the full citation trail; not created or edited here.
3. **It prices the miniaturisation penalty** at a fifth power, which any `PATCH`-family candidate in the loop should carry.

---

## 6. Register updates

**Closes:** the `PATCH` family's `physical_bound` was named in #109 but never read. It is now read, with its scaling rule (§2), its tightness (§3) and its validity box (§4) recorded.

**Opens, and worth a ticket:** the loop's `PATCH` family should carry the fifth-power scaling as its bandwidth-feasibility check, in the same way the absorber family carries Rozanov — including that the bound needs a `Q_hw` reference from one half-wave simulation, which is cheap.

**Does not change:** #187 remains open on its mechanism. This document narrows what can be argued about it, and rules out one shortcut.

**Provenance.** Everything quoted is `LITERATURE-SUPPORTED` — this programme measured none of it, and the paper's own results are simulated (FEKO) and MoM-computed. The 0.094 % fractional-bandwidth conversion in §2 is `CALCULATED` here.
