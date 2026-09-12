# Handoff: metamaterial-printing direction (grilling in progress)

Portable state of an unfinished `/grill-with-docs` session, written so it can
be picked up cold. Nothing here is committed as a decision except where
marked **SETTLED**. Everything else is open, and several of my own earlier
claims were wrong and are corrected below — read the "Corrections" section
before building on anything.

> ### Four claims in this document were later overturned
>
> Research done after this file was written disproved four of its numbers.
> Each is struck through and corrected in place below; the consolidated
> record is [`RUNNING-LISTS.md` §3](RUNNING-LISTS.md).
>
> 1. Example 1's permittivity — the prose figure drops a loss term the
>    drawing carries.
> 2. Whether the cells sit at the printer's feature floor — they do not.
> 3. The cure-compatibility table's silver row — silver prints on PET and
>    TPU after all.
> 4. MXene's loss penalty against copper at radio frequencies — overstated
>    by roughly ten times.
>
> **The live map for this effort is issue #104, not this file.** This is the
> starting point that grew into it, kept for its arithmetic and its record of
> what was believed when.

## Why this exists separately from PR #86

PR #86 (`claude/iterative-prototype-testing-7hbkwr`) implemented spec #87 —
requirement targets, Success score, batched lab test plan, candidate solver,
instrument-package removal. It merged to `main` as `ccb4f5c`.

This is a different thing: the project's actual target turns out to be
**printed metamaterial electromagnetic skins**, and PR #86's loop optimizes
the wrong variable for that (see "The architectural gap"). This stream was
deliberately kept off that PR at the project lead's instruction.

## The target

**US patent US12089385B2**, "Highly-conformal, pliable thin electromagnetic
skin" — US Army (DEVCOM), inventors Zaghloul, Nguyen, Adler. Filed
2020-12-16, granted 2024-09-10.

A pliable film under 2 mm thick carrying sub-wavelength metamaterial
elements, conforming to curved host surfaces (aircraft, vehicles, walls), to
block, absorb, enhance or bend RF. `CONTEXT.md`'s "Adaptive EM skin" entry
was clearly written from this patent — the abstract's four functions are
almost verbatim the glossary's "transmit, absorb, reflect, or steer".

Key patent numbers: **X-band 8–12 GHz** primary (examples span 8.3–17 GHz);
thickness 0.87–2.0 mm; surface conformity <10–20 µm; minimum bend radius
**R = 3T** with embedded elements (also `R = T(50/r − 1)`); metamaterial
insert εr ≥ 2.9, or >50 for the high-permittivity examples (strontium
titanate at ~~εr = 310~~ **ε₁ = 250 − 1.25j**, from FIG. 5C — the prose
figure omits the loss term the drawing carries; Example 2 is 294 − 0.5j);
host polymer εr 2–5, loss tangent <0.2.

The uploaded PDF is a **scan with no text layer** (32 pages, zero extractable
characters; `pdftoppm`/poppler unavailable in this environment). Patent text
was retrieved from Google Patents instead. Anyone re-reading it will need to
do the same or OCR the scan.

### The seven examples

The patent gives seven functionally distinct skins. They need different
design variables, different simulation setups and different success criteria,
so which one you target changes everything downstream.

| # | What it does | Element geometry | Band |
|---|---|---|---|
| 1 | Magnetic mirror — reflects with zero phase shift, so an antenna can sit flush on metal | Strontium titanate cubes, ~~εr = 310~~ **ε₁ = 250 − 1.25j** (FIG. 5C, not the prose); Mie resonance gives µ ≈ 5→20 | 8.3–8.7 GHz |
| 2 | Impedance-matched to free space, no refraction | Dual cubes, ε and µ resonances matched | 9–10 GHz |
| 3 | **Absorber** — no reflection, no transmission | I-shape electric ring resonators over rectangular wire resonators, on FR4 (εr 4.8, **tanδ 0.017**) | 8.5–10.5 GHz — **FIG. 7G's plot range, not a stated requirement** (`RUNNING-LISTS.md` §3 correction 27) |
| 4 | Reflection phase tuned per cell → steers the bounce | Cylinders; **diameter** is the knob | 10 GHz |
| 5 | Same, electrically tunable | Square patches with BST film ~20 µm, <40 V bias | 10–20 GHz |
| 6 | Polarization converter, linear ↔ circular | Meander lines | 13–17 GHz |
| 7 | Backscatter reduction by sideways scattering | Circular inter-digitated rings with meandered slot, checkerboard | 13–15 GHz |

