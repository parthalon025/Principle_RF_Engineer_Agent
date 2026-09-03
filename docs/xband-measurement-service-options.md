# Getting X-Band Coupons Measured Without Owning a VNA: Services, Labs, Costs, and What Comes Back

**Research date:** 2026-09-03
**Serves:** #133 (provenance ceiling / route to measured data), #132 (blocked on measurement capability), #104 (the map)
**Question:** with no vector network analyser and no measurement fixture in-house, how does someone get a printed metamaterial coupon measured at 8–12 GHz, what does it cost, what must they supply, and what comes back?

> **Plain-language framing.** A *vector network analyser* (VNA) is the instrument that sends a radio signal at a thing and records both **how much** comes back and **when** it comes back — amplitude and phase. "Phase" is the timing of the returning wave; it is the half that a simple power meter throws away and the half a metamaterial element library needs. Everything below is about renting, borrowing or buying access to that measurement.

---

## Bottom line up front

**A realistic route to `MEASURED` X-band data exists, and it is not expensive by instrument standards.** Free-space absorber-reflectivity measurement is routine, standardised commercial practice (IEEE Std 1128), sold by EMC/absorber test houses and by specialist RF-materials houses, and available from university anechoic chambers at published hourly rates. Nobody publishes a price list for the material measurement itself — it is universally "request a quote" — but the university rates that *are* published put a one-day session in the **US$2,000–5,000** range, against **US$13,000–30,000** to assemble a used bench that can do it in-house.

**But the coupon size in the map is wrong by roughly an order of magnitude, and that is the finding that matters most.**

- #104 records "Coupons are 11 × 11 cells, sized for free-space horn measurement, not waveguide (#106). Verified practice, not a guess." At the ~3 mm X-band pitch that is a **33 × 33 mm** panel — about **1.1 free-space wavelengths across** at 10 GHz (λ₀ = 29.98 mm). `CALCULATED`.
- NPL's own good-practice guide states flatly that free-field specimens "generally have to be large in cross section: typically **more than 20 wavelengths across for unfocussed techniques and 6 wavelengths for focussed techniques**" ([NPL/IMC, *A Guide to the Characterisation of Dielectric Materials at RF and Microwave Frequencies*, 2003, p. 127](https://www.kirkbymicrowave.co.uk/Support/Links/applications/Dielectric_Measurements/documents/Dielectrics-Good-practice-guide-from-NPL-2003.pdf)). `LITERATURE-SUPPORTED`.
- At X-band that is **≈180 mm square minimum for a focused-beam measurement and ≈600–750 mm square for an ordinary two-horn (unfocused) setup**. `CALCULATED` from λ₀ = 25.0 mm at 12 GHz, 29.98 mm at 10 GHz, 37.5 mm at 8 GHz.
- **A 33 mm coupon is not measurable in free space at X-band by any documented method.** The wave simply spills round the edges; what you would measure is the edge, not the surface.

**The fix is cheap and is a printing decision, not a purchase.** Keep 3 mm cells and make the coupon **60 × 60 cells (180 mm) as an absolute floor, 75 × 75 (225 mm) to be safe at the 8 GHz end, and 100 × 100 (300 mm) to match what the literature and the service houses actually handle.** That is 3,600 to 10,000 cells per coupon instead of 121 — a print-time and ink cost, not a capital cost. The Voltera NOVA's 220 × 300 mm print area accommodates a 225 mm coupon; it does **not** accommodate 300 mm in both axes.

**The deliverable question (ADR-0013) has a clean answer, and it splits by method.** A free-space *reflection* measurement is naturally a **one-port S-parameter set** — S11 magnitude and phase versus frequency, referenced to a flat metal plate in the same position — which is a **Touchstone `.s1p`** file and parses under `rf_tools/touchstone.py` unchanged. An **NRL-arch reflectivity test, which is what most absorber test houses sell, returns reflectivity in dB versus frequency and no phase at all.** If the element library needs phase — and a reflectarray-style alphabet does — the enquiry must ask for *calibrated S11 magnitude and phase as a Touchstone file*, not "an absorber reflectivity report."

---

## 1. The size problem, stated precisely

This section is first because it changes what you ask for.

### What the methods require

