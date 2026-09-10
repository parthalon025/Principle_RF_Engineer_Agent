# MXene's electrical properties in the RF bands: what is measured, what is fitted, and what is still missing

**Date:** 2026-09-10
**Ticket:** [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104) (the map, line 156) — bears on [#383](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/383) (measure RF sheet resistance in band), [#382](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/382) (measure DC conductivity against cure schedule), and on `docs/RUNNING-LISTS.md` §3 item 33.
**Question:** The map's standing claim was *"No measured conductivity, permittivity or surface impedance for MXene exists anywhere in 8–12 GHz, and #106's four-point probe cannot close it — it is a DC instrument."* Is that true?

---

## Bottom line up front

**No. A direct, contactless, in-band X-band measurement of MXene's sheet
impedance *and* conductivity exists, was published in 2023, and its full text
was retrieved and read for this document.** Rakhmanov et al. measured sheet
impedance across the whole of 8.2–12.4 GHz in a WR-90 waveguide and report
**sheet resistance falling from 208 Ω/sq at 4 nm to 21 Ω/sq at 40 nm**, an
**AC (microwave) conductivity of 1.20 × 10⁶ S/m against a DC four-point-probe
value of 1.43 × 10⁶ S/m on the same films**, and — verbatim — *"Sheet
resistance is stable around the entire X-band frequency range."*

*In plain terms: somebody has already put MXene in an X-band waveguide and
measured how much it resists radio-frequency current. The number exists. It is
just not measured on the thing this programme actually prints.*

The second half of the map's claim — that a DC four-point probe cannot close
the gap — is **right for a printed trace and wrong for a thin film**, and this
document works out exactly where the boundary falls (§5). Rakhmanov et al.
in fact used a four-point probe as the cross-check on their own X-band result,
and the two agreed to within 16%.

| Question | Answer | Where |
|---|---|---|
| Does measured X-band MXene sheet impedance exist? | **Yes.** 208 → 21 Ω/sq, 4–40 nm films, WR-90, 8.2–12.4 GHz | §1.2 |
| Does measured X-band MXene conductivity exist? | **Yes.** 1.20 × 10⁶ S/m (AC), 1.43 × 10⁶ S/m (DC), same films | §1.2 |
| On an **extrusion-printed trace**? | **No. Nothing, anywhere, in any of the three sources.** Every one is spray-coated or a wax composite | §6 |
| Does the map's "~9× lossier than copper, ~3.8× than silver" survive? | **No — it recomputes to ~7.0× and ~2.9×** on the RF-band figure | §3 |
| Does §3 item 33's ~1.8× skin-depth disagreement survive? | **No.** It is a mislabelled multiplier, not a conductivity dispute. Both sides use the same σ | §4 |
| Can #106's DC four-point probe close the gap? | **Only below ~1.3 µm at 12 GHz.** A 10–35 µm printed trace is far outside that | §5 |
| Is Wang et al.'s "−53.8 dB X-band absorption" usable here? | **No, on two counts**: it is *calculated*, not measured, and it needs **15 mm** of material against the patent's ≤2 mm | §1.3 |

**One correction this document makes to material already in circulation.** The
research attachment that prompted this work cites V₂CTₓ's −53.8 dB as "the best
single-metal X-band absorption" **with no thickness attached at all**. The
paper's own sentence attaches one: *"V₂CTₓ achieved an RL as low as −53.8 dB at
a thickness of 15 mm."* Fifteen millimetres is **7.5× the entire ≤2 mm skin the
patent allows**, so the figure is not a candidate result for this programme —
it is a result about a different, much thicker part. *In plain terms: the
headline number is real, but getting it needs an absorbing layer 15 mm thick —
seven and a half times the 2 mm that the **entire** part, every layer of it, is
allowed. It is not a thinner-is-slightly-worse trade; the result simply does
not exist in the space this programme designs in.*

---

## 1. The three sources, and what each one actually measures

All three are **primary research articles**, not reviews. The first two come
from the same laboratory — Drexel University's Department of Electrical and
Computer Engineering with the A. J. Drexel Nanomaterials Institute — and share
an author (Rakhmanov) and a senior author (Gogotsi), so they are **not
independent of each other**. The third is a separate group with no overlapping
authors; its affiliations were not checked here.

### 1.1 AlHassoon et al. 2020 — an RF conductivity, but only to 10 GHz, and a fit rather than a reading

> K. AlHassoon, M. Han, Y. Malallah, V. Ananthakrishnan, R. Rakhmanov,
> W. Reil, Y. Gogotsi & A. S. Daryoush, *"Conductivity extraction of thin
> Ti₃C₂Tₓ MXene films over 1–10 GHz using capacitively coupled test-fixture,"*
> **Applied Physics Letters 116(18):184101**, published online 4 May 2020,
> doi [10.1063/5.0002514](https://doi.org/10.1063/5.0002514).

Open-ended MXene transmission lines **spray-coated on PET**, capacitively
coupled to a copper transmission line on RT/duroid — solderless, contactless,
repeatable. Three samples at about **1.0, 1.5 and 4.3 µm**. Benchmarked against
copper and graphite films, and used to predict antenna quality factor and
efficiency. Abstract, verbatim: *"The highest conductivity of 1.2 × 10⁶ S/m was
extracted for the 4.3 µm thick Ti₃C₂Tₓ film."*

**Two things about this that the citation alone hides.**

**It covers only the lower half of X-band.** X-band is 8–12 GHz (WR-90's
usable range is 8.2–12.4 GHz). A 1–10 GHz sweep reaches **8–10 GHz and stops**.
It says nothing at all about 10–12 GHz. Roughly half the band this programme
designs into is outside the measurement.

**It is a fit, not a reading.** The abstract states the method verbatim:
*"The extraction process is based on the least squares error method of curve
fitting to minimize the difference between the full wave numerically simulated
scattering parameters and the measured values of the test circuit."* So the
chain is: measure S-parameters → simulate the fixture full-wave → vary σ until
simulation matches measurement → report the σ that minimises the residual.

*In plain terms: nobody read 1.2 million siemens per metre off a dial. They
measured how the fixture behaved, built a computer model of the same fixture,
and turned a conductivity knob in the model until the two curves lay on top of
each other. The number is whatever the knob said.*

**What rung that lands on.** `LITERATURE-SUPPORTED` — per `CONTEXT.md`'s
mapping, a `paper` resolves there, and there is no separate rung for "measured
by somebody else." That is the right answer for a second reason as well: a
least-squares extraction is only as good as the fixture model it is fitted
against, so it inherits a modelling assumption the raw S-parameters do not
carry. It is **not** `MEASURED` (this programme has no bench — the charter caps
its own output at `SIMULATED`), and it is **not** `CALCULATED` (nothing here is
a deterministic closed-form evaluation). Anyone tempted to promote it because
"a real instrument was involved" should note that a real instrument was
involved in Wang et al. too, and §1.3 explains why that changes nothing.

*One phrasing worth pinning down, because it will otherwise be misread.*
ADR-0015 says a cited paper *"carries whatever rung its own original
measurement had"* — which, read alone, could look like a licence to tag a
paper's measured value `MEASURED`. It is not: the same sentence's own
parenthetical pins it, *"the same convention already in use for
literature-sourced data reaching this project as `LITERATURE-SUPPORTED`"*, and
`CONTEXT.md`'s mapping is explicit — `paper` → `LITERATURE-SUPPORTED`.
**Measured-by-someone-else is `LITERATURE-SUPPORTED`, not `MEASURED`, in this
vocabulary**, and that holds for all three sources here however good their
instruments were.

**Two things about this paper remain open, and the full text is the way to
settle them.**

1. **Is σ = 1.2 × 10⁶ S/m one constant fitted across the whole 1–10 GHz
   sweep, or a frequency-resolved curve of which 1.2 × 10⁶ is the peak?**
   This matters: a single fitted constant is a much weaker claim about 8–10 GHz
   specifically than a resolved curve would be.
2. **Was the fixture validated to the top of its stated range?** A capacitive
   coupling gap behaves differently at 10 GHz than at 1 GHz, and the abstract
   does not say what reference the fixture was checked against near 10 GHz.

**Neither is settled here, because the full text could not be opened** — see
§7 for exactly how far the attempt got, which is further than "403" and short
of readable. **But the underlying physical question behind (1) — does MXene's
conductivity vary with frequency across this band? — is largely answered by
§1.2 from an independent measurement**, so the open item is now a
*methodological* one about what AlHassoon et al. did, not a live physical
uncertainty.

### 1.2 Rakhmanov et al. 2023 — the direct hit, in band, and it was readable

> R. Rakhmanov, C. E. Shuck, J. Al Hourani, S. Ippolito, Y. Gogotsi &
> G. Friedman, *"Ultrathin MXene film interaction with electromagnetic
> radiation in the microwave range,"* **Applied Physics Letters
> 123(20):204105**, submitted 14 September 2023, accepted 30 October 2023,
> published online 17 November 2023, doi
> [10.1063/5.0176575](https://doi.org/10.1063/5.0176575).

**This is the single most direct answer to the map's line 156, and the full
text was retrieved this session from the NSF Public Access Repository** —
`par.nsf.gov/servlets/purl/10544297`, a valid 7-page PDF, extracted with
`pymupdf`. Everything quoted below is verbatim from that text, not from the
abstract.

**What was measured, and how.** Ti₃C₂Tₓ **spray-coated** onto 150 µm
plasma-treated borosilicate glass, at **4, 15, 25 and 40 nm** thickness with
surface roughness 2, 8, 10 and 12 nm respectively (both by AFM; also imaged by
optical microscopy). Measured on a **Keysight PNX vector network analyser**,
TRL-calibrated with a **Keysight WR90 calibration kit (8.2–12.4 GHz, X-band)**,
30 kHz IF bandwidth, 10 scans averaged, 3201 data points. Sheet impedance
extracted by the Wang / Díaz-Rubio / Tretyakov waveguide-discontinuity method
(*IEEE Trans. Microwave Theory Tech.* **65**(12), pp. 5009–5018, 2017), which
de-embeds the substrate by representing film-plus-substrate as a cascaded ABCD
network. DC cross-checked with a **Keithley four-point probe**, five
measurements per sample.

**The numbers, verbatim:**

> "Sheet impedance does not exhibit frequency dependence; hence, averaged
> impedance values are plotted in Fig. 3(a). Sheet resistance decreases with
> thickness from 200 to 20 Ω/sq for 4 and 40 nm-thick films, respectively."

> "Sheet resistance is stable around the entire X-band frequency range."

> "Conductivity values for DC are estimated to be 1.43 × 10⁶ S/m, and for AC,
> it is 1.20 × 10⁶ S/m. The deviations between AC and DC sheet conductance
> values are within the errors of the measurements and are negligible when
> surface roughness is taken into account. This endorses the same mechanism of
> charge carrier transport occurring at DC to microwave range."

> "The calculated relaxation time is around 2.3 ps."

Figure 3's caption gives the endpoints one digit more precisely — *"Sheet
resistance (blue) decreases with thickness from 208 to 21 Ω/sq. DC values in
red match microwave measurement."* Figure 4's caption gives the slope-derived
values — *"the real part of conductivity as 1.30 × 10⁶ S/m and the imaginary
part as 1.9 × 10⁵ S/m."*

**Three checks run on those numbers here, and all three pass.** `CALCULATED`

1. **The stated sheet resistances and the stated AC conductivity are the same
   measurement expressed two ways.** 1/(1.20 × 10⁶ × 4 nm) = **208.3 Ω/sq**;
   1/(1.20 × 10⁶ × 40 nm) = **20.83 Ω/sq**. Both reproduce Figure 3's stated
   endpoints (208 and 21 Ω/sq). This is a self-consistency check, not
   independent corroboration — but it does confirm that the AC figure, not the
   DC one, is the number tied to the in-band sheet resistances.
2. **The Drude relaxation time is self-consistent.** For σ(ω) = σ_DC/(1 − iωτ),
   τ = Im(σ)/(Re(σ)·ω). With Re = 1.30 × 10⁶, Im = 1.9 × 10⁵ and
   f = 10.3 GHz (band centre), τ = **2.26 ps**; at 10.0 GHz, **2.33 ps**. Both
   round to the paper's "around 2.3 ps."
3. **The impedance-matching claim checks out.** Absorption peaks when the sheet
   impedance equals half the wave impedance. Free space: 376.73/2 = **188.4 Ω**,
   against the paper's "188 Ω." A WR-90 TE₁₀ mode has cutoff
   c/(2 × 22.86 mm) = **6.562 GHz**, so its wave impedance at band centre is
   376.73/√(1 − (6.562/10.3)²) = **488.7 Ω**, half of which is **244 Ω** —
   against the paper's "~250 Ω."

**Why this matters beyond the numbers: it separates two effects that are
usually tangled.** These films are 4–40 nm thick against an X-band skin depth
of about 4.6 µm, so **t/δ ≈ 0.001–0.01**. At that ratio the current fills the
film uniformly and R_s = 1/(σt) is exact (§5 quantifies "exact"). So skin
effect contributes essentially nothing, and any DC-to-RF difference that shows
up is a change in **σ itself**, not a change in how much of the film the
current is using. Rakhmanov et al. measure that difference: the AC value is
1.20 × 10⁶ against the DC 1.43 × 10⁶, i.e. **16% below DC**.

**That 16% deserves flagging rather than glossing, because the paper's own
model does not predict it.** The same paper's Drude fit, with τ = 2.3 ps,
predicts |σ| at 10 GHz should be **1.0% below** its DC value (§5 does that
arithmetic) — one sixteenth of what was observed. The authors resolve the
discrepancy by attributing it to measurement error and surface roughness
(*"within the errors of the measurements and … negligible when surface
roughness is taken into account"*), which is a reasonable reading for films
whose roughness is 2–12 nm against thicknesses of 4–40 nm. But it means **the
size of the DC-to-RF gap is bounded by an error argument, not measured**: the
honest statement is "somewhere between ~1% and ~16%, and small either way," not
"16%."

*In plain terms: because these films are absurdly thin, the experiment isolates
the one thing this programme actually needed to know — whether MXene's
conductivity is a different number at radio frequency than at DC. Measured
answer: not by much. How much "not by much" is, is fuzzier than the headline
numbers make it look.*

**Four traps to keep this from being over-read.**

- **"Printed" in the abstract does not mean printed.** The abstract says
  *"ultrathin printed Ti₃C₂Tₓ films."* The methods section says
  **spray-coated**. This is not an extrusion-printed trace, and citing it as
  one would be wrong.
- **4–40 nm is one to four orders of magnitude thinner than a printed trace
  needs to be.** `docs/mxene-voltera-nova-printability.md` puts the
  X-band-relevant thickness for a printed conductor at **20–35 µm**. A 20 µm
  trace is **500× thicker** than the 40 nm film and **5,000×** the 4 nm one.
  **What transfers is σ** — a material property, subject to the microstructure
  caveat below. **What does not transfer is anything with a thickness in it**:
  the 208–21 Ω/sq range, and the 50%-absorption result. At σ = 1.20 × 10⁶ S/m
  a 20 µm trace has R_s = **0.042 Ω/sq**, about **4,500× below** the ~188 Ω/sq
  the absorption peak requires. A printed MXene trace is a mirror, not an
  absorber, and no amount of citing this paper changes that.
- **The microstructure caveat runs both ways and is not quantified.** A 4 nm
  spray-coated film is close to a monolayer percolation network; a 20 µm
  extruded trace has thousands of flake-to-flake junctions stacked through its
  thickness. The paper's conclusion that *"both inter and intra-flake
  mechanisms participate in charge transfer from DC to THz"* is measured on the
  thin case. Whether the junction count in a thick extruded trace changes the
  DC-to-RF relationship is **not** addressed by any source found. `UNKNOWN`.
- **This is a two-port transmission measurement, not a one-port reflection
  one.** The framework is R = |S₁₁|², T = |S₂₁|², A = 1 − R − T, with the
  sample between two waveguide halves. That is **shielding effectiveness /
  absorptivity**, a different quantity from the metal-backed reflection loss in
  §1.3. The paper is unusually careful about this itself, devoting a passage to
  how the conventional SE_A formula *"can lead to confusion when reporting
  results"* because a highly reflective sample produces a large SE_A while
  absorbing almost nothing.

### 1.3 Wang et al. 2025 — a wax composite, and the reflection loss was calculated, not measured

> Wang et al., *"Regulation of Microstructure and Absorption Properties of
> MXene Materials: Theoretical and Experimental,"* **Advanced Science
> 12(41):e09994** (2025), open access at
> [PMC12591198](https://pmc.ncbi.nlm.nih.gov/articles/PMC12591198/),
> doi [10.1002/advs.202509994](https://doi.org/10.1002/advs.202509994).

VNA measurement across **X-band 8.2–12.4 GHz** on six compositions — Ti₃C₂Tₓ,
Ti₂NbC₂Tₓ, Ti₂TaC₂Tₓ, Ti₂VC₂Tₓ, Nb₂CTₓ, V₂CTₓ — paired with density-functional
theory (Materials Studio). Verbatim on the samples:

> "During experiments, 15 wt.% MXene was uniformly mixed with paraffin to
> prepare samples measuring 22.86 × 10.16 mm in size and 2 mm in thickness."

**22.86 × 10.16 mm is exactly the WR-90 waveguide cross-section**, which
independently confirms the band and the method.

**What was measured — complex permittivity:**

> "Ti₂NbC₂Tₓ exhibits the highest ε′ (4.5) … while V₂CTₓ shows the lowest ε′
> (3.0) … Ti₃C₂Tₓ displays intermediate ε′ (3.8–4.0)."

> "V₂CTₓ achieves the highest ε′′ (0.6 at high frequencies) … Ti₃C₂Tₓ exhibits
> a prominent ε′′ peak linked to structural relaxation, while other MXenes show
> moderate losses governed by doping-specific mechanisms."

A **numeric** ε″ is given only for V₂CTₓ (0.6); Ti₃C₂Tₓ's is described as a
peak without a value attached, and the remaining four are not given
individually at all. The real permeability is *"0.98–1.08 for all MXenes, confirming negligible magnetic
energy storage"* — as expected for a non-magnetic material.

**What was *not* measured — the reflection loss.** Verbatim:

> "Reflection loss (RL) of the materials was calculated using transmission line
> theory, with the specific formula as follows: RL(dB) = 20 lg |Z_in − Z₀| /
> |Z_in + Z₀| … Z_in = Z₀ √(µ_r/ε_r) tanh( j (2πfd/c) √(µ_r ε_r) ) … f
> represents the electromagnetic wave frequency, **d is the material
> thickness**, and c is the speed of light."

**`d` is a free parameter in that formula.** The samples are 2 mm thick; the
headline RL figures are the model evaluated at whatever `d` minimises RL. The
paper says so plainly:

> "V₂CTₓ achieved an RL as low as **−53.8 dB at a thickness of 15 mm**, while
> Ti₂VC₂Tₓ exhibited multiple RL values below −30 dB across the 9–12 GHz range,
> with the deepest loss valley at −48.4 dB. … In contrast, Ti₃C₂Tₓ reached
> **−38.7 dB at 17 mm thickness**, and Nb₂CTₓ showed **−36.4 dB at 18 mm
> thickness**."

Against the patent's ≤2 mm skin: **15 mm is 7.5×, 17 mm is 8.5×, 18 mm is 9×**
the entire allowed stack. `CALCULATED`

*In plain terms: the permittivity is a real measurement on a real 2 mm sample.
The dramatic absorption number is arithmetic done afterwards, asking "if we had
made this slab 15 mm thick instead, how well would it absorb?" — and the answer
to that question is not available to a design that has to fit in 2 mm.*

**Three distinctions this paper makes it easy to blur, kept apart:**

- **RL is not SE and neither is absorptivity.** Wang et al.'s RL is a **one-port,
  metal-backed** quantity: the wave enters, hits a perfect conductor behind the
  slab, and RL measures how little comes back. Rakhmanov et al.'s A = 1 − R − T
  is a **two-port** quantity with nothing behind the sample. A slab that scores
  −53.8 dB RL and a film that absorbs 50% are not comparable numbers, and
  neither is a shielding-effectiveness figure in dB.
- **Measured permittivity, calculated reflection loss.** The paper is explicit
  and honest about this. Citations that carry the RL number without the word
  "calculated" and without the thickness are the problem, not the paper.
- **`ε′ = 3.8–4.0` is a wax number, not a MXene number.** See below.

**Why this cannot become a Material-property library entry.** `CALCULATED`

At 15 wt% MXene in paraffin, the **volume** fraction is
(15/ρ_MXene) / (15/ρ_MXene + 85/ρ_wax). With ρ_MXene = 3.7–4.4 g/cm³ and
ρ_wax = 0.90–0.93 g/cm³ this gives **3.5–4.3 vol% MXene, i.e. 95.7–96.5 vol%
wax**. (The paper states no densities, so the density pair is `ASSUMED` and the
volume fraction inherits that.) The measured ε′ of 3.0–4.5 is therefore a
property of *wax with a few percent of flakes in it*.

And the MXene phase's own contribution cannot be recovered from it. A
conductive phase's effective loss permittivity is ε″ = σ/(ω ε₀). At 10 GHz,
ω ε₀ = 0.556 S/m, so:

| σ of the MXene phase | ε″ at 10 GHz |
|---|---|
| 1 × 10⁵ S/m (pessimistic) | 1.80 × 10⁵ |
| 6.9 × 10⁵ S/m (repo's as-printed DC figure) | 1.24 × 10⁶ |
| 1.2 × 10⁶ S/m (§1.2's AC figure) | 2.16 × 10⁶ |

**Any two-phase mixing rule saturates long before that.** Illustrating with
Maxwell-Garnett for spherical inclusions at 4 vol% in a host of ε_h = 2.25, the
effective permittivity is **2.5312** for an inclusion permittivity of 10³ and
**2.5312** for 2.2 × 10⁶ — identical to four decimal places across three orders
of magnitude of inclusion permittivity, because the limit as ε_i → ∞ is
ε_h(1 + 2f)/(1 − f), which contains no ε_i at all. Real MXene flakes are
high-aspect-ratio platelets rather than spheres, which raises the ceiling (and
is why the measured ε′ is 3.0–4.5 rather than 2.53) — but it does not remove
the saturation, and the inversion for σ stays ill-conditioned either way.

*In plain terms: once the flakes are conductive enough, making them even more
conductive stops changing what the wax block measures. So you cannot work
backwards from the wax block's number to the flakes' number. The measurement is
real; it is just a measurement of something else.*

**ADR-0015**'s own justification for the Material-property library settles
where this belongs: *"a material's εr at 10 GHz is a fact about the material,
true regardless of which requirement is asking."* ε′ = 3.8–4.0 is a fact about
**MXene-in-paraffin at 15 wt%**, not a fact about MXene. And per **ADR-0035** a
literature search *"finds and cites candidate sources"*
and *"never writes a library entry itself."* This enters as a **citation for a
human to read**, filed against a MXene-in-paraffin composite and never against
MXene. Auto-populating `ε_r = 3.9` for "MXene" from this paper would be a
straightforward error.

---

## 2. Every number in this document, recomputed

Everything below was recomputed here from first principles rather than copied.
Two standard results for a good conductor, both `CALCULATED`:

```
    skin depth          δ   = 1 / √(π f µ₀ σ)
    surface resistance  R_s = √(π f µ₀ / σ)
```

with µ₀ = 4π × 10⁻⁷ H/m. Note R_s = 1/(σδ), so the two are one relationship
written twice. **Both formulas assume the conductor is thick compared with δ**
— which is exactly the assumption §5 shows fails for a thin film.

*In plain terms: at radio frequency the current does not use the whole
thickness of a conductor — it crowds into a thin layer at the surface. The skin
depth is how thick that layer is. The surface resistance is what the conductor
looks like electrically once you accept that only that layer is carrying
current, and it is quoted in ohms per square (the resistance of any square
patch of the surface, regardless of how big the square is).*

**At 10 GHz:**

| Material | σ (S/m) | δ (µm) | R_s (Ω/sq) |
|---|---|---|---|
| MXene, repo's as-printed extrusion figure (**DC**) | 6.9 × 10⁵ | **6.06** | **0.2392** |
| MXene, AlHassoon RF-extracted / Rakhmanov AC (**RF**) | 1.2 × 10⁶ | **4.59** | **0.1814** |
| Printed silver ink, Voltera spec floor | 1 × 10⁷ | 1.59 | **0.0628** |
| Copper | 5.8 × 10⁷ | 0.661 | **0.0261** |
| Bulk silver (for contrast — see §3) | 6.3 × 10⁷ | 0.634 | 0.0250 |

**Across the band, at the two MXene conductivities:**

| | δ at 8 GHz | δ at 10 GHz | δ at 12 GHz |
|---|---|---|---|
| σ = 6.9 × 10⁵ S/m (DC) | 6.77 µm | 6.06 µm | 5.53 µm |
| σ = 1.2 × 10⁶ S/m (RF) | 5.14 µm | 4.59 µm | 4.19 µm |

---

## 3. Recomputing the map's standing loss preference

`docs/RUNNING-LISTS.md` §3 correction 4, and #104's body at line 78, both carry
the same figure: *"MXene is **~9× lossier than copper and ~3.8× than silver**
at 10 GHz, not the ~85× a DC ratio suggests."*

Above roughly three skin depths, R_s ∝ 1/√σ, so a conductivity ratio becomes a
loss ratio by taking its square root. Recomputing from the R_s column above:
`CALCULATED`

| Against | With σ = 6.9 × 10⁵ (DC) | With σ = 1.2 × 10⁶ (RF) |
|---|---|---|
| Copper, 5.8 × 10⁷ | 0.2392/0.0261 = **9.17×** | 0.1814/0.0261 = **6.95×** |
| Printed silver ink, 1 × 10⁷ | 0.2392/0.0628 = **3.81×** | 0.1814/0.0628 = **2.89×** |
| Bulk silver, 6.3 × 10⁷ | 0.2392/0.0250 = 9.56× | 0.1814/0.0250 = 7.25× |

**The map's 9× and 3.8× reproduce exactly on the DC figure — 9.17 and 3.81.**
So the arithmetic behind the map was right; only its input was DC. **On the one
RF-band figure the same comparison recomputes to ~7.0× copper and ~2.9× printed
silver.** MXene's RF penalty is about a quarter smaller than the map records.

Using Rakhmanov's other two values changes little: at his average
1.30 × 10⁶ S/m the ratios are 6.68× and 2.77×; at his DC 1.43 × 10⁶ S/m,
6.37× and 2.64×.

**The subtlety a reader will otherwise trip on: the map's "silver" is the
printed ink, not the metal.** Look at the table. Against **bulk** silver at
6.3 × 10⁷ S/m the ratio is **9.56×** — *worse* than the 9.17× against copper,
because bulk silver is a better conductor than copper. So a "3.8× versus
silver" figure is arithmetically impossible against bulk silver, and only makes
sense against **printed silver ink at ~10⁷ S/m**, which is the Voltera NOVA's
own spec floor for its own inks. Anyone reading "MXene is only 3.8× lossier
than silver" as a statement about the metal has it backwards by a factor of
two and a half.

*In plain terms: the comparison is MXene against the silver you can actually
squeeze out of this printer, which is roughly six times worse than a solid
silver bar. Compared with a solid silver bar, MXene is about as far behind as
it is behind copper.*

**Two caveats on this recomputation, both load-bearing.**

- **The 1.2 × 10⁶ figure is not measured on a printed trace.** It is a
  spray-coated film in both papers that report it. A printed trace's own σ is
  `UNKNOWN` at RF, which is what #383 exists to fix.
- **R_s ∝ 1/√σ only holds where the conductor is thicker than about three skin
  depths.** For MXene at these conductivities that means thicker than about
  14–20 µm (§5). A thinner trace is in the linear-in-thickness regime instead,
  where the ratio is 1/(σt) on both sides and the square root disappears. The
  ratios in this section describe an electrically thick MXene conductor.

---

## 4. `RUNNING-LISTS.md` §3 item 33 — the disagreement is a label, not a conductivity

Item 33 records a live ~1.8× disagreement about MXene's own skin depth, and
notes that *"neither cites a conductivity."* Working backwards from each side's
number settles it. `CALCULATED`

Inverting δ = 1/√(π f µ₀ σ) gives σ = 1/(π f µ₀ δ²) at f = 10 GHz.

| Side | Its claim | Implied δ | **Implied σ** |
|---|---|---|---|
| §3 correction 7 | a 10 µm film is *"already ~1.65 skin depths at 10 GHz"* | 10/1.65 = **6.061 µm** | **6.90 × 10⁵ S/m** |
| Map #104's 2026-09-05 correction, as quoted by item 33 | MXene's *"3δ is ≈33 µm"* | 33/3 = **11.0 µm** | **2.09 × 10⁵ S/m** |

**Correction 7's implied conductivity is 6.90 × 10⁵ S/m — which is, to three
significant figures, the repo's own as-printed extrusion figure of
6.9 × 10⁵ S/m.** Item 33 is right that correction 7 does not *cite* a
conductivity, but correction 7's number is exactly what that conductivity
produces. That side is sound and its source is identifiable.

**The other side's implied 2.09 × 10⁵ S/m matches nothing in this repo** — not
the as-printed figure, not the freestanding-film figures, not the spray-coated
ones. That is the clue.

**What the 33 µm almost certainly is.** `docs/mxene-voltera-nova-printability.md`
line 106 computes, at σ = 6.9 × 10⁵ S/m, that a printed film needs *"roughly
17–34 µm of thickness across X-band to be electrically thick"* on a **3–5**
skin-depth rule. Recomputing that range's endpoints:

- **3δ at 12 GHz** = 3 × 5.531 = **16.6 µm** — the range's lower end
- **5δ at 8 GHz** = 5 × 6.774 = **33.9 µm** — the range's **upper** end

**33–34 µm is the *five*-skin-depth figure at the *bottom* of the band, not the
three-skin-depth figure.** Dividing it by 3 to recover a δ is what produces the
spurious 11 µm and the spurious 2.09 × 10⁵ S/m.

*In plain terms: one side said "three skin depths is 33 microns." The 33-micron
number was actually five skin depths at the low end of the band. Divide by the
wrong multiplier and you get a skin depth that is 1.8× too big — and a
conductivity three times too small — out of thin air. Both sides were using the
same conductivity all along.*

**Provenance: `INFERRED`.** This is a reconstruction of how a number was
probably produced, not something anyone wrote down. Two things support it —
the 33.9 µm match is to better than 3%, and no conductivity in the repo
produces δ = 11 µm — but neither is proof. What would settle it is the
2026-09-05 comment that first stated "3δ ≈ 33 µm"; **that figure is no longer
present in #104's body or in any of its comments as of 2026-09-10** (checked
directly), so only item 33's quotation of it survives.

**Where AlHassoon's and Rakhmanov's measured value sits: outside both, and it
confirms neither.** At σ = 1.2 × 10⁶ S/m, δ at 10 GHz is **4.59 µm** — smaller
than correction 7's 6.06 µm and much smaller than the map's 11 µm. So the
RF-band measurement does not adjudicate between the two positions; it
**overtakes** them. It says MXene is *more* conductive than either side
assumed, and therefore that radio waves penetrate it *less* deeply than either
side assumed.

**What that does to the conclusion each side drew, stated flatly because it
cuts both ways:**

- **Correction 7's conclusion is strengthened.** It argued a ~10 µm film is
  already opaque and *"thickness is a dead knob."* At σ = 1.2 × 10⁶ S/m a 10 µm
  film is **2.18 skin depths**, deeper into opacity than its own 1.65 — so its
  conclusion holds with more margin than it claimed.
- **The map's conclusion is weakened.** It argued MXene *"never reaches that
  regime at printable thickness,"* so sheet resistance stays **linear** in
  thickness and thickness is the strongest lever the process has. At
  σ = 1.2 × 10⁶ S/m, **3δ is 13.8 µm at 10 GHz** and 12.6 µm at 12 GHz — inside
  the 20–35 µm the printability document says a few extrusion passes reach. A
  printed MXene trace *can* reach the electrically-thick regime, and the
  thickness knob saturates once it does.
- **Neither disturbs #128's finding.** Both routes still agree that for a
  *lossy* element it is the aspect ratio, not the film thickness, that reaches
  the target. Item 33 already said so and that part is untouched.

**Item 33 can be marked resolved** on the evidence in this section, with the
caveat that the resolution rests on an `INFERRED` reconstruction of where 33 µm
came from rather than on the original comment.

---

## 5. What #106's four-point probe can and cannot close

The map says the four-point probe cannot close the gap because it is a DC
instrument. **That is right in general and wrong in one regime, and the
boundary is computable.**

### The regime where a DC probe *is* the X-band answer

For a film thin compared with the skin depth, current fills the whole thickness
uniformly and there is no skin effect to speak of. Then

```
    R_s = 1 / (σ t)          exactly, independent of frequency
```

and a DC four-point probe reading of sheet resistance **is** the X-band sheet
resistance. Rakhmanov et al. state the same thing in their equation (1) — *"for
thin conductive films with thickness d below skin depth, the transverse
electric field induces current density that is equally distributed along the
film"* — and then verify it experimentally against their own four-point probe.

**How good is "exactly"?** The exact surface impedance of an isolated
conducting film is Z_s = η_c / tanh(γt) with η_c = (1+j)/(σδ) and
γ = (1+j)/δ. Evaluating Re(Z_s) against the 1/(σt) approximation:
`CALCULATED`

| t/δ | error in R_s from using 1/(σt) |
|---|---|
| 0.1 | +0.001% |
| 0.2 | +0.014% |
| **0.3** | **+0.07%** |
| 0.5 | +0.55% |
| 1.0 | +8.6% |
| **1.65** (correction 7's 10 µm film at DC σ) | **+52%** |
| **2.18** (the same film at RF σ) | **+110%** |

So the conventional **t/δ ≤ 0.3** rule is if anything conservative: at that
ratio the DC formula is good to better than a tenth of a percent.

### Where the boundary falls, in microns

At the two MXene conductivities, the crossover thickness t = 0.3δ:
`CALCULATED`

| σ | 0.3δ at 8 GHz | 0.3δ at 10 GHz | **0.3δ at 12 GHz** |
|---|---|---|---|
| 6.9 × 10⁵ S/m (DC) | 2.03 µm | 1.82 µm | **1.66 µm** |
| 1.2 × 10⁶ S/m (RF) | 1.54 µm | 1.38 µm | **1.26 µm** |

**The binding number is ~1.3 µm.** Any MXene film at or below about 1.3 µm is
inside the DC-equals-RF regime across the whole of X-band, at either
conductivity. Above roughly 2 µm it is leaving that regime, and by 10 µm a DC
reading understates the RF sheet resistance by 52–110%.

*In plain terms: the four-point probe is not wrong because it is a DC
instrument. It is wrong once the film is thick enough that radio-frequency
current stops using all of it. Below about a micron and a bit, the DC number is
the radio number. A printed trace at 10 to 35 microns is well past that, and
there the DC number flatters the material by anywhere from half again to
double.*

**This is exactly why Rakhmanov et al.'s films could be cross-checked with a
probe and a printed trace cannot.** At 4–40 nm, t/δ ≈ 0.001–0.01, so skin
effect contributes nothing and the two methods must agree **as far as geometry
is concerned**. Any residual difference is dispersion in σ itself or
measurement error — which is exactly the 16% the residual below discusses, and
exactly why that 16% is interpretable at all.

### The residual, named honestly

**The arithmetic above covers classical skin effect only.** It assumes σ itself
is the same number at DC and at 10 GHz. Three things bear on whether that
assumption holds, and they do not all point the same way:

1. **Rakhmanov et al. measured a 16% gap in the "wrong" direction.** AC
   1.20 × 10⁶ S/m against DC 1.43 × 10⁶ S/m is the RF conductivity coming out
   **lower** than DC — meaning RF sheet resistance **higher**, not lower. The
   authors attribute it to measurement error and surface roughness and call it
   negligible. Whether 16% is negligible depends on the decision it feeds; for
   a loss budget it is not nothing.
2. **The Drude fit predicts almost no dispersion across X-band.** With
   τ = 2.3 ps, |σ(ω)|/σ_DC = 1/√(1 + (ωτ)²) gives ωτ = 0.116 at 8 GHz and
   0.173 at 12 GHz, so |σ| falls by **0.7% at 8 GHz and 1.5% at 12 GHz**.
   (The same model at 1 THz predicts a 93% drop, which is why THz results
   emphatically do not transfer into X-band.) `CALCULATED`
   **Items 1 and 2 do not agree with each other**, and should not be read as
   two corroborating facts: the model predicts ~1% and the measurement showed
   ~16%. The paper closes that gap with an error argument, not with physics
   (§1.2). So the DC-to-RF penalty on an ultrathin film is bounded somewhere
   in **~1–16%**, and is not pinned.
3. **The mechanism this document cannot bound.** GHz shunting of inter-flake
   contact resistance — capacitance across a flake junction carrying current
   the DC path cannot — would push the true RF value **below** the DC one by an
   amount nobody here has quantified. Rakhmanov et al.'s films have far fewer
   stacked junctions than a 20 µm extruded trace, so their result does not
   settle it for a printed trace. `UNKNOWN`.

**Practical reading for #106 and #382.** A DC four-point probe on a printed
trace is still worth doing — it is the input to the cure-schedule question
(#382), and it establishes the DC end of the DC-to-RF ratio #383 is chartered
to quantify. What it cannot do is stand in for the RF number on a trace thicker
than about 1.3 µm. The map's conclusion is correct for the artefact this
programme prints; it is the *reason* that needed sharpening, and the sharpened
version has a number attached to it.

---

## 6. What is still genuinely missing

**No X-band measurement on an extrusion-printed MXene trace of known thickness
exists in any of these three sources.** Restating what each one is instead:

| Source | Form of the MXene | Band | What was measured |
|---|---|---|---|
| AlHassoon 2020 | Spray-coated on PET, 1.0–4.3 µm | **1–10 GHz** (lower half of X-band only) | S-parameters; σ by least-squares fit to a full-wave model |
| Rakhmanov 2023 | Spray-coated on glass, 4–40 nm | **8.2–12.4 GHz** (all of X-band) | Sheet impedance in WR-90; σ from R_s and AFM thickness |
| Wang 2025 | **15 wt% in paraffin**, 2 mm slab | **8.2–12.4 GHz** | Complex permittivity of the composite; RL **calculated** afterwards |

Nothing here is extrusion-printed. Nothing here is at printable trace
thickness in band except by extrapolation. `docs/mxene-voltera-nova-printability.md`
§"What could not be verified" already records the sibling gap on the
manufacturing side — no source states per-pass thickness for a fine extruded
MXene line — and the two gaps compound: this programme cannot state a printed
trace's RF sheet resistance because it knows neither the σ of a printed trace
at 10 GHz nor the thickness such a trace would have.

**Still open on AlHassoon 2020 specifically:** whether its σ is one fitted
constant across 1–10 GHz or a frequency-resolved curve, and whether the fixture
was validated near 10 GHz. Both need the full text. §1.2 answers the physical
question those bear on but not the methodological one.

**Still open on the microstructure question:** whether a thick, many-junction
extruded trace has the same DC-to-RF relationship as a thin spray-coated film.
No source found addresses it. `UNKNOWN`.

---

## 7. Every route tried

This section distinguishes claims about the world from claims about us.

**Succeeded:**

| Route | Result |
|---|---|
| Semantic Scholar Graph API, both AIP DOIs | Full abstracts, author lists, dates, volume/issue. Independent of the publisher's own site |
| **NSF Public Access Repository**, `par.nsf.gov/servlets/purl/10544297` | **The whole point of this document.** HTTP 200, `application/pdf`, 2,073,482 bytes, `PDF document, version 1.3, 7 page(s)`. Extracted cleanly with `pymupdf`. **This is the full text of Rakhmanov et al. 2023** |
| PMC open access, `PMC12591198`, raw HTML via `curl` | Full text of Wang et al. 2025, parsed directly without a summarising model. Every quotation in §1.3 comes from this |
| Drexel Nanomaterials Institute publication list | Located a free PDF link for AlHassoon 2020 that no index reports — see the failure table |

**Failed, and precisely how far each got:**

| Route | Outcome |
|---|---|
| **AIP publisher pages**, `pubs.aip.org/aip/apl/article/...` for both DOIs | **HTTP 403 Forbidden** on both. Consistent with the standing publisher-blocking pattern in `RUNNING-LISTS.md` §1 |
| **ResearchGate** | HTTP 403 (recorded from the prior session's attempt; not re-tried here, since the NSF PAR route succeeded and made it unnecessary) |
| **NSF PAR full text of Rakhmanov, first attempt** | *"Downloaded but decoded as unreadable binary"* — **this was a claim about us, not the world.** The bytes were a perfectly valid PDF; what failed was reading them without a PDF extractor. Corrected here. **`pymupdf` is the tool to reach for first on this class of file**, exactly as `docs/costa-thin-spacer-correction.md` §8 already concluded |
| **AlHassoon 2020 full text — Unpaywall** | `is_oa: false`, `oa_status: "closed"`, `has_repository_copy: false`, `oa_locations: []`. Queried 2026-09-10 |
| **AlHassoon 2020 full text — OSTI records API** | Empty result set for the DOI |
| **AlHassoon 2020 full text — NSF PAR search** | No matching record |
| **AlHassoon 2020 full text — Drexel institutional repository** (`researchdiscovery.drexel.edu`) | Record exists, metadata only, no attached file |
| **AlHassoon 2020 full text — Drexel Nanomaterials Institute PDF** (`nano.materials.drexel.edu/wp-content/papercite-data/pdf/722.pdf`) | **A free copy exists and downloads** — HTTP 200, `application/pdf`, 1,453,489 bytes, `PDF document, version 1.7, 6 page(s)`. **But it is AES-256 encrypted with a user password.** The encryption dictionary reads `/Filter /Standard /CFM /AESV3 /Length 256 /R 5`. `pymupdf` (`needs_pass 1`, empty password rejected), poppler's `pdftotext` (`Command Line Error: Incorrect password`) and `pikepdf` (`PasswordError: invalid password`) all refuse it. **So the paper is located but not readable** — a more precise statement than either "no free copy exists" or "we got a 403", and better than the position at the start of this session |

**Not tried:** MDPI-hosted material, per the standing 403 pattern; IEEE Xplore,
recorded as HTTP 418 in `RUNNING-LISTS.md` §1. Neither is likely to hold a copy
of an AIP paper.

**For `RUNNING-LISTS.md` §1, the stranded-source register:**

> **AlHassoon et al. (2020)**, *"Conductivity extraction of thin Ti₃C₂Tₓ MXene
> films over 1–10 GHz using capacitively coupled test-fixture,"* *Appl. Phys.
> Lett.* **116**(18):184101, doi `10.1063/5.0002514` — publisher 403; Unpaywall
> and OSTI both report no open copy; **a free PDF does exist at
> `nano.materials.drexel.edu/wp-content/papercite-data/pdf/722.pdf` but is
> AES-256 password-encrypted** and refused by three independent PDF tools. It
> is the only way to settle whether its σ = 1.2 × 10⁶ S/m is one fitted constant
> across 1–10 GHz or the peak of a resolved curve, and whether the fixture was
> validated near 10 GHz. Bears on #104, #383. **Downgraded in importance** by
> Rakhmanov et al. 2023, whose full text answers the physical question from an
> independent in-band measurement.

---

## 8. What this could change downstream — options, not decisions

Nothing here decides anything. These are the choices this evidence puts in
front of a human, with what each costs.

### For #383 (measure RF sheet resistance of the cured ink, in band)

**#383 currently specifies a microstrip ring resonator on characterised
laminate, extracting conductor loss from the loaded Q.** §1.2 puts a second
method on the table — the **two-port WR-90 transmission measurement** Rakhmanov
et al. used — and the two trade off against each other along a clean axis:
**direct versus representative.** Neither is obviously right; the point of
naming both is that #383 currently names only one.

- **The ring resonator is the more *representative* measurement.** It measures
  the loss of an actual printed trace, in the actual geometry the design uses,
  with the actual current distribution around a printed strip's cross-section.
  Nothing else on offer does that.
- **A common worry about it does not apply here, and the reverse is true.** One
  might expect a lossy conductor to break the extraction. It does the opposite:
  at R_s ≈ 0.18 Ω/sq MXene's conductor loss is about **7× a copper ring's**
  (§3), so conductor loss **dominates** the loss budget rather than perturbing
  it, and #383's subtraction (dielectric loss out, radiation loss out, conductor
  loss left over) becomes a well-conditioned "subtract small from large" instead
  of a difference between comparable terms. **A resistive layer makes the ring
  resonator's extraction easier, not harder.**
- **Its real costs are elsewhere.** The Q is low, so the resonance is broad and
  the Q reading itself carries more uncertainty; the fixture needs a ground
  plane and a feed transition; and converting a per-unit-length loss into an
  R_s still needs a conductor-loss model (strip current distribution, edge
  effects, surface roughness) that the waveguide method does not need.
- **The two-port waveguide measurement is the more *direct* one.** Put the
  coupon between two waveguide halves, measure S₁₁ and S₂₁ across the band,
  de-embed the substrate, and sheet impedance falls out with no resonance to
  fit, no loss budget to subtract and no strip-geometry model. Its accuracy is
  established in the source it came from (Wang, Díaz-Rubio & Tretyakov, *IEEE
  Trans. Microwave Theory Tech.* **65**(12), 2017).
- **But it needs the sample to transmit something, and a printed trace may not.**
  A fully opaque 20 µm film gives S₂₁ near zero and the extraction degrades —
  Rakhmanov et al. warn about this explicitly (*"Error in RF measurements is
  strongly dependent on the transmission signal, and with its decrease, the
  overall analysis becomes erroneous"*), and it is why their own films are
  4–40 nm. In practice that means printing a **deliberately thin coupon** to get
  σ, then computing the working trace's R_s from that σ and a measured
  thickness — which imports the extrapolation this document has been at pains
  to flag. It also needs a coupon matched to the WR-90 aperture
  (22.86 × 10.16 mm), and a **profilometer thickness on the same coupon**, since
  σ = 1/(R_s · t) and sheet resistance alone does not give σ.
- **Doing both is defensible and probably cheap.** They fail differently — one
  extrapolates across thickness, the other across a loss model — and a printed
  ring-resonator coupon and a printed waveguide coupon are the same print job.

**What #383 should measure, restated:** the DC-to-RF ratio on *this* ink at
*this* cure schedule, in band — which is what #383 already says. What §1.2 adds
is a **published comparison range for that ratio on a different form of the
same material**: RF conductivity **between ~1% and ~16% below DC** on
spray-coated ultrathin film — the lower end being the paper's own Drude
prediction, the upper end its measured AC/DC difference (1.20/1.43 = 0.84),
with the paper attributing the gap between them to measurement error (§1.2, §5).
It is a range, not a target: a printed trace landing inside it is consistent
with the published behaviour, and one landing well outside it makes the
junction-density hypothesis in §5's residual the first place to look.

### For #382 (DC conductivity against cure schedule)

**Unaffected, and worth saying so.** §5 shows the DC probe is exactly right
below ~1.3 µm and increasingly wrong above it — but #382 is not trying to
produce an RF number. It is producing the DC end of a ratio, and the cure
schedule that maximises it. Nothing here argues against it.

### For the map, #104

Line 156 as it stands on 2026-09-10 **already carries the correction** — it
opens *"The map previously said no measured conductivity, permittivity or
surface impedance for MXene exists anywhere in 8–12 GHz; that is now false as a
blanket claim."* What this document adds to it:

- Rakhmanov et al. 2023 (`10.1063/5.0176575`) is a **third** source line 156
  does not name, and it is the closest one: sheet impedance and conductivity,
  **measured across all of 8.2–12.4 GHz**, on a film rather than a composite.
- Line 156's characterisation of AlHassoon's open question — *"whether that
  figure is one frequency-independent value or the peak of something that
  varies across the sweep needs the paywalled full text"* — is still literally
  true, but the **physical** question behind it is now answered independently:
  sheet impedance shows no frequency dependence across X-band, and the Drude
  fit predicts under 1.5% dispersion.
- Line 78's *"~9× lossier than copper and ~3.8× than silver"* should be
  recomputed to **~7.0× and ~2.9×** if it is to reflect the RF-band figure,
  and should say **printed silver ink** rather than "silver" (§3).
- Line 87's conductor-thickness preference — *"MXene never reaches that regime
  at printable thickness"* — does not survive at σ = 1.2 × 10⁶ S/m, where 3δ is
  13.8 µm and printable thicknesses reach 20–35 µm (§4).

### What nothing here licenses

**None of this makes a printed MXene trace a characterised letter.** ADR-0027
admits a letter to the Element/Coding-Alphabet library only by being printed
and measured, and nothing in three papers about spray-coated films and a wax
composite loosens that. A candidate built on σ = 1.2 × 10⁶ S/m is a candidate
resting on a `LITERATURE-SUPPORTED` value measured on a different form of the
material, and it should say so.
