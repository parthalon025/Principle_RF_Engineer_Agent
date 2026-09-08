# The Absorber Thickness-to-Bandwidth Bound (Rozanov), Verified and Applied

**Research date:** 2026-09-03
**Serves:** [#129](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/129) — should the loop know the physical bandwidth-versus-thickness bound?
**Map:** [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104)
**Scope:** whether a hard physical limit ties an absorber's thickness to its bandwidth; the
bound's exact form, constants and assumptions; whether it binds a printed resonant
metamaterial absorber; what it permits at 0.87–2.0 mm at X-band; where the patent's
Example 3 sits against it; and whether the other design families (polarisation conversion,
beam steering, backscatter reduction) have a comparable limit.

---

## Bottom line up front

**The bound is real, it is correctly attributed, and it binds this project.** K. N. Rozanov,
*"Ultimate thickness to bandwidth ratio of radar absorbers,"* **IEEE Trans. Antennas Propag.
48(8), 1230–1234, 2000** — verified as a real paper via
[NASA ADS 2000ITAP...48.1230R](https://ui.adsabs.harvard.edu/abs/2000ITAP...48.1230R/abstract)
and cited identically by every downstream source below.

In plain terms: **absorbing radio waves takes time, and time takes thickness.** A wave has to
travel into the layer, be attenuated, and travel back out. The wider the band of frequencies
you want to kill, and the deader you want them, the more round-trip path you must give the
wave. No amount of geometric cleverness — no resonator shape, no printed pattern, no
optimisation run — buys around it, because the limit follows from causality (effects cannot
precede causes) and passivity (the skin cannot generate energy), not from any particular
design.

**The numbers for this project, all `CALCULATED` (§5, script reproduced in §9):**

| Skin thickness | Reflectivity target | Widest fractional bandwidth the bound allows at 9.5 GHz |
|---|---|---|
| 0.87 mm | −10 dB (90% of power absorbed) | **44.9%** (7.37–11.63 GHz) |
| 0.87 mm | −20 dB (99% of power absorbed) | **23.3%** (8.39–10.61 GHz) |
| 2.00 mm | −10 dB | **87.8%** (5.33–13.67 GHz) |
| 2.00 mm | −20 dB | **50.8%** (7.09–11.91 GHz) |

> **Two later corrections govern every Example 3 figure in this document. The arithmetic is
> unaffected; what it is *about* is.**
>
> **This bound does not govern Example 3, by this document's own assumption 4.** §2 lists
> *"Backed by a perfect electric conductor (PEC), no transmission"* as a stated assumption, and
> the anchor does not satisfy it: `seven-example-design-unknowns.md` records Example 3 as
> two-port with no ground plane, because FIG. 7G plots a non-zero Transmission trace and Landy
> *et al.*'s device suppresses transmission with a **cut wire**. Rozanov's own opening — read
> first-hand after this document was written — fixes a slab *"overlying a perfectly reflecting
> plane"* (`rozanov-bound-primary-source.md`; `RUNNING-LISTS.md` §3 correction 26).
>
> **And `8.5–10.5 GHz` is FIG. 7G's plot axis, not a stated requirement** (§3 correction 27).
> The bound is **linear in Δλ**, so every figure below scales one-for-one with that axis label.
>
> The figures are kept because they are correct and useful **for a ground-backed skin this
> programme builds** — ADR-0017 makes those one-port by construction. They are not statements
> about the reproduction anchor.

**An 8.5–10.5 GHz span (21.05% fractional) leaves substantial headroom at −10 dB and almost
none at −20 dB, at the thin end of the envelope.** Read as a thickness demand rather than a
bandwidth ceiling, that span requires **at least 0.392 mm at −10 dB** and **at least 0.784 mm
at −20 dB**. Against a 0.87 mm skin that is 45% and **90%** of the available thickness
respectively; against a 2.0 mm skin, 20% and 39%. So:

- At −10 dB, an 8.5–10.5 GHz span sits at roughly **47% of the bandwidth limit** for 0.87 mm
  and 24% for 2.0 mm — comfortable headroom, and #129's "rough arithmetic puts that comfortably
  inside what 2 mm allows" is **confirmed** *for a ground-backed skin*. Stated here as a fact
  about Example 3 in earlier revisions; it is not one (see the note above).
- At −20 dB, a 0.87 mm skin is at **90% of the limit** — that requirement is at the wall, and a
  search that fails to meet it is probably failing for a physical reason, not a design reason.

**The reflectivity target matters more than the thickness does.** Going from −10 dB to −20 dB
doubles the required thickness exactly (the bound is linear in the dB figure). This is the
single most important thing for the loop to internalise: a customer who tightens a
reflectivity spec by 10 dB has doubled the physical thickness demand, not made the search
harder.

**Equivalent bounds for the other families (§7):** a directly analogous thickness–bandwidth
sum rule **does exist** for **reflection-phase surfaces** (Gustafsson & Sjöberg 2010/2011,
Brewitt-Taylor 2007), which is the family that beam steering and AMC-checkerboard backscatter
reduction are built from — `Bλ₀/d ≤ 2π tan(Φ/4)`, i.e. ≈ 2.6 d/λ₀ for the usual ±45° phase
window. **No** thickness–bandwidth bound exists in the retrieved literature for polarisation
conversion; what exists there is a *single-frequency* thickness-versus-efficiency bound
(Abdelrahman & Monticone 2022), and its authors state the bandwidth version is unsolved. So
this is **a per-family property, not a common field** — but it is a per-family property with
**two** distinct shapes, not "absorbers have one and nobody else does."

---

## 1. The bound's exact statement and form

### 1.1 What Rozanov's own abstract says

> "The analytic properties of the reflection coefficient of a multilayer metal-backed slab are
> analyzed, resulting in a new form of the dispersion relationship that characterizes the
> integral of the reflectance over wavelength in terms of the total thickness and averaged
> static permeability of the slab. This may be transformed to an inequality that produces the
> least thickness to bandwidth ratio achievable for a physically realizable radar absorber. …
> The least thickness of a 10-dB broad-band dielectric radar absorber is shown to be **1/17 of
> the largest operating wavelength**."
> — Rozanov (2000), abstract as recorded by [NASA ADS](https://ui.adsabs.harvard.edu/abs/2000ITAP...48.1230R/abstract)

**The paper itself is stranded.** IEEE Xplore returns 403 to automated fetches from this
environment, and no open-access copy of the 2000 paper was located. Everything quoted below as
"the bound" is therefore **restated from sources that cite it**, attributed to those sources.
Four independent restatements agree, and the "1/17" figure in Rozanov's own abstract is
**reproduced arithmetically** from the restated inequality in §1.4 — which is the strongest
verification available without the original.

### 1.2 The sum-rule form (the integral relation)

Firestein, Shlivinski & Hadad, *"Sum rule bounds beyond Rozanov criterion in linear and
time-invariant thin absorbers,"* **Phys. Rev. B 108, 014308 (2023)**, preprint
[arXiv:2210.06949](https://arxiv.org/abs/2210.06949), §II, Eq. (1) — quoted verbatim:

> "For this scenario, Rozanov [20] established a tradeoff between the power absorption
> efficiency Ã(λ) = 1 − |ρ(λ)|² given in terms of the reflection coefficient ρ(λ), and the
> bandwidth
>
> | ½ ∫₀^∞ ln[1 − Ã(λ)] dλ | = | ∫₀^∞ ln|ρ(λ)| dλ | ≤ **2π² μ_r d**.    (1)
>
> Eq. (1) implies that the tradeoff between the absorption efficiency and the bandwidth depends
> only on the static (long wavelength) relative permeability μ_r = μ/μ₀ and the layer thickness
> d."

Padilla, Deng, Khatib & Tarokh, *"Fundamental absorption bandwidth to thickness limit for
transparent homogeneous layers,"* **Nanophotonics (2023)**, preprint
[arXiv:2308.14839](https://arxiv.org/abs/2308.14839), Eq. (2), citing Rozanov as their ref [7]
— quoted verbatim:

> "d_RL ≥ (1 / 2π²μ_s) | ∫₀^∞ ln |r̃(λ)| dλ | ≡ d_R    (2)
> where μ_s = Re{μ}|_{λ→∞} is the static permeability of the absorber."

**Constants:** the only constant is **2π² = 19.739209**. Nothing else. The bound is
**linear** in thickness and **linear** in static permeability.

**In plain terms.** Read `∫₀^∞ ln|ρ(λ)| dλ` as an *absorption budget*. At every wavelength you
spend some of it: absorbing nothing costs zero (ln 1 = 0), absorbing a lot costs a lot
(ln 0 → −∞). The total you may spend across the entire spectrum, from DC to light, is fixed at
`2π² μ_s d`. Thickness buys budget; static permeability multiplies it. You choose only how to
*spend* it — a little absorption over a wide band, or a lot over a narrow one.

### 1.3 Why the budget is what it is

Both restatements derive it the same way: `ρ(λ)` is analytic in the upper half of the complex
λ-plane (that is causality plus passivity), and at long wavelength it behaves as

> "ρ(λ) ∼ −1 + j 4πμ_r d / λ  as λ → ∞"   — Firestein et al., Eq. (2)

Everything else is Cauchy's theorem applied to that asymptote. **The whole bound is set by how
the structure looks at DC.** Firestein et al. make this explicit: *"the static parameters
themselves set the bound over the entire real wavelength axis without any additional
frequency dependent contributions."* Note what this does **not** contain: permittivity. The
budget does not depend on ε at all — a high-εr substrate does not buy you absorption budget.

### 1.4 The engineering form, and the arithmetic that verifies it

The form actually used in design practice, from Costa & Monorchio et al., *"Ultra-thin and
flexible microwave metasurface absorbers based on resistive patches,"* **Int. J. Microwave and
Wireless Technologies**, [Cambridge Core](https://www.cambridge.org/core/journals/international-journal-of-microwave-and-wireless-technologies/article/ultrathin-and-flexible-microwave-metasurface-absorbers-based-on-resistive-patches/48D423A3150F85A87A886FC82E23C627)
— quoted verbatim:

> "|ln{ρ₀}| Δλ ≤ 2π² Σᵢ{μᵢ dᵢ}"
>
> and for a single non-magnetic layer: "|ln{ρ₀}| Δλ ≤ 2π² d"

where ρ₀ is the worst in-band reflection-coefficient magnitude and Δλ = λ_max − λ_min.

This is the sum rule with the *most permissive possible* assumption about out-of-band
behaviour substituted in: `|ρ| = ρ₀` inside the band and `|ρ| = 1` (perfect mirror, zero
absorption) everywhere outside it. That spends the whole budget in-band and none elsewhere.

**Verification.** Rozanov's headline result — "the least thickness of a 10-dB broad-band
dielectric radar absorber is 1/17 of the largest operating wavelength" — falls straight out.
Broadband means λ_min → 0, so Δλ → λ_max; dielectric means μ_s = 1; 10 dB means
|ln ρ₀| = 10·ln(10)/20 = 1.151293. Then

```
d / λ_max  ≥  1.151293 / 19.739209  =  0.058325  =  1 / 17.15
```

**`CALCULATED`. 1/17.15 reproduces Rozanov's own stated 1/17.** This is the load-bearing
check: it confirms both the constant 2π² and — critically — that `ρ` in the integral is the
**voltage** reflection coefficient, not the power reflectance. If it were the power
reflectance the answer would be 1/8.6, not 1/17. See §8.1 for why that trap matters.

A second, independent cross-check. Kim et al., *"Ultrawide bandwidth electromagnetic wave
absorbers using a high-capacitive folded spiral frequency selective surface in a multilayer
structure,"* **Sci. Rep. 9, 16359 (2019)**,
[PMC6848185](https://pmc.ncbi.nlm.nih.gov/articles/PMC6848185/), state the same bound as
`f_L = cΓ₀ / (172 d)` with Γ₀ in dB. Rearranging the inequality above with a dB argument gives
the constant `2π² × 20/ln(10)` = **171.45**. **`CALCULATED`, matches their 172.**

---

## 2. The assumptions, precisely — every one a place it might not apply

| # | Assumption | Source | Does it hold for this project? |
|---|---|---|---|
| 1 | **Normal incidence** | "A normal incidence plane wave impinges a Dallenbach layer" — Firestein et al., Fig. 1 caption. Explicitly: "Rozanov's derivation is valid only for layer impinged by a normally incident plane wave" — Firestein, Shlivinski & Hadad, [arXiv:2305.13295](https://arxiv.org/abs/2305.13295) | **Only at boresight.** Relaxed form in §2.1. |
| 2 | **Linear and time-invariant (LTI)** | "Under linearity and time invariance (LTI) assumptions Rozanov has established analytically a sum-rule trade-off" — Firestein et al., abstract | **Holds.** Printed passive skins are LTI. |
| 3 | **Passive and causal** (Kramers–Kronig) | "layer that is passive, causal, and linear time-invariant" — Firestein et al., text at Eq. (17) | **Holds.** No sources, no switching. |
| 4 | **Backed by a perfect electric conductor (PEC), no transmission** | "backed by a perfect electric conductor (PEC). See Fig. 1" — Firestein et al., §II; "the PEC boundary enforces that there is no transmitted wave beyond the absorbing layer" — [arXiv:2305.13295](https://arxiv.org/abs/2305.13295) | **Holds if the skin has an opaque ground plane.** This is the one genuinely escapable assumption — see §2.2. |
| 5 | **Static permeability μ_s is the only material parameter that enters** | "depends only on the static (long wavelength) relative permeability μ_r … and the layer thickness d" — Firestein et al., after Eq. (1) | **Holds, at μ_s = 1** for a non-magnetic skin. §4. |
| 6 | **Infinite lateral extent, plane-wave illumination** | Implicit in the transmission-line derivation; "The structure extends to infinitely in the x and y directions" — [arXiv:2305.13295](https://arxiv.org/abs/2305.13295) | **Approximately.** The 11×11-cell coupons (#106) are finite; edge effects are outside the model. |
| 7 | **Bandwidth definition: none is imposed** | The sum rule is over all λ; a bandwidth appears only when you *choose* an out-of-band model | **This is a choice we make, not a physical fact.** See §8.2 — it is the largest source of looseness. |

### 2.1 Oblique incidence — the assumption most likely to bite a conformal skin

Extended by Doane, Sertel & Volakis, *"Matching bandwidth limits for arrays backed by a
conducting ground plane,"* IEEE Trans. Antennas Propag. 61(5), 2511–2518, 2013 (IEEE, not
retrieved), restated verbatim in Firestein, Shlivinski & Hadad,
[arXiv:2305.13295](https://arxiv.org/abs/2305.13295), Eq. (1):

> "| ∫₀^∞ ln |ρ(λ, θ)| dλ | ≤ 2π² μ_s d × { cos(θ), TE ; 1/cos(θ), TM }"

So off-normal, the budget **shrinks by cos θ for TE** (electric field parallel to the surface)
and **grows by 1/cos θ for TM**. The binding case is TE. `CALCULATED`, for a 2.0 mm
non-magnetic skin at 9.5 GHz, −10 dB:

| Incidence | TE factor | Max fractional bandwidth |
|---|---|---|
| 0° | 1.0000 | 87.75% |
| 30° | 0.8660 | 79.31% |
| 45° | 0.7071 | 67.96% |
| 60° | 0.5000 | 50.82% |

**In plain terms:** a skin wrapped round a curved host is hit at a spread of angles at once,
and for one of the two polarisations the physics gets *stricter* the further off-normal you
go. A design specified at normal incidence and then required to hold up to 60° has, for TE,
only 57% of the budget it started with. If a requirement carries an angular spec, the loop
should evaluate the bound at the **worst TE angle in the spec**, not at boresight.

### 2.2 The PEC backing — the one assumption a printed skin might genuinely break

Firestein et al. (2023) is the paper that establishes this. Their whole result is that
replacing the PEC ground with a **partially transparent (penetrable) impedance sheet** admits
a *strictly weaker* bound, and they demonstrate passive LTI designs that beat Rozanov. For an
inductive sheet of inductance L their Eq. (10)/(12) replaces `d` with `d + L/(μ₀μ_r)` — an
*effective* extra thickness that costs nothing physically. They summarise:

> "quite surprisingly, with a proper design, we show that by allowing transmittance through the
> absorbing layer, the net absorbance can be largely increased."

**Whether this is a loophole for us depends entirely on what is behind the skin.** If the skin
is bonded to a metal airframe, the airframe is the PEC and there is no loophole. If the skin
is a free-standing coupon or is applied to a dielectric host and its own printed ground plane
is a *finite-sheet-resistance* printed film rather than solid metal, the assumption is
formally violated — and the escape is real but small unless the sheet is deliberately designed
to transmit. Their same paper closes the other half of the door: for a **reactive** sheet with
`k > 1`, "it is impossible to design a Dallenbach absorber that improves the absorption
performances with respect to Rozanov bound," and for a resistive sheet the maximum
long-wavelength absorption saturates at 0.5. **`LITERATURE-SUPPORTED`, not yet applied to this
geometry.** Recorded as a real open question, not claimed as an advantage.

---

## 3. Does it apply to a resonant metamaterial absorber? Yes, and the literature says so explicitly

This is stated, not merely implied, by three sources.

**Rozanov's own scope** covers "a multilayer metal-backed slab" with the right-hand side
`2π² Σᵢ μ_{s,i} dᵢ` summed over layers — so a stack is in scope from the start (ADS abstract;
sum form quoted by Costa & Monorchio, §1.4).

**Firestein et al. (2023), §I**, put metamaterials in scope by construction:

> "Usually the absorbing bulk is composed of LTI materials, which may be composed of a
> continuous matter, laminate composite or **periodic lattice of conductive, dielectric or
> magnetic elements at scales that are substantially smaller than the operating wavelength,
> i.e., metamaterials.**"

and, on artificial magnetic conductors specifically, §III:

> "Ideally infinite magnetic conductance, i.e., the so called, artificial magnetic conductor
> (AMC) can be synthesized in a narrow frequency band as an high impedance surface. This in
> fact was one of the first practical applications of metamaterials … However, **their physical
> structure renders them to exhibit long wavelength characteristics as of a PEC backed
> structure and therefore they comply with Rozanov's bound.**"

**Padilla et al. (2023), §I**, state validity for "any single-layer (or multi-layer) metal
backed structure," and §5.2 applies the machinery to metal-based and all-dielectric
metamaterial absorbers by simulation.

**The mechanism, in plain terms.** At long wavelength a subwavelength periodic pattern cannot
be resolved as a pattern — the wave sees an averaged sheet. Because the bound is set *entirely*
by the DC behaviour (§1.3), a resonant metamaterial absorber over a ground plane has exactly the
same DC signature as a homogeneous slab over a ground plane, so it inherits exactly the same
budget. **Resonance changes how you spend the budget, never how large it is.** This is the
direct answer to #129's note about #128: *moving the loss into the printed pattern does not
move the bound*, and the literature confirms that read.

**One qualification worth recording.** Padilla et al. compute μ_s and ε_s for metamaterial
absorbers by S-parameter retrieval "from the low-frequency limit … of the effective material
parameters," and observe that a 2×2 supercell "deviates further from the limit, suggesting
higher values of μ_s and ε_s." So for a metamaterial the μ_s in the bound is the *retrieved
effective* static permeability of the composite, not the permeability of the constituent
materials. For open printed traces on a dielectric — no closed conducting loops, no magnetic
ink — μ_s = 1 is the standard and conservative choice, but it is an assumption the loop should
label as such, not a measurement.

**Grating-lobe caveat.** The bound constrains `|ρ|`, the specular reflection coefficient. That
equals the total scattered field only while the unit cell is small enough that no diffracted
order propagates. Gustafsson & Sjöberg make the same restriction explicit for their surface
bound ("operating below the first grating lobe"). For X-band cells at a few tenths of a
wavelength this holds comfortably; it would not hold for a super-cell deliberately sized to
diffract. See §7.3.

---

## 4. The magnetic term — how much a non-magnetic absorber gives up

**The bound scales linearly with static permeability μ_s.** A material with μ_s = 5 gets five
times the budget of a non-magnetic one at the same thickness, or reaches the same performance
at one-fifth the thickness. Ikonen, Rozanov, Osipov & Tretyakov,
[arXiv:physics/0603116](https://arxiv.org/abs/physics/0603116), §1, state it directly:

> "According to the Rozanov limit [29] for the thickness to bandwidth ratio of radar absorbers,
> the thickness of the absorber at microwave frequencies (with a given reflectivity level) is
> **bounded by the static value of μ of the absorber**."

`CALCULATED`, an 8.5–10.5 GHz span at −10 dB (FIG. 7G's plot range, not a requirement — see the
note in the bottom line), and the widest bandwidth a 2.0 mm skin could reach at 9.5 GHz:

| μ_s | Least thickness for an 8.5–10.5 GHz span @ −10 dB | Max fractional BW at d = 2.0 mm |
|---|---|---|
| **1 (this project)** | **0.3918 mm** | **87.8%** |
| 2 | 0.1959 mm | 128.1% |
| 5 | 0.0784 mm | 166.6% |
| 10 | 0.0392 mm | 182.4% |
| 20 | 0.0196 mm | 191.0% |

Note the diminishing return in the right column: past μ_s ≈ 5 the bandwidth saturates, because
a band symmetric about 9.5 GHz cannot exceed 200% fractional (its lower edge would hit DC).
The left column keeps improving linearly, which is the real reason ferrite loading is used —
it buys **thinness**, not unbounded bandwidth.

### 4.1 But you cannot actually have μ_s = 20 at X-band

The bound uses the **static (DC)** permeability, and nature ties static permeability to how
high in frequency the material stays magnetic at all. Ikonen et al., Eq. (18):

> "(μ_s − 1) · ω_res = (4π/3) γ 4πM_s"  — Snoek's law, with γ ≈ 3 GHz/kOe

`CALCULATED` (dividing by 2π to get linear frequency: (μ_s − 1)·f_res = (2/3)·γ·4πM_s):

| Material | 4πM_s | Snoek constant | μ_s available if f_res = 9.5 GHz | if f_res = 12 GHz |
|---|---|---|---|---|
| typical soft ferrite | 5 kOe | 10.0 GHz | **≤ 2.05** | ≤ 1.83 |
| iron (highest practical M_s) | 21.5 kOe | 43.0 GHz | **≤ 5.53** | ≤ 4.58 |

So at X-band the honest magnetic advantage is roughly **2× for a ferrite composite and at best
5–6× for an iron-flake composite**, before dilution by volume fraction in a printable
composite, and before the eddy-current and damping penalties Rozanov himself catalogues in
[*"Acher's constraint on the high-frequency magnetic performance of composites"*](https://www.ursi.org/proceedings/procGA11/ursi/B06-7.pdf)
(URSI GASS 2011 — open access, and Rozanov-authored, which makes it the closest thing to a
primary source retrieved here). Ikonen et al. note hexagonal ferrites can reach "μ_s … as high
as 10 to 20" — but only with f_res = 3 GHz, i.e. a material that has already gone
non-magnetic well before X-band.

**And that is exactly where the bound is loosest.** A material with μ_s = 20 and f_res = 3 GHz
has permeability ≈ 1 at 9.5 GHz; it holds a large *budget* it physically cannot spend in
X-band. Rozanov wrote a follow-up on precisely this gap (Rozanov & Starostenko, *"Influence of
permeability dispersion on the bandwidth of magnetic radio absorbers,"* J. Communic. Technol.
Electronics 48, 652–659, 2003 — cited in the URSI paper, not retrieved).

**Practical consequence for this project.** Being non-magnetic costs us roughly a factor of 2
to 5 in permitted thinness at X-band versus a ferrite-loaded absorber — real, but far less
than the μ_s = 20 headline suggests. It also has a compensating benefit for the loop: **at
μ_s = 1 exactly, the bound has no dispersion looseness in it.** For non-magnetic absorbers the
bound is at its strictest *and* its most trustworthy. That is what makes it usable as a
stopping condition here in a way it would not be for a ferrite design.

---

## 5. Working the numbers for this case

All numbers `CALCULATED` by the script in §9, reproduced there in full — source and output
both — so every figure can be re-run and checked rather than taken on trust.

### 5.1 The setup

- c = 299.792458 mm·GHz, so λ (mm) = 299.792458 / f (GHz)
- 2π² = 19.739209
- μ_s = 1 (non-magnetic, no ferrite loading — the project's stated envelope)
- Centre frequency 9.5 GHz → λ_c = 299.792458 / 9.5 = **31.5571 mm**
- Reflectivity in dB → |ln ρ₀| = |Γ_dB| · ln(10)/20:
  - −10 dB → |ln ρ₀| = 10 × 0.1151293 = **1.151293**
  - −20 dB → |ln ρ₀| = 20 × 0.1151293 = **2.302585**

**Plain reading of the dB figures.** −10 dB means the skin sends back one-tenth of the power
that hit it (90% absorbed); −20 dB means one-hundredth (99% absorbed).

### 5.2 Turning the bound into a fractional bandwidth

The bound is in *wavelength* width Δλ, but requirements are written in *frequency* width. For
a band symmetric in frequency about f_c with fractional bandwidth B:

```
f_min = f_c(1 − B/2),   f_max = f_c(1 + B/2)
Δλ   = c/f_min − c/f_max = (c/f_c) · B / (1 − B²/4) = λ_c · B / (1 − B²/4)
```

Substituting into `|ln ρ₀| Δλ ≤ 2π² μ_s d` and writing `K = 2π² μ_s d / (|ln ρ₀| λ_c)`:

```
B / (1 − B²/4) ≤ K     ⇒     (K/4)B² + B − K = 0     ⇒     B ≤ 2(√(1+K²) − 1) / K
```

(The `1/(1 − B²/4)` factor is why the answer is not simply `B ≤ K`: a fixed *frequency* width
is a *wider* wavelength width the lower in frequency you go, so wide bands are penalised more
than the naive reading suggests. At B = 21% it costs 1.1%; at B = 88% it costs 24%.)

### 5.3 Worked: 0.87 mm at −10 dB

```
K = 19.739209 × 1 × 0.87 / (1.151293 × 31.5571)
  = 17.17311 / 36.32849
  = 0.472679
B = 2 × (√(1 + 0.472679²) − 1) / 0.472679
  = 2 × (√1.223425 − 1) / 0.472679
  = 2 × 0.106096 / 0.472679
  = 0.212192 / 0.472679
  = 0.44888  →  44.89%    (7.37 – 11.63 GHz)
```

### 5.4 All four cases

| d | Target | K | Max B | Band it corresponds to |
|---|---|---|---|---|
| 0.87 mm | −10 dB | 0.472679 | **44.89%** | 7.37 – 11.63 GHz |
| 0.87 mm | −20 dB | 0.236339 | **23.31%** | 8.39 – 10.61 GHz |
| 2.00 mm | −10 dB | 1.086618 | **87.75%** | 5.33 – 13.67 GHz |
| 2.00 mm | −20 dB | 0.543309 | **50.82%** | 7.09 – 11.91 GHz |

### 5.5 The same question asked the other way — where does an 8.5–10.5 GHz span sit?

Worked directly for that span. **Framed as Example 3's position in earlier revisions; it is not
one** — the anchor is unbacked, so this bound does not govern it, and 8.5–10.5 GHz is FIG. 7G's
plot axis rather than a stated requirement (see the note in the bottom line). The arithmetic
below stands for a ground-backed skin over that span:

```
λ_max = 299.792458 / 8.5  = 35.2697 mm
λ_min = 299.792458 / 10.5 = 28.5517 mm
Δλ    =                      6.7180 mm
fractional BW = (10.5 − 8.5)/9.5 = 21.05%

d_min(−10 dB) = 1.151293 × 6.7180 / 19.739209 = 7.73437 / 19.739209 = 0.3918 mm
d_min(−20 dB) = 2.302585 × 6.7180 / 19.739209 = 15.46875 / 19.739209 = 0.7837 mm
```

| Reflectivity target over an 8.5–10.5 GHz span | Least thickness the bound demands | Fraction of a 0.87 mm skin | Fraction of a 2.0 mm skin |
|---|---|---|---|
| −10 dB | 0.3918 mm | **45.0%** | 19.6% |
| −20 dB | 0.7837 mm | **90.1%** | 39.2% |

**Where a ground-backed skin sits over that span: comfortable at −10 dB, at the wall at −20 dB
when thin.** *This was written as "where Example 3 sits". It is not — the bound does not govern
an unbacked structure, and the span is a plot axis (see the note in the bottom line).* The
patent's own thickness for Example 3 specifically is not recorded in this repo — 0.87–2.0 mm is
the range across all seven examples (`docs/HANDOFF-metamaterial-printing-grill.md:33`), and the
example is on FR4, εr 4.8, tanδ 0.017 (`:53`). **Pinning Example 3's actual thickness from the
drawings is the single missing input** that would turn "45% or 90% of the limit" into one
number.

### 5.6 The "impossible requirement" case from #129

#129 poses: *"A customer asking for 60% bandwidth in a 1 mm skin is not a hard design problem,
it is a physically unsatisfiable one."* `CALCULATED`, at 9.5 GHz centre (6.65–12.35 GHz):

```
λ_max = 299.792458 / 6.65  = 45.0816 mm
λ_min = 299.792458 / 12.35 = 24.2747 mm
Δλ    =                       20.8069 mm

d_min(−10 dB) = 1.151293 × 20.8069 / 19.739209 = 1.2136 mm   →  1 mm is IMPOSSIBLE
d_min(−20 dB) = 2.302585 × 20.8069 / 19.739209 = 2.4271 mm   →  1 mm is IMPOSSIBLE
```

**The claim in #129 is confirmed, and the loop can now say something better than "no."** It can
say: *"60% at −10 dB needs at least 1.214 mm; your 1 mm skin is 18% too thin. Either give me
1.22 mm, or accept 50.8% bandwidth at 1 mm, or relax the target to −8.2 dB."* Each of those
three is `CALCULATED` from the same inequality — `max_fbw(-10, 1.0, 9.5)` = 50.82%, and
`19.739209/20.8069 = 0.9487` → `0.9487 × 20/ln(10)` = 8.24 dB. That is the trade-space
language #117 adopted, delivered before a single simulation runs.

---

## 6. How close do real absorbers actually get? (The looseness caveats)

This is the part that decides whether "you are at 78% of the limit" is a usable stopping
condition or a comforting number.

### 6.1 As mathematics, the bound is tight

Firestein et al. (2023), §V, solve an optimisation over (ε, σ) for a Dallenbach layer subject
to Kramers–Kronig and report:

> "It can readily be observed that the bound in Eq. (12) is tight, with 0.99 < τ_[λ1,λ2] ≤ τ ≤ 1"

and their Eq. (12) reduces to Rozanov's in the PEC limit ("for smaller inductance values,
L < 0.1 (μH), where the inductive sheet becomes effectively a short circuit, i.e., a PEC
boundary, the new absorption bound reduced to Rozanov's bound"). **So the bound is not slack.
An optimal homogeneous layer reaches ~99% of it when the integral is taken over the whole
spectrum.**

### 6.2 In practice, resonant absorbers land well short — for two different reasons

**Padilla et al. (2023), §5.2** — the most directly relevant comparison, and the one to read
carefully:

> "Interestingly, all the metamaterials explored fall well short of the fundamental thickness to
> bandwidth limit, a result of their narrow-band absorption. Notably, the 2 × 2 resonator
> supercell, expected to broaden the ADM's absorptance peak, deviates further from the limit,
> suggesting higher values of μ_s and ε_s."

Their own supplemental, however, immediately qualifies it:

> "It should be noted that we reduced the bandwidth of the integral significantly to ensure
> reasonable computational costs. Hence, the large discrepancy between the limit and the
> metamaterial absorbers can be attributed to the much narrower bandwidth of the absorbers
> compared to the limit."

**So "metamaterials fall well short" is partly a truncated-integral artefact, not purely a
physical finding.** Report the qualification alongside the headline; it is exactly the kind of
detail a "% of the limit" metric would silently swallow.

**Costa & Monorchio et al. (IJMWT)** — a flexible X-band metasurface absorber on resistive
patches, i.e. the closest published analogue to this project's design family:

> "By limiting the integral within λ_min = 0.025 m and λ_max = 0.033 m, corresponding to a
> frequency range of [9,12] GHz, we estimate the minimum thickness required to obtain the
> reflection coefficient of the R_s = 0.34 Ω/sq case of Figure 13, found to be equal to
> d_min = 0.19 mm."
>
> "The realized substrate thickness of the 3×3 MSA is h = 0.27 mm, which is reasonably close to
> the above estimated theoretical minimum."

**0.27 mm realised against 0.19 mm bound = 1.42×.** Note what they did: they integrated the
**actual simulated reflectivity curve** over 9–12 GHz, not a rectangular in-band/out-of-band
model. That is the rigorous way to apply the bound, and it is a different (and stricter) number
than the rectangular form in §5 would give.

### 6.3 The dominant looseness is the out-of-band model, and it is *our* choice

The rectangular assumption behind §5 — `|ρ| = ρ₀` in band, `|ρ| = 1` everywhere else — is
**physically impossible for a real absorber**. Any real lossy structure absorbs *something*
outside its design band; a resonant one has skirts by construction. Every joule absorbed out of
band is budget spent, and it is subtracted from what is available in band. **The rectangular
bound is therefore not a target, it is a ceiling on a ceiling.** A design at 70% of it may
already be at 95% of what its own dispersion permits.

This is precisely the doubt #129 raised — *"a candidate can sit far below it for perfectly good
reasons, so 'you are at 40% of the limit' is weaker information than it sounds"* — and the
literature vindicates it. **The fix is available and cheap:** compute the integral against the
candidate's own simulated `|ρ(λ)|` curve, as Costa & Monorchio do, rather than against a
rectangle. That converts a loose ceiling into a genuinely diagnostic number.

### 6.4 Summary of published "how close" data points

| Design | Realised d | Bound d_min | Ratio | Source |
|---|---|---|---|---|
| Optimal homogeneous Dallenbach layer (theory) | — | — | **~1.01×** (τ > 0.99) | Firestein et al. 2023, §V |
| Flexible X-band metasurface absorber, resistive patches | 0.27 mm | 0.19 mm | **1.42×** | Costa & Monorchio, IJMWT |
| Multilayer folded-spiral FSS, 4.7–56.4 GHz | 7.0 mm | 3.41 mm (see §8.1) | **2.05×** | Sci. Rep. 9, 16359 (2019) |
| THz metal and all-dielectric metamaterial absorbers | — | — | far short (truncation-affected) | Padilla et al. 2023, §5.2 |
| High-impedance surfaces (the §7 analogue) | — | — | **82–99%** of bound | Gustafsson & Sjöberg 2010, §6 |

---

## 7. Do the other design families have an equivalent bound?

Directly relevant to how the design-family registry (#109) is shaped. The answer is **not**
"absorbers yes, everyone else no." There are two distinct bound *shapes*, and the families
split across them.

### 7.1 Reflection-phase surfaces (beam steering, AMC-based backscatter reduction) — YES, a real thickness–bandwidth bound

Gustafsson & Sjöberg, *"Physical bounds and sum rules for high-impedance surfaces,"* **Technical
Report LUTEDX/(TEAT-7198)/1-19/(2010)**, later IEEE Trans. Antennas Propag. 59(6), 2196–2204,
2011 — [open-access author manuscript at Lund](https://lup.lub.lu.se/search/files/6059224/1698605.pdf).
Their abstract:

> "Here, a sum rule is presented that relates frequency intervals having high impedance with the
> thickness of the structure. The sum rule is used to derive physical bounds on the bandwidth
> for high-impedance surfaces composed by periodic structures above a perfectly conducting
> ground … and show that the physical bounds are tight."

Main results, quoted verbatim (Eqs. 4.10, 4.11, 5.1):

> "B λ₀ / d ≤ 4π μ_s^max max_{λ∈B} |Y(λ)| × { 1 lossy case ; 1/2 lossless case }"   (4.10)
>
> "A common case is when the high-impedance surface is realized by lossless, non-magnetic
> materials and operating below the first grating lobe. Allowing max|Y(λ)| = 1/2, the
> normalized bandwidth is bounded by **B λ₀ / d ≤ π**."   (4.11)
>
> "B λ₀/d ≤ 2π tan(Φ/4) ≈ { π²Φ/2, Φ ≪ 1 ; 2π, Φ = π ; **2.6, Φ = π/2** }"   (5.1)

where B is fractional bandwidth, λ₀ the centre wavelength, d the thickness, and Φ the allowed
reflection-phase window (the reflection phase stays within |φ| ≤ Φ/2). Earlier and looser
bounds are due to Brewitt-Taylor, *"Limitation on the bandwidth of artificial perfect magnetic
conductor surfaces,"* IET Microw. Antennas Propag. 1(1), 255–260, 2007 (IET, not retrieved;
restated in Gustafsson & Sjöberg Eq. 5.2 as `Bλ₀/d ≤ πΦ` and `Bλ₀/d ≤ π²/ln(2/Φ)`).

**Plain reading, and the same structure as Rozanov.** A grounded periodic surface can hold its
reflection phase inside a tolerance window only over a bandwidth proportional to its thickness.
The familiar ±45° AMC criterion (Φ = π/2) gives **B ≤ 2.6 d/λ₀**. Non-magnetic and lossless
again; μ_s again multiplies; the ground plane again must be a conductor.

`CALCULATED` for this envelope at 9.5 GHz (λ₀ = 31.5571 mm), Φ = π/2:

- d = 0.87 mm → B ≤ 2.6 × 0.87/31.5571 = **7.2%**
- d = 2.00 mm → B ≤ 2.6 × 2.00/31.5571 = **16.5%**

That is a **much** harsher regime than the absorber case, and it is worth saying so plainly:
**a phase-stable surface at 2 mm gets about 16% bandwidth where an absorber at 2 mm gets 88%.**
If the registry carries one bound field, it must carry which *shape* of bound applies, because
the two differ by a factor of five at the same thickness.

**How close real designs get:** Gustafsson & Sjöberg's §6 numerical examples report
`B/B_bound ≈ 82%`, `91%`, `98%`, `99%`. **This bound is tight in practice as well as in
theory** — tighter, empirically, than Rozanov's is for resonant absorbers.

**Caveat on the extrapolation to beam steering.** Gustafsson & Sjöberg state the result for
*high-impedance* (near-zero-phase) surfaces and, in Eq. (5.1), for an arbitrary phase window Φ.
A reflectarray/beam-steering element is the same physical object — a periodic pattern over a
ground plane — evaluated for how far its phase drifts with frequency, so the sum rule applies
element-by-element. **But no retrieved source states a bound on beam-steering bandwidth as
such** (array factor, scan angle, aperture efficiency). Treat the element-level phase-stability
bound as `LITERATURE-SUPPORTED` and the step to array-level steering bandwidth as `INFERRED`.

### 7.2 Polarisation conversion — NO thickness–bandwidth bound; a different bound exists

Abdelrahman & Monticone, *"How thin and efficient can a metasurface reflector be? Universal
bounds on reflection for any direction and polarization,"*
[arXiv:2208.05533](https://arxiv.org/abs/2208.05533). This is a **single-frequency
thickness-versus-efficiency** bound, derived from energy conservation and passivity by
Lagrangian duality — a different animal from a sum rule. Assumptions, verbatim from their
conclusion:

> "The only assumptions are that the structure is passive, with a surface area much larger than
> its thickness, and is made of a single local, isotropic, and nonmagnetic material."

Their result for cross-polarised reflection, in the thin lossless limit, "converges to
Ũ_PC → 1/4" — at most 25% of incident power can be converted by an infinitesimally thin
passive lossless layer, "consistent with" earlier independent derivations. Their worked
microwave example is startlingly close to this project's regime:

> "Using a low-loss metal like Cu, it was possible to create a very thin and efficient
> polarization converter metasurface, with R_PC ≈ 0.8 at 10 GHz, given h = 1.27 mm or
> h/λ = 0.04 … our derived bound in Eq. (11) suggests that a further minimization can be
> achieved … the minimum possible thickness to achieve R_PC = 0.8, using the same material, is
> h_min = 0.003λ, which is more than an order of magnitude lower than the proposed design."

And explicitly, in their own conclusion, that the bandwidth version does not yet exist:

> "more work is needed to extend these results to the problem of broadband maximization of
> reflection, establishing fundamental tradeoffs between bandwidth, thickness, and
> reflectance."

**So for polarisation conversion the honest position is: there is no thickness–bandwidth bound
in the literature as of this search.** What there is instead is a *feasibility* bound —
"can this efficiency be reached at this thickness at all, at one frequency" — which is
genuinely useful as a `REQUIREMENTS`-stage check but answers a different question and cannot
serve as a stopping condition for a bandwidth objective.

**And note the direction of the finding:** for a polarisation converter the bound says the
published 1.27 mm design is **more than 10× thicker than necessary**. That is the opposite
diagnosis from the absorber case, where designs sit at 1.4–2× the limit. A registry that
carries "% of bound" as one number across families would report 8% for a good polarisation
converter and 70% for a good absorber and mean nothing by either.

### 7.3 Backscatter reduction — depends on the mechanism, and this is the interesting case

**By absorption:** it *is* the absorber case. Rozanov binds it.

**By phase cancellation (AMC/PEC or two-AMC checkerboards):** each tile is a reflection-phase
surface, so §7.1 binds the band over which the two tiles keep their required phase difference.
Published practice matches: the traditional PEC–AMC checkerboard achieves roughly 5% RCS
reduction bandwidth precisely because it inherits the AMC's in-phase bandwidth.

**By diffusion / redirection (coding and pixelated metasurfaces):** **no equivalent bound was
found in this search, and there is a physical reason to expect none of the same shape.**
Rozanov's sum rule constrains `|ρ|`, the *specular* reflection coefficient, and it does so
because below the first grating lobe the specular mode is the only channel — so `|ρ| < 1`
necessarily means absorption. A surface with a period large enough to launch propagating
diffracted orders redistributes power into other directions without absorbing it. Monostatic
RCS drops; nothing is dissipated; no absorption budget is spent. Such a surface can achieve
arbitrarily large monostatic reduction at arbitrarily small thickness, limited by fabrication
and by scan/angle stability rather than by a causality sum rule. The conserved quantity that
*does* bind it is total scattering, not backscatter — the nearest formal statement retrieved is
Gustafsson, Vakili, Bayer Keskin, Sjöberg & Larsson, *"Optical theorem and forward scattering
sum rule for periodic structures,"* IEEE Trans. Antennas Propag. 60(8), 3818–3826, 2012, whose
sum rule "relates the total cross section to the static polarizability per unit cell" — a bound
on *total* interaction, which a diffusive surface satisfies while still redirecting freely.
**`INFERRED` from the structure of the sum rule plus the grating-lobe restriction, not stated
as such by any retrieved source. Flagged as needing confirmation before anything depends on
it.**

### 7.4 Verdict for the registry (#109)

**Per-family, and with three distinct shapes — not one common field.**

| Family | Bound exists? | Shape | Form |
|---|---|---|---|
| Absorber | **Yes** | thickness ↔ bandwidth (sum rule) | `\|ln ρ₀\| Δλ ≤ 2π² μ_s d` |
| Beam steering by reflection phase | **Yes** (element level) | thickness ↔ bandwidth (sum rule) | `B λ₀/d ≤ 2π tan(Φ/4)` |
| Backscatter reduction, AMC phase-cancellation | **Yes** (inherited) | thickness ↔ bandwidth (sum rule) | as above, per tile |
| Backscatter reduction, absorptive | **Yes** (inherited) | thickness ↔ bandwidth (sum rule) | as absorber |
| Backscatter reduction, diffusive | **None found** | — | see §7.3 caveat |
| Polarisation conversion | **No bandwidth bound** | thickness ↔ efficiency, single frequency | Abdelrahman & Monticone Eq. (11); 1/4 thin-layer limit |

The registry field cannot be "the Rozanov limit." It has to be something like *"a feasibility
predicate this family supports, if any, together with which quantities it relates"* — because
the answer is a bandwidth ceiling for two families, an efficiency ceiling for another, and
absent for a fourth.

---

## 8. Two traps that would corrupt an implementation

### 8.1 The factor-of-two: voltage versus power reflection coefficient

Rozanov's integral is over `ln|ρ|` where **ρ is the voltage (field) reflection coefficient**.
Taking the log of the *power* reflectance `|ρ|²` instead doubles every answer.

This is verified two ways: (a) Firestein et al.'s Eq. (1) writes both forms explicitly and
carries the compensating factor of ½ on the power form —
`|½∫ln[1−Ã(λ)]dλ| = |∫ln|ρ(λ)|dλ|`; (b) the 1/17 check in §1.4, which only reproduces
Rozanov's own headline under the voltage convention (the power convention would give 1/8.6).

**And the published literature does not always get this right.** Kim et al. (Sci. Rep. 9,
16359) report a −10 dB absorber over 4.7–56.4 GHz at 7.0 mm and quote a "theoretical limit
(6.7 mm)". `CALCULATED` from the voltage-convention bound: `1.151293 × (63.7856 − 5.3155) /
19.739209` = **3.4103 mm**. Doubling it gives **6.8206 mm**, which matches their 6.7 mm within
rounding. Their design is therefore at **2.05×** the voltage-convention bound, not 1.04×.
**`INFERRED` — I could not read their derivation, only their stated numbers, so this is a
reasoned reconstruction, not a proven error on their part.** Either way the moral holds: when
comparing against published "% of Rozanov" figures, **check which convention was used before
believing the number.**

### 8.2 The rectangular out-of-band model is the loosest possible reading

Covered in §6.3. `|ρ| = 1` outside the design band is a fiction; it makes the bound maximally
permissive. If the loop reports "% of the theoretical maximum," it should say which of the two
it computed — the rectangular ceiling, or the integral of the candidate's own curve. They are
not the same number and the difference is not small.

---

## 9. The arithmetic, reproducible

Every `CALCULATED` figure above comes from this script. It is deterministic, it depends on
nothing but `math`, and its final block re-derives four independently published statements as
regression checks.

```python
import math

C = 299.792458  # mm*GHz
TWO_PI2 = 2 * math.pi**2


def abs_ln_rho(db):  # |ln rho_0| from a reflectivity target in dB
    return abs(db) * math.log(10.0) / 20.0


def d_min(db, f_lo, f_hi, mu_s=1.0):
    """Least thickness (mm) the bound allows for this band and level."""
    return abs_ln_rho(db) * (C / f_lo - C / f_hi) / (TWO_PI2 * mu_s)


def max_fbw(db, d_mm, f_c, mu_s=1.0):
    """Largest fractional bandwidth, band symmetric in frequency about f_c.
    Delta-lambda = lambda_c * B/(1 - B^2/4), so with
    K = 2 pi^2 mu_s d / (|ln rho_0| lambda_c), B/(1-B^2/4) <= K solves to
    B = 2 (sqrt(1+K^2) - 1) / K."""
    K = TWO_PI2 * mu_s * d_mm / (abs_ln_rho(db) * (C / f_c))
    return K, 2 * (math.sqrt(1 + K * K) - 1) / K
```

**Verified output.** The script's own section labels say *"Example 3's band"*; they are the
script's literal output and are left verbatim as the record of what it printed. Read them as
*"an 8.5–10.5 GHz span"* — the bound does not govern the unbacked anchor, and that span is a
plot axis (see the note in the bottom line).

```
== constants ==
c                 = 299.792458 mm.GHz
2*pi^2            = 19.739209
|ln rho0| @ -10dB = 1.151293
|ln rho0| @ -20dB = 2.302585
lambda_c @ 9.5GHz = 31.5571 mm

== Q1: max fractional bandwidth at 9.5 GHz centre, mu_s = 1 ==
d=0.87 mm  -10 dB : K=0.472679  B= 44.89%  (7.37-11.63 GHz)
d=0.87 mm  -20 dB : K=0.236339  B= 23.31%  (8.39-10.61 GHz)
d=2.00 mm  -10 dB : K=1.086618  B= 87.75%  (5.33-13.67 GHz)
d=2.00 mm  -20 dB : K=0.543309  B= 50.82%  (7.09-11.91 GHz)

== Q2: least thickness the bound demands for Example 3's band ==
8.5-10.5 GHz  -10 dB : d_min = 0.3918 mm   -> at 0.87 mm that is 45.0% of the skin; at 2.00 mm, 19.6%
8.5-10.5 GHz  -20 dB : d_min = 0.7837 mm   -> at 0.87 mm that is 90.1% of the skin; at 2.00 mm, 39.2%

== Q3: worked check of Example 3's band geometry ==
lambda_max = c/8.5  = 35.2697 mm
lambda_min = c/10.5 = 28.5517 mm
Delta-lambda        = 6.7180 mm
fractional BW       = (10.5-8.5)/9.5 = 21.05%

== Q4: the magnetic term.  Same band, same level, mu_s > 1 ==
mu_s=  1 : d_min(8.5-10.5,-10dB) = 0.3918 mm ; max B at d=2.0 mm =  87.75%
mu_s=  2 : d_min(8.5-10.5,-10dB) = 0.1959 mm ; max B at d=2.0 mm = 128.13%
mu_s=  5 : d_min(8.5-10.5,-10dB) = 0.0784 mm ; max B at d=2.0 mm = 166.55%
mu_s= 10 : d_min(8.5-10.5,-10dB) = 0.0392 mm ; max B at d=2.0 mm = 182.44%
mu_s= 20 : d_min(8.5-10.5,-10dB) = 0.0196 mm ; max B at d=2.0 mm = 191.01%

== Q5: the issue's 'impossible requirement' example ==
60% BW at 9.5 GHz (6.65-12.35 GHz) -10 dB : d_min = 1.2136 mm  -> 1.0 mm skin is IMPOSSIBLE
60% BW at 9.5 GHz (6.65-12.35 GHz) -20 dB : d_min = 2.4271 mm  -> 1.0 mm skin is IMPOSSIBLE

== Q4b: Snoek's law - how much mu_s is actually available at X-band ==
typical soft ferrite   4piMs=  5.0 kOe -> Snoek const  10.0 GHz ; at f_res= 9.5 GHz, mu_s <=  2.05
typical soft ferrite   4piMs=  5.0 kOe -> Snoek const  10.0 GHz ; at f_res=12.0 GHz, mu_s <=  1.83
iron                   4piMs= 21.5 kOe -> Snoek const  43.0 GHz ; at f_res= 9.5 GHz, mu_s <=  5.53
iron                   4piMs= 21.5 kOe -> Snoek const  43.0 GHz ; at f_res=12.0 GHz, mu_s <=  4.58

== Q4c: oblique incidence.  RHS scales by cos(theta) for TE ==
theta= 0 deg : TE factor cos = 1.0000 -> max B at d=2.0 mm, -10 dB =  87.75%   (TM factor 1/cos = 1.0000)
theta=30 deg : TE factor cos = 0.8660 -> max B at d=2.0 mm, -10 dB =  79.31%   (TM factor 1/cos = 1.1547)
theta=45 deg : TE factor cos = 0.7071 -> max B at d=2.0 mm, -10 dB =  67.96%   (TM factor 1/cos = 1.4142)
theta=60 deg : TE factor cos = 0.5000 -> max B at d=2.0 mm, -10 dB =  50.82%   (TM factor 1/cos = 2.0000)

== Q6: cross-checks against published statements ==
broadband (lambda_min->0), -10 dB, mu_s=1: d/lambda_max >= 0.058325 = 1/17.15   [Rozanov: 'least thickness ... is 1/17 of the largest operating wavelength']
same rearranged with Gamma0 in dB: f_L = c*|Gamma0|/(171.45 d)   [Sci Rep 9:16359 writes 172]
IJMWT flexible MSA 10.2-11.4 GHz at  -5 dB : d_min = 0.0902 mm  (paper quotes 0.19 mm)
IJMWT flexible MSA 10.2-11.4 GHz at -10 dB : d_min = 0.1804 mm  (paper quotes 0.19 mm)
SciRep folded-spiral 4.7-56.4 GHz -10 dB : voltage-convention d_min = 3.4103 mm ; power convention (2x) = 6.8206 mm (paper quotes 6.7 mm)
  -> 7.0 mm as a multiple of the voltage-convention bound: 2.05x
```

Two of the Q6 lines are the real regression tests: the **1/17.15** and the **171.45** both
reproduce independently published constants from the same three-line inequality, which is what
lets this document claim the bound is verified rather than recalled.

---

## 10. What this means for the decisions #129 asks

Findings only — #129 is a decision ticket and the decisions are its own to make.

**"Is the bound worth encoding at all?"** As a **feasibility predicate**, unambiguously yes:
§5.6 shows it turns an unsatisfiable requirement into a specific counter-offer before any
search runs, and the arithmetic is three lines. As a **stopping condition**, yes but only in
the curve-integral form of §6.3 — the rectangular form is too loose to stop on, and this is
exactly the weakness #129 anticipated.

**"Where does it live?"** The evidence supports #129's own instinct. The feasibility check is a
pure function of `(band, reflectivity target, thickness, μ_s, worst incidence angle)` — all
requirement-side quantities, no candidate needed. It belongs at `REQUIREMENTS`. The
percentage-of-limit metric needs a simulated `|ρ(λ)|` curve, so it necessarily lives after
`SIMULATION`. **These are two different artefacts that happen to share an equation**, and
conflating them would put a curve-dependent number where no curve exists yet.

**"Does it gate, or advise?"** Two facts bear on it. Against: three of the seven assumptions
(§2) are escapable in this design space — oblique incidence changes the number by up to 43%,
a penetrable backing voids the bound outright (§2.2), and effective μ_s for a metamaterial is a
retrieval, not a constant. For: the failure mode of *advising* when the bound is right is one
wasted overnight run, and the failure mode of *gating* when the bound is wrong is silently
refusing a feasible design. Given the map's standing preference that unattended decisions be
"reversible and recorded," **advising with the counter-offer attached** costs one run and loses
nothing permanently; gating does not have that property.

**"Which form, and verified how?"** §1.4's engineering form, `|ln ρ₀| Δλ ≤ 2π² μ_s d`, with the
§2.1 `cos θ` factor applied at the worst TE angle in the requirement. Verified by reproducing
Rozanov's own 1/17 and Sci. Rep.'s 172 from it. Implementation must respect §8.1 (voltage, not
power) and label §8.2 (which out-of-band model).

**"Does an equivalent bound exist for the other examples?"** §7. Yes for reflection-phase
surfaces, with a form five times harsher at the same thickness; no bandwidth bound for
polarisation conversion; none found for diffusive backscatter reduction. **Per-family, three
shapes.**

---

## 11. What is stranded, and what is still unknown

**Stranded behind paywalls (403 to automated fetch from this environment):**

- **Rozanov (2000) itself**, IEEE Xplore. Everything here is restated from citing sources and
  cross-checked arithmetically against his abstract's own 1/17 figure. **No claim in this
  document quotes Rozanov's paper directly.**
- Brewitt-Taylor (2007), IET — the earlier AMC bound. Restated by Gustafsson & Sjöberg.
- Doane, Sertel & Volakis (2013), IEEE — the oblique-incidence extension. Restated verbatim by
  Firestein et al. (arXiv:2305.13295).
- Rozanov & Starostenko (2003), J. Communic. Technol. Electronics — permeability dispersion and
  magnetic absorber bandwidth. Known only through the URSI paper's citation of it.
- Gustafsson & Sjöberg's IEEE version; the 2010 Lund technical report used instead is the
  accepted author manuscript and is open access.

**Retrieved and used as primary or near-primary:**

- Firestein, Shlivinski & Hadad, Phys. Rev. B 108, 014308 (2023) / [arXiv:2210.06949](https://arxiv.org/abs/2210.06949)
- Firestein, Shlivinski & Hadad, [arXiv:2305.13295](https://arxiv.org/abs/2305.13295) (oblique/multi-angle)
- Padilla, Deng, Khatib & Tarokh, Nanophotonics (2023) / [arXiv:2308.14839](https://arxiv.org/abs/2308.14839)
- Abdelrahman & Monticone, [arXiv:2208.05533](https://arxiv.org/abs/2208.05533)
- Gustafsson & Sjöberg, [TEAT-7198 (2010), open access](https://lup.lub.lu.se/search/files/6059224/1698605.pdf)
- Rozanov, [URSI GASS 2011, B06-7](https://www.ursi.org/proceedings/procGA11/ursi/B06-7.pdf) (Rozanov-authored, open)
- Ikonen, Rozanov, Osipov & Tretyakov, [arXiv:physics/0603116](https://arxiv.org/abs/physics/0603116)
- Kim et al., Sci. Rep. 9, 16359 (2019), [PMC6848185](https://pmc.ncbi.nlm.nih.gov/articles/PMC6848185/)
- Costa & Monorchio et al., IJMWT, [Cambridge Core](https://www.cambridge.org/core/journals/international-journal-of-microwave-and-wireless-technologies/article/ultrathin-and-flexible-microwave-metasurface-absorbers-based-on-resistive-patches/48D423A3150F85A87A886FC82E23C627)

**Still unknown, and each would change a number above:**

1. **Example 3's own thickness.** 0.87–2.0 mm is the range across all seven examples. The
   answer to "45% or 90% of the limit" depends on it, and it should be readable from the
   drawings (`research/seven-example-unknowns`).
2. **Example 3's reflectivity target.** Whether the patent claims −10 dB or −20 dB across
   8.5–10.5 GHz is the difference between comfortable headroom and being at the wall.
3. **Whether the skin's ground plane is opaque.** Decides whether §2.2's escape is live.
4. **Effective static μ_s of the printed pattern**, by S-parameter retrieval at low frequency.
   Assumed 1; not measured. Cheap to check once a Floquet solve exists.
5. **The diffusive-backscatter claim in §7.3** is `INFERRED` from the grating-lobe restriction,
   not sourced. Confirm before the registry depends on it.
6. **Whether the loop should use the rectangular or curve-integral form** — technical work, but
   it decides whether "% of limit" is diagnostic or decorative.
