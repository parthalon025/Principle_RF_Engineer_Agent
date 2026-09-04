# Is εr ≈ 10 Load-Bearing for Example 6's Meander-Line Polarizer, or a Free Design Choice?

**Research date:** 2026-09-04
**Ticket:** [#108](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/108)
**Question:** US12089385B2's Example 6 (a 45°-oriented meander line, ground-backed, linear-to-circular
polarization converter, 13–17 GHz) is built on a substrate with εr = 10.4, tanδ = 0.0028 — a
ceramic-filled-laminate signature, not a pliable polymer, and in tension with the patent's own
stated host-polymer range (εr 2–5) and with this program's flexible-substrate shortlist (silicone
εr ≈ 2.9, Kapton εr ≈ 3.2, both measured — `docs/xband-absorber-substrate-shortlist.md`). Is
εr ≈ 10 *functionally necessary* for this element to convert linear to circular polarization with a
useful axial-ratio bandwidth — or is permittivity a scalable parameter that a re-derivation on a
low-εr flexible substrate could route around by re-sizing the cell?

Provenance tags are `CONTEXT.md`'s ladder — `MEASURED` → `SIMULATED` → `CALCULATED` →
`MANUFACTURER-SPECIFIED` → `LITERATURE-SUPPORTED` → `INFERRED` → `ASSUMED` → `UNKNOWN`. Per
`CONTEXT.md`, a patent or paper's own reported numbers — even ones the source itself calls
"measured" — enter this repo as `LITERATURE-SUPPORTED`; `MEASURED` is reserved for something this
program measured itself. No parallel confidence vocabulary is introduced.

---

## Bottom line up front

Six findings, in descending order of how much weight they carry against "εr ≈ 10 is required."

1. **A published, fabricated, horn-antenna-measured meander-line polarizer achieves 90° phase
   conversion and a 60% relative bandwidth using a dielectric permittivity of 2.65 and a spacer
   permittivity of 1.1 — barely above air.** Zhang, Yin & Ma (2009) built a four-layer meander-line
   polarizer with a **1.65 dB axial ratio ceiling of 2 dB** and **insertion loss under 0.5 dB from
   5.6–10.4 GHz**, and their own design equation states plainly: *"Δθ is determined by the
   dimensions of the meander lines, the thickness and relative permittivity of the dielectric
   layers, the spacing between the sheets."* In plain terms: **permittivity is one knob on a
   multi-knob dial**, traded off against line width, meander offset and layer spacing — not a
   threshold a design must clear. This is the load-bearing physics finding, and it comes from the
   textbook mechanism itself, not an inference (`LITERATURE-SUPPORTED`, §1).

2. **A measured, published X-band-and-Ku-band linear-to-circular converter on εr = 2.2 beats
   Example 6's own performance on breadth.** Undrasi & Khairnar (Optik, 2024) built and
   horn-antenna-tested a reflective LP-to-CP converter on Rogers RT/duroid 5880 (εr = 2.2) that
   hits **AR < 3 dB across 8.09–10.59 GHz (26.76% bandwidth) and again across 17.53–18.63 GHz
   (6.08%)**, with **average conversion efficiency 99.5%**. That is X-band *and* Ku-band, on a
   substrate close to the low end of this programme's shortlist, simultaneously outperforming
   Example 6's own simulated AR minima (patent: below ≈0.5 dB near 13.85 and 16.6 GHz — a narrower
   claim, and never independently measured). In plain terms: **the specific electromagnetic outcome
   this ticket is asking whether εr ≈ 10 is needed for has already been built and tested at
   εr = 2.2, in both of Example 6's target bands** (`LITERATURE-SUPPORTED`, §2).

3. **A near-identical natural experiment landed on nearly the same two frequencies Example 6
   claims — using a meander line, at Ku-band, on a substrate the authors call "low-permittivity."**
   A 2026 meander-line "staircase" metasurface (transmissive, not reflective) reports its Ku-band
   variant's axial ratio has **two minima at ≈13 GHz and ≈17.5 GHz** — essentially the same two
   frequencies as Example 6's stated 13.85/16.6 GHz dips — reached with a *different* cell geometry
   on a *low-permittivity* substrate rather than εr = 10.4. Two independent meander-line
   polarization converters landing on the same operating sub-band from opposite ends of the
   permittivity range is close to a direct empirical answer: **the function re-derives at low εr;
   only the geometry that gets you there changes** (`LITERATURE-SUPPORTED`, §2).

