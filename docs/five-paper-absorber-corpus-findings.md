# Five metamaterial-absorber papers, read against the printed-skin design loop

**Research date:** 2026-09-07
**Map:** [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104)
**Tickets touched:** ~~#187 (decisively)~~ **#187 (partly, and §1's headline ruling on it was
wrong — corrected 2026-09-10, see the box in §1)**, #110, #128, #129, #130/#138, #111/#190,
#105/#148

## What this is, and how much weight it carries

Five papers were read by a fan-out of 91 agents across two workflow runs: a structured
extraction per paper, five analytical lenses each, a three-vote adversarial refutation round on
each paper's load-bearing claims, a per-paper dossier, four cross-paper syntheses and a
completeness critic. Sixteen claims failed refutation at two or more votes and are not carried
here.

**This is a literature analysis, not a measurement campaign.** Nothing in it is `MEASURED` in
this programme's sense. Four of the five papers are simulation-only; the fifth measured one
fabricated sample, and its numbers still enter as `LITERATURE-SUPPORTED`. *In plain terms: with
one part-exception, no object discussed here has ever been put in front of a real wave.*

**Arithmetic below is `CALCULATED` by the analysis and has not been independently re-derived by
hand**, except where this document says otherwise. Confidence is stated per finding rather than
implied by tone — via a `CONFIDENCE: HIGH/MEDIUM-HIGH/LOW` tag distinct from, and never a
substitute for, `CONTEXT.md`'s provenance ladder. Provenance tags one *data point*'s evidence tier
(`MEASURED`, `CALCULATED`, `LITERATURE-SUPPORTED`, …); `CONFIDENCE` tags this *research
synthesis*'s own certainty in a conclusion drawn across all five papers (e.g. "high confidence the
literature is silent on X," a claim about the search, not about any one number) — a question the
provenance ladder has no rung for and was never meant to answer.

| | Paper | Band | Evidence basis |
|---|---|---|---|
| **P1** | Hanif *et al.*, *Int. J. Optomechatronics* **18**(1):2299026 (2024), Ni-PI-Ni | 380–2300 nm | CST, **simulation-only** |
| **P2** | Xu *et al.*, *Coatings* **14**:799 (2024), Ti/Si/Si₃N₄/SiO₂/Ti | 10.90–22.91 µm | Lumerical FDTD, **simulation-only** |
| **P3** | Zheng, Pham, Chen & Lee, MDPI *Encyclopedia*, bandwidth control | — | **Review adaptation**, no structures |
| **P4** | Osgouei *et al.*, *J. Phys. D* **54**:275102 (2021), ITO–Au | 400–3500 nm | FDTD + EMT/TMM, **simulation-only** |
| **P5** | Fu *et al.*, *Sci. Rep.* **6**:36244 (2016), planar Ti/SiO₂ + filter | 500–2000 nm | **One fabricated, measured sample** |

Per #104, band is a per-requirement input: these are optical and infrared papers, and that
makes them evidence about **physics**, not off-topic material. The analytical unit throughout is
the **validity box** — what a mechanism depends on, over what frequency range it holds, and how
it rescales.

> **But read that table as a coverage statement too.** Five papers, none of them microwave. That
> is fine for the physics findings in §2–§6, which are about mechanisms and rescale. It is fatal
> for a claim about *what the microwave literature does or does not contain* — which is exactly
> the claim §1 originally made, and exactly why it was wrong. The corrected §1 and the fourth
> process failure in §7 record it. First-hand read of the paper this corpus missed:
> [`ozden-broadband-supercell-primary-source.md`](./ozden-broadband-supercell-primary-source.md).

---

## 1. #187 — the ticket this corpus was supposed to settle

