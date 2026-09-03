# Building a Two-Conductor Metamaterial Stack on a Voltera NOVA

**Research date:** 2026-09-03
**Ticket:** [#128](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/128), child of the wayfinder map [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104)
**Question:** How would a multi-layer printed metamaterial stack — a reflector layer plus a
lossy resonant layer above it, separated by a dielectric — physically be built on a Voltera
NOVA inside a total thickness of 0.87–2.0 mm?

Provenance tags are `CONTEXT.md`'s ladder — `MEASURED` → `SIMULATED` → `CALCULATED` →
`MANUFACTURER-SPECIFIED` → `LITERATURE-SUPPORTED` → `INFERRED` → `ASSUMED` → `UNKNOWN`.
No parallel confidence vocabulary is introduced.

---

## Bottom line up front

Five findings, in descending order of how much they change the plan.

1. **The printed dielectric cannot be the spacer, and it is not close.** Voltera sells a
   dielectric ink — ACI Materials **SI3104 Stretchable Printed Insulator**, $99.99 for a
   2 mL cartridge, and it is the ink in Voltera's own multi-layer white paper. Its datasheet
   gives a recommended dry film thickness of **9–14 µm per layer and three layers**, so
   **27–42 µm total** (`MANUFACTURER-SPECIFIED`). The stack needs a spacer of roughly
   0.85–2.0 mm. At 14 µm per layer that is **~62 layers to reach 0.87 mm**, each needing its
   own 5–15 minute bake at 135 °C, on a machine whose multi-layer feature is validated to
   **four** layers. Electrically, 42 µm at 10 GHz in an εr ≈ 3 medium is **0.24% of a guided
   wavelength — 0.87° of phase** (`CALCULATED`, §6). That is a coupling capacitor, not a
   spacer. **The substrate is the spacer. There is no third option.**

2. **SI3104 publishes no permittivity and no loss tangent, at any frequency.** The datasheet
   carries DC breakdown (250 V/mil), elongation (>100%), adhesion (ASTM D3359 5B), viscosity
   (25 Pa·s) and cure (135 °C, 5–15 min) — and **no εr, no tanδ, not even a 1 kHz figure**
   ([ACI Data Sheet SI3104 Rev 3](https://www.acimaterials.com/wp-content/uploads/2025/03/ACI-Data-Sheet-SI3104-Rev-3.pdf)).
   In plain terms: nobody has published how much this ink slows a radio wave down or how much
   it heats up, so **it cannot be put in a simulation**. Any solver model of it would be a
   guess wearing an `ASSUMED` tag. Since finding 1 already removes it from the spacer role,
   this matters less than it would have — but it does rule the ink out of any role where its
   electrical behaviour is load-bearing.

3. **Multi-layer printing is real, supported and demonstrated — but layer-to-layer
   registration is a human with a camera, and Voltera publishes no number for it.** NOVA's
   `Plan` feature does conductor → dielectric → conductor stacks, validated to four layers,
   with per-layer height mapping. Alignment is explicitly **"Manual with camera assist
   (8 MP, 17 µm/px)"**
   ([Voltera technical specifications](https://www.voltera.io/technical-specifications)),
   driven by user-placed fiducials in opposing corners. The **±20 µm** figure the programme
   already knows is *single-layer XYZ positioning accuracy* — how precisely the head goes
   where it was told. It is **not** a layer-to-layer registration figure, and no registration
   figure of any kind appears in Voltera's documentation, white papers, blog or spec sheet
   (`UNKNOWN`, §3).

4. **Double-sided printing is a V-One capability, not a NOVA one.** Voltera's own comparison
   table lists "Double-sided PCBs" under **V-One** and "Up to 4 stack-up layers" under
   **NOVA**. The only documented double-sided workflow is the V-One's, and it registers the
   second side **mechanically off two drilled holes** — a rigid-FR1, drill-attachment
   process that does not transfer to a 2 mm flexible sheet. Double-sided on a NOVA is not
   forbidden, it is simply **undocumented and unsupported** (`UNKNOWN`, §4). *But see §7: for
   this particular stack the registration problem may be largely illusory, because an
   unpatterned reflector has nothing to register to.*

5. **The film-thickness floor is ~10 µm, and that kills "make the resonant layer thin so it
   is lossy" for any metal-grade conductor — while making it work perfectly for carbon.**
   Voltera states a print height of 60 µm "can often result in a print thickness of 10–20 µm
   after thermal curing"
   ([Print Settings Overview](https://docs.voltera.io/docs/nova/learn-nova/software-overview/print-settings-overview)).
   At 10 GHz a 10 µm printed-MXene film is already **1.65 skin depths**, so its surface
   resistance is within a few percent of an infinitely thick film's — thinning it further is
   not available and would not help anyway. **Thickness is a dead knob for MXene and silver.**
   For **ACI SC1502 stretchable carbon** (`< 0.6 Ω·cm`, recommended cured thickness 6–12 µm,
   double-printable) the same 10 µm is **0.026 skin depths** — deep in the thin-film regime
   where sheet resistance is exactly `1/σt` and thickness is a clean, linear, printable knob.
   **377 Ω/sq lands at 15.9 µm of SC1502** (`CALCULATED`, §5) — one or two passes. Issue #128's
   Correction 1 ("you cannot make a resistive sheet by printing MXene thin") is correct and
   stands; the conclusion drawn from it — that a printed resistive sheet is unreachable — does
   not. **You cannot print a resistive sheet out of MXene. You can print one out of carbon,
   trivially, using an ink Voltera already sells.**

---

## 1. Dielectric ink: does it exist, and what does it publish?

**Yes, two of them, and one is well documented.**

Voltera's own store lists exactly two dielectric/insulating products for the NOVA:

| Product | Supplier | Price | Voltera store |
|---|---|---|---|
| **SI3104 Stretchable Printed Insulator**, 2 mL cartridge | ACI Materials | $99.99 | [store.voltera.io](https://store.voltera.io/products/aci-ss1109-stretchable-insulator) |
| **ECV003 Green-Tinted Dielectric Varnish**, 2 mL cartridge | Voltera | $99.99 | [store.voltera.io](https://store.voltera.io/products/vfp-ecv003-2ml-cartridge-copy) |

A third appears in a Voltera white paper but is not sold by Voltera: **Saral Dielectric 600**
(Saralon), used as the insulating layer in the electroluminescent-display stack. Saralon's
product page served no technical data to an automated fetch — no datasheet was reachable
(`UNKNOWN`; [saralon.com](https://www.saralon.com/en/inks/dielectric-inks:saral-dielectric-600/)).
ECV003 likewise has no reachable datasheet — the store page gives price, format and NOVA
compatibility only (`UNKNOWN`).

**SI3104 is the one with a real datasheet**, and it is the ink Voltera used in its own
multi-layer demonstration
([Printing a Flexible Membrane Keyboard](https://www.voltera.io/use-cases/white-papers/printing-multilayer-flexible-membrane-keyboard-conductive-silver-ink-dielectric-ink-pet)).
Everything below is `MANUFACTURER-SPECIFIED` from
[ACI Data Sheet SI3104 Rev 3](https://www.acimaterials.com/wp-content/uploads/2025/03/ACI-Data-Sheet-SI3104-Rev-3.pdf):

| Property | Published value | Plain-language reading |
|---|---|---|
| **Permittivity (εr)** | **not published** | Nobody has said how much this ink slows a radio wave down — so a solver has nothing to put in the box. |
| **Loss tangent (tanδ)** | **not published** | Nobody has said how much of a wave's energy it turns into heat. |
| DC breakdown | 250 V/mil (≈ 9.8 V/µm), 3 printed layers | How much voltage it blocks before arcing. This is a *DC insulation* number, not an RF number. |
| Viscosity | 25 Pa·s = **25,000 cP** at 0.1 s⁻¹, 25 °C | Comfortably inside NOVA's 1,000–1,000,000 cP dispensing window. It will extrude. |
| Density / solids | 1.15 g/cm³ / 32% | Two-thirds of what you dispense evaporates; hence the thin dry film. |
| **Dry film thickness** | **14 µm** (150 mesh) or **9 µm** (200 mesh) per layer | How thick one printed-and-baked layer ends up. |
| **Recommended # layers** | **3** | ACI's own recommendation → **27–42 µm total**. |
| Cure | **135 °C, 5–15 min in a box oven** (or 5 min conveyor) | Needs an external oven. NOVA's own heater tops out at 40 °C and exists only to keep ink viscosity steady, not to cure. |
| Elongation / adhesion | >100% / 5B on TPU | Stretches to double length without cracking; sticks well to TPU. |
| Shelf life | 6 months at 20 °C | |

**The honest statement:** the ink exists, it dispenses on a NOVA, Voltera has demonstrated it,
and it is **unsimulatable at X-band** because its permittivity and loss tangent are unpublished
at *any* frequency. There is not even a kHz figure to caveat. Note that the programme's
standing warning — "a kHz figure is NOT an X-band figure", per the Kapton 500HN case in
`docs/xband-absorber-substrate-shortlist.md` — does not even get a chance to apply here.

**Stranded:** ScienceDirect, MDPI and IEEE Xplore return 403 to automated fetches from this
environment, so any peer-reviewed characterisation of screen-printed insulator inks at
microwave frequencies could not be checked. If SI3104's εr has been measured by a third party
at X-band, it was not reachable from here.

## 2. Multi-layer workflow: supported, demonstrated, four layers

**Yes — this is the best-evidenced part of the whole question.**

NOVA's `Plan` software feature exists specifically for this. Voltera's spec sheet says
**"Up to 4 stack-up layers"**, footnoted that more "are achievable but depend on a number of
factors" and are "considered experimental"
([technical specifications](https://www.voltera.io/technical-specifications);
[5.1 Designing Multi-Layer Artworks](https://docs.voltera.io/docs/nova/learn-nova/plan-workflow/5.1-designing-multi-layer-artworks.md)).
`Plan` also **regenerates probe points per layer**, "taking into account subtle height changes
each subsequent layer creates" — in plain terms, after you print a layer the surface is no
longer flat, so the machine re-measures the terrain before printing on top of it, rather than
crashing the nozzle into what it just laid down
([Print Multilayer Flexible and Stretchable Circuits with NOVA](https://www.voltera.io/blog/print-multilayer-flexible-stretchable-circuits-nova)).

**Two published examples on Voltera hardware, both first-party white papers:**

| | Flexible membrane keyboard | Electroluminescent display |
|---|---|---|
| Substrate | PET | Paper and PET |
| Stack | silver → dielectric → silver | Saral Silver 700 → **Saral Dielectric 600** → BluePhosphorL 800 → Conducting Polymer 700 |
| Dielectric ink | **ACI SI3104**, **two passes**, cured after each | Saral Dielectric 600, **air dry 10–20 min, oven curing not recommended** |
| Nozzles | Nordson EFD 7018424, **0.15 mm ID** | 0.15 mm (base), 0.25 mm (layers 2–3), 0.10 mm chamfered (top) |
| Cure | 135 °C, 5 min per pass | 120 °C, 5 min (silver); 120 °C, 1 min (phosphor) |
| Feature size | dispensing "as small as **250 µm W × 40 µm H**" | print height reduced to **~40 µm** for the top layer |
| Probe pitch | 2 mm | 4 mm (layers 1–3), 1 mm (layer 4) |
| Registration data | **none published** | **none published** |

Sources: [membrane keyboard white paper](https://www.voltera.io/use-cases/white-papers/printing-multilayer-flexible-membrane-keyboard-conductive-silver-ink-dielectric-ink-pet),
[electroluminescent white paper](https://www.voltera.io/use-cases/white-papers/printing-electroluminescent-ink-paper-pet).

Note the keyboard's "250 µm W × 40 µm H" — that is a *printed feature*, wider and taller than
a trace, and it is the only height number Voltera attaches to a real multi-layer job.

**No peer-reviewed paper describing multi-layer printing on Voltera hardware was found.** All
multi-layer evidence is Voltera's own marketing and documentation. It is credible and specific,
but it is first-party, and it is not independent.

## 3. Layer-to-layer registration: no published number

This is the sharpest gap in the whole investigation, and it needs stating without softening.

**What Voltera publishes:**

- **XYZ accuracy ± 20 µm** ([technical specifications](https://www.voltera.io/technical-specifications)) — where the print head lands relative to where it was commanded, within one print.
- **XY tool-to-tool positional accuracy ± 15 µm** ([NOVA brochure, pre-release](https://ecelab.pratt.duke.edu/sites/ecelab.pratt.duke.edu/files/2024/Voltera%20NOVA%20brochure.pdf)) — how well the probe module and the dispenser module agree on where a point is. Marked "pre-release specifications are estimates and subject to change".
- **Step resolution 2.5 µm (X) × 7 µm (Y) × 1.25 µm (Z)**; **print height resolution ± 10 µm**.
- **Camera 8 MP, 17 µm/pixel**, with AR overlay.
- **Alignment method: "Manual with camera assist."**

**What Voltera does not publish, anywhere:** a layer-to-layer registration figure. The
alignment workflow is a human operator setting a pivot on a fiducial, nudging with variable
step sizes, then setting rotation — with the documentation itself conceding "there is always
going to be some distortion the further from the center you get"
([Print 4: Alignment](https://docs.voltera.io/docs/nova/getting-started/starter-project/print-4-alignment.md)).
The multi-layer design guide gives **no numeric overlap or clearance margin**; its actual
guidance is qualitative — put fiducials in opposing corners, give the top layer "enough overlap
between the traces of this layer and the conductive layer below it to make a strong connection"
([5.1 Designing Multi-Layer Artworks](https://docs.voltera.io/docs/nova/learn-nova/plan-workflow/5.1-designing-multi-layer-artworks.md)).

**Plain-language reading:** the machine can place a dot to within 20 µm of where it was told.
Whether the *second layer's* coordinate system lines up with the *first layer's* depends on how
well a person eyeballed a camera image at 17 µm per pixel, and Voltera declines to put a number
on that. A realistic expectation is **one to a few camera pixels — tens of microns at best,
degrading away from centre** (`INFERRED`, not `MANUFACTURER-SPECIFIED`; this is our estimate,
not Voltera's claim). It should be **measured on the machine in hand** before any design leans
on it. That is a bench task, and the map already says the NOVA is in hand.

## 4. Double-sided printing: undocumented on NOVA

**The comparison table is unambiguous about where this capability lives:**

| Layer capacity | V-One | NOVA |
|---|---|---|
| | "Double-sided PCBs" | "Up to 4 stack-up layers" |

([technical specifications](https://www.voltera.io/technical-specifications))

The V-One's double-sided workflow registers the second side **mechanically, off drilled holes**:
"The drilled holes serve two critical purposes: They form your electrical connections between
top and bottom layers. They act as reference features that you'll later use to align the bottom
layer to the top", with the board "clamped securely so it cannot shift between drilling and
printing"
([Double Sided PCB Workflow](https://docs.voltera.io/docs/v-one/learn-v-one/drill-attachment/double-sided-pcb-workflow.md)).
That process needs the drill attachment, a rigid FR1 board and mechanical clamping. It does not
transfer to a 0.87–2.0 mm compliant sheet, and the V-One cannot print the stretchable inks or
hold a soft substrate at all (its fixturing is "clamping" only; substrates 1–3 mm; rigid
FR1/FR4 only).

**A NOVA double-sided build is not documented anywhere in Voltera's material** — not in the
docs sitemap, not in the fifteen white papers, not on the spec sheet (`UNKNOWN`).

**What would have to be true for it to work anyway** (all `INFERRED`, none verified):

- Print side A, cure in an external oven, flip, re-align. Nothing in the machine forbids this.
- The flip destroys the fiducial reference, because the fiducials are now on the underside.
  Recovering it needs one of: **through-holes** punched or drilled before printing (the V-One's
  trick, but there is no NOVA drill module), **edge or corner registration** against the
  mounting grid or a custom fixture, or a **transparent substrate** the camera can see the
  first-side fiducials through. Silicone sheet is often translucent, which would help; the
  camera's ability to resolve a fiducial through 2 mm of translucent elastomer is unverified.
- Curing side A at 135 °C before printing side B means the substrate takes two thermal cycles.
  Dimensional change between cycles becomes a registration error the camera cannot see.

**The claim "double-sided gives near-perfect registration for free" (issue #128) is not
supported for a NOVA.** It is supported for the *V-One*, where a drill defines both sides'
datum mechanically. On a NOVA the free lunch is not on the menu — but §7 explains why, for this
particular stack, it may not be needed.

## 5. Minimum controllable film thickness — the binding fact, and the surprise

### What the machine says

| Parameter | Value | Source |
|---|---|---|
| Print height range | **10 – 35,000 µm** | [Print Settings Overview](https://docs.voltera.io/docs/nova/learn-nova/software-overview/print-settings-overview) |
| Print height → cured thickness | **"a print height of 60 µm can often result in a print thickness of 10–20 µm after thermal curing"** | same |
| Guidance for thin prints | for prints thinner than 50 µm, use the same module port for probe and dispenser | same |
| Nozzles supplied | 100, 150, 225 µm; Nordson EFD / Subrex down to **50 µm** available | [NOVA store listing](https://store.voltera.io/products/voltera-nova) |
| Minimum tracewidth | **100 µm**, "dependent on material and nozzle" | [technical specifications](https://www.voltera.io/technical-specifications) |
| Max dispense pressure | 70 PSI | [NOVA brochure](https://ecelab.pratt.duke.edu/sites/ecelab.pratt.duke.edu/files/2024/Voltera%20NOVA%20brochure.pdf) |

Voltera gives **no guaranteed minimum cured film thickness**. The thinnest number it states
anywhere is **10 µm**, as the low end of the 60 µm-print-height example. Treat
**~10 µm as the practical floor** (`MANUFACTURER-SPECIFIED` at the low end of a stated range,
not a guaranteed spec).

The ink datasheets agree and are more specific, because they are written for screen printing
where thickness is metered by the mesh:

| Ink | Volume resistivity | σ (`CALCULATED`) | Recommended cured thickness |
|---|---|---|---|
| **ACI SS1109** stretchable silver | < 4.5×10⁻⁵ Ω·cm | > 2.22×10⁶ S/m | **10–20 µm** |
| **ACI SC1502** stretchable carbon | < 0.6 Ω·cm (= 236 Ω/sq/mil) | > 167 S/m | **6–12 µm**, "double print wet on wet or dry can be used to increase deposition thickness" |
| **ACI SI3104** insulator | — | — | 9–14 µm/layer, 3 layers |

Sources: [SS1109 Rev 4](https://www.acimaterials.com/wp-content/uploads/2025/03/ACI-Data-Sheet-SS1109-Rev-4.pdf),
[SC1502 Rev 4](https://www.acimaterials.com/wp-content/uploads/2025/03/ACI-Data-Sheet-SC1502-Rev-4.pdf),
[SI3104 Rev 3](https://www.acimaterials.com/wp-content/uploads/2025/03/ACI-Data-Sheet-SI3104-Rev-3.pdf).
These are screen-print figures; extrusion on a NOVA is metered by height/speed/pressure instead,
so they are a strong indication of what the *chemistry* wants, not a NOVA guarantee.

### What that means at 10 GHz

Skin depth `δ = 1/√(π f µ₀ σ)` at f = 10 GHz. All `CALCULATED`.

Plain-language reading: **skin depth is how far a radio wave gets into a conductor before it
has faded to about a third of its strength.** A film several skin depths thick behaves as a
solid mirror; a film much thinner than one skin depth behaves as a see-through resistive sheet.

| Conductor | σ (S/m) | δ at 10 GHz | Bulk surface resistance `Rs = 1/σδ` |
|---|---|---|---|
| Copper (reference) | 5.8×10⁷ | 0.66 µm | 0.026 Ω/sq |
| NOVA spec ink, "≥10⁷ S/m single pass" | 1.0×10⁷ | 1.59 µm | 0.063 Ω/sq |
| **ACI SS1109 silver** | 2.22×10⁶ | **3.38 µm** | **0.133 Ω/sq** |
| Printed MXene (`docs/mxene-voltera-nova-printability.md`) | 6.9×10⁵ | 6.06 µm | 0.239 Ω/sq |
| **ACI SC1502 carbon** | **167** | **390 µm** | (never reached — see below) |

The MXene-to-copper ratio here is **0.239 / 0.026 = 9.2×**, which independently reproduces
issue #128's "~9× versus copper" correction. Good — the arithmetic is consistent.

**Now the two consequences, which point in opposite directions:**

**(a) For metal-grade conductors, thickness is a dead knob.** At the machine's ~10 µm floor:

| Conductor | 10 µm | 20 µm | 35 µm |
|---|---|---|---|
| SS1109 silver | **2.96 δ** | 5.92 δ | 10.4 δ |
| Printed MXene | **1.65 δ** | 3.30 δ | 5.78 δ |

At 1.65 skin depths a film's surface resistance is already within a few percent of its
infinitely-thick value. In plain terms: **the thinnest MXene layer a NOVA can print is already
effectively opaque to a 10 GHz wave.** You cannot make it "deliberately lossier by printing it
thinner" — the machine's floor is above the point where thickness stops mattering. Issue #128's
"thinner and lossier resonant layer" is not achievable in MXene or silver on this machine. It is
a real, binding fabrication constraint.

Conversely, this is *good* news for the reflector: **SS1109 silver at its own recommended
10–20 µm is already 3.0–5.9 skin depths** — exactly the "3–5 skin depths, behaves as a mirror"
target from #128, at a thickness the ink datasheet recommends and the machine states as typical.
The 20–35 µm target in #128 was derived for MXene; **for silver the reflector is easier than
assumed** — one to two passes rather than three to five.

**(b) For carbon, thickness is a beautiful knob — and 377 Ω/sq is one pass away.** SC1502's
skin depth is **390 µm**, so a printed 6–24 µm film is **0.015–0.062 skin depths**. Deep in the
thin-film regime, RF sheet resistance equals DC sheet resistance exactly: `Rs = 1/(σt) = ρ/t`.

| SC1502 cured thickness | Sheet resistance (`CALCULATED` from ρ ≤ 0.6 Ω·cm) | Passes at 6–12 µm/pass |
|---|---|---|
| 6 µm | 1000 Ω/sq | 1 |
| 10 µm | 600 Ω/sq | 1 |
| 12 µm | 500 Ω/sq | 1 |
| **15.9 µm** | **377 Ω/sq** ← free-space impedance | **2** |
| 20 µm | 300 Ω/sq | 2 |
| 24 µm | 250 Ω/sq | 2 |

Because the datasheet number is a bound (`< 0.6 Ω·cm`), these are **upper** bounds on `Rs` —
a better-conducting batch shifts the whole column down, and thickness must rise to compensate.
That is a calibration coupon, not a blocker.

**This is the finding that most changes issue #128.** The issue's Correction 1 — that
`Rs = 1/σt` demands a 3.85 nm MXene film to hit 377 Ω/sq, and dispensing produces microns — is
arithmetically correct and stands. But the conclusion "you cannot print a resistive sheet"
generalises from MXene to all printed conductors, and that generalisation is false. MXene's
conductivity is *too high* to make a resistive sheet at printable thickness. Carbon's is four
orders of magnitude lower, which is precisely why it lands in the right place.
**Voltera already sells the ink** (Stretchable Carbon Ink SC1502, $99.99, 2 mL).

This does *not* resurrect the Salisbury screen — the quarter-wave spacing problem in #128 is
independent and still fatal (§6). What it does is give the resonant layer a **continuously
tunable, printable loss parameter that the optimiser can search**, which is exactly the
architectural goal the ticket set out: loss as geometry, not as inherited material property.

## 6. The thickness budget, done as arithmetic

At 10 GHz, free-space wavelength λ₀ = 30 mm. In a dielectric of relative permittivity εr the
guided wavelength is λg = λ₀/√εr. All `CALCULATED`.

| εr | λg | Quarter-wave | 42 µm printed dielectric, as a fraction of λg | as electrical phase |
|---|---|---|---|---|
| 2.9 (silicone, measured, #114) | 17.62 mm | 4.40 mm | 0.238% | 0.86° |
| 3.0 | 17.32 mm | 4.33 mm | 0.242% | 0.87° |
| 3.2 (Kapton, measured, #114) | 16.77 mm | 4.19 mm | 0.250% | 0.90° |
| 4.8 (FR4, patent Example 3) | 13.69 mm | 3.42 mm | 0.307% | 1.10° |

**Reading this plainly.** A quarter-wave spacer — the classic Salisbury geometry — needs
3.4–4.4 mm. The whole skin is 0.87–2.0 mm. Quarter-wave does not fit, confirming #128. But
the *printed* dielectric is not merely too thin for quarter-wave; at **under one degree of
phase** it is too thin to be a spacer of any kind. It delays the wave by nothing. Its job is
insulation between crossing traces, which is what ACI sells it for and what Voltera demonstrated
it doing.

To build a 0.87 mm spacer out of SI3104 would take **62 printed-and-baked layers** (at 14 µm)
or **222 layers** to reach 2.0 mm (at 9 µm), against a `Plan` feature validated to four. Even
ignoring the oven time — 62 layers × 5–15 min = 5 to 15 hours of baking alone — this is not a
process.

**Therefore: the substrate is the spacer.** Its thickness *is* the design variable that sets
the reflector-to-resonator spacing, and it is chosen from stock sheet, not printed. That in turn
means the substrate's permittivity re-enters the design as a first-class electrical parameter —
which the map already knows how to handle (`docs/xband-absorber-substrate-shortlist.md` carries
measured εr for silicone and Kapton, and flags TPU as having **no X-band data of any
provenance**).

## 7. So how does the stack actually get built?

Three routes, ranked by how much of them is evidenced.

### Route A — double-sided on one sheet, unpatterned reflector (recommended)

Print the **lossy resonator array on side A**, flip, print the **reflector as a solid unbroken
sheet on side B**.

**The registration problem largely evaporates, and this seems to have been missed.** A
continuous ground plane has no features. There is nothing on it to align to anything. The only
registration requirement is that the metal covers the area under the array — a millimetre of
slop is irrelevant. **Front-to-back registration only matters if the reflector is patterned**,
and in the reflector-plus-resonator absorber architecture #128 describes, it is not.

What still has to be true, and is not yet verified:

- The NOVA has no documented flip-and-print workflow. It is a manual procedure the operator
  invents (`UNKNOWN`, §4).
- Side A must survive its own 120–135 °C cure and then a second one for side B.
- The vacuum table must hold the sheet with a cured printed pattern facing *down* against the
  porous titanium, without abrading it. Undocumented.
- The substrate must be 0.87–2.0 mm thick, flexible, and dimensionally stable across two bakes.
  NOVA accepts substrates **up to 30 mm** thick, so the stock is not a limit.

### Route B — laminate two printed films

Print each layer on its own thin sheet, then bond. This is the route issue #115 already flags as
a registration risk, and Voltera's own strain-gauge white paper uses lamination (TPU laminated
onto a glove). It converts a printing problem into an assembly problem — and the same
observation applies: an unpatterned reflector makes the alignment tolerance enormous.

### Route C — printed dielectric spacer

**Ruled out.** §1 and §6. 42 µm against a 0.87–2.0 mm requirement, no published permittivity,
and a layer count 15–55× beyond the validated four.

### The stack, with numbers

Assembling everything above into one buildable stack-up (`CALCULATED` / `MANUFACTURER-SPECIFIED`
as marked; **not** simulated, **not** measured):

| Layer | Material | Thickness | Passes | What it does |
|---|---|---|---|---|
| Resonant / lossy | **ACI SC1502 carbon** | 6–24 µm | 1–2 | Resonator array. `Rs` = 250–1000 Ω/sq, set by thickness. 377 Ω/sq at 15.9 µm. |
| Spacer | **substrate sheet** (silicone / Kapton / RO4350B / LCP) | **0.85–1.96 mm** | — | Sets the resonator-to-mirror spacing. Chosen, not printed. |
| Reflector | **ACI SS1109 silver**, unpatterned | 10–20 µm | 1–2 | 3.0–5.9 skin depths. Mirror, `Rs` ≈ 0.13 Ω/sq. |
| **Total** | | **0.87–2.0 mm** | | Fits the patent envelope with the substrate doing the work. |

Minimum printed feature 100 µm; the map already records the seven examples' minimum feature as
**0.2 mm, 2–6× above the machine floor**, so cell geometry is not the constraint here.

An alternative worth costing: **silver for the reflector, MXene for the resonator** keeps
MXene's in-situ, no-oven advantage for the layer that needs it, but gives up the thickness knob
(§5a) — MXene's loss would then have to come entirely from element geometry. Carbon gives both
knobs but needs the 120–135 °C oven, which is the same constraint the map already identified as
the real discriminator (#105: "MXene's decisive advantage is in-situ printing on a host that
cannot be oven-baked").

## 8. Vacuum table and silicone

**Not answered by Voltera, and it should not be guessed at.**

**What is published:** the NOVA Vacuum Module ($1,539.99, included with the machine) has a
**porous titanium top**, "allowing uniform air flow throughout to evenly secure any substrate at
all points", accepts substrates up to **220 × 300 mm**, and was "designed specifically for
printing onto flexible and compliant substrates". Substrates must be **dust-free**; suction is
best when the substrate covers the whole plate, and smaller pieces should be masked with PET or
printer paper. Do not put solvents on the bed — liquid seeps into the pores and can delaminate
the titanium top
([Using the Vacuum Module](https://docs.voltera.io/docs/nova/learn-nova/novas-hardware/using-the-vacuum-module),
[store listing](https://store.voltera.io/products/vacuum-table)).

**What is not published:** any mention of silicone, PDMS or elastomer. Voltera's documentation
query interface, asked directly, returns: *"The docs for NOVA's vacuum module do **not** state
whether it can hold **silicone** or **PDMS** elastomer sheets."* Named substrates across all
Voltera material are PET, Kapton/polyimide, TPU, cotton fabric, paper, ABS, FR1, FR4, glass,
ceramic, silicon wafers, Rogers PCB and Soluboard. **None of the fifteen white papers uses
silicone or PDMS.** Voltera sells PET, polyimide and TPU sheet; it does not sell silicone sheet.
**`UNKNOWN`.**

**Two separate risks, and they are not the same question:**

1. **Will the vacuum hold it?** (`INFERRED`, untested.) Silicone is non-porous and highly
   conformable, so it should seal against a porous plate at least as well as PET — arguably
   better. The countervailing risk is that a soft 60 Shore A sheet **dimples into the pores**
   under suction, putting height-map error and surface waviness exactly where the print goes.
   Voltera publishes no pore size, so this cannot be estimated; it is a coupon test, not a
   literature question.

2. **Will the ink stick to it?** (`LITERATURE-SUPPORTED`, and the answer is "not without
   treatment.") This is the bigger risk and it is well documented outside Voltera. Silicone's
   low surface energy and hydrophobicity are a known, named obstacle to printed conductors:
   *"the low surface energy and hydrophobicity of PDMS hinder ink adhesion and pattern
   fidelity, necessitating surface modification"*
   ([Plasma-aided direct printing of silver nanoparticle conductive structures on PDMS,
   *Sci. Rep.* 14 (2024)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11680893/)). Oxygen or
   dielectric-barrier-discharge plasma fixes it — that paper prints adherent silver at 17 kV
   DBD, reaching a **4.99 µm** film at **6.79×10⁻⁵ Ω·cm** — but the fix is temporary:
   **plasma-treated PDMS undergoes hydrophobic recovery within hours**, and the treated skin
   is brittle and cracks when stretched. In plain terms: **you get a window of a few hours
   after plasma-treating a silicone sheet in which ink will wet it, and then it goes back to
   repelling ink.**

Both of these are bench questions with the machine in hand. Neither is answerable from
documentation, and neither should be assumed.

**Stranded:** the ScienceDirect PDMS inkjet paper (S0042207X25007754) and the WMU flexographic
silver-on-PDMS dissertation were not fetchable — ScienceDirect 403s automated requests from this
environment. The open-access *Scientific Reports* paper above was reachable via PMC and carries
the load.

---

## What could not be verified

Stated plainly, without smoothing:

| Question | Status |
|---|---|
| SI3104 permittivity and loss tangent at any frequency | **Not published by ACI.** Not a kHz-versus-X-band gap — no figure exists at all. |
| ECV003 Green-Tinted Dielectric Varnish datasheet | **Not reachable.** Voltera store page gives price, 2 mL cartridge, NOVA compatibility only. |
| Saral Dielectric 600 datasheet | **Not reachable.** Saralon product page served no technical data. |
| Layer-to-layer registration accuracy on NOVA | **Not published.** Alignment is "manual with camera assist"; ±20 µm is single-layer positioning, not registration. |
| Double-sided printing on NOVA | **Undocumented.** Documented only for the V-One, via drilled-hole mechanical registration on rigid FR1. |
| Guaranteed minimum cured film thickness | **Not published.** The thinnest figure anywhere is the 10 µm low end of Voltera's own 60 µm-print-height example. |
| Vacuum table with silicone / PDMS | **Not stated.** Voltera's own docs query returns an explicit "do not state". |
| Porous titanium pore size | **Not published.** Prevents estimating whether soft silicone dimples into it. |
| Third-party (peer-reviewed) multi-layer printing on Voltera hardware | **None found.** All multi-layer evidence is Voltera first-party. |
| SI3104 or comparable insulator inks characterised at microwave frequencies | **Stranded.** MDPI, ScienceDirect and IEEE Xplore return 403 to automated fetches from this environment. |
| ScienceDirect PDMS-printing sources | **Stranded**, same reason. The open-access *Sci. Rep.* / PMC equivalent was used instead. |

## Primary sources

**Voltera (first-party):**
- [NOVA product page](https://www.voltera.io/products/nova) — specifications, substrate list
- [Technical specifications, V-One vs NOVA](https://www.voltera.io/technical-specifications) — layer capacity, alignment method, camera, accuracy
- [NOVA brochure (PDF)](https://ecelab.pratt.duke.edu/sites/ecelab.pratt.duke.edu/files/2024/Voltera%20NOVA%20brochure.pdf) — pre-release; ±15 µm tool-to-tool, 70 PSI, print height resolution
- [Print Settings Overview](https://docs.voltera.io/docs/nova/learn-nova/software-overview/print-settings-overview) — **print height 10–35,000 µm; 60 µm height → 10–20 µm cured**
- [5.1 Designing Multi-Layer Artworks](https://docs.voltera.io/docs/nova/learn-nova/plan-workflow/5.1-designing-multi-layer-artworks.md) — fiducials, 4-layer limit, per-layer cure
- [Print 4: Alignment](https://docs.voltera.io/docs/nova/getting-started/starter-project/print-4-alignment.md) — camera-assisted manual alignment workflow
- [Using the Vacuum Module](https://docs.voltera.io/docs/nova/learn-nova/novas-hardware/using-the-vacuum-module) — porous titanium, dust-free, masking, no solvents
- [Print Multilayer Flexible and Stretchable Circuits with NOVA](https://www.voltera.io/blog/print-multilayer-flexible-stretchable-circuits-nova) — `Plan`, per-layer probe points
- [Membrane keyboard white paper](https://www.voltera.io/use-cases/white-papers/printing-multilayer-flexible-membrane-keyboard-conductive-silver-ink-dielectric-ink-pet) — SI3104, two passes, 0.15 mm nozzle, 135 °C/5 min
- [Electroluminescent white paper](https://www.voltera.io/use-cases/white-papers/printing-electroluminescent-ink-paper-pet) — 4-layer stack, Saralon inks, ~40 µm print height
- [Double Sided PCB Workflow (V-One)](https://docs.voltera.io/docs/v-one/learn-v-one/drill-attachment/double-sided-pcb-workflow.md) — drilled-hole registration
- Store: [SI3104 insulator](https://store.voltera.io/products/aci-ss1109-stretchable-insulator) · [ECV003 varnish](https://store.voltera.io/products/vfp-ecv003-2ml-cartridge-copy) · [Vacuum Module](https://store.voltera.io/products/vacuum-table) · [NOVA](https://store.voltera.io/products/voltera-nova)

**Ink datasheets (manufacturer):**
- [ACI SI3104 Rev 3](https://www.acimaterials.com/wp-content/uploads/2025/03/ACI-Data-Sheet-SI3104-Rev-3.pdf) — insulator; 9–14 µm DFT, 3 layers, 250 V/mil, 25 Pa·s, 135 °C; **no εr, no tanδ**
- [ACI SS1109 Rev 4](https://www.acimaterials.com/wp-content/uploads/2025/03/ACI-Data-Sheet-SS1109-Rev-4.pdf) — silver; < 4.5×10⁻⁵ Ω·cm, 10–20 µm cured, 135 °C/5 min
- [ACI SC1502 Rev 4](https://www.acimaterials.com/wp-content/uploads/2025/03/ACI-Data-Sheet-SC1502-Rev-4.pdf) — carbon; **< 236 Ω/sq/mil, < 0.6 Ω·cm, 6–12 µm cured, double-printable**, ≥120 °C

**Literature:**
- [Plasma-aided direct printing of silver nanoparticle conductive structures on PDMS, *Sci. Rep.* 14 (2024)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11680893/) — PDMS low surface energy, plasma remedy, hydrophobic recovery, 4.99 µm film

**Repo context:**
- `docs/mxene-voltera-nova-printability.md` — printed-MXene σ = 6.9×10⁵ S/m
- `docs/xband-absorber-substrate-shortlist.md` — measured εr/tanδ for silicone and Kapton at X-band