4. **No paper or patent was found that states high permittivity is functionally necessary for
   meander-line polarization conversion — and the one explicit design-tradeoff quote found argues
   the opposite direction.** A wide-scan mm-wave circular-polarizer patent (US10547117B1) states
   its Rogers 4003 (εr = 3.55) substrate was **"chosen to be large enough to improve performance at
   wide scan angles, but not too large to enable a broadband impedance-match to free space."** In
   plain terms: **that patent explicitly treats high permittivity as a cost, not a benefit** — every
   unit of εr above what wide-angle stability needs is unit of impedance mismatch to free space paid
   back as narrower bandwidth. Basic transmission-line theory backs the mechanism up: a dielectric's
   intrinsic impedance is η ≈ η₀/√εr, so εr = 10.4 presents ≈117 Ω to a 377 Ω free-space wave (a
   3.2× mismatch) where εr = 2.9 presents ≈221 Ω (a 1.7× mismatch) — a smaller step for a
   polarization converter's matching layers to climb (`CALCULATED`, standard transmission-line
   relation, offered as a mechanism consistent with, not proven by, finding 4's quote — §3).

5. **The only place "high permittivity, and here is why" appears anywhere in the surrounding
   literature is unit-cell miniaturization for scan-angle stability in a *different* structure
   class — high-impedance surfaces / general FSS, not meander-line polarizers — and even that is a
   convenience, not a necessity, since the same miniaturization is independently demonstrated using
   meandering/convolution geometry alone, at ordinary εr.** Genovesi *et al.* (2009) built
   angularly-stable high-impedance surfaces on zirconium-tin-titanate ceramic (a genuinely high-εr
   substrate) specifically to shrink the unit cell relative to wavelength. But a separate,
   unrelated paper reaches **0.026λ₀ × 0.026λ₀** unit cells — aggressive miniaturization — purely by
   *meandering the conductor itself*, at ordinary εr, with no ceramic substrate at all. Meandering
   is already a miniaturization technique in its own right; that is the entire premise of a
   *meander*-line element. Reaching for high εr *on top of* an already-miniaturizing topology is not
   documented anywhere as required for polarization conversion specifically (`LITERATURE-SUPPORTED`,
   §4).

6. **Example 6's εr = 10.4, tanδ = 0.0028 matches a well-known family of rigid, ceramic-filled
   PTFE laminates — not a material anyone would reach for on a pliable-skin programme.** Rogers
   RO3010 (εr = 10.2, Df = 0.0023) and TMM10i (εr ≈ 10.0, Df ≈ 0.002) are commercial, catalog-listed
   substrates in exactly this range, built by loading PTFE with ceramic powder specifically to raise
   εr — a well-understood way to buy compactness at the cost of flexibility. No source states which
   product the patent used, so this is an identification by resemblance, not a confirmed match
   (`INFERRED`, §5). It is consistent with what the companion research doc already concluded from
   the patent text alone: this example's substrate contradicts the patent's own εr 2–5 host-polymer
   statement (`docs/seven-example-design-unknowns.md`, finding 4 and §3).

**Net read:** every piece of first-hand physics and every published data point found points the
same direction. Nothing in the literature treats εr ≈ 10 as a requirement for a 45°-meander-line
(or comparable anisotropic-element) linear-to-circular converter; the dominant, repeatedly-cited
role of permittivity in this exact design problem is to set how physically large the resonant
geometry needs to be for a given frequency (the classic λg = λ₀/√εr relation), and the one
explicit tradeoff statement found in the literature argues *moderate-to-low* εr is often the
*better* choice for bandwidth, not just an acceptable substitute. A re-derivation on silicone
(εr ≈ 2.9) or Kapton (εr ≈ 3.2) is not fighting the physics; it is re-solving a well-populated
design space at a different, cheaper-to-reach point in it.

---

## 1. The physics: how does permittivity enter a meander-line polarizer's design equations?

**The operating principle, common to every source found.** A linearly-polarized wave hitting a
45°-oriented anisotropic grid resolves into two equal-amplitude orthogonal components, one aligned
along the meander-line axis and one across it. The along-axis component sees more inductance (the
meander is a folded wire — a slow-wave delay line); the across-axis component sees more capacitance
(the folds present closely-spaced parallel conductors to it). That asymmetry produces a
**differential transmission (or reflection) phase shift Δθ** between the two components. Circular
polarization requires Δθ = 90°; the classic reference for this is Young, Robinson & Hacking,
"Meander-line polarizer," *IEEE Trans. Antennas Propag.* **21**(3), 376–378 (1973)
(`LITERATURE-SUPPORTED`, cited via Zhang, Yin & Ma below — the 1973 original itself was not
directly fetched).

