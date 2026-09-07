# Five metamaterial-absorber papers, read against the printed-skin design loop

**Research date:** 2026-09-07
**Map:** [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104)
**Tickets touched:** #187 (decisively), #110, #128, #129, #130/#138, #111/#190, #105/#148

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
implied by tone.

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

---

## 1. #187 — the ticket this corpus was supposed to settle

**Ruling: the published record does not contain the experiment #187 asks for.** In five papers
across five orders of magnitude of frequency, nobody builds *laterally detuned coplanar
resonators over a single uniform spacer height with no added loss material* and reports the
bandwidth against a control. The absence is the finding. `CONFIDENCE: HIGH.`

**Anyone citing these papers as showing that a super-cell does or does not buy bandwidth is
citing a paper that never ran the test.**

**But the record leans.** Four independent groups all wanted broad bands, all had the
shared-spacer geometry available, and none reached for lateral detuning. Every broadband result
in the corpus is carried by **loss** or by **vertical height variety**.

The sharpest datum is **P4**: the group already had four coplanar resonators in one cell over
one spacer at conserved 31.11 % areal fill, and when they wanted 1170 nm of bandwidth they left
the four resonators **identical** — rotating them 45° for polarization symmetry only — and took
the bandwidth from a lossy material instead, dialling it with that material's thickness. A
near-controlled decline to detune. `LITERATURE-SUPPORTED.`

| Question | Ruling | Confidence |
|---|---|---|
| Does the record show a super-cell buying bandwidth by lateral detuning? | **No — it shows neither way. The test is absent.** | HIGH |
| Does it show lateral detuning is *not* a first-class mechanism? | **Indirectly yes**, by revealed preference across four groups — an argument from practice, not physics | MEDIUM-HIGH |
| Is the repo's 0.7 pp result (22.1 % → 22.8 %) contradicted? | **No. It stands.** | HIGH |
| Is the repo's *mechanism* ("one spacer = one inductance") confirmed? | **No — neither confirmed nor refuted. Open.** | HIGH that it is open |
| Can #187 be closed with "the skin is too thin anyway"? | **No.** The super-cell sits at ~48.5 % of the Rozanov ceiling for the *thinnest* skin in budget | HIGH |

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

Three, all the same shape: **a claim about a tree, made from the wrong tree.**

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

**Rule this yields:** a claim of the form *"X is not in the repo"* must name the commit it was
checked at, and be re-checked against `origin/main` before being recorded.

---

## 8. What to do next

| | Action | Why now |
|---|---|---|
| 1 | **Re-run the #187 super-cell bench with ring elements** carrying per-element self-inductance | The only cheap test that could move a ticket the literature cannot settle (§1.1) |
| 2 | **Record the 3.6–34.5 GHz absorber window** as a property of the thickness budget | It bounds which requirements the loop can serve at all (§2) |
| 3 | **Correct `T1-planar-route.md`'s empty-window claim** before anything cites it | Live contamination; the repo already knows better (§7.1) |
| 4 | **Do not cite P1's absorption figures** | Rozanov-violating by 2.67–4.63× (§6) |
| 5 | Carry the **407 / 1,695 Ω/sq** overlay thresholds into any multispectral scoping | Turns a hand-wave into a design rule (§4) |

**Not recommended:** treating any figure here as validating #110's minimax rule. The corpus
cannot produce a minimax (§5).