> ### CORRECTED 2026-09-10 — the ruling below was wrong, and the root cause is worse than one missed paper
>
> This section originally ruled, at `CONFIDENCE: HIGH`, that **"the published record does not
> contain the experiment #187 asks for ... The absence is the finding."** That claim is false as
> stated, and it was never entitled to be made.
>
> **The root cause: none of the five papers is a microwave paper.** Read the corpus table above —
> P1 is 380–2300 nm, P2 is 10.90–22.91 µm, P3 is a review with no structures, P4 is 400–3500 nm,
> P5 is 500–2000 nm. #187 is an X-band question (8–12 GHz). **A `HIGH`-confidence claim about
> "the published record" for an X-band question was drawn from a corpus that never searched the
> band**, and the §7 rule this document already states — *"a claim of the form 'X is not in the
> repo' must name the commit it was checked at"* — has an obvious analogue that was not applied:
> a claim of the form *"X is not in the literature"* must name the band, database and query it was
> checked against. This one named none of them.
>
> **The experiment exists and has since 2016.** Ozden, Yucedag & Kocer, *"Metamaterial based
> broadband RF absorber at X-band"*, *AEÜ* **70**:1062–1070 (2016),
> doi [10.1016/j.aeue.2016.05.002](https://doi.org/10.1016/j.aeue.2016.05.002) — laterally detuned,
> differently sized coplanar resonators on **one** 0.75 mm FR4 spacer over **one** continuous
> copper ground plane, **no lumped resistors and no resistive film**, with N swept 12 → 16,
> fabricated and measured on a VNA against a control. That is #187's geometry, variable and
> control. Read first-hand in
> [`ozden-broadband-supercell-primary-source.md`](./ozden-broadband-supercell-primary-source.md).
>
> **What it found, and it is two answers to two questions.** On **width** it agrees with the
> repo's bench: *"increasing the number of unit cell in super cell does not change frequency
> bandwidth"* — and the 12-letter tile measured **wider** than the 16-letter tile (2.73 vs
> 2.55 GHz at 80 %). On **depth** it disagrees sharply: *"this increment improves the absorption
> level"*, and a figure read gives a worst-in-band absorptivity of **0.27 (1 letter) → 0.69 (12)
> → 0.79 (16)** over a matched 2.44 GHz window. The likely reconciliation — a hypothesis, not a
> finding — is that Ozden's conductor is loss-free copper (RF surface resistance 26.1 mΩ/sq)
> against this programme's 25–50 Ω/sq printed letters, so his baseline is two sharp peaks with a
> 0.27 hole to fill and the repo's is already loss-broadened to 22.1 % with no hole. §6 of that
> document sets out the test that would settle it.
>
> **What survives from the original ruling**, rescoped: *within these five papers*, nobody runs
> the experiment — which is now an unremarkable statement about five optical and infrared papers
> rather than a finding about the literature. The rescoped table below replaces the original one.
> `CONFIDENCE: HIGH` that these five are silent on it; **no confidence claim about "the published
> record" is made here at all**, because this corpus cannot support one.
>
> Everything else in this document is unaffected — §2 through §6 rest on the papers' own physics,
> not on a claim about what was never published.

**Rescoped ruling: these five papers do not contain the experiment #187 asks for, and they were
never the right place to look for it.** In five papers spanning 380 nm to 22.91 µm — optical and
infrared, not one at microwave — nobody builds *laterally detuned coplanar resonators over a
single uniform spacer height with no added loss material* and reports the bandwidth against a
control. `CONFIDENCE: HIGH about these five papers. No claim is made about the literature.`

**Anyone citing these five papers as showing that a super-cell does or does not buy bandwidth is
citing a paper that never ran the test.** The paper that *did* run it is Ozden *et al.* (2016) —
see the correction above.

**Within the corpus, the record still leans — but it is now a much weaker signal.** Four groups
here all wanted broad bands, all had the shared-spacer geometry available, and none reached for
lateral detuning. Every broadband result *in this corpus* is carried by **loss** or by **vertical
height variety**.