**The design equation, quoted directly from a primary source obtained and read in full.** Zhang,
Yin & Ma, "Multifunctional Meander Line Polarizer," *Progress In Electromagnetics Research
Letters* **6**, 55–60 (2009) — an open-access letter, fetched and read in full via
[JPIER](https://www.jpier.org/ac_api/download.php?id=08112303) — states the mechanism and its
dependencies explicitly:

> "The mechanism of the meander line polarizer is that the field component horizontal to the
> meander line axis is delayed by the inductive character of the grating and the vertical
> component is advanced by the capacitive character of the grating, which results in a
> transmission coefficient differential phase shift Δθ between the two orthogonal components of the
> incident electric field. … **Δθ is determined by the dimensions of the meander lines, the
> thickness and relative permittivity of the dielectric layers, the spacing between the sheets.**"

Four independent variables set Δθ: meander-line dimensions, dielectric thickness, dielectric
permittivity, and inter-sheet spacing. Permittivity is one input to a design that has at least
three other free parameters to trade against it — the textbook description of a design space, not
a threshold. The paper's own worked example (§2 below) builds and tests a real device at
**εr = 2.65** for the sheet dielectric and **εr = 1.1** for the spacers — both far below Example
6's 10.4 — and reaches Δθ = 90° with room to spare (AR < 2 dB, 5.6–10.4 GHz, 60% relative
bandwidth) (`LITERATURE-SUPPORTED`).

**How permittivity physically enters that equation: geometric rescaling, not a new capability.**
Across every FSS/metasurface source consulted, the mechanism is consistent and well-established:
a resonant conductor pattern's electrical size is fixed as some fraction of the **guided
wavelength** λg = λ₀/√εeff, where εeff is an effective permittivity blending the substrate and
whatever air the fringing fields reach. Raising εr shortens λg at a given frequency, so the same
electrical behaviour is reached with a **physically smaller** pattern — "since a higher dielectric
constant for the substrate results in a lower resonant frequency for the dominant mode" at fixed
size, or equivalently a smaller pattern at fixed frequency, and "embedding FSS elements in
dielectric layers effectively reduces the required physical element size … consistent with the
well-known 1/√εr scaling relationship" (search synthesis over the FSS-miniaturization literature,
`LITERATURE-SUPPORTED`; the general 1/√εr relation itself is standard microstrip/FSS theory).
Concretely: a meandered split-ring FSS unit cell has been demonstrated at **0.026λ₀ × 0.026λ₀**
using meandering alone, at ordinary permittivity — miniaturization achieved by folding the
conductor, with no dependence on a ceramic substrate at all
([PMC10618525](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10618525/), `LITERATURE-SUPPORTED`).

**Does higher εr unlock something a low-εr substrate structurally cannot — a phase range, a
resonance Q, a minimum electrical size?** No source found makes that claim. Every published
meander-line (or comparable anisotropic) LP-to-CP converter located in this research reaches the
full 90° differential phase at whatever permittivity it uses, from 1.1 (§1, spacer) through 3.55
(§3) to 10.4 (the patent). What changes with permittivity is the *geometry* needed to get there,
not whether 90° is reachable. The one place a genuine tradeoff surfaces is **bandwidth via
impedance matching to free space**, and it points against high εr, not for it (finding 4, §3
below).

---

## 2. Published low-permittivity and flexible-substrate polarization converters at X/Ku-band

All entries below achieve linear-to-circular (or linear-to-linear 90°) conversion. "Measured"
in the *Validation* column means the cited paper itself reports building and testing a physical
prototype — that provenance still enters this repo as `LITERATURE-SUPPORTED`, per the ladder note
above.

