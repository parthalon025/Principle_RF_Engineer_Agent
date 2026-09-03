# Can MXene Be Printed on a Voltera NOVA for a US12089385B2-Style X-Band EM Skin?

**Research date:** 2026-09-03
**Scope:** Line width, film thickness, and conductivity achievable when printing Ti₃C₂Tₓ MXene ink on a Voltera NOVA Materials Dispensing System (pneumatic/mechanical extrusion, 1,000–1,000,000 cP, 100 µm minimum line width "dependent on material and nozzle," ±20 µm positioning, ≤40 °C material temperature, ≥10⁷ S/m single-pass spec for its own inks, 220×300 mm print area), for a pliable sub-2 mm-thick metamaterial film operating in X-band (8–12 GHz) as contemplated by US Patent 12089385B2.

## Bottom line up front

No one has published MXene printed on a Voltera NOVA or V-One. The closest published analog — a pneumatic three-axis extrusion dispenser using needle-metered MXene paste at Voltera-compatible viscosity — demonstrates **120 µm minimum line width**, room-temperature (no-anneal) as-printed conductivity of **6.26–6.9×10⁵ S/m**, and a **3 µm minimum gap** between adjacent fine features (a separate, tighter number from line width). At that conductivity, X-band skin depth is **~5.5–6.8 µm**, so a film needs on the order of **20–35 µm** (3–5 skin depths) to act as a low-loss conductor rather than a lossy sheet — achievable in a small number of extrusion passes, but no source reports MXene thickness-per-pass at a fine (100–200 µm) line width specifically, so the exact pass count on a NOVA is an extrapolation, not a measurement. Sintering is genuinely not required — this is the strongest, best-supported claim in the literature. Substrate compatibility is solid for PET/PDMS/glass/ceramic and demonstrated on curved and even biological surfaces; textile and TPU adhesion is comparatively unproven and flagged as a real risk.

---

## 1. MXene ink rheology versus the NOVA's 1,000–1,000,000 cP window

MXene ink viscosity spans roughly five orders of magnitude depending on formulation intent, and the literature is explicit that these are two different ink families for two different processes:

- **Inkjet-grade MXene inks** are dilute, low-viscosity, Newtonian-ish fluids — e.g., a 2026 direct-ink-write (DIW) paper on polyimide used an ink whose viscosity fell from **148 to 129 mPa·s (148–129 cP)** as shear rate rose from 100 to 900 s⁻¹ (Frontiers in Marine Science, 2026, DOI 10.3389/fmars.2026.1843170). That is **below** the NOVA's stated 1,000 cP floor — this specific ink would not be dispensable on the NOVA as formulated, despite being called "direct ink writing."
- **Extrusion/DIW-grade MXene inks** are viscoelastic pastes, shear-thinning, with storage modulus (G′) exceeding loss modulus (G″) — "solid-like" behavior needed to hold a printed filament's shape before it sets. Two directly relevant, quantified examples:
  - **Song et al., *Nat. Commun.* 13, 3223 (2022)**, "Room-temperature high-precision printing of flexible wireless electronics based on MXene inks" (DOI 10.1038/s41467-022-30648-2; open-access PMC9184614): ink viscosity **~2.5×10² Pa·s ≈ 250,000 cP**, shear-thinning, at **60 mg/mL** solids loading (>90% single-layer flakes, ~1.6 µm average flake size). **This sits squarely inside the NOVA's 1,000–1,000,000 cP window**, and the printer used — "a programmable three-axis pneumatic extrusion dispenser" with interchangeable needles — is mechanically the same class of machine as the NOVA (pneumatic/volumetric syringe dispensing through a needle, not inkjet).
  - **Zhao et al., *[EMI shielding DIW MXene frames]*** (open-access, PMC8219826): MXene/AlOOH pastes at **9–18 wt% solids (~98–196 mg/mL)**, shear-thinning with G′>G″, dispensed at 15–20 psi through a 410 µm needle on a three-axis DIW machine.

