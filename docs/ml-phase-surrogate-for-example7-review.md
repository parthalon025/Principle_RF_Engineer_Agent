# Can an ML phase surrogate replace a Floquet solve for Example 7's tile phases?

**Date:** 2026-09-13
**Ticket:** [#202](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/202) — opened by `docs/ai-metasurface-survey-against-the-seven-examples.md` §4; part of the wayfinder map [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104).
**Question:** Is an ML phase surrogate accurate enough to stand in for the Floquet solve when populating Example 7's tile-phase lookup — and if so, at which RCS-reduction requirements?
**Scope:** decision only. Nothing is built here, and nothing in this document authorises building anything.

---

## Bottom line up front

**No — and the reason is not accuracy. The surrogate is accurate enough and
still must not be used, because it is priced for a problem Example 7 does not
have.**

Three numbers settle it, and none of them is the 2°.

| | |
|---|---|
| What the corpus costs | **80,000 full-wave unit-cell solves** (70,000 train + 10,000 validate), each one a periodic/Floquet solve of a single cell |
| What it replaces | **2 Floquet solves** — Example 7 needs the reflection phase of exactly two tile types |
| Break-even | **80,000 distinct tile geometries**, within one fixed substrate stack, thickness and band. Example 7 needs two. The surrogate is over-provisioned by **40,000×** |

*In plain terms: this is buying a 56-day factory run to avoid two minutes of
work. The machine it builds is genuinely good at what it does — it can pick a
tile out of eighteen billion billion possibilities in about a second — but
Example 7 does not need to search eighteen billion billion tiles. It needs to
know the reflection phase of two shapes the patent already draws.*

**And the accuracy figure the ticket leans on is not the quantity the ticket
treats it as.** Read at the primary source, the claim is *"an accuracy of
90.05% of phase responses with 2° error in the 360° phase"* — that is **the
fraction of predictions that land inside a 2° window**, not a mean error, not
an RMS, and not a worst case. About **one prediction in ten misses by more than
2°, by an amount nobody published.** A checkerboard needs two phases right at
once, so on those odds roughly **one proposed tile pair in five** (1 − 0.9005²
= 19%) carries at least one uncharacterised error. Against a criterion written
as a *guarantee* ("at least 10 dB"), a ninetieth-percentile figure does not
discharge the budget — the tail does, and the tail is unpublished.

**Five things this settles, and two it does not:**

| | Answer |
|---|---|
| Is the 2° figure real? | **The number is real; its meaning was mis-read.** It is a 90.05th-percentile tolerance hit-rate, not an error magnitude. And the survey's "90.5%" is a transcription slip for **90.05%**. §1 |
| Is the 180 ± 37° criterion solid? | **Yes, and better than literature-supported — it is independently derivable.** `supercell-sizing-rule.md` reproduces 36.87° from first principles. Its *origin*, Chen, Balanis & Birtcher (2015), is unreachable; that no longer matters. §2 |
| Over how many candidate designs does it amortise? | **Candidate count is the wrong denominator.** In this loop candidates cost no Floquet solves at all. The right denominator is *distinct tile geometries*, and break-even is 80,000. §3 |
| Does it survive the finite-aperture problem? | **It neither helps nor hurts — it is error-neutral on that axis.** It predicts the same Floquet phase the solver does and inherits the same blind spot. §4 |
| At which reduction levels is it admitted? | **Rule in §6.** Never as a substitute; as a screen only, only above 80,000 geometries, and only at requirements ≤ 15 dB — above which the surrogate is not the binding term anyway. |
| The shape of the 9.95% tail | **Unresolved, and unresolvable from here.** The paper is Wiley-closed with no repository copy anywhere. §7 |
| Whether the field's criterion is sometimes tightened to ±18° | **Unverified.** Reported by one search summary only; if true, the 15 dB line in §6 moves down. §2.3 |

---

## 1. The primary source, read as far as it can be read

**Q. Zhang, C. Liu, X. Wan, L. Zhang, S. Liu, Y. Yang & T. J. Cui,
"Machine-Learning Designs of Anisotropic Digital Coding Metasurfaces,"
*Advanced Theory and Simulations* **2**(2), 1800132 (2019), doi
[10.1002/adts.201800132](https://doi.org/10.1002/adts.201800132).**

**The full text could not be obtained, and this is a positive finding rather
than a fetch failure.** Unpaywall (queried 2026-09-13) returns
`"is_oa": false`, `"oa_status": "closed"`, `"has_repository_copy": false`,
`"oa_locations": []`, `"best_oa_location": null`. Semantic Scholar returns
`"status": "CLOSED"` with an empty PDF URL. Wiley returned HTTP 403 to both
the `onlinelibrary` and `advanced.onlinelibrary` hosts. Two independent
open-access indexes agree that no free copy exists. → `RUNNING-LISTS.md` §1.

What *was* obtained is the **publisher-deposited abstract in full** (via the
Semantic Scholar graph API, which serves Wiley's own deposit) and a
**technically detailed independent account** of the paper in a review. Those
two together settle the metric question without the full text.

### 1.1 The abstract, verbatim

> "Digital coding representations of meta-atoms make it possible to realize
> intelligent designs of metasurfaces by means of machine learning algorithms.
> Here, a machine-learning method to design anisotropic digital coding
> metasurfaces is proposed, and meta-atoms may require any absolute phase
> values at different positions and under different polarizations. A
> deep-learning neural network to predict the vast and complex system is
> proposed, in which **only 70 000 training coding patterns are used to train
> the network. Another 10 000 randomly chosen coding patterns are employed to
> validate the neural network, showing an accuracy of 90.05% of phase
> responses with 2° error in the 360° phase.** Using the learned network, the
> correct coding pattern among **18 billion of billions** of choices for the
> required phase can be readily found in a second, finishing automatic design
> of anisotropic meta-atoms. Three functional 1-bit anisotropic coding
> metasurfaces are intelligently achieved by the learned network. It is
> convenient to realize **dual-beam scattering** with left-handed circular
> polarization (LHCP) for one beam while right-handed circular polarization
> (RHCP) for the others, dual-beam scattering with circular polarization for
> one beam while linear polarization (LP) for the others, and **triple-beam
> scattering** with LHCP and RHCP for two beams while LP for the third one."

`LITERATURE-SUPPORTED` (publisher-deposited abstract, read first-hand).

### 1.2 The independent account, verbatim

**K. V. Mishra, A. M. Elbir & A. I. Zaghloul, "Machine Learning for
Metasurfaces Design and Their Applications," Chapter 14,
[arXiv:2211.01296](https://arxiv.org/abs/2211.01296) (2022)** — retrieved in
full and text-extracted with PyMuPDF. Their reference [73] is our paper.

> "In [73], a CNN predicted the reflection phase response of binary coded
> meta-atoms where **each meta-atom contains 16-by-16 square sub-pixels and is
> mirrored with two-fold symmetry**. The CNN used in this study is a
> **101-layer deep residual network, known as Resnet-101**. The authors found
> that other networks with fewer layers resulted in less precise and robust
> performance predictions. The results show an accuracy of 90.05% of phase
> responses with 2° error in the 360° phase. A drawback of this binary coding
> approach is that a 16-by-16 pixel meta-atom has 2^16 potential design
> combinations. **This study generated training data by simulating randomized
> pixel matrices.** However, it was fundamentally inefficient in an analogous
> manner to GA because the training data is essentially random and does not
> contain the knowledge of canonical structures in the training data set. This
> likely results in significantly more required training data and greater
> network complexity. Another drawback of this study is that **it required
> full-wave simulation of 70,000 training examples 10,000 test examples to
> generate the training dataset.**"

*(Worth noting for whoever reads this next: these authors are at **DEVCOM Army
Research Laboratory** — the same organisation that holds US12089385B2, the
patent this programme is reproducing. The most detailed account of this
surrogate available to us comes from the patent's own assignee.)*

**This is the sentence that prices the decision:** *"it required full-wave
simulation of 70,000 training examples 10,000 test examples."* The ticket's
80,000-solve figure is confirmed — at one remove, by a reviewer who clearly
read the paper, not by the paper itself.

### 1.3 What "90.05% with 2° error" actually means, and why it matters

Both sources use the same construction: *an accuracy of 90.05% of phase
responses **with 2° error** in the 360° phase*. The 2° is the **window**; the
90.05% is the **hit rate inside it**. So:

- it is **not** a mean absolute error;
- it is **not** an RMS error;
- it is **not** a worst case;
- it **is** the 90.05th percentile of the absolute phase error, evaluated on
  10,000 held-out patterns, stated on a 360° wrapped scale.

**9.95% of predictions — about 995 of the 10,000 — miss by more than 2°, and
neither the abstract nor the review says by how much.** On a wrapped 360°
phase the arithmetic maximum is 180°.

*In plain terms: the advertised figure says "nine times out of ten I am within
two degrees." It says nothing at all about the tenth time. A design criterion
that reads "at least 10 dB, guaranteed" is a promise about the worst case, and
you cannot keep a worst-case promise with a nine-out-of-ten statistic.*

This is corroborated from a second direction. The nearest comparable work from
the same community — **Liu *et al.*, "Phase-to-pattern inverse design paradigm
for fast realization of functional metasurfaces via transfer learning,"
*Nature Communications* **12**, 2974 (2021),
[PMC8137937](https://pmc.ncbi.nlm.nih.gov/articles/PMC8137937/)**, retrieved —
reports *"an accuracy of around 90%"* for phase prediction and treats the
problem as **classification over discretised phase bins with a softmax
cross-entropy loss**, not as regression with a reported error magnitude. The
whole sub-field reports a hit rate, not an error bar. `LITERATURE-SUPPORTED`.

### 1.4 Two corrections to the repo's own record

**(a) The figure is 90.05%, not 90.5%.**
`docs/ai-metasurface-survey-against-the-seven-examples.md` §2 and §4 carry
"90.5%" twice, traced to the Boulaich *et al.* survey. The publisher's own
abstract and the Mishra *et al.* review independently both give **90.05%** — a
decimal-place slip somewhere between the primary and the survey. It changes
nothing numerically (both are "about nine in ten") but it is the kind of
one-remove transcription drift the survey doc's own provenance ceiling warns
about, now demonstrated rather than hypothesised. `LITERATURE-SUPPORTED`.

**(b) The coding space reconciles to 2⁶⁴, and the review's "2^16" is a slip.**
A 16×16 grid is 256 pixels, not 16 bits. Under two orthogonal mirror planes
(the only reading of "mirrored with two-fold symmetry" that closes the
arithmetic) the free-bit count is 256/4 = **64**, and 2⁶⁴ =
18,446,744,073,709,551,616 — exactly the abstract's **"18 billion of
billions."** `CALCULATED`. This matters beyond pedantry: it pins what the
surrogate is actually for. It is a **topology** surrogate over a 64-bit binary
pixel map, not a parameter surrogate over a handful of lengths.

### 1.5 The scope limit nobody has noted

**The paper never validates its surrogate against an RCS-reduction
criterion.** Its three demonstrations are *dual-beam scattering with LHCP/RHCP*,
*dual-beam with CP and LP*, and *triple-beam with LHCP, RHCP and LP* —
polarisation-controlled beam splitting. Monostatic backscatter reduction does
not appear. So the 2°-at-90% figure was never exercised against the ±37°
budget, by anyone, anywhere. `LITERATURE-SUPPORTED` (from the abstract's own
enumeration of what it demonstrates).

*In plain terms: the surrogate has been shown to aim beams in chosen
directions with chosen polarisations. It has not been shown to make a radar
echo go away. Those use the same underlying number — a reflection phase — but
nobody has checked the second one.*

---

## 2. The criterion: verified, and traced one hop further back than the repo had it

### 2.1 Haji-Ahmadi states it, and cites it

`docs/seven-example-design-unknowns.md` §7 item 5 records that Haji-Ahmadi
*et al.* (2017) was read but treats it as the criterion's source. **Its full
text was fetched this session** ([PMC5595835](https://pmc.ncbi.nlm.nih.gov/articles/PMC5595835/))
and it is a *restatement*, not a derivation. Verbatim, from its Unit Cell
Design Methodology section:

> "It is theoretically proven that a phase difference of 180 ± 37° between the
> reflections from two region provides at least 10 dB monostatic RCS
> reduction"

and it attributes that to its reference **[28]**:

> "Chen W, Balanis CA, Birtcher CR. Checkerboard EBG surfaces for wideband
> radar cross section reduction. IEEE Trans. Ant. & Prop. 2015;63:2636–2645."

So "theoretically proven" is Haji-Ahmadi's characterisation of somebody else's
proof. **The origin is Chen, Balanis & Birtcher (2015), doi
[10.1109/TAP.2015.2414440](https://doi.org/10.1109/TAP.2015.2414440), and it
is unreachable** — Unpaywall: `is_oa: false`, `has_repository_copy: false`,
`oa_locations: []`; Semantic Scholar: abstract publisher-elided, no PDF. → a
second entry for `RUNNING-LISTS.md` §1.

### 2.2 It does not matter, because the criterion is derivable

The ticket's worry — *"a surrogate judged against an unverified tolerance is
two unverified numbers, not one"* — is **answered, and answered better than by
fetching the paper.** `docs/supercell-sizing-rule.md` §2.2 derives the
tolerance from the two-term aperture average:

```
    RCS reduction (dB)  =  20 · log₁₀( sin(δ/2) )
    δ_budget            =  2 · arcsin( 10^(−RCSR_dB/20) )
```

At 10 dB that returns **36.87°** against the literature's 37° — agreement to
**0.13°**. `CALCULATED`. The criterion is therefore not an empirical constant
borrowed on trust; it is arithmetic this programme can and has reproduced. Five
independent statements converge on it (Haji-Ahmadi 2017 at ±37°, Cui *et al.*
2014 at 145°–215°, Ali *et al.* 2019 and Wu *et al.* 2020 both restating ±37°,
all four already verified in `docs/example7-coding-metasurface-scoring-recipe.md`
§1.2) plus this derivation as a sixth, first-principles route.

**Verdict on ticket item 2: the criterion is solid.** Promote its standing from
`LITERATURE-SUPPORTED` at one remove to **`CALCULATED`, corroborated by five
independent literature statements.** The only thing still unreachable is the
paper that first wrote it down, and nothing depends on it.

What *is* assumed by the formula, and is load-bearing: equal-area alternating
tiles, equal reflection magnitude (|Γ| = 1 for both tiles), and the two-term
aperture average. `docs/supercell-sizing-rule.md` §6 already lists all three as
limits. Printed MXene and carbon are lossy, so the equal-magnitude assumption
is the weakest of them — and that is a real gap, unrelated to the surrogate.

### 2.3 One unverified complication, named because it would move the answer

The Murugesan & Selvan abstract (§4 below) says, verbatim, that *"a set of
modified criteria recently proposed are used for the FR4 substrate-based
designs."* A search summary — **and only a search summary, no primary text** —
reported those modified criteria as constricting to **180 ± 18°** in the lower
frequency band and relaxing to **180 ± 48°** in the higher band, to maximise
bandwidth. The candidate source (Murugesan & Selvan, *Int. J. RF Microw.
Comput.-Aided Eng.* **31**, e22686, 2021, doi
[10.1002/mmce.22686](https://doi.org/10.1002/mmce.22686)) is Wiley-closed
(Unpaywall `closed`, no repository copy) and its Semantic-Scholar abstract
contains no such numbers. **`UNKNOWN` — treat the ±18°/±48° figures as
unverified.**

But the arithmetic is worth recording because it cuts the right way:
`CALCULATED`

| Tolerance | The reduction it corresponds to |
|---|---|
| 180 ± 18° | **16.11 dB** |
| 180 ± 37° | **9.97 dB** |
| 180 ± 48° | **7.81 dB** |

So if those figures are real, the "modified criteria" are **not a correction to
the formula — they are the same formula read at two different dB thresholds**,
demanding ~16 dB low in the band and accepting ~7.8 dB high in it to buy total
bandwidth. That *strengthens* §2.2's formula rather than challenging it: the
field is using it as a per-sub-band budget allocator. It does, however, mean a
real requirement can legitimately tighten the working tolerance to ~18° over
part of the band, which is where §6's rule has to be careful.

---

## 3. The amortisation — and why the ticket's denominator is the wrong one

### 3.1 Candidates do not cost Floquet solves in this loop

The ticket asks *"over how many candidate designs does an 80,000-solve corpus
amortise."* **That question has no answer, because in this programme's own
Example 7 recipe a candidate design costs zero Floquet solves.**

`docs/example7-coding-metasurface-scoring-recipe.md` §1.1 is explicit about
where the cost sits:

> "**Step 1 — per-tile Floquet lookup (cheap, done once per element in the
> library).** One one-port, PEC-backed Floquet solve per tile type `k` gives
> `∠Γ_k(f)` across the requirement band."

and for the per-candidate evaluation:

> "**Step 3 — aperture-level score, closed form, no full-wave.**"
> "the GA/PSO/random-search optimizer's fitness function is Step 3 (cheap,
> closed-form or ML-surrogate-accelerated, evaluated per candidate across the
> whole population) — **never a full-wave solve per candidate**"

A candidate in Example 7 is a **tile-assignment matrix**. Changing the
assignment changes no geometry, so it needs no new phase. Evaluating ten
thousand arrangements of the same two tiles costs the same two Floquet solves
as evaluating one. **The solve count scales with the number of distinct tile
geometries, not with the number of candidates.**

This is the same `O(shapes)`, never `O(letters)` structure ADR-0039 decision 1
already committed to for the fast tier.

### 3.2 The break-even, computed against the right denominator

Let `G` be the number of **distinct tile geometries** whose Floquet reflection
phase the design needs, within **one fixed substrate stack, thickness and
frequency band**. `CALCULATED` throughout:

| Route | Floquet solves | Notes |
|---|---|---|
| **ML surrogate** | **80,000**, once | 70,000 train + 10,000 validate, per §1.2 |
| Example 7 as the patent draws it | **2** | Two ring-pair variants, `docs/seven-example-design-unknowns.md` §5 |
| Example 7 on the fast tier's empirical curve | **≈ 5–20** | ADR-0039 decision 4: *"run a handful of Floquet solves across its parameter range and fit an empirical curve"* |
| GA over the **arrangement** (the actual optimisation) | **+0** | §3.1 |
| GA over the **tile topology** at 10 × 100 generations | **≈ 1,000** | illustrative; each new topology is one solve |

**Break-even is `G* = 80,000`.** Against each route:

- versus the patent's two tiles: **40,000× over-provisioned**;
- versus the fast tier's empirical curve: **4,000–16,000× over-provisioned**;
- versus a thousand-topology direct search: **80× over-provisioned**.

In wall-clock, using the only per-solve timing this literature publishes —
Zhang, Zou, Guo, Zhao & Shen (2025), already retrieved and quoted in
`docs/ai-metasurface-survey-against-the-seven-examples.md` §3: *"The full-wave
simulation for each unit cell required approximately 1 min"* — 80,000 solves is
**1,333 solver-hours ≈ 55.6 days serial**, against roughly **two minutes** for
the patent's two tiles. `CALCULATED`. **Report this as solver-hours, not
CPU-hours**: no core count is published, and the 1 min/cell figure belongs to a
*different* paper's solver and cell, so it is an order-of-magnitude anchor, not
Zhang 2019's own timing. Zhang 2019 publishes no timing at all.

### 3.3 The corpus does not transfer; the closed form does

This is the part that makes the verdict structural rather than merely
arithmetic, and it is not in the ticket.

**A trained surrogate learns one stack.** Its 80,000 solves were run at one
substrate permittivity, one thickness, one metal, one band. Change any of them
and the network's mapping from pixel map to phase is wrong, and the corpus has
to be regenerated from scratch. There is no `ε_r` you can turn.

**The fast tier's closed form carries those as symbols.** ADR-0039 decision 1
commits to *"one Floquet solve per shape family … and closed-form algebra
(Luukkonen/Tretyakov for patches and strip grids, Costa et al. for the absorber
stack) covers every size, substrate, angle and loss variation after that."*
Substrate permittivity, spacer thickness and frequency are arguments, not
training conditions.

**This programme has not fixed its substrate.** `docs/xband-absorber-substrate-shortlist.md`
carries a main shortlist plus a separate set of deliberately-lossy candidates
across two distinct curvature regimes. Every candidate on that list that the
loop might want to compare would need its own 80,000-solve corpus. **The
multiplier on the surrogate's bill is the length of the substrate shortlist;
the multiplier on the closed form's bill is one.** `INFERRED` — this is our
synthesis of ADR-0039's decision and the shortlist's structure, not a claim
either document makes.

*In plain terms: the closed-form model is a formula with the substrate as a
dial you can turn. The trained network is a photograph of one particular
substrate. If you are still choosing between substrates — and we are — the
formula is the only one of the two that survives the choice.*

### 3.4 The verification trap

Suppose the corpus existed and the surrogate were free to query. Because the
tail is uncharacterised (§1.3), a surrogate-predicted phase cannot be trusted
into a score that claims a guarantee. So it must be Floquet-confirmed before
use. **For a two-tile design, confirming it costs two Floquet solves — exactly
the cost the surrogate was bought to avoid.**

The surrogate can only pay when there are far more candidate geometries than
finalists, i.e. when it is a *screen* over a large topology space. That is a
real use. It is not Example 7's use.

---

## 4. The finite-aperture problem: the surrogate is error-neutral on it

**Answer to ticket item 4: the blind spot is real, and the surrogate neither
creates, worsens nor inherits extra of it. A per-tile phase surrogate predicts
exactly the quantity a per-tile Floquet solve predicts — the infinite-array
reflection phase. Swapping one for the other moves no error on this axis at
all.** The finite-aperture/mutual-coupling error is a property of the *local
periodicity assumption*, which both routes make identically. It is already
fully documented in `docs/local-periodicity-coupling-error.md`, and nothing
about the surrogate changes a line of it.

`INFERRED` — reasoning from what each route computes, not a claim any source
makes.

Haji-Ahmadi *et al.* name the assumption explicitly, verbatim:

> "the reflection phase from each tile can be approximated by that from an
> infinite periodic structure… This approximation allow for efficient
> simulation by using a periodic boundary condition (PBC) applied only on one
> unite cell."

and run the two-stage method the repo already records — Floquet with CST's
frequency-domain solver for the optimisation, then *"a checkerboard-like
metasurface … formed by 4 × 4 alternating AMC tiles where each tile consists of
4 × 4 identical unit cells … the overall size of the RCS reducer surface is
224 mm × 224 mm"* for validation. `LITERATURE-SUPPORTED` (full text retrieved
this session).

### 4.1 Murugesan & Selvan says more than the repo records, and it is good news

`docs/seven-example-design-unknowns.md` §5 and
`docs/example7-coding-metasurface-scoring-recipe.md` §4 both quote one sentence
of this abstract. **The complete publisher-deposited abstract was retrieved
this session via the Crossref API and contains two further sentences that
change the reading.** Verbatim, the whole relevant passage:

> "**The 8 and 10 dB RCS reduction bandwidths drop as array size increases. The
> bandwidth reduction is attributable to mutual coupling**, as has been
> reported in an earlier study. **As therefore expected, all of the three
> structures, for all sizes, present the same RCS reduction bandwidth when a
> mutual coupling mitigation technique is incorporated. For 10 dB RCS reduction
> bandwidth, this value approaches that estimated by using a mutual coupling
> independent semi-empirical equation that holds for infinite arrays.**"

— A. Murugesan & K. T. Selvan, "On the effect of array size on the radar cross
section reduction bandwidth of checkerboard metasurfaces," *Frequenz* **77**(5–6),
273–279 (2023), doi [10.1515/freq-2022-0021](https://doi.org/10.1515/freq-2022-0021).
Array sizes studied: 120, 240 and 480 mm², plus 600 mm² for one structure; one
structure on Rogers, two on FR4. `LITERATURE-SUPPORTED` (publisher-deposited
abstract, complete as an abstract; **full text still stranded** — De Gruyter
returns a bot challenge, Unpaywall `closed`, no repository copy).

Two consequences, and the second is the useful one:

1. **The array-size dependence is a coupling artefact, not a law.** With a
   coupling-mitigation technique applied, *all* sizes give the *same*
   bandwidth. So the effect is removable in principle.
2. **Under mitigation, the 10 dB bandwidth converges on the infinite-array
   estimate.** That is a direct statement that the Floquet/infinite-array
   prediction — the thing a phase lookup *is* — is **recoverable**, not
   systematically wrong. It is conditionally valid, conditional on coupling
   mitigation.

*In plain terms: the earlier reading was "a big checkerboard works worse than
an infinite one, so the infinite-array calculation lies." The full abstract
says something weaker and more useful — the big checkerboard works worse
because its elements are talking to each other, and when you stop them talking,
the infinite-array calculation is right again.*

**What the abstract does not say, and is the gap:** *which* mutual-coupling
mitigation technique, and what the "mutual coupling independent semi-empirical
equation" is. Both would be directly useful to
`docs/example7-coding-metasurface-scoring-recipe.md` §4's open item 1, which
records that *"no closed-form model exists for how mutual-coupling
bandwidth-narrowing scales with array size."* That open item should now read
"a semi-empirical equation exists and is named in an abstract we cannot read."
→ `RUNNING-LISTS.md` §1, raised in priority: the full text would close a gap
this programme has carried through three documents.

---

## 5. The phase-error stack — and why the surrogate is never the binding term

The ticket's table compares the surrogate's error against the whole budget, as
if the surrogate were the only thing spending it. It is not. Example 7's own
scoring recipe (§1.1, Step 2) already sums two terms, and a surrogate would add
a third:

```
    δ(f) = |180° − (∠Γ₁(f) − ∠Γ₂(f))|   ← dispersion across the band
           + Δφ_max · f(N)               ← unlike-neighbour coupling error
           + ε_surrogate                 ← new, if a surrogate populates the lookup
```

And `ε_surrogate` is **up to 4°, not 2°**: each tile carries its own error, and
`docs/supercell-sizing-rule.md` §6 already makes exactly this point for the
coupling term — *"If the two block types are perturbed in opposite directions
the phase difference error could approach twice that."* Two tiles each 2° off
in opposite directions is a 4° error on the *difference*, which is the quantity
the budget governs.

### 5.1 Read as ceilings, not margins

The cleanest way to see which term binds is to invert the formula: each error
source, on its own, sets a **hard ceiling** on achievable reduction.
`CALCULATED`, from `20·log₁₀(sin(δ/2))`:

| Error source | δ | Ceiling on RCS reduction |
|---|---|---|
| ML surrogate, one tile, inside its 2° window | 2° | **35.2 dB** |
| ML surrogate, both tiles at 2°, opposing | 4° | **29.1 dB** |
| Coupling — interior-tuned cell, 0.5 λ pitch, N = 4 | 9° | **22.1 dB** |
| Coupling — interior-tuned cell, 0.5 λ pitch, N = 2 | 12° | **19.6 dB** |
| Coupling — Minkowski fractal, 0.5 λ, N = 2 | 21° | **14.8 dB** |
| Coupling — variable-size square patch, 0.5 λ, N = 2 | 25° | **13.3 dB** |
| Coupling — variable-size square patch, 0.4 λ, N = 2 | 85° | **3.4 dB** |

(Coupling figures are `docs/supercell-sizing-rule.md`'s Δφ_max values, which
trace to Costanzo, Venneri & Di Massa, *IJAP* 2019, Table 3 —
`LITERATURE-SUPPORTED`, `SIMULATED` at source.)

**The coupling term binds first, and by a wide margin.** With the *best*
published alphabet at the *best* pitch, coupling alone caps the design at
19.6–22.1 dB. The surrogate's worst-in-window contribution caps it at 29.1 dB.
**The surrogate is never the limiting term below about 22 dB, and above about
22 dB nothing in this programme's available alphabet reaches the requirement
anyway.**

*In plain terms: arguing about whether a two-degree prediction error is
acceptable is arguing about the second-smallest leak in the bucket. The big
leak is that neighbouring tiles disturb each other by ten to twenty-five
degrees, and that leak is there whether a network or a solver filled in the
phases.*

### 5.2 The stack as a share of budget

Surrogate (4°) plus best-case coupling (12° at N = 2): 16° total.
`CALCULATED`:

| Requirement | 6 dB | 10 dB | 15 dB | 20 dB | 30 dB |
|---|---|---|---|---|---|
| δ_budget | 60.2° | 36.9° | 20.5° | 11.5° | 3.6° |
| Coupling alone (12°) | 20% | 33% | 59% | **105%** | **331%** |
| Surrogate alone (4°) | 7% | 11% | 20% | 35% | **110%** |
| **Both (16°)** | **27%** | **43%** | **78%** | **139%** | **442%** |
| Left over for band dispersion | 44.2° | 20.9° | 4.5° | none | none |

The last row is the decisive one. **Dispersion is what "bandwidth" means** —
the two tiles' phases drift apart from 180° as you move off the design
frequency, and the width of the band where they stay inside budget *is* the RCS
reduction bandwidth. At 15 dB there is 4.5° left for it; at 20 dB there is
nothing left at all before the surrogate is even considered.

**So the honest statement of the ticket's headline comparison is: the ticket's
table is arithmetically correct and premised wrongly.** 36.9/2 = 18.4, so "18×
margin at 10 dB" checks out — but it is 18× margin against *one* error term
considered alone, at its ninetieth percentile, with nine other degrees of
coupling error and all of the band dispersion left out.

---

## 6. The decision, as a rule the loop can apply

**Verdict: not admissible as a substitute for the Floquet solve, at any
reduction requirement. Admissible as a screen, narrowly.**

The reason is amortisation, not accuracy. Stated so it can be applied:

```
Let G = the number of DISTINCT TILE GEOMETRIES whose Floquet reflection
        phase a candidate family needs, within one fixed substrate stack,
        thickness and frequency band.
        (NOT the number of candidate designs — arrangements are free.)

RULE 1 — the default, and it covers Example 7 as specified.
  IF G < 80,000
  THEN an ML phase surrogate is NOT admissible in place of the Floquet
       solve. Run the G solves. Record the reason as cost, not accuracy.
  Example 7 as the patent draws it: G = 2.  Rule 1 applies.
  Example 7 on the fast tier's empirical curve: G ≈ 5–20.  Rule 1 applies.

RULE 2 — the narrow opening, for a genuine topology search.
  IF G ≥ 80,000 — which requires searching the tile's own internal
     topology, not its dimensions — AND the substrate stack, thickness
     and band are FIXED for the whole corpus
  THEN a surrogate is admissible as a SCREEN only:
       (a) its output ranks candidates; it never enters a reported score;
       (b) every finalist's phase is Floquet-confirmed before scoring;
       (c) admitted only where the stated requirement is <= 15 dB.

RULE 3 — the ceiling on Rule 2, and why it is 15 dB.
  Above ~15 dB the phase-error stack (coupling + dispersion) already
  consumes the budget with or without a surrogate — 78% of budget at
  15 dB, over 100% at 20 dB, with the best published alphabet. Above
  ~22 dB no available alphabet reaches the requirement at all. So a
  surrogate cannot help there, and admitting it would imply a precision
  the design does not have.
  If a requirement tightens the working tolerance to ~18° over part of
  the band (section 2.3, UNVERIFIED), drop the Rule 2 ceiling to 10 dB.

RULE 4 — unconditional, and it is ADR-0027 restated.
  A surrogate-predicted phase is never MEASURED, never SIMULATED, and
  never admits a letter to the Element/Coding-Alphabet library. It is
  CALCULATED at best, and the shape it describes is a NEW ELEMENT —
  a hypothesis with a test attached — until it is printed and measured.
```

**One thing Rule 2 would still need before it could be used, and does not
have: the tail.** Until someone publishes the distribution of the 9.95% of
predictions that fall outside 2°, even a screen's ranking is unquantified.
Rule 2 is therefore written as available-in-principle, not ready.

### 6.1 What would change this verdict

- **A published tail distribution** for a phase surrogate of this class —
  worst case, or a percentile curve rather than a single hit rate. That alone
  would not flip Rule 1 (the cost argument is independent) but it is the
  precondition on Rule 2.
- **A requirement that genuinely needs a topology search.** If a real
  requirement cannot be met by any dimensional variation of a characterised
  element and needs a pixel-level topology search over five figures of
  candidates, `G` crosses 80,000 and Rule 2 activates.
- **A fixed substrate.** Rule 2's condition (b) on a fixed stack is currently
  unsatisfiable — the substrate shortlist is still a shortlist.
- **A much cheaper corpus.** `docs/ai-metasurface-survey-against-the-seven-examples.md`
  §3 already identifies the lever: *"the lever that shrinks the bill is
  constraining the geometry encoding."* A 64-bit topology space is the whole
  reason the bill is 80,000. A tighter encoding would lower break-even
  directly, and transfer learning (Liu *et al.* 2021, §1.3) reportedly reaches
  the same ~90% at 20,000 samples rather than 70,000 — a 3.5× cut, still two
  orders of magnitude above `G` for Example 7.

---

## 7. Every route tried

**Succeeded:**

| Route | Result |
|---|---|
| Semantic Scholar graph API, DOI `10.1002/adts.201800132` | **The publisher-deposited abstract in full** — the 90.05% / 2° / 70,000 / 10,000 / "18 billion of billions" sentences, verbatim. §1.1 |
| arXiv:2211.01296 (Mishra, Elbir & Zaghloul), PDF → PyMuPDF text extraction | **The decisive independent account**: ResNet-101, 16×16 sub-pixels, two-fold mirror symmetry, *"required full-wave simulation of 70,000 training examples 10,000 test examples."* §1.2 |
| PMC5595835 (Haji-Ahmadi *et al.* 2017), full text | Criterion verbatim **and its citation to Chen, Balanis & Birtcher [28]** — the repo had it as the source; it is a restatement. §2.1 |
| Crossref API, DOI `10.1515/freq-2022-0021` | **The complete abstract, two sentences longer than the repo's quote** — coupling mitigation restores size-independence and convergence to the infinite-array estimate. §4.1 |
| PMC8137937 (Liu *et al.*, *Nat. Commun.* 2021) | Independent confirmation that this sub-field's "~90% accuracy" is a binned-classification hit rate, not an error magnitude. §1.3 |
| Unpaywall, DOIs `10.1002/adts.201800132`, `10.1109/TAP.2015.2414440`, `10.1515/freq-2022-0021`, `10.1002/mmce.22686` | All four **closed, no repository copy** — positive findings, not fetch failures |
| `docs/supercell-sizing-rule.md` formula, re-evaluated | 36.87° at 10 dB vs the literature's 37°; and ±18°/±48° ≡ 16.11 dB/7.81 dB. §2.2, §2.3 |

**Failed, and why:**

| Route | Outcome |
|---|---|
| **Zhang *et al.* 2019 full text** — `onlinelibrary.wiley.com/doi/full/...` and `advanced.onlinelibrary.wiley.com/doi/abs/...` | **HTTP 403 on both hosts.** Unpaywall `is_oa: false`, `has_repository_copy: false`, `oa_locations: []`; Semantic Scholar `CLOSED`. **No free copy exists.** Costs us: the tail distribution, the exact metric definition, the substrate and frequency, and whether the 70,000 solves were at one frequency or a band |
| **Chen, Balanis & Birtcher 2015** (the criterion's true origin) | **Closed, no repository copy.** Abstract publisher-elided at Semantic Scholar. Does not matter — §2.2 derives the criterion |
| **Murugesan & Selvan 2023 full text** | De Gruyter bot challenge; unchanged from the prior pass. The abstract carried the load |
| **Murugesan & Selvan 2021** (`10.1002/mmce.22686`), the candidate source of the ±18°/±48° modified criteria | Wiley closed; Crossref has no abstract; the Semantic Scholar abstract is about fruitfly optimisation and contains no phase-tolerance figures. **The ±18°/±48° numbers remain `UNKNOWN`** |
| **OpenAlex API** | Rate-limited to zero budget for the day (`"Insufficient budget… Resets at midnight UTC"`). Unpaywall and Semantic Scholar covered the same ground. Worth knowing for the next pass: **OpenAlex now metered, Unpaywall and Crossref still free** |
| **PIER review "A Review of Metasurface-Assisted RCS Reduction Techniques"** | Fetched; the landing page carries bibliography only, no body text. No criterion statement recoverable |

---

## 8. Provenance summary

| Claim | Provenance |
|---|---|
| "70,000 training + 10,000 validation, accuracy of 90.05% of phase responses with 2° error in the 360° phase" | **LITERATURE-SUPPORTED** — publisher-deposited abstract, read first-hand; independently restated in Mishra *et al.* |
| The survey's "90.5%" is a slip for 90.05% | **LITERATURE-SUPPORTED** — two independent routes both give 90.05% |
| "2°" is a tolerance window and "90.05%" the hit rate inside it — not a mean, RMS or worst case | **LITERATURE-SUPPORTED** from the sentence's construction, corroborated by Liu *et al.* 2021's binned-classification framing. **Not confirmable at full-text level** |
| 80,000 solves are full-wave | **LITERATURE-SUPPORTED at one remove** — Mishra *et al.* state it; the paper itself is unreadable |
| ResNet-101, 16×16 sub-pixels, two-fold mirror symmetry, randomized pixel matrices | **LITERATURE-SUPPORTED at one remove** — Mishra *et al.* |
| Coding space = 2⁶⁴ = 1.845×10¹⁹, reconciling "18 billion of billions" with 256 pixels under two mirror planes | **CALCULATED** — and it exposes an arithmetic slip ("2^16") in Mishra *et al.* |
| The paper demonstrates dual/triple-beam polarised scattering, never RCS reduction | **LITERATURE-SUPPORTED** — the abstract's own enumeration |
| 180 ± 37° restated by Haji-Ahmadi, originating with Chen, Balanis & Birtcher [28] | **LITERATURE-SUPPORTED** — full text retrieved |
| δ_budget = 2·arcsin(10^(−RCSR/20)); 36.87° at 10 dB; ±18° ≡ 16.11 dB, ±48° ≡ 7.81 dB | **CALCULATED** — reproduces the literature's 37° to 0.13° |
| The ±18°/±48° modified criteria themselves | **UNKNOWN** — one search summary, no primary text. Flagged as the single unverified number that would move §6's ceiling |
| Murugesan & Selvan: bandwidth drops with array size; coupling mitigation restores size-independence; converges to an infinite-array semi-empirical estimate | **LITERATURE-SUPPORTED** — complete publisher-deposited abstract via Crossref. Full text stranded |
| Break-even G* = 80,000 distinct tile geometries; 40,000× over-provisioned for Example 7 | **CALCULATED** from the two solve counts |
| 1,333 solver-hours ≈ 55.6 days serial | **CALCULATED**, using a 1 min/cell anchor from a *different* paper (Zhang *et al.* 2025). Zhang 2019 publishes no timing |
| Candidates cost zero Floquet solves in this loop | **INTERNAL-HISTORY** — `docs/example7-coding-metasurface-scoring-recipe.md` §1.1 Steps 1 and 3, ADR-0039 decision 1 |
| The corpus does not transfer across substrates; the closed form does | **INFERRED** — our synthesis of ADR-0039 decision 1 and the substrate shortlist's structure |
| Surrogate contributes up to 4° to δ, not 2° (two tiles, opposing) | **CALCULATED**, on the doubling argument `docs/supercell-sizing-rule.md` §6 already makes for the coupling term |
| The ceiling table (35.2 / 29.1 / 22.1 / 19.6 / 14.8 / 13.3 / 3.4 dB) | **CALCULATED** from `20·log₁₀(sin(δ/2))`; the Δφ_max inputs are **LITERATURE-SUPPORTED** (Costanzo *et al.* 2019, `SIMULATED` at source) |
| The surrogate is error-neutral on the finite-aperture axis | **INFERRED** — reasoning from what each route computes |
| The admissibility rule in §6 | **INFERRED** — this document's decision, built on the above |

### 8.1 Register updates

**Opens, for `RUNNING-LISTS.md` §1:**

> **Zhang, Liu, Wan, Zhang, Liu, Yang & Cui (2019)**, "Machine-Learning Designs
> of Anisotropic Digital Coding Metasurfaces," *Adv. Theory Simul.* **2**(2),
> 1800132, doi 10.1002/adts.201800132 — Wiley-closed; **Unpaywall and Semantic
> Scholar both confirm no repository copy exists anywhere**. Holds the one thing
> that would let an ML phase surrogate be judged properly: the **distribution of
> the 9.95% of predictions that fall outside the 2° window**. Bears on #202
> (Rule 2's precondition), #191, #132.

> **Murugesan & Selvan (2023)**, *Frequenz* **77**(5–6), 273–279, doi
> 10.1515/freq-2022-0021 — full text still stranded (De Gruyter bot challenge).
> **Raised in priority**: its abstract names a *mutual-coupling mitigation
> technique* that restores array-size independence, and a *mutual-coupling
> independent semi-empirical equation* for the 10 dB bandwidth of an infinite
> array. Either would close the open gap recorded at
> `docs/example7-coding-metasurface-scoring-recipe.md` §4 item 1. Bears on
> #202, #104, #130.

> **Chen, Balanis & Birtcher (2015)**, "Checkerboard EBG Surfaces for Wideband
> Radar Cross Section Reduction," *IEEE Trans. Antennas Propag.* **63**(6),
> 2636–2645, doi 10.1109/TAP.2015.2414440 — closed, no repository copy, abstract
> publisher-elided. The **origin** of the 180 ± 37° criterion. **Low priority**:
> §2.2 derives the criterion independently to within 0.13°, so nothing depends
> on reading it.

**Corrections other documents should carry:**

- `docs/ai-metasurface-survey-against-the-seven-examples.md` §2 and §4:
  **90.5% → 90.05%**, and the figure is a hit rate inside a 2° window, not a 2°
  error. Its §4 caution — *"This comparison is a reason to open that paper, not
  a substitute for opening it"* — was right, and the paper cannot be opened.
- `docs/seven-example-design-unknowns.md` §1 and §7 item 5: the 180 ± 37°
  criterion is **restated** by Haji-Ahmadi *et al.*, who cite it to Chen,
  Balanis & Birtcher (2015). Not a defect — the quote is verbatim and correct —
  but the attribution is one hop short.
- `docs/example7-coding-metasurface-scoring-recipe.md` §1.1 Step 4's last
  bullet calls the Zhang 2019 surrogate *"cheap enough … to sit inside a GA's
  per-candidate evaluation with 5–30× headroom."* **Two things are off there:**
  a surrogate in this loop would populate Step 1's lookup, not Step 3's
  per-candidate fitness (the fitness function is already closed-form and needs
  no phase prediction); and "cheap" prices the query, not the 80,000-solve
  corpus behind it. Its §4 open item 1 should also be softened per §4.1 above.

**Closes:** #202's five questions, with a conditional admissibility rule (§6)
and two named unverified numbers — the surrogate's error tail, and the
±18°/±48° modified criteria.

---

## 9. Sources

1. Q. Zhang, C. Liu, X. Wan, L. Zhang, S. Liu, Y. Yang & T. J. Cui, "Machine-Learning Designs of Anisotropic Digital Coding Metasurfaces," *Advanced Theory and Simulations* **2**(2), 1800132 (2019), doi [10.1002/adts.201800132](https://doi.org/10.1002/adts.201800132). **Abstract only — full text closed, no free copy exists.**
2. K. V. Mishra, A. M. Elbir & A. I. Zaghloul, "Machine Learning for Metasurfaces Design and Their Applications," Chapter 14, [arXiv:2211.01296](https://arxiv.org/abs/2211.01296) (2022). **Retrieved in full.** The detailed account of [1].
3. M. Haji-Ahmadi, V. Nayyeri, M. Soleimani & O. M. Ramahi, "Pixelated Checkerboard Metasurface for Ultra-Wideband Radar Cross Section Reduction," *Scientific Reports* **7**, 11437 (2017), doi [10.1038/s41598-017-11714-y](https://doi.org/10.1038/s41598-017-11714-y), via [PMC5595835](https://pmc.ncbi.nlm.nih.gov/articles/PMC5595835/). **Retrieved in full.**
4. W. Chen, C. A. Balanis & C. R. Birtcher, "Checkerboard EBG Surfaces for Wideband Radar Cross Section Reduction," *IEEE Trans. Antennas Propag.* **63**(6), 2636–2645 (2015), doi [10.1109/TAP.2015.2414440](https://doi.org/10.1109/TAP.2015.2414440). **Closed; cited as the criterion's origin by [3], not read.**
5. A. Murugesan & K. T. Selvan, "On the effect of array size on the radar cross section reduction bandwidth of checkerboard metasurfaces," *Frequenz* **77**(5–6), 273–279 (2023), doi [10.1515/freq-2022-0021](https://doi.org/10.1515/freq-2022-0021). **Complete publisher-deposited abstract via Crossref; full text stranded.**
6. A. Murugesan & K. T. Selvan, "On further enhancing the bandwidth of wideband RCS reduction checkerboard metasurfaces using an optimization algorithm," *Int. J. RF Microw. Comput.-Aided Eng.* **31**, e22686 (2021), doi [10.1002/mmce.22686](https://doi.org/10.1002/mmce.22686). **Abstract only; does not contain the ±18°/±48° figures attributed to this line of work.**
7. C. Liu *et al.*, "Phase-to-pattern inverse design paradigm for fast realization of functional metasurfaces via transfer learning," *Nature Communications* **12**, 2974 (2021), via [PMC8137937](https://pmc.ncbi.nlm.nih.gov/articles/PMC8137937/). **Retrieved.** Independent anchor on what "~90% accuracy" means in this sub-field.
8. M. H. Boulaich, S. Ohamouddou, M. A. Ennasar & A. El Afia, "AI-Assisted Metasurface Antennas Design/Optimization and Performance Enhancement Techniques: A Comprehensive Survey," *IEEE Access* **14**, 29803–29836 (2026), doi [10.1109/ACCESS.2026.3667812](https://doi.org/10.1109/ACCESS.2026.3667812). The survey that raised the question; source of the 90.5% slip.
9. S. Costanzo, F. Venneri & G. Di Massa, "Modified Minkowski Fractal Unit Cell for Reflectarrays with Low Sensitivity to Mutual Coupling Effects," *IJAP* **2019**, Art. 4890710, doi [10.1155/2019/4890710](https://doi.org/10.1155/2019/4890710). Source of every Δφ_max in §5.1, via `docs/local-periodicity-coupling-error.md`.
