# Encapsulation over a printed X-band absorber: how far it moves the resonance, and where the model gap actually is

**Date:** 2026-09-10
**Bears on:** the wayfinder map [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104),
[ADR-0033](adr/0033-absorber-loss-lives-in-the-printed-pattern-not-the-substrate.md)'s
reference cell, [ADR-0039](adr/0039-two-tier-em-modelling-hybrid-fast-tier-meep-and-emerge.md)'s
tier split, [ADR-0043](adr/0043-band-and-fabrication-capability-are-per-requirement-inputs.md)'s
three fabrication stages. Sibling of
[`costa-thin-spacer-correction.md`](costa-thin-spacer-correction.md), whose §4 and §7
this document leans on directly.
**Question:** the map states that no source characterises the coupling between a
protective coating and the resonant element underneath it. How much does a coating
actually move an X-band printed absorber's resonance, and is the "no source" claim true?

**This is a finding about the world. It decides nothing.** No ADR follows from it;
the decisions it feeds — which encapsulant, which modelling tier, who applies the
coat — belong to tickets that have not been written.

---

## Bottom line up front

**The map's sentence is right in a narrowed form and wrong as an absolute, and the
size of the effect splits cleanly into three regimes that need three different
answers.**

The absolute — *"no source found characterises that coupling"* — is falsified by a
document already in this tree.
[`literature-validation-cases.md`](literature-validation-cases.md) Case 3 reconstructs
a published band-pass FSS in which **1.00 mm of ABS encapsulation, εᵣ = 2.4,
tan δ = 0.006** sits directly over a capacitive FSS layer, cascades it as an ABCD
stack, and scores the result against the paper's own measurement. That is a
dielectric superstrate on a resonant element with numbers attached, held here, and
executed. *In plain terms: we already own a worked example of the exact thing the map
says nobody has characterised.*

The narrowed form survives intact: **no MXene-encapsulation source reports the EM
effect.** §9.

**Three regimes, computed in §4–§6 against ADR-0033's cell** (period 6.0 mm,
1.50 mm silicone spacer, εᵣ 2.9, nominal 10 GHz):

| Coating | Resonance shift | Retune (capacitive gap) | Status |
|---|---|---|---|
| **~100 nm** (iCVD class) | **−0.004% to −0.007%** (−0.35 to −0.70 MHz) | none needed | Electromagnetically invisible — **and unapplyable in this shop** (§4) |
| **20–50 µm** (conformal coat, laminated film) | **−0.70% to −2.75%** (−70 to −275 MHz) | **+19 to +75 µm**, *widening* the gap | A trim, in the same direction as and additive with Costa eq (10) (§5) |
| **≥1.8 mm** (cast or potted) | **−13.9% to −18.6%** (10.0 → 8.14–8.61 GHz) | +438 to +617 µm | A **resonance estimate, not an absorption prediction** — at this size the layer is a front-face transformer (§6) |

**Two invariants worth having, both demonstrated numerically in §7:**

- **The shift depends on the effective permittivity and the cell period, not on the
  gap.** Across the live 0.53 / 0.57 mm gap ambiguity the *baseline* resonance moves
  by 160 MHz while the *encapsulation shift* moves by under 1 MHz. The gap question
  and the encapsulation question do not have to be settled in any particular order.
- **The retune moves the gap *away* from the printer's feature floor, not toward it.**
  That is good news and it should be said as such.

**What this settles, and what it does not:**

| | Answer |
|---|---|
| Is "no source characterises that coupling" true? | **No.** Case 3 is in the tree, with numbers, and has been run. §1 |
| Is a narrowed version true? | **Yes** — no *MXene*-encapsulation source reports the EM effect. §9 |
| How big is the coupling? | Three regimes, §4–§6. `CALCULATED`, uncertainty stated |
| Is there an adopted closed form for a dielectric **layer of finite height above** a grid? | **No.** Costa eq (10) corrects for a metal **mirror below**. The ~0.1–1 mm regime is model-free here. §8 |
| Has the FSS-superstrate literature been searched? | **No.** Two named routes are unchecked, so **no absolute negative is written here.** §8 |
| Can the code express an encapsulated stack? | **No.** `grid_effective_permittivity` takes one argument and hardcodes air above; `geometry/stack.py` does not exist. §10 |

---

## 1. The sentence being corrected, and the fact that falsifies it

Verbatim from #104's map body, under "Not yet specified":

> **Encapsulation is the accepted fix and it collides with the electromagnetics** —
> it adds dielectric directly onto a resonant element, and no source found
> characterises that coupling. If the loop searches over materials, the
> encapsulation layer has to be in the stack it simulates.

The last sentence is correct and §10 confirms it against the code. The middle clause
is the one that fails.

**Case 3 in [`literature-validation-cases.md`](literature-validation-cases.md).**
Verified at line 42 (the status table) and lines 272–317 (the case itself). The paper
is **arXiv:2511.16777v1** — Tehranian, Budhu, Perkowski, Sookdeo, Church, Harris and
Pfeiffer, *Design, Fabrication, and Measurement of a Hemispherical Multi-Layer
Band-Pass Frequency Selective Surface*. The reconstructed stack, quoted from line 311
onward:

| Layer | Value |
|---|---|
| ABS encapsulation | **1.00 mm, εᵣ = 2.4, tan δ = 0.006** |
| Capacitive FSS layer | shunt 78 fF |
| ABS spacer | 1.25 mm |
| Inductive FSS layer | shunt 1.66 nH |
| ABS spacer | 1.25 mm |
| Capacitive FSS layer | shunt 78 fF |
| ABS encapsulation | 1.00 mm |
| **Total** | **4.50 mm** |

