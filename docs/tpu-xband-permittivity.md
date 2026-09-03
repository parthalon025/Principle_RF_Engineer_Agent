# TPU at X-Band: Relative Permittivity and Loss Tangent

**Research date:** 2026-09-03
**Serves:** #127 (what the loop does with a substrate that has no permittivity data)
**Supersedes the "no data" finding in:** #114 (closed) — see §10
**Scope:** Thermoplastic polyurethane (TPU) — relative permittivity (εr) and loss tangent (tanδ) at X-band (8–12 GHz), for use as a printed-metamaterial-skin substrate on the Voltera NOVA vacuum table.

---

## Bottom line up front

**TPU X-band data exists. It was found. #114's conclusion — "no X-band electrical data of *any* provenance" — is now wrong, and the reason it was reached is that the previous pass was locked out of MDPI by HTTP 403 and had no PDF text extractor.** Both blocks were routed around this time: MDPI content was reached through its PubMed Central mirror, and `pymupdf` (present in this environment) extracted text and figures from PDFs that defeated the earlier attempt.

The headline number, for solid (fully dense) 3D-printed **ester-based TPU**, measured in a **WR-90 X-band waveguide**:

| Quantity | 8.2 GHz | 10 GHz | 12.4 GHz | Provenance |
|---|---|---|---|---|
| ε′ (relative permittivity) | ≈ 2.75 | ≈ 2.71 | ≈ 2.68 | `MEASURED` (`LITERATURE-SUPPORTED` as it reaches us) |
| ε″ (imaginary permittivity) | ≈ 0.29 | ≈ 0.27 | ≈ 0.23 | `MEASURED` (`LITERATURE-SUPPORTED`) |
| tanδ = ε″/ε′ | ≈ 0.105 | ≈ 0.099 | ≈ 0.084 | `CALCULATED` from the two rows above |

