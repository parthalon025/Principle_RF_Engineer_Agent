# Does element self-inductance rescue the detuned super-cell? A bench run for #187

**Date:** 2026-09-07
**Ticket:** [#187](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/187) — part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104).
**Question:** `docs/five-paper-absorber-corpus-findings.md` §1.1 recommended re-running the super-cell bench with ring/loop letters carrying a per-element series self-inductance, on the grounds that #187's *"one spacer = one inductance"* is sound for patches but not obviously for rings — and Example 3's element is a ring.

**Answer: the ring hypothesis fails. Element self-inductance does not rescue lateral detuning — it narrows the band and deepens the detuning penalty.** #187's conclusion survives and now covers both element classes.

---

## 1. The bench, and why it is the right one

The circuit model is ported from `geometry/prototype_lossy_cell_fit.html` — Luukkonen grid capacitance inside Costa *et al.*'s absorber stack ([arXiv:1211.1902](https://arxiv.org/abs/1211.1902)), the model #111 adopted. Reading that file confirmed §1.1's diagnosis directly:

```js
gridZ = R_ohmic + R_D + 1/(jωC)     // capacitance only — no inductance term
slabZ = shorted lossy line           // the ONE shared inductance
```

Every letter contributes only a capacitance; **all** inductance comes from the shared grounded slab. *"One spacer = one inductance"* was not a finding of that model — it was an assumption built into its topology.

The one term added here is a per-element series inductance, using the **exact Babinet dual** of the capacitance formula already in the file, so the extension stays inside the adopted model family:

```
C = ε₀ (2p/π) ln(1/sin(πg/2p))      [patches, capacitive]
L = μ₀ (p/2π) ln(1/sin(πw/2p))      [wires/loops, inductive]
```

Setting `L = 0` recovers the patch model exactly, so both cases run the same code path.

**Letters combine as area-weighted admittances in parallel, with the slab admittance added once, not per letter.** That single shared `Y_d` is the precise content of the shared-spacer claim, and making it explicit is the point of the bench.

Script: `scratchpad/bench/supercell.py` (throwaway, not committed).

---

## 2. The baseline reproduces

| | Band at ≥90 % | Fractional |
|---|---|---|
| #187 as reported (1 cell, 1.5 mm silicone) | 9.03–11.27 GHz | 22.1 % |
| **This bench** (p = 9.0 mm, g = 1.3 mm, R = 50 Ω) | **9.03–11.25 GHz** | **21.9 %** |

`CALCULATED`. The ported model behaves like the one that produced #187's numbers, so comparisons made with it carry weight.

---

## 3. Detuning never pays, at any spread

Patch letters, resonance detuned by ±spread (each letter's `C` scaled by `1/k²` so the resonance offset is exact and identical whatever `L` is):

| Spread | 2 cells | 3 cells | 4 cells |
|---|---|---|---|
| 0 (baseline) | 21.92 | 21.92 | 21.92 |
| 2 % | 21.86 | 21.89 | 21.89 |
| 5 % | 21.62 | 21.73 | 21.75 |
| 10 % | 20.74 | 21.15 | 21.29 |
| 15 % | 18.74 | 20.00 | 20.37 |
| 25 % | 0.00 | 13.55 | 15.81 |
| 40 % | 0.00 | 0.00 | 0.00 |

**Monotonically harmful.** There is no spread at which lateral detuning buys bandwidth in this model.

---

## 4. Element inductance makes it worse, not better

Sweeping the per-element series inductance at fixed geometry:

| L (pH/sq) | 1 cell | 2 detuned | 3 detuned | 4 detuned | best gain |
|---|---|---|---|---|---|
| 0 | 21.92 | 18.74 | 20.00 | 20.37 | −1.54 |
| 50 | 20.31 | 16.26 | 17.89 | 18.39 | −1.92 |
| 100 | 18.71 | 13.42 | 15.61 | 16.24 | −2.46 |
| 200 | 15.18 | 4.55 | 9.92 | 11.11 | −4.07 |
| 400 | 5.14 | 0.00 | 0.00 | 0.00 | −5.14 |
| 800+ | 0.00 | 0.00 | 0.00 | 0.00 | — |

Two monotone trends, both against the hypothesis: **baseline bandwidth falls as L rises**, and **the detuning penalty deepens**.

*In plain terms: giving each element its own loop inductance makes it a sharper, higher-Q resonator. Sharper resonators are narrower, and a row of slightly different sharp resonators is worse than one, not better.*

**And a realistic ring is far outside the working regime.** A 0.5 mm trace on a 9.0 mm period gives **4392 pH/sq** — an order of magnitude past where the design stops meeting 90 % at all. Re-tuning to restore resonance (period 9.0 → 4.3 mm) gives a working ring design, and it is *worse* on both counts: **13.4 % baseline against the patch's 21.9 %**, with detuning still negative.

---

## 5. The sign discrepancy with #187, reconciled

#187 reported detuning **gaining** 0.7 pp (22.1 → 22.8 %). §3 above shows it **losing**. Both are right, and the reconciliation is the useful part.

Re-tuning the geometry at each sheet resistance so the design stays at ~10 GHz:

| R (Ω) | p (mm) | g (mm) | f₀ (GHz) | 1 cell | 4 detuned | gain |
|---|---|---|---|---|---|---|
| 25 | 6.5 | 0.65 | 9.98 | 19.29 % | 20.12 % | **+0.83** |
| 50 | 9.0 | 1.30 | 9.96 | 21.89 % | 20.38 % | **−1.51** |

**The gain's sign depends on the operating point.** #187's +0.7 pp is reproducible at R ≈ 25 Ω; at R = 50 Ω the same experiment loses 1.5 pp. Either way the magnitude is ≲1.5 pp — nowhere near a bandwidth mechanism, which is #187's substantive conclusion and is unaffected.

---

## 6. A methodological trap this run walked into

An earlier pass swept R at fixed geometry and produced an apparently striking result: **39.18 % bandwidth at R = 300 Ω**, against 21.9 % at R = 50 Ω, suggesting loss is a large bandwidth lever.

**It is an artefact, and it was nearly reported as a finding.** Checking the curves showed the absorption peak walking across the spectrum as R rises:

| R (Ω) | 50 | 100 | 150 | 200 | 300 |
|---|---|---|---|---|---|
| peak absorption | 0.9564 | 0.8472 | 0.8506 | 0.9080 | 0.9788 |
| **at (GHz)** | **9.96** | **12.19** | **18.58** | **24.05** | **27.27** |

**R is not a loss knob at fixed band — it retunes the structure.** The "39 %" belongs to a different design operating at 27 GHz. Any comparison across R must re-tune the geometry at each point (§5), and the non-monotonic zeros at R = 100–150 Ω are genuine misses where the peak never reaches 0.90, not a solver failure.

---

## 7. What this settles, and what it does not

**Settles:** §1.1's ring challenge, negatively. Element self-inductance does not make lateral detuning pay; it makes both the baseline and the detuning worse. #187's finding extends from patch letters to ring letters.

**Does not settle:** the mechanism claim in full. This bench shares the original's blind spot — **no inter-cell coupling**, which is #187's own class (d) and the one term the model omits by construction. A super-cell whose letters couple strongly to unlike neighbours is still untested, and `docs/local-periodicity-coupling-error.md` records that coupling as real (+6.9 % unlike-neighbour pulling in a measured control, per #138).

**Also not settled:** whether loss is the large bandwidth lever `five-paper-absorber-corpus-findings.md` §1 infers from the literature. §6 shows the naive test is confounded, and the re-tuned test in §5 only converged at two of six operating points — at higher R the search could not restore a 10 GHz resonance within the geometry range swept, so those rows are absent rather than negative.

**Provenance.** All figures `CALCULATED` in this session from the ported model. Nothing here is `MEASURED`, and the model is a scattering surrogate — per #111, valid for predicting reflection, never for extracting a material's own properties.