That is a **1.00 mm dielectric superstrate directly over a capacitive resonant layer,
with a stated thickness, a stated permittivity and a stated loss tangent**, cascaded
in the order the wave meets it, and scored against a measured planar curve. The case
is marked `EXECUTED → FAIL` — but it fails on the *passband depth* (−0.393 dB
reconstructed against −1.7 dB measured), and the document's own diagnosis is the
silver paste's unmodelled loss, not the encapsulation. **The stop-band, which is set
by the reactances, lands where the paper says it does** — which is precisely the
quantity a superstrate would detune if the cascade were getting it wrong.
`LITERATURE-SUPPORTED` for the paper's constants; `CALCULATED` for the ABCD result
(the case runs `rf_tools/transmissive_absorber.py`, a closed form, not a solver).

*In plain terms: somebody built a filter with a 1 mm plastic skin over the patterned
layer, published the plastic's electrical numbers, and we already reproduce where its
blocking band sits. That is a characterisation of the coupling, and it is sitting in
this repository.*

**Two honest limits on how far that carries.** Case 3's superstrate is 1.00 mm on a
stack whose cell period is not published in a form this repo reconstructed — so it
does not hand over a *rule*, only an existence proof plus one worked point. And it is
a **transmissive** two-port filter, not a ground-backed absorber; the mechanism by
which a superstrate loads a capacitive layer is the same, but the stack around it is
not.

**So the correction is:** the coupling is characterised *somewhere*, with numbers,
including in this tree. What is missing is not evidence that it can be characterised —
it is an adopted closed form for the intermediate thickness regime (§8) and any
source at all on the MXene case specifically (§9).

---

## 2. The cell, and the rule being stretched

**The reference cell**, from ADR-0033's consequences table:

| Layer | Material | Thickness |
|---|---|---|
| Resonant + lossy | ACI SS1109 silver plates + one ACI SC1502 carbon bridge, coplanar | 12 µm |
| Spacer | Silicone 60 ShA, εᵣ = 2.9, tan δ = 0.10 | 1.50 mm |
| Reflector | ACI SS1109 silver, unpatterned | 15 µm |

Period **D = 6.0 mm**, capacitive gap **≈0.53 mm** (up to ≈0.57 mm under the
unresolved eq (10) prefactor, #234), carbon bridge 0.245 × 4.0 mm. Silicone's
εᵣ 2.9 / tan δ 0.10 is `LITERATURE-SUPPORTED` — a single Agilent 85070E probe
measurement of one commercial grade, per
[`xband-absorber-substrate-shortlist.md`](xband-absorber-substrate-shortlist.md) §1
and its own §7 item 4 caveat.

**The rule the encapsulation stretches**, from `costa-thin-spacer-correction.md` §4,
quoting Costa (arXiv:1211.1902) verbatim:

> "If the hypothesis of a sufficiently thick substrate is verified (thicker than
> 0.3 D, where **D is FSS periodicity** [35], the effective permittivity, ε_reff,
> simply corresponds to the average between the relative permittivity of the
> substrate … and the relative permittivity of free space"

So today `eps_eff = (2.9 + 1)/2 = 1.95` — the printed grid sees silicone below and
air above, and the gap field averages the two. *In plain terms: the electric field in
the gap between two printed plates leaks upward into air as much as downward into
the rubber, so the number the formula uses is the average of the two.* An
encapsulation layer replaces the air half. That is the entire mechanism.

**The threshold, and a subtlety a careful reader needs.** Costa states `0.3 D` for a
*grounded substrate*. Costa & Monorchio's ACES overview restates it more strictly and
more generally, quoted verbatim in the same §4:

> "The effect of substrates is generally taken into account by multiplying the FSS
> capacitance through the averaged permittivity of the **dielectrics enclosing the
> FSS** [51]. This approximation is acceptable only for thick dielectric substrates
> (**thicker than an half of the cell periodicity**)…"

Only the ACES phrasing — *"dielectrics enclosing"* — is naturally read as covering a
layer above. **Applying either threshold to a superstrate is an `INFERRED` step, not
a quoted source statement.** Neither paper tests it on a superstrate, and Costa's own
mechanism for the `0.3 D` figure is evanescent Floquet modes **reflecting off a PEC
ground plane** — a boundary that does not exist above the grid. A dielectric/air
interface reflects those modes far more weakly than a metal one. The threshold
transfer is a plausible inference and is used as one below; it is not a citation.

---

## 3. The ansatz, and why the *period* is the right length scale

Everything in §4–§6 rests on one modelling step, so it is stated separately and its
uncertainty is stated with it.

**The ansatz.** The field a periodic grid throws above itself is a sum of evanescent
Floquet harmonics. The slowest-decaying one has transverse wavenumber `2π/D`, so the
field decays as `exp(−2πz/D)` and its energy density as `exp(−4πz/D)`. The effective
permittivity of the upper half is the energy-weighted average of what actually sits
there, so a coating of thickness `t` and permittivity `ε_c` gives

```
    w(t)      = 1 − exp(−4π t / D)              the fraction of the upper-half
                                                 field energy inside the coating

    ε_above   = 1 + (ε_c − 1) · w(t)

    eps_eff   = ( ε_above + ε_substrate ) / 2
```

**Two reasons to believe the length scale.**

*First, the exponent is Costa's own.* Eq (10) — `C₀ − (2Dε₀/π)·ln(1 − e^(−4πd/D))` —
carries exactly `4π·(length)/D`. That is not a coincidence of algebra: both are
first-evanescent-harmonic results on the same lattice, one looking down at a mirror,
one looking up at a coating.

*Second, and more usefully, it reproduces both published thresholds.* `CALCULATED`

| Threshold | `t` | `w(t)` | Residual error in `eps_eff` if treated as saturated |
|---|---|---|---|
| Costa, `0.3 D` | 1.80 mm | **0.97695** | 0.76% |
| ACES, `0.5 D` | 3.00 mm | **0.99813** | 0.06% |

A rule stated as "acceptable above 0.3 D" ought to be about 98% converged at 0.3 D,
and a stricter restatement at 0.5 D ought to be essentially exact. It is, on both
counts, with no fitting. **A competing choice of scale fails this test decisively:**
if the governing length were the *gap* (0.53 mm) rather than the period, saturation
would arrive at ~0.16 mm — 0.027 D — and neither published threshold would make any
sense. The period is the right scale, and the literature's own numbers say so.

**Uncertainty, stated rather than implied: this is good to about a factor of two, and
that band is carried through every number below.** Three reasons it is not tighter:

1. It keeps one harmonic where the true field is a sum over all of them, and the
   higher ones decay faster — which would make the effect *smaller*.
2. It weights by field energy where the quantity actually wanted is a partial
   capacitance; those coincide for a parallel-plate region and not exactly here.
3. It transfers a substrate-derived decay to a superstrate across a much weaker
   reflecting boundary (§2).

**What a 2× error costs**, at the middle of regime 2 (50 µm, ε_c 3.0): `CALCULATED`

| Weight scaled by | Resonance shift | Gap retune |
|---|---|---|
| ×0.5 | −1.13% | +30.1 µm |
| **×1.0** | **−2.22%** | **+60.1 µm** |
| ×2.0 | −4.30% | +119.7 µm |

Every regime-2 figure below should be read as carrying that spread. **Regime 1's
conclusion survives a 2× error by three orders of magnitude, and regime 3's does not
depend on the ansatz at all** (it is in the saturated limit) — so only regime 2 is
genuinely sensitive to it, which is exactly the regime §8 names as model-free.

### How the numbers below were produced

Resonance is solved from Costa's own condition — his §V, `X = −B`, the FSS reactance
cancelling the grounded slab's:

```
    1 / (ω C)   =   (η₀ / √ε_r) · tan( k₀ d √ε_r )
```

with the grid capacitance `C = eps_eff · [ ε₀ (2D/π) ln(1/sin(πg/2D)) + δ ]`, where
`δ` is Costa's eq (10) thin-spacer term (the conservative `ε₀` form, = 1.4940 fF at
this cell). The grid formula was checked bit-for-bit against the repo's own
`capacitive_grid_sheet_capacitance_f` for the air-above case — 130.4666 fF at
g = 0.53 mm from both — and `δ` comes from the repo's own
`thin_spacer_capacitance_correction_f`. The lossless slab is used for the resonance
condition, as Costa does.

