# The charter's opening physics, checked against the AMC/high-impedance-surface primaries

**Date:** 2026-09-13
**Ticket:** [#471](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/471) — bears on [#465](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/465), [#220](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/220), [#346](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/346); part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104).
**Question:** `CLAUDE.md`'s charter opens on a magnetic mirror — a surface that reflects with 0° phase shift instead of 180°, so an antenna can lie flat on it. Does the classical artificial-magnetic-conductor / high-impedance-surface literature actually back that, with citable and ideally *measured* numbers? And is the ±90° in-phase-bandwidth convention the field's own, or a later restatement?

---

## Bottom line up front

**Yes. The charter's physics is correct, the ±90° convention is now read from
the primary text rather than a summary, and the programme has its first
measured in-phase reflection numbers — four of them, from two independent
laboratories.**

Four things this settles, and one it does not:

| | Answer |
|---|---|
| Is ±90° the field's own convention, or a later restatement? | **The field's own, and it is in the founding paper.** Sievenpiper et al. (1999) state it twice on p. 2064 in their own words. §1 |
| Does the classical literature report a *measured* in-phase reflection band? | **Yes.** Sievenpiper's own Fig. 14 is a measured reflection-phase curve; three more measured bands come from a flexible, via-less AMC. §2, §3 |
| Is a printable magnetic mirror reachable on this shop's configuration? | **Yes — vias are not required for the reflection phase.** Sievenpiper says so himself, and a measured via-less flexible AMC exists that keeps its band while bent. §4 |
| Can `REFLECTION_PHASE` be scored today? | **Yes, with one named caveat.** There is now a primary-source definition of the scored quantity, a closed-form predictor, and four measured points to calibrate against. §6, decision 3 |
| Is there an X-band-**centred** measured in-phase number? | **Still no.** The closest measured band starts at 12.0 GHz. §7 |

**The single most useful number this pass produced.** Sievenpiper's own design
equations reduce to a one-line closed form for the ±90° in-phase bandwidth of
a printed high-impedance surface:

```
    Δω / ω₀  =  2π · µ_r · t / λ₀
```

— fractional in-phase bandwidth equals 2π times the substrate thickness
divided by the free-space wavelength (times the relative permeability of the
spacer, which is 1 for every material this shop has). `LITERATURE-SUPPORTED`
(read from primary text, §5).

*In plain terms: how wide a band a flat magnetic mirror works over is set by
one thing — how thick it is compared to the radio wave. Nothing else in the
design changes that ceiling; the pattern on top only decides which frequency
it sits at. At 10 GHz the wave is 30 mm long, so a 1.55 mm board can work over
at most about a third of its centre frequency, and a 0.76 mm board over at
most about a sixth.*

**And four measured surfaces say how much of that ceiling real hardware
reaches: 62–92%.** §6. That is a calibration band the programme did not have
yesterday, and it is exactly what `REFLECTION_PHASE` needed in order to be
able to say whether a candidate's simulated number is plausible.

---

## 1. The ±90° convention, from the primary text

Both quotes are from **Sievenpiper, D., Zhang, L., Broas, R. F. J.,
Alexópolous, N. G. & Yablonovitch, E., "High-Impedance Electromagnetic
Surfaces with a Forbidden Frequency Band," *IEEE Trans. Microwave Theory
Tech.* 47(11), 2059–2074 (1999)**, doi
[10.1109/22.798001](https://doi.org/10.1109/22.798001). Both are on **p. 2064**.
Retrieval route and verification are in §8.

The definition, verbatim:

> "Typical parameters for a two-layer ground plane are 2 nH of inductance,
> and 0.05 pF of capacitance. For these values, the reflection phase is
> plotted in Fig. 8. At very low frequencies, the reflection phase is π, and
> the structure behaves like an ordinary flat metal surface. The reflection
> phase slopes downward, and eventually crosses through zero at the resonance
> frequency. Above the resonance frequency, the phase returns to −π. **The
> phase falls within π/2 and −π/2 when the magnitude of the surface impedance
> exceeds the impedance of free space.** Within this range, image currents are
> in-phase, rather than out-of-phase, and antenna elements may lie directly
> adjacent to the surface without being shorted out."
> — §IV-B "Reflection Phase", p. 2064

and, one column later, the bandwidth is *defined* by that window:

> "The total bandwidth is roughly equal to the characteristic impedance of the
> surface divided by the impedance of free space
>
> `Δω/ω₀ = Z₀/η`   (26)
>
> **This is also the bandwidth over which the reflection coefficient falls
> between +π/2 and −π/2**, and image currents are more in-phase than
> out-of-phase. It represents the maximum usable bandwidth of a flush-mounted
> antenna on a resonant surface of this type."
> — §IV-C "Radiation Bandwidth", p. 2064, immediately after Eq. (26)

*In plain terms: a magnetic mirror is never perfect except at exactly one
frequency. The convention is to count the band where the bounce is closer to
"in step" than to "out of step" — that is, where the returning wave's timing
is shifted by less than a quarter of a cycle either way. Inside that band an
antenna lying flat on the surface is helped rather than shorted out.*

**`LITERATURE-SUPPORTED`, primary text, page-located, and read as a rendered
page image** — the PDF's text layer silently drops every `π/2` (the maths is
in a subset font), which is exactly the failure mode
`docs/costa-thin-spacer-correction.md` §1 documents. Both quotes were read at
420 dpi off the primary PDF, not reconstructed from the text layer.

### The same statement, from the same author, in a second primary document

Sievenpiper's PhD dissertation — **Sievenpiper, D. F., *High-Impedance
Electromagnetic Surfaces*, Ph.D. dissertation, Dept. of Electrical
Engineering, UCLA, 1999**, 162 pages — states it a third time and ties it
explicitly to the design equations, verbatim from §10.1, thesis p. 134:

> "ω₀ is the frequency where the reflection phase is zero, and where the
> surface behaves as a magnetic conductor. This is also the frequency where an
> antenna will perform best on such a ground plane. The bandwidth in Equation
> 10.1.8 corresponds roughly to the width of the surface wave band gap, or
> equally well, **the frequency range over which the reflection phase falls
> between +π/2 and -π/2.** The bandwidth of the actual antenna might be
> smaller, depending on the geometry of the antenna, and the size and shape of
> the ground plane."

### What this changes in this repo, and one caveat that must travel with it

`docs/example1-2-scoring-recipe.md` §2 currently records the ±90° default as
*"`LITERATURE-SUPPORTED`, cited via consistent secondary summary — neither
primary paper's full text was independently fetched in this pass"*, and its §4
flags it as *"secondary-source-level … worth a primary-text check before this
becomes a hardcoded default anywhere in code."* **That check is now done for
Sievenpiper 1999, and it passes.** (That document is not edited here — #471's
scope is the evidence, not the recipe.)

**The caveat, which is Sievenpiper's own and is easy to lose:** the ±90° band
is a property of *the surface*, and the last sentence quoted above says the
antenna's usable band **may be narrower**. ±90° is the right default for
scoring a magnetic mirror as a surface. It is **not** a promise about a
finished antenna, and a requirement written about an antenna's bandwidth must
not be scored against it without saying so. This is the same trap
`docs/requirement-derived-thresholds.md` exists to prevent: a convention
imported as a gate rather than a default.

### Yang & Rahmat-Samii 2003 — confirmed unreachable, and no longer load-bearing

**Yang, F. & Rahmat-Samii, Y., "Reflection Phase Characterizations of the EBG
Ground Plane for Low Profile Wire Antenna Applications," *IEEE Trans. Antennas
Propag.* 51(10), 2691–2703 (2003)**, doi
[10.1109/TAP.2003.817559](https://doi.org/10.1109/TAP.2003.817559).

**No free copy exists.** This is a positive result from two independent
open-access indexes, not a fetch failure — the same standard
`docs/costa-thin-spacer-correction.md` §5 applied to Tretyakov & Simovski:

- Unpaywall: `is_oa: false`, `oa_status: "closed"`, `has_repository_copy: false`, `oa_locations: []`
- OpenAlex: `is_oa: false`, `oa_status: "closed"`, `any_repository_has_fulltext: false`, one location (the DOI itself, not OA)

Routes tried and failed are in §8. **It no longer matters for the convention**,
because the convention traces to Sievenpiper 1999 and is now read there. What
is still stranded behind it is Yang & Rahmat-Samii's own, narrower question —
how much of the ±90° surface band a real low-profile *dipole* actually keeps —
which is the quantitative version of Sievenpiper's caveat above. That is a
real gap, but it is a gap in antenna-level scoring, not in surface-level
scoring, and this programme scores surfaces.

---

## 2. A measured in-phase reflection band, from 1999

Sievenpiper 1999 **Fig. 14, "Measured reflection phase of a two-layer
high-impedance surface"** is a measured curve — not a simulation. The method,
verbatim from p. 2067:

> "The reflection phase of the high-impedance surface can be measured using
> two microwave horn antennas, as shown in Fig. 13. The measurement is done in
> an anechoic chamber lined with microwave absorbing foam. … A reference
> measurement is taken of a surface with known reflection properties, such as
> a flat sheet of metal, and all subsequent measurements are divided by this
> reference. A factor of [π] is added to the phase data to account for the
> reference scan of the metal sheet, which is known to have a reflection phase
> of [π]."

**The sample**, verbatim from p. 2067 (§VI-A, the same surface Fig. 14
measures):

> "The structure consisted of a triangular array of hexagonal patches as shown
> in Fig. 1, with a period of 2.54 mm and a gap between the patches of 0.15
> mm. The thickness of the board was 1.55 mm, and the dielectric constant was
> 2.2."

**The result**, in the paper's own words (p. 2067):

> "Within the region between [+π/2] and [−π/2], indicated on the graph by
> arrows, plane waves are reflected in-phase, rather than out-of-phase. This
> range also corresponds to the measured surface-wave bandgap, indicated on
> the graph by a shaded region"

and the bandgap is stated numerically on the same page: *"A surface-wave
bandgap is measured between the TM band edge at 11 GHz and the TE band edge at
17 GHz."*

### The numbers, two independent readings

| Reading | +90° edge | 0° crossing | −90° edge | Width | Fractional |
|---|---|---|---|---|---|
| The paper's own prose (band-gap proxy) | ≈11 GHz | — | ≈17 GHz | 6 GHz | ≈42.9% |
| Pixel digitisation of Fig. 14 (this pass) | 12.0 GHz | 14.75 GHz | 18.4–18.7 GHz | ≈6.5 GHz | **≈44.1%** |

The digitisation traced the plotted curve at 600 dpi against the figure's own
axis frame (0 and 30 GHz at the left/right borders, π and −π at the top/bottom
borders), after deleting long horizontal runs so the dotted ±π/2 grid-lines
could not be mistaken for the trace. The two readings agree to about one
percentage point, and the paper says "approximately" about its own
correspondence, so the disagreement is inside the source's own stated
tolerance.

**Provenance.** The *underlying data* is `MEASURED`. The *numbers in the second
row* are `INFERRED` — read off a drawing, per this repo's standing treatment of
digitised figures (`docs/costa-thin-spacer-correction.md` §6). Cite them as
"≈44%, digitised", never as a measured figure quoted by the authors. The first
row is `LITERATURE-SUPPORTED` but is a band-gap number standing in for a
phase-band number, on the authors' own statement that the two coincide.

*In plain terms: in 1999 somebody put a patterned circuit board in an anechoic
chamber, bounced radio waves off it, compared the timing against a plain metal
plate, and found the bounce was in step rather than inverted from about 12 GHz
to about 18.5 GHz. That is the effect the charter opens by describing, measured
on real hardware.*

---

## 3. Three more measured bands — and they are flexible and via-less

**de Cos, M. E., Álvarez, Y., Hadarig, R. & Las-Heras, F., "Flexible Uniplanar
Artificial Magnetic Conductor," *Progress In Electromagnetics Research* **106**,
349–362 (2010)** — open access, retrieved in full and read first-hand.

The paper states the convention independently, which is a third primary-ish
corroboration of §1, verbatim from p. 349:

> "it is considered [1–3] that AMCs behave as PMCs over a certain frequency
> band, the so called bandwidth of AMC performance or AMC operation bandwidth,
> which is generally defined in the range from +90° to −90°, since in this
> range, the phase values would not cause destructive interference between
> direct and reflected waves."

**The structure**, verbatim: *"the novel AMC design with neither via holes nor
multilayer substrates"*, on *"RO3003 of Rogers, which is bendable"*, εr = 3.0,
loss tangent 0.0013, thickness h = 0.762 mm (30 mil), metallisation 18 µm, unit
cell 11.52 mm × 1.05 scale factor, 12 × 12 cells. Measured in an anechoic
chamber against a flat metal reference, flat and bent.

**The measured results**, verbatim:

> "the manufactured flat prototype … has the resonance at 6.23 GHz which means
> a 3.3% deviation with respect to the simulation (6.03 GHz)"

> "The frequency bandwidth of AMC performance for the flat prototype is 392
> MHz (6.29%) in good agreement with simulated value (7.84%) … whereas for the
> creeping bent prototype the bandwidth of AMC performance is 387 MHz (6.19%)
> and for the smooth bent AMC is 416 MHz (6.63%), even slightly greater than
> that of the flat prototype."

> "there is no frequency shift for the manufactured creeping bent prototype
> with respect to the flat prototype resonance, whereas the smooth bent
> prototype has its resonance at 6.27 GHz, which means just a 0.6% deviation"

A fourth measured point, for the same unit cell on a **rigid** substrate
(Arlon 25N, εr = 3.28, same 0.762 mm thickness), is quoted in the same paper
from the authors' own earlier work: *"the resonance frequency is 5.89 GHz and
the frequency bandwidth of AMC performance is approximately 433 MHz (7.3%)."*

`MEASURED` throughout, quoted verbatim from a first-hand read of the primary.

*In plain terms: a magnetic mirror printed on one flexible sheet, with no
drilled holes and no stacked layers, was measured flat and then bent two
different ways. Bending it moved the working frequency by less than one
percent and changed the width of the working band by less than half a
percentage point. That is the single most relevant experiment in this
document for a programme whose whole product conforms to a curved surface.*

---

## 4. Is a printable magnetic mirror reachable here? The vias are not required

This is #471's question 4, and the answer is in Sievenpiper's own dissertation,
in the introduction to Chapter 8 ("Alternative Structures", thesis p. 88),
verbatim:

> "The simplest alternative is a thin sheet of metal islands, without the
> ground plane or the conducting vias. Such a structure will not support
> surface waves over a certain frequency range, but it is a poor reflector.
> **If a ground plane is added, the structure is completely reflective, and it
> has the favorable reflection phase properties of the high-impedance surface,
> but it permits the propagation of surface waves.** It is only when both the
> ground plane and the vias are included that the two important properties of
> the high-impedance surface are obtained: (a) in-phase, 100% reflection, and
> (b) suppression of surface current propagation"

He makes the same split in the journal paper (p. 2063), verbatim:

> "Recent work involving grounded frequency selective surfaces has also been
> shown to mimic a magnetic conductor [37]. However, these structures do not
> possess a complete surface-wave bandgap, since they lack the vertical
> conducting vias, which interact with the vertical electric field of TM
> surface waves."

and thesis §8.2, "Addition of a Ground Plane", computes the reflection phase of
exactly the via-less structure — a capacitive sheet over a ground plane — by
transmission matrix, and finds it *"crosses through zero at some resonance
frequency"* with the same `ω₀ = 1/√(LC)` (thesis Eq. 8.2.8).

**So the two properties of a Sievenpiper mushroom separate cleanly:**

| Property | Needs a patterned top layer | Needs a ground plane | Needs vias |
|---|---|---|---|
| 0° reflection phase (the magnetic mirror) | yes | **yes** | **no** |
| Surface-wave band gap | yes | yes | **yes** |

*In plain terms: the drilled-through metal posts in the classic "mushroom"
design are there to stop radio waves crawling sideways along the surface. They
are not what makes the bounce come back in step. Drop the posts and you still
have a magnetic mirror — you just also have waves skittering across it, which
matters for an antenna's pattern and its coupling to neighbours, and does not
matter for the reflection phase itself.*

### What that means for this shop, concretely

- **A printable magnetic mirror needs two conductor layers and no vias**: a
  patterned patch array on top, a plain sheet underneath, dielectric between.
  Per **ADR-0017** the base printed layer already supplies its own reflector by
  default, and `docs/voltera-multilayer-capability.md` records that the
  registration problem "largely evaporates" when the bottom layer is
  unpatterned — which is precisely this stack.
- **The feature floor is inside the published range, at its loose end.**
  Sievenpiper's own thesis §10.1 (p. 130), verbatim: *"Using standard printed
  circuit fabrication techniques, the minimum gap width between adjacent metal
  regions is around 100 to 200 microns."* This repo's working floor is 0.2 mm
  (`docs/diw-feature-floor-mechanism.md`, `docs/voltera-multilayer-capability.md`).
  So the programme sits at the coarse end of what conventional AMC design
  assumes, not outside it — but with **zero margin at the bottom of that
  range**, and Sievenpiper's own measured X/Ku sample used a 0.15 mm gap, below
  this shop's floor.
- **The ticket's premise that "every published route needs a ceramic, a via
  array, or a multilayer stack" is false.** de Cos 2010 is one substrate, one
  patterned layer, one ground plane, no vias, bendable, and measured. `MEASURED`.
- **Per ADR-0028 this changes ranking and warnings, never the search.** A
  mushroom-with-vias candidate is still returned; it is returned with a
  fabrication warning that a via-less candidate does not carry.

**Not addressed here, and load-bearing if this becomes a real candidate:**
every measured surface above is *etched copper*. Whether a printed silver or
MXene conductor has enough conductivity and thickness to behave as the "100%
reflective" ground plane the model assumes is a different question, already
owned by `docs/mxene-skin-depth-conductivity-correction.md`. Nothing in this
document supports carrying these numbers onto a printed conductor without that
check. `UNKNOWN`.

---

## 5. The closed form: fractional in-phase bandwidth = 2π t / λ₀

Sievenpiper's thesis §10.1 gives the design equations. Read from a rendered
page image (thesis pp. 129–134), verbatim:

```
    C  =  w (ε₁ + ε₂) / π  ·  cosh⁻¹( a / g )              Equation 10.1.1
    C_sheet  =  C_individual × F        (F = 1 square, √3 triangular, 1/√3 hexagonal)
    L_sheet  =  µ t                                        Equation 10.1.6
    ω₀  =  1 / √(LC)                                       Equation 10.1.7
    Δω / ω₀  =  √(L/C) / √(µ₀/ε₀)                          Equation 10.1.8
```

where `a` is the centre-to-centre lattice spacing, `g` the gap between plates,
`w` the width of the capacitor (for a triangular lattice of hexagons, the
shared hexagon edge), `ε₁`/`ε₂` the permittivities either side of the patch
plane, `t` the substrate thickness, and `µ` the spacer's permeability.

**Substituting Eq. 10.1.6 and 10.1.7 into 10.1.8 collapses it.** With
`√(L/C) = ω₀L` and `η₀ = µ₀c`:

```
    Δω/ω₀  =  ω₀ L / η₀  =  ω₀ µ_r µ₀ t / (µ₀ c)  =  ω₀ t µ_r / c  =  2π µ_r t / λ₀
```

`CALCULATED`. Sievenpiper reaches the same place himself in thesis §5.7 by a
different route, verbatim: *"the bandwidth is related to the ratio of the
actual resonance frequency to this natural frequency"*, `Δω/ω₀ = ω₀/ω_natural`
(Eq. 5.7.1) with `ω_natural = c/(µ_r t)` (Eq. 5.7.2). Two independent
statements in the same document agree, so this is not a transcription artefact.

*In plain terms: how wide a band a flat magnetic mirror works over depends on
one thing only — how thick it is compared with the wavelength. Everything you
draw on the surface decides which frequency it lands on, not how wide the band
is. Making it thinner always costs bandwidth, one-for-one.*

### This independently corroborates the constant in #465's unimplemented bound

ADR-0047 and `docs/example1-2-scoring-recipe.md` §3 carry Gustafsson & Sjöberg's
high-impedance-surface bound as `B·λ₀/d ≤ 2π` for the Φ = π (±90°) window, and
that document's own worked table reads *"0.87 mm | `2π×0.87/31.5571` = 17.4%"*.
Sievenpiper's design equation gives `B = 2π µ_r t/λ₀` — **the same constant,
the same linear dependence on thickness, and the same linear dependence on the
spacer's permeability**, from a completely independent derivation (a lumped LC
half-power argument, not a causality sum rule).

**`INFERRED`, and deliberately not asserted as an identity.** Gustafsson &
Sjöberg's own definition of `B` was not re-read in this pass, and the two could
differ by a wavelength-space-versus-frequency-space convention. What is safe to
say is the useful part: **the constant `2π` in #465's unimplemented bound now
has a second, independent primary source behind it, and the LC model of a
printed high-impedance surface sits at or very near that ceiling rather than
somewhere arbitrary beneath it.** That materially de-risks #465; it does not
implement it.

### There is also a closed-form phase curve, which this repo currently says it lacks

`designs/design_families.py:1355` records, for `REFLECTION_PHASE`:
*"Deliberately nothing to declare, not an omission (#239). What this family
needs is a per-cell reflection PHASE … and no closed form in this repo returns
a phase at all."* That is true of the repo. It is **not** true of the
literature. The same LC model gives the whole curve:

```
    Z_s(ω)  =  jωL / (1 − ω²LC)          ∠Γ(ω)  =  ∠[ (Z_s − η₀) / (Z_s + η₀) ]
```

which reproduces every statement Sievenpiper makes in §1 by construction:
`∠Γ → π` as `ω → 0`; `∠Γ = 0` at `ω₀`; and `|∠Γ| = π/2` exactly where
`|Z_s| = η₀`, which is his sentence *"the phase falls within π/2 and −π/2 when
the magnitude of the surface impedance exceeds the impedance of free space."*
Solving `|Z_s| = η₀` exactly (rather than by his small-term expansion) gives
band edges whose width is `Δω/ω₀ = √(L/C)/η₀` **exactly**, not approximately —
so Eq. (26)'s "roughly" is conservative about its own accuracy. `CALCULATED`.

Whether this belongs in `rf_tools/` as a fast-tier predictor for
`REFLECTION_PHASE` is a decision for #465/#220, not for this ticket. It is
recorded here because the family's own docstring says no such closed form
exists, and a primary source now says otherwise.

---

## 6. Prediction against measurement — the calibration the family was missing

Applying `Δω/ω₀ = 2π t/λ₀` to every measured AMC located in this pass, using
each surface's own measured centre frequency and its own stated substrate
thickness:

| Surface | Substrate | f₀ (measured) | t | t/λ₀ | Predicted 2π t/λ₀ | Measured ±90° BW | Measured / predicted |
|---|---|---|---|---|---|---|---|
| Sievenpiper 1999 Fig. 14, two-layer, vias | 1.55 mm, εr 2.2 | 14.75 GHz | 1.55 mm | 0.0763 | 47.9% | ≈44.1% *(digitised)* | **92.0%** |
| de Cos 2010 rigid (Arlon 25N) | 0.762 mm, εr 3.28 | 5.89 GHz | 0.762 mm | 0.0150 | 9.41% | 7.30% | **77.6%** |
| de Cos 2010 flexible, smooth bent | 0.762 mm, εr 3.0 | 6.27 GHz | 0.762 mm | 0.0159 | 10.01% | 6.63% | **66.2%** |
| de Cos 2010 flexible, flat | 0.762 mm, εr 3.0 | 6.23 GHz | 0.762 mm | 0.0158 | 9.95% | 6.29% | **63.2%** |
| de Cos 2010 flexible, creeping bent | 0.762 mm, εr 3.0 | 6.23 GHz | 0.762 mm | 0.0158 | 9.95% | 6.19% | **62.2%** |

`CALCULATED` (predictions), against `MEASURED` (the last column's inputs, except
row 1 which is `INFERRED` from a digitised figure).

**Every measured surface lands below the ceiling, and between 62% and 92% of
it.** Nothing beats it, which is what a bound should look like, and nothing is
so far below it that the formula is useless.

Two readings of the spread, both worth carrying:

- The 92% row is the thickest surface in electrical terms (`t/λ₀` = 0.076,
  five times the others). The four thin surfaces cluster at 62–78%. **A
  plausible reading is that the LC model gets optimistic as the surface gets
  electrically thinner** — but four points from one paper and one from another
  is not enough to claim a trend, and it is recorded as an observation, not a
  correction. `INFERRED`.
- Sievenpiper's own §10.3 anticipates the direction: he plots measured against
  calculated resonance frequency, with error bars that are the measured and
  calculated bandwidths, for *"23 different structures built during the course
  of this study"*, and names the causes — *"the approximation used in
  calculating the capacitance, particularly for the two-layer design, and also
  the formula used for inductance, which admittedly neglects many effects, such
  as additional contributions from the vias."*

### A second, independent check of the model on Sievenpiper's own sample

Feeding his published geometry (triangular lattice of hexagons, a = 2.54 mm,
g = 0.15 mm, t = 1.55 mm, εr = 2.2) through Eqs. 10.1.1/10.1.3/10.1.6/10.1.7
gives `C_individual` = 43.8 fF, `C_sheet` = 75.9 fF/sq, `L` = 1.948 nH/sq and
**f₀ = 13.1 GHz, against 14.75 GHz measured — 11% low.** `CALCULATED`.

One input is `ASSUMED`: Sievenpiper defines `w` as *"the width of the
capacitor"* and shows it in a figure not reproducible from the text layer; this
takes it as the shared hexagon edge, `(a − g)/√3`. A different reading of `w`
moves `C` in proportion and f₀ as its inverse square root, so the 11% figure is
sensitive to that choice and should not be quoted as the model's accuracy
without it.

**Predicting the band edges rather than the width** is the cleaner test,
because it uses only one fitted number. Taking `L = µ₀t` from the stated 1.55 mm
thickness and back-fitting `C` from the measured 14.75 GHz zero crossing, the
exact `|Z_s| = η₀` solution puts the ±90° edges at **11.63 and 18.70 GHz**.
Digitisation of the measured curve gives **12.0 and 18.4–18.7 GHz**. The upper
edge agrees to about 0.1 GHz; the lower edge is 0.37 GHz (3%) out. `CALCULATED`
against `INFERRED`.

---

## 7. What is still missing, stated precisely

**There is still no measured in-phase reflection band centred inside X-band
(8–12 GHz).** #471's finding on that point survives this pass intact. What has
changed is the size and shape of the hole:

| | Before this pass | After |
|---|---|---|
| Primary-source ±90° definition | none | Sievenpiper 1999 p. 2064, twice; thesis §10.1 |
| Measured in-phase bandwidths in the corpus | zero | four (6.2, 6.2, 6.3, 14.8 GHz centres) |
| Measured on a **flexible, via-less, single-substrate** AMC | zero | three (flat, and two bend patterns) |
| Closed-form predictor for the scored quantity | none | `2π µ_r t/λ₀`, primary-source |
| Calibration of real hardware against that predictor | none | 62–92% of ceiling, n = 5 |
| Measured band **centred** in 8–12 GHz | none | **still none** |

The nearest miss is Sievenpiper's Fig. 14, whose in-phase band *starts* at
about 12.0 GHz — it touches the top edge of X-band and covers none of it.

**One lead, deliberately not relied on.** Saleem, M. & Li, X.-L., "Low
Scattering Microstrip Antenna Based on Broadband Artificial Magnetic Conductor
Structure," *Materials* 13(3):750 (2020), doi
[10.3390/ma13030750](https://doi.org/10.3390/ma13030750) — open access, and the
right shape: two metal layers, **no vias**, FR-4, εr 4.3, 2.4 mm thick, 8 mm
period, **0.20 mm smallest gap** (exactly this shop's floor), with an in-phase
band reported as spanning X-band. **The full text could not be read** — MDPI
returns HTTP 403 and the PMC mirror (PMC7040665) serves an HTML shell rather
than the PDF to every route tried. A retrieval summary of it returned a
bandwidth figure whose own arithmetic does not close (4.6 GHz over an 8.7 GHz
centre is 52.9%, not the 42% quoted alongside it), and it conflated the
paper's ±90° AMC band with a separate `180° ± 37°` checkerboard
phase-difference criterion. **Nothing from it is carried into this document as
a result.** It is the single highest-value item to fetch next: if it reads as
advertised, it is simultaneously the missing X-band number, a via-less design,
and a design sitting on this shop's exact feature floor. → `RUNNING-LISTS.md` §1.

---

## 8. Every route tried

**Succeeded:**

| Route | Result |
|---|---|
| **Sievenpiper 1999, IEEE Trans. MTT 47(11)** — Wayback Machine snapshot (2026-08-14) of `optoelectronics.eecs.berkeley.edu/ey1999ieee4711.pdf`, a copy hosted by co-author **Eli Yablonovitch's own group** | **The full 16-page paper**, `application/pdf`, 417,018 bytes, pp. 2059–2074. Live host currently returns HTTP 403 with *"Server unable to read htaccess file"* — a server misconfiguration, not a paywall |
| **Sievenpiper PhD dissertation (UCLA, 1999)** — Wayback snapshot of `optoelectronics.eecs.berkeley.edu/ThesisDan.pdf` | **All 162 pages**, 2,022,633 bytes. Chapters 8 and 10 carry the via-role statement and the design equations the journal paper compresses |
| 420 dpi page renders (PyMuPDF) of both PDFs | **Decisive.** The text layer silently drops every `π/2`; the renders show them unambiguously. Same subset-font failure mode as `docs/costa-thin-spacer-correction.md` §1 |
| 600 dpi pixel digitisation of Fig. 14 | ±90° edges at 12.0 and 18.4–18.7 GHz, zero crossing 14.75 GHz. Cross-checks against the paper's own prose band-gap numbers to ~1 percentage point |
| **de Cos et al. (2010), *PIER* 106** — direct download from `jpier.org` | Full 14-page open-access text. Four measured ±90° bandwidths, flat and bent, on a via-less flexible AMC |
| **US12089385B2** — Google Patents, full text | §9 below. Verbatim confirmation of the two sentences `CLAUDE.md` quotes, and of Example 1's stated permittivity |
| Unpaywall + OpenAlex + Semantic Scholar on both IEEE DOIs | Positive confirmation that no free copy of either exists — a fact about the world, not a fetch failure |

**Failed, and why:**

| Route | Outcome |
|---|---|
| **Yang & Rahmat-Samii 2003**, IEEE Trans. AP 51(10) | **Closed access, no repository copy.** Unpaywall `is_oa:false / closed / has_repository_copy:false / oa_locations:[]`; OpenAlex `is_oa:false / closed / any_repository_has_fulltext:false`. Two independent indexes agree → `RUNNING-LISTS.md` §1 |
| `ieeexplore.ieee.org/iel5/8/27715/01236087.pdf` (the paper's direct Xplore PDF) | HTTP 418, the same teapot this repo already records for Xplore |
| **Cambridge University Press**, Yang & Rahmat-Samii's own book chapter 6 (*Electromagnetic Band Gap Structures in Antenna Engineering*, 2009) — the authors' own restatement | Serves a preview shell, not the chapter. `WebFetch` returned only the abstract-level summary; a direct `curl` of the same URL returned 847 KB of HTML, not a PDF |
| **scispace** mirror of the same book | Returns a 13-page PDF that is **front matter only** — title page, blurb, author biographies, table of contents. No technical content |
| **DTIC** `ADP015050` (Rahmat-Samii, "The Marvels of EBG Structures") | HTTP 403 |
| **ACES Journal** 18(4), Nov 2003, same Rahmat-Samii review — **retrieved successfully** but contains **no ±90° statement**. Recorded as a documented null so nobody re-fetches it | Read in full; two mentions of "reflection phase", neither a bandwidth definition |
| **MDPI / PMC**, Saleem & Li (2020) | MDPI HTTP 403 (a block this repo already records); the PMC mirror served an HTML shell rather than the PDF on both `pmc.ncbi.nlm.nih.gov` and `www.ncbi.nlm.nih.gov` paths. §7 |
| `ieice.org` ISAP 2009, "From a PEC Ground Plane to an EBG Surface" | HTTP 202 with a zero-byte body |
| `ee.ucla.edu` thesis path (the original 1999 host) | 503 over HTTP, 403 over HTTPS. The Berkeley Wayback copy replaced it |

**Not tried, deliberately:** Sci-Hub and equivalents. Every route above is the
publisher, an author's own institutional page, an open-access journal, or the
Internet Archive's copy of an author's own institutional page.

---

## 9. The patent's own text, re-verified

`CLAUDE.md`'s charter quotes US12089385B2 three times. All three are confirmed
verbatim against Google Patents' full text of the granted patent (retrieved
2026-09-13, 414,132 bytes of HTML, text-extracted):

| Charter quote | Patent text | Verdict |
|---|---|---|
| *"reflective with 180-degree phase shift and zero transmission"* [0003] | "The electromagnetic properties of such surfaces are generally reflective with 180-degree phase shift and zero transmission." | **Exact** |
| *"a planar or conformal antenna situated slightly above such surface will have its signal cancelled on axis"* [0058] | "A planar or conformal antenna situated slightly above such surface will have its signal cancelled on axis as a result." | **Exact** |
| *"produces the same full reflection with 0° phase shift, with doubling the signal strength"* [0058] | "On the other hand, a perfect magnetic conducting (PMC) surface, produces the same full reflection with 0° phase shift, with doubling the signal strength." | **Exact** |

Paragraph numbers `[0003]` and `[0058]` are as reported by the Google Patents
rendering; the sentences themselves are confirmed against the raw page text.

**One gloss the charter's "doubling" deserves, because a reader will ask.** On a
perfect electric conductor the image of a flat-lying antenna is inverted, so
direct and reflected fields subtract and cancel on axis. On a perfect magnetic
conductor the image is in phase, so they **add**: the on-axis field is twice
what the element alone would give, which is +6 dB in field. That is the sense
in which the strength "doubles" — it is a comparison against the free-standing
element, not a claim that a surface creates energy. `CALCULATED`, textbook
image theory; Sievenpiper's own framing of the same fact is *"the image
currents in the surface reinforce the currents in the antenna, instead of
canceling them"* (1999, p. 2064).

### Example 1's permittivity: the patent's own body text says 310

#471 records that the patent *"contradicts itself on the ceramic's
permittivity enough to move the resonance by 2.2× its own width"*, and
`docs/example1-2-scoring-recipe.md` §3 carries `ε₁ = 250 − 1.25j, tanδ ≈ 0.005`
for the same insert.

**Confirmed from the patent's body text, verbatim:**

> "By embedding the metamaterial inserts 552A made by very high dielectric
> material of εr>50 (for example, strontium titanate, εr=310), the loop
> current is created within the dielectric inserts, which leads to magnetic
> resonances"

and the band, verbatim:

> "FIGS. 5D-5F are plots showing simulated and measured performance of this EM
> skin 500 over select frequencies ranging from 8.3-8.7×10⁹ Hz."

> "The retrieved relative permeability of this layer is shown to be around 5,
> rising to close to 20 around resonance frequency in the X-band."

**Half the contradiction is verified, half is not.** `εr = 310` is in the
patent's running text and is confirmed here first-hand. The competing `250 −
1.25j` is **not in the running text at all** — a search of the full extracted
text for "250" returns only unrelated patent-citation numbers. It presumably
comes from the table in FIG. 5C, which is a drawing and was not re-rendered in
this pass. **So the contradiction is real in the sense that two different
numbers are recorded in this repo for the same material, but this pass
verified only one of them, and cannot say which surface of the patent the
other came from.** Settling it needs FIG. 5C rendered and read, which is a
small, cheap task and belongs to #220, not here.

*Why the difference matters: a Mie resonance sits at a frequency proportional
to 1/√εr. Between 250 and 310 that is a 11.4% shift — against a stated band
(8.3–8.7 GHz) that is only 4.7% wide. The resonance moves by more than twice
its own bandwidth, so the two numbers do not describe the same device.*
`CALCULATED`.

---

## 10. The four decisions #471 asked for

### Decision 1 — a dedicated AMC/HIS harvest pass? **Defer the broad pass; the narrow gap is one paper wide.**

`INFERRED` (a judgement, not a literature claim).

The ticket's coverage finding was correct: the three MXene research documents
return zero hits for this vocabulary. But the reason to run a harvest is to get
something, and this pass already got the things a harvest would have been run
for — a primary-source definition, four measured bands, a closed-form
predictor, and a printability answer. What remains unfetched is **one specific
paper** (§7) and **one specific question** (how much of the ±90° surface band a
real antenna keeps — Yang & Rahmat-Samii's own subject, §1).

Running a broad AMC/HIS harvest now would collect precedent for a family that
has no live requirement pointing at it. **The recommendation is: no broad
harvest until a `REFLECTION_PHASE` requirement actually arrives, and when one
does, start from the two named gaps rather than from a keyword sweep.**

### Decision 2 — does ±90° get a primary-source read before becoming a default? **It has one now, and it may become a default.**

`LITERATURE-SUPPORTED` (Sievenpiper 1999 p. 2064, twice, read from a page
render; corroborated by the same author's dissertation §10.1 and independently
by de Cos et al. 2010).

`docs/example1-2-scoring-recipe.md` §4's condition — *"worth a primary-text
check before this becomes a hardcoded default anywhere in code"* — is
**satisfied**. The tier moves from "cited via consistent secondary summary" to
"read first-hand from the primary".

Three conditions travel with it, and all three come from the primary text
rather than from caution:

1. **It stays a reversible default, not a gate.** Unchanged from
   `example1-2-scoring-recipe.md` §2 and `requirement-derived-thresholds.md`.
   Nothing in Sievenpiper makes ±90° a threshold; it is where the reflected
   wave stops helping and starts hurting, which is a sensible place to draw a
   line and not the only one.
2. **It describes the surface, not the antenna.** Sievenpiper's own next
   sentence: *"The bandwidth of the actual antenna might be smaller, depending
   on the geometry of the antenna, and the size and shape of the ground
   plane."* Scoring an *antenna* requirement against a *surface* band would
   overstate the answer, and by an amount nobody here has measured.
3. **It is a normal-incidence statement.** Every measured number in this
   document is normal incidence. de Cos et al. measured oblique incidence too
   but this pass did not read those numbers.

### Decision 3 — is `REFLECTION_PHASE`'s evidence base strong enough to score a candidate today? **Yes, with one caveat that must be printed on the score.**

`INFERRED` from the evidence assembled in §1–§6.

Yesterday the family had a registry entry, an `UnreadPhysicalBound`, a
validated Palace path that had only ever been pointed at unpatterned metal
(#347), and a merged ±90° readout (#346) with nothing to check its answers
against. It now additionally has:

- **a primary-source definition of the scored quantity** (§1) — so the number
  #346 computes is the number the field means;
- **a closed-form ceiling**, `2π µ_r t/λ₀`, from a primary source, that needs
  only the substrate thickness and the centre frequency (§5) — so a candidate's
  simulated bandwidth can be sanity-checked before anyone trusts it;
- **four measured surfaces landing at 62–92% of that ceiling** (§6) — so
  "plausible" has a range. A candidate returning 40% of the ceiling is
  conservative; one returning 110% has a modelling error, not a breakthrough.

**The caveat that must be printed on any such score:** *no measured in-phase
reflection band exists anywhere in this programme's evidence with its zero
crossing inside 8–12 GHz. The calibration band above is anchored at 6.2 GHz
(three points, flexible, via-less) and 14.8 GHz (one point, rigid, with vias),
and X-band sits between them. It is interpolation, not measurement.* That is a
`Warn, never block` warning in ADR-0028's sense: it names the assumption
(that the 62–92% band interpolates across X-band), the cost if wrong (a
bandwidth claim off by tens of percent), and the cheapest way to find out
(§7's one unfetched paper, or the patterned-cell Palace run #471's existing
comment already scoped).

**On the `UnreadPhysicalBound`:** it stays truthful and stays where it is.
Gustafsson & Sjöberg has still not been read first-hand *in this pass* for its
own definition of `B`. What §5 adds is independent corroboration of its `2π`
constant from a second primary source, which is a reason to expect #465's
implementation to be straightforward, not a reason to skip it.

### Decision 4 — is a printable magnetic mirror reachable here? **Yes. The vias are optional and the ceramic is not needed.**

`MEASURED` for the existence proof (de Cos et al. 2010: via-less, single
substrate, flexible, measured flat and bent); `LITERATURE-SUPPORTED` for the
mechanism split (Sievenpiper's own thesis, §4); `CALCULATED` for the design
point below.

The ticket's own framing — *"whether every published route needs a ceramic, a
via array, or a multilayer stack this shop cannot make"* — is answered: **no.**
The minimum viable magnetic mirror is a patterned conductor layer over a plain
conductor layer with dielectric between, which is what ADR-0017 already says
this programme's skins print.

**An X-band design point, computed from Sievenpiper's own equations**, at this
shop's 0.2 mm feature floor, triangular lattice of hexagons:

| a (period) | g (gap) | t | εr | f₀ | a/λ₀ | Ceiling 2π t/λ₀ | Expected measured (× 62–92%) |
|---|---|---|---|---|---|---|---|
| 4.4 mm | **0.20 mm** | 1.55 mm | 2.2 | **9.5 GHz** | 0.140 | 30.9% | **19–28%** |
| 4.0 mm | **0.20 mm** | 1.55 mm | 2.2 | 10.1 GHz | 0.135 | 33.0% | 20–30% |
| 6.0 mm | **0.20 mm** | 0.762 mm | 3.0 | 9.9 GHz | 0.199 | 15.9% | 10–15% |

`CALCULATED`, with `w` `ASSUMED` as the shared hexagon edge (§6) and the model
carrying an ~11% frequency error on Sievenpiper's own X/Ku sample. **These are
starting points for a solver, not predictions.** Two caveats belong on them:

- The bottom row's `a/λ₀ = 0.199` is a fifth of a wavelength, and Sievenpiper
  warns in his own §10.3 that *"the use of a lumped parameter model is itself
  questionable for structures in which free-space wavelength approaches the
  lattice constant"*. Thin plus X-band pushes the cell size up, and the model
  down in confidence, at the same time.
- **The thickness–bandwidth trade is the whole design.** Going from 1.55 mm to
  0.762 mm to buy conformality halves the achievable band. That is not a
  modelling artefact to engineer around; it is `2π t/λ₀`, and §6 says real
  hardware does not beat it.

**Per ADR-0028 this shapes ranking and warnings, never the search.** A
mushroom-with-vias candidate and a sintered-ceramic Mie-cube candidate are both
still returned. What changes is that the via-less printed candidate is the one
that can be built here, and the other two carry a fabrication warning naming
what is missing.

---

## 11. Register updates

**Opens, for `RUNNING-LISTS.md` §1** — two rows, proposed text in the ticket
comment and the handoff report. In summary: **Yang & Rahmat-Samii (2003)**,
closed access confirmed by two independent indexes, stranding the
antenna-versus-surface bandwidth question; and **Saleem & Li (2020)**,
MDPI 403 with a non-serving PMC mirror, stranding what may be the missing
X-band via-less measured number at exactly this shop's feature floor.

**Closes:** #471's four decisions. The coverage gap the ticket was filed for is
now partly filled rather than merely named: the effect has a primary-source
definition, four measured bandwidths, a closed-form ceiling and a printability
answer. The X-band-centred measured number the ticket asked for **still does
not exist in this programme**, and that is stated as the standing gap rather
than papered over.

**Not touched, deliberately:** `CLAUDE.md`, `CONTEXT.md`,
`docs/example1-2-scoring-recipe.md`, `docs/RUNNING-LISTS.md`, ADR-0047, and
#104. §1 and §10's decision 2 name the specific edit
`example1-2-scoring-recipe.md` §2/§4 now warrants (a confidence-tier upgrade
from secondary to primary), and §5 names what #465 gains, but neither change is
made here — this ticket's product is the evidence and the decision, not the
downstream edits.
