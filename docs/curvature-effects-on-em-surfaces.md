# What curvature actually does: bending, conformity and the three design methods

**Research date:** 2026-09-08
**Ticket:** bears on [#189](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/189) (printed conductor under bend strain); touches `rf_tools/patch_synthesis.py`'s curvature model and [`docs/local-periodicity-coupling-error.md`](./local-periodicity-coupling-error.md); part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104).
**Question:** How does bending to a radius of curvature change electromagnetic behaviour, separately for (a) continuous-dimension microstrip patches, (b) uniform periodic surfaces (FSS/metasurface), and (c) coded surfaces built from *mixed* unit cells — and how much curvature can a per-cell characterisation survive?

Every citation below is marked **retrieved** (the primary source was downloaded and read in this session), **figure-read** (the number was digitised from the published figure by rendering the PDF, with the stated tolerance), or **STRANDED** (identified, paywalled, not read — quoted from nothing). Nothing recalled from memory is presented as checked.

---

## Bottom line up front

**1. Yes — the sign of the patch frequency shift depends on the bend axis, and one paper measures both axes on the same antennas.** Boeykens, Vallozzi & Rogier (Ghent, 2012) bend five textile patches over plastic cylinders from **90 mm down to 31.5 mm radius** and measure both directions:

| Bend axis | Pure conformal geometry (rigid model) | Measured on a real deformable antenna |
|---|---|---|
| **Resonant length wrapped** (E-plane bend) | **+2.6%** (1.5665 → 1.6075 GHz) | **+0.58%** (1.5505 → 1.5595 GHz) |
| **Non-resonant width wrapped** (H-plane bend) | **exactly zero** — the model line is flat | **−0.42%** (1.5335 → 1.5270 GHz) |

*In plain terms:* bend the patch so that the direction the current runs is the one that gets curved, and the tone it rings at goes **up**. Bend it the other way, leaving the current's path straight, and pure geometry does nothing at all — the only thing left is the substrate being squashed, which pushes the tone **down**. Opposite signs, and different mechanisms rather than just different sizes.

**2. This repo's own curvature formula gets the sign right for one axis and is roughly 7–9× too large in magnitude.** `rf_tools/patch_synthesis.py` predicts `f_curved = f_flat · L/(2R·sin(L/2R))`, i.e. `Δf/f ≈ L²/(24R²)`. For Boeykens' prototype 3 (resonant length 69.3 mm) at R = 31.5 mm that is **+20.2%**; the measured/modelled cylindrical cavity gives **+2.6–3.0%**. The formula also has no substrate thickness in it, and applies the same correction to *both* bend axes where the cavity model gives zero for one of them. §1.5.

**3. For a checkerboard or 1-bit coding surface the whole phase budget is ±37°, and two independent routes agree on it.** Wu et al. derive from the cancellation equation that 10 dB RCS reduction requires the two cells' reflection phases to differ by **180° ± 37°**; Shabanpour, Tretyakov & Simovski independently adopt **±40°** as their practical criterion. *Plainly: the two tile types have to stay roughly half a wave out of step with each other, and you may drift about a tenth of a wave before the trick stops working.* That is the entire error budget curvature must share with everything else — including the **12°–85°** neighbour-coupling errors this repo already documented in `local-periodicity-coupling-error.md`. §3.1.

**4. The curvature a periodic surface tolerates is set by its element's angular stability, not by the radius.** On a cylinder the local incidence angle is exactly `θ(s) = s/R` (arc distance over radius). Khan et al. state the link outright: their coding metasurface holds 10 dB RCS reduction up to a **central angle of 90°** *because* the meta-atom is stable to **45° incidence** — and 90°/2 = 45°. The design rule that falls out is `S ≤ 2·θ_max·R`: **usable arc length = twice the element's angle limit times the radius**. Shabanpour et al. give measured θ_max values: **≈60°** for an angle-stable Jerusalem-cross cell, **<30°** for a mushroom/high-impedance cell. §4.

**5. For #189, the printed-conductor numbers that exist are these** — and none of them is carbon on silicone:

| Material | Condition | Result | Status |
|---|---|---|---|
| Screen-printed silver (Asahi LS411AW) on 125 µm PET | 10 mm radius, 30,000 cycles (≈0.63% outer-fibre strain) | 13 Ω → **25.4 Ω (+95%)**; recovers to 12.6 Ω after a 150 °C/20 min re-anneal | measured |
| Screen-printed silver (DuPont 5064H), same test | same | 17.7 Ω → **29.6 Ω (+67%)**; anneal only returns it to 19.6 Ω; opens start at **8,000 cycles** | measured |
| Ti₃C₂Tₓ MXene grid film | 5,000 bending cycles at 180° | **ΔR_s = +9.5%** (from 4.32 Ω/sq) | measured |
| Direct-written CNT lines on paper | radius down to **1 mm** | **<3%** resistance change; **<5%** after 1,000 cycles | measured |

*Plainly: a printed silver mirror can double its resistance under a very gentle bend repeated tens of thousands of times and nobody would notice, because a mirror only has to reflect. A printed carbon resistor doing the same thing would move its design value by a factor of two — and #189's design puts all its dissipation in one carbon bridge.* §5.

**6. The sources disagree about the sign for E-plane bending, and the disagreement is not resolved.** Boeykens (measured, 1.57 GHz textile) says **up**; Zhang et al. (measured + calculated, 5.8 GHz polyimide) says **down, −6.91%** at a 35° E-plane bend; Zaidi et al. (1.575 GHz textile) says **up** in its prose while its own Figure 6 shows every bent curve **below** the flat one. §6.

---

## 0. One piece of geometry that runs through all three answers

Three relations do most of the work below. All three are plain geometry, derived here rather than quoted, and flagged as such.

**(i) Local incidence angle.** Wrap a flat sheet onto a cylinder of radius `R`. A cell sitting an arc distance `s` from the crown is tilted by

```
    θ(s) = s / R          (radians)
```

so a plane wave arriving along the crown normal hits that cell at `θ` off-normal. Ali et al. write exactly this as `θ_c1 = S/R_c` for their conformal FSS ([Sci. Rep. 2025, §"Model utilized for analyzing the flexible FSMS"](https://doi.org/10.1038/s41598-025-07696-x), retrieved). *Plainly: on a curved skin no two tiles see the wave from the same direction, and the disagreement grows one degree for every R/57 mm you walk along the surface.*

**(ii) Arc versus chord — and why it is the same mechanism twice.** Bending (as opposed to stretching) preserves the arc spacing `p` between neighbouring cells. What changes is the spacing **as projected onto the incoming wavefront**:

```
    p_projected = p · cos θ(s)
```

That projection is precisely what oblique incidence does to a flat array. **So "effective periodicity changes" and "local incidence angle changes" are not two mechanisms — they are one mechanism described twice.** The genuinely separate mechanism is the *physical* inter-element gap, and pure bending does not change it at all. It changes only if the surface stretches, or if a flat layout is projected onto a curve without redrawing the elements (§2.2).

**(iii) Outer-fibre bend strain.** For a stack of total thickness `T` bent to radius `R`,

```
    ε = T / (2R)
```

which is the relation already used in [#189](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/189). At R = 10 mm and T = 125 µm this is 0.63%; at R = 4.6 mm and T = 1.527 mm it is 16.6%.

---

## 1. (a) Microstrip patches: does the sign flip with the bend axis?

### 1.1 The source that answers it

**F. Boeykens, L. Vallozzi and H. Rogier, "Cylindrical Bending of Deformable Textile Rectangular Patch Antennas", *International Journal of Antennas and Propagation* **2012**, Article ID 170420, 11 pp. DOI [10.1155/2012/170420](https://doi.org/10.1155/2012/170420).** Open access (CC-BY). **Retrieved and read in full this session** (Hindawi and Wiley both 403; a Wayback Machine copy of the publisher PDF served it).

This is the right paper because it does three things nobody else in this pass does at once: it separates the mechanisms analytically, it measures **both bend axes on the same five antennas**, and it says explicitly what the earlier literature had *not* done:

> "Cylindrical bending of deformable textile antennas has been an important subject in recent papers, but exclusively from an experimental point of view [4, 5, 14–16]. The general conclusions drawn from these contributions are that bending causes an upward shift of the resonance frequency … Yet, these studies are rather qualitative and do not provide physical insight into the complex mechanisms occurring due to antenna bending." — §1, verbatim

**Setup.** Five prototypes; aramid and cotton substrates (ε_r 1.715–1.75, h = 2.0–4.05 mm); patch materials both stretchable (Flectron electro-textile) and non-stretchable (copper foil); 1.57 GHz GPS band and 2.45 GHz ISM. Bent over **plastic cylinders of radius 31.5 mm to 90 mm** ("These radii resemble typical curvatures of human body parts"), measured on a PNA-X vector network analyser.

**Geometry, from §2.1 verbatim:** "The cavity is bounded by electric walls at ρ = a and ρ = a + h and magnetic walls at φ = ±β/2 and z = ±L/2." So **`W` is the wrapped (circumferential) dimension and `L` is the straight (axial) one.** The paper then maps the two experiments:

> "When the antennas are bent in the W_p direction, the model is used by setting L = L_p and W = W_p. According to the model, the TE10 mode is then excited … Similarly, when bending the antennas in the L_p direction, one has to set L = W_p and W = L_p. According to the model, the TM01 mode is then excited."

### 1.2 Which patch dimension is the resonant one — and therefore which case is "E-plane"

The paper never uses the words "E-plane" or "H-plane", so the mapping is an inference, made here and marked as such. Three independent checks agree that **W_p is the resonant dimension**:

1. **Sizing.** Prototype 3: L_p = 78.5 mm, W_p = 69.3 mm, ε_r = 1.715, target 1.57 GHz. A half-wave at 1.57 GHz in ε_eff ≈ 1.7 is 73 mm before fringing shortens it to about 70 mm — W_p, not L_p.
2. **The feed.** "All prototypes are fed by a probe feed structure, with the probe located on the perpendicular bisector of the L_p edge" — i.e. the feed offset runs along W_p, which is where a patch feed offset belongs.
3. **The model's own behaviour.** In the L_p-bend case (Fig. 5) the uncompressed model line is *flat* — the resonance does not care about the radius. That can only be true if the resonant dimension is the one lying along the untouched cylinder axis, which in that case is W_p.

So: **Figure 4 = the resonant length is wrapped = E-plane bending. Figure 5 = the non-resonant width is wrapped = H-plane bending.**

### 1.3 The numbers

Read by rendering the published PDF at 5× and reading the plotted markers against the axis gridlines. **Figure-read; treat as ±0.002 GHz (±0.13%).** Both figures are prototype 1 (stretchable Flectron patch, aramid) and prototype 3 (non-stretchable copper foil, 2.7 mm cotton).

| Case | Curve | R = 90 mm | R = 31.5 mm | Change |
|---|---|---|---|---|
| **E-plane bend** (Fig. 4) | Prot. 3, model with ε_r,flat — *rigid conformal, no compression* | 1.5665 GHz | **1.6075 GHz** | **+2.6%** |
| | Prot. 3, **measured** | 1.5505 GHz | 1.5595 GHz | **+0.58%** |
| | Prot. 1 (stretchable), **measured** | 1.5690 GHz | 1.5695 GHz | **≈0%** (<0.05%) |
| **H-plane bend** (Fig. 5) | Prot. 3, model with ε_r,flat | 1.5335 GHz | 1.5335 GHz | **0.0%** (flat line) |
| | Prot. 3, **measured** | 1.5335 GHz | 1.5270 GHz | **−0.42%** |
| | Prot. 1 (stretchable), **measured** | ~1.5655 GHz | ~1.5655 GHz | **≈0%** |

The paper's own words for the H-plane case, verbatim:

> "According to the model, the resonance frequency of prototype 1 does not vary since no compression occurs and the resonant length is not bent in TM_z mode. For prototype 3, a decrease in resonance frequency now occurs for smaller bending radii. **This effect is purely due to compression of the substrate**, which can also be noticed by comparison with the curve obtained from the model without compression correction, where the resonance frequency does not change."

### 1.4 Three mechanisms, not one — and they fight each other

This is the payload of the paper and the part most useful to this programme.

| Mechanism | What it does | Sign of Δf | Turned off when… |
|---|---|---|---|
| **Conformal geometry** (cylindrical cavity dispersion) | changes the resonant path the cavity mode sees | **up** | the resonant dimension is not the wrapped one → **exactly zero** |
| **Patch stretching** | the conductor elongates, so the resonant length grows | **down** | the conductor is non-stretchable |
| **Substrate compression** | the squashed substrate's permittivity rises (`ε_r,comp = ε_r,flat·(1 + ηh(d−0.5)/a)`, their Eq. 29) | **down** | the patch is perfectly stretchable (then d = 0.5 and the term vanishes) |

The stretchable prototype 1 is the clean demonstration: its resonance **does not move at all** from R = 90 mm to R = 31.5 mm, in either bend direction, because stretching and compression both switch off together. *Plainly: an antenna printed on something that stretches with the bend barely notices being bent; one printed on something that squashes instead does.*

How big is the compression term on its own? Their Table 3 and Table 4 give the mean error when it is ignored, averaged over all the cylinders:

| | Prot. 1 | Prot. 2 | Prot. 3 | Prot. 4 | Prot. 5 |
|---|---|---|---|---|---|
| E-plane bend, τ(0) — compression ignored | 0.09% | 1.56% | 1.97% | 1.94% | **2.91%** |
| H-plane bend, τ(0) | 0.04% | 0.37% | 0.23% | 0.76% | **1.28%** |
| Either, τ(η) — compression modelled | 0.09% | 0.03% | 0.09% | 0.07% | 0.12% |

*Plainly: ignore the fact that the fabric gets squashed and you will be wrong by up to about 3% in frequency; model it with one fitted constant and you are wrong by about a tenth of a percent.* Note that τ(0) is largest for prototype 5, the thickest substrate (4.05 mm) — the compression term scales with `h`.

### 1.5 What this says about `rf_tools/patch_synthesis.py`

The repo's model (module notes under "Curvature-induced resonant-frequency shift") treats the resonance as set by the **chord** between the radiating edges:

```
    f_curved = f_flat · L / (2R·sin(L/2R))     ⇒   Δf/f ≈ L²/(24R²)
```

Against Boeykens' prototype 3 (resonant length L = W_p = 69.3 mm, h = 2.7 mm):

| R | Repo formula | Boeykens conformal-geometry model | Boeykens measured |
|---|---|---|---|
| 31.5 mm | **+20.2%** (guard rejects: L/R = 2.20 > 0.5) | +2.6% (vs R = 90 mm) | +0.58% |
| 90 mm | **+2.47%** (guard rejects: L/R = 0.77 > 0.5) | reference point | reference point |
| 139 mm (guard boundary, L/R = 0.5) | **+1.04%** | curve already flat at this radius | — |

Three findings, all derived here from the published numbers:

- **The sign is right for E-plane bending.** Both say the frequency goes up. The repo's module note that it "does not capture bend-axis-dependent sign reversals" is honest and correct — this document supplies the reversal it was flagging.
- **The magnitude is roughly 7–9× too large.** Fitting Boeykens' red curve to `Δf/f = C/R²` gives C ≈ 30 mm²; the repo's formula has C = L²/24 = 200 mm².
- **It has no substrate thickness in it.** The cavity model's curvature term depends on `h` (the mode lives between ρ = a and ρ = a + h) and its compression term depends on `h` explicitly. A formula in `L` and `R` alone cannot reproduce either.

**What it is still good for:** an order-of-magnitude "does curvature matter here at all?" screen. Inside its own guard (`L/R < 0.5`) its maximum prediction is +1.04%, which for a patch with 2% impedance bandwidth is half a bandwidth — the right order to warn about, the wrong number to design to.

### 1.6 The other patch sources

**Zhang, Huang, Sun, Meng, Zhang & Zhao, "Analysis Method of Bending Effect on Transmission Characteristics of Ultra-Low-Profile Rectangular Microstrip Antenna", *Sensors* **22**(2), 602 (2022). DOI [10.3390/s22020602](https://doi.org/10.3390/s22020602).** Open access; **retrieved** (via PubMed Central).

Polyimide film, 0.254 mm thick, ε_r = 3.6; patch 13.5 × 17 mm; 5.8 GHz. E-plane bending only, expressed as bend **angle** rather than radius. Their calculated resonance:

| E-plane bend angle | 0° | 5° | 10° | 15° | 20° | 25° | 30° | 35° |
|---|---|---|---|---|---|---|---|---|
| Resonant frequency (GHz) | 5.79 | 5.75 | 5.73 | 5.64 | 5.60 | 5.53 | 5.49 | **5.42** |

**−6.91% at 35°.** Validated against HFSS (max error 0.92%) and against VNA measurement on 9 samples (max difference 0.55%). Their stated mechanism, verbatim: *"E-plane bending affects the current path, especially for the fundamental mode of resonance. Simultaneously, the curved patch also changes the fringe field of the radiating edge, thereby affecting the effective dielectric constant."* They also state, verbatim, *"E-plane bending more significantly influences the frequency of patch antennas than H-plane bending"*, but publish **no H-plane data**. **This is the opposite sign to Boeykens for the same bend axis — see §6.**

**"Dual-Band Bent Sensing Textile Antenna Under Dual-Mode Resonance", *Sensors* **25**(24), 7511 (2025). DOI [10.3390/s25247511](https://doi.org/10.3390/s25247511).** Open access; **retrieved**. Flannel substrate 0.8 mm, ε_r = 1.3, copper tape; bent over cylinders **R = 30 mm to 80 mm**; measured. Both bands shift **downward** for smaller R — verbatim: *"the center resonant frequencies of both operating modes exhibited consistent trends of change (i.e., frequency shifts toward lower frequencies for smaller R)."* Magnitude at R = 30 mm: **75 MHz at 2.45 GHz (−3.1%)** and **105 MHz at 5.8 GHz (−1.8%)**. Sensitivities **1.1 MHz/mm** and **1.78 MHz/mm** of radius. Bending about the y-axis (perpendicular to the current) shifts more than about the x-axis.

**N. I. Zaidi et al., "Analysis on different shape of textile antenna under bending condition for GPS application", *Bulletin of Electrical Engineering and Informatics* **9**(5), 1964–1970 (2020). DOI [10.11591/eei.v9i5.2185](https://doi.org/10.11591/eei.v9i5.2185).** Open access; **retrieved**. Three patch shapes on e-textile, 1.575 GHz, bent over cylindrical foam of **42.5 mm radius** (≈135° wrap), both E- and H-plane, simulated and measured.

Its prose says, verbatim: *"When the bending angle of the antenna increases, the effective length is decreased and the resonant frequency will shift to a higher band [22]."* **But its own Figure 6(a) shows the opposite.** Figure-read from the published PDF at 8× (Design 1, rectangular patch, x-axis 1.0–2.0 GHz; **±0.02 GHz**): flat simulated ≈1.57 GHz, H-plane bent simulated ≈1.54 GHz, E-plane bent simulated ≈1.52 GHz; flat measured ≈1.50 GHz, E-plane bent measured ≈1.38 GHz. **Every bent curve sits below the flat one**, E-plane furthest. The "[22]" the claim rests on is Song & Rahmat-Samii — see immediately below. Recorded as a source whose figures contradict its own text; the figures are evidence and the text is not.

**L. Song and Y. Rahmat-Samii, "A Systematic Investigation of Rectangular Patch Antenna Bending Effects for Wearable Applications", *IEEE Trans. Antennas Propag.* **66**(5), 2219–2228 (2018). DOI [10.1109/TAP.2018.2809469](https://doi.org/10.1109/TAP.2018.2809469).** **STRANDED.** This is the canonical primary source for the E-plane/H-plane question, it is the reference the wearable literature chains back to, and it could not be retrieved: IEEE Xplore returns HTTP 418 to automated fetches, Semantic Scholar reports `openAccessPdf: CLOSED`, and no author copy or dissertation chapter surfaced. **No number from it is quoted anywhere in this document.** Getting it is the single highest-value follow-up on sub-question (a).

---

## 2. (b) Uniform periodic surfaces: FSS and single-cell-type metasurfaces

### 2.1 What conforming does, and what it does not

Two mechanisms are usually blamed for conformal FSS degradation. Only one of them is caused by curvature as such.

**Mechanism A — local incidence angle / projected periodicity.** Real, unavoidable, and quantified in §4. This is §0(i) and §0(ii), which are the same thing.

**Mechanism B — element distortion.** *Not* caused by curvature; caused by **projecting a flat artwork onto a curved surface without redrawing it.** Álvarez et al. designed around it deliberately:

> "The slots are designed as arcs in the sphere for **having the radial periodicity and dimensions equal to the planar unit cell** … the slots are made directly on the sphere using radial arcs instead of projecting the planar dipole slot structure into a sphere, so that the radial length of the slots can be directly controlled."

and describe what happens when you do not:

> "…a bandstop conformal FSS that was realized by using screen printing (with a conformal mask) … was reported in [35], but **the resonant frequency of the FSS was shifted and the stop band bandwidth enlarged** when compared with its electromagnetically simulated infinite planar counterpart. This was due to the **distorted FSS elements** on the curved surface **and the oblique incident angles**."

— H. F. Álvarez, D. A. Cadman, A. Goulas, M. E. de Cos Gómez, D. S. Engström, J. C. Vardaxoglou & S. Zhang, "3D conformal bandpass millimeter-wave frequency selective surface with improved fields of view", *Scientific Reports* **11** (2021). DOI [10.1038/s41598-021-91218-y](https://doi.org/10.1038/s41598-021-91218-y). Open access; **retrieved**. Both quotes verbatim.

*Plainly: bending a printed sheet does not stretch the shapes on it. But if you take a flat drawing and wrap it onto a dome by projection — the way a map of the world gets stretched near the poles — you have changed the shapes, and the resonance moves for that reason alone. Draw the elements on the curved surface in the first place and that error disappears; only the tilt remains.*

**This matters directly for this programme.** A design produced flat and then printed on a curved former inherits mechanism B. A design whose geometry is generated *on* the curved surface — which is what `agent/main.py`'s flat-vs-conformal geometry preparation step exists to do — does not.

### 2.2 What is measured, on a real curved FSS

Álvarez et al.'s spherical dome (50 mm spherical radius, 80 mm aperture, 6 mm periodicity, Ka-band, 3D-printed PLA + copper electroplating, **measured**):

- Conformal FSS: **−3 dB passband bandwidth ≈11% at a stable centre frequency of ≈32.5 GHz**, preserved to **30° of rotation** (TE) and **20°** (TM); −5 dB bandwidth to **45°** (TE) and **30°** (TM).
- Finite **planar** FSS of the same 80 mm diameter in the same near-field setup: steady −3 dB passband only to **≈5°** in both polarisations.
- The infinite periodic planar reference (Floquet, normal incidence): centre 32.6 GHz, ≈10% bandwidth.

**The conformal surface is closer to the infinite-planar ideal than the equal-sized flat one is.** *Plainly: in a near-field setup a dome-shaped filter behaves more like the textbook infinite sheet than a flat filter of the same size does, because the dome presents roughly the same tilt to every ray coming out of the feed while the flat one does not.*

Ali, Riaz, Malik, Shafique & Koziel, "Ultra-miniaturized capacitive loaded conformal frequency selective metasurface for S, C, and X band applications", *Scientific Reports* (2025), DOI [10.1038/s41598-025-07696-x](https://doi.org/10.1038/s41598-025-07696-x). Open access; **retrieved**. A 41 × 27 element, **229 × 152 mm** panel at 10 GHz, wrapped on polystyrene formers and measured:

- Simulated, conformed to a **180° arc**: verbatim, *"Both responses are consistent with little shift in the resonant frequency; however, the bandwidth remains the same thus depicting the stable response."*
- Measured at **R_c = 300 mm** and **R_c = 150 mm**: verbatim, *"the resonant frequency is intact, but with increasing incident angle, the stopband rejection decreases, and a slight shift towards a higher frequency is observed."*

Derived here from their own `θ_c1 = S/R_c`: at R_c = 150 mm the 229 mm panel subtends **1.53 rad = 87.5°**, so its cells span **±44° of local incidence** — and the resonance survives. That is a concrete curvature tolerance for a miniaturised X-band FSS, expressed the way §4 wants it.

### 2.3 The mutual-coupling mechanism, with a number

The same paper measures how much the resonance depends on inter-element spacing at all — which is the scale against which any coupling change must be judged:

> "The decrease in neighbouring UE spacing increases the mutual capacitance, hence decreasing the resonance frequency. … Fig. 7(b) shows that the resonant frequency is around **12 GHz** when the spacing between the neighbouring UEs is large, representing the standalone resonance of a UE … In the case of close neighbouring UEs, the resonance is shifted to a lower frequency [**10 GHz**]." — verbatim

**Mutual coupling between neighbours is worth about 2 GHz out of 12, i.e. ~17% of the resonant frequency**, for this element at this pitch. Their equivalent circuit puts numbers on it: L = 0.65 nH, intra-element C_ia = 0.125 pF, **inter-element C_ie = 0.265 pF** — the coupling capacitance is *twice* the element's own.

**Now combine with §0(ii).** Bending preserves the physical arc gap between neighbours, so it does not change `C_ie`. Only stretching, or projecting a flat artwork onto a curve, does. **So for a bent (not stretched) FSS, the mutual-coupling channel is essentially closed and the local-incidence channel carries the whole effect.** *Plainly: bending a sheet doesn't move the tiles further apart along the sheet, so it doesn't change how strongly they talk to each other; it only changes the angle each one is presented at.* This is a mechanism separation, derived here from the two cited facts, not a quoted result — see §7.

---

## 3. (c) Coded and checkerboard surfaces built from mixed cells

This is the programme's main path, so this section carries the design rule.

### 3.1 The phase budget: 180° ± 37°, from two independent directions

**G. Wu, W. Yu, T. Lin, Y. Deng & J. Liu, "Ultra-Wideband RCS Reduction Based on Non-Planar Coding Diffusive Metasurface", *Materials* **13**(21), 4773 (2020). DOI [10.3390/ma13214773](https://doi.org/10.3390/ma13214773).** Open access; **retrieved**. Verbatim:

> "From Equation (3), it can be figured that, to get 10 dB RCS reduction, the phase difference between the unit cells should vary from **143° to 217°**, to satisfy **180° ± 37°** phase difference."

The arithmetic, reproduced here as a check: for two equal-amplitude cells the reduction is `−20·log₁₀|cos(Δφ/2)|`; setting that to 10 dB gives `|cos(Δφ/2)| = 10^(−0.5) = 0.3162`, `Δφ/2 = 71.55°`, `Δφ = 143.1°` or `216.9°`. It matches exactly.

**Independently:** J. Shabanpour, V. Lenets, G. Lerosey, S. Tretyakov & C. Simovski, "Engineering of Intelligent Reflecting Surfaces: Reflection Locality and Angular Stability", *IEEE Trans. Antennas Propag.* **72**(5) (2024), DOI [10.1109/TAP.2024.3375659](https://doi.org/10.1109/TAP.2024.3375659); preprint [arXiv:2308.10589](https://arxiv.org/abs/2308.10589), **retrieved**. Verbatim:

> "The practical requirement for the closeness of ∆Φ_R to ideal 180° was defined as the **maximal allowed deviation of ∆Φ_R from 180° equal to ±40°**."

Two groups, different problems (RCS reduction versus beam steering), different years, arriving at ±37° and ±40°. **Take ±37° as the budget; it is the derivable one.**

**And the budget is already largely spent.** [`docs/local-periodicity-coupling-error.md`](./local-periodicity-coupling-error.md) records, from Costanzo, Venneri & Di Massa, per-element phase errors of **12° (best case) to 85° (worst case)** from unlike neighbours alone, at 0.4λ pitch and X-band. At 0.5λ pitch the same table gives 25° / 21° / 12° for square-patch, Minkowski and modified-Minkowski cells. *Plainly: the total error allowance for the whole design is about a tenth of a wave, and just having differently-shaped neighbours can eat all of it before curvature is even considered.* Curvature is the third claimant on a budget that two claimants can already exhaust.

### 3.2 Curvature versus RCS reduction: what has been simulated and measured

**H. A. Khan, U. Rafique, S. M. Abbas, F. Ahmed, Y. Huang, J. A. Uqaili & A. Mahmoud, "Polarization-Independent Ultra Wideband RCS Reduction Conformal Coding Metasurface Based on Integrated Polarization Conversion-Diffusion-Absorption Mechanism", *Photonics* **10**(3), 281 (2023). DOI [10.3390/photonics10030281](https://doi.org/10.3390/photonics10030281).** Open access; **retrieved** (MDPI's HTML is 403 to automated fetches; the article PDF on `mdpi-res.com` served it).

Rogers RT/Duroid 5880, PB-phase "0"/"1" meta-atoms of identical size and different orientation. **Simulated only for the conformal cases; no conformal measurement.**

- Planar (central angle α = 0): **>10 dB RCS reduction from 10.8 to 31.3 GHz**, 97% fractional bandwidth.
- Conformally bent to central angles **α = 30°, 60°, 90°**: verbatim, *"the RCS reduction bandwidth is almost completely sustained up to central angles of 90 degrees for conformal metasurfaces **since the performance of the proposed meta-atom is stable up to an incidence angle of 45°**."*
- Their statement of the mechanism, verbatim: *"the surface is curved so that EM waves are incident obliquely, which will affect the reflection phase characteristics of an incident wave and result in a decrease in RCS reduction performance."*

**That single sentence is the design rule.** A central angle of 90° puts the edge cells at 45° of local incidence, which is exactly the element's stability limit. §4 generalises it.

**Q. Chang, J. Ji, K. Chen, W. Wu & Y. Ma, "Transparent and Ultra-Thin Flexible Checkerboard Metasurface for Radar–Infrared Bi-Stealth", *Sensors* **24**(5), 1531 (2024). DOI [10.3390/s24051531](https://doi.org/10.3390/s24051531).** Open access; **retrieved**. ITO-on-PET checkerboard, two cell sizes (p₁ = 2 mm, p₂ = 8 mm) in a P = 80 mm super-period, total thickness 1.6 mm.

- Planar: **10 dB RCS reduction, 10.6–19.4 GHz**; backscatter at 11.8 GHz −19 dB (PEC −0.9 dB), at 16.8 GHz −25 dB (PEC +2.2 dB).
- Cylindrically curved through **curvature angles γ = 5°, 10°, 15°, 20°** (simulated): *"When γ is less than 15°, an RCS reduction of approximately 10 dB can still be achieved in the frequency range of 11–19 GHz."* Their stated mechanism, verbatim: *"This is because **the curvature changes the impedance match of the base unit, thereby changing the reflection amplitude and phase**."*
- **Measured**, TE, normal incidence, at γ = 20° versus flat: *"although there are differences between the experimental results and the simulation results, the overall trend of change is basically consistent."*

**A trap, worth naming.** At γ = 10° the paper reports backscatter of **+0.9 dB (PEC) and −12.8 dB (metasurface)**; at γ = 20°, **−0.4 dB (PEC) and −25 dB (metasurface)**. The metasurface number gets *better* at the larger bend while the *reduction* curves get worse. Both are true, because the PEC reference is also curving. *Plainly: a curved plate scatters less straight back at you than a flat plate does, whatever is printed on it — so some of the "RCS reduction" you measure on a bent panel was bought by the bend and not by the design. Any figure of merit has to be quoted against an equally-bent reference, and this paper does that; a careless one would not.*

**Y. Zhang, L. Liang, J. Yang, Y. Feng, B. Zhu, J. Zhao, T. Jiang, B. Jin & W. Liu, "Broadband diffuse terahertz wave scattering by flexible metasurface with randomized phase distribution", *Scientific Reports* **6**, 26875 (2016). DOI [10.1038/srep26875](https://doi.org/10.1038/srep26875).** Open access; **retrieved**. Seven patch sizes on 30 µm polyimide over a gold ground, spanning 0–300° of reflection phase, arranged by a pseudorandom sequence; 4 × 4 super-cells over 9.6 × 9.6 mm.

**Measured, wrapped on a copper cylinder of 10 mm diameter (R = 5 mm):** *"the metal cylinder indicates a broadband −10 dB backward reflection suppressions from 0.8–1.55 THz for both polarization incidences"*, and *"the wideband specular reflection suppression is kept up to 60° for TE wave and to 45° for TM wave, **which is similar to the case of flat metasurface**."* At 1 THz λ = 300 µm, so R = 5 mm is **≈17λ** — electrically a very tight cylinder for the wavelength, and the diffuse-scattering function survives it.

**H. Su, Q. Xiao et al., "Conformal, transparent, and efficient MXene grid antennas for flexible wireless electronics", *Science Advances* (2026), eaee8104. DOI [10.1126/sciadv.aee8104](https://doi.org/10.1126/sciadv.aee8104).** Open access; **retrieved**. This one is unusually close to the programme's own target: a **digital coding metasurface** made of a **nanoimprinted 2D-material (MXene) conductor**, bent and **measured**.

> **Correction.** An earlier revision of this paragraph called the conductor a "printed 2D-material conductor"; §5.3 below quotes the paper's own fabrication route verbatim as **nanoimprint** (lithography plus blading), not a dispensed or screen-printed process. Reconciled to nanoimprint. **This does not demote the precedent to "ruled out."** It is a real, measured MXene coding device that this configuration's own process (Voltera NOVA dispensing, see `docs/voltera-multilayer-capability.md`) does not currently reproduce — a **capability warning** (ADR-0025/ADR-0027/ADR-0028 shape: report the candidate, flag the assumption), not a disqualification. The device still informs the curvature rule below and still scores as precedent; only its fabrication route differs from what this shop can currently print.

- **Measured**, conformally attached to a cylindrical foam former of **radius 100 mm**: *"the EM waves at a center frequency of **11 GHz** can still be scattered into dual beams"*, matching the flat-state simulation.
- Communication payload, **measured** at 1 Mbps in the bent state: *"This results in a calculated **BER of 0.57%**, confirming the system's resilience to bending."* The abstract separately quotes *"a low bit error rate (~**0.15%**) even in a curved state"* and the conclusion *"a BER down to 0.6% even under mechanical bending"*; **the flat-state BER at the same data rate is not stated**, so the flat-to-bent penalty cannot be extracted. *Plainly: with the surface wrapped onto a 10 cm-radius cylinder the data link still ran at well under one error per hundred bits — the beam-forming survived the bend — but the paper does not publish the flat number needed to say how much the bend cost.*

**"Conformal Reconfigurable Intelligent Surfaces: A Cylindrical Geometry Perspective", [arXiv:2601.00734v2](https://arxiv.org/abs/2601.00734) (2026).** Preprint; **retrieved**. Cylindrical 1-bit RIS, **R = 400 mm**, 3.6 GHz, patch cells `L = 26 mm` on a `p = 38 mm` lattice over a 1.57 mm grounded substrate, N = 30 illuminated elements — so the lit arc spans **2.85 rad ≈ 163°**, i.e. local incidence out to **±82°**. Simulated (ANSYS HFSS), no measurement.

> "…the one-bit meta-atom … achieves exactly 180° phase difference at normal incidence but **gradually deteriorates at oblique angles**. Consequently, meta-atoms located near the edges of the illuminated [region]…"

Cost of assuming local flatness, from their model-versus-full-wave comparison: sidelobe-level discrepancies **within about 3 dB for steering up to 60°, rising to ≈5 dB at 75°**, attributed verbatim to *"the simplifying assumptions inherent to the semi-analytical model, including locally planar approximations and the neglect of higher-order EM interactions."*

---

## 4. Cross-cutting: local incidence angle, and how much curvature a per-cell characterisation survives

### 4.1 The rule, stated in the literature

Shabanpour et al. (IEEE TAP 2024 / arXiv:2308.10589, **retrieved**) prove the thing this repo needs. Their term for the local-periodicity assumption is **reflection locality**:

> "A usual way to design RIS based on metasurfaces is based on the application of the approximation in which the reflective properties of a uniform MS are attributed to a unit cell of the non-uniform one. We call this approximation the **reflection locality**. In the present paper, we show that this approximation **may result in heavy errors**. We also find a condition under which this approximation is applicable for a wide range of incidence and deflection angles. **This condition is the angular stability of the reflection phase** of a uniform MS based on which the non-uniform one is generated." — abstract, verbatim

**So: per-cell characterisation holds exactly as far as the element's reflection phase is angle-stable, and no further.** Their measured/simulated numbers for two element families at 16–20 GHz, on a 0.5 mm ε_r = 3 substrate with a 1.5 mm air gap:

| Element | Angular stability within ±40° of 180° | Note |
|---|---|---|
| **Jerusalem cross** (their design) | **θ_max ≈ 60°**, TE *and* TM, across a 20% band | reflects >99% of incident power |
| **Mushroom / high-impedance surface** | either band **<10%**, or **θ_max < 30°** | in TM at θ ≥ 60°, verbatim: *"the states '0' and '1' cannot be properly engineered … ∆Φ_R does not exceed π/2"* |

*Plainly: the mushroom cell — the standard high-impedance building block — stops being able to represent a "0" and a "1" at all beyond about 60° of tilt; the two states collapse to less than a quarter-wave apart when they need to be half a wave apart. An angle-stable cell holds to 60°.*

### 4.2 The curvature budget that follows

Combining §0(i) with §4.1, and with Khan et al.'s explicit 90°-central-angle / 45°-element statement:

```
    usable aperture arc length     S  ≤  2 · θ_max · R
    usable half-width from crown   s  ≤  θ_max · R
```

**Derived here** from the cited geometry and the cited θ_max values; the special case `S = 2 × 45° × R` is Khan et al.'s own result.

Worked, for a cylinder and the element families above:

| Host radius R | Angle-stable cell (θ_max = 60° = 1.047 rad) | Mushroom-type cell (θ_max = 30° = 0.524 rad) |
|---|---|---|
| 50 mm | usable arc **105 mm** | **52 mm** |
| 100 mm | **209 mm** | **105 mm** |
| 300 mm | **628 mm** | **314 mm** |
| 1000 mm (wing/hull) | **2.09 m** | **1.05 m** |

*Plainly: on a 10 cm-radius pipe you can wrap about 21 cm of a well-behaved coded skin before the tiles at the edges are being hit at an angle their design never anticipated — and only about half that if the tiles are the common mushroom type. Beyond that, you either change the element for an angle-stable one, or you re-characterise the edge tiles at the angle they actually see.*

### 4.2.1 An independent multi-radius validation of the rule

**P. Tiwari, S. K. Pathak & V. Siju, "Design, development and characterization of resistive arm based planar and conformal metasurfaces for RCS reduction," *Scientific Reports* **12**, 14992 (2022). DOI [10.1038/s41598-022-19075-x](https://doi.org/10.1038/s41598-022-19075-x).** Open access; **retrieved** via [PMC9440246](https://pmc.ncbi.nlm.nih.gov/articles/PMC9440246/).

This is the first source in this document that tests `S ≤ 2·θ_max·R` at **more than one radius on the same device** — exactly what validating a geometric rule needs, and something none of §3.2's single-radius papers can offer.

Their 16×16 unit-cell panel has period `a = 10.93 mm`, verbatim: *"The optimized parameter of the unit cell are a = 10.93 mm"* — so **`S = 16 × 10.93 = 174.88 mm`** (`CALCULATED`). Their own stated element limit, verbatim: *"the proposed absorber maintains more than 90% absorptivity up to 40° angle of incidence in the given frequency regime"* — so **`θ_max = 40°`**.

`CALCULATED`, bounding `2·θ_max·R` (θ_max = 0.698132 rad) against the panel's actual `S`, and reading edge-cell local incidence as `(S/2)/R`:

| R | `2·θ_max·R` bound | S = 174.88 mm | Verdict | Edge-cell incidence | Paper's own words |
|---|---|---|---|---|---|
| 130 mm | 181.51 mm | inside the bound (~3.7% headroom) | **no violation** | 38.5° | "good" |
| 100 mm | 139.63 mm | over the bound | **violation** | 50.1° | performance "deteriorates" |
| 50 mm | 69.81 mm | over the bound | **violation** | 100.2° (past grazing) | deteriorates further |

The rule's own flip radius, `S/(2·θ_max) = 174.88/1.396263 = 125.24 mm`, sits **within ~3.7%** of R = 130 mm — the last radius the paper reports as good — and on the correct side of it (`CALCULATED`).

**Two caveats to carry with this validation, not to smooth over.** First, the operating band is **13.42–22.66 GHz (Ku+K band, not X-band)** — verified verbatim (*"20 dB reflection reduction for 51.21% fractional bandwidth (13.42–22.66 GHz)"*). Because the rule under test is purely geometric (arc length versus angular stability, with no frequency term), this validates the *rule*, not a transferred X-band number. Second, the device is, verbatim, *"four metallic patches loaded with eight lumped resistors"* at **150 Ω** each (*"SMD Resistor—1206 Package"*) on a **rigid FR-4** substrate (`εr = 4.3`, `tanδ = 0.025`) — roughly 2,048 soldered SMD resistors across the 256-cell panel, **not a printed pattern**. **This is a capability-warned precedent, not a disqualified one:** it is a real, measured, multi-radius validation of the curvature rule, on a fabrication route (soldered discrete components on rigid FR4) this configuration's printer does not currently reproduce. It still counts as evidence for the rule and still scores as precedent.

Note the sanity check against §3.2, corrected here after recomputing rather than asserting. **Zhang et al.'s THz surface** on a full cylinder of R = 5 mm ≈ 17λ genuinely sits inside the rule, where the *illuminated* arc is what matters, not the closed circumference. **Su et al.'s MXene coding surface, recomputed (`CALCULATED`, assumptions stated below).** Su et al.'s device is a 10-cell 1-D binary period measured conformally on R = 100 mm at 11 GHz, splitting the reflected wave into dual beams. For a 1-bit binary grating the diffracted beams sit at `sin θ = ±λ/Γ`, where Γ is the supercell period. At 11 GHz, λ = 299.792458/11 = 27.254 mm (27.25 mm used below, matching the geometry as given). Solving `Γ = λ/sin θ` for the beam angles the paper reports, and reading edge-cell local incidence as `(Γ/2)/R` (from §0(i), taking the half-period as the arc distance from the supercell's own centre to its edge):

| Beam angle | Γ = λ/sin θ | Edge-cell local incidence |
|---|---|---|
| 15° | 105.3 mm | 30.2° |
| 20° | 79.7 mm | 22.8° |
| 30° | 54.5 mm | 15.6° |

**This is short of what the original line claimed.** Su et al. do not publish a `θ_max` for their own meta-atom — no stated angular-stability limit the way Khan et al. or Shabanpour et al. give one — so whether the geometry actually "sits inside" `S ≤ 2·θ_max·R` **cannot be confirmed against the rule as written here; downgraded to not yet checked against the element's own limit.** What the arithmetic does support: at the 20° and 30° beam angles the edge-cell incidence (22.8°, 15.6°) sits comfortably inside even a mushroom-class element's `<30°` window (§4.1); at the 15° beam angle the edge incidence (30.2°) just exceeds that same window, though it remains well inside an angle-stable (Jerusalem-cross-class, ~60°) element's. That is a plausibility check against *typical* element classes, not a verification against Su et al.'s own element.

### 4.3 What was *not* found

**A published number in degrees for "reflection phase drifts by X° per Y° of incidence" for a named unit cell.** The literature reports it as a pass/fail against a criterion (±37°, ±40°) and a limiting angle (30°, 45°, 60°), not as a slope. Multiple searches (arXiv, Europe PMC full text, general web) surfaced statements of the form "stable up to 45°" but no phase-versus-angle curve digitisable into a coefficient. **This is a gap, and it is the one number that would let the design loop *compute* a curvature penalty rather than pass/fail it.** See §7.

### 4.4 A limitation of the rule itself: it tests the worst cell, never how much that cell matters

**`S ≤ 2·θ_max·R` is a worst-cell test.** It asks only whether the single most-tilted cell in the aperture stays inside the element's angle-stability window; it does not ask how much that cell actually contributes to what a radar sees. That omission can flip a verdict, and this section records where.

A conformal chessboard metastructure reporting **−10 dB RCS reduction over 5.3–18 GHz**, stated **"robust to 180 degrees of curvature and 0–60 degrees incidence"** (Composite Structures, S0263823125008997 — ScienceDirect returns HTTP 403 to automated fetch from this environment. **This is a claim about us, not a finding about the paper**: the quote above has not been independently read against the published text from here, and is carried as reported rather than verified) illustrates it. Read against this repo's own implementation of the rule: `rf_tools/patch_synthesis.py`'s `curvature_exceeds_validity_box` accepts `theta_max_deg` only in `(0, 90]`, and its own docstring states plainly that "no published element stays angle-stable at or past grazing incidence." A full 180° central angle demands `theta_max_deg ≥ 90` under `S ≤ 2·θ_max·R` (central angle `= 2·θ_max`) — the boundary the function's own comment says no characterised element reaches. So a candidate built on this structure, checked against this rule with any real (i.e. less-than-grazing) characterised `θ_max`, would be dropped: `orchestration/design_loop.py`'s `capability_verdict_holds` calls `_curvature_exceeds_validity_box(arc_length_m, host_radius_m, entry["theta_max_deg"])` at **line 683** (verified by reading the file directly), and the module's own ledger vocabulary records a family a validity-box check excludes with `reason_kind="capability-verdict"` and `verdict="dropped"` — **the only check in this codebase whose outcome removes a family from the ranked report** (`_validate_capability_verdict_entry` requires `verdict == "dropped"` for that `reason_kind`; verified in the same file).

**But at a 180° wrap the edge cells sit at ~90° of local incidence, and `cos(90°) = 0`.** A cell tilted to grazing incidence contributes essentially nothing to the surface's projected aperture as seen along the original boresight — it is edge-on to the wave. *In plain terms: the rule throws the whole design out because its outermost tiles are badly tuned, when those same tiles are turned almost sideways to the radar and barely reflect anything back at all — good or bad tuning at that angle makes almost no difference to what gets measured.*

**Why this is serious, not a curiosity.** Under the programme's governing principle — physics is the only thing that blocks a candidate; equipment, inventory and what has been published shape ranking and warnings, never the search — a worst-cell geometric test that ignores projected aperture **is not physics doing the blocking.** It is a proxy for physics (angle-stability of a per-cell characterisation) standing in for the actual physical quantity (contribution to backscatter), and the proxy diverges from the real quantity precisely at the extreme angles where it matters most. Every other consequence recorded in §8 below is advisory; this is the one place in the codebase where a proxy has the power to make a candidate disappear from the report entirely rather than carry a warning on it.

**A candidate fix, recorded as an open question — no code changed here; `rf_tools/` and `orchestration/` belong to another agent's scope:** either (a) weight the per-cell check by projected aperture (a `cos θ(s)` factor) so a mistuned edge cell contributing near-zero backscatter cannot veto the whole aperture, or (b) keep the check but relabel its result explicitly as a worst-cell screen and route it through the ordinary capability-warning path (report the candidate, flag the assumption) instead of the drop path.

**Two further escapes the rule assumes away**, both worth carrying alongside the fix:

- **The paper's own model does not use one flat per-cell characterisation.** As reported to this document, the Composite Structures device uses a *propagation-phase-compensation model* — its cells are not evaluated against a single flat-panel characterisation the way `S ≤ 2·θ_max·R` assumes. §4.1's founding premise ("reflection locality": one uniform-MS characterisation applied cell-by-cell) does not hold for a device designed this way in the first place.
- **The reference is also curving.** §3.2 above already records, from Chang et al., that an equally-bent PEC reference scatters less straight back than a flat one: *"a curved plate scatters less straight back at you than a flat plate does, whatever is printed on it — so some of the 'RCS reduction' you measure on a bent panel was bought by the bend and not by the design."* An RCS figure measured at extreme curvature is therefore measured against a reference that is itself already helping the number look better, independent of anything the pattern does.

**None of this demotes the chessboard precedent to "ruled out."** It is a real (if currently unfetched, HTTP-403) published claim, and per the governing principle it remains a candidate the search should surface. What this section records is that *this repo's own implementation* would currently drop it for a reason that does not survive a projected-aperture check — a defect in the check, to be fixed at the owning layer (`rf_tools/`/`orchestration/`), not a reason to treat the precedent itself as excluded.

---

## 5. Printed conductors under bend strain — for #189

### 5.1 The strain a bend actually applies

From `ε = T/(2R)` (§0(iii)), for the stacks in the sources below:

| Source | Stack thickness T | Bend radius R | Outer-fibre strain |
|---|---|---|---|
| Kujala et al. (silver on PET) | 125 µm | 10 mm | **0.63%** |
| Owens et al. (CNT on paper) | ~100 µm paper | 1 mm | **~5%** |
| #189's own stack | 1.527 mm | 59 mm | **1.29%** |
| #189's own stack at the patent minimum | 1.527 mm | 4.6 mm | **16.6%** |

*Plainly: the published bend tests are gentle by this programme's standards. The silver test that nearly doubled a track's resistance was applied at less than half the strain of #189's demonstrated 59 mm bend, and one twenty-sixth of the strain at the patent's minimum radius.*

### 5.2 Silver

**M. Kujala, T. Kololuoma, J. Keskinen, D. Lupo, M. Mäntysalo & T. M. Kraft, "Bending reliability of screen-printed vias for a flexible energy module", *npj Flexible Electronics* **4**, 24 (2020). DOI [10.1038/s41528-020-00087-4](https://doi.org/10.1038/s41528-020-00087-4).** Open access; **retrieved**. Screen-printed silver microparticle inks on 125 µm PET, laser-cut through-vias, custom pneumatic two-plate bender with plates 2 cm apart (**10 mm bending radius**), ≥30,000 cycles, resistance logged continuously.

Their Table 3, "Cyclic bending trials", verbatim values:

| Ink | R₀ (Ω) | After bending 1 | After anneal 1 | After bending 2 | After anneal 2 |
|---|---|---|---|---|---|
| **Asahi LS411AW** | 13 | **25.4** | 12.6 | 23.1 | 13.7 |
| **DuPont 5064H** | 17.7 | **29.6** | 19.6 | 36.4 | 26.6 |

Plus, verbatim: *"The interconnection starts to break after **8000 bending cycles** and breaks completely shortly after the shown 30,000 bending cycles"* (DuPont), while *"The Asahi ink on the other hand restores almost completely to the starting value."* Abstract, verbatim: *"The 10-mm radius bending test showed no signs of via specific breakdown after 30,000 cycles."*

The stated mechanism is worth carrying: resistance **rises with cycling and falls back during rest**, because *"The samples' ink polymer matrix relaxes, which brings the ink's silver flakes closer together."* A 20 min re-anneal at 150 °C (Asahi) / 130 °C (DuPont) recovers most of it once, less of it twice.

*Plainly: printed silver is not a wire, it is metal flakes suspended in a polymer. Bending loosens the polymer and the flakes drift apart; resting, and especially re-baking, packs them back together. So a resistance measurement taken right after a bend test is not the same number as one taken the next morning.* **That is a measurement-protocol warning for #189's coupon run:** record time-since-bending with every reading, or the numbers will not be comparable.

### 5.3 MXene

**Su, Xiao et al., *Sci. Adv.* (2026), eaee8104** (as §3.2; **retrieved**). Nanoimprinted Ti₃C₂Tₓ grid transparent conductive film, verbatim:

> "MXene grid TCF can withstand more than **5000 bending cycles (180°)** with a slight increase of R_s (**ΔR_s of 9.5%**)"

from a starting sheet resistance of **4.32 Ω/sq**. Antenna-level: after 1000 bending cycles the transparent MXene dipole's realised gain went **0.646 dB → 0.539 dB** and average efficiency **61.84% → 60.56%**. Bending radius not stated (the bend is described only as 180°).

**S. Sathyanarayanan & A. N. Grace, "Mechanical Robustness and Conductivity Retention in Ti₃C₂ MXene-Enhanced Electrodes on Flexible Substrates", *ACS Omega* (2026). DOI [10.1021/acsomega.6c02342](https://doi.org/10.1021/acsomega.6c02342).** Open access; **retrieved**. MXene coatings 5–100 nm on PET, PEN, ITO-PET, ITO-PEN and PI; sheet resistance before and after **500 bending cycles**:

| Sample | Before | After | Change |
|---|---|---|---|
| Bare ITO-PET | 45.39 Ω/sq | 12,629 Ω/sq | **+27,700%** (catastrophic) |
| ITO-PET + 5 passes MXene | 18.08 | 94.36 | +422% |
| Bare ITO-PEN | 14.31 | 135.16 | +845% |
| ITO-PEN + 5 passes MXene | 12.37 | 28.50 | +130% |
| PET + 3 passes MXene (~30 nm) | 272.83 | 300.32 | **+10%** — *"retains 91% conductivity"* |
| PET + 5 passes MXene | 34.11 | 52.46 | +54% |

*Plainly: brittle transparent conductors shatter when bent; a MXene overlayer bridges the cracks with flakes and keeps current flowing across them. Their stated "sweet spot" is about 30 nm of MXene.*

**Caveat, and it is a real one: this paper never states the bending radius.** It says only *"500 bending cycles over a fixed radius"*. Numbers without the radius cannot be converted into strain and cannot be compared to anything else here. Recorded as a limitation, not smoothed over.

### 5.4 Carbon

**C. E. Owens, R. J. Headrick, S. M. Williams, A. J. Fike, M. Pasquali, G. H. McKinley & A. J. Hart, "Substrate-Versatile Direct-Write Printing of Carbon Nanotube-Based Flexible Conductors, Circuits, and Sensors", *Advanced Functional Materials* **31**(25), 2100245 (2021). DOI [10.1002/adfm.202100245](https://doi.org/10.1002/adfm.202100245); preprint [arXiv:2105.10942](https://arxiv.org/abs/2105.10942), **retrieved**.**

Verbatim from the abstract: *"The lines are flexible, with **< 5% change in DC resistance after 1,000 bending cycles**, and **<3% change in DC resistance with a bending radius down to 1 mm**."*

And from the body, verbatim: *"We measured the relationship between the bending radius of the substrate and resistance for printed traces with linear density of 0.2–9 mg/m and **radii of curvature from 0.02 mm (sharp fold) to 35 mm**, corresponding to **compressive strains of 1 to 0.002** … Compared to the resistance of traces measured on a flat substrate (of **20 − 1200 Ω**, depending on the linear density), bending the substrate to a radius of > 1 mm show a change in resistance within 3%."*

Supplementary, verbatim: *"the conductivity degrades linearly with bend cycles up to a mean **28% increase in resistance over 1,000 bending cycles**"* — but only for the sparsest traces (v_ink/v_nozzle = 0.05, R₀ ≈ 300–2100 Ω); dense traces are *"constant within 2% for at least 1,000 bending cycles with a full inward crease."*

**This is the best carbon number found, and it is not the material #189 needs.** It is direct-written carbon *nanotube* ink on paper, not screen-printed carbon-black paste on silicone or TPU. Carrying it across would be an unlabelled substitution. What it does establish: **carbon-based printed conductors are, as a class, far less bend-sensitive than printed silver** — 3% at 1 mm radius against silver's +67–95% at 10 mm radius over cycles. That is a hypothesis worth testing on the actual ink, not a result about it.

### 5.5 What #189 still needs, unchanged

No source found in this pass reports **sheet resistance versus bend radius, in Ω/sq, for a screen-printed or dispensed carbon ink on a silicone or TPU substrate.** ACI's own datasheets (per #189) publish elongation >200% and "rapid return after strain" and no curve. The measurement described in #189 — four-point probe flat, then over mandrels spanning ~1% to ~17% strain, then 100 cycles — remains the only route to that number, and §5.2's flake-relaxation finding adds one requirement to it: **log the elapsed time between bending and reading.**

---

## 6. Where the sources disagree

This repo treats a disagreement between sources as a finding. Three of them:

**6.1 The sign of the E-plane shift.** Boeykens et al. (measured, 1.57 GHz, aramid/cotton textile, R = 31.5–90 mm): resonant-length bending shifts the resonance **up**, +0.58% measured, +2.6% for the rigid conformal case. Zhang et al. (measured + calculated, 5.8 GHz, 0.254 mm polyimide, 0°–35° bend): E-plane bending shifts it **down**, −6.91%. The *Sensors* 2025 textile antenna (measured, 2.45/5.8 GHz, 0.8 mm flannel, R = 30–80 mm): **down** in both bands.

**Not reconciled here.** Two candidate explanations, neither verified: (i) the substrates differ enormously in compressibility — a 2.7 mm cotton weave squashes and a 0.254 mm polyimide film does not, and compression is the down-pushing term in Boeykens' decomposition, so the *balance* of the two competing terms could legitimately differ; (ii) the papers may not mean the same thing by "E-plane bending", since Zhang et al. give bend *angle* with no radius and Boeykens gives radius with no angle. Settling it needs Song & Rahmat-Samii (§1.6, STRANDED), which is the source all three chains cite.

**6.2 A paper against its own figures.** Zaidi et al. state in prose that bending raises the resonance and cite Song & Rahmat-Samii for it; their Figure 6 shows every bent trace below the flat one. Recorded, not reconciled. This matters beyond one paper because that sentence — "the effective length is decreased and the resonant frequency will shift to a higher band" — is the form in which the claim propagates through the wearable-antenna literature.

**6.3 Whether curvature helps or hurts a periodic surface.** Álvarez et al. find their **conformal** dome FSS *closer* to ideal infinite-array behaviour than an equal-sized flat one (−3 dB bandwidth stable to 30° versus 5°), because the dome equalises the incidence angles from a near-field feed. Every RCS paper in §3.2 finds curvature *degrades* performance. Both are correct and they are not in conflict: the first is a near-field problem where curvature *reduces* the spread of incidence angles, the second is a far-field plane-wave problem where curvature *creates* it. **The sign of the curvature effect depends on whether the illumination is a plane wave or a nearby feed.** Worth carrying into any requirement that names a radome.

---

## 7. What could NOT be established

Stated plainly rather than paraphrased into apparent findings.

1. **Song & Rahmat-Samii (IEEE TAP 2018) was not read.** It is the canonical E-plane/H-plane primary source and it is paywalled (IEEE returns 418 to automated fetches; no author copy, dissertation chapter or repository deposit found). No number from it appears in this document. **Highest-value follow-up.**
2. **No published phase-versus-incidence-angle slope, in degrees per degree, for any named unit cell.** The literature reports pass/fail against ±37–40° and limiting angles (30°/45°/60°); it does not publish the curve. Without it, a curvature penalty can only be evaluated as a threshold, not computed.
3. **Chang et al.'s curvature angle γ cannot be converted to a radius.** The paper gives γ = 5–20° without stating the width of the simulated panel that subtends it, and the figure defining γ was not readable as text. Its RCS numbers are therefore not comparable with the radius-based results.
4. **Sathyanarayanan & Grace never state their bending radius.** 500 cycles "over a fixed radius". The sheet-resistance table is real; the strain it corresponds to is unknown.
5. **No sheet-resistance-versus-bend-radius data for screen-printed carbon on silicone or TPU.** The closest is CNT ink on paper (§5.4), a different material on a different substrate. #189 remains open on exactly the grounds it was opened.
6. **No FSS paper found that reports a resonant-frequency shift in MHz or % against a stated radius of curvature.** The conformal-FSS results retrieved say "little shift", "resonance intact", "slight shift towards a higher frequency" — qualitative. Numbers exist for incidence *angle* and for bandwidth, not for the frequency shift versus radius.
7. **The mechanism separation in §2.3 (bending preserves inter-element coupling; only stretching or projection changes it) is derived here, not quoted.** It follows from two cited facts — that bending preserves arc length, and that Ali et al.'s coupling is set by inter-element spacing — but no source found states it in those terms. Treat as a hypothesis with an obvious test: simulate one super-cell flat and the same super-cell conformed with arc length preserved, and difference the per-cell phases.
8. **Josefsson & Persson, *Conformal Array Antenna Theory and Design* — the textbook cited in `rf_tools/patch_synthesis.py` — was not read.** No copy retrievable in this session. The module's claim that it supports a bend-axis-dependent sign remains **UNVERIFIED against the textbook**; §1 supports the claim from a different source.

---

## 8. Consequences for this repo

Written as findings, not as instructions — nothing here is a decision.

1. **`rf_tools/patch_synthesis.py`'s curvature model needs an axis argument and a smaller coefficient.** As it stands it applies an E-plane-shaped correction regardless of bend axis, at roughly 7–9× the magnitude the measured cavity model supports, with no dependence on substrate thickness (§1.5). The honest short-term fix is to keep it as a screen and say so in the returned value; the honest long-term fix is the cylindrical cavity dispersion relation, which Boeykens publishes in closed form.
2. **The warning this deserves, per CLAUDE.md's "warn, never block" rule, is bend-axis-specific and load-bearing.** *Assumption:* the host curvature is around the axis you think it is. *Cost if wrong:* the frequency moves the other way, by up to a few percent — for a patch with 2% bandwidth, off-band. *Cheapest way to find out:* ask which way the part wraps, which is a one-line question to the requester and not a simulation.
3. **The coded-surface phase budget is ±37°, and `local-periodicity-coupling-error.md`'s 12–85° already spends it.** Any curvature allowance has to be taken out of what is left, not added on top. A design that is already at 45° of neighbour-coupling error has no curvature headroom at all.
4. **The curvature rule the design loop can actually use is `S ≤ 2·θ_max·R`** (§4.2), where θ_max is a *property of the chosen element* that must be characterised, not assumed. This is a cheap check — it needs only the aperture arc length, the host radius, and one number per letter in the alphabet — and it turns "is this host too curved?" into arithmetic.
5. **Element angular stability belongs in the Element/Coding-Alphabet library as a characterised property.** ADR-0027 admits letters by printing and measurement. On this evidence, a letter's record needs `θ_max` (the angle at which its reflection phase leaves the ±37° window) alongside its phase and amplitude, or the curvature rule above has nothing to evaluate.
6. **Generate conformal geometry on the curved surface, never by projecting a flat layout.** §2.1 identifies element distortion as a mechanism that is entirely avoidable and that has been measured to shift resonances and widen stopbands when it is not avoided.
7. **#189's coupon protocol gains one requirement:** record time-since-bending with each reading, because printed-ink resistance relaxes after bending on a timescale of tens of minutes (§5.2). And the flat-versus-bent comparison for any RCS figure must use an equally-bent reference (§3.2), or curvature will be credited with reduction it did not produce.