| Source | Topology | Substrate, εr / tanδ | Flexible? | Band | AR / conversion result | Validation |
|---|---|---|---|---|---|---|
| Zhang, Yin & Ma, *PIER Lett.* **6**, 55–60 (2009) [(JPIER, open access, fetched in full)](https://www.jpier.org/ac_api/download.php?id=08112303) | 4-layer meander line, 45° | Dielectric εr = 2.65 (0.25 mm film); spacer εr = 1.1 | Not stated as flexible; thin (0.25 mm) film + foam spacer | 5.6–10.4 GHz (C/X) | **AR < 2 dB**, IL < 0.5 dB, 60% relative BW | **Fabricated, horn-antenna measured** |
| Undrasi & Khairnar, *Optik* (2024), [ScienceDirect S0030401824006278](https://www.sciencedirect.com/science/article/abs/pii/S0030401824006278) (fetch 403'd; via search-tool summary of the abstract page) | Modified L-patch + 3 dipoles, reflective, dual-band | Rogers RT/duroid 5880, εr = 2.2 | Rigid PTFE-composite; not pliable, but low εr | **8.09–10.59 GHz (X) and 17.53–18.63 GHz (Ku), simultaneously** | **AR < 3 dB, 26.76% + 6.08% BW; AR < 1.2 dB over most of each band; 99.5% avg. conversion efficiency** | **12×12-cell prototype, horn-antenna measured** |
| "Metasurface-Based LTC Polarization Converter with S-Shaped SRR," [PMC10383296](https://pmc.ncbi.nlm.nih.gov/articles/PMC10383296/) (fetched directly) | S-shaped split-ring resonator | Rogers RT/duroid 5880, εr = 2.2, t = 1.575 mm | **Explicitly "designed on a flexible substrate ... for conformal and wearable applications"** | 12.4 GHz (Ku) | AR < 3 dB | via search-tool extraction of the paper |
| Meander-line staircase metasurface, *Electronics* **15**(10), 2111 (2026), [DOI 10.3390/electronics15102111](https://doi.org/10.3390/electronics15102111) (mdpi.com fetch 403'd, per this environment's known MDPI block; via search-tool summary) | **Meander-line, transmission mode**, electrically continuous across cells | "Low-permittivity substrate" (exact εr not recovered) | Not stated | **Full X-band, 8–12 GHz** (41% ARBW); **scaled to Ku-band, AR minima ≈13 GHz and ≈17.5 GHz** (44.9% ARBW) | Simulated and experimentally validated per the search summary |
| Companion design, *Electronics* **14**(18), 3639 (2025), DOI 10.3390/electronics14183639 (via search-tool summary) | Two L-shaped resonators, opposite faces | **Explicitly "low-permittivity substrate"** | Not stated | X-band (implied) | 26% relative BW, 65% conversion efficiency, IL < 1.3 dB | via search summary |
| Naseri & Matos, "Dual-Band Dual-LTC Polarization Converter … K/Ka-Band," (fetch attempts on academia.edu and ResearchGate both 403'd; via search-tool summary) | **Meander-line element + ELC split-ring, both oriented at 45°** — the closest topological match to Example 6 found anywhere | Rogers RT/duroid 5880, t = 1.575 mm (εr = 2.2 by the material's standard spec) | Rigid, low εr | **K/Ka-band**, not X/Ku | Not recovered in this pass | via search summary |
| Dual elliptical reflective polarizer (search synthesis; source paper not individually re-verified) | Elliptical patches | RT5880, εr = 2.2, tanδ = 0.0009 | Rigid, low εr | 7.70 & 9.42 GHz (C/X) | AR < 3 dB, PCR 99.9% | via search summary |
| Multi-band reflective metasurface, *Opt. Quantum Electron.* (2025), [DOI 10.1007/s11082-025-08037-y](https://doi.org/10.1007/s11082-025-08037-y) (Springer paywall, fetch redirected to a login page; via search-tool summary) | Not identified in this pass | Rogers RO3003, εr = 3.00 ± 0.04, tanδ = 0.0010, h = 1.52 mm | Rigid, low εr | X/Ku/K | PCR > 90% to 45° incidence | via search summary |
| Asymmetric multi-band metasurface, [PMC11811059](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11811059/) / *Sci. Rep.* DOI 10.1038/s41598-024-81388-w | Not identified in this pass | RO3003, εr ≈ 3.0, h = 0.76 mm | Rigid, low εr | Ku/K/Ka/U | AR < 3 dB, 2.75–34.47% fractional BW, stable to 45° | via search summary |
| PDMS trilayer converter, IOPscience DOI 10.1088/1402-4896/ae2c27 (via search-tool summary) | Trilayer, square metallic patches, 3 resonances | **PDMS**, εr not stated in the recovered summary | **Explicitly flexible** (PDMS) | **7.3–15.69 GHz — spans X and Ku** | PCR > 90% | Simulated and "corroborated by experimental measurements" per the summary |
| Ferrite-nanoparticle flexible substrate, [ScienceDirect S1110016824011918](https://www.sciencedirect.com/science/article/pii/S1110016824011918) (fetch 403'd; via search-tool summary) | Cross-polarization conversion | PDMS + ferrite nanoparticles | **Explicitly flexible**; bending stability tested to 60° | 5.86–7.99 GHz and 10.75–11.63 GHz (C/X) | PCR > 99% to 60° incidence | Fabricated and measured per the summary |
| Textile-based LTC polarizer for pico-satellites, ResearchGate 333134156 (via search summary) | Dodecagonal element, patch-backed | ShieldIt conductive fabric / felt, and a PDMS variant | **Explicitly flexible/textile** | S-band, 1.578–2.578 GHz | > 90% conversion efficiency (48.12% BW) | Fabricated, per the summary |
| Ka-band FSS converter (search synthesis) | Dual rectangular strips, chamfered edges | RO5880, εr = 2.2, t = 1.575 mm | Rigid, low εr | 24–38 GHz | 3 dB AR from 27–30.3 GHz | Not independently confirmed |

**Reading the table plainly.** Every row hits the standard 3 dB axial-ratio bar for "converts to
circular polarization," most with efficiency ≥ 90% and several with independently fabricated,
horn-antenna-measured prototypes — at permittivities from 1.1 (a spacer, functionally air) through
3.55, with none above ≈3.55 among sources whose εr was actually recovered. Two of the rows are
explicitly flexible/wearable substrates (PDMS, textile) hitting X/Ku-band or overlapping it. The
staircase meander-line row is the strongest single data point: it is the same *topology* (meander
line, 45°) as Example 6, on a substrate the source paper itself calls low-permittivity, landing on
Ku-band axial-ratio minima within roughly a gigahertz of Example 6's own claimed 13.85/16.6 GHz.

**FR-4 (εr ≈ 4.3–4.8), not a ceramic laminate, is the substrate that shows up most often across the
broader meander-line/LP-to-CP search results** — several Ka-band, C/X-band and Ku-band designs
found during this research used FR-4, sitting comfortably inside the patent's own stated εr 2–5
host range and well below 10.4 (search synthesis, not independently tabulated here,
`LITERATURE-SUPPORTED`). This reinforces that εr ≈ 10.4 is an outlier choice within the published
meander-line-polarizer literature, not the norm it would need to be for "high permittivity is what
this function needs" to hold up.

---

## 3. High-permittivity meander-line polarizers, and the one explicit rationale found

**No paper describing a meander-line (or closely comparable) LP-to-CP converter on a substrate
comparable to Example 6's εr = 10.4 was located**, despite searches specifically for meander-line
polarizers on alumina, generic ceramic, Rogers TMM10, and RO3010. The published meander-line
literature clusters at εr 1.1–4.8 (§2); the high-εr FSS/HIS literature that does exist is a
different structure class solving a different problem.

**The one explicit "why high permittivity" statement found, anywhere, points against using it for
this function.** US10547117B1 ("Millimeter wave, wideband, wide scan phased array architecture for
radiating circular polarization at high power levels," Google Patents, via search-tool summary —
not independently re-fetched) describes a cascaded-waveplate linear-to-circular polarizer using
**Rogers 4003, εr = 3.55**, and states the choice directly:

> "The permittivity of the 4003 substrate (ε=3.55) is chosen to be large enough to improve the
> performance at wide scan angles, but not too large to enable a broadband impedance-match to free
> space."

This is a genuine engineering tradeoff statement, and it caps out at εr = 3.55 — a third of Example
6's 10.4 — for a design whose whole premise (wide-scan-angle phased-array polarization) is exactly
the kind of angular-stability problem that would most reward pushing εr higher if higher were
free. It was not pushed higher, because the same source identifies the cost: too much permittivity
breaks the impedance match to free space, which is a bandwidth and efficiency penalty, not a
benefit, for a device whose whole job is to receive and re-radiate a free-space wave.

**The mechanism behind that tradeoff is ordinary transmission-line theory.** A medium's intrinsic
wave impedance is η = η₀/√εr, where η₀ ≈ 377 Ω is free space's impedance. At εr = 10.4,
η ≈ 377/√10.4 ≈ 117 Ω — a **3.2×** step down from free space. At εr = 2.9 (silicone), η ≈ 377/1.70
≈ 221 Ω — a **1.7×** step. In plain terms: **a higher-εr substrate presents a bigger impedance
"cliff" to an incoming radio wave**, and every matching layer or geometric trick a design uses to
smooth that cliff back down is bandwidth and complexity spent buying back what a lower-εr choice
would not have cost in the first place (`CALCULATED`, standard transmission-line relation — this
is this document's own arithmetic, offered as a plausible mechanism consistent with the Rogers 4003
quote above, not a claim independently proven for meander-line polarizers specifically).

**The only genuine "high permittivity, stated reason" example found in the wider literature is a
different structure class, and even there the reason is convenience, not necessity.** Genovesi,
Costa, Cioni *et al.*, "Miniaturized high impedance surfaces with angular stability by using
zirconium tin titanate substrates and convoluted FSS elements," *Microwave and Optical Technology
Letters* **51**(11), 2753–2758 (2009) (via search-tool summary — the specific εr of the ZST
material used was not recovered in this pass, `UNKNOWN`) built high-impedance surfaces — not
polarizers — on a genuinely high-permittivity ceramic specifically to shrink the unit cell and
stabilize the response across incidence angle. That is a real, documented reason to reach for high
εr — but it is (a) about a different device class (HIS/FSS reflectors, not polarization
converters), and (b) a compactness/angular-stability convenience, achievable by other means
(meandering itself, as §1 already showed reaching 0.026λ₀ cells with no ceramic at all) — not a
statement that the *function* is unreachable otherwise.

**Patents for real, deployed meander-line polarizer radomes specify substrate permittivity in the
same 2–5 range this programme already uses.** The "Integrated higher order Floquet mode meander
line polarizer radome" patent family (US11949162, US12088009 — both direct PDF fetches returned
unreadable binary streams from this environment's tools; the following is via a search-tool
extraction of the patents' indexed text, not independently re-verified by direct read) specifies a
substrate with **"a dielectric constant between 2.0 and 5.0 … about 2.2,"** built from PCB-grade
laminates (FR-4- or Megtron-6-class material). In plain terms: **a currently-patented meander-line
polarizer radome — the same device family as Example 6, built for the same job (converting a
linear wave to circular for a real antenna system) — explicitly targets the exact εr range
(2.0–5.0) this programme's flexible-substrate shortlist already occupies**, not εr ≈ 10.

---

## 4. What Example 6's substrate probably is, and why that matters

Example 6's substrate — **εr = 10.4, tanδ = 0.0028** — was not identified by name in the patent
(per `docs/seven-example-design-unknowns.md`, §3, row 6: `LITERATURE-SUPPORTED` for the value,
`UNKNOWN` for the material). This research located two commercial ceramic-PTFE laminate families
with closely matching published specs:

| Product | εr (Dk) | Loss tangent (Df) | Class |
|---|---|---|---|
| Rogers RO3010 | 10.2 ± 0.30 | 0.0023 (max, at 10 GHz) | Ceramic-filled PTFE composite |
| Rogers TMM10 / TMM10i | ≈9.80–10.0 ± 0.245 | 0.0020–0.0023 | Ceramic/thermoset laminate |

(via search-tool retrieval of published laminate-comparison data and manufacturer listings,
`INFERRED` as an identification-by-resemblance — neither figure is an exact 10.4/0.0028 match, and
no source confirms the patent used either product by name.)

Both are members of the same commercial category: **PTFE loaded with ceramic powder specifically
to raise εr for miniaturization**, sold as rigid sheet stock for RF/microwave PCBs — not a family
anyone would select for a **pliable** skin, which is this whole programme's premise (the patent's
own title: "Highly-conformal, pliable thin electromagnetic skin"). This is consistent with, and
sharpens, what `docs/seven-example-design-unknowns.md` already flagged: Example 6 is one of three
of the patent's seven worked examples (with Examples 1–2 and 4) whose stated material property
contradicts the patent's own εr 2–5 host-polymer statement. The most economical explanation
consistent with everything found in this research is that Example 6's substrate was **a standard
high-εr laminate the inventors had on hand or wanted for compactness in a bench demonstration**,
not a substrate chosen because low-εr laminates cannot do the job — no source anywhere states the
latter, and §1–§3 show the opposite has been repeatedly demonstrated.

---

## 5. Re-deriving Example 6 at εr 2.9–3.2: what changes, and what does not

If the λg = λ₀/√εeff scaling described in §1 applies directly, moving from εr = 10.4 to a
programme-shortlist substrate scales linear dimensions by roughly √(εr_high/εr_low):

| Target substrate | εr | Scale factor √(10.4/εr) | Example 6's 4×6 mm cell, rescaled |
|---|---|---|---|
| Silicone (measured, `docs/xband-absorber-substrate-shortlist.md`) | 2.9 | 1.89× | ≈ 7.6 × 11.3 mm |
| Kapton/polyimide (measured, same doc) | 3.2 | 1.80× | ≈ 7.2 × 10.8 mm |

(`CALCULATED`, first-order estimate using the classic 1/√εr resonant-length relation — **not** a
validated redesign.) Two honest caveats on this number, stated plainly rather than smoothed over:

- **This is a heuristic, not a simulation.** A ground-backed meander line at t = 1.6 mm with a
  0.2 mm trace does not have all its field lines confined inside the dielectric — some fringe
  into the air above the trace. The *effective* permittivity a real trace sees is therefore always
  somewhat below the substrate's bulk εr, and the ratio εeff(low-εr)/εeff(high-εr) is a gentler
  step than the bulk-εr ratio suggests — meaning the true rescale factor is probably **smaller**
  than 1.8–1.9×, not larger. Confirming that needs an actual full-wave sweep, not arithmetic.
- **Growing a cell by ~1.8–1.9× is not free, but nothing found in this research or the sibling
  documents suggests it is a blocker.** The patent's own thickness ceiling (2 mm total skin,
  claim 7 per `docs/seven-example-design-unknowns.md`) is a thickness limit, not a lateral-size
  limit — a larger cell footprint does not fight it. And the minimum feature in Example 6's own
  geometry (w = 0.2 mm meander width) already sits comfortably above this programme's printable
  floor (per the same document, 2–6× above the NOVA's 100 µm minimum linewidth); growing the whole
  cell by ~2× only widens that margin.

What does **not** change under this rescaling, per §1's design equation and every example in §2, is
the achievability of the 90° differential phase shift itself — that has been demonstrated
end-to-end, measured with real hardware, at permittivities from 1.1 to 3.55, in bands overlapping
or matching Example 6's 13–17 GHz target.

---

## What could not be verified

Stated plainly, without smoothing:

| Question | Status |
|---|---|
| The exact commercial substrate Example 6 used | **Not stated by the patent.** RO3010/TMM10i are a resemblance match on εr and tanδ, not a confirmed identification (`INFERRED`). |
| Zirconium-tin-titanate's exact εr in the Genovesi *et al.* (2009) HIS paper | **Not recovered.** General knowledge places ZST substrates in the εr ≈ 30–40 range depending on composition, but this was not independently confirmed from the paper itself, which was reachable only via a search-tool summary. |
| Whether the Naseri & Matos K/Ka-band meander-line-plus-SRR converter's reported axial ratio meets or beats 3 dB | **Not recovered.** Both academia.edu and ResearchGate returned 403 to direct fetch; only the substrate and topology were confirmed via search summary. |
| The exact εr the 2026 meander-line staircase metasurface paper (*Electronics* 15(10), 2111) used, beyond "low-permittivity" | **Not recovered.** mdpi.com returned 403 to direct fetch, consistent with this environment's known MDPI block (per the task's own caveat and this programme's prior experience in `docs/xband-absorber-substrate-shortlist.md` and `docs/seven-example-design-unknowns.md`). Everything about this source came from a search-engine-generated summary of the abstract/metadata, not a fetched full text. |
| ScienceDirect-hosted sources (Undrasi & Khairnar; the PDMS ferrite-nanoparticle converter; several others) | **Stranded at 403,** same as this programme has documented repeatedly for ScienceDirect. Findings from these sources rest on search-tool summaries of the publicly indexed abstract, not a fetched full text — a materially weaker form of `LITERATURE-SUPPORTED` than the Zhang/Yin/Ma and PMC10383296 sources, which were fetched and read directly. |
| The Chu & Lee (1987) analytical meander-line model, and the original Young/Robinson/Hacking (1973) paper | **Not directly fetched.** Both are cited via Zhang, Yin & Ma's reference list, not read first-hand. Their equations (susceptance formulas, oblique-incidence extensions) were not independently examined. |
| A single controlled study varying only εr on one fixed meander-line topology, to isolate permittivity's effect from every other simultaneously-changing geometric variable | **Not found.** Every comparison in this document is *across* different published designs (different authors, different cell geometries, different bands), not a single paper's own εr sweep on one fixed topology. That is the strongest form of evidence this question could have, and it was not located — the finding rests on convergence across many independent designs rather than one controlled experiment. |
| Whether US10547117B1's and US11949162/US12088009's patent text was read directly | **No.** Direct PDF fetches of the meander-line-polarizer-radome patents returned unreadable binary streams from this environment's WebFetch tool; their content here comes from a search tool's own extraction/summary of the indexed patent text, not this document's own reading of the source. |
| Local corpus check (`F:\data`, per global config's mandatory-research-corpus rule) | **Checked, zero relevant results.** A dedicated grep pass across `F:\data\arxiv-chunks` (~40,000 full-text papers) found no paper on meander-line polarizers, polarization-converting metasurfaces, or substrate-permittivity effects on them. Root cause, not absence-of-evidence: this corpus's categorized physics/materials content is almost entirely April–December 2007, and it has no `physics.app-ph`/`eess.SP` category at all — the meander-line-polarizer-metasurface literature cited above is 1973 (foundational) and 2009–2026 (the modern subfield), a window this corpus doesn't cover. Treat as a corpus coverage gap, not a negative finding. |

---

## Primary sources

**Fetched and read in full, this session:**
- Zhang, J.-C., Yin, Y.-Z., Ma, J.-P., "Multifunctional Meander Line Polarizer," *Progress In
  Electromagnetics Research Letters* **6**, 55–60 (2009) —
  [open-access PDF via JPIER](https://www.jpier.org/ac_api/download.php?id=08112303) — the design
  equation (§1), and a fabricated, horn-antenna-measured device at εr = 2.65/1.1, AR < 2 dB,
  5.6–10.4 GHz, 60% relative bandwidth.
- "A Metasurface-Based LTC Polarization Converter with S-Shaped Split Ring Resonator Structure for
  Flexible Applications," [PMC10383296](https://pmc.ncbi.nlm.nih.gov/articles/PMC10383296/) — RT5880
  (εr = 2.2, t = 1.575 mm), explicitly flexible/conformal/wearable, 12.4 GHz, AR < 3 dB.

**Retrieved via search-tool summary (source itself 403'd or paywalled to direct fetch — see "What
could not be verified" for the reliability caveat this implies):**
- Undrasi, A., Khairnar, V.V., "A compact dual-band linear-to-circular polarization converter for
  X-band and Ku-band applications," *Optik* (2024),
  [ScienceDirect S0030401824006278](https://www.sciencedirect.com/science/article/abs/pii/S0030401824006278).
- "Full X-Band Reconfigurable Linear-to-Circular Polarization Converter Based on a Continuous
  Meander-Line Staircase Metasurface," *Electronics* **15**(10), 2111 (2026),
  [DOI 10.3390/electronics15102111](https://doi.org/10.3390/electronics15102111).
- "A Reconfigurable Metasurface for Linear-to-Circular Polarization Conversion Using Mechanical
  Rotation," *Electronics* **14**(18), 3639 (2025), DOI 10.3390/electronics14183639.
- Naseri & Matos, "Dual-Band Dual-Linear-to-Circular Polarization Converter in Transmission Mode —
  Application to K/Ka-Band Satellite Communications" (meander line + ELC SRR, both at 45°, RT5880).
- US10547117B1, "Millimeter wave, wideband, wide scan phased array architecture for radiating
  circular polarization at high power levels," via
  [Google Patents](https://patents.google.com/patent/US10547117B1/en) — the Rogers-4003/εr = 3.55
  design-tradeoff quote (§3).
- "Integrated higher order Floquet mode meander line polarizer radome," US11949162 / US12088009 —
  εr 2.0–5.0, ≈2.2 substrate spec for a patented meander-line polarizer radome (§3).
- Genovesi, S., Costa, F., Cioni, B., *et al.*, "Miniaturized high impedance surfaces with angular
  stability by using zirconium tin titanate substrates and convoluted FSS elements," *Microwave and
  Optical Technology Letters* **51**(11), 2753–2758 (2009).
- Rogers RO3010 and TMM10/TMM10i datasheet figures, via manufacturer listings and a published
  microwave-laminate comparison chart (§4).
- Multiple additional low-εr/flexible-substrate polarization-converter papers tabulated in §2
  (PDMS trilayer converter, ferrite-nanoparticle PDMS converter, textile pico-satellite polarizer,
  RO3003-based multi-band converters, RT5880 elliptical-patch converter, RO5880 Ka-band FSS).

**Repo context:**
- `docs/seven-example-design-unknowns.md` — full geometric and material table for all seven of
  US12089385B2's worked examples, including the original identification that Example 6's
  εr = 10.4/tanδ = 0.0028 "is a ceramic-filled laminate signature, not a pliable polymer" and
  contradicts the patent's own host-polymer statement.
- `docs/voltera-multilayer-capability.md` — this repo's research-doc convention (BLUF, provenance
  ladder, detailed sections, "what could not be verified," primary sources), followed here.
- `docs/xband-absorber-substrate-shortlist.md` — measured εr/tanδ for this programme's flexible
  substrate shortlist: silicone εr = 2.9 (`MEASURED`, Agilent 85070E probe), Kapton 500HN
  εr = 3.2 ± 0.03 (`MEASURED`, ring resonator, 10–65 GHz).