The sharpest datum is **P4**: the group already had four coplanar resonators in one cell over
one spacer at conserved 31.11 % areal fill, and when they wanted 1170 nm of bandwidth they left
the four resonators **identical** — rotating them 45° for polarization symmetry only — and took
the bandwidth from a lossy material instead, dialling it with that material's thickness. A
near-controlled decline to detune. `LITERATURE-SUPPORTED.`

| Question | Ruling | Confidence |
|---|---|---|
| Do these five papers show a super-cell buying bandwidth by lateral detuning? | **No — they show neither way. The test is absent from *this corpus*.** | HIGH about these five |
| Does the *literature* contain the test? | **Yes. Ozden *et al.* (2016), X-band, fabricated and measured** — [primary-source read](./ozden-broadband-supercell-primary-source.md) | HIGH |
| ~~Does it show lateral detuning is *not* a first-class mechanism? **Indirectly yes**, by revealed preference across four groups~~ | **FALLS, 2026-09-10.** The four-group revealed preference was an argument from silence, and the silence was an artefact of an all-optical corpus. Ozden's own Introduction names **five further groups** reaching for lateral detuning — Lee & Lee [20], Kollatou *et al.* [21], Park *et al.* [22], Gu *et al.* [23] (>80 % over 2.35 GHz in X-band), Ghosh *et al.* [24], reference numbers verified against the printed reference list. **At microwave, lateral detuning is a small but real literature, not a road not taken.** | ~~MEDIUM-HIGH~~ → withdrawn |
| Is the repo's 0.7 pp result (22.1 % → 22.8 %) contradicted? | **No. It stands** — and Ozden's *measured* N-sweep agrees with it on width | HIGH |
| Is the repo's *mechanism* ("one spacer = one inductance") confirmed? | **No — neither confirmed nor refuted. Open.** Ozden is consistent with it and with a competing loss-regime explanation | HIGH that it is open |
| Can #187 be closed with "the skin is too thin anyway"? | **No.** The super-cell sits at ~48.5 % of the Rozanov ceiling for the *thinnest* skin in budget. Independently: the #187 bench extracts **25.7 %** of its Rozanov budget on 1.5 mm against Ozden's measured **46.1 %** on 0.75 mm, so the bench design has ~1.8× more headroom against the same physics | HIGH |

### 1.1 The one cheap, actionable challenge

The repo's premise — *one spacer = one inductance* — is sound for **patch** elements, where the
shunt inductance is the current path through the spacer to ground. **It is not obviously sound
for rings.** A closed conductor loop carries in-plane self-inductance set by enclosed area and
trace width, **independent of spacer height**, and P1 asserts exactly this twice in its own
words (*"the additional inductivity by the circular ring"*).

This matters here specifically: **Example 3's element is an I-shaped *ring* resonator**, and it
is the programme's anchor. If the circuit bench that produced the 0.7 pp figure modelled a
patch, it tested the wrong element class.

> **Recommendation.** Before closing the multi-resonator rationale, re-run the super-cell bench
> (a) with ring / loop / split-ring letters and a per-element series self-inductance in the
> circuit model, and (b) with resistive loading dialled in first, scoring **minimax** at each
> step. `CONFIDENCE: MEDIUM-HIGH that the gap is real; LOW that P1 predicts the outcome` — P1
> offers no circuit extraction, no fitted L or C, no equivalent-circuit figure. Its inductance
> claim is prose beside field plots, not a derivation.

**Status, 2026-09-10.** Part **(a)** is **done and came out negative**:
`docs/supercell-ring-inductance-bench.md` ran it and found element self-inductance *narrows* the
band and *deepens* the detuning penalty, so the ring hypothesis fails and #187's finding extends
from patch to ring letters. Part **(b)** — resistive loading dialled in first, scored on minimax —
is **still open, and is now the highest-value open item on #187**, because a published X-band
result at near-zero conductor loss (Ozden, 26.1 mΩ/sq) shows a large minimax gain from lateral
detuning where this programme's 25–50 Ω/sq letters show none. The concrete sweep is in
[`ozden-broadband-supercell-primary-source.md`](./ozden-broadband-supercell-primary-source.md) §7.