**Verdict:** extrusion-formulated MXene ink does fit the NOVA's viscosity window; it is the dilute inkjet-style formulations (not what a NOVA would use anyway) that fall outside it.

## 2. Achieved line width in published MXene extrusion/DIW printing

| Source | Nozzle/needle ID | Reported line width | Width : nozzle ID ratio |
|---|---|---|---|
| Song et al., *Nat. Commun.* 2022 (PMC9184614) | Not stated numerically in main text (small needles used) | **120 µm minimum** demonstrated; "standard" lines 2.5–3+ mm for bulk features | Not determinable from available text |
| Zhao et al., DIW MXene/AlOOH frames, EMI shielding (PMC8219826) | 410 µm | 400 ± 30 µm filament width | ~1.0 (line ≈ nozzle ID — unusually tight) |
| Frontiers 2026, DIW MXene on polyimide | Not specified | Programmed layer width/height: 200 µm | Not determinable |

The **finest demonstrated MXene extrusion-printed feature is the 120 µm line width in Song et al. (2022)** — on a pneumatic extrusion dispenser, not a Voltera. This is *above* the NOVA's advertised 100 µm floor, consistent with the NOVA's own caveat that 100 µm is "dependent on material and nozzle" — i.e., 100 µm is likely a best-case number for the NOVA's own low-viscosity silver ink through their finest (150 µm) Nordson EFD tip, not a guarantee for an arbitrary paste. Separately, the same paper reports a **3 µm minimum *gap*** between adjacent fine MXene lines/pads (0.43% spatial uniformity) — this is a different, tighter metric than line width (see §8) and represents state-of-the-art precision for room-temperature nanomaterial printing, achieved via a controlled dispensing/wetting strategy rather than simply shrinking the needle.

No source in this search reports MXene extrusion at line widths finer than 120 µm on any platform.

## 3. Film thickness per pass and total achievable thickness

This is the weakest-evidenced area. Numbers found:

- **Song et al. (2022):** states thickness scales linearly with number of printed passes/layers and achieved **6260–6900 S/cm conductivity with N=2** (two passes), but does **not** give a numeric per-pass thickness in the accessible text.
- **Zhao et al. DIW frames:** layer thickness ≈ **0.75 mm (3 layers), 1.35 mm (4 layers), 2 mm (6 layers)** → roughly 0.25–0.34 mm (250–340 µm) per pass. This is a coarse, macroscale lattice/frame structure printed through a 410 µm needle for a bulk EMI-shielding part, not a fine line on a thin flexible skin — the per-pass thickness here is not representative of a 100–200 µm fine-line trace, where far less material is deposited per pass.
- **Spray-coated (non-extrusion) MXene antenna films** for calibration/comparison: Solution-processed antennas at **1.0, 3.2, and 5.5 µm** thickness (PMC9119193); the 5.5 µm spray-coated film reached 99% radiation efficiency, competitive with 35 µm copper.

**Honest gap:** no source quantifies per-pass thickness for a *fine, 100–200 µm-wide extruded MXene line* the way it would be laid down on a NOVA. Reaching an X-band-relevant thickness (see §4/§8) for a *narrow* trace likely requires either multiple passes over the same path or a wider/taller single bead than the finest demonstrated line width — these two goals (finest line vs. thickest film) pull in opposite directions and no source optimizes for both simultaneously.

## 4. As-printed conductivity — not freestanding-film conductivity

Distinguishing printed/extruded traces from vacuum-filtered freestanding films (much denser, always higher-σ) and from spray-coated films:

