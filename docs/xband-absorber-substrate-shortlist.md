# Substrate Shortlist for a Flexible X-Band Absorber

**Research date:** 2026-09-03
**Ticket:** [#114](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/114), child of the wayfinder map [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104)
**Scope:** Which substrates give an X-band (8–12 GHz) absorber a loss tangent it can work
with, across the range of host surfaces a customer requirement might state. The patent's
Example 3 absorber sits on rigid FR4 (εr 4.8, tanδ 0.017), and for an absorber that loss
tangent is a primary design input, not incidental — so swapping to a flexible **low-loss**
substrate weakens absorption and has to be compensated somewhere else.

Provenance tags are `CONTEXT.md`'s ladder — `MEASURED` → `SIMULATED` → `CALCULATED` →
`MANUFACTURER-SPECIFIED` → `LITERATURE-SUPPORTED` → `INFERRED` → `ASSUMED` → `UNKNOWN`.
No parallel confidence vocabulary is introduced.

---

## Bottom line up front

Four findings, in descending order of how much they change the picture.

1. **A deliberately-lossy flexible substrate exists, is commercial, is cheap, and has
   already been demonstrated at X-band at the patent's own thickness.** Plain 60 Shore A
   silicone sheet (Polymax SILONA, FDA/GP grade) was **measured** at **εr = 2.9,
   tanδ = 0.10** and used as a 2 mm conformal radar-absorber substrate spanning X and Ku
   bands, printed with graphene ink and bent around a 5.9 cm-radius metal cylinder for only
   a 3.6% bandwidth penalty (Huang, Pan & Hu, *Sci. Rep.* **6**, 38197, 2016,
   DOI [10.1038/srep38197](https://doi.org/10.1038/srep38197)). That tanδ is **~6× FR4's**.
   It resolves the ticket's central tension in the opposite direction from the one assumed:
   going flexible does not have to cost dissipation, it can buy more of it. Silicone's
   weakness is adhesion, not loss (§5).

2. **Polyimide is not a low-loss substrate at X-band.** The datasheet-nominal ~0.002 is a
   kHz figure. Measured on 127 µm Kapton 500HN with a ring resonator, **tanδ = 0.012 ± 0.004
   and εr = 3.2 ± 0.03** across 10–65 GHz (Yang *et al.*, *Wireless Power Transfer*,
   DOI [10.1017/wpt.2015.21](https://doi.org/10.1017/wpt.2015.21)). At 0.012 versus FR4's
   0.017, polyimide gives up only ~30% of the substrate dissipation, not an order of
   magnitude. This is the single most useful correction in the report, and it is exactly the
   `MANUFACTURER-SPECIFIED`-at-1-kHz versus `MEASURED`-at-X-band gap the ticket warned about.

3. **The cure ceiling prunes less of the conductor set than the handoff's matrix says.**
   `docs/HANDOFF-metamaterial-printing-grill.md` marks silver `✗` on both PET and TPU. Two
   primary sources contradict that: silver nanoparticle ink sintered at **120 °C / 30 min on
   PET** with cross-cut adhesion testing (*J. Electrochem. Soc.*
   [10.1149/2.0091909jes](https://doi.org/10.1149/2.0091909jes)), and
   **DuPont/Celanese Micromax Intexar PE874**, a stretchable silver conductor whose
   datasheet cure is **"Dry at 130 °C for 15 minutes"** and which is stated to be
   "compatible with polyurethane (TPU) film and select synthetic fabrics"
   ([PE874 TDS](https://www.ccieurolam.com/wp-content/uploads/PE874-TDS.pdf)) — and which
   Voltera already lists as a NOVA-compatible ink (`docs/mxene-voltera-nova-printability.md`
   §6). Photonic/intense-pulsed-light curing decouples the ink's peak temperature from the
   substrate's entirely ([NovaCentrix PulseForge](https://pulseforge.com/pulseforge_blog/the-evolution-of-photonic-curing/)).
   **What actually prunes silver is not the substrate class — it is whether the part can
   leave the host for an oven or a flashlamp.** That is precisely the regime split the map
   describes, and it should be modelled as a process constraint, not a material one.

4. **The adhesion asymmetry is real and it points the opposite way from the loss tangent.**
   Silver-on-polyimide and silver-on-PET are well-evidenced; Intexar PE874 is a
   manufacturer-qualified silver-on-TPU/textile path. MXene-on-PET is demonstrated,
   MXene-on-polyimide is directionally confirmed but never adhesion-tested,
   MXene-on-TPU is unpublished, and MXene-on-textile has a literature-acknowledged
   unresolved adhesion problem. Meanwhile **the best lossy substrate (silicone) is the worst
   adhesion substrate for any printed ink** — native PDMS/silicone is too low-surface-energy
   to print on at all without plasma or UV-ozone pretreatment. See §5.

---

## The arithmetic that reframes the question

The patent's Example 3 substrate contributes dissipation roughly in proportion to tanδ.
Against FR4's 0.017 (`LITERATURE-SUPPORTED`, from the patent via
`docs/HANDOFF-metamaterial-printing-grill.md`):

| Substrate | tanδ @ X-band | Ratio to FR4 | Effect on substrate dissipation |
|---|---|---|---|
| LCP (ULTRALAM 3850) | 0.0025 | 0.15× | ~7× **less** — worst case for the swap |
| Rogers RO4350B | 0.0037 | 0.22× | ~5× less |
| PDMS | ~0.01–0.02 (see caveat, §3) | ~0.6–1.2× | roughly comparable |
| Polyimide (Kapton 500HN) | 0.012 | 0.7× | ~30% less — nearly a wash |
| **FR4 (Example 3 baseline)** | **0.017** | **1.0×** | — |
| Felt (textile) | ~0.016–0.041 | 0.9–2.4× | comparable to **more** |
| Denim (textile) | ~0.073–0.086 | 4.3–5.1× | ~5× **more** |
| **Silicone sheet, 60 ShA** | **0.10** | **5.9×** | **~6× more** |

`CALCULATED` (ratio arithmetic only). The premise "flexible ⇒ low loss ⇒ weaker absorber"
holds only for the engineered low-loss laminates (LCP, PTFE-class). Every commodity flexible
polymer and every textile in this survey sits at or above FR4's loss tangent.

---

## 1. Main shortlist

Host regime: **A** = large-radius hosts (wing, hull, sUAS body), where `R = 3T` clears by
one to two orders of magnitude and rigid-but-low-loss substrates are fully competitive;
**B** = tight or compound-curvature hosts (textiles, small fairings, anything that cannot
leave the airframe for an oven). Entries serving both are marked **A+B**.

Against the patent's **0.87–2.0 mm total skin thickness** and its **`R = 3T`** minimum bend
radius (so R = 2.6–6.0 mm at the patent's own thickness bounds).

| # | Substrate | εr @ X-band | tanδ @ X-band | Provenance | Thickness range | Min bend radius | Cure-temp ceiling | Host regime |
|---|---|---|---|---|---|---|---|---|
| 1 | **Silicone sheet, 60 ShA** (Polymax SILONA GP/FDA) | **2.9** | **0.10** | `MEASURED` — Agilent 85070E dielectric probe, Huang *et al.* 2016 | 0.5–6 mm stock (12 mm on request); **2 mm used at X/Ku** | Elastomer; demonstrated conformal at **R = 59 mm** on a cylinder; no vendor minimum published | **−60 to +230 °C continuous** ([Polymax TDS](https://www.polymax.co.uk/silicone-products/polymax-silona-black-1-2m-x-10m-x-2-0-mm-thick.html)) | **A+B** |
| 2 | **Polyimide** (DuPont Kapton 500HN) | **3.2 ± 0.03** | **0.012 ± 0.004** | `MEASURED` — microstrip ring resonator, 10–65 GHz, Yang *et al.* | 25–127 µm per ply; needs 7–16 plies to reach 0.87–2.0 mm | IPC-2223 static: 6× total thickness (single-sided) → 0.76 mm at 127 µm | ~400 °C (handoff, `LITERATURE-SUPPORTED`) | **A+B** |
| 3 | **LCP** (Rogers ULTRALAM 3850) | **2.9** | **0.0025** | `MANUFACTURER-SPECIFIED` **at 10 GHz / 23 °C**, IPC 2.5.5.5.1 — at-frequency, not kHz | **25 / 50 / 100 µm** only; 9–80 plies to reach the patent window | "Low modulus — bends easily for flex and conformal applications" (no number given) | Melt 315 °C; solder float 288 °C pass | **A+B** (thickness is the binding problem, not flex) |
| 4 | **Eccosorb BSR / MFS** (Laird, magnetically loaded silicone) | **UNKNOWN** | **UNKNOWN** | ε′/ε″/µ′/µ″ **not published** — datasheet gives dB/cm attenuation only | Sheet stock; specific thicknesses not in the accessible datasheet text | "Flexible and can be fitted to **compound curves**"; "very flexible material and conforms to contoured surfaces" | **160 °C service temp**; RTV-silicone bonding above 121 °C | **A+B** |
| 5 | **PDMS** (Sylgard-class, cast) | **2.9 → 2.55** over 1–220 GHz | **not separately tabulated at X-band**; reaches 0.048 only at 210 GHz | `MEASURED` for εr (CPW de-embedding, Cresson *et al.* 2014); tanδ at X-band `INFERRED` from the same curve | Castable to any thickness incl. the full 0.87–2.0 mm window in one pour | Elastomer; no vendor minimum | ~200 °C service (`LITERATURE-SUPPORTED`) | **B** (and A) |
| 6 | **PET, heat-stabilised** (DuPont Melinex ST505) | ~3.0 | **UNKNOWN at X-band** | `MANUFACTURER-SPECIFIED` values are kHz–MHz; no X-band measurement found | 25–350 µm per ply | IPC-2223-class, ~6× thickness static | Heat-stabilised grade survives the **130 °C** Intexar cure (it is the qualification substrate on the PE874 TDS); the handoff's "~80 °C" figure applies to unstabilised PET | **A+B** |
| 7 | **TPU film** | **UNKNOWN at X-band** | **UNKNOWN at X-band** | No X-band measurement found; the only accessible number is 1 MHz and strain-dependent (8.02 → 2.88 at 400% strain) — and that source is MDPI-stranded (§7) | 50 µm–2 mm | Elastomer | **130 °C** demonstrated via PE874 (`MANUFACTURER-SPECIFIED`) | **B** |
| 8 | **Textile — felt** (wool blend) | 1.13–1.34 (some sources 1.22) | 0.016–0.041 | `LITERATURE-SUPPORTED`; measured mostly at 2.45/5.8 GHz, **not** X-band; moisture-dependent | 1–3 mm typical — sits inside the patent window natively | Drapes freely | Fibre-dependent; PE874 qualified on "select synthetic fabrics" | **B** |
| 9 | **Textile — denim/jean** | 1.63–1.81 (one source 2.2) | **0.073–0.086** | `LITERATURE-SUPPORTED`; same caveat as felt | ~0.5–1 mm | Drapes freely | Cotton ~150 °C | **B** |
| 10 | **FR4 (Example 3 baseline)** | **4.8** | **0.017** | `LITERATURE-SUPPORTED` — from the patent, via the handoff | 0.8 / 1.6 mm standard | Rigid — no bend | ~130–180 °C Tg | **A** only |
| 11 | **Rogers RO4350B** | **3.48 ± 0.05** | **0.0037** | `MANUFACTURER-SPECIFIED` at 10 GHz / 23 °C | 0.17–1.52 mm — fits the patent window in one ply | Rigid | Hydrocarbon/ceramic, standard PCB thermal processing | **A** only |
| 12 | **Glass / fused silica** | ~3.8 (borosilicate) | ~0.0002–0.001 | `LITERATURE-SUPPORTED` — no first-party X-band measurement retrieved in this pass | Arbitrary | Rigid | Effectively unlimited | **A** only |

### Deliberately-lossy candidates carried but not fully verified

| Substrate | Reported X-band electricals | Provenance | Why it is not in the main table |
|---|---|---|---|
| Carbon-fibre-loaded silicone foam (2% CF, 0.33 g/cm³) | ε′ 7 → 1.1 and dielectric loss 1.9 → 0.7 across 2–18 GHz | `LITERATURE-SUPPORTED`, **abstract only** | ScienceDirect returned 403; the numbers come from a search-result abstract, not a fetched page. Density-graded, so a single (εr, tanδ) pair does not describe it |
| rGO–SiC–LLDPE composite, 0.7 mm flexible | S11 ≈ −25 dB at 10.7 GHz, 96.7% absorption | `LITERATURE-SUPPORTED`, **not verified** | EPJ Applied Metamaterials PDF (DOI [10.1051/epjam/2020009](https://doi.org/10.1051/epjam/2020009)) is 5.6 MB and defeated every text-extraction route tried in this environment. Substrate εr/tanδ never recovered |
| TPU + carbonyl iron powder, FDM-printed (30–80 wt%) | CIP filler alone at 8 GHz: ε′ 24.32, ε″ 0.31, µ′ 1.77, µ″ 2.49. Composite values **graphical only** | `MEASURED` for the filler; `UNKNOWN` for the composite | *Polymers* 2022 via [PMC9695098](https://pmc.ncbi.nlm.nih.gov/articles/PMC9695098/). Magnetic loss dominates (tan µr > tan εr). 3 mm test thickness exceeds the patent's 2.0 mm; FDM at 205 °C nozzle / 90 °C bed is not a DIW route |
| Lossy silicone, 4 mm (same SILONA family) | εr 2.90, tanδ 0.10 | `MEASURED` (secondary use of the same material) | 4 mm is 2× the patent's thickness ceiling; listed only as corroboration of entry #1 |

---

## 2. What the two regimes actually select

### Regime A — large-radius hosts (wing, hull, sUAS body)

`R = 3T` at T ≤ 2 mm gives R ≤ 6 mm; a wing or hull curves on tens of centimetres to metres,
so the bend constraint clears by one to two orders of magnitude — exactly as
[#105](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/105) recorded.
The part can also leave the host for an oven, so the whole conductor set is live.

Survivors, ranked by how much of Example 3's dissipation they preserve rather than by
"best substrate":

- **FR4 itself (#10)** — if the requirement's host tolerates a rigid panel bonded to a
  large-radius surface, the patent's own substrate is still the highest-fidelity choice and
  needs no compensation at all. This deserves saying out loud: the map's "no thumb on the
  scale" principle cuts against reflexively discarding it.
- **Silicone sheet (#1)** — 2 mm, tanδ 0.10, takes a 130–230 °C cure, so silver and copper
  are both in play. Highest dissipation of anything surveyed.
- **Polyimide (#2)** — tanδ 0.012, 400 °C ceiling, the best-evidenced silver adhesion of any
  substrate here. Needs 7–16 plies (or a thick cast film) to reach the patent's thickness.
- **RO4350B (#11)** — single-ply 0.17–1.52 mm at εr 3.48, but tanδ 0.0037 removes ~78% of
  the substrate dissipation. Only worth it if the compensation budget is elsewhere.
- **LCP (#3) / glass (#12)** — lowest loss of all, therefore the largest compensation
  requirement. LCP additionally cannot reach the patent's thickness without a 9–80-ply
  laminate stack, which is a manufacturing problem, not an RF one.

### Regime B — tight or compound curvature (textiles, small fairings, no-oven hosts)

Here the NOVA's 40 °C material-temperature ceiling binds, and if the part genuinely cannot
leave the host, silver and copper are pruned and only the room-temperature conductor set
(MXene) survives — as the handoff argued. But note finding #3: **that pruning follows from
"cannot leave the airframe", not from the substrate**. A small fairing that can be printed on
a bench and cured in an oven keeps silver on TPU (PE874, 130 °C) or on heat-stabilised PET
(120 °C).

Survivors:

- **Silicone sheet (#1)** and **PDMS (#5)** — both castable/stock in the patent's thickness
  window, both fully conformable, and silicone's 230 °C service temperature means the cure
  ceiling is set by whether an oven is reachable, never by the substrate. **Adhesion is the
  binding constraint here, not loss and not temperature** (§5).
- **Textiles (#8, #9)** — natively in the 0.5–3 mm window, drape freely, and carry loss
  tangents at or **above** FR4's. Their problem is the opposite one: εr of 1.1–1.8 is far
  below FR4's 4.8, so the guided wavelength — and therefore the unit-cell periodicity the
  loop searches — shifts substantially. They are also moisture-dependent, which makes εr a
  function of environment rather than a constant.
- **TPU (#7)** — the only entry with **no X-band electrical data at all**. It is the most
  frequently assumed conformal substrate in this programme and the least characterised.
- **Eccosorb BSR/MFS (#4)** — explicitly sold for compound curves, but with no published
  permittivity it cannot be simulated. It would have to be characterised on the bench before
  the loop could use it.

---

## 3. Where the datasheet-versus-measured gap actually bites

The ticket's warning about datasheet-nominal-at-1-MHz is borne out unevenly:

| Substrate | Datasheet-nominal tanδ | Measured at X-band | Gap |
|---|---|---|---|
| Polyimide (Kapton) | ~0.002 (kHz) | **0.012 ± 0.004** (10–65 GHz) | **~6×** — the trap the ticket named, confirmed |
| LCP (ULTRALAM 3850) | 0.0025 — *already at 10 GHz* | — | none; Rogers specifies at frequency (IPC 2.5.5.5.1) |
| RO4350B | 0.0037 — *already at 10 GHz* | — | none |
| Silicone (SILONA) | **none published** | **0.10** (author-measured) | the vendor publishes no dielectric data at all |
| PET / TPU / textiles | kHz–MHz only, or none | **not found at X-band** | unquantifiable — the measurement does not exist in the accessible literature |

Two method caveats on the numbers that *are* measured, stated so a reader does not
over-trust them:

- The silicone εr/tanδ (#1) came from an **Agilent 85070E open-ended coaxial probe**. That
  method is well-suited to lossy and high-permittivity materials and is at its least accurate
  on low-loss, low-εr solids where air gaps at the probe face dominate. For a tanδ of 0.10 it
  is in its comfortable range, but the value carries method uncertainty the authors do not
  quote. Provenance stays `MEASURED`; confidence within that rung is not high.
- The Kapton figures (#2) are a **ring-resonator extraction fitted across 10–65 GHz**, i.e.
  a single (εr, tanδ) pair fitted to the whole band, not a per-frequency X-band point. Its
  lower bound is 10 GHz, so it covers only the **upper half** of X-band; 8–10 GHz is
  extrapolation from that fit.

---

## 4. Thickness and bend radius against the patent

The patent's `R = 3T` is **twice as aggressive as the flex-circuit industry's own static
rule.** IPC-2223 gives a minimum static bend radius of 6× total thickness for single-sided
flex (and up to 12× double-sided, 100× dynamic). At T = 2 mm, IPC-2223 would say R ≥ 12 mm
where the patent says R ≥ 6 mm. `LITERATURE-SUPPORTED`. Worth flagging to
[#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104): if the loop
enforces `R = 3T` as a hard `CALCULATED` constraint per open question Q6, it is enforcing a
patent-derived rule that is looser than the standard the flex industry applies to the same
material stack — and for a stack containing embedded rigid metamaterial elements, that is
the direction that costs reliability, not the safe direction.

Thickness fit against the patent's 0.87–2.0 mm:

- **Fits in a single ply:** silicone sheet (0.5–6 mm), PDMS (cast), felt (1–3 mm), FR4
  (0.8/1.6 mm), RO4350B (0.17–1.52 mm), Eccosorb BSR/MFS.
- **Needs lamination:** polyimide (7–16 plies of 127 µm), PET (3–80 plies), **LCP (9–80
  plies of 25–100 µm)**. LCP's thinness is the reason it does not simply win on flexibility:
  Rogers' own multilayer guidance forbids stacking ULTRALAM 3908 bondply to gain thickness
  and requires a spacer build instead, so an 0.87–2.0 mm LCP skin is a genuine multilayer
  construction, not a thicker sheet.

---

## 5. Adhesion evidence — MXene versus sintered silver

The asymmetry the ticket asked to keep visible. Shown, not averaged.

| Substrate | Sintered-silver adhesion | Provenance | MXene adhesion | Provenance |
|---|---|---|---|---|
| **Polyimide** | Strongest evidence in the survey. ASTM D3359 peel-adhesion **grade 5** reported for films sintered at 150 °C; nanoparticles not detached by scotch tape at 300 °C sinter | `LITERATURE-SUPPORTED` | Printing demonstrated (Frontiers 2026 DIW paper), but **no adhesion testing reported**, and that source is the conductivity outlier flagged in `docs/mxene-voltera-nova-printability.md` §4 | `LITERATURE-SUPPORTED` (printability only); adhesion `UNKNOWN` |
| **PET** | Sintered 120 °C / 30 min, 3 layers, 20 µm drop spacing, ρ = 5.25 µΩ·cm; adhesion tested per **ASTM D3359 cross-cut** | `LITERATURE-SUPPORTED` | Best-demonstrated MXene substrate — Song *et al.* 2022, spray-coated antennas, blade-coated films. Adhesion **not quantified** in any of them | `LITERATURE-SUPPORTED` |
| **TPU** | **Manufacturer-qualified.** PE874 is a stretchable silver conductor "compatible with polyurethane (TPU) film", cure 130 °C / 15 min, claimed "excellent stretchability, adhesion, and conduction" | `MANUFACTURER-SPECIFIED` | **Nothing found.** No source in either research pass reports MXene extrusion-printed on TPU | `UNKNOWN` |
| **Textile** | PE874 covers "select synthetic fabrics"; washable with proper encapsulation | `MANUFACTURER-SPECIFIED` (vendor does not name the fabrics) | **Acknowledged unresolved problem.** Weak interfacial bonding, poor wash fastness; workarounds such as ALD Pt priming layers exist *because* bare aqueous MXene ink does not reliably bond to textile | `LITERATURE-SUPPORTED` — and the literature's finding is negative |
| **Silicone / PDMS** | **Requires surface pretreatment.** Native PDMS is too hydrophobic/low-surface-energy to print on: "the hydrophobicity of the PDMS surface prevented printing of the Ag NP ink on top of the native PDMS substrate." Atmospheric-plasma or UV-ozone oxidation creates a hydrophilic silica layer, after which printed patterns survive stringent adhesion tests | `LITERATURE-SUPPORTED` | Song *et al.* 2022 print MXene on PDMS (and on PVA, ferrite, curved surfaces, leaves and fruit), but report **no adhesion quantification** | `LITERATURE-SUPPORTED` (printability); adhesion `UNKNOWN` |
| **Glass / ceramic** | Standard, well-established | `LITERATURE-SUPPORTED` | Demonstrated substrate class | `LITERATURE-SUPPORTED` |

**The finding that matters:** the substrate with the best loss tangent for an absorber
(silicone, tanδ 0.10) is also the one that will not accept a printed conductor without a
plasma or UV-ozone step. Neither MXene nor silver escapes this — it is a property of the
silicone surface, not of the ink. Any candidate scoring that puts silicone at the top on RF
grounds must carry that process step as an explicit constraint, and the Sci. Rep. absorber
that validates the RF case used **stencil printing with an air blaster**, not direct-write,
and did not report adhesion at all.

---

## 6. Consequences for the map

Three things this survey changes or sharpens:

1. **The handoff's cure-compatibility matrix needs revising.** Its `✗` for silver on PET and
   silver on TPU is contradicted by primary sources (§ bottom-line #3). The correct axis is
   *"can this part leave the host for an oven or flashlamp?"* — a per-requirement process
   input — not *"what is this substrate made of."* Since the map already treats the host
   surface as a per-requirement input, this belongs in the same slot.
2. **The premise "flexible substrate ⇒ low loss ⇒ weaker absorber" is only true for
   engineered low-loss laminates.** For commodity flexible polymers, elastomers and textiles
   the loss tangent is at or above FR4's. Framing the substrate search as a compensation
   problem risks optimising around a constraint that only two of the twelve candidates
   actually impose.
3. **TPU is the programme's largest uncharacterised assumption.** It is the substrate most
   often named for conformal work and the only one in this table with *no* X-band electrical
   data of any provenance. If Q14's bench characterisation happens, a TPU coupon in a WR-90
   waveguide would close a bigger gap than another MXene conductivity measurement.

---

## 7. What could not be verified

Stated plainly, per the repo's principle that unverified claims stay visible as such.

1. **TPU has no X-band εr or tanδ from any accessible source.** Not measured, not
   manufacturer-specified at frequency, not even a defensible literature range. The one
   quantitative source found (dielectric constant 8.02 → 2.88 under 400% strain) is at
   **1 MHz** and is published in MDPI *Polymers* — **stranded behind MDPI's HTTP 403**
   (verified in this environment; theirs, not a proxy problem). Provenance for TPU at X-band
   is `UNKNOWN`, full stop.
2. **PET's X-band tanδ was not pinned down.** Search results repeatedly assert "the loss
   tangent of PET is typically set as 0.002 in agreement with literature," but no fetched
   primary source states a measured X-band value. A promising one —
   *Periodica Polytechnica EECS*, which measured Kapton HN, Mylar A and Teonex Q51 PEN with a
   **split-cylinder resonator around 10 GHz** — **could not be fetched: `pp.bme.hu` timed out
   at DNS resolution from this environment on every attempt** (WebFetch `ETIMEOUT`, curl
   HTTP 000). That is the single highest-value stranded source in this pass; a human with a
   browser should retrieve it, because it would upgrade PET, PEN and a second independent
   Kapton figure from `UNKNOWN`/single-source to `MEASURED`.
3. **Eccosorb BSR/MFS complex permittivity and permeability are not published.** The Laird
   datasheet (RFP-DS-BSR MFS 012618, retrieved successfully) gives frequency range 1–40 GHz,
   service temperature 160 °C, Shore A > 70, thermal conductivity 0.865 W/mK, volume
   resistivity 2×10⁸ Ω·cm, outgassing 0.47% TML / 0.28% CVCM per ASTM E595-07, and
   "Typical Attenuation" in dB — but **no ε′, ε″, µ′ or µ″**. Several sibling datasheets
   (Eccosorb MCS, GDS, GDS-U, SF) were fetched but are typeset with **custom font
   subsetting that defeats text extraction**, and no PDF rendering tool
   (`pdftoppm`/poppler, working `pypdf`) is available in this environment. Laird's own
   `laird.com` PDF host returns **403/503 to WebFetch** though it serves to curl. Anything
   requiring those tables needs a human with a browser.
4. **Whether the silicone tanδ of 0.10 is a property of that grade or of silicone
   generally.** The 0.10 figure rests on a single measurement of one commercial product with
   one method. Polymax publishes no dielectric data. A second, independent X-band
   measurement of unfilled silicone rubber was not found. Treat #1's headline number as
   `MEASURED` but single-sourced.
5. **The PDMS X-band loss tangent specifically.** Cresson *et al.* measure 1–220 GHz and
   report εr falling 2.9 → 2.55 and tanδ "increasing slowly to reach 0.048 at 210 GHz."
   The X-band value is on that curve but is not tabulated in the accessible abstract, and
   **IEEE Xplore returned HTTP 418** to every fetch. The ~0.01–0.02 used in the §"arithmetic"
   table is `INFERRED` from the curve's shape, not read off it.
6. **Textile values at X-band.** Every felt/denim/Cordura number found is either measured at
   2.45/5.8 GHz, extracted by a different method (coaxial ring, matrix-pencil two-line,
   waveguide transmission line — which disagree with each other: jean is reported as both
   εr 2.2/tanδ 0.04 and εr 1.67/tanδ 0.0035), or reported only in a ResearchGate figure
   caption without the underlying paper being fetchable. They are `LITERATURE-SUPPORTED` with
   wide spread, not `MEASURED` at X-band.
7. **The EPJ Applied Metamaterials rGO–SiC–LLDPE paper** (0.7 mm flexible composite,
   96.7% absorption at 10.7 GHz) could not be read: the open-access PDF is 5.6 MB and every
   extraction route available here either timed out or produced only binary streams; the
   `full_html` view returned **403**. Its substrate εr/tanδ remain unrecovered.
8. **ScienceDirect returned 403** to every fetch, stranding the carbon-fibre-loaded silicone
   foam paper and the MXene-substrate-adhesion review. **PMC intermittently served a
   reCAPTCHA page** instead of content (PMC10143187, the PDMS wearable-substrate evaluation,
   was lost this way after PMC9695098 fetched normally).
9. **Whether Voltera's NOVA vacuum table actually holds silicone sheet or cast PDMS.** The
   machine's published substrate list is glass, ceramic, TPU (via vacuum table), PET,
   polyimide and textiles. Silicone rubber is not on it. Nothing found says it cannot be
   held; nothing says it can. `UNKNOWN`, and it gates the highest-scoring RF candidate.
10. **Copper.** This pass concentrated on silver and MXene because those are where the
    adhesion asymmetry lives. Copper's oxidation-controlled sinter (inert atmosphere or
    photonic reduction of CuO) was not researched substrate-by-substrate; the handoff's
    treatment of it is inherited unchanged and unverified here.

---

## Sources

Primary sources fetched and read in full:

- Huang, X., Pan, K. & Hu, Z. "Experimental Demonstration of Printed Graphene Nano-flakes
  Enabled Flexible and Conformable Wideband Radar Absorbers." *Scientific Reports* **6**,
  38197 (2016). DOI [10.1038/srep38197](https://doi.org/10.1038/srep38197)
- Yang, Z. *et al.* "Flexible substrate technology for millimeter wave wireless power
  transmission." *Wireless Power Transfer*. DOI
  [10.1017/wpt.2015.21](https://doi.org/10.1017/wpt.2015.21) —
  [PDF](https://www.maxapress.com/data/article/wpt/preview/pdf/wpt-3-1-24.pdf)
- Rogers Corporation, *ULTRALAM 3000 Liquid Crystalline Polymer Circuit Material* data sheet
  RF1.3000 — [PDF](https://www.midwestpcb.com/data_sheets/RogersULTRALAM.pdf)
- Laird Technologies, *Eccosorb BSR / MFS High Loss, Magnetically Loaded, Elastomeric
  Microwave Absorber*, RFP-DS-BSR MFS 012618 —
  [PDF](https://www.laird.com/sites/default/files/2019-01/RFP-DS-BSR%20MFS%20012618%20(1).pdf)
- DuPont, *Intexar PE874 Stretchable Silver Conductor* technical data sheet, K-29701 (8/17) —
  [PDF](https://www.ccieurolam.com/wp-content/uploads/PE874-TDS.pdf)
- Polymax, *SILONA 60 ShA FDA silicone sheet* product specification —
  [product page](https://www.polymax.co.uk/silicone-products/polymax-silona-black-1-2m-x-10m-x-2-0-mm-thick.html)
- Wang, Q. *et al.* "Electromagnetic-Wave Absorption Properties of 3D-Printed Thermoplastic
  Polyurethane/Carbonyl Iron Powder Composites."
  [PMC9695098](https://pmc.ncbi.nlm.nih.gov/articles/PMC9695098/)
- NovaCentrix, "The Evolution of Photonic Curing" —
  [PulseForge](https://pulseforge.com/pulseforge_blog/the-evolution-of-photonic-curing/)

Sources used at abstract- or search-snippet level only, and flagged as such above:
Cresson, P.-Y., Orlic, Y., Legier, J.-F., Paleczny, E., Dubois, L., Tiercelin, N., Coquet,
P., Pernod, P. & Lasri, T., "1 to 220 GHz complex permittivity behavior of flexible
polydimethylsiloxane substrate," *IEEE Microwave and Wireless Components Letters* **24**(4),
278–280 (2014) — [HAL record](https://hal.science/hal-00980037v1); the silver-on-PET
sintering study (*J. Electrochem. Soc.*,
DOI [10.1149/2.0091909jes](https://doi.org/10.1149/2.0091909jes)); Rogers RO4350B data sheet
values; IPC-2223 bend-radius rules; and the textile dielectric compilations.

Repo documents this builds on: `docs/HANDOFF-metamaterial-printing-grill.md` (whose εr = 310
and "right at the machine's floor" figures are superseded per the map's caveat, and whose
cure-compatibility matrix this document further corrects), and
`docs/mxene-voltera-nova-printability.md`.
