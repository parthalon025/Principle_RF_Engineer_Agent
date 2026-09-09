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
