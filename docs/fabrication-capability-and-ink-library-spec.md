# Fabrication-capability and Ink-property libraries — specification

**Status:** plan-only specification. No code accompanies it, per issue
[#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104)'s standing
preference. Implementation lands as its own `ready-for-agent` issue, the same way
[#154](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/154) implemented
ADR-0015 after the decision was accepted.

**Provenance ladder** is `CONTEXT.md`'s eight rungs. `MEASURED` appears nowhere in this
document: this programme has measured none of it yet. That is the point — see §7.

---

## 1. The problem, stated as a test

The design loop treats **material** as a searched variable
([#105](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/105): *"Material
is a variable; material properties are the constant"*), and
[#108](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/108) settled that
fabrication is a **configured** capability — *"three independent stages — print / cure
(gated by oven-reachability, not the printer's own warmer) / laminate — not one lumped
'which printer.'"*

Neither is true of the tree today.

| Library | Status |
|---|---|
| Material-property | Built — `designs/material_properties.py`, ADR-0015 |
| Element/Coding-Alphabet | `CONTEXT.md:382` vocabulary only, **no code** |
| **Fabrication capability** | `CONTEXT.md:181` vocabulary only, **no code** |
| **Ink-property** | **Does not exist** — not in code, not in `CONTEXT.md` |

The Material-property library is also the thinnest of the three in practice: it is built, but
seeded only with FR4. `docs/xband-absorber-substrate-shortlist.md` §1 already catalogues
twelve substrates with εr, tan δ and provenance — starting with silicone — and none of it has
been migrated out of the markdown table. See §9.4.

#108's configured-fabrication decision has **no ADR**; ADR-0017 covers the printed-reflector
default, not this.

**This spec adopts `CONTEXT.md`'s existing term rather than coining one.** An earlier draft
called the first table `machine_capabilities`, which was a second name for a concept the
domain model already had — and one the entry's own *Avoid* list warns against:

> *Avoid*: **fabrication route** — describes one chosen path through a capability, not the
> configured set a path gets chosen from; **printer capability** — too narrow, since cure and
> lamination are not properties of the printer alone.

`CONTEXT.md:181` already defines **Fabrication capability** as *"the configured, cross-run set
of what a specific piece of equipment can currently build … checked per candidate design, the
same way a Material-property library entry is checked per material: not re-derived per
requirement, and never hardcoded into the loop's own logic,"* with the three stages named and
the never-silently-dropped disposition already attached. So the design work here is **not**
the concept — it is the schema, the seed rows, and the seam to the ink library. Only
**Ink-property** is a genuinely new term.

**The test this spec must pass is a row count, not an abstraction.** A library holding one
member is a constant wearing a library's clothes —
[#107](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/107) already
noticed the same thing about the family registry (*"designed now, with one member"*). So:

> **Add a second machine and a second ink. Everything that breaks was a hidden constant.**

*In plain terms: you have not made the loop printer-agnostic by writing an interface. You
have made it printer-agnostic when a second printer is actually in the table and the answers
change.*

### 1.1 The hidden constants this exposes

Every figure below has been used in analysis on this programme as though it were a fact about
the world. Each is a property of one machine or one product:

| Figure | Actually a property of |
|---|---|
| 0.2 mm feature floor | the Voltera NOVA |
| ~10 µm minimum cured film | the NOVA — and see §5.1, it is not even a spec |
| 40 °C material-temperature ceiling | the NOVA |
| ±20 µm positioning | the NOVA |
| 377 Ω/sq at 15.9 µm | ACI SC1502 specifically |
| σ = 6.26–6.9 × 10⁵ S/m | one MXene ink, from one paper |

The sharpest case: a prior synthesis concluded that a `PLANAR-RESISTIVE` design family is
**valid 22.8–114 GHz**. That is stated as a property of a *design family*, and **both
endpoints are properties of one printer** — the lower bound is quarter-wave thickness against
the skin budget, the upper is a ±20 µm layer-height tolerance. Swap the machine and the
family's whole validity window moves.

#104 already names this failure: *"manufacturing and material figures are **measurements
valid inside a stated box** (pitch, ink, pass count, cure, grade), and quoted without their
box they are assumptions."* Quoting them without their box is what converts a measurement into
an assumption, and there is currently nowhere to keep the box.

---

## 2. Three libraries, one shape, three different keys

All three follow `designs/material_properties.py` exactly: a keyed tuple, **every citation its
own row and never collapsed**, per-entry provenance, and a cited family bracket on a miss.
Nothing new is invented here; the shape is ADR-0015's, applied twice more.

| Library | Key | Holds | Frequency-keyed? |
|---|---|---|---|
| Material-property (built) | `(material, frequency, property)` | facts about a **substance** — TPU's εr, FR4's tan δ | yes |
| **Fabrication capability** (`CONTEXT.md:181`, unbuilt) | `(machine, process_stage, capability)` | facts about **one piece of equipment at one stage** — feature floor, thickness per pass, cure ceiling | no |
| **Ink-property** (new) | `(ink, process_state, property)` | facts about a **purchasable product** and what it becomes when printed | no |

### 2.1 Why ink cannot just be a material

An ink's electrical behaviour is **not a property of the ink alone**. ACI SC1502 at 6 µm, at
12 µm and at 24 µm are three different sheet resistances; MXene's as-printed conductivity
depends on whether it was cured, and at what temperature. The property belongs to the triple
`(ink, machine, process settings)`, and the Material-property library has no process axis to
hang that on.

So the seam is:

- **Ink-property library** — what you buy and what the datasheet says it becomes when printed
  a stated way (volume resistivity, recommended cured thickness, cure schedule, viscosity).
- **Fabrication-capability library** — what a given machine can actually lay down (line width,
  thickness per pass, positioning, temperature ceiling, build area).
- **Material-property library** — what the *cured film* then is, electromagnetically, at
  frequency.

A printable candidate is therefore a **`(machine, ink, material)` triple**, and the loop must
enumerate triples rather than assume one of each.

### 2.2 Everything here is ENVELOPE class

`docs/` S6's derivation separates **LAW** (derived, non-revisable) from **REGIME**
(model-validity gates) from **ENVELOPE** (revisable data, *never code*). Machine and ink facts
are **envelope throughout**. None of them is ever law: a feature floor is a fact about a
product generation, revised by the next one. They are therefore **data rows, never constants
in Python**.

---

## 3. Fabrication-capability library

### 3.1 Schema

```sql
-- Facts about one machine at one process stage. Deliberately no UNIQUE on
-- (machine, process_stage, capability): two sources disagreeing about the
-- same machine's minimum tracewidth is the case this table exists to keep,
-- exactly as material_properties keeps three FR4 papers that disagree.
CREATE TABLE IF NOT EXISTS fabrication_capabilities (
    id BIGSERIAL PRIMARY KEY,
    machine TEXT NOT NULL,              -- 'Voltera NOVA'
    process_stage TEXT NOT NULL,        -- 'print' | 'cure' | 'laminate'  (#108)
    capability TEXT NOT NULL,           -- 'min_tracewidth_m'
    value DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL,
    qualifier TEXT,                     -- the stated box: 'with 100 um nozzle,
                                        -- material-dependent'
    provenance TEXT NOT NULL,
    citation TEXT,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS fabrication_capabilities_machine_stage_idx
ON fabrication_capabilities (machine, process_stage);
```

**`process_stage` is #108's decision made structural.** A machine gets a row per stage it can
perform, and a stage it cannot perform simply has no rows — which is how "the NOVA's warmer is
not an oven" is expressed without a special case. An oven is a separate `machine` with only
`cure` rows.

**`qualifier` is the stated box, and it is not optional in spirit.** `min_tracewidth_m = 100e-6`
without *"dependent on material and nozzle"* is the assumption #104 warns about. A row whose
qualifier is genuinely empty should say so explicitly rather than leaving `NULL` ambiguous.

### 3.2 Seed rows — Voltera NOVA

Every figure below is transcribed, not derived. Sources are already in
`docs/voltera-multilayer-capability.md`.

| capability | value | qualifier | provenance |
|---|---|---|---|
| `min_tracewidth_m` | 100 µm | "dependent on material and nozzle" | `MANUFACTURER-SPECIFIED` |
| `nozzle_diameters_m` | 100, 150, 225 µm | supplied; Nordson EFD / Subrex to 50 µm available | `MANUFACTURER-SPECIFIED` |
| `positioning_accuracy_m` | ±20 µm | **single-layer, in-plane** — see §5.2 | `MANUFACTURER-SPECIFIED` |
| `max_dispense_pressure_psi` | 70 | — | `MANUFACTURER-SPECIFIED` |
| `material_temperature_max_c` | 40 | material temperature, not substrate | `MANUFACTURER-SPECIFIED` |
| `ink_viscosity_range_cp` | 1,000–1,000,000 | — | `MANUFACTURER-SPECIFIED` |
| `print_area_m` | 220 × 300 mm | — | `MANUFACTURER-SPECIFIED` |
| `min_cured_film_m` | 10 µm | **low end of a 60 µm print-height example; Voltera publishes no guaranteed minimum** | `INFERRED` |

That last row is the one this library most needs to exist for. It has been used across this
programme as "the machine's ~10 µm floor," and it is the low end of one worked example. In the
library it carries `INFERRED` and its qualifier, so a reader cannot mistake it for a spec.

---

## 4. Ink-property library

### 4.1 Schema

```sql
-- Facts about one purchasable ink in one process state. process_state
-- captures what was done to it, because an ink's conductivity is not a
-- property of the ink alone (see spec section 2.1).
CREATE TABLE IF NOT EXISTS ink_properties (
    id BIGSERIAL PRIMARY KEY,
    ink TEXT NOT NULL,                  -- 'ACI SC1502'
    process_state TEXT NOT NULL,        -- 'as-printed' | 'cured-120C-10min' | ...
    property TEXT NOT NULL,             -- 'volume_resistivity_ohm_m'
    value DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL,
    qualifier TEXT,
    provenance TEXT NOT NULL,
    citation TEXT,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ink_properties_ink_property_idx
ON ink_properties (ink, property);
```

### 4.2 Seed rows

| ink | process_state | property | value | provenance | citation |
|---|---|---|---|---|---|
| ACI SS1109 silver | cured (datasheet) | `volume_resistivity_ohm_m` | < 4.5×10⁻⁷ | `MANUFACTURER-SPECIFIED` | SS1109 Rev 4 |
| ACI SS1109 silver | cured (datasheet) | `recommended_cured_thickness_m` | 10–20 µm | `MANUFACTURER-SPECIFIED` | SS1109 Rev 4 |
| ACI SC1502 carbon | cured (datasheet) | `volume_resistivity_ohm_m` | < 6×10⁻³ | `MANUFACTURER-SPECIFIED` | SC1502 Rev 4 |
| ACI SC1502 carbon | cured (datasheet) | `recommended_cured_thickness_m` | 6–12 µm | `MANUFACTURER-SPECIFIED` | SC1502 Rev 4 |
| ACI SC1502 carbon | cured (datasheet) | `cure_temperature_min_c` | 120 | `MANUFACTURER-SPECIFIED` | SC1502 Rev 4 |
| ACI SI3104 insulator | cured (datasheet) | `recommended_cured_thickness_m` | 9–14 µm/layer, 3 layers | `MANUFACTURER-SPECIFIED` | SI3104 datasheet |
| Printed MXene (Shao) | as-printed, no anneal | `conductivity_s_per_m` | 6.26–6.9×10⁵ | `LITERATURE-SUPPORTED` | **Shao et al. 2022**, DOI 10.1038/s41467-022-30648-2 — *not* Song et al.; see below |

**The attribution on that row is itself a correction.** `RUNNING-LISTS.md` §3 item 35 records
that `docs/mxene-voltera-nova-printability.md` *"attributes its central printability figures
to the wrong paper, about six times"* — the 120 µm line width and the 6,260 → 6,900 S/cm
conductivity are **Shao et al. 2022**, cited throughout that document as "Song et al." A
library row with a `citation` field makes the miscitation a single correctable value rather
than six occurrences in prose, which is one of the concrete arguments for having the library
at all.

The same item carries a second trap the library must not re-import: **MXene's widely-quoted
"3 µm" figure is a line *gap*, not a line *width*.** The achievable width is 120 µm, forty
times larger. They are enforced at different points in a design rule, so
`min_tracewidth_m` and `min_gap_m` must be distinct capabilities and must never be
substituted for one another.

**The MXene row exposes a real gap and the library should say so.** The source gives a
conductivity with **no thickness at all**. So every sheet resistance computed for printed
MXene on this programme has paired a literature conductivity with a machine-spec thickness
from a *different* document — a cross-source pairing, not a measurement. In library terms:
there is no `(MXene ink, as-printed, thickness_per_pass_m)` row, and its absence must be
visible rather than papered over by borrowing the NOVA's number.

**A note on `cure_temperature_min_c` = 120 °C for SC1502.** Cross-referenced against the
machine library, the NOVA's `material_temperature_max_c` = 40 °C means the cure is **not
reachable on the printer** — it needs the separate `cure` stage on a different machine
(an oven), exactly as #108 requires. That cross-check falls straight out of having both
libraries and is invisible with either one alone.

**SI3104 is the live worked example of a library miss, and it is the programme's own
dielectric.** The insulator ink a printed spacer would be made from *"publishes no
permittivity and no loss tangent, at any frequency"*
(`docs/voltera-multilayer-capability.md:30`). So the ink library holds its process rows
(9–14 µm per layer, three layers) while the **Material-property** lookup for its cured film
returns a miss and falls through to a cited Family fallback bracket — which is precisely
[#127](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/127)'s case,
arising not on some hypothetical substrate but on the dielectric this programme would
actually print. Any absorber design using a printed SI3104 spacer is today resting on a
bracket, and the libraries make that visible in the ranked output instead of leaving it
implicit.

---

## 5. The rule that would have prevented four errors: derive, do not store

### 5.1 Sheet resistance is never stored

`R_s` is a **derived** quantity — a function of `(ink conductivity, printed thickness,
frequency)`. Storing it bakes in a formula choice, and the formula has a validity gate.

This is not hypothetical. Analysis on this programme computed printed MXene at
**0.145 Ω/sq** using `R_s = 1/(σt)` at 10 GHz. That is a **thin-film** relation, valid only
well below one skin depth. It is the same error class `docs/RUNNING-LISTS.md` §3 correction 4
exists to stop: *"'MXene behaves as a copper ~85× lossier' is a DC ratio applied at 10 GHz."*

**And the size of the error is itself unresolved, which strengthens rather than weakens the
rule.** §3 item 33 records a live ~1.8× disagreement about MXene's own skin depth: correction
7 puts a 10 µm film at **1.65 δ** (δ ≈ 6.06 µm), where the DC formula is invalid and the
finite-thickness surface impedance gives **0.2198–0.3145 Ω/sq**; map #104's conductor-thickness
correction puts 3δ at ≈33 µm, i.e. δ ≈ 11 µm, which puts the same film at **~0.9 δ**, where
the DC formula is roughly right and thickness is a *linear* lever. Item 33 is explicitly
*"recorded, not resolved"* — it *"needs one stated conductivity at one stated frequency."*

So the right answer for printed MXene at 10 µm is **0.145 Ω/sq or 0.22–0.31 Ω/sq depending on
a conductivity nobody here has measured.** A stored `R_s` would have to silently pick one. A
derivation carrying its `t/δ` gate reports the gate as unsatisfied and names the missing input
— which is the correct behaviour, and it is exactly the row #106 can supply.

*In plain terms: nobody can say what this film's sheet resistance is until someone measures
how well the ink actually conducts. Writing down a single number would hide that; writing down
the recipe makes the missing ingredient obvious.*

So:

> **Store σ and t. Derive `R_s` at the point of use, through a function that carries the
> `t/δ` gate with it and refuses — or flags — outside its validity range.**

A derivation that carries its own gate cannot be misapplied the way a stored number can. This
is the same principle S6 reached for regime labels: *a regime that can be computed should not
be stored.*

*In plain terms: don't write down the answer, write down the ingredients and the recipe — then
the recipe can tell you when it doesn't apply.*

### 5.2 The ±20 µm ambiguity, recorded rather than resolved

`±20 µm` is published as **single-layer positioning accuracy**, which most naturally means
in-plane placement. Two analyses on this programme have borrowed it for **layer height**, and
one of them rested an entire upper frequency bound (~114 GHz) on that borrowing.

The library cannot resolve this — only the bench can. What it can do is make the borrowing
impossible to do silently: the row's `capability` is `positioning_accuracy_m` with qualifier
*"single-layer, in-plane"*, and there is **no** `layer_height_accuracy_m` row. A lookup for
layer-height accuracy returns a miss, and a miss is visible.

---

## 6. Composition with the physics bounds

The physics-bounds work (S6) provides LAW / REGIME / ENVELOPE. These two libraries are pure
ENVELOPE, and they compose with it in one direction only:

- A **law** violation says a material cannot exist.
- A **regime** gate says the formula you used is outside its validity — §5.1's `t/δ` gate is
  exactly one of these.
- An **envelope** miss says *nothing you own can make this today*, which per
  [#127](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/127) and
  [#108](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/108) is
  **reported, never a rejection**: the candidate stays in the ranked output, marked *excluded
  from selection today, reason stated*.

That last point is what keeps the loop honest about hypothetical materials. "No ink in the
library reaches 400 Ω/sq at a printable thickness" is a **procurement finding**, an output of
the loop — not a pruning rule, and not a reason a candidate disappears.

---

## 7. Why this is urgent: #106 has nowhere to put its results

[#106](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/106) (process
characterisation) is running now, and it produces exactly these rows: layer height, film
thickness, trace width, sheet resistance on a printed coupon, measured with a microscope,
profilometer and four-point probe.

Those are among the very few things this programme can legitimately tag **`MEASURED`** —
#133 settled that the RF-response ceiling is `SIMULATED`, but *"geometry, thickness and sheet
resistance are measurable … those are the simulation's inputs, and measuring them is a genuine
upgrade."*

With no library, #106's output lands in a prose document and rots. That is precisely the
failure `CLAUDE.md`'s preamble records having shipped three times.

A measured row also **supersedes nothing** — it accumulates alongside the
`MANUFACTURER-SPECIFIED` one, and the disagreement between them is the finding. That is
ADR-0015's discipline applied unchanged: three FR4 papers disagreeing by up to 25 % on tan δ
are kept, not averaged.

---

## 8. Acceptance test

Not "does the interface look general." The test is:

1. Add a second machine — any DIW system with a different feature floor and thickness range.
2. Add a second conductive ink at a different resistivity.
3. Re-run the candidate enumeration.

**Pass:** the candidate set and the ranked output change, and no Python constant needed
editing.

**Fail:** anything still reads a NOVA or ACI number that is not a library row — including
prose in a doc that a later session will quote as though it were general.

A companion sweep should grep for the six figures in §1.1 and confirm each now resolves
through a library lookup.

---

## 9. The fourth thing: the host surface

Printer, dryer and laminator are covered above — they are the three `process_stage` values of
one **Fabrication capability**, and the concept already exists at `CONTEXT.md:181`. The
**host surface** was the fourth, and until this change it was not a defined term at all.

**`CONTEXT.md` now defines it** (entry: *Host surface*), because the gap was real: it was
referenced by six places, each taking a different slice, with no definition anywhere:

| Where | Which slice |
|---|---|
| `CONTEXT.md:107-108` | curvature, platform, and *"whether the host surface is asserted to be a reliable conductive backing"* |
| `CONTEXT.md:190` | the cure gate — *"whether the finished part can leave its host and reach an external oven"* |
| `CONTEXT.md:383-384` | design-family spine fields — *"host thickness, host εr/tanδ"* |
| ADR-0017 | whether the host is a ground plane — asserted, never assumed |
| `rf_tools/calculations.py:706` | `curvature_length_correction_factor(l_m, radius_of_curvature_m)` |
| `geometry/freecad_curved.py` | exists, and #104 records it as unwired |

**Six slices and no definition is the signature of a missing domain object.**

### 9.1 It is an input to all three fabrication stages, not just to geometry

This is the part that makes it belong in *this* spec rather than a purely electromagnetic one:

- **print** — can the equipment reach the host *in situ*? #105 settled that MXene's decisive
  advantage is *"in-situ printing on a host that cannot be oven-baked"* — a statement about
  the host, deciding a material.
- **cure** — `CONTEXT.md:190`'s gate is the host's, in its own words: can the part *leave*
  it. A wing cannot go in an oven.
- **laminate** — `CONTEXT.md:194` says bonding *"onto the final host."*

So the host gates every stage, and #104's causal chain runs through it entirely: *"Its radius
of curvature drives bend radius, which drives substrate class, which drives which conductors
survive the cure ceiling."* Radius of curvature is a geometric fact that ends up selecting a
**conductor**.

### 9.2 The split mirrors material exactly

#105 settled that **material is a variable; material properties are the constant.** The same
split applies here and resolves what would otherwise be a contradiction with #104's
no-inheritance rule:

- **The specific host in a requirement** — *this* customer's wing — is a **per-requirement
  input**, re-derived every pass, never inherited. #104: *"The host surface is a
  per-requirement input, never a project constant."*
- **Host-class properties** — a CFRP skin's temperature limit, a steel hull's conductivity, a
  polymer sUAS body's stiffness — are **facts that accumulate**, library-shaped, exactly like
  material properties.

Those are two different objects and the tree currently has neither.

### 9.3 What is settled, and what is not

**Settled: the term.** `CONTEXT.md` now carries *Host surface*, defined by the properties it
carries rather than by what it is — because the range is unbounded. A sticker, a PET film, a
wing, a hull, an sUAS body, or something living: `docs/mxene-voltera-nova-printability.md:71`
records printing demonstrated *"on curved substrates and even on leaves and fruit."* **No
closed list of host types is possible, so no design decision may key on one** — which is the
same discipline #105 applies to material, one level out.

**Settled: the candidate is a quadruple, not a triple.** The cure stage cannot be evaluated
without the host, because its gate is *defined* in terms of the host. So the enumerated
candidate is at least **`(host, machine, ink, material)`**, and an implementation stopping at
the triple will have to be reopened.

**Settled: the host does NOT get a fourth library.** A host's material properties *are*
material properties, so they belong in the Material-property library that already exists —
and that catalogue is already begun. `docs/xband-absorber-substrate-shortlist.md` §1 holds
twelve entries with εr, tan δ and provenance, starting with **Silicone sheet 60 ShA at
εr 2.9 / tan δ 0.10, `MEASURED`**, and running through polyimide, LCP, PDMS, PET, TPU, two
textiles, FR4, RO4350B and fused silica. It already carries a **Host regime** column — A for
large-radius hosts (wing, hull, sUAS body), B for *"anything that cannot leave the airframe
for an oven"* — which is `CONTEXT.md`'s cure gate under another name.

So the split is clean and needs no new table:

- **Host material properties** → the existing Material-property library. A CFRP skin, a PET
  film, a silicone sheet and animal tissue are all just materials with properties.
- **Host instance facts** — this host's radius of curvature, its extent, whether *this* part
  can leave it for an oven, whether the requirement asserts it as a conductive backing →
  **per-requirement input**, re-derived each pass and never inherited, per #104.

### 9.4 Three wrinkles the migration will hit

The shortlist is library-shaped data living in a markdown table, so migrating it is the
obvious first population of the Material-property library beyond its FR4 seeds. Three things
will not fit cleanly, and it is cheaper to know now:

1. **Not every column is frequency-keyed.** εr and tan δ are. **Cure-temperature ceiling,
   minimum bend radius and thickness range are not** — they are mechanical and process facts
   that do not vary with frequency. The library's `(material, property, frequency band)` key
   can carry them only by convention (a band spanning everything), which is a modelling
   decision someone should take deliberately rather than by accident.
2. **Adhesion is a property of a PAIR, and nothing can hold it.** §5 of the shortlist
   tabulates adhesion as *silver-on-X* and *MXene-on-X* — two columns, because adhesion is a
   fact about an `(ink, substrate)` pair, not about either alone. The Material-property
   library is keyed by one material; the Ink-property library proposed above is keyed by
   `(ink, process_state, property)` with no substrate axis. **Neither shape holds a pair
   property**, and adhesion is decisive: the shortlist records MXene-on-TPU adhesion as
   `UNKNOWN` and textile adhesion as a *"literature's finding is negative."*
3. **A host class is not a material.** "Textile" and "glass/ceramic" are families, not
   substances, and the shortlist lists denim and felt separately for exactly that reason. That
   is what the **Family fallback bracket** already exists for, so the mechanism is in place —
   but the migration must decide per row whether it is entering a material or a family.

No ADR is proposed for the glossary term — defining a term is cheap to reverse and involved no
real trade-off. The pair-property gap in wrinkle 2 may warrant one, since it changes a table's
shape.

---

## 10. What this spec deliberately does not do

- **It does not build the Element/Coding-Alphabet library.** That is #109's, already specified
  in `CONTEXT.md:382` and equally unbuilt, and it has a different key
  `(element family, substrate stack, band, incidence-angle range)`. Named here only so the
  count of unbuilt libraries is honest: three, not two.
- **It does not resolve the ±20 µm layer-height question** (§5.2). It makes the ambiguity
  visible and hands it to the bench.
- **It does not populate a second machine.** Seeding a real second row is implementation work
  and is the acceptance test, not the spec.
- **It does not change the Material-property library.** The `(material, frequency, property)`
  key is right and stays.
- **It does not decide whether a cured film's RF properties are auto-derived** from an ink row
  plus a machine row, or entered as their own material row. See §10.

---

## 11. Open questions for a human

1. **Does a cured film get an automatic Material-property row?** When SC1502 is printed at
   15.9 µm and cured, is "SC1502 cured film" a material in its own right with its own
   frequency-keyed entries, or is it always recomposed on demand from ink σ + machine t? The
   derive-don't-store rule (§5.1) argues for recomposition; the accumulate-measurements
   discipline argues that a *measured* cured film deserves its own row. These conflict.
2. **What is the `process_state` vocabulary?** `'as-printed'` and `'cured-120C-10min'` are
   sketches. A free-text field will drift; a closed enum will not survive a second machine.
3. **Does a machine row need a validity date?** A firmware or nozzle revision changes a
   feature floor. `created_at` records when the row was entered, not when the fact held.
4. **Should `#108`'s configured-fabrication decision now get an ADR?** It is load-bearing for
   this spec and currently lives only in an issue comment.

---

## 12. Corrections this spec records

Candidates for `docs/RUNNING-LISTS.md` §3 (which on current `main` runs to item 39). Two are
new to the repo; the rest are cautions about analysis done *for* this spec, kept because the
erroneous versions reached a committed document before being caught.

**New to the repo:**

1. **`rf_tools/calculations.py:540-541`** raises *"Substrate dielectric constant eps_r must be
   > 1"* — a false physical claim stated as one, on a live path from the Material-property
   library (`orchestration/design_loop.py:485-494` → `patch_effective_permittivity`). The
   guard is correct: Hammerstad's fit at `:551` interpolates between `eps_r` and 1 and is
   meaningless below it. Only the message is wrong, and the same file names a formula's
   validity correctly eight lines below (*"only valid for W/h > 1"*). **Name the formula, not
   the material.**
2. **`docs/requirement-derived-thresholds.md:128`** claims *"The Python does not currently
   hardcode thresholds."* The tree hardcodes roughly 25 bounds — in the one document whose
   purpose is stopping an unexamined constant from doing a requirement's work.

**Cautions from this spec's own analysis, and one outright error:**

3. **A verification pass reported that §3 ended at item 29 and that item 33 did not exist.
   Both were false, and the cause is instructive.** The working clone was cut from `e626857`,
   before PR #192 merged; on `main` §3 runs to 39 and **item 33 is precisely the ~1.8 × MXene
   skin-depth disagreement the pass reported as non-existent.** Issue #104's body had been
   right all along, and was overruled on the strength of a stale checkout.
   **Five agents independently "verified" the absence against the same stale tree.**
   Independent verification is worth nothing when every verifier reads the same stale
   artifact — so a claim of the form *"X is not in the repo"* must state the commit it was
   checked at, and be re-checked against `origin/main` before it is recorded.
   *In plain terms: five people checking the same out-of-date copy is one check, not five.*
4. **A prior analysis concluded the programme owned no ink in the 377–435 Ω/sq window.** It
   does: §3 item 7 already records ACI SC1502 carbon reaching 377 Ω/sq at 15.9 µm, about two
   passes. Not a new correction — a caution that an analysis re-derived, and then contradicted,
   a fact already written down. The Salisbury screen is still ruled out at X-band, but by the
   **quarter-wave spacer** (4.553 mm in TPU at 10 GHz, 2.28× the 0.87–2.0 mm budget), never by
   the ink.
5. **`R_s = 1/(σt)` was applied to printed MXene at 10 GHz without checking `t/δ`** (§5.1). The
   corrected value depends on which side of item 33's unresolved disagreement is right, so the
   honest answer is a range across two regimes, not a replacement number.
6. **A DC conductivity ratio was used for an RF comparison, the same error class as item 4.**
   MXene is **1.79×** closer to a free-space match than ACI SS1109 silver, not 3× — above ~3
   skin depths surface resistance goes as 1/√σ, and 1.794 = √(2.22×10⁶ / 6.9×10⁵) exactly.
   Carries item 33's caveat: it assumes the 6.9×10⁵ S/m figure.
7. **Nanometre thicknesses computed from bulk conductivity are lower bounds, not predictions.**
   Fuchs–Sondheimer surface scattering plus grain-boundary scattering drop σ_film 1.7–3.0×
   below bulk at 5–10 nm, and further for a 2-D-flake film.