Source: **Vong, Chevalier, Maalouf, Ville, Rosnarho & Laur, *Materials* 15(9):3320 (2022), DOI [10.3390/ma15093320](https://doi.org/10.3390/ma15093320)**, Figure 9a. Open access; read via [PMC9099990](https://pmc.ncbi.nlm.nih.gov/articles/PMC9099990/).

**In plain terms.** Radio waves passing through this TPU travel about 1.65× more slowly than through air (that is what εr ≈ 2.7 means — the wave slows by √2.7), and roughly **10% of the wave's energy is converted to heat per radian of phase it advances** (that is what tanδ ≈ 0.10 means). The second number is the one that matters here.

**The consequence for the programme is the opposite of what #114 assumed.** #114 framed the central tension as "going flexible weakens absorption and needs compensating." TPU at X-band has a loss tangent of **≈ 0.099 at 10 GHz against FR4's 0.017 — about 5.8× lossier than the patent's own rigid substrate**, and essentially level with the 60 Shore A silicone sheet (tanδ 0.10) that #114 identified as its headline deliberately-lossy find. TPU is not a low-loss substrate that costs the design dissipation. **TPU is a lossy substrate, in the same class as silicone, and it is the one the NOVA already holds on its vacuum table.** It should enter the ranking as a scored candidate, not as an unmodellable exclusion.

**One important caveat that does not go away:** TPU is a *family*, not a material (§5). The X-band number above is for one unnamed commercial ester-based grade of low Shore hardness. Manufacturer data at 1 MHz spans εr 4.0–7.5 and tanδ 0.040–0.140 across grades — a spread of nearly 2× in εr and 3.5× in tanδ *within the same product line*. A single X-band figure for "TPU" should be treated as an order-of-magnitude-correct placeholder for the family, not as a characterisation of whatever spool is actually loaded.

---

## 1. The X-band measurement in detail

**Vong et al., *Materials* 15(9):3320 (2022)** built a flexible 3D-printed multilayer radar absorber for X and Ku bands. To do it they had to characterise their own filaments, and one of the two was **unfilled TPU** — which is exactly the number this repo needs, sitting in a paper about something else. This is why it was missed: nothing in the title, abstract or keywords says "TPU permittivity."

**Material.** "Composite filaments with high magnetic losses were prepared from a commercial **ester-based thermoplastic polyurethane** matrix selected because of its **low shore hardness** and its melt temperature close to 160 °C." The *un*filled version of this same matrix is what the paper calls the "lossless filament." No brand or grade is named, and no Shore number is given — only "low."

**Sample form.** 3D printed as a **fully dense** plate (printed at 230 °C, 10 mm/s), then "cut into rectangular samples to fit the dimensions of standard rectangular waveguides in C to Ku frequency bands, especially **WR187, WR137, WR90, and WR62**." WR-90 *is* the X-band waveguide (8.2–12.4 GHz), so X-band is directly measured, not extrapolated into.

**Method.** Transmission/reflection in the loaded waveguide on an **Agilent/Keysight N5245A PNA-X**, with S-parameters inverted by the **NRW-NIST iterative method** to give both permittivity and permeability. (Plain English: they put a slab of the material inside a metal pipe, measured how much of the radio wave bounced back and how much got through, and solved backwards for the material constants. The "NIST iterative" variant is used because the plain Nicolson-Ross-Weir inversion goes unstable at certain thicknesses.)

**Reported values.** The running text gives only the coarse statement: *"The lossless filament has a permittivity between 2.5 and 3 that slightly decreases with increasing frequency (Figure 9a)."* The per-frequency numbers exist **only as a plotted figure**, so the table in the Bottom Line was obtained by **digitising Figure 9a** — locating the plotted marker centres in the published image and mapping them against the axis gridlines.

**Uncertainty — three separate contributions, do not conflate them:**

1. **The authors' own printing repeatability**, stated explicitly: *"In the case of the non-loaded filament, the tolerances of the permittivity are **±0.3 for the real part and ±0.02 for the imaginary part**."* On ε′ ≈ 2.7 that is **±11%**; on ε″ ≈ 0.27 it is **±7.4%**. This is the dominant term, and it is a real physical spread — reprint the same filament and you get a different number, because print density varies.
2. **Digitisation error** from reading a plotted figure: roughly ±0.03 on ε′ and ±0.01 on ε″ at the published image resolution. Small next to (1).
3. **Measurement error** of the waveguide method itself: not stated by the authors.

So the honest statement is **εr = 2.7 ± 0.3 and tanδ = 0.10 ± 0.01 across X-band** — and the ± is mostly manufacturing spread, not instrument noise.

**Frequency trend across the band.** Both ε′ and ε″ fall gently and monotonically with frequency (ε′ 2.75 → 2.68, ε″ 0.29 → 0.23 across 8.2 → 12.4 GHz). Digitised over the paper's full 4–18 GHz sweep:

| f (GHz) | ε′ | ε″ | tanδ |
|---|---|---|---|
| 5.1 | 2.85 | 0.37 | 0.129 |
| 7.3 | 2.78 | 0.32 | 0.114 |
| **8.1** | **2.76** | **0.29** | **0.105** |
| **9.0** | **2.74** | **0.27** | **0.099** |
| **9.9** | **2.71** | **0.27** | **0.098** |
| **10.7** | **2.70** | **0.25** | **0.091** |
| **11.6** | **2.69** | **0.24** | **0.091** |
| **12.4** | **2.68** | **0.23** | **0.084** |
| 14.1 | 2.66 | 0.22 | 0.081 |
| 18.0 | 2.61 | 0.20 | 0.076 |

(X-band rows in bold. ε′ and ε″ are `MEASURED` by the authors and read off their figure; tanδ is `CALCULATED` as ε″/ε′.)

**A naming trap worth flagging.** The paper calls this the **"lossless filament."** It is not lossless. In that paper "lossless" means "carries no *magnetic* absorber filler" — it is the low-permittivity impedance-matching layer of a two-material absorber stack, contrasted against a carbonyl-iron-loaded filament with a *magnetic* loss tangent of 0.5–1. A dielectric tanδ of 0.10 is, by ordinary microwave-substrate standards, very lossy indeed. **Anyone skimming this paper for a low-loss flexible substrate would read the word "lossless" and record exactly the wrong conclusion.**

---

## 2. Corroboration at 2.4 GHz — NinjaFlex

The X-band figure does not stand alone. An independent group measured a *named, purchasable* TPU by a completely different method at a lower frequency, and the two are consistent.

**Moscato, Bahr, Le, Pasian, Bozzi, Perregrini & Tentzeris**, *IEEE Antennas and Wireless Propagation Letters* **15**, 1506–1509 (2016), "Infill Dependent 3D-Printed Material Based on NinjaFlex Filament for Antenna Applications," DOI [10.1109/LAWP.2016.2516101](https://doi.org/10.1109/LAWP.2016.2516101). IEEE Xplore returns 403; the **author post-print is open** in the University of Pavia repository, [IRIS handle 11571/1119842](https://iris.unipv.it/handle/11571/1119842). A companion conference paper (Bahr et al., *45th European Microwave Conference*, Paris, 2015, pp. 742–745) is openly hosted by Georgia Tech at [tentzeris.ece.gatech.edu/EUMW15_Bahr.pdf](https://tentzeris.ece.gatech.edu/EUMW15_Bahr.pdf) and carries the same data as Fig. 7.

**Material.** NinjaFlex, which the manufacturer's own datasheet states is *"made from a specially formulated **thermoplastic polyurethane (TPU)** material"*, **85 Shore A**, specific gravity 1.19 ([NinjaTek NinjaFlex TDS](https://ninjatek.com/wp-content/uploads/NinjaFlex-TDS.pdf)). Note the 2015 conference paper loosely calls it a "thermoplastic elastomer (TPE)"; the manufacturer datasheet is the authority and says TPU.

**Method.** Microstrip **ring resonator**, first resonance at **2.4 GHz**, 1.2 mm substrate, Anritsu 37347C VNA. Permittivity from the resonant frequency, loss tangent from the resonator Q.

**Values** (`MEASURED`, `LITERATURE-SUPPORTED`; read from Fig. 7 / Fig. 3b, and the 100% figures are confirmed in the running text):

| Infill | εr @ 2.4 GHz | tanδ @ 2.4 GHz |
|---|---|---|
| 100% (solid) | **3.00** | **0.060** |
| 70% | 2.75 | ≈ 0.040 |
| 40% | 2.33 | ≈ 0.042 |

The 100% pair is stated verbatim in the AWPL text: *"The thickness of the substrate is 1.2 mm, the dielectric permittivity is 3.0 and the loss tangent 0.06."*

**Consistency check with §1.** Solid TPU reads εr 3.00 at 2.4 GHz and 2.71 at 10 GHz — a gentle downward slope with frequency, exactly what §1's trend shows continuing. tanδ reads 0.060 at 2.4 GHz and ≈0.099 at 10 GHz — rising with frequency, which is the normal behaviour for a polar polymer in this range and matches Covestro's own statement that "dielectric loss increases with a higher measuring frequency" (§6). **Two labs, two materials, two methods, two frequencies, one coherent picture: TPU is a mid-permittivity, distinctly lossy dielectric, and it gets lossier as you go up in frequency.**

**Two caveats on the NinjaFlex numbers.** (a) The authors state the characterisation "exploits not only the dielectric substrate but also considers the **thin film of glue** that is required to manufacture copper clad NinjaFlex" — a 25 µm copper foil was bonded with epoxy, so the extracted tanδ includes the epoxy layer and is therefore an *upper* bound on the TPU alone. (b) Even "100% infill" FDM printing leaves some void; the true bulk-TPU εr is likely a little above 3.0.

---

## 3. Do not use the porous / foamed TPU numbers

Three recent papers report X-band permittivity for something called "TPU" with values between 1.5 and 2.4. **All three are foams, and none of them characterise solid TPU.** Recording them as TPU's permittivity would understate εr by ~30% and understate loss badly. They are listed here so the next reader does not repeat the mistake.

| Source | Reported | Frequency | Why it is not solid TPU |
|---|---|---|---|
| Li, Xu, Wen & Wang, *Molecules* **30**(17):3610 (2025), DOI [10.3390/molecules30173610](https://doi.org/10.3390/molecules30173610) ([PMC12430016](https://pmc.ncbi.nlm.nih.gov/articles/PMC12430016/)) | ε′ ≈ **1.9**, ε″ ≈ **0.16** | 2–18 GHz, coaxial line, Agilent E5071C | Sample is **TPU foam** made by vapour-induced phase separation, mean pore size 39.69 µm. The paper's own words: *"TPU foam demonstrates almost no electromagnetic absorption... electromagnetically transparent."* Grade: Wanhua 75A. |
| Kaftelen Odabaşı et al., *Polymers* **18**(1):19, DOI [10.3390/polym18010019](https://doi.org/10.3390/polym18010019) ([PMC12787563](https://pmc.ncbi.nlm.nih.gov/articles/PMC12787563/)) | ε ≈ **1.5–2.4** | X-band, VNA + NRW | Porous TPU (`p-TPU`) via VIPS + lyophilisation. Loss tangent for the neat porous TPU is not reported. |
| Vong et al. 2022 (§1), Figure 9e | ε′ **1.85 → 1.78**, ε″ **0.15 → 0.10** | 4–18 GHz, WR90 etc. | The *same* filament as §1, deliberately printed with a "Grid" infill pattern (1.8 mm holes, 1 mm walls). The paper states the air inclusion drops ε′ *"from around 2.8 to 1.8."* |

**Plain reading:** foaming a polymer mixes air into it, and air has εr = 1. So a foam always measures lower than the solid it is made from, and the number you get describes the *foam's* air fraction as much as the polymer. Vong et al. is the clean demonstration because the same lab measured both forms of the same material: **2.8 solid → 1.8 foamed.**

A related trap: the substrate infill of a 3D print is the same effect. **§2's 40% infill NinjaFlex reads εr 2.33 — that is not TPU, it is TPU-and-air.** If the loop ever models a printed TPU substrate it must know the print's infill density, because εr is tunable across roughly 2.3–3.0 by that parameter alone.

---

## 4. What was found near-band but is not usable as X-band

| Source | Value | Frequency | Why it does not answer the question |
|---|---|---|---|
| Singh et al., *Nat. Acad. Sci. Letters* (2024), DOI [10.1007/s40009-024-01513-1](https://doi.org/10.1007/s40009-024-01513-1); open post-print at [NTU IRep 52667](https://irep.ntu.ac.uk/id/eprint/52667/) | εr **1.74–2.07**, tanδ **0.0047–0.0049** under 0–25 N load, ring resonator, 0.65 mm substrate | Not stated; the companion antenna is designed at 2.45 GHz | The specimen is **3D-printed TPU on a cotton/lycra woven fabric at 60% infill** — a TPU-fabric-air laminate, not TPU. The very low tanδ is inconsistent with every solid-TPU measurement here and is best read as a property of that laminate. |
| Mukai, Li & Suh, *Fashion and Textiles* **8**:24 (2021), DOI [10.1186/s40691-021-00248-7](https://doi.org/10.1186/s40691-021-00248-7) | ε′r **2.36 / 2.06 / 1.59** and ε′i **0.23** at 100 / 70 / 40% infill (→ tanδ ≈ 0.097 at 100%) | **Not stated in the paper.** The associated antenna is designed for 2.45 GHz | Resonant-cavity method, NinjaTek 85A TPU. Genuinely useful and its tanδ ≈ 0.097 at 100% infill agrees strikingly with §1's X-band value — but **the paper never states the measurement frequency**, so it cannot be placed on the frequency axis and cannot be cited as an X-band figure. `MEASURED` but at `UNKNOWN` frequency. |
| Bhattacharya et al., *eXPRESS Polymer Letters* (open access, [EPL-0003931](https://www.expresspolymlett.com/article.php?a=EPL-0003931)) | ε′ 14.x and up for filled composites | X-band, WR-90 | TPU matrix (Lubrizol Thermedics) but **every** specimen is filled with MWCNT/TiO₂/Fe₃O₄. **No neat-TPU baseline is reported.** A recurring pattern — see §9. |
| He et al., *Materials* **13**(15):3341 (2020), DOI [10.3390/ma13153341](https://doi.org/10.3390/ma13153341) | pure TPU **ε = 3.6** | 10³ Hz (1 kHz), Agilent 4294A impedance analyser, 40 Hz–10⁷ Hz | Low-frequency dielectric spectroscopy. Useful only as the low-frequency anchor of the dispersion curve (§6). |

---

## 5. TPU is a family, not a material — how much does grade matter?

This is the part of #127's question that the single X-band number does **not** settle, and it is why a single figure for "TPU" arguably should not exist.

### 5.1 Polyester vs polyether backbone

TPU is built from a hard segment plus a soft segment, and the soft segment is either a **polyester** or a **polyether** polyol. This changes the electrical answer.

- **Covestro** (Desmopan/Texin), [Electrical properties](https://solutions.covestro.com/en/highlights/articles/theme/product-technology/electrical-properties-tpu): *"**Polyether grades generally have slightly higher dielectric constants than polyester grades**"*, while for loss *"no significant differences"* between the two. `MANUFACTURER-SPECIFIED`.
- **BASF Elastollan** ([product-range brochure](https://download.basf.com/p1/8a8082587fd4b608017ff4e900830157/en/Elastollan), pp. 28–31) publishes per-grade values at **1 MHz**, IEC 60250, which show the same direction and let the split be quantified. `MANUFACTURER-SPECIFIED`:

| Grade | Chemistry | Shore | εr @ 1 MHz | tanδ @ 1 MHz |
|---|---|---|---|---|
| C 78 A 10 | polyester | 80 A | 6.0 | 0.070 |
| C 85 A 10 | polyester | 87 A | 6.0 | 0.070 |
| C 59 D 53 | polyester | 57 D | 5.0 | 0.060 |
| 1175 A 10 W | polyether | 75 A | 6.5 | **0.140** |
| 1185 A 10 FHF | polyether | 89 A | 5.5 | 0.096 |
| 1185 A 10 HFFR | polyether | 86 A | 6.2 | 0.111 |
| 1195 A 10 / A 15 | polyether | 95 A | 7.5 | not published |
| 1154 D 10 | polyether | 53 D | 4.5 | 0.060 |
| 1154 D 10 FHF | polyether | 58 D | 4.5 | 0.064 |
| 1174 D 11 | polyether | 75 D | 4.0 | 0.040 |

(BASF publishes the loss column as "Dielectric factor at 1 MHz" in units of 10⁻⁴; 700 × 10⁻⁴ = 0.070. Column-to-grade alignment was verified by rendering the datasheet pages as images, because flat text extraction from that PDF loses the table geometry.)

**Reading it:** at 1 MHz, εr spans **4.0 to 7.5** and tanδ spans **0.040 to 0.140** *inside one manufacturer's unfilled TPU range*. That is a ~1.9× spread in εr and a **3.5× spread in tanδ**. Polyether grades do trend higher in εr, and in this table also higher in 1 MHz loss than Covestro's "no significant difference" suggests.

### 5.2 Shore hardness

A clear and consistent trend, and the more useful predictor of the two:

- **Covestro**: dielectric constant ranges **8.0 down to 4.0**, *"values decrease with increasing material hardness"*; loss factor **0.10 down to 0.03**, *"inversely proportional — higher in softer grades."* `MANUFACTURER-SPECIFIED`.
- **BASF**, from the table above: the soft A-grades (75–95 Shore A) sit at εr 5.5–7.5; the hard D-grades (53–75 Shore D) sit at εr 4.0–4.5, with tanδ falling to 0.040 at 75 D.

**Why, in plain terms.** The soft segment is the mobile, rubbery part of the chain. Its polar groups can rotate to follow an applied field, and that rotation is both what raises the dielectric constant and what dissipates energy as heat. A softer grade has more soft segment, so it stores more and loses more. **Softer TPU is lossier TPU.** For an absorber that is a feature, not a defect — and conveniently, the softest grades are also the most conformal.

### 5.3 What this means for the X-band number

§1's sample is described only as *"ester-based... low shore hardness."* By §5.1–5.2 that is the **lower-εr chemistry** in its **higher-εr, higher-loss hardness class**. §2's NinjaFlex is 85 Shore A of unstated chemistry. The two land at εr 2.7 (10 GHz) and 3.0 (2.4 GHz) respectively, which is reassuringly tight — but **there is no X-band data at all for hard D-grade TPU, and the 1 MHz data says D-grades differ from A-grades by ~35% in εr.** Extending εr ≈ 2.7 to a 75 D TPU would be `INFERRED`, and probably wrong by more than the measurement tolerance.

---

## 6. The datasheet trap, running the opposite way from Kapton

This repo's standing example is Kapton 500HN: a datasheet tanδ of ~0.002 at kHz against a *measured* 0.012 at X-band — the datasheet is **6× too optimistic**. TPU inverts the shape of that error and is worth recording as a second, differently-flavoured case.

| Frequency | εr | tanδ | Provenance |
|---|---|---|---|
| 1 kHz | 3.6 (one grade) | not extracted | `MEASURED` — He et al. 2020 |
| 1 MHz | **4.0 – 7.5** | **0.040 – 0.140** | `MANUFACTURER-SPECIFIED` — BASF Elastollan |
| unstated (IEC 60250) | 4.0 – 8.0 | 0.03 – 0.10 | `MANUFACTURER-SPECIFIED` — Covestro |
| 2.4 GHz | 3.00 | 0.060 | `MEASURED` — Moscato et al. 2016 |
| **8–12 GHz** | **2.68 – 2.75** | **0.084 – 0.105** | `MEASURED` — Vong et al. 2022 |

**Two separate errors, in opposite directions, from using the datasheet:**

1. **εr: the datasheet is far too high.** A 1 MHz value of 6.0 against an X-band value of 2.7 is a **2.2× overstatement**. Substituting 6.0 into a solver would put the guided wavelength off by √(6.0/2.7) = 1.49 — a metamaterial unit cell sized on that assumption would be **~50% wrong in periodicity** and would resonate nowhere near the intended band. This is a design-destroying error, not a refinement.
2. **tanδ: the datasheet happens to be roughly right, for the wrong reason.** 0.040–0.140 at 1 MHz brackets the X-band 0.084–0.105. But that is coincidence, not physics: εr falls steeply between 1 MHz and 10 GHz while ε″ falls more slowly, so tanδ = ε″/ε′ stays broadly flat. Nothing about the datasheet tells you that, and Covestro's own note that loss *"increases with a higher measuring frequency"* would, taken at face value, lead you to expect the X-band figure to be *higher* than the 1 MHz one.

**The rule this supports:** the failure mode is not "datasheets under-report loss." It is "**a low-frequency datasheet is measuring a different physical process from the one X-band sees**." Below ~1 MHz the polar urethane groups have time to rotate with the field and contribute enormously to εr; by 10 GHz they cannot keep up and have largely dropped out. `MANUFACTURER-SPECIFIED` at 1 kHz or 1 MHz must never be promoted to an X-band value in either direction, and TPU is a sharper example of this than Kapton because *both* numbers move.

**Also worth recording:** **NinjaTek's own NinjaFlex datasheet publishes no dielectric data whatsoever** — no permittivity, no loss, no dielectric strength. The full electrical section is absent. For the specific filament most likely to be loaded on a NOVA-adjacent printer, the manufacturer contributes nothing, and every number in §2 comes from academics who had to measure it themselves.

---

## 7. Moisture

Polyurethanes absorb water, and water at X-band has εr ≈ 63 with a very high loss — so even a small water fraction moves a polymer's microwave properties disproportionately. Direct evidence:

**How much water TPU takes up** (`MANUFACTURER-SPECIFIED`):

| Source | Water absorption | Conditions |
|---|---|---|
| BASF Elastollan (polyether grades 1175 A 10 W, 1185 A 10 FHF) | **1.4%** | equilibrium in water, 23 °C, similar ISO 62 |
| BASF Elastollan, same grades | **0.4–0.5%** | equilibrium at 23 °C / 50% r.h. (ordinary room air) |
| NinjaTek NinjaFlex TDS | **0.22%** | ASTM D570, 24 hours |

Polyether grades absorb more than polyester grades (higher polarity), while polyester grades are the ones that *hydrolytically degrade* on long wet exposure — a different failure, and the reason BASF markets polyether for "excellent hydrolysis resistance."

**What that water does to the dielectric properties** (`MEASURED`, but **not at X-band**): Pushparaj Subramaniyan, Das, Raihan & Prabhakar, *Polymers* **17**(5):691 (2025), DOI [10.3390/polym17050691](https://doi.org/10.3390/polym17050691) ([PMC11902309](https://pmc.ncbi.nlm.nih.gov/articles/PMC11902309/)) immersed TPU (Sinterit FLEXA Grey) and measured by broadband dielectric spectroscopy over **10 Hz – 10⁶ Hz**:

- after **90 days** immersion, neat TPU's dielectric loss rose **+79.5% at 10 Hz** and **+8.20% at 10⁶ Hz**;
- after **160 days**, loss had *fallen* 35.4% at 10 Hz and 1.86% at 10⁶ Hz versus unaged — the authors attribute the non-monotonic behaviour to morphology change in the hard/soft segment distribution, not to water content alone.

**Two things to take from this.** First, the effect is real and large at low frequency. Second, and more useful: **it shrinks steeply with frequency** — +79.5% at 10 Hz collapses to +8.2% at 1 MHz, three orders of magnitude higher. Extrapolating that trend four more decades to 10 GHz suggests the moisture sensitivity of TPU's *loss* at X-band is probably modest. **But that is an extrapolation off the end of the measured range and is `INFERRED`, not established.** No X-band moisture-dependence measurement for TPU was found.

**Practical note for a printed skin:** BASF's numbers say TPU sitting in ordinary room air equilibrates at 0.4–0.5% water. That is the state a printed coupon is in unless it is dried and sealed, and it is presumably also the state Vong et al.'s samples were in — so §1's numbers are best read as "TPU as it actually exists in a lab," which is the useful case anyway.

---

## 8. What this changes for #114 and #127

**For #114's shortlist.** TPU moves from "cannot be simulated" to a Regime B (tight/compound curvature) candidate with numbers:

- **εr 2.7 ± 0.3, tanδ ≈ 0.10 across X-band** (`MEASURED`, one grade)
- Sits alongside silicone (εr 2.9, tanδ 0.10) as a **deliberately-lossy flexible substrate**, and unlike silicone it is **already on Voltera's published NOVA substrate list** ("glass, ceramic, TPU via vacuum table, PET, polyimide, textiles", as quoted in #114), and unlike silicone it does **not** have the low-surface-energy adhesion problem that #114 identified as silicone's binding constraint.
- #114's own correction to #105 noted that **DuPont/Celanese Intexar PE874 cures at 130 °C on TPU film** and is already on Voltera's ink list — so a conductor route on TPU exists.

**Taken together, TPU now looks like a stronger Regime B candidate than silicone**, because it matches silicone's loss, beats it on printability and adhesion evidence, and beats it on being a substrate Voltera actually supports. That conclusion was unavailable while TPU had no permittivity.

**For #127's actual question.** #127 asks what the loop does with an unmodellable candidate, and used TPU as one of its two worked examples. **TPU is no longer a valid example** — it was never a data gap in the world, only a gap in *our* search, and it closed the moment someone got past a 403 and opened a PDF. That is itself the strongest possible evidence for #127's own framing:

> *"Is 'unmodellable' a fabrication constraint or a data gap? It looks like a property of the material but is really a property of our knowledge, and it disappears the moment someone measures it."*

Here it disappeared without anyone measuring anything new. **A candidate excluded for missing data must therefore be reported, never silently dropped — because the exclusion may be one successful web fetch away from being wrong, and nobody will ever discover that if the candidate never appears in the output.** #127's second example, **Eccosorb BSR/MFS, remains genuinely unmodellable** (Laird publishes attenuation only, no ε′/ε″/µ′/µ″), so the ticket still needs its answer — but it should be argued from Eccosorb, and TPU should be moved into the "this is what happens when the loop reports the gap instead of hiding it" column.

---

## 9. Honest gaps

1. **No named, purchasable grade has X-band data.** §1's material is "a commercial ester-based TPU of low Shore hardness" — unnamed. §2's NinjaFlex is named but measured only at 2.4 GHz. Nobody has published X-band εr/tanδ for a spool you can order by part number.
2. **No X-band data for hard (Shore D) TPU.** The 1 MHz manufacturer data says D-grades differ from A-grades by ~35% in εr and up to 3.5× in tanδ. Applying §1's numbers to a D-grade is `INFERRED` and likely wrong.
3. **No X-band moisture-dependence measurement** (§7). The trend argues it is small; the trend is an extrapolation across four decades of frequency.
4. **The X-band per-frequency numbers come from digitising a published figure**, because the authors report only "between 2.5 and 3" in text. The digitisation is straightforward and the axis calibration unambiguous, but it is a figure read, not a table read.
5. **Only one X-band source.** §2 corroborates the *shape* of the answer at a different frequency by a different method, which is meaningful — but there is no second independent X-band measurement of solid TPU. A single source at ±11% stated repeatability is thin for a primary design input.
6. **The neat-matrix baseline is systematically missing from the composite literature.** Dozens of papers measure TPU-plus-filler across X-band for absorber and EMI-shielding work; almost none report the unfilled TPU control. Checked and confirmed absent in: Zheng & Wang, *Polymers* **14**(22):4960 (2022), DOI [10.3390/polym14224960](https://doi.org/10.3390/polym14224960) ([PMC9695098](https://pmc.ncbi.nlm.nih.gov/articles/PMC9695098/) — TPU/carbonyl-iron, 0.3–18 GHz coaxial, BASF TPU 1195A matrix, composites only, no unfilled baseline) and Bhattacharya et al., *eXPRESS Polym. Lett.* (X-band WR-90 — four filled RAMs, no neat control). **This is why the data looked absent: the number is a control specimen that authors routinely omit.**
7. **Still blocked, and would add value if a human opened them:**
   - **MDPI direct (403)** — routed around via PMC successfully, but only for papers PMC mirrors.
   - **IEEE Xplore (403)** — "Characterization of 3D-printed dielectric substrates with different infill for microwave applications," Moscato et al., IEEE IMWS-AMP 2016 ([IRIS 11571/1470234](https://iris.unipv.it/handle/11571/1470234), no full text deposited). Its abstract states it did **broadband characterisation of NinjaFlex from 2 GHz to 20 GHz using microstrip lines** — i.e. **it contains a second, independent NinjaFlex X-band curve** for a *named* filament, which would close gaps 1 and 5 at once. **This is the single highest-value stranded source in this search.**
   - **Taylor & Francis (403)** — "3D printing of electromagnetically functional materials for radio frequency applications using fused filament fabrication," *Virtual and Physical Prototyping*, DOI [10.1080/17452759.2026.2627763](https://doi.org/10.1080/17452759.2026.2627763). OpenAlex reports it **gold open access**, but tandfonline returns 403 to automated fetches. A review of exactly this topic; likely tabulates TPU values with citations.
   - **ScienceDirect (403)**, **Wiley (403)**, **ResearchGate (403)**, **Semantic Scholar API (429 throughout)**, **NC State repository (bot challenge)**.

---

## 10. Why #114 concluded "no data" and what actually unblocked it

Recorded because it is a reusable lesson about the search, not about TPU.

| #114's blocker | What worked this time |
|---|---|
| MDPI returns 403 to every automated fetch | **PubMed Central mirrors MDPI's open-access content.** `pmc.ncbi.nlm.nih.gov` served the full text of both decisive MDPI papers. Europe PMC's REST API (`/fullTextXML`) served machine-readable full text with no blocking at all. |
| "No PDF renderer (poppler, working pypdf) exists in this environment" | **`pymupdf` is installed and works.** It extracted text, per-span font data, and page/figure images from every PDF tried. |
| Publisher paywalls (IEEE 403) strand the key papers | **University repositories hold author post-prints.** The IEEE AWPL NinjaFlex paper came from `iris.unipv.it`; a companion paper from an author's own faculty page at Georgia Tech; another from Nottingham Trent's IRep. |
| Custom font subsetting "defeats text extraction" | **The subsetting was a fixed +29 character-code offset.** Decoding per text span recovered the whole document. Where that fails, rendering the page region to an image and reading it visually works. |
| Numbers exist only inside plotted figures | **Figures can be digitised.** §1's entire X-band table was recovered by locating plotted marker centres against axis gridlines in the published figure image. |
| Search terms were about substrates and TPU | **The number lived in a paper about a magnetic absorber.** Nothing in its title, abstract or keywords mentions TPU permittivity — the TPU figure is a supporting characterisation for the *other* material. Searching for the application, not the property, is what surfaced it. |

---

## 11. What measurement would still be worth doing

Not to obtain a first value — that now exists — but to close gaps 1, 2 and 5:

**A WR-90 waveguide transmission/reflection measurement of the specific TPU stock the programme intends to use**, per ADR-0012's external-request route (this repo has no instrument path of its own), alongside #106's coupon run:

- **Fixture:** WR-90 (X-band, 8.2–12.4 GHz), sample machined or printed to the 22.86 × 10.16 mm guide cross-section. This is the same fixture class #114 proposed for a TPU coupon, so the request is unchanged — only its justification is stronger, because there is now a published number to check against rather than a void to fill.
- **Specimens:** at minimum the actual spool in use; ideally one soft A-grade and one hard D-grade, to test whether §5.2's hardness trend survives to X-band.
- **Conditioning:** measure as-received (room-air equilibrium) *and* after drying, which would close gap 3 with two extra data points.
- **Expected result, so the measurement can falsify something:** **εr 2.7 ± 0.3, tanδ 0.10 ± 0.01.** If the coupon lands there, TPU is confirmed as a lossy conformal substrate in silicone's class and the design can proceed on published data. If it lands near tanδ 0.02, then §1's sample was atypical and the whole "TPU is lossy" conclusion needs revisiting.

**Cheaper alternative that needs no bench time:** a human with a browser opening the IEEE IMWS-AMP 2016 paper (gap 7) would supply a second independent NinjaFlex curve across 2–20 GHz for a named, purchasable filament. That is a five-minute task with a library login and it closes more of this than any other single action.

---

## Sources

**Primary — X-band and microwave measurements of TPU**

- Vong, C., Chevalier, A., Maalouf, A., Ville, J., Rosnarho, J.-F., & Laur, V. (2022). Manufacturing of a Magnetic Composite Flexible Filament and Optimization of a 3D Printed Wideband Electromagnetic Multilayer Absorber in X-Ku Frequency Bands. *Materials*, **15**(9), 3320. DOI [10.3390/ma15093320](https://doi.org/10.3390/ma15093320). Open access via [PMC9099990](https://pmc.ncbi.nlm.nih.gov/articles/PMC9099990/). — **§1, the X-band figure.**
- Moscato, S., Bahr, R., Le, T., Pasian, M., Bozzi, M., Perregrini, L., & Tentzeris, M. M. (2016). Infill Dependent 3-D-Printed Material Based on NinjaFlex Filament for Antenna Applications. *IEEE Antennas and Wireless Propagation Letters*, **15**, 1506–1509. DOI [10.1109/LAWP.2016.2516101](https://doi.org/10.1109/LAWP.2016.2516101). Author post-print: [IRIS 11571/1119842](https://iris.unipv.it/handle/11571/1119842). — **§2.**
- Bahr, R., Le, T., Tentzeris, M. M., Moscato, S., Pasian, M., Bozzi, M., & Perregrini, L. (2015). RF Characterization of 3D Printed Flexible Materials — NinjaFlex Filaments. *45th European Microwave Conference*, Paris, pp. 742–745. [PDF](https://tentzeris.ece.gatech.edu/EUMW15_Bahr.pdf). — **§2, Fig. 7.**
- Mukai, Y., Li, S., & Suh, M. (2021). 3D-printed thermoplastic polyurethane for wearable breast hyperthermia. *Fashion and Textiles*, **8**, 24. DOI [10.1186/s40691-021-00248-7](https://doi.org/10.1186/s40691-021-00248-7). — **§4, frequency not stated.**
- Singh, R., et al. (2024). 3D Printing of Thermoplastic Polyurethane on Woven Fabric for Body-Centric Applications. *National Academy Science Letters*. DOI [10.1007/s40009-024-01513-1](https://doi.org/10.1007/s40009-024-01513-1). Post-print: [NTU IRep 52667](https://irep.ntu.ac.uk/id/eprint/52667/). — **§4.**
- Bhattacharya, P., et al. Microwave absorption behaviour of MWCNT based nanocomposites in X-band region. *eXPRESS Polymer Letters*. [Open access](https://www.expresspolymlett.com/article.php?a=EPL-0003931). — **§4, §9 (no neat baseline).**
- Zheng, Y., & Wang, Y. (2022). Electromagnetic-Wave Absorption Properties of 3D-Printed Thermoplastic Polyurethane/Carbonyl Iron Powder Composites. *Polymers*, **14**(22), 4960. DOI [10.3390/polym14224960](https://doi.org/10.3390/polym14224960). — **§9 (no neat baseline).**

**Porous / foamed TPU — not solid TPU**

- Li, Y., Xu, Y., Wen, G., & Wang, J. (2025). Fabrication of 3D Porous and Flexible Thermoplastic Polyurethane/Carbon Nanotube Composites Towards High-Performance Microwave Absorption. *Molecules*, **30**(17), 3610. DOI [10.3390/molecules30173610](https://doi.org/10.3390/molecules30173610). — **§3.**
- Kaftelen Odabaşı, H., Kaya, Ü., Odabaşı, A., Helhel, S., Ruiz-Perez, F., & Caballero-Briones, F. Investigating the Structural, Thermal, Electric, Dielectric, and EMI Shielding Properties of Porous Thermoplastic Polyurethane Reinforced with Carbon Fiber/Magnetite Fillers. *Polymers*, **18**(1), 19. DOI [10.3390/polym18010019](https://doi.org/10.3390/polym18010019). — **§3.**

**Low-frequency and moisture**

- He, X., Zhou, J., Jin, L., Long, X., Wu, H., Xu, L., Gong, Y., & Zhou, W. (2020). Improved Dielectric Properties of Thermoplastic Polyurethane Elastomer Filled with Core–Shell Structured PDA@TiC Particles. *Materials*, **13**(15), 3341. DOI [10.3390/ma13153341](https://doi.org/10.3390/ma13153341). — **§4, §6 (pure TPU ε = 3.6 at 1 kHz).**
- Pushparaj Subramaniyan, S., Das, P. P., Raihan, R., & Prabhakar, P. (2025). Moisture-Driven Morphology Changes in the Thermal and Dielectric Properties of TPU-Based Syntactic Foams. *Polymers*, **17**(5), 691. DOI [10.3390/polym17050691](https://doi.org/10.3390/polym17050691). — **§7.**

**Manufacturer data (`MANUFACTURER-SPECIFIED`)**

- BASF. *Elastollan® — Thermoplastic Polyurethane Elastomers (TPU)*, product range brochure, pp. 28–31. [PDF](https://download.basf.com/p1/8a8082587fd4b608017ff4e900830157/en/Elastollan). — **§5.1, §6, §7.**
- Covestro. *Electrical properties* (TPU technology article). [Link](https://solutions.covestro.com/en/highlights/articles/theme/product-technology/electrical-properties-tpu). — **§5.1, §5.2, §6.**
- NinjaTek. *NinjaFlex 3D Printing Filament — Technical Specifications*. [PDF](https://ninjatek.com/wp-content/uploads/NinjaFlex-TDS.pdf). — **§2 (TPU, 85 Shore A), §6 (no dielectric data published), §7 (0.22% moisture).**

**Stranded (fetch blocked; listed for a human with a browser)**

- Moscato, S., et al. (2016). Characterization of 3D-printed dielectric substrates with different infill for microwave applications. *IEEE MTT-S IMWS-AMP*. [IEEE 7588330](https://ieeexplore.ieee.org/document/7588330) (403) — metadata at [IRIS 11571/1470234](https://iris.unipv.it/handle/11571/1470234), no full text deposited. **NinjaFlex, 2–20 GHz. Highest-value missing source.**
- *3D printing of electromagnetically functional materials for radio frequency applications using fused filament fabrication*. *Virtual and Physical Prototyping*. DOI [10.1080/17452759.2026.2627763](https://doi.org/10.1080/17452759.2026.2627763) — reported gold OA by OpenAlex, tandfonline 403 to automated fetch.