**Method validation.** Anchored so the *uncorrected* model sits at exactly
10.000 GHz, this chain reproduces `costa-thin-spacer-correction.md` §7's headline
independently: **−1.065% and +27.8 µm**, against that document's **−1.07% and
+28 µm**. `CALCULATED`

**One discrepancy recorded rather than smoothed.** The anchor gap comes out at
0.6098 mm here against that document's 0.6158 mm — about 1% apart, from constants or
from its use of the lossy slab — and ADR-0033's as-drawn 0.53 mm gap resonates at
9.58 GHz in this lossless solve, not the "~9.9–10.0 GHz centre" the ADR reports (its
figure comes from the full absorptivity model in the #186 prototype, which carries
the resistive bridge and the losses, and is a different quantity from a lossless
reactance crossing). **Absolute frequencies here are therefore worth about ±3%; the
*fractional shifts* are not, and fractional shifts are what this document reports.**
That the trim reproduces to 0.005 percentage points is the evidence for that split.

---

## 4. Regime 1 — ~100 nm, and the irony attached to it

`CALCULATED`. At `t = 100 nm` on a 6.0 mm period, `4πt/D = 2.0944×10⁻⁴`, so
`w = 2.0942×10⁻⁴` — **about two hundredths of one percent** of the upper-half field
energy is inside the coating.

| Coating εᵣ | `eps_eff` | ΔC/C | Resonance shift | On 10 GHz |
|---|---|---|---|---|
| 2.5 | 1.950000 → 1.950157 | +0.00805% | **−0.00366%** | −0.35 MHz |
| 3.0 | 1.950000 → 1.950209 | +0.01074% | **−0.00488%** | −0.47 MHz |
| 4.0 | 1.950000 → 1.950314 | +0.01611% | **−0.00732%** | −0.70 MHz |

**The bound, not just the claim.** The worst case in the table is 0.0073%. Multiply
the ansatz weight by ten — five times worse than the stated 2× uncertainty — and it
is 0.073%, still under a tenth of a percent. The layer is also **0.002° of electrical
thickness** at 10 GHz in εᵣ 2.9, so it cannot act as a transmission-line section
either. Nothing about a 100 nm film reaches the resolution of any measurement this
programme could make.

*In plain terms: a coating that thin is a rounding error twice over — it barely
touches the field in the gap, and the wave passing through it does not notice it is
there. It moves a 10 GHz resonance by less than a megahertz.*

**And here is the irony, stated plainly: the one provably-invisible encapsulant is
the one this shop cannot apply.** The 100 nm figure comes from initiated chemical
vapour deposition (iCVD) of PV4D4 — a **vacuum CVD process**. The configured
fabrication capability is a Voltera NOVA: direct-ink-write extrusion, 100 µm minimum
tracewidth, 40 °C maximum material temperature, dispensing through a nozzle onto a
vacuum table (`docs/fabrication-capability-and-ink-library-spec.md` §3.2,
`MANUFACTURER-SPECIFIED`). There is no vacuum chamber, no CVD reactor, and no
`laminate`-stage capability of any kind (§11). A candidate encapsulated by iCVD is a
candidate that needs somebody else's equipment.

**Capability warning** (per ADR-0043 and ADR-0025's 2026-09-09 correction — this is a
*Capability warning*, which never drops the candidate, not a `capability-verdict`):