| Method | Minimum specimen size (published rule) | At 10 GHz | At 8 GHz (worst case in band) |
|---|---|---|---|
| Unfocused free-field (two plain horns, NRL arch) | > 20 λ₀ across ([NPL GPG, p. 127](https://www.kirkbymicrowave.co.uk/Support/Links/applications/Dielectric_Measurements/documents/Dielectrics-Good-practice-guide-from-NPL-2003.pdf)) | 600 mm | 750 mm |
| Focused beam / quasi-optical (lens or mirror horns) | 6 λ₀ across (same source) | 180 mm | 225 mm |
| Focused beam, alternative rule | Specimen ≥ 5 × Gaussian-beam radius at the waist (same source, p. 126) | — | — |
| Focused beam, alternative rule (spot-focusing lens horns) | Transverse dimension > 3 × the 3 dB E-plane beamwidth at focus (Ghodgaonkar/Varadan free-space method, as quoted in secondary summaries — primary is IEEE, stranded) | — | — |
| NRL arch, to reach −40/−50 dB reflectivity | ≥ 6 λ per side (secondary summary of IEEE Std 1128 practice) | 180 mm | 225 mm |

Two independent anchors agree on roughly the same number:

- NPL notes that in a typical focused system "the beam diameter at the specimen surface **approaches 300 mm at 8 GHz**" (p. 127) — so the specimen has to be at least that, and the measurement is an *average over the illuminated patch*, not a point probe.
- A published open-access X-band focused-beam setup used a **222 mm PTFE lens** on an 8.2–12.4 GHz horn and measured **300 × 300 × 100 mm** concrete blocks, stating only that "the cross section was sufficiently larger than the 3 dB beamwaist of the antenna" ([Kim et al., *Materials* / PMC8659499](https://pmc.ncbi.nlm.nih.gov/articles/PMC8659499/)). `LITERATURE-SUPPORTED`.

Published metamaterial-absorber validations sit in the same place: reported X-band prototypes are typically **15 × 15 cells of 12 mm (180 mm)** or **20 × 20 cells**, measured with two horns in an anechoic chamber against a VNA (found via search summary of ScienceDirect/Springer articles that are themselves stranded behind 403s — treat as `INFERRED` pending a readable primary).

### What that means for a 3 mm pitch

| Coupon | Cells per side at 3 mm pitch | Total cells | Wavelengths across at 10 GHz |
|---|---|---|---|
| 33 mm (the map's current 11 × 11) | 11 | 121 | 1.1 λ₀ |
| 180 mm (focused-beam floor at 10 GHz) | 60 | 3,600 | 6.0 λ₀ |
| 225 mm (focused-beam floor at 8 GHz) | 75 | 5,625 | 7.5 λ₀ |
| 300 mm (matches real service-house practice) | 100 | 10,000 | 10.0 λ₀ |
| 600 mm (unfocused two-horn floor at 10 GHz) | 200 | 40,000 | 20.0 λ₀ |

All `CALCULATED`. The NOVA's print area is **220 × 300 mm**, so 225 mm square is the largest practical square coupon on one plate; 300 mm is only reachable in one axis.

> **Plain-language reading.** Radio waves at 10 GHz are 30 mm long. To measure how a surface reflects, the surface has to be several waves wide, or the wave just wraps around the edge and you measure the edge instead. The current 33 mm coupon is barely one wave across. You need roughly six waves (180 mm) with focusing optics, or twenty (600 mm) without them.

### A citation in the map that does not check out

#104 and the brief for this ticket attribute the 11 × 11 coupon convention to **Costanzo et al., *IJAP* 2019, DOI 10.1155/2019/9479010**, described as characterising a reflectarray unit cell with an 11 × 11 identical-cell array and two identical horns.

That DOI resolves to **"A Single-Layer Dual-Band Reflectarray Cell for 5G Communication Systems," Costanzo, Venneri, Borgia & Di Massa, *International Journal of Antennas and Propagation* vol. 2019, pp. 1–9** ([Crossref](https://api.crossref.org/works/10.1155/2019/9479010); [Semantic Scholar record](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1155/2019/9479010), Gold OA, CC BY). Its subject is a **28/38 GHz** cell, and both the Crossref and Semantic Scholar abstracts describe **numerical validation only** — "numerical validations demonstrate the cell's effectiveness." Neither abstract mentions an 11 × 11 array, horn antennas, or any measurement. The full text is on Wiley and returns **403 to automated fetches here**, so this is not proof of absence — but the DOI does not support the claim as stated, and it is a **28/38 GHz** paper being used to justify an **X-band** coupon size, which would not transfer even if the array detail were there (11 × 11 cells at 28 GHz spans a different number of wavelengths than 11 × 11 cells at 10 GHz).

**Recommendation for #104:** demote "Coupons are 11 × 11 cells… Verified practice, not a guess" from settled to open, and re-derive the coupon size from the wavelength rule above. `UNKNOWN` until the Wiley full text is read by a human.

---

## 2. Commercial services: free-space and surface characterisation at X-band

None publishes a price. All are "request a quote." All prices and offerings below are as of **2026-09-03** and should be re-checked; RF service pricing is quoted per job, not listed.

### 2.1 Specialist RF-materials measurement houses

**Compass Technology Group** (Kennesaw/Suwanee, GA, USA) — the most directly relevant find. They sell both the instruments and the measurement service.

- Service page: [Contract RF Materials Measurement](https://compasstech.com/services/contract-rf-materials-measurement/). `MANUFACTURER-SPECIFIED`.
- **Focused-beam measurements**, frequency bands "2–20+ GHz, 20–40 GHz, 40–60 GHz, 60–90 GHz" — X-band sits inside the first band.
- **Sample size: "approximately 2″ to 24″ square, depending on lower frequency bound."** The 2″ (50.8 mm) end is for the highest bands; a 2 GHz lower bound implies the 24″ end. Where X-band lands inside that range is not stated — this must be asked, but the NPL 6 λ rule says expect **≥ 180–225 mm**.
- **What they measure: "complex permittivity, permeability, sheet impedance, and/or S-parameters."** The "and/or S-parameters" is the important phrase for ADR-0013 — raw S-parameters are on the menu.
- Also offer **waveguide measurements**, **coaxial airline (7 mm)**, **ASTM D2520 resonant cavity**, and **anechoic absorber testing to IEEE 1128** (200 MHz and up, reflection amplitude only).
- Their own [focused-beam system page](https://compasstech.com/focused-beam-free-space-materials-measurement-system/) says the specimen holder takes "specimens up to 24″ x 24″" and that their CTGcalc software "acquires S-parameter data and performs calibrations, including time domain gating" — i.e. the underlying data product is S-parameters.
- Contact is a phone number and a form; no pricing, no published turnaround.

**MuEpsln, LLC** (Concordville, PA, USA) — the continuation of **Damaskos, Inc.**, a 30-year-old name in microwave material measurement. [Homepage](https://muepsln.com/) states it "provides measurement services, measurement fixtures, measurement software, and design tools" and continues "Damaskos, Inc.'s 30+ year tradition." [Measurement services page](https://muepsln.com/measurement-services/): `MANUFACTURER-SPECIFIED`

- Fixtures: **"cavity, coaxial, waveguide, and free space methods."**
- Frequency: **300 kHz to 70 GHz** for materials; 0.5–26 GHz for antenna patterns and RCS.
- Measures "dielectric constant, loss tangent, conductivity, complex permeability, shielding effectiveness, insertion loss, return loss, sheet resistivity."
- Materials handled include "magrams" (magnetic radar-absorbing materials), radomes, laminates, circuit boards.
- **No sample-size, deliverable, or price information published.** "Contact us with requirements for more information."

### 2.2 Absorber / EMC test houses (NRL arch)

The **NRL arch** is the 1945 Naval Research Laboratory method: a non-reflective arch carrying two horns, a metal plate underneath as the 0 dB reference, and the difference between plate-alone and plate-plus-sample is the reflection coefficient. It is the standard commercial absorber test and it is **scalar** — magnitude only.

**EMCTEST Technologies** (Italy) — [NRL Arch Reflectivity Test](https://www.emctest.it/?l=nrl-arch-test&country=uk). `MANUFACTURER-SPECIFIED`

- **1–18 GHz standard, extendable to 40 GHz on request.** X-band well inside.
- Follows **IEEE 1128-1998** and IEEE AMTA 2016.
- Sample types listed include "polymers in sheet form, RF absorbers, radar absorbing materials (RAM)."
- **"Request now a free quotation"** — no published prices, no published minimum sample size.

**ETS-Lindgren / ETS-Rantec** (USA) — the largest absorber manufacturer, and it runs its own arch. A GTEMCELL-hosted reprint of the ETS description ([Arch-Test-Reflection-loss.pdf](https://wgtem.com/wp-content/uploads/2023/02/Arch-Test-Reflection-loss.pdf)) states: "The swept-frequency Naval Research Labs (NRL) arch method is used by ETS-Rantec to measure microwave absorber reflectivity performance. The test is conducted at frequencies between **1 and 18 GHz**. However, testing can be conducted at higher frequencies if requested." Two arches cover the range. `MANUFACTURER-SPECIFIED`. The same document describes a **vertical coaxial reflectometer** for the low-frequency end per IEEE 1128 §7.2.3.3 — not relevant at X-band.

**GTEMCELL Ltd** (Italy) manufactures a 3 m arch for 1–18 GHz and invites enquiries for testing — same document.

**Caveat that matters:** NPL's guide is blunt about the arch's ceiling — it "suffers from diffraction and limited-aperture effects however, and so may not be effective for reflection coefficients less than about −40 dB" (p. 125). For an absorber spec of −10 to −20 dB that is fine; for characterising a low-loss element it is not.

### 2.3 Antenna / EM test houses that publish prices

These do not sell material characterisation, but they establish what a small US RF lab charges for chamber time, which is the closest published anchor available.

**Antenna Test Lab Co** (Ohio, USA) — [published price list](https://antennatestlab.com/prices). `MANUFACTURER-SPECIFIED`, checked 2026-09-03.

- Standard resolution: **US$525** (setup + one antenna), **US$350** per additional antenna.
- Higher resolution: **US$875** (setup + one antenna), **US$700** per additional.
- Frequency coverage: "As wide as: 300 MHz–6 GHz; or **1.5–18 GHz**; or 18–40 GHz."
- **Deliverable: spreadsheet data in Excel format.** Not Touchstone.

**GTRI (Georgia Tech Research Institute)** — [Electromagnetic Measurements and Analysis](https://www.gtri.gatech.edu/focus-areas/electromagnetic-measurements-and-analysis). The Advanced Concepts Laboratory "specializes in the accurate measurement of radar cross section, **material properties**, and antenna performance," operating "a compact range and **multiple free-space focused-beam systems**," and is "a trusted source of measurements in support of customer R&D and QA." `MANUFACTURER-SPECIFIED`. This is a genuine focused-beam material-measurement capability at a US applied-research institute that takes external sponsors. No prices, no sample specs published; engagement is by contacting the laboratory director. GTRI also runs the [EMTEF antenna test range](https://emtef.org/), 200 MHz–100 GHz.

**NSI-MI Technologies** and **MVG (Microwave Vision Group)** are the other two names in the IEEE Std 1128 working group alongside ETS-Lindgren ([Chen, Rodriguez & Foged, "Progress on the Development of IEEE Std 1128," AMTA 2023](https://www.nsi-mi.com/-/media/project/oneweb/oneweb/nsi/files/technical-papers/2023/progress-on-the-development-of-the-isss-std-1128.pdf)) — both are antenna/absorber measurement houses with the relevant hardware. Neither publishes a materials-testing price list.

---

## 3. University labs with published external-user access

This is the most price-transparent route, and two US universities publish rate cards that an external requester can plan against.

### Texas A&M — Intelligent Electromagnetic Sensor Laboratories (iEMSL)

[Published fee schedule](https://iemsl.engr.tamu.edu/fees/measurement-services-facility-access/). `MANUFACTURER-SPECIFIED`, checked 2026-09-03. Rates are stated uniformly with no internal/external distinction shown on the page.

| Item | Rate |
|---|---|
| Membership, daily | US$300/day |
| Membership, monthly | US$2,500/month |
| Training, setup, assisted testing | US$250/hour |
| Equipment usage, > 10 GHz (VNA, spectrum analysers) | US$50/hour, **in addition to** membership |
| **Anechoic chamber, assisted operation** | **US$500 setup + US$450/hour, or US$4,500/day** |

Notes on the page: "The anechoic chamber is available only with assisted operation." "Minimum 1-hour charge per use." "Daily membership is intended for assisted sessions. Self-conducted use of equipment above 10 GHz requires training first, which makes monthly membership the practical option."

Their [capability listing](https://iemsl.engr.tamu.edu/facilities-full/anechoic-chamber/) gives the chamber as **400 MHz to 140 GHz** for antenna characterisation, and the lab advertises "antenna measurement services, **electromagnetic material characterization services**, and S-parameters and system-level testing."

**Order-of-magnitude for one day:** US$4,500 (chamber day rate) + US$300 (daily membership) ≈ **US$4,800**, before any setup fee or fixture work. `CALCULATED`.

### University of Kansas — Anechoic Chamber (M2SEC)

[Chamber overview](https://chamber.ku.edu/chamber-overview-0) and [published rates](https://chamber.ku.edu/rates). `MANUFACTURER-SPECIFIED`, checked 2026-09-03.

- Capability: **30 MHz to 18 GHz**, 10 m range, 15 × 35 × 15 ft, ~100 dB shielding. X-band inside.
- Rates, three explicit user classes:

| User class | Access only | With technician |
|---|---|---|
| KU | US$40/hr | US$84/hr |
| External academic | US$63/hr | US$132/hr |
| **External (industry/private)** | **US$120/hr** | **US$252/hr** |

- Mandatory first-time training: US$85 (KU) / US$133 (external academic) / **US$255 (external)**.

**Order-of-magnitude for one 8-hour day, external, with technician:** US$255 training + 8 × US$252 = **US$2,271**. `CALCULATED`. This is the cheapest credible published route found.

### Others worth an enquiry

- **Embry-Riddle Aeronautical University** (Daytona Beach) — [anechoic chamber](https://daytonabeach.erau.edu/about/labs/anechoic-chamber) described as "available for commercial and government (pay-per-use) testing," to 20 GHz with extension to 110 GHz. No published rates.
- **University of Alabama** Remote Sensing Center — [electromagnetic anechoic chamber](https://rsc.ua.edu/electromagnetic-anechoic-chamber/).
- **Ohio State ElectroScience Laboratory** — long-standing compact range and materials work (their published output includes single-port NRW method development), but no external-access policy or rate card was found in this pass. `UNKNOWN`.

**What universities are good and bad at.** Good: cheap, will engage with an unusual sample, may collaborate rather than invoice. Bad: they are set up for *antenna* measurement, not *material* measurement — a free-space material bench needs a metal-plate reference, time-domain gating and a specimen frame that an antenna chamber may not own. Ask specifically whether they have a material-measurement fixture or only an antenna positioner.

---

## 4. National metrology institutes

### NPL (UK) — the strongest offering

[Electromagnetic materials — measurements on materials](https://www.npl.co.uk/products-services/electromagnetic-materials/measurements). `MANUFACTURER-SPECIFIED`, checked 2026-09-03.

- Range **1 kHz to 750 GHz**.
- Methods: coaxial line and waveguide transmission-line **100 MHz–18 GHz**; split-post dielectric resonators 1.8–14 GHz; open resonators for very low loss (tan δ < 0.003); open-ended coaxial probes 50 MHz–50 GHz; quasi-optical transmission 50–750 GHz.
- **Explicitly lists "Metamaterials and artificial dielectrics" among measurable material categories.** This is the only institution found that names metamaterials in its service description.
- Engagement: customer services phone / enquiry form, "bespoke solutions." No price list.

NPL also authored the definitive open guidance document used throughout this note: **Clarke, Gregory, Cannell, Patrick, Wylie, Youngs & Hill, *A Guide to the Characterisation of Dielectric Materials at RF and Microwave Frequencies*, IMC/NPL, 2003** ([NPL record](https://eprintspublications.npl.co.uk/2905/); [full PDF mirror](https://www.kirkbymicrowave.co.uk/Support/Links/applications/Dielectric_Measurements/documents/Dielectrics-Good-practice-guide-from-NPL-2003.pdf)). 187 pages, free, and it is the source of the specimen-size rules in §1. `LITERATURE-SUPPORTED`.

### NIST (US) — guidance yes, service no

**NIST does not sell a material permittivity/reflectivity measurement as a catalogued service.** The [SP 250 fee schedule](https://www.nist.gov/document/feesch-11-2-2pdf) (the appendix listing every NIST calibration with its price) contains **no dielectric-material, permittivity, or absorber-reflectivity line item**. The closest entries are:

- **61290S** — "Special Microwave and RF Scattering-Parameter Measurement Services, **by Prearrangement** — **At Cost**"
- **64300S** — "Special Test Services for Antenna/Field Strength/**Reflectivity** Measurements, Utilizing the Anechoic Chamber and Standard Field Method — **At Cost**"
- **63400S** — "Special Consulting, Advisory, and Other Services — At Cost"

`MANUFACTURER-SPECIFIED`. **Staleness flag: the fee schedule retrieved is dated 2011.** Fees and service IDs will have moved; the structural point (no catalogued material service, only "at cost, by prearrangement" special tests) is what should be carried forward, not the specific IDs. Current enquiries go to `calibrations@nist.gov`.

Where NIST is genuinely valuable is **documented method**, free:

- **NIST Technical Note 1520**, Baker-Jarvis et al., *Dielectric and Conductor-Loss Characterization and Measurements on Electronic Packaging Materials* (2001) — [PDF](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=20484).
- **NIST Technical Note 1536**, Baker-Jarvis, Janezic, Riddle, Johk, Kabos, Holloway, Geyer & Grosvenor, *Measuring the Permittivity and Permeability of Lossy Materials: Solids, Liquids, Metals, Building Materials, and Negative-Index Materials* (2005) — [nvlpubs PDF](https://nvlpubs.nist.gov/nistpubs/Legacy/TN/nbstechnicalnote1536.pdf), also on [Internet Archive](https://archive.org/details/measuringpermitt1536bake). This is the standard US reference and explicitly covers **negative-index (metamaterial) media** and free-space methods. `LITERATURE-SUPPORTED`.

### PTB (Germany), METAS (Switzerland)

PTB publishes a [testing and calibration facilities](https://www.ptb.de/cms/en/ptb/fachabteilungen/abt1/fb-16/ag-162/testing-and-calibration-facilities.html) page and does research on microwave permittivity, but **no catalogued material-measurement service was found** in this pass. `UNKNOWN` — not "does not exist," just not established here.

---

## 5. What a requester must supply, and what comes back

### Sample requirements

| Requirement | Value | Source |
|---|---|---|
| **Size, focused beam** | ≥ 6 λ₀ across → **≥ 180 mm sq at 10 GHz, ≥ 225 mm sq at 8 GHz** | NPL GPG p. 127 |
| **Size, unfocused two-horn / arch** | ≥ 20 λ₀ across → **≥ 600 mm sq at 10 GHz** | NPL GPG p. 127 |
| **Size, vendor-stated (Compass focused beam)** | "approximately 2″ to 24″ square, depending on lower frequency bound" | [Compass](https://compasstech.com/services/contract-rf-materials-measurement/) |
| **Size, vendor-stated (Compass UHF free-space, 0.5–5 GHz)** | "approximately 24″ to 48″ square" | same |
| **Flatness** | NPL: "similar considerations apply to specimen flatness and positioning" as to mirror surface finish; mismounting is listed among the dominant uncertainty sources | NPL GPG pp. 126–127 |
| **Quantity** | One panel per distinct surface. For a per-letter library, **one panel per letter** — this is the cost driver | `INFERRED` |
| **Mounting** | Specimen sits at the beam waist in a holder; arch tests sit flat on the reference metal plate | NPL GPG; ETS/GTEMCELL arch description |
| **Reference** | A flat metal plate of the same size and position provides the 0 dB / short-circuit reference | ETS/GTEMCELL arch description; SSL calibration in [PMC8659499](https://pmc.ncbi.nlm.nih.gov/articles/PMC8659499/) |
| **Lead time** | **Not published by any service found.** Must be asked | `UNKNOWN` |

Practical consequence for #106/#132: **the coupon must be flat, rigid enough to stay flat in a vertical holder, and large.** A flexible printed skin on a thin substrate will need a backing frame, and the backing must not itself be reflective in an uncontrolled way.

### Deliverable format — the ADR-0013 question

This is the part #104 flags as open ("a free-space reflection-phase measurement is not obviously a 2-port S-parameter set"). It resolves cleanly:

- **A free-space normal-incidence reflection measurement is a one-port S-parameter measurement.** The VNA is calibrated (typically short-short-load using a metal plate at two offset positions, plus time-domain gating to reject room echoes — see [PMC8659499](https://pmc.ncbi.nlm.nih.gov/articles/PMC8659499/)), then records **S11 magnitude and phase versus frequency**. That is exactly a **Touchstone `.s1p`**. ADR-0013's Touchstone path works unmodified; `rf_tools/touchstone.py` needs no new format.
- **A free-space reflection *and transmission* measurement** (two horns, sample between them) is a genuine 2-port set — **`.s2p`** — and yields ε* and μ* by Nicolson-Ross-Weir. Only useful if the sample transmits; a metal-backed absorber does not.
- **An NRL-arch absorber reflectivity test returns reflectivity in dB versus frequency and no phase.** It is a difference of two power measurements. It is *not* a Touchstone file and will typically arrive as a plot plus a table or spreadsheet. This is what most absorber test houses sell by default.
- **What vendors actually say they produce:** Compass lists "**complex permittivity, permeability, sheet impedance, and/or S-parameters**" as the data delivered, and their software "acquires S-parameter data." Antenna Test Lab Co delivers **Excel spreadsheets**. IEEE Std 1128's revision is being rewritten around **"Vector Network Analyzers (VNAs) and S-parameter measurements, as they serve as the fundamental basis for most transmission and reflection measurements related to absorber testing"** ([AMTA 2023 paper](https://www.nsi-mi.com/-/media/project/oneweb/oneweb/nsi/files/technical-papers/2023/progress-on-the-development-of-the-isss-std-1128.pdf)) — so asking for raw S-parameters is squarely within current practice, not an odd request.

**Concrete wording for an enquiry:** *"Normal-incidence free-space reflection, 8–12 GHz, calibrated against a flat metal plate at the specimen position, time-domain gated. Please deliver calibrated S11 magnitude and phase as a Touchstone .s1p file in addition to any report, plus the calibration and gating parameters used."* Getting "in addition to any report" into the request is what prevents a PDF-only deliverable, which under ADR-0013 rides along as unparsed context and produces no structured `MEASURED` value.

---

## 6. The buy option, for comparison

X-band needs an instrument that reaches at least 12.4 GHz. That rules out essentially every low-cost VNA: the popular hobby and mid-range instruments (NanoVNA/LiteVNA class, Pico PicoVNA 108 at 8.5 GHz, Siglent SNA5000A at 8.5 GHz) all stop below the band. Above 12 GHz you are in the used-microwave-instrument market or paying new-instrument prices.

### Verified published prices (2026-09-03)

| Item | Price | Source |
|---|---|---|
| Agilent/HP **8720D**, 50 MHz–20 GHz, refurbished | **US$12,295** | [Test Equipment Depot](https://www.testequipmentdepot.com/agilent-hp-8720d-50mhz-20ghz-network-analyzer-refurbished.html) (via search summary) |
| Keysight/Agilent **8720ES**, 50 MHz–20 GHz, refurbished | **US$17,500** | [Liberty Test](https://libertytest.com/keysight-8720es-refurbished.html) |
| Agilent/HP **8720D**, used | **US$24,988** | [AccuSource Electronics](https://accusrc.com/product-Agilent-HP-8720D-8035) (via search summary) |
| **WR-90 waveguide horn antenna, 8.2–12.4 GHz, used ("pull")** | **US$104.90** | [RF Parts](https://www.rfparts.com/wr90-ha-p.html) (via search summary) |
| Copper Mountain **SC5065** (6.5 GHz — *below X-band*, listed for scale only) | US$15,995 MSRP | search summary |

`MANUFACTURER-SPECIFIED` for the dealer listings; the two marked "via search summary" were not directly fetched (the pages are JavaScript-rendered or 403) and should be confirmed before being relied on. **Flag: dealer stock and prices for 25-year-old microwave instruments move constantly.**

Auction-market prices for 8719/8720-series analysers are commonly reported well below dealer-refurbished prices, but no verifiable sold-price data was obtainable here. `UNKNOWN` — do not plan against a number that has not been seen.

### What a working bench actually costs

| Component | Realistic range | Note |
|---|---|---|
| VNA to ≥ 12.4 GHz (used/refurb) | US$8,000–25,000 | 8719D (13.5 GHz) is cheaper than 8720D/ES (20 GHz) and sufficient for X-band |
| Pair of WR-90 horns | US$200–3,000 | US$105 each used; new standard-gain horns from Pasternack/Fairview/Eravant are quote-only |
| Coax-to-WR-90 adapters, phase-stable cables | US$500–2,000 | |
| Calibration kit (3.5 mm or 2.4 mm) | US$1,000–5,000 | Used mechanical cal kits; TRL is the preferred method for free-space per NPL |
| Absorber, specimen frame, positioner, metal reference plate | US$1,000–5,000 | The unglamorous half; a free-space bench without absorber does not work |
| **Total** | **≈ US$13,000–30,000** | `CALCULATED` from the ranges above |

Focusing lenses or mirrors — which is what turns a 600 mm specimen requirement into a 180 mm one — are a further cost and are not commonly found second-hand.

### Rental

**Copper Mountain Technologies** moved its **C1220 2-port 20 GHz** VNA to rental-only after an end-of-sale on 2025-05-31, and runs a [VNA rental programme](https://coppermountaintech.com/vector-network-analyzer-rental/) covering the C1220, the C1420 (4-port, 20 GHz) and calibration kits. **No rental prices are published** — "Request a Quote." `MANUFACTURER-SPECIFIED`. General-purpose instrument rental houses (Electro Rent, TRS-RenTelco, TestWorld) also rent this class of analyser; none publishes rates.

### Send-out versus buy

| Route | Cost | What you get |
|---|---|---|
| One day, KU chamber, external + technician | ≈ **US$2,271** | Chamber time; you supply method and possibly fixture |
| One day, TAMU iEMSL chamber, assisted | ≈ **US$4,800** | Chamber + assistance + >10 GHz instruments |
| Commercial material house, per job | **Quote only** — no data | Turnkey, calibrated, traceable |
| Buy a used bench | **US$13,000–30,000** | Unlimited repeat measurements, plus the learning curve |

**The crossover is roughly 3–8 outsourced sessions.** `CALCULATED`. For a one-off validation of Example 3, send it out. For a **per-letter measured library** — which is #130/#131's whole differentiator and implies dozens of distinct panels measured repeatedly as the process changes — buying is the cheaper end state, and the alphabet's value proposition is what tips it.

---

## 7. Cheaper and alternative methods worth knowing

### 7.1 The waveguide simulator — the cheap method for periodic surfaces, with a real catch

#133 dismisses WR-90 on the grounds that its 22.86 × 10.16 mm aperture holds only ~7 × 3 cells at 3 mm pitch, "which is barely an array." **That reasoning is incomplete, and the correction matters.**

The **waveguide simulator** (Hannan & Balfour, IEEE Trans. AP, 1965 — primary source on IEEE Xplore, **stranded, 403**) exploits the fact that the metal walls of a waveguide act as **image planes**: a handful of cells inside the guide behaves electromagnetically like an *infinite* periodic array, because each wall reflects the cells into a virtual infinite lattice. Secondary summaries of the method state that "the number of elements that need to be constructed is small… such an array [is] well represented by the infinite array which results from imaging by the waveguide walls," and that in reflectarray practice "with only two elements inside the waveguide simulator, scattering response of the infinite array illuminated by plane waves is accurately achieved." It is documented specifically for reflectarray reflected-phase characterisation, with reported agreement to simulation within ~7% mean error. `INFERRED` — every primary source located (IEEE, ResearchGate, academia.edu) returned 403 or paywall here; the technique's existence and use are well attested across multiple independent secondary summaries, but no primary text was read.

> **Plain-language reading.** Put a few cells in a metal pipe. The pipe's shiny walls create mirror images of them, and the mirror images create images of the images, so the wave inside behaves as if it were hitting an endless field of identical cells — which is exactly the condition a metamaterial simulation assumes. You measure a stamp-sized sample and learn what an infinite surface would do.

**Two constraints, both arithmetic, both actionable:**

1. **The cells must fit the guide an integer number of times.** WR-90 is 22.86 × 10.16 mm — which is exactly **0.900 × 0.400 inch**. At a 3 mm pitch that is 7.62 × 3.39 cells: **non-integer, so the imaging is broken and the simulator is invalid**. But at **2.54 mm (0.100 inch) pitch it is exactly 9 × 4 = 36 cells**, and at 1.27 mm (0.050 inch) exactly 18 × 8 = 144 cells. `CALCULATED`. **Choosing a 2.54 mm pitch instead of 3 mm makes a WR-90 waveguide simulator exactly commensurate** — a free design decision now that unlocks a very cheap measurement later.

2. **The simulator represents oblique incidence, not broadside, and the angle sweeps with frequency.** The TE₁₀ mode in a guide of width *a* is the sum of two plane waves at angle θ to the axis where **sin θ = λ₀ / (2a)**. For WR-90 (*a* = 22.86 mm): **θ = 55.1° at 8 GHz, 41.0° at 10 GHz, 33.1° at 12 GHz**. `CALCULATED` from standard TE₁₀ mode theory. So a WR-90 simulator tells you how the surface behaves at a **33°–55° incidence that changes across the band** — it does *not* give you the broadside absorption curve that US12089385B2's Example 3 specifies.

**Net:** the waveguide simulator is the cheapest and smallest-sample route to a *periodic-surface* measurement, and it is the standard technique for reflectarray element phase. It is **not** a substitute for a broadside absorber reflectivity curve. For an alphabet of elements characterised by *reflected phase*, it is close to ideal. For validating Example 3's absorption, it is not.

### 7.2 Waveguide transmission/reflection (NRW) on a filled WR-90 section

The conventional WR-90 material measurement — a slab machined to fill the 22.86 × 10.16 mm cross-section, S11 and S21 measured, ε* and μ* extracted by Nicolson-Ross-Weir — is offered by Compass, MuEpsln, and most material labs, and needs only a **postage-stamp sample**. But it measures the **bulk properties of a homogeneous slab**, not the response of a *patterned* surface. It is the right tool for characterising the **substrate** (issue #114's Kapton/silicone/TPU question, where TPU has no X-band data of any provenance) and the wrong tool for characterising a metamaterial letter.

### 7.3 Resonant cavity methods

**ASTM D2520** resonant-cavity permittivity measurement is offered by Compass and NPL (split-post dielectric resonators, 1.8–14 GHz). Very accurate for **low-loss dielectrics** at **single spot frequencies**, tiny samples. Wrong tool for a broadband absorber, right tool for pinning a substrate's εr and tan δ at a couple of X-band points cheaply.

### 7.4 Low-cost free-space, done in-house

The NPL guide notes that unfocused normal-incidence free-space measurement can be done with "matched waveguide horns attached via coaxial cables to an ANA," and that "accurate measurements were performed with waveguide bridges… which may be considered as a cheaper option" (p. 125). With time-domain gating — which every modern VNA has, and which NPL calls "very useful for improving the accuracy of free-field measurements (especially unfocussed measurements)" — a two-horn bench in an ordinary room with some absorber is a real, documented method. That is the DIY end of the "buy the bench" option, and its main cost is the 600 mm specimen.

### 7.5 What is *not* an option

- **Simulating the fixture.** Modelling a free-space or WR-90 fixture predicts what a measurement would show; it produces `SIMULATED` data with extra steps. #133 is right that this is only worth building if measurement is genuinely coming.
- **Any instrument below ~12.4 GHz.** The cheap VNA market stops at 6–8.5 GHz. There is no low-cost shortcut into X-band.

---

## 8. Answering #133's decisions directly

**Does a realistic route to `MEASURED` X-band data exist?** Yes, and there are four of them, in increasing order of cost:

1. **WR-90 waveguide simulator** — smallest samples, cheapest, gives element reflected phase; but at 33°–55° incidence, not broadside, and requires a 2.54 mm pitch to be geometrically valid.
2. **University anechoic chamber, external user** — ≈ US$2,300–4,800/day published (KU, Texas A&M); needs a 180–600 mm coupon and probably your own fixture.
3. **Commercial material house** (Compass, MuEpsln, GTRI, NPL) — turnkey, focused-beam, delivers S-parameters; quote-only, needs a 180–600 mm coupon.
4. **Absorber test house NRL arch** (EMCTEST, ETS-Rantec) — cheapest turnkey absorber number, but **scalar reflectivity only, no phase**, and limited to about −40 dB.

**What provenance does a simulation on measured inputs carry?** Unchanged by this research: `SIMULATED`. But note that route 1 above changes the picture — a waveguide-simulator measurement of a *letter* is a genuine `MEASURED` reflected-phase datum for that letter, at oblique incidence, obtainable for the price of one day's chamber time or one small contract job. #130's per-letter measured library is **not** blocked on buying a VNA; it is blocked on a coupon-geometry decision and one purchase order.

**Coupon size, the decision that cannot wait.** The current 11 × 11 / 33 mm choice is measurable by **no method found in this research**: too small for free space by a factor of 5–20, and non-commensurate with WR-90. Two coupon families are needed, not one:

- **A waveguide-simulator coupon**, 22.86 × 10.16 mm, at **2.54 mm pitch** (9 × 4 cells exactly) or 1.27 mm (18 × 8).
- **A free-space coupon**, **≥ 225 mm square** to survive the 8 GHz end of the band with focusing optics, at whatever pitch the design wants. 75 × 75 cells at 3 mm.

**Whether the destination changes.** The map's "validated by reproducing Example 3" can become measured-agreement, not just simulated-agreement, for **US$2,300–5,000 and a 225 mm coupon** — provided the coupon is printed at that size. That is a smaller obstacle than #133 assumed, and it is a purchasing and printing decision rather than a capability gap.

---

## 9. What is stranded, and what is stale

**Stranded behind 403s to automated fetch — a human with institutional access should read these:**

| Source | Why it matters |
|---|---|
| Costanzo, Venneri, Borgia & Di Massa, *IJAP* 2019, [10.1155/2019/9479010](https://onlinelibrary.wiley.com/doi/10.1155/2019/9479010) (Wiley) | The map's cited authority for the 11 × 11 coupon. Abstract does not support the claim; full text unread |
| Costanzo et al., *IJAP* 2019, [10.1155/2019/4890710](https://onlinelibrary.wiley.com/doi/full/10.1155/2019/4890710) (Wiley) — "Modified Minkowski Fractal Unit Cell" | The other candidate for the 11 × 11 claim |
| Hannan & Balfour, "Simulation of a phased-array antenna in waveguide," IEEE Trans. AP, 1965 (IEEE Xplore) | Primary source for the waveguide simulator — everything in §7.1 rests on secondary summaries |
| IEEE Std 1128-1998 itself (IEEE Xplore / paywalled) | The actual sample-size and procedure requirements for absorber reflectivity testing |
| Ghodgaonkar, Varadan & Varadan free-space method papers (IEEE Xplore) | Primary source for the "3 × 3 dB beamwidth" specimen rule |
| ScienceDirect and MDPI metamaterial-absorber measurement papers | Independent confirmation of typical fabricated array sizes |

**Date-stamped and potentially stale:**

- All prices checked **2026-09-03**. Used-instrument dealer stock turns over weekly.
- **NIST SP 250 fee schedule retrieved is dated 2011** — service IDs and fees will have changed; the structural finding (no catalogued material measurement) is the durable part.
- **NPL Good Practice Guide is 2003.** Its physics — specimen size in wavelengths — does not age. Its equipment commentary does.
- **IEEE Std 1128 is under active revision**; the 2023 status paper says the title is changing to "30 MHz to 40 GHz" and the material-properties section is being greatly expanded to include the focused-beam free-space method. A revised standard may land with explicit X-band sample requirements.
- Copper Mountain's C1220 end-of-sale was **2025-05-31**; the rental-only status may change again.

**Not established in this pass (`UNKNOWN`, not "no"):**

- Lead times from any service. Nobody publishes one.
- Actual X-band sample size for Compass's focused beam (their range spans 2″–24″ without saying where X-band falls).
- Whether PTB or METAS sell material measurement.
- Ohio State ESL's external-access policy.
- Auction-market prices for 8719/8720-series VNAs.
