---
status: accepted
---

# An absorber's loss lives in the printed pattern, split across two inks by function

Issue [#128](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/128)
("Put the absorber's loss in the printed pattern, not the substrate") asked
where an absorber's dissipation should come from: the substrate's own loss
tangent — a fixed material property inherited the moment a substrate is
picked, invisible to the optimiser — or the printed conductor pattern itself,
which is geometry, exactly what the loop searches. A prototype (PR #186,
driveable copy at the linked artifact) built a scaled two-layer cell with
real dimensions to answer it, and issue #190 later supplied a missing term
(Costa's thin-spacer capacitance correction) that the prototype's own model
was missing at its operating point.

**Decision: loss lives in the printed pattern, and the pattern must split
the job across two different-function inks in one coplanar layer.** A
well-conducting ink (silver or MXene) forms the capacitive/resonant
plates and carries essentially no loss; a separate, genuinely resistive
ink (carbon) forms a short, wide bridge that does the damping. One printed
element cannot supply both jobs inside the patent's ≤2 mm skin — reusing
Example 3's own I-shaped ring resonator in carbon over-damps it by roughly
two orders of magnitude (≈6.7 kΩ/sq against the ≈11–90 Ω/sq a thin resonant
cell actually wants).

**The lossy bridge is tuned by aspect ratio, not by ink thickness.** What
the wave sees is not a film's sheet resistance alone but that sheet
resistance multiplied by how many square tiles long the current path is —
a narrow ring multiplies it, a short wide bridge divides it. Thickness is a
dead knob at both ends of the ink list Voltera sells: silver and MXene are
several skin depths thick at any printable film and sit at ~0.1–0.25 Ω/sq
regardless of pass count; carbon is deep in the thin-film linear regime
(~0.04 skin depths at 10 GHz) but even its full printable thickness range
(6–24 µm, one to two passes) only spans 250–1000 Ω/sq — never close to the
11–90 Ω/sq window. Element aspect ratio spans three orders of magnitude and
reaches down into that window; ink thickness does not.

**The reflector stays unpatterned**, per ADR-0017's existing default, so
front-to-back layer registration — unmeasured and unpublished on the NOVA —
never sits on this stack's critical path.

## Considered and rejected

- **A resistive sheet at classic Salisbury quarter-wave spacing (~377
  Ω/sq).** Rejected outright: quarter-wave at 10 GHz needs ≈4.3–7.5 mm of
  standoff, and the patent's entire skin is 0.87–2.0 mm. 377 Ω/sq answers
  that question, not this one.
- **One lossy element doing both capacitance and damping.** Rejected —
  Example 3's own I-shape in carbon gives ~13.3 squares in the current path,
  turning 500 Ω/sq carbon into ~6.7 kΩ/sq: ~85× over-damped, predicting
  ~6% absorption instead of the ~100% a matched cell gives.
- **Tuning loss by ink thickness alone.** Rejected — every printable
  thickness for every ink Voltera sells lands either far below (silver,
  MXene) or far above (carbon) the 11–90 Ω/sq the cell wants; thickness
  offers less than a decade of adjustment where three orders of magnitude
  are needed.
- **Leave the substrate's loss tangent as the loss mechanism** (the
  premise #114 had been ranking substrates on). Rejected as the primary
  mechanism, though not zero: with Costa's thin-spacer term included, a
  lossy substrate (silicone, tanδ 0.10) still supplies 20–36% of the total
  dissipation at this design point, so substrate loss tangent remains a
  real, secondary contributor worth carrying — just not the mechanism
  the optimiser should rely on to hit a target.

## Consequences

- The absorber family's Tier B optimiser gains a genuinely searchable loss
  variable: the lossy element's aspect ratio (current-path length in sheet
  squares), not per-layer ink thickness and not substrate selection.
- This partly reverses #114's substrate ranking. Loss tangent stops being
  the deciding factor — silicone's tanδ 0.10 buys at most a third of the
  budget, not the primary mechanism — so substrate is chosen on bending,
  temperature, adhesion and cost, with loss tangent as a secondary,
  quantifiable bonus.
- Requires **coplanar two-ink printing on one layer** — a nozzle change,
  governed by the ±20 µm single-layer positioning figure rather than the
  unpublished layer-to-layer registration figure, but undocumented on the
  NOVA today. Tracked as bench work on #106 and #189.
- The recommended cell for the Example-3-anchor reproduction, corrected for
  Costa's thin-spacer term (#190):

  | Layer | Material | Thickness | Passes |
  |---|---|---|---|
  | Resonant + lossy | ACI SS1109 silver plates + one ACI SC1502 carbon bridge, coplanar | 12 µm | 1 |
  | Spacer | Silicone 60 ShA (or Kapton / RO4350B / LCP) — stock sheet, not printed | 1.50 mm | — |
  | Reflector | ACI SS1109 silver, unpatterned | 15 µm | 1–2 |

  Period 6.0 mm (0.20 λ₀), gap ~~0.498 mm~~ **≈0.53 mm** (widened per
  Costa's correction, conservative `ε₀` prefactor; up to ≈0.57 mm under the
  `ε₀ε_r` prefactor, open on #234), carbon bridge 0.245 × 4.0 mm
  (untouched by the correction — only the capacitive gap moves). Predicted
  ≥90% absorption from 9.1–11.3 GHz around a ~9.9–10.0 GHz centre once the
  gap is retuned; the correction moves the design *away* from the 0.2 mm
  feature floor, not toward it.
- This is a plan-only decision (#104's map is explicitly plan-only); no
  code changes accompany it. Implementation lands as a separate
  `ready-for-agent` issue once the design-loop spec exists.
- Full working notes: `geometry/PROTOTYPE-lossy-cell-fit.md` (PR #186,
  kept as a reference asset, never merged) and
  `docs/costa-thin-spacer-correction.md`.

## Corrections

### 2026-09-10 — the reachable sheet-resistance space is wider than the ink catalogue, and three smaller errors

**The Decision stands, and nothing below moves it.** *"Loss lives in the
printed pattern, and the pattern must split the job across two
different-function inks in one coplanar layer"* survives every finding
here: the resonant plates still need ~0.1–0.25 Ω/sq to stay lossless, so
even a 32.5 Ω/sq formulated ink cannot serve them, and the two-ink split
is untouched. **The lossy bridge is still tuned by aspect ratio, not by
ink thickness.** Only the reasoning moved.

*In plain terms: how to build the thing is unchanged. Four of the
arguments used to get there needed fixing, and one sibling document has
raised a question about the recommended cell that nobody has answered
yet.* Five items, in descending order of how much they matter.

---

#### (a) The rejected-alternatives list rejects *thickness* and is silent on *formulation*

**What this ADR said:**

> - **Tuning loss by ink thickness alone.** Rejected — every printable
>   thickness for every ink Voltera sells lands either far below (silver,
>   MXene) or far above (carbon) the 11–90 Ω/sq the cell wants; thickness
>   offers less than a decade of adjustment where three orders of
>   magnitude are needed.

**Why that was wrong.** Not about thickness — about what the sentence
licenses. It steps from **an enumeration of the ink catalogue** to **a
claim about the reachable sheet-resistance space**, and that step is
defended nowhere in this ADR. Which inks a vendor stocks is a fact about
a catalogue; which sheet resistances are printable is a fact about
chemistry. *In plain terms: "none of the three inks on the shelf lands in
the window" is not the same statement as "no ink can land in the window",
and the ADR used the first to conclude the second.*

**What is true instead.** **Li et al., *ACS Applied Materials &
Interfaces* 16(32):42448 (2024), [DOI 10.1021/acsami.4c07084](https://doi.org/10.1021/acsami.4c07084)**
report a screen-printed, low-concentration (~46 mg/mL) MXene–PEDOT:PSS
ink whose square resistance is **tunable across 5–32.5 Ω/sq**, used in an
absorber spanning 4.4–20 GHz. Formulation is therefore a third knob
alongside thickness and aspect ratio, and this ADR did not consider it.

Stated precisely, because the overlap is partial and it would be easy to
oversell: the ink's 5–32.5 Ω/sq range meets this cell's 11–90 Ω/sq window
over **11–32.5 Ω/sq — the bottom quarter of the window** (21.5 Ω/sq of a
79 Ω/sq span, 27%), **not "squarely inside" it**; the 5–11 Ω/sq part of
the ink's range falls *below* the window. What matters is that it reaches
**31 Ω/sq**, which is exactly the value this ADR's own recommended
1.50 mm silicone cell asks of its carbon bridge
(`geometry/PROTOTYPE-lossy-cell-fit.md:108`: a 0.245 × 4.0 mm bridge is
0.06 squares, turning 500 Ω/sq carbon into 31 Ω/sq).

**The fifth rejected-alternative entry this list should have carried.**
Recorded here rather than inserted silently above, so it is visible as a
later addition. Its operative text:

> - **Tuning loss by ink formulation.** **Not considered at the time** —
>   this is the omission, not a rejection. Now a live candidate: a
>   formulated resistive ink reported at 5–32.5 Ω/sq reaches the bottom
>   quarter of the window directly. It carries **two Capability
>   warnings** and is **reported, never dropped**: (i) it is
>   **screen-printed**, and screen printing is not the configured
>   fabrication route — ADR-0043 §2 records that *"today's configuration
>   has exactly one entry: the Voltera NOVA, DIW printing only"*; (ii) a
>   ~46 mg/mL **low-concentration** ink may sit **below the NOVA's
>   1,000 cP viscosity floor** — the closest comparable additive-free
>   extrusion MXene ink in this literature is 0.71 Pa·s = **710 cP**
>   (recorded on [#448](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/448)),
>   already under it. *Read the second warning narrowly*: it is about
>   *this* dilute formulation, not about MXene generally —
>   `docs/mxene-voltera-nova-printability.md` §1 records an
>   extrusion-formulated MXene ink at ~2.5×10² Pa·s ≈ 250,000 cP that
>   *"sits squarely inside the NOVA's 1,000–1,000,000 cP window"*.

Both warnings are equipment and inventory facts, so under ADR-0028
(*"the program warns and proceeds"*), ADR-0025's 2026-09-09 correction and
this repo's Capability-warning mechanism (ADR-0030), they shape the
**ranking** and the **warnings** and never the **search**. A candidate
needing an ink nobody stocks and a press nobody owns is still returned,
scored, and labelled. *In plain terms: "we can't make it here today" is
something to tell the reader, not a reason to hide the option.*

**Provenance: `UNVERIFIED`, pending the primary paper**, which nobody
here has read first-hand. Attachment-level material does not say whether
the 4.4–20 GHz band was **measured on a fixture or predicted by the
deep-learning inverse-design model** the work credits, and gives no film
thickness — so no conductivity can be extracted from it, and the
5–32.5 Ω/sq figure cannot be independently re-derived.

**The supersede trigger, named so nobody has to guess.** A four-point-probe
reading inside **11–90 Ω/sq on a NOVA-printed resistive formulation**
would make *"the pattern must split the job across two different-function
inks"* **false**. That is a changed Decision, so it requires a **new ADR**
under ADR-0020, not another amendment. Nothing short of that — including
reading Li et al. in full — reaches the Decision.

**One unusual fact worth recording: the DC probe is legitimate here.**
`CALCULATED`. At 5–32.5 Ω/sq and t ≤ 10 µm, `σ = 1/(R_s·t)` gives
20,000 S/m down to 3,077 S/m, so `δ = 1/√(π f µ₀ σ)` at 10 GHz is
35.6 µm to 90.7 µm and **t/δ ≤ 0.281**. Evaluating the exact
finite-thickness surface impedance `Z_s = (1/σt)·u·coth u` with
`u = (1+j)t/δ` at that worst corner gives a real part **1.00055 ×** the
DC value — so `R_s = 1/(σt)` is exact and **a four-point-probe reading
*is* the X-band sheet resistance to well under 1%**. This is the rare case
where the bench instrument #106 already has answers an RF question
directly. *In plain terms: the film is so thin compared with how far a
10 GHz wave penetrates that the wave sees all of it, exactly as a DC
current does — so a cheap meter gives the radio answer.* **Caveat, and it
is not small:** this covers **classical skin effect only**, not any
frequency dependence of σ itself. GHz shunting of inter-flake contact
resistance could put the true RF value **below** the DC one by an
unquantified margin.

**Raised by:** [#448](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/448)
("Is ink formulation a third loss knob, alongside thickness and aspect
ratio?").

---

#### (b) "Several skin depths" overstates by about an order — for MXene, not for silver

**What this ADR said:**

> silver and MXene are several skin depths thick at any printable film and
> sit at ~0.1–0.25 Ω/sq regardless of pass count

**Why that was wrong.** `CALCULATED`, from `δ = 1/√(π f µ₀ σ)`. At the
best-evidenced as-printed extrusion conductivity for MXene,
**σ = 6.9×10⁵ S/m** (`docs/mxene-voltera-nova-printability.md` §4),
δ = **6.06 µm** at 10 GHz, so a 10 µm film is **1.65 skin depths**. Across
X-band (8–12 GHz) and the reported σ range 6.26–6.9×10⁵ S/m the figure
runs **1.41–1.81 δ**. That is *one to two* skin depths, not "several" —
an overstatement of roughly an order of magnitude in the wrong direction,
since "several" implies the ≳3δ opaque regime.

The claim is right for **silver** and wrong for **MXene**, and the
sentence bundles them. `docs/voltera-multilayer-capability.md:485-486`
records **SS1109 silver at its recommended 10–20 µm as 3.0–5.9 skin
depths** — genuinely "several". MXene is not there at printable
thickness.

**What is true instead.** The conclusion is unaffected. At 10 µm the
finite-thickness surface impedance gives **0.22–0.31 Ω/sq** and the
thin-film form gives 0.145 Ω/sq
(`docs/fabrication-capability-and-ink-library-spec.md:311-316`); silver
sits at ~0.13 Ω/sq. Every one of those is **two orders below** the
11 Ω/sq floor of the window, so no printable metal-class ink reaches it
and the two-ink split stands either way. *(A second-order note on the same
sentence: its stated "~0.1–0.25 Ω/sq" band is the thin-film figure, and
the finite-thickness calculation runs to 0.31 Ω/sq — outside the quoted
band, and still two orders below the window.)*

**Why the wording matters even though the number does not.** As written it
**conflicts with two live records**. Issue #104's wayfinder map states
*"MXene never reaches that regime at printable thickness"* — "that regime"
being ≳3δ — which is compatible with 1.65 δ and flatly incompatible with
"several". And `docs/RUNNING-LISTS.md` §3 item 33 records a **still-open
~1.8× disagreement about MXene's own skin depth**: correction 7's 1.65 δ
against the map's 3δ ≈ 33 µm (δ ≈ 11 µm, putting the same film at ~0.9 δ),
*"recorded, not resolved"* pending *"one stated conductivity at one stated
frequency"*. **Both** readings of that open item put MXene below "several
skin depths"; this ADR's wording sits outside the disagreement rather than
on either side of it.

**Raised by:** this research pass, against
`docs/RUNNING-LISTS.md` §3 item 33 and #104's conductor-thickness bullet.

---

#### (c) The stated carbon span contradicts the ADR's own working notes, and "never close" overstates the gap

**What this ADR said:**

> even its full printable thickness range (6–24 µm, one to two passes)
> only spans 250–1000 Ω/sq — never close to the 11–90 Ω/sq window.

**Against `geometry/PROTOTYPE-lossy-cell-fit.md:110`, the ADR's own cited
working notes:**

> Carbon's thickness knob spans 8:1 (1000 → 125 Ω/sq) and every value on it
> is too high.

**Why that was wrong — and which of the two is.** Both were verified
verbatim, and both cannot be right. `R_s = ρ/t` is linear, so a **6→24 µm**
thickness range is a **4:1** ratio and spans **1000 → 250 Ω/sq**. An 8:1
span reaching **125 Ω/sq** requires **48 µm** — four passes — which is
beyond the ink's only pass-count language on record:
`docs/voltera-multilayer-capability.md:441` quotes the SC1502 datasheet as
*"double print wet on wet or dry can be used to increase deposition
thickness"*, i.e. two passes, i.e. 24 µm.

**The 250 Ω/sq figure is the better-sourced one and the ADR is right**;
the prototype note is the orphan. It is corroborated by
`docs/voltera-multilayer-capability.md:495-502`'s thickness table
(6 µm → 1000 Ω/sq … 24 µm → 250 Ω/sq) and by the prototype's *own* table
22 lines above the offending sentence
(`geometry/PROTOTYPE-lossy-cell-fit.md:88`: *"ACI SC1502 carbon, 24 µm
(2 passes, datasheet max) | 250 Ω/sq"*). Note that the 8:1 figure has
already propagated: #104's map repeats *"Carbon's printable thickness
spans 8:1"*, inheriting it from the same note.

**What is true instead, second part: drop "never close".** 250 Ω/sq
against the window's 90 Ω/sq top edge is a factor of **2.78** — a miss
under three-fold, not a miss by inspection. At the prototype's own
(unsupported) 125 Ω/sq endpoint it would be **1.39**. *In plain terms: the
cheapest carbon film the machine can print is about two and three-quarter
times too resistive for this cell — genuinely too resistive, but close
enough that someone should have checked whether a thicker film or a
different formulation closes it, which is exactly what item (a) turns
out to be about.* The conclusion is unchanged — a 2.8× miss is still a
miss, and aspect ratio remains the lever that reaches — but "never close"
is the kind of phrasing that stops the next reader re-checking.

**Raised by:** this research pass.

---

#### (d) One factual error: Voltera does not sell an MXene ink

**What this ADR said:**

> Thickness is a dead knob at both ends of the ink list Voltera sells:
> silver and MXene are several skin depths thick at any printable film …

**Why that was wrong.** MXene is not on that list.
`docs/mxene-voltera-nova-printability.md` §6 (line 65) records:
*"**Nothing found.** Voltera's own NOVA product page lists named
compatible inks (Creative Materials EXP 2613-40 gold ink, Celanese
Micromax/Intexar PE874 stretchable silver paste, generic carbon/silver/copper
inks) … No paper found names Voltera V-One or NOVA in connection with
MXene. This combination appears to be genuinely unpublished."* **Voltera
sells no MXene ink, and nobody has printed MXene on a NOVA.** The MXene
leg of that ink list is a one-paper extrapolation from Shao et al.,
*Nat. Commun.* **13**:3223 (2022), printed on a different machine (a
programmable three-axis pneumatic extrusion dispenser). MXene also has no
row in the shipped material-property seed data — `designs/material_properties.py`
and `designs/material_families.py` name SS1109 silver, SC1502 carbon,
Intexar PE874 and the substrate set, and no MXene.

**What is true instead — and what it does *not* mean.** This is a
**labelling** error, not a disqualification. Under ADR-0028, ADR-0025's
2026-09-09 split and ADR-0027's own 2026-09-10 correction, an ink the shop
does not stock and a machine nobody has proved is a **Capability warning
attached to a candidate that is still returned and scored**, never a
reason to drop it; and ADR-0044 keeps MXene a candidate scored on merit
with no thumb on the scale in either direction. The correct reading of the
sentence is therefore: *silver is a stocked ink whose thickness knob is
dead by measurement; MXene is an unstocked, un-demonstrated ink whose
thickness knob is dead by a one-paper extrapolation.* Same conclusion for
the Decision, different confidence, and the difference must be visible to
whoever reads it.

**Raised by:** this research pass, against
`docs/mxene-voltera-nova-printability.md` §6.

---

#### (e) An open question — not a correction — about the recommended cell's centre frequency

This one is **recorded as unresolved**, because the evidence sits right at
the edge of its own stated uncertainty and does not support a correction.

`docs/encapsulation-em-coupling.md`, merged since this ADR was written,
solves this ADR's as-drawn **0.53 mm gap** from Costa's `X = −B` resonance
condition and reports:

> ADR-0033's as-drawn 0.53 mm gap resonates at 9.58 GHz in this lossless
> solve, not the "~9.9–10.0 GHz centre" the ADR reports

`CALCULATED`, against this ADR's stated ~9.9–10.0 GHz and #190's
Costa-corrected **9.893 GHz** (`docs/costa-thin-spacer-correction.md:435`),
the gap is **3.2%** (3.16% against 9.893 GHz, 3.23% against the 9.9 GHz
lower edge, 4.20% against the 10.0 GHz upper edge).

**Why this is suggestive and not conclusive.** Two reasons, and both are
in the source document itself.

1. It states its own bound: *"Absolute frequencies here are therefore
   worth about ±3%; the fractional shifts are not, and fractional shifts
   are what this document reports."* A 3.2% discrepancy against a ±3%
   figure is **at the edge**, not beyond it.
2. It offers its own explanation, which would dissolve the discrepancy
   entirely: this ADR's figure *"comes from the full absorptivity model in
   the #186 prototype, which carries the resistive bridge and the losses,
   and is a different quantity from a lossless reactance crossing."* A
   lossy resonator's absorption peak and a lossless network's reactance
   zero are not the same number, and are not required to agree.

*In plain terms: two different calculations of "where this cell resonates"
disagree by about three percent. One of them says up front that it is only
good to about three percent, and also says the two are not measuring quite
the same thing. That is a reason to check, not a reason to change the
number.*

**What would settle it.** A **Floquet solve on the actual cell** — the
same quantity, computed once by a full-wave method instead of twice by two
different circuit models. #104's map lists that capability as
**unspecified**: *"What SIMULATION and VERIFICATION look like for a unit
cell — Floquet port setup, mesh, convergence"* is still an open patch, and
`docs/meep-absorber-validation.md` scopes today's validated `SIMULATED`
claim explicitly as *"not a patterned unit cell"*. So this cannot be
closed today, which is why it is filed as an open question against the
recommended cell rather than left as a silent disagreement between two
documents.

**Raised by:** `docs/encapsulation-em-coupling.md` §3.

---

**All five are amendments, not a supersede** (ADR-0020). The Decision
paragraph is unchanged and is not in dispute: (a) adds a knob the list
omitted without reaching the two-ink split, (b), (c) and (d) fix wording
and sourcing behind a conclusion that survives each fix, and (e) is an
open question with no finding attached. The one thing that *would*
supersede this ADR is named under (a).