> **What is assumed:** that a ~100 nm vacuum-deposited encapsulant can be obtained for
> a printed coupon. **What it costs if wrong:** the only encapsulation regime with no
> RF penalty at all is unreachable, and the decision falls back to regime 2 with its
> −0.7% to −2.8% trim and its model gap. **Cheapest way to find out:** one quote from
> a CVD or parylene coating service for a 220 × 300 mm coupon — a phone call, not an
> experiment.

**Provenance of the 100 nm figure itself.** It is reported by the two outside research
passes that commissioned this document (§9), and **no citation for it reached this
repository** — `INFERRED`, and deliberately not load-bearing: the table above is
computed for 100 nm as a *thickness*, so it holds whatever process puts it there.

---

## 5. Regime 2 — 20–50 µm conformal coat or laminated film

The realistic case, and the one with a genuine number attached. Coating permittivity
is bracketed 2.5–3.5, which spans the ordinary conformal-coat chemistries (acrylic,
urethane, silicone, parylene) and the thin polymer films this programme already
handles.

`CALCULATED`, anchored so the bare cell sits at exactly 10.000 GHz (gap 0.6375 mm
with the Costa term included):

| Coating | `w(t)` | `eps_eff` | ΔC/C | Resonance | Shift | Retune |
|---|---|---|---|---|---|---|
| 20 µm, εᵣ 2.5 | 0.0410 | 1.9808 | +1.578% | 9.9297 GHz | **−0.703%** (−70 MHz) | **+18.7 µm** |
| 20 µm, εᵣ 3.0 | 0.0410 | 1.9910 | +2.104% | 9.9066 GHz | **−0.934%** (−93 MHz) | **+24.9 µm** |
| 50 µm, εᵣ 3.0 | 0.0994 | 2.0494 | +5.099% | 9.7779 GHz | **−2.221%** (−222 MHz) | **+60.1 µm** |
| 50 µm, εᵣ 3.5 | 0.0994 | 2.0743 | +6.373% | 9.7247 GHz | **−2.753%** (−275 MHz) | **+75.1 µm** |

**So: roughly −1% to −3% in resonant frequency, order −100 to −300 MHz from 10 GHz,
restored by widening the capacitive gap by roughly +19 to +75 µm.** With the ansatz's
stated 2× band, the honest spread is about −0.4% to −5.5% and +9 to +150 µm.

*In plain terms: painting a protective layer a human-hair thick over the printed
pattern drags the surface's tuned frequency down by one to three percent — a couple
of hundred megahertz on ten gigahertz. To put it back you open the gap between the
printed plates by about the width of a fine human hair, and no other dimension has to
move.*

**Why this regime is a capacitance loader and not a transmission line.** At 50 µm the
layer is **0.96–1.07° of electrical thickness** at 10 GHz across εᵣ 2.55–3.2 (at
20 µm, 0.38–0.43°). A one-degree section transforms nothing. That single number is
what separates this regime from §6, where the same material at 1.8 mm is 37° and
everything changes.

### It is the same direction as Costa eq (10), and it adds to it

Both effects raise the grid capacitance and both therefore pull the resonance down.
Evaluated at one fixed drawn geometry — the 0.6098 mm gap an *uncorrected* model
would draw for 10 GHz — so the two are composed rather than scaled: `CALCULATED`

| Applied | Resonance | Shift | Gap needed to hold 10 GHz |
|---|---|---|---|
| Costa eq (10) only | 9.8935 GHz | −1.065% | 0.6375 mm (**+27.8 µm**) |
| Costa + 20 µm, εᵣ 2.5 | 9.8238 GHz | **−1.762%** | 0.6562 mm (**+46.4 µm**) |
| Costa + 20 µm, εᵣ 3.0 | 9.8009 GHz | **−1.991%** | 0.6624 mm (**+52.7 µm**) |
| Costa + 50 µm, εᵣ 3.0 | 9.6733 GHz | **−3.267%** | 0.6977 mm (**+87.9 µm**) |
| Costa + 50 µm, εᵣ 3.5 | 9.6205 GHz | **−3.795%** | 0.7126 mm (**+102.9 µm**) |

**Together: roughly −2% to −4% in frequency, +46 to +103 µm on the gap.** The two
corrections are of comparable size, which is the point worth carrying: a programme
that has just absorbed a −1% correction as "a trim, not a redesign" is looking at
another one of the same order the moment it commits to a coating.

### The retune moves *away* from the feature floor

ADR-0033's tightest manufacturing margin is the **0.245 mm carbon bridge** against a
**0.2 mm feature floor**, and `costa-thin-spacer-correction.md` §7 already records
that eq (10)'s retune "moves the design *away* from the 0.2 mm feature floor, not
toward it." **The encapsulation retune does the same thing, for the same reason: it
widens the gap.** From 0.53 mm the gap goes to 0.55–0.60 mm; the carbon bridge is
untouched, because only the capacitive gap carries the shift.

That matters more than it sounds, because
[`diw-feature-floor-mechanism.md`](diw-feature-floor-mechanism.md) suggests the real
floor may be worse than 0.2 mm — if Nordson EFD's 1.5× rule transfers, *"a 150 µm tip
would floor at 229 µm and a 200 µm tip at 305 µm."* Every micron the encapsulation
pushes the gap outward is a micron of margin against a floor that may yet move up.
**This is the one unambiguously good piece of news in the document and it should be
read as such.**

---

## 6. Regime 3 — ≥1.8 mm cast or potted, and why the number below is not a prediction

1.8 mm is Costa's `0.3 D` at this period; 3.0 mm is the stricter ACES `0.5 D`. At
either the coating is effectively a half-space (§3: 97.7% and 99.8% saturated), so
the ansatz stops doing any work and `eps_eff` is just the two-sided average.

`CALCULATED`, same 10.000 GHz anchor:

