# A superposition coupling-error bound for our own alphabet, at block size N

**Date:** 2026-09-11
**Ticket:** No issue opened yet. Direct continuation of `docs/RUNNING-LISTS.md` §5 item 4
("An error bar on the superposition fast tier — for *our* alphabet"), downstream of
[#111](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/111)
(`docs/local-periodicity-coupling-error.md`),
[#130](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/130)
(`docs/supercell-sizing-rule.md`) and
[#138](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/138)
(`docs/ishape-interior-tuning.md`).
**Question:** Those three documents each combine published numbers with this repo's own
element geometry for a *piece* of this question. Nobody has yet put the pieces together
into the single thing item 4 asks for: *"superposition of independently characterised
letters is accurate to ±X° at block size N"* — for our own alphabet, not a generic one.

Every number below traces to a retrieved primary source (cited with DOI/arXiv id) or is
this document's own arithmetic, tagged per `CONTEXT.md`'s Provenance discipline:
`CALCULATED` (I did the arithmetic), `LITERATURE-SUPPORTED` (a retrieved source states
it), `INFERRED` (read off a figure, or an analogy between two geometries). Nothing below
is `MEASURED` — nobody has printed and characterised a letter in this program yet
(`CONTEXT.md`: **Letter** — "a symbol described in a paper, or drawn and simulated but
never printed, is not a letter"). Everything here concerns a **Symbol**, a candidate for
the alphabet, not an admitted **Letter**.

---

## Bottom line up front

**There is no single safe ±X° for our alphabet today, and that is itself the finding —
but it is not a shrug. It splits into one part that is boundable now and one part that
is not, and the document says exactly where the line falls.**

Our only fully-analysed candidate letter is the patent's I-shaped electric-ring-resonator
absorber cell (US12089385B2 Example 3 = Landy et al.'s absorber, arXiv:0803.1670),
already run through `docs/ishape-interior-tuning.md`. Its cell is **rectangular, not
square** — `a₁ = 4.2 mm` (H-plane) by `a₂ = 12 mm` (E-plane) — so it has **two different
electrical pitches at 10 GHz, not one**:

| Axis | Pitch | In wavelengths at 10 GHz (λ₀ = 29.979 mm) |
|---|---|---|
| H-plane (`a₁`) | 4.2 mm | **0.140 λ** |
| E-plane (`a₂`) | 12 mm | **0.400 λ** |

Costanzo, Venneri & Di Massa (IJAP 2019, DOI 10.1155/2019/4890710) tested pitch down to
**0.3λ only**. Our E-plane pitch (0.400λ) sits inside that window, with no interpolation
needed — it lands almost exactly on their tested 0.4λ point. Our H-plane pitch (0.140λ)
sits **below the floor of every quantified source this repo has retrieved**, in the same
territory where Budhu & Grbic (arXiv:2211.11588) report local periodicity as an outright
qualitative failure (their tested pitch: 0.150λ) rather than a graded error in degrees.

That geometric accident — one axis inside the data, one axis just below it — is what
makes a genuinely combined bound possible, and it splits the answer in two:

1. **The gap/capacitive channel (E-plane, boundable).** Built with interior tuning (the
   split gap `G`, or interdigital fingers, per `docs/ishape-interior-tuning.md` §4.2) so
   the letter never changes what it presents to its neighbour, this channel matches
   Costanzo's fixed-edge cell at the *identical tested pitch* (0.4λ): **Δφ_max ≈ 20° per
   cell** (`INFERRED`, an analogue bound — see §2 for exactly how far this can be
   trusted). Diluted by block averaging (`docs/supercell-sizing-rule.md`'s
   `f(N_x,N_y)` model, `CALCULATED`), this falls to **≤11.4° at a 7×5 block**, which
   clears a 20 dB RCS-reduction requirement. **This part is a genuine worked answer.**

2. **The inductive/neighbour-detuning channel (H-plane, not boundable from published
   phase data).** Withayachumnankul, Fumeaux & Abbott's control experiment
   (arXiv:1109.0055) measured **+6.9% unlike-neighbour frequency pulling** on a
   geometrically *identical* ELC resonator family — zero gap excursion, same mechanism
   as our interior-tuned letter — at a pitch (0.117–0.156λ) that closely brackets our
   own H-plane pitch (0.140λ). Converting that pulling to a phase error needs a formula
   nobody publishes for this geometry; a standard single-pole approximation
   (`CALCULATED`, heavily assumption-laden, see §3) puts the **single-cell phase error at
   roughly 108°–163°** — several times every RCS-reduction phase budget this repo uses,
   and **nobody has ever measured how this specific channel dilutes with block size**,
   so `f(N)` cannot be applied to it with any confidence.

**The honest top-line statement:** *our candidate letter's superposition error is
bounded at ≤11.4° at a 7×5 block on its gap/capacitive channel alone — but that bound is
not the whole story, because a second, larger, unquantified channel exists on the same
letter's other axis, and closing it needs one specific new measurement, not a literature
search (§5).* Reporting "±11.4° at N = 7×5" without that caveat would be the kind of
smuggled precision this program's charter warns against.

For the patent's own two other Tier B examples — Example 4 (`REFLECTION_PHASE`, pitch
0.071λ) and Example 5/7 (`REFLECTION_PHASE`/`DIFFUSIVE`, pitch 0.2λ) — **no quantified
bound is possible at all**: both sit below Costanzo's data floor and at or below Budhu &
Grbic's qualitative-failure pitch. See §4.

---

## 1. What is being combined, and why these two sources specifically

`docs/RUNNING-LISTS.md` §5 item 4 names two published sources as the raw material:

- **Costanzo, Venneri & Di Massa, *IJAP* 2019, DOI
  [10.1155/2019/4890710](https://doi.org/10.1155/2019/4890710).** Publishes **max
  reflection-phase error against element pitch at 10 GHz**, for three element shapes,
  from a method-of-moments extended-local-periodicity (ELP) solve (`SIMULATED` at
  source; their Section 4 experimental validation — an 11×11 array, two horns, a VNA —
  confirms the *assembled array's* pattern, not any one element's Δφ, per
  `docs/RUNNING-LISTS.md` §3 correction 14). Table 3, reproduced from
  `docs/local-periodicity-coupling-error.md`:

  | Cell pitch | Square patch max Δφ | Minkowski max Δφ | Fixed-edge ("proposed") max Δφ |
  |---|---|---|---|
  | 0.5λ | 25° | 21° | **12°** |
  | 0.4λ | >45° (85° peak) | ≅45° | **20°** |
  | 0.3λ | >45° (85° peak) | ≅45° | **34°** |

  This is a *pitch-versus-error* curve, at fixed neighbour count (their ELP protocol
  always swaps in exactly two extreme E-plane neighbours). It says nothing about how
  the error changes with *how many* neighbours are modelled.

- **An, Zheng, Shalaginov *et al.*, arXiv:[2102.01761](https://arxiv.org/abs/2102.01761)
  (*Adv. Optical Mater.* 10(3):2102113, 2022).** Publishes the only retrieved
  **error-versus-neighbour-count curve**: a periodic-boundary (0-neighbour) prediction
  carries **59.14° phase MAE** against a 10-neighbour-each-side ground truth, at 0.516λ
  pitch, on a silicon-nanoblock optical platform (`SIMULATED`, CST). They settle on
  **N = 4 neighbours each side** for their own low-index platform and **N = 2** for a
  higher-index, more tightly-confining one — because *"even considering only the single
  nearest meta-atom on each side of the target would largely improve [accuracy], but
  the large error values … are caused by … randomly arranged meta-atoms."*

These two curves answer **different questions along different axes** — pitch-versus-error
at fixed neighbour count, and neighbour-count-versus-error at fixed pitch — and neither
was measured on our geometry, our band, or our element shape. Item 4's own text already
says what combining them is *for*: not to average two numbers together, but to (a) pin a
Δφ_max for our own pitch from Costanzo's curve, then (b) use `docs/supercell-sizing-rule.md`'s
block-averaging model — itself informed by An et al.'s finding that error does not sit
entirely on the outermost ring of neighbours — to turn that per-cell number into a
per-block one. That is what §2 below does. An et al.'s numeric role in this document is
narrower than a first read suggests, and §2.4 states exactly what it is and is not used for.

---

## 2. The gap/capacitive channel: a worked, boundable figure

### 2.1 Which pitch, and why 20° is the right Costanzo row

`docs/ishape-interior-tuning.md` §1.3–1.4 establishes, from Landy et al.'s own axis
triad (arXiv:0803.1670 Fig. 1(c), `LITERATURE-SUPPORTED`), that the I-shape's E-plane
runs along `a₂ = 12 mm = 0.400λ` at 10 GHz. Costanzo's protocol swaps in the alphabet's
extreme members along the **E-plane** specifically, because *"they give higher mutual
coupling levels and consequently higher phase errors with respect to the H plane case"*
(`docs/local-periodicity-coupling-error.md` §2.1, quoting Costanzo et al.). Our E-plane
pitch (0.400λ) lands on Costanzo's own **tested 0.4λ row** — not close to it,
*on* it, to three significant figures (12/29.979 = 0.40028λ) — so no pitch interpolation
is needed for this axis.

The row that applies is the **fixed-edge ("proposed") cell**, not the square patch or
Minkowski: Δφ_max = **20°**. This is the cell Costanzo built specifically so that
*tuning never changes the gap to the neighbour* — exactly the design rule
`docs/ishape-interior-tuning.md` §2.4 establishes for our I-shape tuned by its interior
split gap `G` (or by interdigital fingers replacing it, per Withayachumnankul et al.'s
measured 1.50× fixed-outline alphabet, arXiv:1009.0139): **zero gap-to-neighbour
excursion by construction.**

**This is an analogy, not a measurement of our shape, and the analogy's strength should
be stated plainly.** What is shared: (a) the same tested pitch, 0.4λ; (b) the same
physical mechanism Costanzo credits for the low number — *"the capacitance variation
exhibited by the variable square-based cells is about 20 times larger than that provided
by the corresponding fractal cells"* — which is a statement about gap excursion, and our
I-shape's gap excursion under `G`-tuning is **zero**, same as their fixed-edge cell's.
What is *not* shared: the outline. Costanzo's fixed-edge cell is a modified-Minkowski
fractal patch; ours is an ERR-over-cut-wire. Borrowing their number is therefore
`INFERRED`, carried at the same confidence `docs/ishape-interior-tuning.md` already
assigned it, not `LITERATURE-SUPPORTED` for our own shape. **Confirming it needs one ELP
solve on the I-shape itself** — the same protocol Costanzo used, applied to our
geometry, which `docs/ishape-interior-tuning.md` §7 already specifies and defers.

### 2.2 Block averaging, on our own cell's real aspect ratio

`docs/supercell-sizing-rule.md` §2.1, generalised for a rectangular cell in
`docs/ishape-interior-tuning.md` Amendment 1, gives the boundary fraction of an
`N_x × N_y` block of identical cells (the fraction touching a foreign neighbour, hence
carrying the per-cell error):

```
f(N_x, N_y) = 1 − (N_x−2)(N_y−2) / (N_x·N_y)          for N_x, N_y ≥ 2
```

and bounds the block-averaged phase error as `Δφ_block ≤ Δφ_max · f(N_x, N_y)`
(`INFERRED` — this repo's own model, not published anywhere; its own stated limit is
that it treats the error as binary per cell, full on the boundary ring, none inside,
which An et al.'s convergence curve shows is optimistic — see §2.4).

The **ceiling** — the block's own diffracted lobe has to clear the panel's specular
return, not just exist — uses Amendment 2's two-axis form:

```
sin θ = (λ/2) · sqrt( 1/a_x² + 1/a_y² )      a_x = N_x·p_x,  a_y = N_y·p_y
```

with `p_x = a₁ = 4.2 mm`, `p_y = a₂ = 12 mm`, against a specular-lobe floor of
**4.78°** for a 6λ (180 mm) coupon (`docs/supercell-sizing-rule.md` §3, using the
coupon size `#106` specifies). And the **panel-fit** constraint (Amendment 4,
`2·N_x·p_x ≤ L` and `2·N_y·p_y ≤ L`) is checked and, on this small a cell, is never
binding at the block sizes below.

### 2.3 The worked table

Using Δφ_max = 20° (§2.1) against the cancellation-derived phase budget
`δ = 2·arcsin(10^(−RCSR_dB/20))` (`CALCULATED`; `docs/supercell-sizing-rule.md` §2.2,
confirmed at primary level against Haji-Ahmadi et al., *Sci. Rep.* 7:11437 (2017),
DOI 10.1038/s41598-017-11714-y — their stated **180° ± 37°** criterion for 10 dB
reproduces the formula's 36.87° to 0.13°):

| Required RCS reduction | Phase budget δ | Minimum feasible block (N_x × N_y) | Δφ_block at that block | Diffraction angle θ |
|---|---|---|---|---|
| 6 dB | 60.2° | 5 × 2 | 20° | 71.5° |
| 10 dB | 36.9° | 5 × 2 | 20° | 71.5° |
| 15 dB | 20.5° | 5 × 2 | 20° | 71.5° |
| 20 dB | 11.5° | 7 × 5 | **11.4°** | 34.6° |

(5 × 2 is also this cell's **hard floor** — Amendment 3 shows no block smaller than
5 × 2 produces a propagating diffracted order at all on this cell, independent of any
coupling-error consideration; `f(5,2) = 1.0`, so no averaging happens there regardless.
The 20 dB row is the first one where the coupling-error floor, not the diffraction
ceiling, sets the block size — verified: `f(7,5) = 1 − (5)(3)/35 = 0.5714`,
`20° × 0.5714 = 11.43° ≤ 11.5°`, and `sin θ = 0.5676 → θ = 34.6°`, both checked directly
in this document, agreeing with `docs/ishape-interior-tuning.md` §5's own Δφ_max = 20°
row to the same precision.)

**This is the worked, usable half of the answer: on its E-plane/capacitive channel, an
I-shape alphabet tuned by interior gap or interdigital finger count is accurate to ≤20°
at the smallest block the physics allows, falling to ≤11.4° at a 7×5 block — comfortably
inside a 20 dB requirement's ±11.5° budget.**

### 2.4 What An et al.'s curve actually contributes here

Not a number plugged into the table above — no retrieved figure gives the exact shape
of An et al.'s error-versus-N curve between N = 0 and N = 10, only its endpoints
(59.14° at N = 0, by definition 0 at N = 10) and their stated operating choice (N = 4 for
a low-index platform, N = 2 for a high-index one). What it contributes is a **caveat on
§2.2's averaging model**: An et al.'s reason for needing N = 4 rather than N = 1 is that
*"even considering only the single nearest meta-atom … would largely improve"* accuracy
but not fully — some of the error comes from neighbours beyond the first ring. Skarda,
Trivedi, Su *et al.* (arXiv:2107.09879) independently report the same split by **element
aspect ratio**: tall, strongly-confining elements tolerate a local approximation; flat,
thin ones — which is what a printed conductor on a thin dielectric host is — do not.
`docs/supercell-sizing-rule.md`'s own provenance section already states this limit for
`f(N)`: *"this understates for N ≥ 4."* This document does not attempt to re-derive a
sharper model from An et al.'s two endpoints alone — that would be interpolating between
two points on a curve measured on a different platform, in a different band, which is
exactly the kind of silent extrapolation the task instructions warn against. **The
honest statement is that §2.3's table is an upper bound that becomes less conservative,
not more, as the block grows past a handful of cells**, and closing that is the same
open item `docs/supercell-sizing-rule.md` already names: our own alphabet's Δφ_max,
measured rather than borrowed, needs the bench.

---

## 3. The inductive/neighbour-detuning channel: what published data cannot bound

### 3.1 The measurement that matches our H-plane pitch

`docs/ishape-interior-tuning.md` §4.3 already found the closest available control
experiment: **Withayachumnankul, Fumeaux & Abbott, "Effects of mutual coupling in
dual-resonance metamaterials," arXiv:[1109.0055](https://arxiv.org/abs/1109.0055)
(2011).** A 20×20 array of ELC resonators, cell `a = 13 mm`, footprint `d = 11 mm` —
**2 mm gap everywhere, held geometrically identical** — with alternate rows biased to
different frequencies by a loaded varactor. Measured (VNA, anechoic chamber) and
simulated (HFSS), with a fitted circuit model. Reading their Fig. 3 (`INFERRED`, off the
plotted curve, `SIMULATED` at source):

> the 0 V population resonates at 2.70 GHz surrounded by like neighbours, and at
> 2.885 GHz surrounded by neighbours tuned to 24 V — **a +6.9% shift from the neighbours
> alone, with the shape held perfectly fixed.**

Their fitted circuit gives **mutual inductance M = 2.8 nH against self-inductance
L = 36.5 nH — a 7.7% coupling coefficient** (`LITERATURE-SUPPORTED`, quoted verbatim).
The mechanism is explicitly **inductive**, not the capacitive/gap mechanism Costanzo's
number addresses:

> "At M = 0, where the two systems are decoupled, the two resonances become comparable
> in strength. Hence, a difference in the resonance strengths is responsible purely by
> the inter-cell inductive coupling."

Their electrical pitch is `a = 13 mm` at 2.70–3.57 GHz, i.e. **0.117–0.156λ** — bracketing
our I-shape's H-plane pitch of **0.140λ** almost exactly. This is the nearest pitch
match to our own geometry anywhere in the retrieved literature, closer than Costanzo's
own 0.3λ floor.

**Interior tuning removes the capacitive channel; it does not remove this one.**
`docs/ishape-interior-tuning.md` §4.3 already states this and does not attempt to
convert the 6.9% pulling into a phase-degree figure, flagging that step as needing a
solve. This document takes that one step further, clearly marked as a rough,
order-of-magnitude estimate rather than a bound.

### 3.2 Converting frequency pulling to a phase-error estimate — CALCULATED, heavily assumption-laden

For a single-pole resonant reflection element — the kind a phase-agile, ground-backed
coding-surface letter must be, by design (`CONTEXT.md`: **Symbol** — "characterised
reflection response … across the family's band") — a standard near-resonance
approximation for how much the reflection phase moves as the resonance is detuned by
`Δf/f₀` at quality factor `Q` is:

```
φ(Δf) ≈ 2 · arctan( 2Q · Δf/f₀ )
```

This is a generic single-pole/Lorentzian approximation used loosely across microwave
engineering for a moderately-high-Q resonant reflection element; it is **not** quoted
from any of this document's retrieved sources and is **not** specific to the ERR/ELC
topology. It is used here only to turn a measured frequency shift into a plausible order
of magnitude for the corresponding phase shift, and its own assumptions are stated
rather than hidden.

**The Q input.** No retrieved source states Withayachumnankul's own resonator Q
directly. Landy et al. (arXiv:0803.1670) — the patent's own reproduced absorber, sharing
Example 3's geometry — report their absorption peak's **FWHM as 4% of centre
frequency**, giving `Q = f₀/FWHM ≈ 25` (`LITERATURE-SUPPORTED` FWHM, `CALCULATED` Q, but
for a *different structure* — a coupled two-layer absorber, not Withayachumnankul's
single-layer transmissive ELC). Bracketing that with Q = 10 (broader, more damped) and
Q = 50 (narrower, less damped) covers the plausible range for either family:

| Q | 2Q·(Δf/f₀) = 2Q·0.069 | φ = 2·arctan(2Q·0.069) |
|---|---|---|
| 10 | 1.38 | **108.1°** |
| 25 (Landy's own FWHM) | 3.45 | **147.7°** |
| 50 | 6.90 | **163.4°** |

**Across the entire plausible Q range, the single-cell phase estimate is 108°–163°** —
several times the 20° capacitive-channel bound in §2, and larger than every RCS-reduction
phase budget this repo uses (60.2° at 6 dB down to 11.5° at 20 dB) **before any block
averaging is applied at all.**

### 3.3 Why this cannot simply be run through §2.2's block-averaging model

`docs/supercell-sizing-rule.md`'s `f(N)` model was built and validated (against
Costanzo's own protocol) for the **capacitive/gap-distance mechanism** — it dilutes
because a cell deep inside a block sees only like neighbours *of the same gap*. Nothing
retrieved states whether the **inductive** channel dilutes the same way. It plausibly
does, by the same physical logic (an interior cell's magnetic near field also
terminates mostly on like neighbours) — but that is a plausibility argument, not a
citation, and this document declines to assert a number built on an unstated model
applied outside where it was checked. **This is exactly the kind of silent
extrapolation the task's own instructions warn against, so it is named as a gap instead
of quietly folded into §2.3's table.**

---

## 4. Where the patent's other Tier B anchors fall — and why no number is honest there either

`designs/design_families.py` declares `REFLECTION_PHASE` and `DIFFUSIVE` as the two Tier
B families this program's alphabet actually serves; both are `optimizer_class =
"COMBINATORIAL"` over a symbol alphabet, and neither has a fixed pitch of its own — pitch
is a per-design spine field (`cell_period_x_m`/`cell_period_y_m`), not a family constant.
But the patent's own worked examples, which this repo treats as its anchor geometry
(`docs/seven-example-design-unknowns.md` §2), give concrete numbers, and they are tighter
than Example 3's I-shape on *both* axes:

| Patent example | Family | Period at 10 GHz | In wavelengths | Costanzo's tested floor | Nearest quantified data point |
|---|---|---|---|---|---|
| 3 (I-shape, E-plane) | — (candidate letter for Tier B) | 12 mm | **0.400λ** | 0.3λ | **Inside the tested range** (§2) |
| 3 (I-shape, H-plane) | — | 4.2 mm | **0.140λ** | 0.3λ | Below floor; §3's estimate applies |
| 7 (checkerboard ring pair) | `DIFFUSIVE` | 6 mm | **0.200λ** | 0.3λ | **Below floor; no number available** |
| 5 (BST square patch) | `REFLECTION_PHASE` (tunable) | 6 mm | **0.200λ** | 0.3λ | **Below floor; no number available** |
| 4 (cylindrical hole) | `REFLECTION_PHASE` | 2.125 mm | **0.071λ** | 0.3λ | **Below floor; no number available** |

For all three of these, Costanzo's curve simply does not reach — the nearest data point
below 0.3λ in any retrieved source is Budhu & Grbic's **0.150λ**, and their finding
there is qualitative only: *"the metasurface designed using locally periodic based
extractions … fails to perform wide-angle reflection."* No phase-error number attaches
to that statement; it is a design that did not work, not a design with a stated error
bar. Example 4's pitch (0.071λ) is smaller again than the pitch at which Budhu & Grbic
already report total failure.

**Stating precisely what is missing, rather than interpolating:** there is no published
source, in this repo or otherwise located in this pass, that gives a numeric
reflection-phase coupling error anywhere near 0.07–0.2λ pitch. Extending Costanzo's
0.3λ→0.4λ→0.5λ trend downward to 0.2λ or 0.07λ by eye, or worse, by linear or
log-linear fit, would produce a number with no support — the trend itself is already
non-linear (25°→85° between 0.5λ and 0.4λ for the square patch, more than triple over a
20% pitch reduction) and Budhu & Grbic's result shows the curve does not merely keep
climbing, it eventually stops being a *curve* at all and becomes qualitative collapse.
**The only honest statement for Examples 4, 5 and 7's own pitches is that the coupling
error at those pitches is unknown, and the nearest published fact suggests it is large
enough to matter.** Closing this needs the same ELP protocol run at our own pitch — see
§5.

---

## 5. What would turn this into a real, single number

Two concrete, bounded pieces of work close the two gaps this document identifies, in
order of leverage:

1. **Run Costanzo's own ELP protocol on the I-shape itself, both axes.** Build the
   extended 3×3 cell (the I-shape plus its eight real neighbours), solve once with all
   nine identical, once with the two E-plane neighbours swapped for the alphabet's
   extremes, and once with the two H-plane neighbours swapped — exactly the
   `simulation/palace.py` `PALACE_FLOQUET` adapter `designs/design_families.py` already
   names for `REFLECTION_PHASE`/`DIFFUSIVE`. This replaces §2's `INFERRED` 20° with a
   `SIMULATED`, geometry-specific Δφ_max on both axes at once, and directly answers
   `docs/ishape-interior-tuning.md` §7's open question of which axis actually dominates.
2. **Re-run Withayachumnankul's own dual-bias apparatus reporting phase, not just
   frequency.** Their arXiv:1109.0055 rig already exists, at a pitch (0.117–0.156λ)
   almost exactly matching our H-plane pitch, and already varies only the electrical
   state of the resonator while holding geometry fixed — precisely the control this
   question needs. It reported resonance frequency shift; it did not report the S11/S21
   phase shift that frequency shift implies. That is the one paper closest to already
   having done this experiment, and re-analysing (or re-running) it for phase would
   replace §3's `108°–163°` `CALCULATED` estimate with a real number.

Until at least (1) is done, **§2.3's ≤11.4°-at-7×5 figure should be read as "the part of
the error this repo can currently price," not as "the error."**

---

## 6. Provenance summary

| Claim | Provenance |
|---|---|
| I-shape cell 4.2×12 mm; H-plane 0.140λ, E-plane 0.400λ at 10 GHz | `CALCULATED` from FIG. 7F (US12089385B2) / Landy et al. arXiv:0803.1670, via `docs/ishape-interior-tuning.md` §1.4 |
| Costanzo Table 3 Δφ_max values (12–85° across 0.3–0.5λ, three shapes) | `LITERATURE-SUPPORTED` — Costanzo, Venneri & Di Massa, DOI 10.1155/2019/4890710, full text retrieved; `SIMULATED` (MoM) at source |
| Δφ_max ≈ 20° as our I-shape's E-plane gap/capacitive-channel bound | `INFERRED` — analogy between Costanzo's fixed-edge cell and our I-shape's interior-tuned design, matched on tested pitch and on the stated zero-gap-excursion mechanism; **not** a measurement of our own shape |
| `f(N_x,N_y)` boundary-fraction model and its stated understatement for N ≥ 4 | `INFERRED` — this repo's own model, `docs/supercell-sizing-rule.md`/`docs/ishape-interior-tuning.md` Amendment 1; the understatement caveat is informed by An et al.'s N-convergence finding (arXiv:2102.01761) |
| §2.3 worked table (block sizes, Δφ_block, diffraction angles) | `CALCULATED` — independently re-derived and checked against `docs/ishape-interior-tuning.md` §5's own Δφ_max = 20° row in this document |
| δ_budget formula and its 10 dB/36.9° value | `CALCULATED`; confirmed at primary level against Haji-Ahmadi et al., *Sci. Rep.* 7:11437 (2017), DOI 10.1038/s41598-017-11714-y |
| An et al. 59.14° MAE at N=0; N=4/N=2 chosen operating points | `LITERATURE-SUPPORTED` — arXiv:2102.01761, preprint and published PDF retrieved; `SIMULATED` (CST) at source |
| Withayachumnankul +6.9%/+2.8% frequency pulling; M=2.8 nH, L=36.5 nH (7.7% coupling) | `LITERATURE-SUPPORTED` for the circuit values (quoted verbatim); the +6.9%/+2.8% figures are `INFERRED` (read off arXiv:1109.0055 Fig. 3, `SIMULATED` at source) |
| Withayachumnankul pitch 0.117–0.156λ brackets our H-plane 0.140λ | `CALCULATED` |
| φ ≈ 2·arctan(2Q·Δf/f₀) single-pole phase-vs-detuning approximation | `INFERRED` — a generic engineering approximation, not sourced from any retrieved paper; applied here as an order-of-magnitude tool only |
| Q ≈ 25 from Landy et al.'s 4% FWHM | `LITERATURE-SUPPORTED` FWHM (arXiv:0803.1670); `CALCULATED` Q; carried across to a *different* structure (Withayachumnankul's ELC), flagged as an assumption |
| §3.2's 108°–163° single-cell phase-error estimate | `CALCULATED`, resting on the two assumptions immediately above — explicitly not a bound, an order-of-magnitude estimate |
| The inductive channel's dilution with block size N is unknown | `LITERATURE-SUPPORTED` negative finding — no retrieved source measures or models this |
| Example 4/5/7 pitches (0.071λ, 0.2λ, 0.2λ) fall below Costanzo's tested floor and near/below Budhu & Grbic's qualitative-failure pitch | `CALCULATED` (pitches) / `LITERATURE-SUPPORTED` (Budhu & Grbic's qualitative finding, arXiv:2211.11588) |
| No quantified coupling-error source exists at 0.07–0.2λ pitch | `LITERATURE-SUPPORTED` negative finding — absence across every source reachable in this and the prior two research passes, not proof of absence in the field at large |

---

## 7. Sources

1. S. Costanzo, F. Venneri, G. Di Massa, "Modified Minkowski Fractal Unit Cell for
   Reflectarrays with Low Sensitivity to Mutual Coupling Effects," *International
   Journal of Antennas and Propagation* **2019**, Art. 4890710, DOI
   [10.1155/2019/4890710](https://doi.org/10.1155/2019/4890710). The X-band
   Δφ_max-versus-pitch table (§1, §2).
2. S. An, B. Zheng, M. Y. Shalaginov *et al.*, "Deep Convolutional Neural Networks to
   Predict Mutual Coupling Effects in Metasurfaces," arXiv:
   [2102.01761](https://arxiv.org/abs/2102.01761); *Adv. Optical Mater.* **10**(3),
   2102113 (2022). The only published error-versus-neighbour-count curve (§1, §2.4).
3. N. I. Landy, S. Sajuyigbe, J. J. Mock, D. R. Smith, W. J. Padilla, "A Perfect
   Metamaterial Absorber," arXiv:[0803.1670](https://arxiv.org/abs/0803.1670);
   *Phys. Rev. Lett.* **100**, 207402 (2008). The geometry US12089385B2 Example 3
   reproduces; source of the 4% FWHM used for the Q estimate in §3.2.
4. W. Withayachumnankul, C. Fumeaux, D. Abbott, "Compact electric-LC resonators for
   metamaterials," arXiv:[1009.0139](https://arxiv.org/abs/1009.0139); *Optics Express*
   **18**(25):25912–25921 (2010). The measured fixed-outline interior-tuning alphabet
   (§2.1).
5. W. Withayachumnankul, C. Fumeaux, D. Abbott, "Effects of mutual coupling in
   dual-resonance metamaterials," arXiv:[1109.0055](https://arxiv.org/abs/1109.0055)
   (2011). The control experiment behind §3's inductive-channel estimate.
6. J. Budhu, N. Ventresca, A. Grbic, "Unit Cell Design for Aperiodic Metasurfaces,"
   arXiv:[2211.11588](https://arxiv.org/abs/2211.11588). The qualitative
   local-periodicity-failure data point at 0.150λ pitch (§1, §4).
7. J. Skarda, R. Trivedi, L. Su *et al.*, "Low-overhead distribution strategy for
   simulation and optimization of large-area metasurfaces," arXiv:
   [2107.09879](https://arxiv.org/abs/2107.09879). Aspect-ratio corroboration for why
   thin printed elements need more than one ring of neighbours (§2.4).
8. M. Haji-Ahmadi, V. Nayyeri, M. Soleimani, O. M. Ramahi, "Pixelated Checkerboard
   Metasurface for Ultra-Wideband Radar Cross Section Reduction," *Sci. Rep.*
   **7**:11437 (2017), DOI
   [10.1038/s41598-017-11714-y](https://doi.org/10.1038/s41598-017-11714-y). Primary
   confirmation of the 180° ± 37° / 10 dB criterion used in §2.3.
9. US Patent **US12089385B2**, "Highly-conformal, pliable thin electromagnetic skin,"
   Zaghloul, Nguyen & Adler (US Army DEVCOM). Examples 3, 4, 5 and 7 geometry (§4).

Full coupling background: [`local-periodicity-coupling-error.md`](./local-periodicity-coupling-error.md).
Block-size derivation this document reuses and extends:
[`supercell-sizing-rule.md`](./supercell-sizing-rule.md),
[`ishape-interior-tuning.md`](./ishape-interior-tuning.md).
Anchor-example geometry: [`seven-example-design-unknowns.md`](./seven-example-design-unknowns.md).
