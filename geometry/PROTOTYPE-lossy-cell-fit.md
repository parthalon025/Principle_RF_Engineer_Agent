# Prototype — does a lossy resonant cell fit inside a 2 mm printed skin?

**Ticket:** [#128](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/128) — put the
absorber's loss in the printed pattern, not the substrate. Part of the wayfinder map
[#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104).

**Throwaway. Branch only, never main.** Open `prototype_lossy_cell_fit.html` in a browser —
one file, no server, no install. Published copy:
<https://claude.ai/code/artifact/5e11be2a-20a8-429c-b6ef-5cd9407db39b>

---

## The question it was built to answer

#128 asked for "a rough two-layer cell sketch with real dimensions and a stated stack-up,
enough to react to. Not a simulation — a drawing that either fits or does not." Its three
open sub-questions were: does a resonant element with enough ohmic loss **fit** in a
sub-wavelength cell at the NOVA's 0.2 mm feature floor; **how is the stack built** inside
2 mm; and **what thickness does each layer want**.

The second was already answered on the ticket — the substrate is the spacer, the reflector is
unpatterned silver, printed dielectric is not an option. This prototype takes that stack as
given and answers the first and third.

---

## The answer, in one line

**Yes — but only if the loss and the capacitance are made out of different metal.**

A single lossy element cannot do both jobs at this thickness. Split them and the cell fits —
though the winning bridge is 0.245 mm against a 0.2 mm floor, so the margin is real but thin.
Leave them combined and nothing on the shortlist fits.

---

## The five things it settled

### 1. The pattern must supply most of the loss — but on silicone the substrate is a real minority partner

**Revised 2026-09-06 after adopting Costa et al.** The first version of this document said the
substrate supplies 2.2–5.3% and called it a rounding error. That was computed with a *lossless*
FSS capacitance, which cannot show the loss of the dielectric sitting in the gap between
elements. Costa's model has that term (his R_D), and it is the larger of the two dielectric
terms. Corrected figures, per Costa's three-way split at 10 GHz:

| Substrate | Gap dielectric R_D | Slab bulk | Substrate share of the loss budget |
|---|---|---|---|
| **Silicone 60 ShA** (tanδ 0.10) | 5.9–11.1 Ω/sq | 0.4–3.9 Ω/sq | **20–36%** |
| Kapton (tanδ 0.012) | 0.7–1.4 Ω/sq | 0.05–0.5 Ω/sq | 2.5–4.4% |
| FR4 (tanδ 0.017) | 1.1–2.3 Ω/sq | 0.1–1.6 Ω/sq | 4.1–6.9% |
| RO4350B (tanδ 0.0037) | 0.2–0.4 Ω/sq | 0.02–0.2 Ω/sq | 0.8–1.4% |
| LCP (tanδ 0.0025) | 0.15–0.3 Ω/sq | 0.01–0.1 Ω/sq | 0.5–0.9% |

So the premise still holds — the printed pattern supplies **64–80%** even on the lossiest
flexible sheet, and **95–99%** on every other one. But "rounding error" was wrong for silicone,
and the correction rehabilitates it: on silicone the loss is genuinely shared. Choosing a
substrate on loss tangent buys up to a third of the budget there, and essentially nothing
anywhere else.

Costa's own paper states the mechanism this ticket rests on, in as many words: *"Ohmic losses
can be neglected in microwave range since the resistor in (8) is generally one or two orders of
magnitude lower than the dielectric resistor (7). Conversely, if the metal is replaced by a
resistive paint, the resistor assumes considerably higher values than the dielectric resistor."*
Carbon ink is that resistive paint.

### 2. The cell wants 11–90 Ω/sq of ohmic loss, and no ink Voltera sells lands there

The resistance a perfectly matched cell wants from its printed pattern, over the legal
thickness range:

| Spacer | on silicone εr 2.9 | on Kapton εr 3.2 | on FR4 εr 4.8 |
|---|---|---|---|
| 1.0 mm | 11 Ω/sq | 17 Ω/sq | 17 Ω/sq |
| 1.5 mm | 31 Ω/sq | 40 Ω/sq | 44 Ω/sq |
| 1.96 mm | 59 Ω/sq | 75 Ω/sq | 90 Ω/sq |

(These are the **ohmic** figures — what the printed film must add on top of what the substrate
already supplies. Before the Costa correction they were 17/39/70 on silicone.)

Against what the machine can actually print at 10 GHz:

| Ink | Sheet resistance |
|---|---|
| ACI SS1109 silver, 10 µm | 0.13 Ω/sq |
| Printed MXene, 10 µm | 0.24 Ω/sq |
| **← the 11–90 Ω/sq the cell wants sits in this gap →** | |
| ACI SC1502 carbon, 24 µm (2 passes, datasheet max) | 250 Ω/sq |
| ACI SC1502 carbon, 12 µm (1 pass) | 500 Ω/sq |

**Nothing lands in the window.** The metals are three orders too conductive; carbon is three
to thirty times too resistive. This is the finding the ticket's comment thread had not
reached — the comment concluded carbon "lands exactly where a resistive sheet wants to be,"
which is true of the 377 Ω/sq Salisbury target but not of what a *thin resonant* cell wants,
and the thin resonant cell is the architecture #128 chose.

### 3. So thickness is not the loss knob — the element's aspect ratio is

Sheet resistance is not what the wave sees. What it sees is sheet resistance multiplied by
**how many square tiles long the current path is**. A short, wide element divides the ink's
resistance; a long, narrow one multiplies it. That factor is pure geometry — exactly the kind
of thing the design loop already searches, and it spans far more range than thickness does:

| Element | Squares in the path | 500 Ω/sq carbon becomes |
|---|---|---|
| Example 3's I-shaped ring resonator | ~13.3 | 6.7 kΩ/sq |
| A full-cell square patch | 1.0 | 500 Ω/sq |
| A bridge 0.245 mm long × 4 mm wide | 0.06 | **31 Ω/sq** |

Carbon's thickness knob spans 8:1 (1000 → 125 Ω/sq) and every value on it is too high.
Aspect ratio spans three orders and reaches down into the window. **This qualifies the
"thickness is a clean linear knob" claim in the ticket's second comment**: the knob is real
and linear, but its whole range sits above the target, so it cannot be the primary control.

### 4. The anchor's own element is the worst possible host for a lossy ink

Rescaled from Landy et al.'s fabricated device to silicone at 10 GHz, Example 3's I-shaped
ring resonator becomes a 5.89 × 16.83 mm cell with a 0.84 mm minimum feature — the features
clear the 0.2 mm floor easily. But its current runs around a narrow ring roughly **13 squares
long**, so in carbon it presents **3.3 kΩ/sq against the 31 Ω/sq wanted — 107× over-damped**,
absorbing 6% of the incident power.

The circuit model here only approximates a two-resonator cell, so the exact factor is soft.
The sign is not: a narrow-trace resonator multiplies the ink's resistance by its square count,
and that is the wrong direction by two orders of magnitude. Reusing the anchor's geometry with
a lossy ink does not work, and this is the reason.

### 5. The cell that fits

| Layer | Material | Thickness | Passes |
|---|---|---|---|
| Resonant + lossy | ACI SS1109 silver plates + one ACI SC1502 carbon bridge, coplanar | 12 µm | 1 |
| Spacer | Silicone sheet 60 ShA (or Kapton / RO4350B) — **stock sheet, not printed** | 1.50 mm | — |
| Reflector | ACI SS1109 silver, **unpatterned** | 15 µm | 1–2 (4.4 skin depths) |
| **Total** | | **1.527 mm** | inside 0.87–2.00 mm |

In-plane geometry at 10 GHz: cell period **6.0 mm (0.20 λ₀)**, gap between elements
**0.498 mm**, carbon bridge **0.245 mm long × 4.0 mm wide**. Smallest printed feature
**0.245 mm** against the 0.2 mm floor — clears it, but by only a quarter, which is less margin
than the pre-Costa figure of 0.314 mm suggested. Predicted **100% absorption at 10.0 GHz,
≥90% from 9.1 to 11.3 GHz (22% fractional)** — well inside the Rozanov ceiling of ~88% that
`docs/absorber-thickness-bandwidth-bound.md` computes for 2 mm.

The bridge is the tuning knob and it still has range across the legal spacer thicknesses, but
widening it (the `b` control) is now the way to buy back margin over the feature floor.

**Two consequences worth flagging before anyone builds this.**

- It needs **two conductive inks side by side on the same layer**. That is a nozzle change,
  not a second layer — so it is governed by the ±20 µm single-layer positioning figure, not by
  the layer-to-layer registration figure `docs/voltera-multilayer-capability.md` §3 records as
  unpublished. Still an assumption: coplanar two-ink printing on a NOVA is undocumented and
  belongs in #106's bench work.
- It preserves #108's layer architecture exactly — one functional patterned layer on a blank
  printed reflector, no two-patterned-layer registration problem.

### And one derived constraint nobody had stated

**The feature floor sets a minimum spacer thickness.** A thinner spacer needs more capacitance
to resonate, which means a narrower gap; below about **1.04 mm on silicone** (0.97 mm on
Kapton, 0.90 mm on RO4350B) the gap the physics wants falls under 0.2 mm and the printer
cannot make it. There is no thinner cell available on this machine, whatever the optimiser
tries. Scenario 05 in the prototype walks into this wall.

---

## Added after the first pass

**Reflector as a control (silver / MXene).** Both are mirrors — MXene at 27 µm is 4.5 skin
depths, and its 0.24 Ω/sq against silver's 0.13 is under 1% of what the lossy layer supplies.
The real difference is the cure path: silver needs 135 °C, MXene is room-temperature. MXene
cannot be the lossy layer — 130–280× too conductive, and reaching the target would need ~27 mm
of meandered trace in a 6 mm cell, which is 1.5 guided wavelengths and stops being a resistor.
(`RUNNING-LISTS.md` §3 item 6 already records that "N meandered squares gives N× the
resistance" is DC reasoning; this reproduces that correction independently.)

**Two transmissive designs.** D is a single-layer square-loop slot bandpass (Langley & Parker
equivalent circuit via Babinet); E puts the lossy cell over it instead of a solid mirror. The
carried finding is the **layer count** — a bandpass needs one patterned layer, so the
unpublished layer-to-layer registration figure never enters; the rasorber needs two on opposite
faces, which puts it back on the critical path. E fails in this model (best ~75% absorbed,
~26% through) because one resonant layer is a single pole; recorded as **provisional**, since
the bandpass model drops a correction term and probably over-states its bandwidth.

Two notes this raises elsewhere. A bandpass is a *printable* transmissive design, which is the
live conflict **ADR-0017** assumed did not exist — its consequences section says a transmissive
design would break the printed-reflector default "but the only such examples in the patent
(1 and 2) are already excluded on fabrication-process grounds, so there is no live conflict
today." That exclusion is an artefact of the patent's example list, not of what is printable.
And the printed insulator cannot separate two patterned layers at all: a patch layer over a
wire mesh at 30 µm overlaps ~73 mm² per cell, ~64 pF against a 0.38 pF design value.

**Datasheet corrections.** Fetched ACI SC1502 Rev 4 and SS1109 Rev 4 directly. SC1502 does
**not** need ≥120 °C — "Low cure temperature 80 °C is possible for temperature sensitive
materials"; the no-oven conclusion survives (80 °C still exceeds the NOVA's 40 °C) but the
substrate set widens. SS1109 cures at 135 °C for 15 min, not 5. Both publish elongation
>200% on TPU and "rapid return after strain", but **no resistance-versus-strain curve and no
cycle count** — which matters asymmetrically, since silver works as a mirror while the carbon
bridge's resistance *is* the design parameter. `RUNNING-LISTS.md` already ranks "carbon sheet
resistance at two passes" as unknown #4 of 11, tagged to #106 and #128; strain is the natural
extension of that same coupon.

**Bend rule.** The bench enforces the patent's R ≥ 3T. `RUNNING-LISTS.md` unknown #10 records
that IPC-2223's flex-circuit standard is 6× total thickness — twice as strict — which would put
the minimum radius for this 1.527 mm stack at 9.2 mm rather than 4.6 mm, and halve the
worst-case strain from 16.6% to 8.3%. Tracked on #115, unresolved.

**The full-wave check this needs is currently not runnable.** Per #111's resolution:
`simulation/palace.py` has native Floquet ports but **no conductivity field at all**, so it
cannot see conductor loss — the whole point here; `simulation/openems.py` has **no Floquet
boundary**. The adopted plan is to extend Meep with a Bloch `k_point` and adopt EMerge, neither
built. Ohmic loss must be modelled as a surface-impedance boundary, never a meshed conductor.

---

## What the model is

`CALCULATED` throughout, and it is the formulation **#111 adopted for the fast tier**:
Luukkonen's analytical patch-grid capacitance inside **Costa, Genovesi, Monorchio & Manara's
absorber-stack model** ([arXiv:1211.1902](https://arxiv.org/abs/1211.1902)). The grid
capacitance is complex — its effective permittivity is the air/substrate average carrying the
substrate's loss tangent — so Costa's dielectric resistor R_D falls straight out of it. The
substrate and mirror below are a shorted transmission line with complex propagation constant.
Absorption is `1 − |Γ|²` at normal incidence.

**One term of Costa's model is not implemented.** Below a spacer thickness of about 0.3 × the
cell period, evanescent Floquet modes reflected by the ground plane raise the gap capacitance,
and his equation (10) corrects for it. This design sits at d/p = 0.25, inside that regime, but
the equation's exact form could not be recovered — the paper's PDF encodes its maths in a subset
font that defeats text extraction, and no open secondary source restating it was found. The
*direction* is known (capacitance rises, so the true resonance sits below what is drawn and the
gap needed to reach 10 GHz is wider than shown); the magnitude is not. The frequency axis
carries that bias.

Deliberately **not** a full-wave solve. It gets resonant frequency and match to within tens of
percent, which is all a fit question needs. It does not model coupling between neighbouring
cells, oblique incidence, polarisation, or bending — and it does not describe a two-resonator
cell properly, which is flagged in the page wherever design C is selected. The square-count
factor uses a uniform-current approximation, so treat it as order-of-magnitude.

## Sources it leans on

`docs/voltera-multilayer-capability.md` (ink and machine figures), the ACI SC1502 and SS1109
datasheets, `docs/xband-absorber-substrate-shortlist.md` (substrate εr/tanδ),
`docs/ishape-interior-tuning.md` (Landy et al. 2008 dimensions),
`docs/absorber-thickness-bandwidth-bound.md` (Rozanov ceiling),
`docs/diw-feature-floor-mechanism.md` (the 0.2 mm floor and its caveats).
