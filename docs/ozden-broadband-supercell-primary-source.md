# Ozden's broadband X-band super-cell, read first-hand — #187's experiment exists

**Date:** 2026-09-10
**Ticket:** [#187](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/187) — part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104). Bears on [#128](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/128), [#110](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/110), [ADR-0040](./adr/0040-design-is-selection-and-placement-from-a-quantised-alphabet.md), [ADR-0041](./adr/0041-absorber-score-is-worst-in-band-minimax-with-fsv-comparison.md).
**Question:** Does a broadband super-cell buy bandwidth, or does the shared spacer forbid it? And has anyone ever actually run that experiment?

**Source:** K. Ozden, O. M. Yucedag & H. Kocer, *"Metamaterial based broadband RF
absorber at X-band"*, **Int. J. Electron. Commun. (AEÜ) 70 (2016) 1062–1070**,
doi [10.1016/j.aeue.2016.05.002](https://doi.org/10.1016/j.aeue.2016.05.002).
Received 14 December 2015, accepted 2 May 2016.

---

## Bottom line up front

**Somebody ran #187's experiment ten years ago, and this programme's literature
survey said nobody had.** Ozden *et al.* built laterally detuned, differently
sized coplanar resonators on **one** shared 0.75 mm dielectric over **one**
continuous copper ground plane, with no lumped resistors and no resistive film,
swept the number of letters from 12 to 16, fabricated both, and measured both on
a VNA. That is #187's geometry, #187's variable and #187's control.

`docs/five-paper-absorber-corpus-findings.md` §1 ruled at `CONFIDENCE: HIGH` that
*"the published record does not contain the experiment #187 asks for."* **That
ruling is wrong**, and §11 below records why: its five papers were 380–2300 nm,
10.90–22.91 µm, a review, 400–3500 nm and 500–2000 nm — **not one microwave
paper** — so a high-confidence claim about "the published record" for an X-band
question came out of a corpus that never searched the band. That correction has
landed on the claim itself (ADR-0024).

**What the paper says, and it is two different answers to two different
questions:**

| | Answer | Where |
|---|---|---|
| Do more letters widen the band? | **No.** *"increasing the number of unit cell in super cell does not change frequency bandwidth"* — and the 12-letter tile measured **wider** than the 16-letter tile (2.73 vs 2.55 GHz at 80 %) | §4, measured |
| Do more letters raise the worst-in-band absorption? | **Yes, strongly.** *"this increment improves the absorption level."* Over a matched 2.44 GHz window the simulated minimax goes **0.27 (1 letter) → 0.69 (12) → 0.79 (16)** | §5, figure read |
| Is that a contradiction? | **No — width and depth are different quantities.** #187's bench measured width and got the same flat answer Ozden got | §6 |
| Does it transfer to this programme? | **Probably not, and now for a stated reason.** Ozden's conductor is loss-free copper (RF surface resistance **26.1 mΩ/sq**); this programme's letters are **25–50 Ω/sq**, roughly **1000–1900× more resistive**, and already loss-broadened to 22.1 % as a single cell. Detuning fills a hole between two sharp peaks; it cannot widen a curve that has no hole | §6 |

*In plain terms: their absorber is built from two very sharp, very efficient
resonances with a deep dip between them, and scattering a range of slightly
different sizes across the sheet fills that dip in. Ours is built from lossy,
already-blurry resonances with no dip to fill — so there is nothing for the same
trick to work on. Both results can be true at once, and this programme lives in
the second world.*

**Rozanov (§7):** Ozden's measured ≥90 % result extracts **46.1 %** of its
thickness budget on 0.75 mm; this programme's #187 bench extracts **25.7 %** on
1.5 mm. Per [ADR-0047](./adr/0047-the-loop-advises-against-a-physical-bound-never-gates-on-it.md)
that **advises, never gates** — but it says the bench design has roughly 1.8× of
headroom against the same physics, so a null result there is not the bound
talking.

---

## 0. How it was retrieved, and what that closes

`docs/RUNNING-LISTS.md` §1 carries a **ScienceDirect / HTTP 403** row. This
paper sat behind it, with the note that the full text was needed to check the
actual cell layout.

**The route that worked, first try:** a plain `curl` with a desktop user-agent
against an open mirror,
`https://iranarze.ir/wp-content/uploads/2016/10/E142.pdf` — HTTP 200,
3,841,143 bytes, `application/pdf`, 9 pages, complete typeset article including
the reference list. No proxy, no headless browser, no publisher login. Text was
extracted with `pymupdf`; every quote below was then **re-read visually from a
4× render of the page region it sits in**, because the PDF's text layer maps
Greek and symbol glyphs onto Latin ones (λ renders as `k`, ε as `e`, µ as `l`,
δ as `d`, and `×` and `°` drop entirely). Quotes below carry the restored
symbols; the restoration is from the render, not a guess.

This adds a row to the "routes around a block that do work" list already in
`RUNNING-LISTS.md` §1: **an open mirror of a paywalled PDF, found by searching
for the filename rather than the title.** It is the same class of move as "PMC
mirrors MDPI".

---

## 1. The geometry — this is #187's experiment, verbatim

Everything in this section is `LITERATURE-SUPPORTED`, quoted from the paper and
confirmed against a 4× page render.

**One ground plane.** From §2, p. 1062:

> "Bottom layer is metallic continuous ground plane."

**One spacer, one thickness, stated with its loss.** Same paragraph:

> "These metallic layers are selected as copper which has 17 µm thickness and
> its frequency independent conductivity (σ) is 5.8 × 10⁷ S/m. The dielectric
> material is epoxy glass cloth laminate (FR4) which has 0.75 mm thickness and
> its relative dielectric permittivity (ε_r) is 3.6 and the loss tangent (tan δ)
> is 0.03. The simulated metamaterial has the dimensions, in millimeters, of:
> L₁ = 6.67, L₂ = 5.33, L₃ = 3.25, w = 0.50, g = 0.33 and d = 0.54."

**One layer — the paper says so itself**, in its Introduction:

> "The broadband metamaterial absorber can be obtained using a single-layer
> microstrip technology, which has the advantages of simple structure and easy
> fabrication."

**The detuning is purely lateral.** From §2.2, and this is the decisive
sentence:

> "Explicitly, by multiplying the dimensions of the original unit cell along the
> x- and y-axis by a scaling factor s_i, the center absorption frequency can be
> downshifted (s_i > 1) or upshifted (s_i < 1), whereas the absorption curve
> retains its initial shape and fractional bandwidth. **No scaling is applied
> along the z-direction.**"

**No lumped resistors, no resistive film.** This is an *absence* read against a
complete materials specification, and is stated as such: the paper names exactly
two materials — copper (17 µm, σ = 5.8 × 10⁷ S/m) top and bottom, and FR4
(0.75 mm, ε_r 3.6, tan δ 0.03) between — and never mentions a resistor, a
resistive sheet, a lossy filler or a second dielectric anywhere in the design,
fabrication or measurement sections. Its Introduction explicitly positions the
work *against* the lumped route: *"methods involving the use of lumped elements
can also widen the working band for microwave frequencies [25]. However, using
lumped elements is not feasible, especially in the THz, IR or optical
frequencies."* The only loss channels available are FR4's tan δ = 0.03 and a
copper conductor loss that §6 shows is negligible.

> **So: laterally detuned coplanar cells, one shared spacer, one continuous
> ground plane, no added loss material, N swept, fabricated and measured against
> a control. That is precisely the experiment `five-paper-absorber-corpus-findings.md`
> §1 declared absent from the literature.**

### 1.1 The letters, and how far apart they are tuned

Figure 5 prints the sixteen scaling factors as numeric labels on the plot, and
its two insets name which letter sits in which cell of each tile. Read from a 3×
enlargement — `INFERRED` (read off a drawing), though these are *printed
numerals*, not values interpolated against an axis, so the reading risk is
misreading a digit rather than mis-scaling a curve:

| | s₁ | s₂ | s₃ | s₄ | s₅ | s₆ | s₇ | s₈ | s₉ | s₁₀ | s₁₁ | s₁₂ | s₁₃ | s₁₄ | s₁₅ | s₁₆ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| value | 1.050 | 1.037 | 1.025 | 1.012 | 1.000 | 0.990 | 0.987 | 0.980 | 0.975 | 0.970 | 0.961 | 0.960 | 0.950 | 0.937 | 0.925 | 0.912 |

- **KOH12** (3 rows × 4): `S15 S10 S2 S9` / `S14 S8 S3 S7` / `S13 S6 S4 S5`.
  Twelve letters; s spans 0.925–1.037, a **12.1 % spread** in resonant frequency.
- **KOH16** (4 rows × 4): `S12 S4 S16 S11` / `S10 S2 S15 S9` / `S8 S3 S14 S7` /
  `S6 S1 S13 S5`. All sixteen; s spans 0.912–1.050, a **15.1 % spread**.

Two things fall out of that table, and both matter to #187.

**First, the placement is deliberately shuffled, not sorted.** KOH12's top row
runs S15, S10, S2, S9 — rank positions 15, 10, 2, 9 out of 16, adjacent. This is
the concrete form of the paper's own sentence in §2.2:

> "Considering the coupling effects of unit cells, the location of the unit cell
> is also optimized in the super cell to improve the absorption bandwidth of
> metamaterial absorber."

**Lateral *placement* is a design variable here, separate from lateral
*scaling*.** `docs/supercell-ring-inductance-bench.md` §7 records that the
repo's own bench "shares the original's blind spot — **no inter-cell
coupling**". Ozden not only models that coupling, he optimises against it. This
is the exact term map #104 line 108 says all three of the repo's own checks omit
by construction, and here is a published design that treats it as the main
lever.

**Second, the wider spread lost.** KOH16 has *more* letters and a *wider*
detuning spread (15.1 % vs 12.1 %) and measured a **narrower** 80 % band
(2.55 vs 2.73 GHz). Within this one paper, more detuning bought less width.

### 1.2 The letter is not a single resonator — an honest caveat on the whole result

The element is two concentric rings: *"The inner ring is composed of ELC
resonator connected by the inductive wire parallel to the splits [11]. The outer
ring is also made up of split ring resonator (SRR) with oppositely oriented
splits."* One cell therefore already produces **two** resonances, at 9.10 and
10.53 GHz (§3).

So Ozden's broadband result rests on **three** stacked mechanisms — a
dual-resonance element, lateral size detuning, and coupling-optimised placement
— and the paper never separates their contributions. Anyone citing this as
evidence for lateral detuning alone is over-reading it. It is the *only*
published instance of #187's geometry found so far; it is not a clean
single-variable study of it.

### 1.3 The super-cell is nearly a wavelength across — which is the paper's own explanation

`CALCULATED` from §1.1's scaling factors and L₁ = 6.67 mm, so `INFERRED`
upstream of the scale factors:

| Tile | Approx. super-cell footprint | At λ₀ = 29.6–29.8 mm |
|---|---|---|
| KOH12 (12 letters) | ~26.4 × 20.5 mm | **0.89 λ × 0.69 λ** |
| KOH16 (16 letters) | ~26.6 × 27.5 mm | **0.90 λ × 0.93 λ** |

That is the arithmetic behind the paper's own stated mechanism for the null
result (§4): *"due to super cell size which is electrically comparable with
working wavelength."* KOH16's tile is the larger of the two in the direction
that grew, which is a physically coherent reason its measured band came out
narrower than KOH12's rather than wider.

*In plain terms: once the repeating pattern is as big as the wave itself, the
sheet stops behaving like a smooth surface and starts behaving like a grating —
it begins throwing energy sideways instead of just soaking it up. Adding more
different letters makes the repeat bigger, so past a point every letter you add
costs you something.*

**This is a real, quantified ceiling on the super-cell idea, and it is
independent of the loss regime argument in §6.** ADR-0040's alphabet
composition inherits it: a tile is bounded not by how many letters you own but
by how large the tile may be before it diffracts. `CALCULATED`; the diffraction
threshold itself is not computed here.

---

## 2. What was measured, and what "measured" means here

**Setup**, §2.3, verbatim: two planar coupons, *"9.6 cm × 9.6 cm (KOH12) and
12.5 cm × 12.5 cm (KOH16) supercell prototypes have been fabricated through
printed circuit board (PCB) technique on a FR4 substrate"*; a *"vector network
analyzer (Net Rohde & Schwarz ZVL, 9 KHz – 13.6 GHz)"* and *"a pair of
double-ridged waveguide horn antennas (HF907 800 MHz – 18 GHz)"*; horns 45 cm
apart, sample 90 cm away; the metallic back face measured first as the
reflection reference.

**Results**, §3, verbatim and complete:

> "KOH12 operates in the X-band and yields absorption rates greater than 80 % in
> the frequency range from 8.71 GHz to 11.44 GHz. KOH16 operates in the X-band
> as well and yields absorption rates greater than 80 % and 90 % in the
> frequency range from 8.86 GHz to 11.41 GHz and from 9.09 GHz to 11.08 GHz,
> respectively. The measured absorption bandwidths are 2.73 GHz for KOH12 and
> 2.55 for KOH16 at 80 % absorption level."

Restated with the fractional bandwidths this repo scores on (`CALCULATED`):

| Tile | Floor | Band | Width | Fractional | Centre |
|---|---|---|---|---|---|
| KOH12 | ≥80 % | 8.71–11.44 GHz | 2.73 GHz | **27.1 %** | 10.075 GHz |
| KOH16 | ≥80 % | 8.86–11.41 GHz | 2.55 GHz | **25.2 %** | 10.135 GHz |
| KOH16 | ≥90 % | 9.09–11.08 GHz | 1.99 GHz | **19.7 %** | 10.085 GHz |

**Provenance.** These are *the authors'* measurements on *their* coupons. In
this programme's ladder they enter as `LITERATURE-SUPPORTED`, **not**
`MEASURED` — `MEASURED` is reserved for this programme's own bench, of which
there is none (CLAUDE.md: everything here is capped at `SIMULATED` until there
is bench access). Nothing in this document is `MEASURED`.

**Distinctions the house rules require, applied here.** These are
**absorptivity** figures, A(f) = 1 − |S₁₁|² with |S₂₁|² taken as zero behind the
continuous ground plane — *not* return loss and *not* shielding effectiveness.
The paper states the identity explicitly: *"T(f) is zero due to the presence of
the continuous copper ground plane. Thus, the total absorption is calculated
only by considering the reflection coefficient via relation A(f) = 1 − R(f)."*
80 % absorptivity is −6.99 dB reflectivity; 90 % is −10.00 dB. All figures are
X-band, 7–13 GHz swept.

---

## 3. The two coupling sentences

Quoted in full because map [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104)
line 108 records inter-cell coupling as the one mechanism all three of this
repo's own #187 checks omit by construction.

From §2.2, on design:

> "Considering the coupling effects of unit cells, the location of the unit cell
> is also optimized in the super cell to improve the absorption bandwidth of
> metamaterial absorber."

From §2.2, on why the 16-letter tile came out smoother:

> "This improved absorption bandwidth of KOH16 is mainly due to the
> electromagnetic field coupling between the neighbor unit cells."

**Note the internal tension**, and it is worth carrying: this second sentence
says KOH16 has *"improved absorption bandwidth"*, while §3's measurement says
KOH16's 80 % bandwidth is 0.18 GHz **narrower** than KOH12's. The sentence sits
in the simulation section and its own preceding clause is about *level*
(*"possible to get smoother absorption level around 90 %"*), so the most likely
reading is loose wording for "improved absorption". It is recorded rather than
smoothed over.

---

## 4. The N-sweep, verbatim — the case *against* detuning

Both statements are in §3, both attributed to the **measurements**, and they say
the same thing twice:

> "The measurement results show that increasing the number of unit cell in super
> cell does not change frequency bandwidth. On the other hand, this increment
> improves the absorption level."

> "Despite increasing the number of unit cells in a super cell, bandwidth of the
> absorber does not increase due to super cell size which is electrically
> comparable with working wavelength."

And the numbers are worse than "does not change": **the 12-letter tile beat the
16-letter tile on band, 2.73 GHz against 2.55 GHz at the 80 % floor.** More
letters, wider detuning spread, less measured bandwidth.

**This is a published, fabricated, measured N-sweep on #187's exact geometry,
and it comes out flat-to-negative on width.** Anyone using this paper to argue
that a broadband super-cell buys bandwidth is arguing against its own headline
result.

---

## 5. The figure read — the case *for* detuning, and it is about depth

Everything in this section is `INFERRED`: pixel-read from the published figures
at their embedded resolution (1418 px wide), calibrated against each panel's own
printed gridlines. It is a drawing read, not data.

**Two calibration checks, both passed**, which is why this read is recorded at
all rather than discarded:

1. **Against the paper's own stated numbers.** Fig. 1(b)'s two absorption peaks
   read **0.970 at 9.10 GHz** and **0.979 at 10.50 GHz**; the text states
   *"97.95 % and 98.40 %"* at *"9.10 GHz and 10.53 GHz"*. Within ~1 percentage
   point and 0.03 GHz.
2. **Against a second, independent figure of the same curves.** The simulated
   KOH12 and KOH16 traces appear twice — in Fig. 6 and again as the "Sim." curve
   in Fig. 9(a) and 9(b). Read separately, the two renderings agree on the
   continuous ≥80 % run to **0.01 GHz** in both cases. A pixel-read error would
   not reproduce across two differently drawn figures.
3. **Against the paper's own measured width.** The measured ("Exp.") KOH12 trace
   in Fig. 9(a) holds ≥0.80 continuously over a span reading **2.73 GHz** — the
   paper's stated figure, to two decimal places, with a uniform +0.02 GHz offset
   on both edges.

### 5.1 The simulated single cell has no continuous 80 % band at all

Fig. 1(b), captioned *"Simulated absorption, transmission and reflection of one
unit cell"*, under PEC/PMC boundaries — i.e. an infinite array of **identical**
cells, the s = 1 letter alone.

| | Value |
|---|---|
| ≥0.80 windows | **8.96–9.21 GHz (0.25 GHz)** and **10.39–10.69 GHz (0.30 GHz)** — two disjoint windows |
| ≥0.90 windows | 9.01–9.16 GHz and 10.45–10.62 GHz |
| Between the peaks | **minimum 0.266 at 9.79 GHz** |

**There is no continuous ≥80 % band. There is a 0.27 hole in the middle of one.**

### 5.2 The detuned tiles fill the hole

Scoring all three simulated curves on **the same fixed window** — 8.63–11.07 GHz,
2.44 GHz wide, 24.8 % fractional, which is the widest continuous ≥80 % run any of
them achieves — and taking the **worst-in-band absorptivity**, which is exactly
[ADR-0041](./adr/0041-absorber-score-is-worst-in-band-minimax-with-fsv-comparison.md)'s
minimax quantity:

| Simulated | Letters | Minimax over 8.63–11.07 GHz | Longest continuous ≥80 % run |
|---|---|---|---|
| Fig. 1(b), one cell | 1 | **0.266** | none (0.30 GHz best) |
| Fig. 6 / 9(a), KOH12 | 12 | **0.692** | 0.97–0.98 GHz |
| Fig. 6 / 9(b), KOH16 | 16 | **0.785** | **2.44–2.45 GHz** |

**Monotone in N, and the gain is large.** The worst-absorbing frequency in a
24.8 % band goes from swallowing 27 % of the power to swallowing 79 % of it,
with no change to the spacer, the ground plane, the thickness or the materials —
only the lateral sizes and positions of coplanar letters over one shared
spacer.

*In plain terms: one letter on its own leaves a frequency right in the middle of
the band where three-quarters of the radar energy bounces straight back. Sixteen
slightly different letters on the same sheet cut that to one fifth, without the
part getting any thicker.*

**Two corrections to what a previous pass reported**, both found by doing the
read rather than repeating it:

- The claim that *"the detuned tiles hold ≥80 % continuously over ~2.5 GHz"* is
  true of **KOH16 only**. The simulated **KOH12 does not** — it dips to 0.75 at
  9.8 GHz and holds ≥0.80 for only 0.98 GHz. Its measured curve holds 2.73 GHz;
  its own simulation does not. The paper's own headline — 12 letters beat 16 on
  band — is a **measurement** result that its **simulation** contradicts by 2.5×
  in the other direction.
- The in-band minimum moves **0.27 → 0.79**, not 0.27 → 0.90.

### 5.3 A defect in the measured KOH16 trace

Reading the measured ("Exp.") KOH16 curve in Fig. 9(b), the longest continuous
≥0.80 run is **8.94–11.28 GHz = 2.33 GHz**, not the 8.86–11.41 GHz = 2.55 GHz
the text reports. The trace dips to ~0.78 at ~8.92 GHz and slips back under 0.80
from ~11.30 GHz, running 0.70–0.79 out to the stated 11.41 GHz edge.

The measured traces carry a visible ±0.1–0.2 ripple with a ~0.1 GHz period —
the signature of an un-gated free-space reflection measurement — so the most
likely reading is that the authors took the 0.80 crossings **through** the
ripple rather than at its lower envelope. It is recorded because it is
load-bearing for ADR-0041: **scored as worst-in-band over the interval the paper
itself reports, KOH16's measured absorptivity is ~0.78, not ≥0.80.** The KOH12
number does not have this problem — its measured run reproduces exactly. `INFERRED.`

---

## 6. Why both results are right, and why this programme is in the second regime

**Hypothesis, not a finding.** Nothing below is tested; §7 says how to test it.

The two answers — Ozden's simulated 0.27 → 0.79 gain, and this repo's measured
+0.7 pp nothing — are not in conflict, because **the baselines are in different
physical regimes.**

| | Ozden (2016) | This programme's #128/#187 bench |
|---|---|---|
| Conductor | 17 µm copper, σ = 5.8 × 10⁷ S/m | printed resistive letters, R_s = 25–50 Ω/sq |
| Skin depth at 10 GHz | 0.661 µm — the copper is **25.7 skin depths** thick | n/a; the letters are resistive by design |
| **RF surface resistance at 10 GHz** | **26.1 mΩ/sq** | **25–50 Ω/sq — 958× to 1916× higher** |
| DC sheet resistance | 1.01 mΩ/sq | ~the same as RF (thin-film regime) |
| Spacer | FR4, 0.75 mm, **tan δ = 0.03** | silicone, 1.5 mm, **tan δ ≈ 0.10** |
| Single-cell baseline | **two sharp peaks, 0.27 hole between them, no continuous ≥80 % band** | **one broad resonance, 22.1 % continuous ≥90 %** |
| What detuning bought | filled the hole: minimax 0.27 → 0.79 | +0.7 pp of width, or −1.5 pp at R = 50 Ω |

**Note the DC-vs-RF distinction, because it is the whole argument.** At DC,
17 µm of copper is 1.01 mΩ/sq. At 10 GHz the current crowds into the top
0.661 µm and the effective surface resistance rises 25.7× to 26.1 mΩ/sq — still
utterly negligible. `CALCULATED` from R_s = 1/(σδ), δ = √(2/ωµ₀σ). So Ozden's
**only** meaningful loss channel is FR4's tan δ = 0.03, and the resonators
themselves are essentially loss-free: high-Q, sharp, deep, narrow.

**The mechanism, stated plainly.** Lateral detuning is a *hole-filling* trick.
It takes a response with peaks and troughs and slides copies of it along in
frequency until the troughs of one land under the peaks of another. Its payoff
is proportional to how deep the troughs are.

- Ozden's troughs are 0.27 deep. There is a great deal to fill. Filling it is
  worth 52 percentage points of worst-in-band absorptivity.
- This programme's letters are **already loss-broadened**: R_s at 25–50 Ω/sq on
  a tan δ ≈ 0.10 spacer produces one wide, shallow, heavily damped resonance
  that is 22.1 % wide at ≥90 % **before any detuning at all**. There is no
  trough. Averaging a set of slightly offset broad humps returns approximately
  the same broad hump — which is exactly the ±1.5 pp the bench measured, in
  either sign depending on operating point.

*In plain terms: their trick is patching potholes, and their road is full of
them. Our road was already paved — by loss — so there is nothing left to patch.
Both crews are telling the truth about their own road.*

**This is a hypothesis with a named alternative.** The competing explanation is
#187's original one — *one spacer, one inductance, so detuning only averages
capacitances* — which `docs/supercell-ring-inductance-bench.md` §7 records as
still unsettled. The two are not exclusive: the shared-inductance argument says
detuning *cannot* create a second resonance; the loss-regime argument says that
even where it can (Ozden's cell has two resonances already, from its
dual-ring element, §1.2) the payoff scales with how deep the trough is. Ozden's
result is consistent with both.

---

## 7. What would settle it — one bench run

Concretely, and it is cheap:

**Re-run the #128/#187 circuit bench with Ozden's stack, sweeping only the sheet
resistance.**

| Held fixed at Ozden's values | |
|---|---|
| Spacer | 0.75 mm, ε_r = 3.6, tan δ = 0.03 |
| Element | dual-resonance (two coupled series-LC branches, tuned to 9.10 and 10.53 GHz) |
| Letters | 12 and 16, with the §1.1 scale factors |
| Detuning | lateral only — cell period and all in-plane dimensions × s_i, spacer unchanged |

**Sweep:** R_s from **26 mΩ/sq** (Ozden's copper) up through 1, 10, 25, 50, 100,
250 Ω/sq (printed-trace values), re-tuning the geometry at each point to hold
~10 GHz — `docs/supercell-ring-inductance-bench.md` §6 records that failing to
re-tune produced a spurious "39 % bandwidth" that was nearly reported as a
finding.

**Score at each point:** the minimax over a fixed band (ADR-0041), one letter
against 12 and 16.

**The one number to find: the sheet resistance at which the detuning gain
collapses from Ozden's ~+50 pp of minimax to the bench's +0.7 pp of width.**

- **If it collapses at printed-trace R_s**, #187's practical answer for this
  programme is unchanged **and the reason is now known** — which is a strictly
  better outcome than the current unexplained null, because it converts "detuning
  doesn't work" into "detuning doesn't work *at our loss level*, and here is the
  loss level where it starts to."
- **If it does not collapse**, the bench has a modelling gap — most likely the
  inter-cell coupling term §1.1 shows Ozden optimising and the bench omits by
  construction — and #187 reopens on much firmer ground.

Either way the run is a few minutes of the existing bench and answers a question
that has now consumed three separate research passes.

---

## 8. Rozanov comparison

Computed with this repo's own `rf_tools.physical_bounds.rozanov_min_thickness_m`
(Rozanov Eq. 9, µ_s = 1, non-magnetic), read first-hand in
`docs/rozanov-bound-primary-source.md`. `CALCULATED`.

| Design | Floor | Band | Rozanov d_min | Actual thickness | **Budget extracted** |
|---|---|---|---|---|---|
| Ozden KOH12, measured | ≥80 % | 8.71–11.44 GHz | 0.3349 mm | 0.75 mm | **44.6 %** |
| Ozden KOH16, measured | ≥80 % | 8.86–11.41 GHz | 0.3083 mm | 0.75 mm | **41.1 %** |
| **Ozden KOH16, measured** | **≥90 %** | **9.09–11.08 GHz** | **0.3455 mm** | **0.75 mm** | **46.1 %** |
| **This repo's #187 bench** | **≥90 %** | **9.03–11.27 GHz** | **0.3849 mm** | **1.50 mm** | **25.7 %** |

Both figures reproduce the previous pass's numbers exactly, so no correction is
needed there.

*In plain terms: physics sets a floor on how thin an absorber of a given
bandwidth and depth can be. Ozden's part is 0.75 mm where the floor is 0.35 mm —
it is using 46 % of what its thickness entitles it to. The bench design is
1.5 mm where the floor is 0.38 mm — 26 %. The bench design has more room against
the same physics than the published part does, so a null result there is not the
thickness bound talking.*

**Per [ADR-0047](./adr/0047-the-loop-advises-against-a-physical-bound-never-gates-on-it.md)
this advises and never gates.** What it advises: the ~1.8× headroom gap is real
but modest, and it means the bench's flat detuning result cannot be blamed on
"the skin is too thin anyway" — which is the same conclusion
`five-paper-absorber-corpus-findings.md` §1 reached by a different route, and
that row of its table stands.

**One caveat that swings this by 2×**, and it is §9's second defect: if the
fabricated coupon used standard 1.6 mm FR4 rather than the simulated 0.75 mm,
Ozden's ≥90 % extraction falls from 46.1 % to **21.6 %** — *below* the bench's
25.7 %, reversing the comparison. The row is reported at 0.75 mm because that is
the number the paper states; the sensitivity is flagged because it is not a
small one.

---

## 9. Defects in the primary source, carried honestly

**(i) The Introduction and §3 disagree about which band belongs to which tile.**
The Introduction (p. 1063) reads:

> "the absorbers which consist of 12 (KOH12) and 16 (KOH16) scaled unit cells
> yield absorption rates greater than 80 % in the frequency range from 8.86 GHz
> to 11.41 GHz and from 9.09 GHz to 11.08 GHz, respectively."

That assigns 8.86–11.41 to KOH12 and 9.09–11.08 to KOH16, both at 80 %. §3
assigns 8.86–11.41 to **KOH16** at 80 % and 9.09–11.08 to KOH16 at **90 %**.

**§3 is the self-consistent one**, and the abstract settles it: the abstract
states *"Measurement bandwidth for an absorption level of 80 % is 2.73 GHz for
KOH12 and 2.55 GHz for KOH16"* — 11.44 − 8.71 = 2.73 and 11.41 − 8.86 = 2.55,
which matches §3 and not the Introduction. **Cite §3; the Introduction's
sentence is a transcription error.**

**(ii) The stated λ/18 thickness does not match the stated 0.75 mm dielectric —
and thickness is the Rozanov budget variable, so this is load-bearing.**
From §2.3, verbatim:

> "The absorber has a thickness of λ/18 where λ is the operating wavelength
> corresponding to the middle of the absorption bandwidth."

`CALCULATED`: the middle of KOH12's measured band is 10.075 GHz, so
λ₀ = 29.756 mm and λ₀/18 = **1.653 mm**.

| Candidate thickness | λ₀ is this many times it |
|---|---|
| 0.75 mm (stated dielectric) | λ₀/39.7 |
| 0.784 mm (dielectric + 2 × 17 µm copper) | λ₀/38.0 |
| **1.6 mm (standard FR4)** | **λ₀/18.6** |

**λ/18 is off by 2.1× against the full stated stack (2.2× against the dielectric
alone), and lands within 3.3 % of standard 1.6 mm FR4.** Two readings, and the
paper does not distinguish them:

- The simulation used 0.75 mm, the fabricated coupon used a stock 1.6 mm board,
  and §2.3's λ/18 describes the coupon. This would explain the number exactly,
  and would explain the KOH12 simulation-vs-measurement mismatch in §5.2.
- λ/18 is simply an error and the whole stack is 0.75 mm.

**Consequence, §8:** the ≥90 % Rozanov extraction is 46.1 % under the first
reading and 21.6 % under the second. It is the difference between "extracts
nearly half its budget" and "extracts about a fifth", so it cannot be waved
away. `UNKNOWN` which is right; the paper contains no photograph scale, no
board-thickness callout in Fig. 8, and no stack-up drawing that would settle it.

**(iii) The angle-of-incidence data is SIMULATED, never measured.** §2.2,
verbatim: *"The simulated absorption of the metamaterial absorber is also
investigated for different incident angles (θ)..."*, and Fig. 7's caption reads
*"Simulated absorption at different incident angles."* The conclusions
nevertheless assert *"The absorption performance of the KOH12 and KOH16 is also
maintained for oblique incidences less than 40°"* without the qualifier.
**There is no measured oblique-incidence data in this paper.** Since a
conformal skin on a curved host is an oblique-incidence problem by construction
(#110), this matters: the angle claim is `SIMULATED`, and per CLAUDE.md nothing
in this programme rises above `SIMULATED` anyway — but it must not be quoted as
though it were bench data.

**(iv) An unbacked superlative.** The abstract claims *"These are the highest
absorption levels for planar metamaterial absorbers at X-band."* The paper
contains **no comparison table** and cites no competing measurement against
which "highest" is judged. Its own Introduction names Gu *et al.* [23] at
*"greater than 80 % ... 2.35 GHz in the X-band"*, which Ozden's 2.73 GHz does
exceed on width — but width is not "absorption level", and no level comparison
is made anywhere. Treat the superlative as unsupported.

---

## 10. The absorber does not cover 8–12 GHz

An outside research pass reported that this absorber *"covers 8–12 GHz"*. **It
does not.**

`CALCULATED`: the best measured band is KOH12's **8.71–11.44 GHz**. Against the
4.00 GHz of X-band as the paper itself defines it (*"a novel X-band (8–12 GHz)
metamaterial broadband absorber"*, abstract):

- **2.73 GHz of 4.00 GHz = 68.2 % of X-band.**
- It reaches **neither edge**: 0.71 GHz short at the bottom, 0.56 GHz short at
  the top.

The overclaim is not the paper's — the paper is careful, stating its band edges
in three places and never asserting full coverage. It is a summarisation error,
and it is recorded here so the next reader inherits the correct number.

---

## 11. Capability warning — the pattern is printable; the stack is a redesign

Reported, never dropped ([ADR-0025](./adr/0025-the-morning-report-leads-with-the-trade-space-and-records-what-was-not-tried.md),
[ADR-0027](./adr/0027-the-alphabet-admits-only-printed-letters-and-identity-includes-the-process.md)).
This warning is load-bearing in ADR-0025's sense: whether the stack is
reproducible changes whether this design can be a candidate at all, not merely
how it scores.

**What does not transfer.** Ozden's stack is 17 µm etched copper on rigid
0.75 mm FR4 with a **continuous copper back face**. Against this configuration's
declared capability — **Voltera NOVA direct-ink-write extrusion, ~100–120 µm
line, ≤40 °C material temperature, 220 × 300 mm bed**:

1. **The conductor is not this configuration's ink.** 17 µm of bulk copper at
   26.1 mΩ/sq RF surface resistance is not reachable by direct-ink-write with
   any ink in the catalogue. ACI SS1109 silver at σ > 2.22 × 10⁶ S/m is 26×
   below copper's bulk conductivity before any porosity penalty. **The whole of
   §6's argument is that this difference is the point, not a detail.**
2. **The substrate is not conformable.** Rigid FR4 is the opposite of the
   pliable sub-2 mm skin US12089385B2 contemplates.
3. **The continuous back face needs double-sided registration on a compliant
   sheet, which is a logged NOVA limitation.** `docs/voltera-multilayer-capability.md`
   records verbatim that *"Double-sided printing is a V-One capability, not a
   NOVA one"*, that Voltera *"publishes no layer-to-layer registration figure"*,
   and that the V-One's own double-sided workflow *"does not transfer to a 2 mm
   flexible sheet."*

**What does transfer — and it is the useful half.** The *pattern* is well inside
the machine's reach:

| Feature | Ozden (s = 1) | Ozden (smallest letter, s = 0.912) | vs ~100 µm | vs ~120 µm | vs the 0.2 mm design floor |
|---|---|---|---|---|---|
| Trace width w | 0.50 mm | 0.456 mm | 5.0× / 4.6× | 4.2× / 3.8× | 2.5× / 2.3× |
| Gap g | 0.33 mm | 0.301 mm | 3.3× / 3.0× | 2.8× / 2.5× | 1.6× / 1.5× |

`CALCULATED`. The ~100–120 µm figure is the NOVA's advertised floor and the best
line width demonstrated for a real paste respectively
(`docs/mxene-voltera-nova-printability.md` §8); the 0.2 mm figure is the more
conservative design floor in `docs/fabrication-capability-and-ink-library-spec.md`.
**Ozden's finest feature clears all three**, including after the 0.912 lateral
scaling shrinks it.

> **The pattern is printable; the stack is a redesign.** A useful thing to know:
> if the geometry is ever worth reproducing, the obstacle is the copper, the
> board and the back face — not the drawing.

---

## 12. Register updates

**For `docs/RUNNING-LISTS.md` §1 — a resolution, not a new opening.** The
ScienceDirect HTTP 403 row's note that *"the full text is needed to check the
actual cell layout"* is closed: the layout is read, quoted and reproduced above.
The ScienceDirect **block** remains real; a further route around it is now
recorded (§0: open PDF mirrors located by filename).

**Corrections landed on their claims** (ADR-0024 — *a correction lands at the
claim; the register keeps the lesson*):

- `docs/five-paper-absorber-corpus-findings.md` §1's `CONFIDENCE: HIGH` "the
  published record does not contain the experiment" ruling — **rescoped to the
  five papers actually searched**, with the root cause named: none of the five
  is a microwave paper.
- The same file's `MEDIUM-HIGH` "revealed preference across four groups" row —
  **falls**. Ozden's own Introduction names five further groups reaching for
  exactly this: Lee & Lee [20], Kollatou *et al.* [21], Park *et al.* [22], Gu
  *et al.* [23] (>80 % over 2.35 GHz in X-band), Ghosh *et al.* [24]. Reference
  numbers verified against the printed reference list. Lateral detuning is not a
  road-not-taken; it is a small literature.

**Not amended: [ADR-0040](./adr/0040-design-is-selection-and-placement-from-a-quantised-alphabet.md).**
Its §"Open and unresolved" paragraph says the broadband-bandwidth rationale is
*"still open on #187"* and that three follow-up checks *"have since narrowed but
not settled"* it. **That remains exactly true after this paper** — the
literature now contains the experiment, and the experiment answers *width*
flatly (§4) and *depth* strongly (§5) while leaving the transfer to this
programme's loss regime untested (§6). The ADR's own statement of the position
is unchanged; only the evidence beneath it has grown.

**Open, for #187:** the §7 bench run. It is the only cheap step left that can
move the ticket.
