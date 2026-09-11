# The `BANDPASS_FSS` passband bound, read from the original

**Date:** 2026-09-11
**Ticket:** [#482](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/482), [#483](https://github.com/parthalon025/Principle_RF_Engineer_Agent/pull/483); part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104).
**Question:** Does Bode–Fano gain-bandwidth theory bound `BANDPASS_FSS` (a free-standing, single-layer, resonant-aperture radome), and if not, what does?

`designs/design_families.py`'s `BANDPASS_FSS.physical_bound` named broadband
matching theory — Bode's and Fano's gain-bandwidth limits — as a lead, without a
citation, and one paywalled 2025 paper (Zheng, Hao & Li, IEEE TMTT) as an
unread, search-engine-paraphrased candidate. Both questions have now been
settled by sources read in full.

---

## Bottom line up front

**Two findings, and the first is a negative result that stops a wrong bound
from being adopted.**

1. **Classical Bode–Fano does not bound this structure, and the reason is
   structural.** Bode–Fano bounds a lossless matching network in front of a
   *fixed load with non-zero Q*. For `BANDPASS_FSS` — free space on both
   sides, no ground plane, no second layer — the only honest load is the far
   half-space itself: a pure resistance, `η₀ = 376.73 Ω`, with `Q = 0`. Every
   form of the criterion has `Q` (or `RC`, or `L/R`) in the denominator of its
   right-hand side, so the bound reads `≤ ∞`. This is not a missing derivation
   — it is what the theorem is supposed to say when the all-frequency match
   genuinely exists: remove the sheet, and free space in front of free space
   transmits perfectly at every frequency, forever. **Do not fold a Bode–Fano
   bound into this family.** §2 below is the full argument, including two
   attempted rescues and why each fails.

2. **A real, measurement-validated bound for exactly this geometry does
   exist**, from the same "passive-system sum rule" family Bode–Fano belongs
   to, but derived for the right object:

   > **`B ≤ γπΔ / (Aλ₀)`**
   >
   > A. Ludvig-Osipov, J. Lundgren, C. Ehrenborg, Y. Ivanenko, A. Ericsson,
   > M. Gustafsson, B. L. G. Jonsson & D. Sjöberg, "Fundamental Bounds on
   > Transmission Through Periodically Perforated Metal Screens With
   > Experimental Validation," *IEEE Trans. Antennas Propag.* **68**(2):
   > 773–782, Feb. 2020, doi:`10.1109/TAP.2019.2943430`. Read in full from
   > the open author manuscript, [arXiv:1810.07669v3](https://arxiv.org/abs/1810.07669)
   > (bibliographic record cross-checked against Crossref). Their Eq. (12).

   Its stated object is *"arbitrary periodic apertures in thin screens"* in
   free space at normal incidence — the `BANDPASS_FSS` geometry in the
   source's own words — and it is verified against measurements of an array
   of horseshoe-shaped slots laser-milled in **18 µm aluminium foil**, within
   a factor of ~1.2 of this programme's own ~15 µm printed conductor.

**What this costs the programme, plainly stated:** the bound needs one number
nothing here can currently compute — the static (DC) polarizability `γ` of
the aperture's Babinet-complementary patch shape, per unit cell. That is an
electrostatic field solve, far cheaper than a frequency sweep, but it is not a
closed form and no tool in `rf_tools`/`simulation` produces it. Until it does,
the bound can be **quoted and evaluated by hand**, but not computed
automatically from a candidate's geometry. See §6.

---

## 1. What was read, and what was not

House rule (`CLAUDE.md`; the discipline `docs/RUNNING-LISTS.md` §1 applies to
its MXene-paper entries): a claim attributed to a source must be something
actually read and quotable, never a search-engine paraphrase presented as
fact.

| Source | Status |
|---|---|
| Ludvig-Osipov et al. (2020), *IEEE TAP* 68(2):773–782 | **READ IN FULL** — arXiv:1810.07669v3 author manuscript, all sections + Appendix A. Crossref-confirmed bibliographic record |
| Sjöberg, Gustafsson & Larsson (2010), Lund TEAT-7199 (published as *EPL* 92(3):34009) | **READ IN FULL** — open technical-report PDF, lup.lub.lu.se |
| Bernland, Luger & Gustafsson (2011), *J. Phys. A* 44:145205 | **READ IN PART** — open technical-report version Lund TEAT-7193 (§1, §5.3, §6, reference list) |
| Steer, M., *Microwave and RF Design III — Networks*, §7.2 "Fano-Bode Limits" | **READ IN FULL** — open CC BY-NC textbook, eng.libretexts.org |
| UCSB ECE145A (Long) impedance-matching handout, pp. 5–6 | **READ** |
| Pozar, *Microwave Engineering* 4th ed., §5.9 "The Bode–Fano Criterion", p. 266 | **NOT READ — location confirmed only**, via the Library of Congress's enhanced-catalogue TOC for this edition. **No equation here is attributed to Pozar.** Note the correction: Bode-Fano is Pozar §5.9 (inside Ch. 5, *Impedance Matching and Tuning*), **not** Ch. 12 (*Microwave Amplifier Design*) — `rf_tools/filter_synthesis.py`'s existing Pozar §§8.3–8.4 citation is unaffected |
| Fano, R.M. (1950), *J. Franklin Inst.* 249(1):57–83 and 249(2):139–154 | **STRANDED**, permanently: OpenAlex confirms `is_oa: false`, `any_repository_has_fulltext: false`. Cited only as a bibliographic target, via three independent secondary sources that agree on its pagination |
| Fano's 1947/48 MIT RLE Technical Report 41/42 (the thesis behind the 1950 paper) | **STRANDED for now, but bot-walled rather than paywalled** — MIT DSpace returns an AWS WAF JavaScript CAPTCHA, not a subscription gate. Likely retrievable by a human with a browser in one click |
| Bode, H.W. (1945), *Network Analysis and Feedback Amplifier Design* | **NOT RETRIEVED** — an Internet Archive item exists but archive.org was unreachable this pass |
| Zheng, Hao & Li (2025), *IEEE TMTT* 73(11):8451–8463 | **Still stranded**, unchanged. Nothing here relies on it. §5 makes one falsifiable prediction about it |

---

## 2. Why classical Bode–Fano does not reach this structure

Quoted **verbatim** from Steer, §7.2 (Steer's own equation numbers):

> "The Fano-Bode criteria include the term \(1/|\Gamma(\omega)|\), which is the
> inverse of the magnitude of the reflection coefficient **looking into the
> matching network** … [for a general load] `(BW/ω₀)·ln(1/Γ_avg) ≤ π/Q`
> (7.2.7) … where `Q` is that of the **load**. … If the load stores any
> reactive energy, so that the Q of the load is nonzero, the in-band
> reflection coefficient looking into the matching network cannot be zero
> across the passband. … **A match over all frequencies is only possible if
> the Q of the load is zero; that is, if the load is resistive.**"

Bode–Fano needs three distinct objects: a real source, a lossless matching
network, and a *fixed load impedance* at a well-defined internal port. For
`BANDPASS_FSS` at normal incidence the only honest identification is:

| Bode–Fano object | This structure |
|---|---|
| Source | the incidence half-space, `η₀ = 376.73 Ω`, purely real |
| Lossless matching network | the patterned conductor sheet |
| Load | **the transmission half-space, `η₀ = 376.73 Ω`, purely real** |

The load is a pure resistance: `X = 0`, `B = 0`, `Q = 0`. Substituting into
Eq. (7.2.7): `(BW/ω₀)·ln(1/Γ_avg) ≤ π/0 = ∞`. **Vacuous, and correctly so** —
Steer's own text says the vacuous case is exactly the resistive one, and here
the all-frequency match is not a theoretical curiosity but a constructible
object: remove the sheet, and free space in front of free space has
`Γ(ω) = 0` at every frequency.

**Two attempted rescues, both fail:**

- *"The aperture itself is the load, the rest of the sheet is the matching
  network."* Fails twice over. Physically, there is no port between them —
  the aperture and the surrounding conductor share one Floquet port pair and
  the theorem has nowhere to cut. Even granting an artificial cut, the
  resulting shunt element (see §3.2's parallel-LC tank) is **lossless**
  (`R = 0`), which drives Eq. (7.2.6)'s `πR/|X|` to zero — a claim of *zero*
  achievable bandwidth, contradicted by the sheet's own near-total
  transmission at resonance. A purely reactive element has nothing to
  "match"; it is removed, not matched.
- *"The load is the far half-space seen through the sheet."* This is exactly
  the identification above, and is vacuous for the same reason.

**Provenance: `CALCULATED`** (substituting `Q = 0` into a quoted, published
inequality) **and `INFERRED`** (the judgement that no alternative source/load
split rescues it) — this is this repository's own derivation; no source
states the negative result directly.

**Bode–Fano and Rozanov are nonetheless members of one family, just not the
same member.** Bernland, Luger & Gustafsson, TEAT-7193 §1, verbatim: "Some
previous examples of sum rules and physical limitations within electromagnetic
theory are in the analysis of **matching networks [10]** … **extra ordinary
transmission through sub-wavelength apertures [15]**, **radar absorbers
[29]** … and **frequency selective surfaces [16]**" — their [10] is Fano
1950, their [29] is Rozanov 2000, their [15]/[16] are the Gustafsson-group
aperture/FSS papers that the 2020 paper below descends from. Fano's matching
equations and Rozanov's absorber bound are both members of this "passive
linear time-invariant system" sum-rule family; neither is the member that
reaches a periodic aperture array. The member that does is below.

---

## 3. The bound that applies

### 3.1 The object, quoted

Ludvig-Osipov et al., §II, verbatim: *"We consider the scattering of a
linearly polarized electromagnetic plane wave by a periodically perforated
metal screen in free space … The theory is derived under the assumption that
the structure is an **infinitely thin two-dimensional periodic PEC screen**
of infinite extent in the plane normal to the incident wave direction."*
Their abstract: *"Fundamental limitations for this phenomenon are formulated
as a sum rule, relating the transmission coefficient over a bandwidth to the
static polarizability. The sum rule is rigorously derived for **arbitrary
periodic apertures in thin screens**."* One patterned conductor layer,
apertures, free space both sides, no ground plane, no spacer, two-port,
normal incidence — the `BANDPASS_FSS` architecture, in the source's own
words.

### 3.2 Why the shunt topology is a parallel-LC tank (derived, not assumed)

`rf_tools/transmissive_absorber.py`'s own ABCD/S-parameter machinery, applied
to a bare shunt admittance `Y` between two `η₀` ports, gives (algebra
elsewhere in this repo's own commit history for this document; reproduced
here for completeness):

```
S21 = 2 / (2 + Y*eta0)              S11 = -Y*eta0 / (2 + Y*eta0)
```

Near-total transmission needs `Y -> 0`; strong reflection needs `|Y| -> inf`.
Of the four one/two-element lossless shunt candidates (plain `C`, plain `L`,
series `L`-`C`, parallel `L`-`C`), only the **parallel `L`‖`C` tank** has
`Y(ω₀) = 0` at its own resonance — the other three are low-pass, high-pass or
band-**stop**. A loop-shaped *slot* cut in a conductor is the Babinet
complement of a conducting *loop patch*; `rf_tools/calculations.py`'s already
-adopted grid-impedance pair (`capacitive_grid_sheet_capacitance_f` /
`inductive_grid_sheet_inductance_h`, "the exact Babinet dual") satisfies
`Z·Z' = η₀²/4` exactly, and a conducting loop (series `L`-`C` in shunt, a
notch) maps under that relation to a parallel-`L'`-`C'` tank at the **same**
resonant frequency — a passband. This agrees with, and supplies the mechanism
behind, Munk's Group 2 loop-type classification already recorded in
`docs/element-library-prior-art.md` ("the most recommended element for both
stop and band-pass applications") and with the repo's own three-layer
reconstruction in `verification/fss_bandpass_circuit_check.py` (a single tank
is the one-pole case of that ladder).

### 3.3 The derivation chain (the paper's own steps, equation numbers theirs)

1. **Zero-thickness symmetry**: *"E(t) − E(i) = E(r) at z = 0 … This can be
   rewritten as T(k) = 1 + R(k)."*
2. **Power conservation bounds `T` to a disc**: *"|T(k)|² + |R(k)|² ≤ 1 …
   |T(k) − 1/2| ≤ 1/2"* — `T` is a holomorphic map from the upper half-plane
   to a disc centred at 1/2.
3. **A Möbius transform makes it Herglotz**: `g(k) = i·(1 − T(k))/T(k)` (Eq. 4).
4. **Low-frequency (Babinet) asymptote**: *"we utilize Babinet's principle …
   In the complementary structure, the perforations are filled with perfect
   magnetic conductor (PMC) … the polarizabilities used here are the
   polarizabilities for the complementary structure"* — `T(k) ~ −ikγ/(2A)` as
   `k → 0` (Eq. 6), `A` the unit-cell area, `γ` the magnetic polarizability of
   the **PEC-patch complement** of the aperture.
5. **A pulse Herglotz function isolates the passband**: `h_Δ(ζ) = (1/π)·ln[(ζ
   − Δ)/(ζ + Δ)]`, `Δ² = (1 − T₀²)/T₀²` (Eqs. 7–8) — `Im h_Δ(x) = 1` for
   `|x| < Δ`, `0` otherwise.
6. **The Herglotz integral identity** (Appendix A, Eq. A.2) gives `∫₀^∞ Im
   h_Δ(g(λ)) dλ = γΔπ/A` (Eq. 10, `λ = 2π/k`).
7. **Truncating to the main passband**: `∫_{λ1}^{λ2} Im h_Δ(g(λ)) dλ ≤
   γπΔ/A` (Eq. 11), giving

   > **`B = 2(λ2 − λ1)/(λ1 + λ2)  ≤  γπΔ/(Aλ₀)`**   — **Eq. (12)**,
   > `λ₀ = (λ1 + λ2)/2`.

Note `B` here is a **wavelength-domain** fractional bandwidth of the passband
edges, not the frequency-domain `(f_high − f_low)/f_center` this repo uses
for Rozanov's bound elsewhere — the two coincide only in the narrow-band
limit and must not be substituted for each other.

### 3.4 What it says, in plain terms

`γ` is the static (DC) polarizability of the **complementary patch shape**
you get by swapping metal and hole — a volume-dimensioned number describing
how much a steady field is distorted by that shape, computable without ever
running a frequency sweep: *"Testing the static polarizability for each
design candidate can thus replace numerically costly wide-frequency-range
full-wave simulations."* `A` is the unit-cell area, `λ₀` the passband centre
wavelength, `Δ` a threshold factor. Shape matters enormously at fixed open
area: *"The same total bandwidth, as achieved by cutting out 15% of the
screen with square-shaped perforations, can be attained by cutting out only
2.5% of the screen with the horseshoe-shaped perforations."*

*Plainly: how wide a window a perforated sheet can open is set by how much
electrical "bulk" one repeating cell's worth of metal has when you put it in
a steady field. Cut a cleverer hole and the number goes up; shrink the cell
relative to the wavelength and it goes down.*

---

## 4. Validity conditions — quoted, checked against this family

| # | Condition | Source | Holds for `BANDPASS_FSS`? |
|---|---|---|---|
| a | Normal incidence | Fig. 1, §II | Yes at boresight; **no** for the family's declared incidence-angle sweep axis |
| b | Single propagating Floquet mode | §II: *"For frequencies below the first grating lobe … only the fundamental mode is propagating"* | Yes — the same limit `rf_tools/transmissive_absorber.py` already states |
| c | Infinitely thin screen | §II, §III (`T = 1+R` needs it) | Relaxable and quantified, §4.1 below |
| d | PEC (lossless) conductor | §III: *"We refrain here from considering lossy materials and impedance surfaces from a theoretical perspective, as the resulting lossy case bound is in general not tight."* | **The real gap** — §4.2 |
| e | Negligible cross-polarisation | §III | Assumed, not independently checked |
| f | Sufficiently many unit cells | §V, citing another source: *"30 periods in both dimensions … sufficient to ensure a negligible difference … between finite and infinite structures"* | A panel-size requirement |
| g | Linear, causal, passive | §III | Yes |

### 4.1 Finite thickness — a close fit to this programme's own regime

§V, verbatim: *"For w/d = 1, we observe a noticeable bandwidth reduction …
However, when **w/d = 10, the difference between the transmittance of the
infinitely thin screen and the screen of thickness d is negligible, resulting
in a bandwidth reduction of about 2%** … the inequality in (12) is still
valid for cases with a finite thickness. However, when the slot width becomes
comparable to the slot thickness, the bound is not tight."*

`BANDPASS_FSS`'s description records *"square-loop slots in a ~15 um metal
layer"* with a *"gap swept 120-360 um"*. `w/d`: 120 µm/15 µm = **8.0**, 200
µm/15 µm = **13.3**, 360 µm/15 µm = **24.0** — the narrow end sits just under
the paper's "negligible" line, the rest comfortably past it. The paper's own
measured sample is an 18 µm aluminium foil with slot widths of 0.3 mm and
0.06 mm — an experiment run within a factor of ~1.2 of this programme's own
conductor thickness.

### 4.2 Conductor loss — the gap this repo already measured from the other side

§V: *"The aluminum screen has slightly lower amplitude (about 5%) in the
transmission peak … However, the bandwidth reduction is negligible."*
Conclusions: *"the approach of this paper does not directly translate to the
impedance-surface case. The impedance surface does not have zero transmission
in low-frequency limit, which is one of the key elements used in the
derivation … and therefore requires further investigation."*

Aluminium is ~3.5×10⁷ S/m; this programme's route is dispensed conductive
paste. `verification/fss_bandpass_circuit_check.py` already found, from the
opposite direction, that a lossless circuit reconstruction of a real
paste-printed bandpass FSS understated insertion loss by **1.3 dB** at
midband ("our model gave the surface free wiring, and the real one was made
of something closer to pencil lead"). **This bound caps passband *width*; it
says nothing about the insertion-loss *floor* inside that width**, and for a
paste-printed conductor that floor is not free.

---

## 5. A falsifiable prediction about the stranded Zheng/Hao/Li (2025) paper

`BANDPASS_FSS`'s prior citation named Zheng, Hao & Li (2025), *"Thickness-to
-Bandwidth Limit for Impedance Matching Metasurfaces Design According to the
Bode–Fano Theorem,"* as an unread, paraphrased lead. §2 above now makes a
testable prediction the next person with IEEE access can settle in one
paragraph:

> **Prediction (`INFERRED`).** Their derivation will be legitimate *for their
> problem* and will go vacuous for this one. An "impedance matching
> metasurface" is, by its own name, an antireflection layer in front of
> something mismatched — a dielectric wall, a substrate, an antenna aperture
> — and *that* load supplies the non-zero `Q` this family's own load lacks.
> `BANDPASS_FSS` has free space on both sides (`requires_ground_plane=False`,
> no spacer, no second layer); its load `Q` is zero, and the same argument
> applied to this geometry returns `≤ ∞`. **What to check first when it
> becomes readable:** what impedance sits behind their metasurface. Free
> space → the prediction is wrong and this section should be rewritten.
> Anything else → the prediction holds and their paper, while real and
> correct, does not reach this family.

A second, independent reason it may not reach this family regardless: whether
its object is a discrete periodic aperture array or a continuous homogenised
layer. That remains unread and is not resolved by this prediction.

---

## 6. What this changes in the repo, and what still cannot be computed

`designs/design_families.py`'s `BANDPASS_FSS.physical_bound` moves from
`UnreadPhysicalBound` to a real `PhysicalBound`, citing Ludvig-Osipov et al.
(2020) Eq. (12) via `rf_tools.physical_bounds.perforated_screen_min_polarizability_m3`
/ `perforated_screen_max_wavelength_fractional_bandwidth`.

**The one concrete gap this creates, named precisely (`CLAUDE.md`'s "when
stuck, name the missing measurement"):** the bound is stated in `γ`, the
static polarizability of the aperture's Babinet-complementary patch, and
nothing in `rf_tools` or `simulation` computes it. It is an **electrostatic**
solve (`∇×E=0`, `∇·D=0`), not a full-wave one — `simulation/meep.py` is FDTD
and is the wrong tool for it — and it is far cheaper than the frequency
sweeps this programme already runs, but it does not exist here today. Until
it does, a human supplies `γ` (from a literature value for a matching shape,
or a hand calculation) to evaluate the bound against a candidate; the loop
cannot derive it from geometry alone.

**The honest warning to attach to any candidate scored against this bound**
(the charter's assumption / cost / cheapest-test triad):

- **Assumed:** the printed conductor behaves as PEC. Validated by the source
  for aluminium; explicitly *not* extended by its authors to lossy impedance
  surfaces.
- **Costs if wrong:** the bound still correctly caps passband *width* (it
  follows from passivity, which printed paste also obeys) but says nothing
  about the insertion-loss *floor* inside that width — already measured once,
  in the pessimistic direction, at 1.3 dB.
- **Cheapest way to find out:** print one aperture array in the actual ink at
  the actual thickness and measure `|S21|` at the passband peak — the same
  first bench measurement `CLAUDE.md`'s "filling the alphabet is step one"
  already names as this programme's first job.

**Not changed by this document:** the family's declared incidence-angle sweep
axis. The bound above is normal-incidence only (§4, row a); it bounds the
boresight case and says nothing about how the passband moves off-axis, which
remains the family's own separate, undischarged concern.

---

## 7. Provenance summary

| Claim | Provenance |
|---|---|
| Steer's Fano–Bode inequalities, including the `π/Q` general form | `LITERATURE-SUPPORTED` — verbatim, open textbook |
| The parallel-LC shunt tank is the unique lossless bandpass topology; its Babinet derivation from a loop slot | `CALCULATED` — derived from `rf_tools/transmissive_absorber.py`'s and `rf_tools/calculations.py`'s own adopted formulas |
| Bode–Fano is vacuous for `BANDPASS_FSS` | `CALCULATED` (the `Q=0` substitution) + `INFERRED` (no alternative split rescues it) — no source states this negative result directly |
| Fano's and Rozanov's bounds are members of one passive-system sum-rule family, but different members | `LITERATURE-SUPPORTED` — verbatim, reference numbers checked |
| **Eq. (12): `B ≤ γπΔ/(Aλ₀)`, and every validity condition in §4** | `LITERATURE-SUPPORTED` — read in full, quoted verbatim, bibliography Crossref-confirmed, measurement-validated by the source |
| The `w/d=10 -> 2%` thickness tolerance and the aluminium-as-PEC result | `LITERATURE-SUPPORTED` — verbatim §V |
| `w/d` = 8–24 for this programme's own 15 µm / 120–360 µm regime | `CALCULATED` — arithmetic on figures already in `designs/design_families.py` |
| Prediction about Zheng, Hao & Li (2025) | `INFERRED` — explicitly falsifiable; nothing here depends on it |