## SETTLED

1. **Start with Example 3 (absorber). All seven eventually in scope.** The
   second half is the architecturally consequential part.
2. **Fabrication: Voltera NOVA Materials Dispensing System**, for
   prototyping. Verified specs from Voltera: minimum line width **100 µm**
   ("dependent on material and nozzle"); Nordson EFD 150 µm and 200 µm tips
   referenced; viscosity **1,000–1,000,000 cP** (so direct-ink-write of
   pastes, three to five orders above inkjet's ~10 cP); positioning accuracy
   **±20 µm** (XYZ resolution 2.5 / 7 / 1.25 µm); material temperature
   control only **up to 40 °C**; **≥10⁷ S/m** single-pass conductivity
   (their silver); print area 220 × 300 mm; substrates glass, ceramic, TPU
   via vacuum table, PET, polyimide, textiles.
3. **Conductor: MXene primary; silver and copper are optional alternatives.**
4. **Material AND substrate are variables in the process**, not fixed inputs.
   (This overturned an earlier recommendation of mine to fix the material —
   see Corrections.)

## Evidence gathered

Two research documents, both with inline primary-source citations and
explicit statements of what could not be verified:

- **`docs/mxene-voltera-nova-printability.md`** (this branch) — can MXene be
  printed on this machine, at what feature size, and is the film electrically
  thick at X-band.
- **`docs/PATCH_ANTENNA_FIXTURE_CANDIDATES.md`** (on the PR #86 branch) — a
  search for a real published case to serve as an end-to-end test fixture.
  Finding is an evidenced **no**: nothing surveyed combines redistributable
  rights, measured *and* simulated data, machine-readable Touchstone, 50 µm
  geometry and a characterized (not datasheet-nominal) εr. Note this was run
  against a 2.45 GHz assumption and should be redone for X-band.

### The MXene numbers that matter

- Finest demonstrated extrusion-printed line: **120 µm** — Song et al.,
  *Nature Communications* 13, 3223 (2022), DOI 10.1038/s41467-022-30648-2,
  open access. On a pneumatic three-axis dispenser, mechanically the same
  class as the NOVA, **not** a Voltera.
- Ink viscosity ~250,000 cP at 60 mg/mL — **inside** the NOVA's window.
- As-printed conductivity **6.26–6.9×10⁵ S/m** (not freestanding-film, which
  is higher and not what you get from a printer).
- **No sintering required** — room-temperature metallic conductivity. This is
  the best-supported claim in the literature and the real justification for
  choosing MXene.
- **No MXene-on-Voltera combination exists anywhere** — confirmed absent from
  the literature and Voltera's own site, not merely unfound.

### Arithmetic worth not re-deriving

- Skin depth δ = √(1/(πfμσ)). At 10 GHz: printed silver (10⁷ S/m) ≈ **1.6 µm**;
  MXene (6.9×10⁵ S/m) ≈ **5.5–6.8 µm** across 8–12 GHz.
- So MXene needs **~20–35 µm** (3–5 skin depths) to behave as a conductor
  rather than a lossy sheet. Silver needs 2–3 µm.
- Sheet resistance Rs = 1/(σt). MXene at 25 µm ≈ **0.06 Ω/sq**; copper at the
  same thickness ≈ 0.0007 Ω/sq.
- At 10 GHz, λ₀ = 30 mm; on εr ≈ 3 the guided wavelength is ~17 mm, so
  sub-wavelength cells land around 1.7–6 mm with intra-cell gaps typically
  100–300 µm.

> ~~"Right at the machine's floor, not comfortably below it."~~
> **Overturned.** That gap range was a generic estimate, never checked
> against what the patent's drawings actually specify. Read from the
> drawings, the smallest feature across all seven examples is **0.2 mm —
> 2 to 6 times *above* the NOVA's 100 µm floor.** In plain terms: the
> printer can draw these shapes with room to spare, so feature size is not
> the binding fabrication constraint this document took it for.

### Cure compatibility — prunes the material/substrate space for free

| | PET (~80 °C) | TPU | Polyimide (400 °C) | Glass/ceramic |
|---|---|---|---|---|
| **Silver** (120–200 °C cure) | ~~✗~~ **✓** | ~~✗~~ **✓** | ✓ | ✓ |
| **Copper** (sinter + oxidation) | ✗ | ✗ | ✓ | ✓ |
| **MXene** (room temp) | ✓ | ✓ | ✓ | ✓ |

> **The silver row was wrong.** Silver cures at 120 °C for 30 min on PET, and
> Intexar PE874 — already on Voltera's own materials list — cures at 130 °C
> on TPU film. Substrate class does not rule silver out.
>
> **What rules silver out is whether the finished part can leave the host and
> go into an oven.** A skin printed onto an aircraft where it sits cannot; a
> coupon printed on a loose sheet can. That is a property of the job, not of
> the substrate. It narrows MXene's decisive advantage to printing *in place*
> on something that cannot be baked — and leaves silver competitive
> everywhere else, PET and TPU included.

The NOVA reaches only 40 °C, so silver and copper must be sintered
off-machine.

## Corrections — do not inherit these errors

1. **"MXene's loss is the absorber's mechanism" — WRONG.** I said this; the
   arithmetic doesn't support it. At the thickness needed for electrical
   thickness, MXene is ~0.06 Ω/sq, a *conductor*. A resistive-sheet absorber
   wants ~377 Ω/sq, which MXene would only reach at ~4 nm — far below what
   dispensing can produce. In Example 3, MXene behaves as a slightly lossier
   copper — ~~85×~~ **about 9× at 10 GHz** — which **damps the resonance:
   broader band, shallower peak**. That may be desirable, but it is a
   different claim. MXene's justification is the 40 °C cure, not the loss.

   > **The 85× was a direct-current ratio quoted at 10 GHz.** At radio
   > frequencies the current does not fill the conductor; it rides the top
   > few micrometres. Once the film is thicker than about three skin depths,
   > what matters is surface resistance, which scales as 1/√σ rather than
   > 1/σ — so the square root halves the exponent and the honest RF penalty
   > is **~9× versus copper and ~3.8× versus silver**, roughly ten times
   > smaller than every comparison built on 85× assumed.
2. **"Fix the material, don't let the solver search it" — overruled.**
   Material and substrate are process variables. For an absorber especially,
   the substrate's loss tangent is a primary design input (FR4's 0.017 does
   much of the dissipating), so fixing it would optimize around the wrong
   thing.
3. **`CONTEXT.md` contradicts the patent.** The "Metamaterial unit cell"
   entry says geometry "— not material composition —" produces the effective
   permittivity/permeability. The patent's Example 1 gets its magnetic
   response from Mie resonance in **strontium titanate at ε₁ = 250 − 1.25j**
   (FIG. 5C; this document first recorded the prose's 310), and
   Example 5 uses tunable BST. Material composition is doing the work. This
   glossary entry needs correcting.
4. **50 µm is almost certainly not feature resolution.** Best demonstrated
   MXene line is 120 µm; the machine's own floor is 100 µm with *their*
   silver. But ±20 µm positioning accuracy × a safety factor lands close to
   50 µm as a **placement/registration budget**. Unconfirmed — see Q3.

## The architectural gap in the merged loop

> **This is now a gap on `main`, not on a branch.** PR #86 merged as
> `ccb4f5c`, so everything below describes shipped code rather than a
> proposal. It is also in direct tension with issue #104's stated
> destination — "unit-cell periodicity rather than patch length as the
> degree of freedom" — which makes closing it implementation work someone
> has to budget for, not a footnote.

`orchestration/design_loop.py` hardwires `ANALYSIS` to
`patch_resonant_frequency_hz` (~line 403; moved from `rf_tools.calculations`
to `rf_tools.patch_synthesis` under issue #522) and
`OPTIMIZATION` to `optimize_patch_length_for_target_frequency` (~line 436).
Both are **rectangular microstrip patch** formulas. So the solver built in
#95 will faithfully converge on *patch length* — not a printed
metamaterial's degree of freedom.

The right pieces already exist in the repo and are **not wired into the
loop**:

- `rf_tools/calculations.py::maxwell_garnett_effective_permeability` —
  effective-medium model, the natural fast inner-loop calculation
- `geometry/unit_cell.py::generate_unit_cell_array` — takes `spacing_m`,
  i.e. the unit-cell period, a genuine design variable
- `geometry/freecad_curved.py::map_unit_cell_layout_to_curved_surface`
- `simulation/palace.py` and `simulation/openems.py` — the only two adapters
  with periodic/Floquet boundaries, which is what actually characterizes a
  unit cell. `CONTEXT.md` already describes Palace's Floquet ports as being
  "for characterizing a periodic metamaterial unit cell's actual
  electromagnetic behavior" — the domain doc knows; the loop doesn't.

Also missing entirely: any model of **conductor loss** (no sheet resistance,
surface impedance or finite conductivity anywhere) and any model of
**fabrication constraints** (no minimum feature size, no bend radius, no
cure compatibility).

## Open questions

Numbered as asked in session; several were re-asked after evidence arrived.

**Blocking:**

- **Q3** — What does the 50 µm figure actually constrain: feature resolution,
  placement/registration accuracy, or layer-thickness control? Evidence says
  it cannot be feature resolution on this machine.
- **Q10** — Confirm the MXene bet is specifically **no-sintering** (enabling
  PET/TPU on a 40 °C machine), not conductivity.
- **Q14** — **Nobody has printed MXene on a Voltera.** Should the first real
  use of the system be *process characterization* — print coupons, measure
  actual line width, thickness-per-pass and conductivity on the real machine
  with the real ink — before any design iteration? Every constraint above is
  currently literature-extrapolated to uncharacterized hardware.
  **Recommended as the next step.**
- **Q20** — What is the actual worst-case bend radius on the target platform?
  R = 3T forces TPU-class substrates, but most vehicle/aircraft panels curve
  on radii of tens of centimetres to metres, where polyimide is fine — and
  then **silver becomes available and outperforms MXene ~15×**. This could
  substantially simplify the programme.

**Design shape:**

- **Q16** — How should the loop carry seven design families? Recommended: a
  registry defined now, while Example 3 is the only member, rather than
  retrofitting a seam after three families exist.
- **Q21** — Confirm: discrete material/substrate pairs enumerated and
  cure-pruned (outer), continuous geometry search within each (inner),
  commitment to a pair still gated at `ARCHITECTURE`.
- **Q17** — For Example 3: peak absorption or bandwidth? MXene's damping
  trades one for the other, and they score candidates differently.
- **Q18 / Q23** — Which substrate, and what is the real shortlist? For an
  absorber the loss tangent is a design input, and swapping the patent's
  rigid FR4 (tanδ 0.017) for a flexible low-loss substrate **weakens
  absorption** and needs compensating.
- **Q15** — Thickness-per-pass is unmeasured at fine line widths. You need
  20–35 µm. Fold into Q14.

**Smaller:**

- **Q22** — Material-property provenance. Substrate εr/tanδ can come from
  laminate datasheets through the existing ingestion pipeline as
  `MANUFACTURER-SPECIFIED`; MXene conductivity is `LITERATURE-SUPPORTED`
  until characterized, then `MEASURED`. A score should inherit the weakest
  link rather than presenting all candidates as equally trustworthy.
- **Q6** — Enforce R = 3T and the feature floor as hard `CALCULATED`
  candidate constraints. (Supersedes ADR-0014's `INFERRED` "manufacturability
  risk" note, which was an under-call.)
- **Q7** — Add a `patent` source type? `CONTEXT.md` has none, and a patent's
  numbers carry different weight than a measurement while its claims are
  legal text that must never read as design guidance.
- **Q5** — Two-tier EM modelling: Maxwell-Garnett for the fast inner loop,
  Palace/openEMS Floquet to confirm survivors. Both halves already exist.
- **Q2 / Q4** — Confirm X-band 8–12 GHz, and that the route is DIW dispensing
  of printed elements rather than the patent's punch-and-insert of pre-made
  pieces.

## Loose ends

- A background cloud session (`session_01W89Vgd1PWs5xS4zNf5fpL1`, "MXene
  EM-skin conductor research") was spawned by a sub-agent that delegated
  instead of researching. It works in **its own clone**, is not reachable via
  `SendMessage`, and had not pushed anything. Its output covering broader
  ground — oxidation/shelf life, EMI shielding, a full silver/copper/MXene
  comparison — may be stranded. The decision-critical material was
  re-researched directly and is in
  `docs/mxene-voltera-nova-printability.md`.
- The fixture research should be **redone for X-band**; it assumed 2.45 GHz.
- MDPI returns HTTP 403 to automated fetches from this environment (verified
  — theirs, not a proxy problem). Anything behind it needs a human with a
  browser.