| Method | Conductivity (as-fabricated) | Notes |
|---|---|---|
| Extrusion-printed, room temp, no anneal (Song 2022) | **6.26×10⁵ S/m** as-printed; **6.9×10⁵ S/m** after 4 h storage at ~10% RH (no heat) | Best-evidenced extrusion-printed number |
| DIW porous frame + AlOOH crosslink + freeze-dry (Zhao) | **4,119–5,323 S/m** | Two orders of magnitude lower — porous, freeze-dried lattice, not dense film |
| Spray-coated antenna film, PET substrate (PMC9119193) | ~1.5×10⁶ S/m measured; theoretical freestanding Ti₃C₂Tₓ up to 2×10⁶ S/m (20,000 S/cm) | Not extrusion; included for calibration |
| Blade-coated, vacuum-annealed 180 °C, 4 h (PMC9979651) | Up to 1.93×10⁶ S/m (19,325 S/cm) | Shows annealing benefit, but blade-coating ≠ extrusion, and 180 °C exceeds NOVA's 40 °C ceiling and most flexible-substrate limits |
| Frontiers 2026 DIW-on-polyimide | 0.307 S/m (3.07×10⁻³ S/cm) | Anomalously low vs. other extrusion work — likely a less-optimized/diluted formulation; flagged as an outlier, not representative |

**Realistic as-printed (room temperature, no anneal) ceiling for extrusion-printed MXene, based on the best-evidenced source: ~6–7×10⁵ S/m.** That is roughly an order of magnitude below the NOVA spec sheet's own ≥10⁷ S/m claim for its silver ink, and well below bulk metals, but still "metallic" by MXene's own literature standard.

## 5. Does MXene genuinely need no sintering?

Yes — this is the best-supported claim in the entire investigation. Song et al. (2022) state explicitly that their printed tracks reach **metallic conductivity (6,260–6,900 S/cm) "without annealing,"** at room temperature, and that a brief low-humidity storage step (not heat) is what pushes conductivity from 6,260 to 6,900 S/cm. This is presented as a deliberate contrast with metal-nanoparticle inks (silver, copper) that require 120–200+ °C sintering to fuse nanoparticles and burn off binder — MXene flakes are already-conductive 2D crystals that only need to be packed into intimate flake-to-flake contact via drying/mild densification, not fused. Mild treatment (10% RH storage, or elsewhere in the literature 180 °C vacuum annealing for blade-coated films) **substantially helps** conductivity but is optional rather than required for basic conduction — consistent with the task's instruction to report that honestly rather than overclaim "no benefit from heat at all." For a NOVA (≤40 °C material temperature) printing on PET (~80 °C limit) or TPU, this is the single most important enabling fact: MXene sidesteps the thermal ceiling that would rule out silver/copper inks on those substrates.

## 6. Anyone printing MXene on a Voltera specifically

**Nothing found.** Voltera's own NOVA product page lists named compatible inks (Creative Materials EXP 2613-40 gold ink, Celanese Micromax/Intexar PE874 stretchable silver paste, generic carbon/silver/copper inks) and a customer testimonial from an MIT researcher who printed **carbon nanotube inks** on the platform ("we've been able to print carbon nanotube inks and get field-emitted electrons") — the closest analog found to a low-dimensional nanomaterial ink on this machine class, but not MXene. Voltera's blog and material-partner content (e.g., the NovaCentrix Metalon partnership) likewise show no MXene mention. No paper found names Voltera V-One or NOVA in connection with MXene. This combination appears to be genuinely unpublished.

## 7. Substrate compatibility for the patent's flexible substrates (PET, polyimide, TPU, textile)