| Coating | `eps_eff` | ΔC/C | **Naive** `1/√C` | **Solved** `X = −B` | Resonance |
|---|---|---|---|---|---|
| PDMS, εᵣ 2.55 | 1.950 → 2.725 | **+39.74%** | −15.41% | **−14.19%** | 8.581 GHz |
| PDMS/silicone, εᵣ 2.9 | 1.950 → 2.900 | **+48.72%** | −18.00% | **−16.64%** | 8.336 GHz |
| Kapton 500HN, εᵣ 3.2 | 1.950 → 3.050 | **+56.41%** | −20.04% | **−18.58%** | 8.142 GHz |

At the finite 1.8 mm rather than the saturated limit the same three come out at
−13.93%, −16.35% and −18.26% — a fifth of a percentage point of difference, which is
what a 97.7% weight buys.

**Report both, and say why they differ.** The naive answer treats the stack as a
lumped `LC` where `f ∝ 1/√C`. It overshoots by 1.2–1.5 percentage points every time,
because the "L" is not an inductor: it is a grounded slab whose reactance
`(η₀/√ε_r)·tan(k₀ d √ε_r)` rises **faster** than a pure inductor's, so the reactance
crossing is pushed back up in frequency. `costa-thin-spacer-correction.md` §7 records
exactly this effect on its own, much smaller correction — *"the solved values are
slightly smaller because the slab's reactance `tan(k₀d√ε_r)` rises faster than a pure
inductor's, which stiffens the resonance"* — and at a 40–56% capacitance change it
grows from a quarter of a percentage point to well over one. **A 1/√C estimate is a
sanity check here, not a result.**

### Now the caveat that matters more than the number

**At 1.8 mm the coating stops being a capacitance multiplier and becomes a
transmission-line section in front of the whole stack.** `CALCULATED`

| Coating | 1.8 mm | 3.0 mm | Quarter-wave at 10 GHz | Wave impedance |
|---|---|---|---|---|
| PDMS, εᵣ 2.55 | **34.52°** | 57.53° | 4.693 mm | 235.9 Ω |
| PDMS/silicone, εᵣ 2.9 | **36.81°** | 61.35° | 4.401 mm | 221.2 Ω |
| Kapton, εᵣ 3.2 | **38.67°** | 64.44° | 4.190 mm | 210.6 Ω |

**About 37 degrees of electrical thickness** at εᵣ 2.9 — a fifth of a wavelength, and
roughly 41% of the way to a quarter-wave transformer (a quarter-wave in PDMS is
4.40 mm). *In plain terms: at this thickness the coating is no longer "extra
dielectric near the printed shapes." It is a slab of material the wave has to travel
through and partly bounce off before it ever reaches the absorber, and slabs like
that are what impedance matching is built out of.*

A 37° section of 221 Ω line sitting between free space (377 Ω) and the absorber
transforms whatever the absorber presents. **It can act as a matching layer as
readily as a detuner** — a mismatched absorber can be *improved* by it, and a matched
one degraded. Which happens depends on the complex input impedance at the frequency
of interest, which the resonance condition above does not compute.

**So the −13.9% to −18.6% is a RESONANCE ESTIMATE, not a predicted absorption
response.** It says where the grid-plus-slab subsystem's reactance crossing moves to.
It does not say what the encapsulated stack reflects. Those are different questions,
and only the second one is what a requirement asks about. Anyone quoting the −14 to
−19% as an absorption prediction is quoting it wrong.

**A second reason this regime needs a solver, not algebra:** at 1.8 mm the coating's
own loss tangent enters the stack as a real dissipation path in front of the absorber,
not merely as a dilution term in the gap. §12.

---

## 7. Two invariants, demonstrated

### 7.1 The shift does not depend on the gap

The gap is live: ADR-0033 carries **≈0.53 mm** under eq (10)'s conservative `ε₀`
prefactor and **≈0.57 mm** under the `ε₀ε_r` form, unresolved on #234. If the
encapsulation answer moved with it, this document would inherit that open question.
It does not. `CALCULATED`

Structurally, `C = eps_eff × f(g, D)` factorises, so the *fractional* capacitance
change from a coating is exactly gap-independent. The *frequency* shift is not exactly
so, because the baseline resonance itself depends on `g` — so it is worth showing
rather than asserting:

| Coating | Shift at g = 0.53 mm | Shift at g = 0.57 mm | Difference |
|---|---|---|---|
| 20 µm, εᵣ 2.5 | −0.7097% | −0.7073% | 0.0024 pp |
| 50 µm, εᵣ 2.5 | −1.6946% | −1.6889% | 0.0057 pp |
| 20 µm, εᵣ 3.0 | −0.9430% | −0.9398% | 0.0032 pp |
| 50 µm, εᵣ 3.0 | −2.2406% | −2.2331% | 0.0075 pp |
| 20 µm, εᵣ 3.5 | −1.1746% | −1.1706% | 0.0040 pp |
| 50 µm, εᵣ 3.5 | −2.7777% | −2.7685% | 0.0092 pp |

Meanwhile the same 40 µm of gap ambiguity moves the **baseline** resonance from
9.5791 GHz to 9.7386 GHz — **160 MHz, or 1.67%.**

*In plain terms: the unresolved question about the gap width moves where this cell
resonates by 160 megahertz. It moves how much a coating shifts that resonance by
under one megahertz. The two questions can be answered in either order, or by
different people, and neither has to wait for the other.*

### 7.2 The retune direction is away from the feature floor

Already stated in §5 and worth repeating as an invariant rather than a regime-2
detail: **every regime here that needs a retune needs the gap to get *wider*.** More
capacitance from above must be paid for by less capacitance from the gap, and less
gap capacitance means a bigger gap. That is true at 20 µm (+19 µm), at 50 µm
(+75 µm), and in the thick regime (+438 to +617 µm, leaving a 4.75–4.92 mm patch on a
6.0 mm period). It is monotone and it has no exception in this geometry.

**The direction is the good one at every scale.** Nothing here pushes a printed
feature toward the 0.2 mm floor, and the tightest feature in the cell — the 0.245 mm
carbon bridge — is not touched by the shift at all.