---

## 2. The thickness budget is a bandpass, and X-band sits near its lower edge

The most decision-changing finding in the corpus, and it is about the programme rather than the
papers. The 0.87–2.0 mm skin does not get steadily easier or harder with frequency — **it fails
at both ends, for opposite reasons** (all `CALCULATED`):

| | Low-frequency wall | High-frequency wall |
|---|---|---|
| **What binds** | Rozanov: a thin skin cannot absorb a wide band | Electrical thickness: the skin stops being sub-wavelength |
| **0.87 mm** | lowest centre supporting a 40 % band at 90 % absorption: **8.37 GHz** | 0.87 mm = λ/10 at **34.46 GHz** |
| **2.0 mm** | lowest such centre: **3.64 GHz** | 2.0 mm = λ/10 at **14.99 GHz** |

**So the printed-skin absorber window on this budget is roughly 3.6–34.5 GHz, most comfortably
8–30 GHz.** Below it, physics forbids the bandwidth. Above it, the "electrically thin
metamaterial" framing expires and the stack becomes a multi-mode dielectric slab — a different
design problem needing a different model.

*In plain terms: this thickness is a Goldilocks band. At 1 GHz the wave is so long that 2 mm of
anything is far too thin to swallow much of it. At 100 GHz the wave is so short that 2 mm is
two-thirds of a wavelength — the skin is no longer a skin, it is a slab.*

**Consequence for an all-bands loop:** at 100 GHz and 300 GHz the budget becomes a *floor*
problem rather than a ceiling problem — 0.87 mm is λ/3.4 and 0.87 λ respectively. A design there
either uses higher-order spacing or abandons the thin-skin model. That is a different family,
not a rescaled one.

---

## 3. Fabrication — the ink catalogue is not the constraint; the squares count is

Between ACI SC1502 carbon (σ > 167 S/m) and ACI SS1109 silver (σ > 2.22 × 10⁶ S/m) there is an
**empty window of more than four orders of magnitude** in Voltera's catalogue, and three of the
five papers imply an operating point inside it.