- **PET:** Well-demonstrated. Used as a MXene ink substrate in multiple sources (Song 2022; spray-coated antenna PMC9119193; blade-coated transparent films PMC9979651). Aqueous MXene ink is compatible; PET's ~80 °C thermal ceiling is irrelevant since MXene needs no high-temperature step.
- **Polyimide:** Demonstrated (Frontiers 2026 DIW paper), though that source is the outlier with unusually low measured conductivity and doesn't report adhesion testing — polyimide compatibility is directionally confirmed but not well-characterized quantitatively.
- **PDMS / curved and biological surfaces:** Song et al. (2022) print on PDMS, PVA, ferrite, and explicitly demonstrate printing on curved substrates and even on leaves and fruit — strong evidence for conformal application onto non-flat surfaces, directly relevant to the patent's "conforming to curved surfaces" requirement.
- **TPU and textile:** This is the weak point. No source found MXene extrusion-printed directly on TPU. For textile, the literature is explicit about a **real, unresolved adhesion problem**: "a major challenge in applying MXenes to fabric surfaces is achieving durable adhesion... weak interfacial bonding often results in poor wash fastness and limited long-term stability under mechanical deformation," driven by fiber roughness, chemical inertness, and porosity. Workarounds in the literature (e.g., atomic-layer-deposited Pt priming layers on textile to promote MXene ink adsorption) exist specifically *because* bare aqueous MXene ink does not reliably bond to textile — i.e., the problem is acknowledged as real enough to need a fix, not solved outright.

## 8. The 100 µm question, answered plainly

Line width and line-to-line gap are genuinely different constraints in this literature, and the gap is the tighter one:

- **Finest demonstrated MXene extrusion line width: 120 µm** (Song et al. 2022) — slightly above, not below, the NOVA's advertised 100 µm floor.
- **Finest demonstrated MXene feature *gap*: 3 µm** (same paper) — far below 100 µm, but this is a gap between printed pads/tracks achieved through a specific wetting/dispensing control strategy, not a general-purpose minimum line width.
- The NOVA's own 100 µm figure is explicitly qualified as "dependent on material and nozzle," using Nordson EFD 150–200 µm tips presumably with Voltera's own lower-viscosity, purpose-tuned silver ink (≥10⁷ S/m). MXene paste at the viscosity needed to hold a fine bead shape (~250,000 cP, per Song et al.) is a different rheological regime than whatever ink the 100 µm spec was measured with, and no source demonstrates sub-100 µm MXene lines on any extrusion platform.

**Realistic estimate for this machine with MXene paste: line widths in the 120–150+ µm range are the best-evidenced target, not the NOVA's advertised 100 µm floor** — achievable in principle given the ink sits inside the correct viscosity band and the demonstrated precision (3 µm gaps) shows the underlying dispensing physics can be controlled very tightly when optimized. Whether 100 µm itself is reachable on a NOVA specifically, with MXene specifically, is unverified either way — no source contradicts it, but none confirms it, and the one closest analog (a comparable pneumatic extrusion dispenser) achieved 120 µm as its finest reported number.

---

## Summary table

