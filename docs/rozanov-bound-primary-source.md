# The Rozanov bound, read from the original at last

**Date:** 2026-09-05
**Ticket:** [#129](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/129) — bears on [#116](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/116), [#133](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/133); part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104).
**Question:** What does Rozanov's thickness-versus-bandwidth bound actually say, and under exactly which conditions does it hold?

`RUNNING-LISTS.md` §1 has carried this entry since the register was created:

> **Rozanov (2000)**, "Ultimate thickness to bandwidth ratio of radar absorbers" — Behind IEEE. Its result is verified through two independent open-access restatements that agree with each other, but **the original was never read**.

**It has now been read.** This document records what it says, in its own words.

---

## Bottom line up front

**The bound is real, it is stronger than the restatements conveyed, and it does
not apply to this programme's reproduction anchor.**

The third of those is the finding that matters. Rozanov's derivation opens by
fixing the geometry it is about, and the wording is not incidental:

> "We consider a slab of thickness d, permittivity ε = ε′ − iε″, and
> permeability μ = μ′ − iμ″, **overlying a perfectly reflecting plane** and
> illuminated at **normal incidence** by a monochromatic plane wave."
> — Rozanov (2000), §II first paragraph, p. 1230, verbatim

**In plain terms.** The whole result is about an absorber with solid metal
behind it. The metal is what makes the maths work: with nothing getting
through, all the energy that fails to bounce back must have been turned into
heat, and the reflection alone tells the whole story. Take the metal away and
energy has a third place to go — straight through — and the derivation's
central bookkeeping no longer closes.

Per [`seven-example-design-unknowns.md`](./seven-example-design-unknowns.md)
lines 184–186 and 345, **Example 3 has no ground plane** — it is two-port and
transmissive, and the evidence is the patent's own drawing: FIG. 7G plots a
non-zero Transmission trace. So the bound's assumption (b) fails for the one
design this programme has committed to reproducing. See §4.

---

## 1. What the paper actually states

All equation numbers are Rozanov's own.

**The single-layer dispersion relation, Eq. (6):**

```
    | ∫₀^∞ ln|ρ(λ)| dλ |  ≤  2π² μ_s d
```

> "which is held for the reflection coefficient of any metal-backed
> magnetodielectric layer" — verbatim

**The multilayer generalisation, Eq. (7):**

```
    | ∫₀^∞ ln|ρ(λ)| dλ |  ≤  2π² Σᵢ μ_{s,i} dᵢ
```

**The working form, Eq. (9)** — what a design actually gets measured against:

```
    |ln ρ₀| · (λ_max − λ_min)  <  2π² Σᵢ μ_{s,i} dᵢ
```

**The broad-band reduction, Eq. (10)**, where `Γ₀ = 20 log ρ₀` is reflectance
in decibels and `λ_max ≫ λ_min`:

```
    λ_max · Γ₀  ≤  40π² Σᵢ μ_{s,i} dᵢ / ln 10  ≈  172 Σᵢ μ_{s,i} dᵢ
```

**The narrow-band refinement, Eq. (14)** — for a quarter-wave / first-
interference-minimum absorber with negligible permeability dispersion:

```
    Δλ / d  <  16 μ_s / |ln ρ₀|
```

**In plain terms.** Every one of these says the same thing in a different
dress: *a thin absorber cannot also be a broadband one.* Thickness buys
bandwidth, and the exchange rate is fixed by physics, not by cleverness. If a
requirement asks for both beyond what the inequality allows, no amount of
design effort will produce it — the answer is "make it thicker, or accept a
narrower band."

**The broad-band headline, and what everyone is actually quoting.** Eq. (10)
continues, verbatim:

> "For nonmagnetic broad-band absorbers (μs,i ≡ 1), it follows from (10) that
> the application of any multilayer slab made of dielectrics with any
> physically realizable frequency dependence of the permittivity cannot
> provide 10-dB reflectance level, if the thickness of the absorber is less
> than **λmax/17.2**."

**The abstract rounds this to 1/17; the derivation gives 1/17.2.** Anyone
quoting "1/17" is quoting the abstract rather than Eq. (10) — worth knowing,
because that is the route by which the figure reaches most secondary sources.

*Plainly: an ordinary non-magnetic coating that must cut reflected radar power
to about a tenth across a wide band can never be thinner than about a
seventeenth of the longest wavelength it has to absorb — roughly 6% of that
wavelength, as an absolute floor.*

---

## 2. The number the restatements did not carry

Rozanov's §IV comparison is worth quoting because it is the practical payload:

> "For the 10-dB reflectance level, the ultimate d/Δλ value of a nonmagnetic
> Dallenbach screen is 1/3.2 as it can be seen from (2). Inequality (14)
> produces 1/13.9 for this value, and the largest possible bandwidth of a
> narrow-band dielectric absorber…" — verbatim

| Absorber | Ultimate `d/Δλ` at −10 dB |
|---|---|
| Plain Dallenbach screen | 1 / 3.2 |
| **Best possible narrow-band non-magnetic dielectric** | **1 / 13.9** |
| Best possible **broad-band** non-magnetic multilayer, Eq. (10) | **1 / 17.2** |

**In plain terms.** A plain single-layer absorber has to be about a third of
the bandwidth's worth of wavelength thick. A perfectly optimised one can be
about four times thinner than that — but no thinner, ever. That factor of
~4.3 is the entire headroom that clever design buys you, and it is a ceiling,
not a target.

And the headline for the non-magnetic case, from the text around Eq. (10):
no multilayer slab made of dielectrics with any physically realisable
permittivity beats the `≈ 172 Σ dᵢ` limit — **magnetic materials are the only
way to move it**, because `μ_s` is the only term on the right-hand side that
a non-magnetic design cannot raise above 1.

---

## 3. Stated assumptions — the part that decides applicability

Read directly from §II and §III, not inferred:

| # | Assumption | Rozanov's own words / location | Escapable? |
|---|---|---|---|
| a | **Normal incidence** | "illuminated at normal incidence by a monochromatic plane wave" (§II ¶1) | No, as stated |
| b | **Backed by a perfectly reflecting plane** | "overlying a perfectly reflecting plane" (§II ¶1); Eq. (6) "any **metal-backed** magnetodielectric layer" | **This is the one that fails for Example 3** |
| c | **Linear and causal medium** | Kramers–Kronig / minimum-phase analyticity used to extend ρ(ω) into the complex plane (§III), cited to Nussenzveig ref. [8] | No — it is what makes the integral finite |
| d | Passive, no gain | implicit in the analyticity argument | No |

**An honesty note on (c) and (d).** The paper does *not* restate "linear,
time-invariant, passive" as a labelled assumption list. They are implicit in
its invocation of Kramers–Kronig causality and the analyticity of ρ(ω).
Standard in this literature, but this is inferred-from-method rather than
quoted, and is flagged as such rather than dressed up as a citation.

**And the bound is not a non-magnetic result.** μ appears throughout the
derivation; the widely-quoted 1/17.2 is the **special case μ_s,i ≡ 1**. The
paper also gives two sharper, narrower corollaries the restatements omit:
Eqs. (12)/(13) for absorbers with strong magnetic dispersion — *"valid only if
the imaginary part of the permeability is negligibly small at λmax"* — and
Eq. (14) for the narrow-band quarter-wave case assumed thin (|ε| ≫ |μ|).

**Assumption (b) is not a technicality.** `docs/absorber-thickness-bandwidth-bound.md:182`
already flagged it as *"the one genuinely escapable assumption"* and §2.2 of
that document explores replacing the PEC ground with a partially transparent
sheet. That exploration is now the load-bearing branch rather than an aside.

---

## 4. What this means for the anchor, and for #129

**The programme's own skins are fine.** ADR-0017 decided the base printed
layer always supplies its own conductive reflector by default, so anything
this project *builds* is metal-backed and the bound applies to it directly.

**The reproduction anchor is not.** Patent Example 3 / Landy et al. 2008 is
somebody else's device, and it is unbacked — it suppresses transmission with a
cut wire rather than a ground plane, which is why FIG. 7G has a non-zero
transmission trace at all.

So the two are different cases and the repo currently conflates them.
`docs/absorber-scoring-conventions.md` lines 14, 48, 62 and 349 assert Example 3
is ground-backed and collapse absorptivity to `A = 1 − |S₁₁|²` on that basis,
calling it *"the single most useful simplification in this document."*
`docs/seven-example-design-unknowns.md` says the opposite, from the drawing.
**The drawing reading should win** — it is evidence, and this repo's standing
rule is that the drawings have twice beaten the prose already.

**Consequences to work through on #129:**

1. Every headroom figure in `docs/absorber-thickness-bandwidth-bound.md`
   computed *for Example 3* (lines 39, 301, 304, 426, 774–775) assumes a
   backing that example does not have.
2. `A = 1 − |S₁₁|² − |S₂₁|²` is the form the anchor needs — **two ports**,
   which lands squarely on #133's fixture, cost and Touchstone-format
   conclusions.
3. The bound is still worth having for the programme's own designs. The
   question "should the loop know the bound" survives; the question "is the
   anchor near the limit" does not, as posed.

---

## 5. A second, independent problem with the same numbers

Every Example 3 headroom figure also uses **8.5–10.5 GHz (21.05% fractional)**
as the design's *band*. The bound is **linear in Δλ**, so this input scales
every result one-for-one.

The patent's own prose, now retrieved verbatim, says:

> "The plot of FIG. 7G shows simulated scattering performance of the EM skin
> 700 over **select frequencies ranging from 8.5-10.5×10⁹ Hz (a sub-band of
> the X-band)**. The simulated data assumed a 0.87 mm-thick absorber
> metamaterial layer using FR4 dielectric layer of permittivity of 4.8 and
> loss tangent of 0.017." — US12089385B2, Example 3 description

That is **a description of what was plotted**, not a statement that the device
is required to absorb across it. Yet `docs/absorber-scoring-conventions.md:374`
now reads *"The requirement is '≥90% absorption across 8.5–10.5 GHz'"*, and
`docs/HANDOFF-metamaterial-printing-grill.md:73` files it in a band column.

**This is the same failure mode #130 already documented once**, where a
±22.5° phase budget borrowed from beam-forming silently encoded a 14.2 dB
requirement nobody had stated. The rule that came out of it applies verbatim
here: *a number read off a plot is not a requirement.*

---

## 6. Register updates this closes and opens

**Closes:** `RUNNING-LISTS.md` §1's Rozanov entry. The original was retrieved
outside IEEE Xplore and read directly; equations, constants and assumptions
above are quoted from it rather than from a restatement.

**Opens:** a correction to the environment note in §1 — **`pymupdf` was not
in fact pre-installed** in this session, contrary to what the register says.
It installed cleanly via `pip` with no trouble, so the capability claim holds;
the "already there" claim does not.