**That gap is bridged by geometry, not chemistry.** The printed current path across this corpus
spans **0.06 squares** (the programme's own carbon bridge, 0.245 × 4.0 mm) to **~36 squares**
(P1's ring at a 0.2 mm line). One ink at 250–1000 Ω/sq therefore reaches an effective loop
resistance of **15 Ω to 36 kΩ — a 2,400:1 range** (`CALCULATED`), which brackets every target
the five papers imply.

P1 supplies a concrete, band-independent recipe, and it is the corpus's best #128 datapoint:
squares count is a pure shape ratio and therefore **scale-invariant**. P1's outer ring is 449.2
squares at 8.681 Ω/sq → 3,900 Ω. At 10 GHz that same ring is 7.203 mm around, giving 36.0
squares at a printable 0.2 mm line — so **~108 Ω/sq reproduces the same loop resistance**, and
the middle ring independently gives the same figure, as it must.

Two caveats, both real: matching *R* does not match *L* or *C*, so the resonance retunes; and
P1's second loss channel (bulk polyimide) does not transfer, making it positive on the pattern
and negative on the substrate.

**What actually binds is not feature size.** It is **thickness control, cure-cycle dimensional
change, and whether two inks can be laid coplanar before any bake**. Voltera publishes no
layer-height accuracy and no layer-to-layer registration figure at all
(`docs/voltera-multilayer-capability.md`, `UNKNOWN`) — which is exactly the #106 bench gap, and
exactly why `docs/fabrication-capability-and-ink-library-spec.md` exists.

---

## 4. Multispectral — the discriminant is electrical continuity, and it has a number

A radar-plus-IR skin is the architecture the DEVCOM context makes live. The corpus gives it a
threshold rather than a vibe.

**A resistive overlay on a matched microwave absorber must exceed 407 Ω/sq to leave a 90 %
absorption floor intact, and 1,695 Ω/sq for a 99 % floor** (`CALCULATED`).

Every IR-functional *continuous* conductor in this corpus fails that by one to three orders of
magnitude. **But every *patterned* IR layer passes it by two to three orders**, because a metal
grid of period *p* presents Y/Y₀ ≈ 2π·k·(p/λ), and an IR-scale period is microscopic at 10 GHz.

*In plain terms: a solid metal film on top ruins the radar absorber underneath. The same metal
cut into a fine grid is invisible to a radar wave, because the holes are thousands of times
smaller than the wavelength it cares about.*

So the multispectral conflict is **not** material-versus-material. It is continuous-versus-
patterned, and it is designable.

---

## 5. What the corpus cannot give us — and this bounds everything above

**No minimax can be read off any paper in the corpus, at any angle.** #110 scores the single
worst-absorbing frequency in band. P1's thirteen figures are behind HTTP 403; every other
paper's extraction carries captions and axis ticks, not curve data. *So this corpus cannot
supply a single #110-conformant score for any structure in it.*

That is a hard limit on how far these papers can validate the scoring rule, and it should be
stated wherever they are cited.

**The angle and polarization findings were never adversarially tested.** Sixteen claims failed
refutation across the corpus; **none was an angle or polarization claim** — that material passed
through the lens stage without a refutation round. It is not endorsed, merely unchallenged.

---

## 6. What must not be inherited

**P1's absorption figures violate the Rozanov bound at every rung, and its own comparison table
makes it unmistakable.** The structure is inside the bound's stated assumptions — ground-backed,
transmission argued negligible, normal incidence, non-magnetic. `CALCULATED`: at the ≥90 % floor
over 1920 nm it needs **d ≥ 111.98 nm against 42 nm claimed (2.67× short)**; at its reported
98.16 % mean, **d ≥ 194.31 nm (4.63×)**. Even stage one is already outside.

Applying identical arithmetic to all nine comparators in **P1's own Table 3** gives compliance
margins of **3.86× to 25.27× — nine out of nine comply. P1 comes in at 0.38×.**

Both escape routes close. Its 10 nm ground is below one skin depth above 1705 nm, so its stated
"above the skin depth" justification is false — yet as a 6.944 Ω/sq shunt sheet it still
transmits only ~0.13 %, making it *a mirror by mismatch, not by attenuation*. And the
ferromagnetic μ allowance is never invoked, never parameterised, and irrelevant to a printed
non-magnetic skin.

> **Do not propagate 98.16 %, or any P1 absorption figure, into a #104 trade study.**

Two further cautions. **P1's 1920 nm band is censored at the simulation window** — 2300 − 380
exactly. And its narrowest feature, W2 = 0.5 nm, is a **line width, not a gap**; it appears
exactly once in the article and is never justified, so the honest fabrication status is
`UNKNOWN` rather than either "printable" or "impossible."

---

## 7. Process failures in this analysis, recorded because they cost real cycles

Four, all the same shape: **a claim about a tree, made from the wrong tree.**

1. **A brief built from an issue body rather than the documents it points at.** The commissioning
   context for the first workflow omitted `docs/voltera-multilayer-capability.md` — listed in
   #104's own table — so agents re-derived a procurement spec for an ink the repo already owns
   (ACI SC1502, 377 Ω/sq at 15.9 µm, two passes). `T1-planar-route.md` still carries the
   uncorrected claim that the window is *"an empty band of the current ink inventory."*
2. **Five agents "independently" verified an absence against one stale checkout.** The branch was
   cut from `e626857`, before PR #192 merged; `RUNNING-LISTS.md` §3 item 33 — the ~1.8× MXene
   skin-depth disagreement — was genuinely absent from that tree and present on `main`.
   **Independent verification is worth nothing when every verifier reads the same stale
   artifact.** Verified here: `f86dae6` (which added item 33) is **not** an ancestor of
   `e626857`.
3. **The completeness critic made the inverse error.** Auditing for exactly that contamination,
   it checked at post-merge `HEAD` and concluded the pre-merge readings were *"manufactured
   corroborating evidence."* They were not; they were correct for the tree they ran against. The
   critic's *recommendations* stand — restore the struck claim, do not write a false correction —
   but its stated cause is wrong.
4. **Added 2026-09-10 — §1's `HIGH`-confidence claim about "the published record" was made from
   an all-optical corpus.** Five papers at 380–2300 nm, 10.90–22.91 µm, 400–3500 nm and
   500–2000 nm plus one review, and none at microwave, were used to rule that an **X-band**
   experiment does not exist in the literature. It does — Ozden *et al.* (2016), fabricated and
   measured. Ninety-one agents, five analytical lenses, three-vote adversarial refutation and a
   completeness critic all ran **inside** the corpus and none of them asked whether the corpus
   covered the band the question was about. **Adversarial review of the contents cannot catch a
   defect in the selection.**

**Two rules this yields:**

1. A claim of the form *"X is not in the repo"* must name the commit it was checked at, and be
   re-checked against `origin/main` before being recorded.
2. A claim of the form *"X is not in the literature"* must name **the band, the databases and the
   queries** it was checked against — and it may not be graded above the coverage of the corpus
   that produced it. A survey confined to one band supports a claim about that band and nothing
   wider. The provenance ladder has no rung for this, which is exactly why the `CONFIDENCE` tag
   exists; it was set from how thoroughly the papers were read rather than from whether they were
   the right papers.

---

## 8. What to do next

| | Action | Why now |
|---|---|---|
| 1 | **Re-run the #128/#187 circuit bench with Ozden's stack** — 0.75 mm, ε_r 3.6, tan δ 0.03, dual-resonance cell, 12–16 letters, lateral scale factors — sweeping sheet resistance from 26 mΩ/sq to printed-trace values | Supersedes the ring-element recommendation below. It looks for the **one number** that would explain the repo's null: the R_s at which Ozden's ~+50 pp minimax gain collapses to the bench's +0.7 pp. [Details](./ozden-broadband-supercell-primary-source.md) §7 |
| 1b | ~~**Re-run the #187 super-cell bench with ring elements** carrying per-element self-inductance~~ | ~~The only cheap test that could move a ticket the literature cannot settle (§1.1)~~ — **DONE 2026-09-07**, `docs/supercell-ring-inductance-bench.md`: the ring hypothesis failed. Also, "a ticket the literature cannot settle" was wrong; see the §1 correction |
| 2 | **Record the 3.6–34.5 GHz absorber window** as a property of the thickness budget | It bounds which requirements the loop can serve at all (§2) |
| 3 | **Correct `T1-planar-route.md`'s empty-window claim** before anything cites it | Live contamination; the repo already knows better (§7.1) |
| 4 | **Do not cite P1's absorption figures** | Rozanov-violating by 2.67–4.63× (§6) |
| 5 | Carry the **407 / 1,695 Ω/sq** overlay thresholds into any multispectral scoping | Turns a hand-wave into a design rule (§4) |
| 6 | **Bound the super-cell by tile size, not letter count.** Ozden's 16-letter tile is ~0.90 λ × 0.93 λ across, and he attributes the flat N-sweep to *"super cell size which is electrically comparable with working wavelength"* | A ceiling on ADR-0040's composition that is independent of the loss argument — every letter added grows the tile. [Details](./ozden-broadband-supercell-primary-source.md) §1.3 |

**Not recommended:** treating any figure here as validating #110's minimax rule. The corpus
cannot produce a minimax (§5). *(Ozden's figures can — a matched-window minimax of 0.27 → 0.69 →
0.79 for 1 → 12 → 16 letters — but that is a figure read from a different paper, outside this
corpus, and is recorded as `INFERRED` there rather than imported here.)*