---

## 8. The genuine gap, stated precisely

**Costa eq (10) corrects a grid for a metal *mirror* a distance `d` BELOW it. No
adopted closed form exists here for a dielectric *layer of finite height `t` ABOVE*
it.** The two ends are covered — `t → 0` is the bare cell, `t ≳ 0.3 D` is the
saturated average — and **the intermediate ~0.1–1 mm regime is model-free.** §3's
ansatz is this document's own construction, not an adopted form, and it is labelled
`CALCULATED` with a stated 2× band for exactly that reason.

Two things a careful reader needs alongside that:

- **The `0.3 D` / `0.5 D` thresholds are stated against the *substrate*, not against
  "each bounding medium."** Costa's is for a *grounded substrate*; only the ACES
  restatement is phrased as *"the dielectrics **enclosing** the FSS"*, at `0.5 D`.
  **Applying either to a superstrate is an `INFERRED` step**, and Costa's mechanism —
  evanescent modes reflecting off a PEC — does not transfer automatically to a
  dielectric/air boundary, which reflects them far more weakly.
- The three regime boundaries in this document therefore inherit that inference. The
  *numbers* inside each regime do not depend on it; the *placement* of the boundaries
  does.

### The unfetched candidate closed form — a fetch, not a solve

`costa-thin-spacer-correction.md` §8 already records it, in the table of routes that
failed:

> **Costa, Monorchio & Manara, IEEE APM 54(4) 2012** … DOI `10.1109/MAP.2012.6309153`.
> Unpaywall reports not open access, no OA locations. Behind IEEE. … The APM paper is
> the source of a *different*, later interpolating formula (**ACES eq (5), an
> effective-permittivity fit in `x = 10 d/D`**), which is an alternative to eq (10),
> not a restatement of it.

**An effective-permittivity fit in layer-thickness-over-period is exactly the shape of
the form that is missing.** It is `eps_eff(x)` where `x = 10·d/D` — the same
dimensionless ratio §3 builds its ansatz on, published as a fit rather than
constructed here. If it transfers to a superstrate it replaces §3 outright; if it does
not, reading it will say why.

`docs/RUNNING-LISTS.md` §1 records **IEEE Xplore returning HTTP 418** to this
environment, so this needs institutional access. **It is a fetch, not a solve, and it
is the single highest-value action on this question.**

### Two unchecked routes, so no absence claim is written here

The map's own rule is that *"no data exists" is a claim about the world; "we could not
fetch it" is a claim about us*. **The FSS-superstrate literature has not been
searched, so this document writes no absolute negative about it.** Two obvious homes
that were not checked:

- **Callaghan, Parker & Langley**, *"Influence of supporting dielectric layers on the
  transmission properties of frequency selective surfaces"*, **IEE Proc. H 138(5),
  1991**. The title is the question. Unchecked.
- **Munk**, *Frequency Selective Surfaces: Theory and Design* (Wiley, 2000),
  dielectric-loading chapters. The standard reference on precisely this effect.
  Unchecked.

Either could turn §3's ansatz into an adopted, cited form or falsify it. **Until one
of them is read, "no closed form exists" means "none is adopted here" and nothing
stronger.**

---

## 9. What the outside research actually said

Recorded so the correction in §1 is honest rather than one-sided.

Two research passes fed this document — one on MXene EM properties, one on printing
methods. **Both mandate encapsulation as the durability fix, and both state it without
a thickness, without a permittivity, and without any statement of its effect on a
resonant element.** The only thickness either supplies is the iCVD PV4D4 figure at
100 nm used in §4, which arrives without a citation this repository can check.