| Printing method | Nozzle ID | Line width | Thickness/pass | As-printed conductivity | Post-treatment needed | Source |
|---|---|---|---|---|---|---|
| Pneumatic extrusion (needle) | Not numerically stated | 120 µm min; 3 µm min gap | Not stated (N=2 passes → final result) | 6.26×10⁵ S/m (as-printed) → 6.9×10⁵ S/m (10% RH, 4 h, no heat) | None required; mild humidity conditioning helps | Song et al., *Nat. Commun.* 13, 3223 (2022), PMC9184614 |
| DIW extrusion (macro frame/lattice) | 410 µm | 400±30 µm | ~250–340 µm | 4,119–5,323 S/m (porous, post AlOOH crosslink + freeze-dry) | Freeze-drying, no thermal anneal | Zhao et al., EMI shielding MXene frames, PMC8219826 |
| DIW extrusion, low-viscosity ink | Not specified | 200 µm (programmed) | Not stated | 0.307 S/m (outlier — low) | Precursor powder dried 75 °C; no post-print treatment | Frontiers 2026, DOI 10.3389/fmars.2026.1843170 |
| Spray coating (not extrusion; reference only) | n/a | n/a (film, not line) | 1.0 / 3.2 / 5.5 µm | ~1.5×10⁶ S/m | None; RT | PMC9119193 |
| Blade coating (not extrusion; reference only) | n/a | n/a (film, not line) | 2.2 nm – 11.5 nm | Up to 1.93×10⁶ S/m | Vacuum anneal 180 °C, 4 h (boosts conductivity but exceeds NOVA's 40 °C and most flexible-substrate thermal limits) | PMC9979651 |

## Skin depth / electrical-thickness check at X-band

Using δ = 1/√(π f μ₀ σ), cross-validated against a literature-computed value (Nano Research, δ = 24.57 µm at f = 3.5 GHz, σ = 1.2×10⁵ S/m — confirmed, "Investigation of MXene nanosheets based radio-frequency electronics by skin depth effect," DOI 10.1007/s12274-023-6127-7, accessible only via search-result snippets — full text was 403/503-blocked from every route tried, so this is the one figure in the report sourced from a search snippet rather than a fetched page):

At the best-evidenced as-printed extrusion conductivity (σ ≈ 6.9×10⁵ S/m):

- δ(8 GHz) ≈ **6.8 µm**
- δ(10 GHz) ≈ **6.1 µm**
- δ(12 GHz) ≈ **5.5 µm**

This matches the task's own ~5 µm estimate closely. Using the conventional "3–5 skin depths for a good conductor/shield" rule of thumb, a printed MXene film would need roughly **17–34 µm** of thickness across X-band to be electrically thick — consistent with the task's 15–25 µm estimate. The spray-coated antenna literature (PMC9119193) independently supports this: a 5.5 µm MXene film already achieved 99% radiation efficiency at 16.4 GHz (comparable to 35 µm copper), and a separate source reports MXene RF films in the 8–128 µm range with an optimum near 12 µm — both suggest MXene may perform respectably even somewhat below the naive multi-skin-depth threshold, though neither of those two data points is at X-band specifically or from extrusion printing.

---

## What could not be verified

1. **Per-pass film thickness for a fine (100–200 µm-wide) extruded MXene line.** Every source with a thickness number is either a coarse macro-lattice (250–340 µm/pass through a 410 µm needle) or a non-extrusion process (spray/blade coating, nm-scale films). No source states "N passes of an X µm-wide MXene bead yields Y µm of thickness." The number of passes needed to reach 20–35 µm thickness *at a fine line width* on a NOVA is therefore an extrapolation from these two different regimes, not a measurement.
2. **The Orangi/Beidaghi extrusion-printable MXene ink paper** (*ACS Nano* 14, 640–650, 2020, DOI 10.1021/acsnano.9b07325) — the paper the task specifically flagged as a key primary source — could not be fetched in full text through any route tried (ACS Publications returned 403 directly; a USPTO-hosted PDF mirror of a related patent also 403'd; a ResearchGate mirror 403'd). Only the abstract-level claim that the ink "shows desirable viscoelastic properties for extrusion printing at room temperature" was confirmed; specific nozzle diameter, line width, and per-pass thickness numbers from that paper are **not verified here** and should be treated as an open item if this specific source is needed.
3. **The Nano Research skin-depth paper's full text** (DOI 10.1007/s12274-023-6127-7) was blocked (403 on Springer, 503 on a university PDF mirror). The δ = 24.57 µm @ 3.5 GHz figure used above for cross-validation came from a search-engine snippet, not a fetched page — it independently checks out against the standard skin-depth formula, but the paper's other claims (e.g., an "8–128 µm range, 12 µm optimal" antenna-thickness figure that appeared in a separate search snippet) could not be attributed to a specific, confirmed source and are reported with that caveat rather than as verified fact.
4. **MDPI-hosted sources** were avoided entirely per the known 403 bot-blocking in this environment; any MXene DIW work published in MDPI journals (Materials, Polymers, Micromachines, etc.) is therefore absent from this survey and could contain additional relevant data not captured here.
5. **Nozzle diameter for the single most relevant analog** (Song et al. 2022, the pneumatic extrusion dispenser achieving 120 µm lines) is not stated numerically in the accessible main text — only that "smaller needles" were used for the finest lines. Without this number, the line-width-to-nozzle-ID ratio (a key predictor for how a NOVA + Nordson EFD 150/200 µm tip would perform) cannot be computed for the best data point in this report.
