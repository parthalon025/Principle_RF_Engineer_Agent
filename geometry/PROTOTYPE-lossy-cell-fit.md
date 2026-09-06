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

A single lossy element cannot do both jobs at this thickness. Split them and the cell fits
with room to spare; leave them combined and nothing on the shortlist fits.

---

## The five things it settled

### 1. Substrate loss is a rounding error, so #128's premise is forced, not preferred

Silicone at tanδ = 0.10 is the lossiest flexible sheet in
`docs/xband-absorber-substrate-shortlist.md`, about six times FR4's. Across the whole
0.87–2.0 mm budget at 10 GHz it supplies **2.2% to 5.3%** of the dissipation the cell needs.
RO4350B and LCP supply **0.1–0.2%**.

Plainly: at these thicknesses the wave barely spends any time inside the substrate, so it
hardly matters how lossy the substrate is. #128 argued for pattern-loss on architectural
grounds — that geometry is searchable and material properties are not. The arithmetic says
it is also the only thing that works. And it kills the substrate ranking outright: choosing a
substrate on loss tangent buys between nothing and 5%.

### 2. The cell wants 17–92 Ω/sq, and no ink Voltera sells lands there

The resistance a perfectly matched cell wants from its printed pattern, over the legal
thickness range:

| Spacer | on silicone εr 2.9 | on Kapton εr 3.2 | on FR4 εr 4.8 |
|---|---|---|---|
| 1.0 mm | 17 Ω/sq | 17 Ω/sq | 18 Ω/sq |
| 1.5 mm | 39 Ω/sq | 41 Ω/sq | 46 Ω/sq |
| 1.96 mm | 70 Ω/sq | 76 Ω/sq | 92 Ω/sq |

Against what the machine can actually print at 10 GHz:

| Ink | Sheet resistance |
|---|---|
| ACI SS1109 silver, 10 µm | 0.13 Ω/sq |
| Printed MXene, 10 µm | 0.24 Ω/sq |
| **← the 15–92 Ω/sq the cell wants sits in this gap →** | |
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
| A bridge 0.31 mm long × 4 mm wide | 0.08 | **39 Ω/sq** |

Carbon's thickness knob spans 8:1 (1000 → 125 Ω/sq) and every value on it is too high.
Aspect ratio spans three orders and reaches down into the window. **This qualifies the
"thickness is a clean linear knob" claim in the ticket's second comment**: the knob is real
and linear, but its whole range sits above the target, so it cannot be the primary control.

### 4. The anchor's own element is the worst possible host for a lossy ink

Rescaled from Landy et al.'s fabricated device to silicone at 10 GHz, Example 3's I-shaped
ring resonator becomes a 5.89 × 16.83 mm cell with a 0.84 mm minimum feature — the features
clear the 0.2 mm floor easily. But its current runs around a narrow ring roughly **13 squares
long**, so in carbon it presents **3.3 kΩ/sq against the 39 Ω/sq wanted — 85× over-damped**,
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
**0.498 mm**, carbon bridge **0.314 mm long × 4.0 mm wide**. Smallest printed feature
**0.314 mm**, comfortably above the 0.2 mm floor. Predicted **100% absorption at 10.0 GHz,
≥90% from 9.1 to 11.3 GHz (22% fractional)** — well inside the Rozanov ceiling of ~88% that
`docs/absorber-thickness-bandwidth-bound.md` computes for 2 mm.

The bridge is the tuning knob and it has real range: 0.2–0.8 mm of length across the legal
spacer range, all of it printable.

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

## What the model is

A lumped circuit model, `CALCULATED` throughout: the printed layer is one resistance in series
with one capacitance (Luukkonen's analytical patch-grid form, effective permittivity taken as
the air/substrate average); the substrate and mirror below are a shorted transmission line with
complex propagation constant. Absorption is `1 − |Γ|²` at normal incidence.

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