That is consistent with what the tree already holds. The map's own ink-handling entry
(#104, verified verbatim) records the durability case in full — *"−82% conductivity
over six months, unencapsulated"* (Zhang et al.,
[10.1038/s41467-019-09398-1](https://doi.org/10.1038/s41467-019-09398-1)), against a
two-year unencapsulated counter-example from Shao et al. that does not obviously
reconcile with it — and then states the collision this document is correcting. A
repository-wide search for `iCVD`, `PV4D4` or `encapsulat` returns **nothing on the
MXene case**: the only hits are Case 3's ABS layers (§1) and one line in
`xband-absorber-substrate-shortlist.md` §5 noting that textile MXene is *"washable
with proper encapsulation"* — a durability claim, not an electromagnetic one.

**So the map's sentence is right in its narrowed form and wrong as an absolute:**

- ✅ **True:** no MXene-encapsulation source found reports the EM effect of the
  encapsulant. The durability literature and the electromagnetics literature do not
  overlap on this material.
- ❌ **False as written:** *"no source found characterises that coupling."* Case 3 is
  in the tree, with a thickness, a permittivity, a loss tangent, and an executed
  cascade scored against measurement.

The distinction is not pedantry. The absolute version implies the coupling is
uncharacterisable and the loop must simulate its way out. The narrow version says
something much more actionable: **the gap is material-specific and the method is
already demonstrated.**

---

## 10. The code seam, precisely

**`rf_tools/sheet_impedance.py`.** Verified by reading it:

```python
def grid_effective_permittivity(eps_r: float) -> float:
    """The half-air, half-substrate average a coplanar grid's gap field sees.

        eps_eff = (eps_r + 1) / 2
    ...
    """
```

**It takes one argument and hardcodes the air half.** The docstring says so in its
first line. There is no parameter for what sits above the grid, and no caller could
supply one.

The seam propagates exactly one level down. `capacitive_grid_sheet_capacitance_f`
(`rf_tools/sheet_impedance.py`) calls it internally —
`eps_eff = grid_effective_permittivity(eps_r)` — and that function feeds
`patterned_sheet_impedance` in `rf_tools/absorber.py:141`, which feeds `absorptivity`
at `:213`, which is the ANALYSIS-step model for the whole `ABSORBER` design family.
`grid_gap_loss_tangent` (`:1069`) has the identical shape: `eps_r*tan_delta/(eps_r+1)`,
the same hardcoded air dilution, so a *lossy* superstrate is equally inexpressible.

**So every regime in §4–§6 was computed outside the repo's own functions**, with the
grid formula re-implemented and cross-checked bit-for-bit against
`capacitive_grid_sheet_capacitance_f` for the air-above case only (§3). *In plain
terms: the code can model this cell with air on top and cannot model it with anything
else on top, so the arithmetic in this document had to be done beside the code rather
than through it.*

**And `geometry/stack.py` does not exist.** `docs/em-field-visualization-design-panel.md:294`
describes it in the present tense:

> `geometry/stack.py` defines a LayerStack: an ordered list of layers, each carrying
> thickness_m, role (host / adhesive / substrate / conductor / **coverlay**), εr,
> tanδ, sheet_resistance_ohm_sq, a provenance tier read from `knowledge/provenance.py`,
> and a citation string.

Listing `geometry/` returns `PROTOTYPE-lossy-cell-fit.md`, `__init__.py`,
`freecad_curved.py`, `prototype_lossy_cell_fit.html`, `unit_cell.py` — and no
`stack.py`. A repository-wide search for `coverlay` returns that one design-panel line
and nothing else. **The `coverlay` role — the layer an encapsulant would occupy — is
named in a design document for a file that has never been written.** This is the
`CLAUDE.md` failure mode about planning docs, appearing in a design panel rather than
a roadmap.

**The map's last sentence is therefore correct and live:** *"If the loop searches over
materials, the encapsulation layer has to be in the stack it simulates."* Today it
cannot be, at either level — not in the closed form, and not in a layer-stack
representation.

---

## 11. Who applies the coat

**None of the three encapsulation routes is a Voltera NOVA operation.** The NOVA is
direct-ink-write extrusion: ~100 µm minimum tracewidth (120 µm for printed MXene per
Shao et al.), 100/150/225 µm supplied nozzles, ±20 µm single-layer positioning, 70 psi
maximum dispense pressure, **40 °C maximum material temperature**, 220 × 300 mm print
area (`docs/fabrication-capability-and-ink-library-spec.md` §3.2,
`MANUFACTURER-SPECIFIED`).

| Route | What it needs | On the NOVA? |
|---|---|---|
| iCVD, ~100 nm | vacuum CVD reactor | **No** — no vacuum chamber |
| Conformal coat, 20–50 µm | spray, dip or brush, then cure | **No** — DIW dispenses traces, not films |
| Laminated film, 20–50 µm | flat-film-to-flat-film bonding | **No** — no laminate capability configured |
| PDMS pour, ≥1.8 mm | mould, degas, thermal cure | **No** |

ADR-0043 decomposes fabrication into **three independent stages — print / cure /
laminate — never one lumped "which printer" fact**, and names lamination as *"bonding
an already-cured coupon onto the final host; as configured today, flat-film-to-flat-film
only, with no embedded-component capability."*

**Verified: zero laminate rows are seeded.** `docs/fabrication-capability-and-ink-library-spec.md`
§3.2, verbatim: *"All eight rows are `print`-stage: the Voltera NOVA's own dispensing
hardware. **No `cure` or `laminate` rows are seeded yet** — the external-oven cure
ceiling and lamination bond limits are tracked qualitatively in `CONTEXT.md`'s Host
surface entry and #108, not yet as `fabrication_capabilities` rows."* A
repository-wide search for `fabrication_capabilities` returns that spec document and
nothing else — **the table is a schema on paper, not a table in the tree.**

**Per ADR-0043 and ADR-0025's 2026-09-09 correction, the whole encapsulation branch
therefore carries a Capability warning naming who applies the coat — and is still
reported.** ADR-0025 is explicit that a shortfall in what the shop has loaded is a
*Capability warning*, which *"never removes the candidate from consideration"*, and not
a `capability-verdict`, which would drop it. ADR-0021's rule, quoted in that
correction: *"A candidate the configuration cannot build in this pass is reported in
the ranked output with its reason attached... not deleted from it."*

> **Capability warning — encapsulation application.** *What is assumed:* that an
> encapsulation step exists at all, at any thickness. *What it costs if wrong:* the
> durability fix the MXene literature mandates cannot be executed on any configured
> machine, so a printed MXene candidate is a candidate with an unaddressed −82%
> six-month conductivity decay. *Cheapest way to find out:* one quote from a
> conformal-coating or parylene service, and one bench test of hand-brushed coat
> uniformity on a scrap coupon. Neither needs a design decision first.

**Warn, never block.** The candidate is returned either way. What changes is that the
reader is told the coat is somebody else's operation before they plan around it.

---

## 12. Two things no paper settles

**1. The coating's own loss is not obviously neutral, and PDMS's is `INFERRED`.**

ADR-0033 already assigns the substrate **20–36% of the dissipation budget** at this
design point — *"with Costa's thin-spacer term included, a lossy substrate (silicone,
tanδ 0.10) still supplies 20–36% of the total dissipation."* A lossy layer added on
the other side of the printed pattern is therefore landing in a budget where dielectric
loss is already a third of the answer, not a rounding term.

And the number needed to evaluate it does not exist here.
`xband-absorber-substrate-shortlist.md` §7 item 5, verbatim: *"The PDMS X-band loss
tangent specifically. Cresson et al. measure 1–220 GHz and report εr falling 2.9 → 2.55
and tanδ 'increasing slowly to reach 0.048 at 210 GHz.' The X-band value is on that
curve but is not tabulated in the accessible abstract, and IEEE Xplore returned HTTP
418 to every fetch. The ~0.01–0.02 used in the § 'arithmetic' table is `INFERRED` from
the curve's shape, not read off it."* The shortlist's main table records PDMS's X-band
tan δ as **not separately tabulated at all**.

*In plain terms: we do not know how lossy the most likely thick encapsulant is at the
frequency we care about, and loss is already carrying a third of this design's job.
Adding a layer of unknown lossiness to a stack whose loss budget is already contested
is not obviously either good or bad — and at 20–50 µm it is probably negligible, while
at 1.8 mm it certainly is not.*

**2. No ADR decides whether an encapsulated stack goes through the closed form at
all.**

ADR-0039 sets the tier split: a hybrid fast tier of one Floquet solve per shape family
plus closed-form algebra, promoted to full-wave confirmation by top score. It says
nothing about a superstrate. Given §8 — no adopted closed form for the intermediate
regime — and §6 — a thick layer that is a transformer rather than a capacitance
multiplier — **whether an encapsulated candidate may be scored by the fast tier or
must escalate is an open call, and ADR-0039's tier split is where it belongs.** Nobody
has made it. This document does not make it either; it only establishes that the
question is real.

---

## 13. What would confirm it

**A three-run Floquet sweep on ADR-0033's cell: bare, +25 µm, +1.8–2.0 mm.**

| Run | What it settles |
|---|---|
| **Bare** | The baseline against which the other two are read, and a check on §3's method against the repo's own model |
| **+25 µm** | Whether the −0.7% to −2.8% of §5 is right, and by how much the ansatz is off — the one number that would replace a 2× band with a measurement |
| **+1.8–2.0 mm** | **The only run that can see the transformer effect of §6.** Neither of the other two can: at 0.4–1.0° of electrical thickness there is nothing to transform |

Three runs, one geometry, one solver. The third is the one that cannot be skipped,
because it is the only one testing a mechanism the algebra above deliberately declines
to predict.

**The blocker, verified before citing.**
[`meep-absorber-validation.md`](meep-absorber-validation.md) scopes what `SIMULATED`
currently means, verbatim from its "What these four cases earn" section:

> **What it now means, and only for this:** for a bare or ground-backed *uniform,
> unpatterned* resistive sheet, hit at *normal incidence*, with any dielectric's loss
> tangent read at *band centre*, solved by Meep FDTD at 10 GHz — `SIMULATED` means the
> returned number was checked against an answer this codebase did not produce…

and, two paragraphs later:

> What `SIMULATED` still does not mean — **for a patterned unit cell**, an oblique
> angle, the NEC2 dipole, the Palace/Floquet path, and every other adapter in
> `simulation/` — is stated once, for the whole codebase, in `verification/README.md`…

**So the validated envelope explicitly excludes a patterned unit cell**, which is
exactly what this sweep is. ADR-0039 commits the work that would open it —
*"`simulation/meep.py` needs a Bloch `k_point` added to its periodic-boundary
handling"* — and that work is listed as committed, not done. Its own closing line
names the same gap: *"the canonical case is validated, the design case is not yet. The
next reference case should be a patterned cell with a published response."*

**Which puts §8's fetch first in the queue.** Reading ACES eq (5) costs a library
login. Running the sweep costs an adapter capability that does not exist yet.

---

## 14. Provenance summary

| Claim | Provenance |
|---|---|
| Case 3's encapsulation constants — 1.00 mm ABS, εᵣ 2.4, tan δ 0.006 | `LITERATURE-SUPPORTED` (arXiv:2511.16777v1) |
| Case 3's cascade result (−0.393 dB at 10 GHz, stop-band passing) | `CALCULATED` (`rf_tools/transmissive_absorber.py`, closed form) |
| `eps_eff = (ε_above + ε_below)/2` for a thick bounding medium | `LITERATURE-SUPPORTED` (Costa arXiv:1211.1902; ACES restatement) |
| The `0.3 D` / `0.5 D` thresholds as stated | `LITERATURE-SUPPORTED` — **against the substrate** |
| Applying those thresholds to a **superstrate** | `INFERRED` — no source states it |
| The evanescent-weight ansatz `w(t) = 1 − e^(−4πt/D)` | `CALCULATED`, **good to ~2×**, §3 |
| Regime 1 shift, −0.004% to −0.007% | `CALCULATED` — survives a 10× ansatz error |
| Regime 2 shift, −0.70% to −2.75%; retune +19 to +75 µm | `CALCULATED` with the 2× band |
| Regime 2 additive with Costa: −1.8% to −3.8%; +46 to +103 µm | `CALCULATED` |
| Regime 3 solved shift, −13.9% to −18.6% | `CALCULATED` — **a resonance estimate, not an absorption prediction** |
| 37° electrical thickness at 1.8 mm / εᵣ 2.9; quarter-wave 4.40 mm | `CALCULATED` |
| Gap-independence of the shift (<0.01 pp across 0.53–0.57 mm) | `CALCULATED` |
| Silicone 60 ShA, εᵣ 2.9 / tan δ 0.10 | `LITERATURE-SUPPORTED`, single-sourced |
| Kapton 500HN, εᵣ 3.2 | `LITERATURE-SUPPORTED` (ring resonator, 10–65 GHz fit) |
| PDMS X-band tan δ | `INFERRED` — read off a curve's shape, §12 |
| iCVD PV4D4 at 100 nm | `INFERRED` — reported by the commissioning research passes, no citation reached this repo, **not load-bearing** |
| Voltera NOVA capability figures | `MANUFACTURER-SPECIFIED` |
| Zero `cure` / `laminate` rows seeded | Verified in the tree |
| `geometry/stack.py` does not exist | Verified by listing `geometry/` |
| `grid_effective_permittivity` hardcodes air above | Verified by reading `rf_tools/sheet_impedance.py` |
| ACES eq (5) as the candidate missing form | `LITERATURE-SUPPORTED` that it exists (recorded in `costa-thin-spacer-correction.md` §8); **unread** |
| The FSS-superstrate literature | **Unsearched.** No absence claim is made |
