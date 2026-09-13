# Does an RF-band measured conductivity for MXene exist, and does it move the ~9× loss figure?

**Date:** 2026-09-13
**Ticket:** [#454](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/454) — part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104) (the map). Bears on `docs/RUNNING-LISTS.md` §3 item 33, map line 156/157, [#383](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/383)'s method choice, and — unexpectedly — on **ADR-0044**'s "15× on conductivity" figure.
**Question:** Is AlHassoon et al.'s RF conductivity real and reliable, and what precisely does it change about the standing "~9× lossier than copper" figure and the map's flat "no measured value exists anywhere in 8–12 GHz"?
**Companion document:** `docs/mxene-rf-band-electrical-properties.md` (2026-09-10) answered the map's blanket-absence claim from Rakhmanov et al. 2023. This document answers the narrower question #454 actually asks, and **finds two measurements that document does not carry** — which change its headline number.

---

## Bottom line up front

**Yes, RF-band measured MXene conductivities exist — there are now four of
them, not one — and no, they do not move the ~9× figure to a single new
number. They move it to a range, 4.1× to 7.0× copper, because the four
sources disagree with each other by a factor of about three.**

Two of the four are new to this programme and are the reason the answer is a
range rather than a correction:

| Source | Band measured | Form | σ reported | Against its own DC |
|---|---|---|---|---|
| **AlHassoon et al. 2020**, APL 116(18):184101 | **1–10 GHz** | spray-coated on PET, 1.0–4.3 µm | **1.2 × 10⁶ S/m** | not stated in the abstract |
| **Rakhmanov et al. 2023**, APL 123(20):204105 | **8.2–12.4 GHz** | spray-coated on glass, 4–40 nm | **1.20 × 10⁶ S/m** (AC) | **16% BELOW** DC (1.43 × 10⁶) |
| **Han et al. 2021**, Adv. Mater. 33(1):2003225 — **new** | **1–10 GHz** TL loss; antennas at 10.9 & 16.4 GHz | spray-coated on PET, 1.0–5.5 µm | **3.0 × 10⁶ S/m** | **2× ABOVE** DC (1.5 × 10⁶) |
| **Tajin & Dandekar 2022**, IEEE Access 10:25850 — **new** | **0.9–1.4 GHz** | cast/coated on PET, 0.2–2 µm | **3.5 × 10⁶ S/m** | **2.3–3.5× ABOVE** DC (1.0–1.5 × 10⁶) |

*In plain terms: four different groups have now put MXene in front of a
network analyser at radio frequency and asked how well it conducts. All four
get an answer. They do not get the same answer — the spread is about three to
one — and, worse for anyone wanting one number, they do not even agree on
whether MXene conducts **better** or **worse** at radio frequency than it does
at DC. Three say better. One says slightly worse.*

**What that does to the repo's standing figures**, every number recomputed
here from first principles (§3): `CALCULATED`

| | Standing figure | On the RF measurements |
|---|---|---|
| Map line 78 / `RUNNING-LISTS.md` §3 correction 4 | ~9× lossier than copper | **4.1× – 7.0×** |
| Same | ~3.8× lossier than printed silver ink | **1.7× – 2.9×** |
| Map line 157 (already corrected once) | ~7.0× copper, ~2.9× silver ink | **correct as the pessimistic end only** — it is built on the single lowest of the four σ values |
| Map line 87 | "MXene never reaches [3 skin depths] at printable thickness" | **false at every RF σ.** 3δ at 10 GHz is 13.8 µm at the lowest and **8.1 µm** at the highest, against 10–35 µm printed |
| ADR-0044 | printed silver beats MXene "roughly **15×** on conductivity (10⁷ vs 6.9×10⁵)" | **2.9× – 8.3×** on conductivity; **1.7× – 2.9×** on the loss that matters |

**Four things this settles, and two it does not:**

| | Answer | Where |
|---|---|---|
| Does an RF-band measured MXene conductivity exist? | **Yes, four.** Two of them new to this repo | §1 |
| Is the AlHassoon figure real? | **Yes.** Bibliographically confirmed against two indexes independent of the publisher; abstract recovered verbatim | §2 |
| (c) Is it on an extrusion-printed trace? | **No — spray-coated on PET, 1.0–4.3 µm.** Settled from the abstract. The gap the map's bullet is about stays open | §2.3 |
| Does it move the ~9×? | **Yes, to a range.** 4.1×–7.0× copper | §4 |
| (a) One fitted constant over 1–10 GHz, or a resolved curve? | **Not settled.** The abstract's wording leans to one constant per sample (`INFERRED`); the full text is locked | §2.1 |
| (b) Was the fixture validated near 10 GHz? | **Not settled. `UNKNOWN`** | §2.2 |

**Why (a) and (b) no longer block anything.** They were load-bearing when
AlHassoon was the only RF-band source. It is now one of four, and the two
questions it leaves open — does σ vary across the band, and is the instrument
trustworthy at the top — are both answered independently: Rakhmanov et al.
measured sheet impedance across the *whole* of X-band on a calibrated WR-90
fixture and found it flat (*"Sheet resistance is stable around the entire
X-band frequency range"*), and Han et al. ran a single σ against measured
transmission loss from 1 to 10 GHz and against antennas at 10.9 and 16.4 GHz.
**AlHassoon 2020 has stopped being the hinge.** It is handed over as a
citation (ADR-0035) and logged as stranded (§9).

---

## 1. The four sources, and what kind of number each one is

**None of these is `MEASURED` in this repo's vocabulary.** Per `CONTEXT.md`'s
mapping a `paper` resolves to **`LITERATURE-SUPPORTED`**, and
measured-by-someone-else stays there however good the instrument was —
`docs/mxene-rf-band-electrical-properties.md` §1.1 already settled that
reading and nothing here reopens it. Everything this document computes
*itself* is tagged `CALCULATED`.

A distinction that matters more than the provenance rung, because three of
the four share the same weakness:

> **Three of the four σ values were obtained by turning a knob in a simulator
> until the simulated curve lay on top of the measured one.** Only Rakhmanov
> et al. extracted sheet impedance from the measurement directly.

*In plain terms: a "measured conductivity" is almost never read off a dial. It
is usually the number that, when typed into a computer model of the same test
fixture, makes the model agree with what the instrument saw. That makes the
answer only as good as the model of the fixture — and it means two groups
measuring the same material with different fixtures can honestly report
different conductivities.*

### 1.1 AlHassoon et al. 2020 — the ticket's source, and it is real

> K. AlHassoon, M. Han, Y. Malallah, V. Ananthakrishnan, R. Rakhmanov,
> W. Reil, Y. Gogotsi & A. S. Daryoush, *"Conductivity extraction of thin
> Ti₃C₂Tₓ MXene films over 1–10 GHz using capacitively coupled test-fixture,"*
> **Applied Physics Letters 116(18):184101**, 4 May 2020, doi
> [10.1063/5.0002514](https://doi.org/10.1063/5.0002514).

**The citation, the DOI, the author list, the volume/issue/article number and
the abstract all check out** against two indexes that do not depend on the
publisher's own site — the Semantic Scholar Graph API and OpenAlex, queried
2026-09-13. `LITERATURE-SUPPORTED` The ticket's reading of it is accurate.
Verbatim from the abstract:

> "Thin films of two-dimensional MXene (Ti₃C₂Tₓ) are evaluated in terms of
> their conductivity over the radio frequency (RF) range of 1–10 GHz using a
> custom designed test fixture. A contactless method is developed for
> extracting the conductivity of MXene films of various thickness (1.0–4.3 μm)
> at RF frequencies. Open ended MXene transmission lines with various
> thicknesses are spray-coated on polyethylene terephthalate substrates
> capacitively coupled to a copper transmission line test fixture realized on
> a RT/duroid (filled polytetrafluoroethylene composite laminate) substrate to
> provide solderless repeatable RF connection. The extraction process is based
> on the least squares error method of curve fitting to minimize the
> difference between the full wave numerically simulated scattering parameters
> and the measured values of the test circuit for various samples. RF
> characterization was performed for three MXene samples, with thicknesses of
> about 1.0, 1.5, and 4.3 μm to extract the corresponding conductivity.
> Moreover, MXene performance was compared against copper and graphite films.
> The highest conductivity of 1.2 × 10⁶ S/m was extracted for the 4.3 μm thick
> Ti₃C₂Tₓ film. The extracted MXene conductivity is used to predict the
> quality factor and efficiency of antennas."

### 1.2 Han et al. 2021 — new to this repo, and the most in-band of the three "RF above DC" results

> M. Han, Y. Liu, R. Rakhmanov, C. Israel, M. A. S. Tajin, G. Friedman,
> V. Volman, A. Hoorfar, K. R. Dandekar & Y. Gogotsi, *"Solution-Processed
> Ti₃C₂Tₓ MXene Antennas for Radio-Frequency Communication,"* **Advanced
> Materials 33(1):2003225** (2021), doi
> [10.1002/adma.202003225](https://doi.org/10.1002/adma.202003225). **Full
> text read** from the NIH author manuscript at
> [PMC9119193](https://pmc.ncbi.nlm.nih.gov/articles/PMC9119193/) (retrieved
> via the NCBI eutils API, 2026-09-13; every quotation below is from that
> text, not an abstract).

Ti₃C₂Tₓ **spray-coated** from a 10 mg mL⁻¹ aqueous colloid onto PET, three
thicknesses (1.0, 3.2, 5.5 µm), surface roughness ≈15 nm. 67 mm and 102 mm
microstrip transmission lines, S-parameters on a VNA from 1 to 10 GHz, plus
patch antennas at **5.6, 10.9 and 16.4 GHz** measured for gain and radiation
efficiency in an anechoic chamber and a reverberation chamber.

**The conductivity statement, verbatim:**

> "It can be seen that the simulated α values of copper TL are in agreement
> with the measured values, when the electrical conductivity for simulation is
> 5.8 × 10⁵ S cm⁻¹. However, for MXene TLs, to match the measured α values, we
> applied an electrical conductivity of **3.0 × 10⁴ S cm⁻¹** for simulation,
> which is **two times higher** than the value (≈1.5 × 10⁴ S cm⁻¹) that we
> measured using the four-point probe method. If the conductivity of
> 1.5 × 10⁴ S cm⁻¹ is used, α will turn out to be much higher than the
> experimental results."

3.0 × 10⁴ S cm⁻¹ = **3.0 × 10⁶ S/m**; their DC value 1.5 × 10⁴ S cm⁻¹ =
1.5 × 10⁶ S/m. (Their copper, for the record, is 5.8 × 10⁵ S cm⁻¹ =
**5.8 × 10⁷ S/m** — which matters in §3.)

Their own explanation, verbatim: *"This implies that the in-plane conductivity
of MXene films along the propagation direction is higher than its surface
conductivity … Further investigation is required to fully understand the
interaction between free electrons of MXene in the in-plane direction and EM
waves."*

**Two measured numbers from this paper that are worth more to this programme
than the σ itself**, because they are a direct loss comparison against copper
in band: `LITERATURE-SUPPORTED`

> "the attenuation constant of an MXene TL is only **0.061 dB mm⁻¹ at 10 GHz**
> while that of the copper TL is **0.045 dB mm⁻¹**. Even for a 1.0 μm thick
> MXene TL, the attenuation constant only increases to 0.090 dB mm⁻¹"

and the antenna efficiencies: *"For 5.5 μm thick MXene antennas, the radiation
efficiency reaches 90% at 5.6 GHz, **92% at 10.9 GHz**, and 99% at 16.4 GHz …
Even for 1.0 μm thick MXene antennas, the radiation efficiency reaches 81% at
5.6 GHz, **87% at 10.9 GHz**, and 93% at 16.4 GHz."*

### 1.3 Tajin & Dandekar 2022 — new to this repo, the largest DC-to-RF gap, and below band

> M. A. S. Tajin & K. R. Dandekar, *"Anomalous Radio Frequency Conductivity
> and Sheet Resistance of 2D Ti₃C₂Tₓ MXene,"* **IEEE Access 10:25850–25856**
> (2022), doi
> [10.1109/ACCESS.2022.3154038](https://doi.org/10.1109/ACCESS.2022.3154038),
> CC-BY. **Full text read** from chapter 2.3 of the author's Drexel
> dissertation, *"Reconfigurable Radio Frequency Transceivers for Next
> Generation Internet of Things"* (208 pp., CC BY-SA, Drexel Research
> Discovery `filePid=13493061260004721`, downloaded and text-extracted with
> `pymupdf`, 2026-09-13). The dissertation lists the IEEE Access paper among
> its own publications and the chapter is that paper.

Two-port microstrip lines, 41 mm × 3 mm MXene top layer on PET taped to a
single-sided FR4 board with a copper ground, push-type SMA connectors,
**S-parameters 0.9–1.4 GHz**, the working number taken at **936 MHz**. RLGC
parameters extracted from the measurement-plane-corrected ABCD matrix, sheet
resistance from the per-unit-length R.

**Verbatim:**

> "The extracted RF (936 MHz) sheet resistance values are **0.3 Ω/sq,
> 0.4 Ω/sq, and 2.5 Ω/sq** for the 2 µm, 1 µm, and 0.2 µm thick MXene films,
> respectively."

> "The RF conductivity of MXene is found to be **35,000 S/cm**, which is close
> to the previously found value of 30,000 S/cm [Han et al. 2021]. From
> four-point probe measurements, the DC conductivity of MXene was found to be
> between **10,000 - 15,000 S/cm**. … However, the sheet resistance values of
> the three samples are lower at RF. These results are only possible if MXene
> has increased conductivity at RF."

**And a named mechanism**, which is the part this programme's own open
question was missing. Verbatim:

> "Since the space between the flakes contains no charge carriers (assuming
> vacuum), the only way to continue the current flow is by introducing a
> time-varying electric field. In other words, **only AC/RF currents can
> continue through the intra-layer gap, while DC currents are completely
> blocked** due to their time-invariant nature."

> "When RF current is introduced in one layer, the adjacent layers (physically
> connected and disconnected) participate in carrying the current. As a
> result, **the effective cross-sectional area of the current flow is
> increased and the ohmic losses are reduced.** Due to the time-invariant
> nature of DC, there is no interaction between the two layers."

*In plain terms: MXene is a stack of flakes like a badly shuffled deck of
cards. At DC, current can only travel where two cards physically touch. At
radio frequency it can also jump the gaps — capacitively across a gap in the
same layer, and by induction between layers — so more of the stack carries
current and the material looks better than its DC measurement says. That is
the claim. It is the exact mechanism `docs/mxene-rf-band-electrical-properties.md`
§5 listed as `UNKNOWN` and unquantified; it now has a published measurement
and a stated physical argument behind it, though still not a model that
predicts its size.*

**One skeptical check this paper does not survive cleanly.** `CALCULATED` Its
two routes to σ disagree. Inverting its own stated sheet resistances with
σ = 1/(R_s·t), which is exact here because all three films are far thinner
than the skin depth:

| Film | stated R_s at 936 MHz | implied σ |
|---|---|---|
| 2.0 µm | 0.3 Ω/sq | 1.67 × 10⁶ S/m |
| 1.0 µm | 0.4 Ω/sq | 2.50 × 10⁶ S/m |
| 0.2 µm | 2.5 Ω/sq | 2.00 × 10⁶ S/m |

Mean ≈ **2.1 × 10⁶ S/m**, about **1.7× below** the headline 3.5 × 10⁶ S/m,
which came from the separate conductivity-and-thickness fit against
reflection-corrected S₂₁. So **35,000 S/cm is the upper end of this paper's
own evidence, not its centre**, and a DC-to-RF enhancement of ~1.4–2× is
better supported by it than the 2.3–3.5× the headline implies. Against the
DC range it quotes (1.0–1.5 × 10⁶ S/m), an implied 2.1 × 10⁶ is a 1.4–2.1×
enhancement — which lands on top of Han et al.'s independent "two times
higher."

One thing the paper does get exactly right, and it is a useful check that its
arithmetic is sound: it states the skin depth of a 35,000 S/cm conductor at
936 MHz as 8.79 µm. Recomputing, δ = √(2/(ωµ₀σ)) = **8.79 µm**. `CALCULATED`

### 1.4 Rakhmanov et al. 2023 — already in the repo, and still the only one measured across the whole band

Carried in full in `docs/mxene-rf-band-electrical-properties.md` §1.2 and not
re-derived here. The one-line summary: sheet impedance in a TRL-calibrated
WR-90 fixture across **8.2–12.4 GHz** on 4–40 nm spray-coated films; sheet
resistance 208 → 21 Ω/sq; **AC σ = 1.20 × 10⁶ S/m against DC 1.43 × 10⁶ S/m
on the same films**, the AC value 16% *below* DC, with the authors attributing
the gap to measurement error and surface roughness. It is the only one of the
four whose σ is not a simulator fit, the only one covering the whole of
X-band, and the only one pointing the other way.

---

## 2. Is the AlHassoon figure reliable? (a), (b) and (c)

### 2.1 (a) One constant, or a resolved curve? — `INFERRED`, leaning to one constant per sample

The abstract says *"RF characterization was performed for three MXene samples,
with thicknesses of about 1.0, 1.5, and 4.3 μm to extract **the corresponding
conductivity**"* and *"**The highest** conductivity of 1.2 × 10⁶ S/m was
extracted for the 4.3 μm thick film."* Singular, once per sample, with
"highest" comparing across *thicknesses* rather than across frequency.

**That reads as one fitted constant per sample over the 1–10 GHz sweep, and it
is a reading, not a finding.** `INFERRED` A least-squares fit of simulated to
measured S-parameters *can* be run per frequency point and reported as a
curve; the abstract gives no sign that it was, and the phrase "the
corresponding conductivity" is how a single number per sample is normally
written. The full text is the only way to be sure and it is locked (§9).

**Why this no longer matters much.** The physical question underneath it — does
MXene's conductivity move across X-band? — is answered by Rakhmanov et al.
from a direct in-band measurement: *"Sheet impedance does not exhibit
frequency dependence"* across 8.2–12.4 GHz, with a Drude relaxation time of
~2.3 ps implying under 1.5% dispersion anywhere in the band. Whether
AlHassoon reported one number or eleven, the band is flat.

### 2.2 (b) Was the fixture validated to the top of its range? — `UNKNOWN`

Nothing in the abstract, and nothing in the two indexes' metadata, says what
the fixture was checked against near 10 GHz. One weak piece of evidence
points the right way: *"MXene performance was compared against copper and
graphite films"* — benchmarking the same fixture against a conductor of known
conductivity is exactly what a validation looks like. But the abstract does
not say at which frequencies the copper benchmark was run, and a capacitive
coupling gap behaves very differently at 10 GHz than at 1 GHz. **`UNKNOWN`,
and it stays `UNKNOWN`** — the full text is the only route and it is locked.

A note for whoever reaches the full text later: the same lead author's
**open-access** sibling paper is the place to see how this group validates an
extraction fixture — K. Alhassoon et al., *"Complex Permittivity and
Permeability Extraction of Ferromagnetic Materials for Magnetically Tuned
Microwave Circuits,"* *IEEE J. Microwaves* (2021), doi
[10.1109/JMW.2021.3062415](https://doi.org/10.1109/JMW.2021.3062415), OA at
IEEE. Not fetched here (IEEE Xplore is HTTP 418 from this environment,
`RUNNING-LISTS.md` §1) and **not a substitute** — it is a different fixture
for a different quantity. Recorded as a lead, not as evidence.

### 2.3 (c) The film's form — **settled, and it is the part that matters**

**Spray-coated on PET, 1.0–4.3 µm.** Verbatim from the abstract, quoted in
full in §1.1. It is **not** an extrusion-printed trace.

So the ticket's own framing is confirmed: *"even a clean result narrows the
map's wording rather than closing the gap the bullet is actually about."* And
the same is true of all four sources — spray-coated on PET (AlHassoon, Han,
Tajin) or spray-coated on glass (Rakhmanov). **Nobody has measured the RF
conductivity of an extrusion-printed MXene trace at any frequency.** That gap
is exactly as open after this document as before it, and it is #383's.

---

## 3. Every number recomputed, and one discrepancy found

Two standard good-conductor results, both `CALCULATED`, with
µ₀ = 4π × 10⁻⁷ H/m:

```
    skin depth          δ   = √( 2 / (ω µ₀ σ) )  =  1 / √(π f µ₀ σ)
    surface resistance  R_s = √( π f µ₀ / σ )     =  1 / (σ δ)
```

*In plain terms: at radio frequency the current crowds into a thin skin at the
surface of a conductor instead of using the whole thickness. The skin depth is
how thick that skin is. The surface resistance is what the conductor looks
like electrically once you accept that only that skin carries current, quoted
in ohms per square — the resistance of any square patch of the surface,
whatever size the square.*

Both assume the conductor is thick compared with δ. That assumption is
checked, not assumed, in §4.

**At 8 / 10 / 12 GHz, for every σ in play:** `CALCULATED`

| σ (S/m) | where it comes from | δ @8 | δ @10 | δ @12 | R_s @10 (Ω/sq) | 3δ @10 | 10 µm is … |
|---|---|---|---|---|---|---|---|
| 2.09 × 10⁵ | map's old "3δ ≈ 33 µm", implied | 12.31 | 11.01 | 10.05 | 0.4346 | 33.0 µm | 0.91 δ |
| 6.9 × 10⁵ | repo's as-printed DC figure | 6.774 | 6.059 | 5.531 | 0.2392 | 18.2 µm | 1.65 δ |
| 1.2 × 10⁶ | AlHassoon RF; Rakhmanov AC | 5.137 | **4.594** | 4.194 | 0.1814 | 13.8 µm | **2.18 δ** |
| 1.43 × 10⁶ | Rakhmanov DC 4-point probe | 4.706 | 4.209 | 3.842 | 0.1662 | 12.6 µm | 2.38 δ |
| 1.5 × 10⁶ | Han DC 4-point probe | 4.594 | 4.109 | 3.751 | 0.1622 | 12.3 µm | 2.43 δ |
| 3.0 × 10⁶ | Han RF fit | 3.249 | 2.906 | 2.653 | 0.1147 | **8.7 µm** | 3.44 δ |
| 3.5 × 10⁶ | Tajin RF | 3.008 | 2.690 | 2.456 | 0.1062 | **8.1 µm** | 3.72 δ |

(δ in µm.) Reference conductors at 10 GHz: copper at 5.8 × 10⁷ S/m →
R_s = 0.02609 Ω/sq, δ = 0.661 µm; copper at 5.96 × 10⁷ → 0.02574, 0.652 µm;
bulk silver at 6.3 × 10⁷ → 0.02503, 0.634 µm; printed silver ink at
1 × 10⁷ → 0.06283, 1.592 µm.

**Every `CALCULATED` figure in the ticket reproduces**, with one caveat:

| Ticket's figure | Recomputed | Verdict |
|---|---|---|
| δ = 4.59 µm at 10 GHz for σ = 1.2 × 10⁶ | **4.594 µm** | ✓ |
| 10 µm print = 2.18 skin depths | **2.177** | ✓ |
| correction 7's 1.65 δ implies σ ≈ 6.9 × 10⁵ | **6.895 × 10⁵** | ✓ |
| #111's "3δ ≈ 33 µm" implies σ ≈ 2.1 × 10⁵ | **2.093 × 10⁵** | ✓ |
| 7.25× bulk silver | **7.246×** at σ_Ag = 6.3 × 10⁷ | ✓ |
| **6.95× copper** | **6.95×** at σ_Cu = **5.8 × 10⁷**; **7.05×** at σ_Cu = **5.96 × 10⁷** | **the ticket's own brief names 5.96 × 10⁷ and its number is the 5.8 × 10⁷ one** |

**The copper-constant discrepancy, named rather than smoothed over.** Two
values of copper's conductivity are both standard: **5.8 × 10⁷ S/m** is the
IEC annealed-copper reference, and **5.96 × 10⁷ S/m** is pure copper at 20 °C.
The repo's arithmetic uses 5.8 × 10⁷ throughout (and so, independently, does
Han et al. 2021 for its own copper transmission line), which is the right
choice for comparing against a real fabricated conductor. **It is a 1.4%
difference in the ratio and changes nothing — recorded only so the next person
recomputing 6.95 and getting 7.05 does not go looking for a bug.**

---

## 4. What it does to the ~9×, and why the honest answer is a range

Above roughly three skin depths R_s ∝ 1/√σ, so a conductivity ratio becomes a
loss ratio by taking its square root. `CALCULATED`

| σ (S/m) | vs copper 5.8 × 10⁷ | vs copper 5.96 × 10⁷ | vs bulk silver 6.3 × 10⁷ | vs printed silver ink 1 × 10⁷ |
|---|---|---|---|---|
| 6.9 × 10⁵ (DC, what the map used) | **9.17×** | 9.29× | 9.56× | **3.81×** |
| 1.2 × 10⁶ (AlHassoon / Rakhmanov AC) | **6.95×** | 7.05× | 7.25× | **2.89×** |
| 1.43 × 10⁶ (Rakhmanov DC) | 6.37× | 6.46× | 6.64× | 2.64× |
| 3.0 × 10⁶ (Han RF) | **4.40×** | 4.46× | 4.58× | **1.83×** |
| 3.5 × 10⁶ (Tajin RF) | **4.07×** | 4.13× | 4.24× | **1.69×** |

**The map's 9.17× and 3.81× reproduce exactly on the DC figure, so the
arithmetic was always right and only the input was DC.** Map line 157's
already-corrected 7.0× / 2.9× is also right — but only for the lowest of the
four RF values. **The defensible statement is a range: 4.1× to 7.0× copper,
1.7× to 2.9× printed silver ink.**

*In plain terms: the programme has been assuming MXene wastes about nine times
as much of the signal as copper does. The radio-frequency measurements say
somewhere between four and seven times. Which end depends on which of four
disagreeing papers you believe, and nobody has measured the thing this shop
would actually print.*

**Two caveats, both load-bearing.**

- **A surface-resistance ratio is not a circuit-loss ratio, and the gap is
  large.** Han et al.'s *measured* transmission-line attenuation at 10 GHz is
  0.061 dB/mm for 5.5 µm MXene against 0.045 dB/mm for 35 µm copper — a ratio
  of **1.36×**, not 4.4×. `CALCULATED` from their stated values. The
  difference is that a real microstrip line also loses power in its dielectric
  and to radiation, and those losses are the same for both conductors, so a 4×
  worse conductor does not make a 4× worse line. Their 1.0 µm line, at
  0.090 dB/mm, is **2.0×** copper's. *In plain terms: quadrupling the
  resistance of the metal does not quadruple the loss of the circuit, because
  much of the loss never lived in the metal. Anyone reading "7× lossier" as
  "7× worse antenna" is reading it wrong — the same paper's antennas hit 92%
  radiation efficiency at 10.9 GHz on a 5.5 µm film.*
- **The √σ scaling only holds above about three skin depths**, and at these
  conductivities that means thicker than 8–18 µm (table in §3). Below that the
  film is in the linear regime where R_s = 1/(σt) on both sides and the square
  root disappears. Checking the exact film impedance
  Re[η_c/tanh(γt)] against both limits at 10 GHz: `CALCULATED`

  | σ | t | exact R_s | thick-limit | 1/(σt) | t/δ |
  |---|---|---|---|---|---|
  | 1.2 × 10⁶ | 10 µm | 0.1754 | 0.1814 | 0.0833 | 2.18 |
  | 1.2 × 10⁶ | 20 µm | 0.1814 | 0.1814 | 0.0417 | 4.35 |
  | 3.5 × 10⁶ | 10 µm | 0.1064 | 0.1062 | 0.0286 | 3.72 |
  | 3.5 × 10⁶ | 20 µm | 0.1062 | 0.1062 | 0.0143 | 7.43 |

  At 20 µm the thick-conductor formula is exact to four figures at both
  conductivities. **So the ratios above describe a printed trace correctly,
  provided it is printed at 20 µm or more** — and this also kills map line 87's
  "MXene never reaches that regime at printable thickness" at every RF σ, not
  just the lowest one.

---

## 5. `RUNNING-LISTS.md` §3 item 33 — what this adds

`docs/mxene-rf-band-electrical-properties.md` §4 resolved item 33 by
reconstructing the spurious 11 µm skin depth as a mislabelled multiplier
(a five-skin-depth figure at the bottom of the band divided by three), leaving
both sides on the same σ = 6.9 × 10⁵ S/m. **That reconstruction is `INFERRED`
and this document does not disturb it** — the two implied conductivities
reproduce here to three figures (§3), which is the part that was checkable.

What changes is the conclusion each side's position supports, because the
RF-band values sit **above both** of them rather than between them:

- **Correction 7 is strengthened further than the companion document says.**
  It argued a ~10 µm film is already opaque at 1.65 δ. At σ = 1.2 × 10⁶ that
  is 2.18 δ; at σ = 3.5 × 10⁶ it is **3.72 δ** — past the three-skin-depth
  rule outright. Its conclusion that thickness is a dead knob holds with
  margin at every RF value.
- **The map's opposite position fails harder.** 3δ at 10 GHz is 13.8 µm at the
  lowest RF σ and **8.1 µm** at the highest, against the 20–35 µm
  `docs/mxene-voltera-nova-printability.md` gives for a printed conductor. A
  printed MXene trace reaches the electrically-thick regime comfortably, and
  the thickness knob saturates once it does.
- **Neither touches #128's finding** that for a *lossy* element the aspect
  ratio, not the film thickness, is the knob. Item 33 already said so.

---

## 6. Han et al. ACS Nano 2020 — verifying the ticket's second route

The ticket's weaker route checks out in substance, with one numeric
correction and one thing it gets better than expected.

**The paper is:** M. Han, C. E. Shuck, R. Rakhmanov, D. Parchment, B. Anasori,
C. M. Koo, G. Friedman & Y. Gogotsi, *"Beyond Ti₃C₂Tₓ: MXenes for
Electromagnetic Interference Shielding,"* **ACS Nano 14(4):5008–5016** (2020),
doi [10.1021/acsnano.0c01312](https://doi.org/10.1021/acsnano.0c01312).
Abstract verified via Semantic Scholar; **full text not reachable** (§9).
`LITERATURE-SUPPORTED`

Verbatim from the abstract, the two sentences that matter:

> "The EMI shielding effectiveness of sprayed Ti₃C₂Tₓ film with a thickness of
> only ~40 nm reaches 21 dB."

> "A transfer matrix model was shown to fit EMI shielding data for highly
> conductive MXenes, but **could not describe the behavior of materials with
> low conductivity**."

**The inversion, done here.** For a sheet far thinner than a skin depth, with
free space on both sides, total shielding effectiveness and sheet resistance
are one-to-one: `CALCULATED`

```
    SE(dB) = 20 log₁₀( 1 + η₀ / (2 R_s) )      ⟹     R_s = (η₀/2) / (10^(SE/20) − 1)
```

| Data point | R_s | σ = 1/(R_s t) |
|---|---|---|
| 21 dB at 40 nm (from the abstract) | **18.4 Ω/sq** | **1.36 × 10⁶ S/m** |
| 1.4 dB at ~2 nm (ticket's figure, `UNVERIFIED`) | 1077 Ω/sq | 4.64 × 10⁵ S/m |

**Two findings.**

1. **The ticket's claim that "in the regime where it is well conditioned the
   answer equals the DC value" is confirmed, and it is a stronger
   cross-check than the ticket claims.** The 40 nm point inverts to
   **1.36 × 10⁶ S/m** — between Rakhmanov et al.'s AC 1.20 × 10⁶ and DC
   1.43 × 10⁶ on comparable films. Two different laboratories' measurements,
   one a shielding number and the other a waveguide sheet impedance, agree on
   MXene's conductivity to within ±13%. `CALCULATED`
2. **The thin-end breakdown is real in direction but my multiplier is 2.9×,
   not the ticket's 3.7×.** The ticket's 2 nm / 1.4 dB pair is not in the
   abstract and I could not open the figure it comes from, so **either the
   data pair or the inversion convention differs** — a substrate-backed
   inversion, or SE_total versus SE_A, would shift it. The qualitative point
   stands: a film at the thin end of that series inverts to a conductivity
   roughly three times lower than the 40 nm point, which is the signature of
   percolation or a nominal rather than measured thickness, and is consistent
   with the paper's own admission that its transfer-matrix model "could not
   describe the behavior of materials with low conductivity." **The ticket's
   3.7× should be carried as `UNVERIFIED` or replaced with ~2.9×
   `CALCULATED` from the stated pair.**

And the ticket's conclusion survives intact: **this route teaches nothing
about the DC-versus-RF question**, because in the regime where it is
well-conditioned it returns the DC value, and in the regime where it would be
interesting it is broken.

---

## 7. What the map should say

**Line 157 as it stands is already corrected and is not wrong.** What it is,
is *under*-corrected in one direction and *over*-confident in another:

- It names three sources. **There are five relevant ones.** Han et al. 2021
  (`10.1002/adma.202003225`) and Tajin & Dandekar 2022
  (`10.1109/ACCESS.2022.3154038`) are missing, and both are full-text
  readable, which the two it leans on hardest are not.
- It replaces "~9×" with a **single** number, ~7.0×. That number is the
  lowest-σ corner of a four-way disagreement. **A range, 4.1×–7.0×, is what
  the evidence supports.**
- Its strongest claim — *"the AC/DC agreement endorses the same mechanism of
  charge carrier transport occurring at DC to microwave range"*, inherited
  from Rakhmanov — is **contradicted by two independent sources**, each of
  which reports RF conductivity roughly twice DC and one of which offers a
  physical mechanism for it. That disagreement is the single most
  decision-relevant thing in this document and it is not on the map.
- Its conclusion that **nothing is measured on an extrusion-printed trace
  stands, unchanged, across all five sources.** That is the gap. It is #383's.

**Say the direction plainly, as the ticket asks.** This is good news for MXene
twice over: every RF-band measurement puts its conductivity at or above the DC
figure the repo has been carrying, and three of the four put it well above.
Per **ADR-0044** that is a scoring input and not a reason to lean — and the
same ADR's own "**15×** on conductivity" advantage for printed silver
(10⁷ vs 6.9 × 10⁵ S/m) recomputes to **2.9×–8.3×** on conductivity and
**1.7×–2.9×** on surface resistance. `CALCULATED` That does not reverse
ADR-0044's decision, which rests on cure temperature rather than on
conductivity, but the margin it quotes in passing is between two and five
times smaller than stated.

---

## 8. For #383 — the WR-90 route, and three things about `transmissive_absorber.py`

The ticket proposes adding, as an alternative to #383's microstrip ring
resonator, *"a WR-90 two-port measurement on a NOVA-printed coupon of
profilometer-measured thickness, inverted with
`rf_tools/transmissive_absorber.py`."* **The measurement is a good idea and
now has two independent precedents** — Rakhmanov et al.'s WR-90 sheet
impedance and Han et al. ACS Nano's shielding series, both inverted the same
way. **The software half of the proposal needs three corrections**, found by
reading the module (`rf_tools/transmissive_absorber.py`, read 2026-09-13):

1. **The module is a forward model only. There is no inverse.** `stack_response`
   and `transmissive_absorptivity` take a sheet resistance and return R, T, A.
   Nothing in the module solves for R_s from a measured S₂₁. Inverting needs
   either a root-find wrapped around `stack_response`, or the closed form in
   §6 for the thin-sheet case. Small job; not zero.
2. **Its source-side port impedance is hardcoded to free space.**
   `stack_response` calls `s_parameters(cascade(*layers), ETA0_OHM, load)` —
   η₀ = 376.73 Ω. `s_parameters` itself accepts any port impedance, so the
   capability is there one level down, but the public entry point does not
   expose it. **A WR-90 TE₁₀ mode is not 376.73 Ω.** Its cutoff is
   c/(2 × 22.86 mm) = **6.557 GHz**, so its wave impedance is 627.4 Ω at
   8.2 GHz, 499.0 Ω at 10.0 GHz and 443.9 Ω at 12.4 GHz. `CALCULATED`
   Using η₀ where the waveguide impedance belongs **understates the extracted
   sheet resistance by 1.18× to 1.67× across the band** — 1.30× at band
   centre. *In plain terms: a waveguide squeezes the wave, so the wave pushes
   back harder than it does in open air. Use the open-air number and the
   coupon looks like a better conductor than it is, by up to two-thirds.*
   Rakhmanov et al. get this right and say so: their matched-absorption
   impedance is *"~250 Ω"* in WR-90 against *"188 Ω"* in free space, which
   recomputes to 244.3 Ω and 188.4 Ω. `CALCULATED`
3. **A printed trace will not transmit enough to invert.** At σ = 1.2 × 10⁶
   and 20 µm, R_s = 0.042 Ω/sq — **4,500× below** the 188 Ω/sq a half-power
   sheet needs; at σ = 3.5 × 10⁶ and 35 µm it is 0.008 Ω/sq, **23,000×
   below**. `CALCULATED` S₂₁ is then indistinguishable from zero and the
   extraction is ill-conditioned, which is precisely why every source here
   measured a deliberately thin film. **So the coupon has to be printed
   thin on purpose** — one or two passes, not the working thickness — and σ
   then has to be carried across to the working trace, importing exactly the
   extrapolation this document keeps flagging. It also needs the coupon cut to
   the WR-90 aperture (22.86 × 10.16 mm) and a profilometer thickness on the
   *same* coupon, since σ = 1/(R_s·t).

**The cheapest honest version of #383, stated as an option and not a
decision:** print one coupon thin enough to transmit and one at working
thickness; four-point-probe both (that is #382's instrument, already
scheduled); WR-90 the thin one for σ at RF; and report the DC-to-RF ratio.
Four published comparison points now exist for that ratio — **0.84× (Rakhmanov),
~1.4–2.1× (Tajin's own sheet resistances), 2× (Han 2021), 2.3–3.5× (Tajin's
headline)** — and a printed trace landing outside all of them is the
interesting result, not the failure.

---

## 9. Every route tried

This section separates claims about the world from claims about us.

**Succeeded:**

| Route | Result |
|---|---|
| Semantic Scholar Graph API, DOI `10.1063/5.0002514` | Full abstract, author list, date, volume/issue/article number — **independent of the publisher's site**. This is what confirms the AlHassoon citation is real |
| OpenAlex, same DOI | Title and OA status confirmed independently; `is_oa: false`, `oa_status: "closed"`, `any_repository_has_fulltext: false`, **zero** OA locations. Queried 2026-09-13 |
| **OpenAlex citing-works query** (`filter=cites:W3021169493`) | **The single most productive route of the session.** Twelve citing papers, five open access — this is how Tajin & Dandekar 2022 was found |
| DOAJ article API | Full abstract of Tajin & Dandekar 2022, including the 35,000 S/cm and 10,000–15,000 S/cm figures, without touching IEEE |
| **Drexel Research Discovery**, `pdfCoverPage?filePid=13493061260004721` | **Tajin's 208-page dissertation, unencrypted, 26 MB, extracted cleanly with `pymupdf`.** Chapter 2.3 is the IEEE Access paper in full. A dissertation is the reliable free route to a paywalled chapter from a US university, and it worked first try |
| **NCBI eutils**, `efetch.fcgi?db=pmc&id=9119193` | **Full text of Han et al. 2021** as JATS XML. Note: `curl` on `pmc.ncbi.nlm.nih.gov` itself returns a reCAPTCHA page; **the eutils API does not and is the route to reach for** |
| Semantic Scholar author-papers endpoint | Located AlHassoon's OA sibling paper (§2.2) and confirmed he has no other MXene RF publication |
| Drexel Nanomaterials Institute 2020 publication list | Confirmed `722.pdf` is the AlHassoon paper and that it is the only free copy the institute hosts |

**Failed, and precisely how far each got:**

| Route | Outcome |
|---|---|
| **AlHassoon 2020 full text — Drexel PDF** `nano.materials.drexel.edu/wp-content/papercite-data/pdf/722.pdf` | **Downloads fine (HTTP 200, 1,453,489 bytes, valid 6-page PDF) and is cryptographically locked.** Its encryption dictionary is `/Filter /Standard /V 5 /R 5 /CFM /AESV3 /Length 256`. **Verified here directly rather than by trusting a tool's refusal:** for `/R 5`, a valid user password `pw` satisfies `SHA-256(pw ‖ U[32:40]) == U[:32]`. For the empty password that comparison **fails**, and so does the owner-password equivalent. So the user password is genuinely non-empty — **this is a fact about the file, not a tool problem.** Confirms the prior session's finding by an independent method |
| **Han et al. ACS Nano 2020 full text — Drexel PDF** `…/pdf/668.pdf` | Same story, different cipher: HTTP 200, 3,622,501 bytes, `/V 4 /R 4`, `needs_pass 1`. **The two files use different encryption revisions, which means the DRM comes from each publisher's own file rather than from the Drexel host** — so "find another Drexel-hosted copy" is not a route |
| **AlHassoon 2020 — Unpaywall / OSTI / NSF PAR / Drexel institutional repository** | All four reported no open copy in the prior session (`docs/mxene-rf-band-electrical-properties.md` §7); OpenAlex independently agrees today. **Four indexes now concur that no free, readable copy exists.** A claim about the world |
| **AlHassoon 2020 — a Drexel dissertation**, the route that worked for Tajin | **No dissertation found.** Two targeted searches returned only his journal papers. He is now at Qassim University; whether his Drexel thesis exists in Research Discovery could not be established, because the repository's search endpoint returns HTTP 302 to a JavaScript application and `idea.library.drexel.edu` reset the connection. **Worth one more try by a human with a browser** — it is the highest-probability remaining route to (a) and (b) |
| **IEEE Xplore**, both the Tajin PDF (`ielx7/…/09720913.pdf`) and the document page | **HTTP 418** on the PDF via `curl`; the document page returned empty content via `WebFetch`. Matches the standing pattern in `RUNNING-LISTS.md` §1. **Irrelevant in the end** — the dissertation route got the same text |
| **ResearchGate** | Not attempted; standing 403 pattern |
| **`scholar.archive.org`, CORE API** | Both rate-limited (HTTP 429 / "rate limit reached") on first contact. Not retried — the citing-works route had already succeeded |
| **`mdtajin.com`** (author's own site, which search results said lists publications) | **DNS does not resolve** from this environment, and the proxy rejected the CONNECT. A claim about us |
| **AIP publisher pages** | Not attempted; 403 on both DOIs in the prior session |

**For `RUNNING-LISTS.md` §1, amending the existing AlHassoon entry:**

> **AlHassoon et al. (2020)** — the existing entry stands, with three
> additions: (i) the AES-256 lock on the Drexel copy is now **verified
> cryptographically** (empty user password fails the `/R 5` SHA-256 check),
> not merely inferred from three tools refusing it; (ii) **OpenAlex is a
> fourth index** agreeing no open copy exists; (iii) **its importance is
> downgraded again** — it is now one of four RF-band measurements, and the two
> questions its full text would settle are answered independently by
> Rakhmanov et al. (band flatness) and Han et al. 2021 (a single σ validated
> against 1–10 GHz loss data). **The one route not yet exhausted is a Drexel
> dissertation by AlHassoon**, which would contain the chapter in full if it
> exists; the repository's search needs a browser.

> **Han et al., ACS Nano 14(4):5008–5016 (2020)**, doi
> `10.1021/acsnano.0c01312` — **new entry.** Abstract readable; full text and
> figures not. The Drexel-hosted copy (`…/pdf/668.pdf`) is `/R 4`
> password-encrypted. Needed to verify the thin-end (~2 nm, 1.4 dB) data point
> of its X-band shielding series, which is the only part of #454's second
> route that could not be checked. Bears on #454, #383.

---

## 10. Register updates

**Opens / changes, for whoever maintains the map and the lists:**

1. `RUNNING-LISTS.md` §3 item 33 — **mark resolved**, with the §5 addition
   that the RF values strengthen correction 7 beyond what the companion
   document states.
2. Map #104 line 78 and `RUNNING-LISTS.md` §3 correction 4 — **~9× / ~3.8×
   becomes a range, 4.1×–7.0× copper and 1.7×–2.9× printed silver ink.**
3. Map #104 line 157 — **add the two missing sources and convert the single
   7.0× to the range.** Its inherited claim that AC and DC agree is contested
   by two sources; say so.
4. Map #104 line 87 — **"MXene never reaches [3 skin depths] at printable
   thickness" is false at every RF conductivity.**
5. **ADR-0044's in-passing "15× on conductivity"** is 2.9×–8.3× on the RF
   values. Flagged, not edited — the ADR's decision does not rest on it.
6. **#383** — add the WR-90 two-port alternative, with §8's three software
   caveats attached, because the ticket's "inverted with
   `rf_tools/transmissive_absorber.py`" is not yet true as written.

**What nothing here licenses.** Per **ADR-0035** this is a citation handed to
a human and **no library entry is written** — not by this document and not by
anything it recommends. Per **ADR-0027** none of it makes a printed MXene
trace a characterised letter. A candidate resting on any σ in §3's table is
resting on a `LITERATURE-SUPPORTED` value measured on a **spray-coated film,
never an extrusion-printed trace**, and it should say so.

**Closes:** #454. Both of its questions are answered — an RF-band measured
conductivity exists (four of them, two new to this repo), and it moves the ~9×
figure to a range of 4.1×–7.0×. Of its three "what would settle it" items,
**(c) is settled** from the primary abstract, **(a) is `INFERRED`** from the
abstract's wording, and **(b) stays `UNKNOWN`** behind a cryptographically
locked file — and neither (a) nor (b) is load-bearing any more, because
AlHassoon et al. 2020 is no longer the only RF-band source. The claim being
made is about the world for the absence of a printed-trace measurement, and
about us for the two locked PDFs; §9 says which is which, line by line.
