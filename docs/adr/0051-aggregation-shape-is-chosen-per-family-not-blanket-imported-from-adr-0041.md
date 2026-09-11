---
status: accepted
---

# Reflection-phase and RCS-type criteria score worst-in-band minimax; aperture-synthesis criteria score a direct coherent array-factor computation instead; the physical-bound table gains Example 1 and a new transmissive-surface family

Issue [#467](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/467) ("How do the other six patent examples get charted?"), a line item on the
#104 wayfinder map ("Printed metamaterial EM skin design loop"), closes the
first "Not yet specified" entry: Example 3 (the absorber) already had a
scoring recipe via #110/ADR-0041; Examples 1, 2, 4, 5, 6 and 7 did not. Each
now has a primary objective, a default for customer silence, and a
physical_bound assignment (or a confirmed absence of one), recorded in full in
`docs/example1-2-scoring-recipe.md`, `docs/example4-5-beam-steering-scoring-recipe.md`,
`docs/example6-polarization-scoring-recipe.md` and
`docs/example7-coding-metasurface-scoring-recipe.md`. This ADR records the two
decisions that generalize across all six and are load-bearing for how a future
example gets charted, plus the specific additions to #129/ADR-0047's
physical_bound table.

## Decision

**1. The aggregation-shape question is re-asked per family, not blanket-imported from ADR-0041 — and it splits the six examples into two genuinely different shapes.**

ADR-0041 adopted worst-in-band minimax for the absorber (Example 3) because
the requirement is itself a "must hold everywhere in-band" compliance bar, and
Yiğit & Duysak (2021) argue explicitly against averaging for exactly that
reason. That reasoning does not automatically transfer to every family that
happens to sweep a quantity across frequency — it transfers only where the
*physical shape* of the requirement is the same.

- **Shape A — a compliance bar (Examples 1, 2, 6, 7): worst-in-band minimax,
  direct extension of ADR-0041.** Reflection phase (Example 1: `max_f |∠Γ(f)|`),
  impedance mismatch (Example 2: `max_f |Γ_eff(f)|`), axial ratio (Example 6:
  `max_f AR(f,θ)` per tested angle), and RCS reduction (Example 7:
  `min_f RCS_reduction_dB(f)`) are each a single quantity swept along one axis
  where the field's own reporting convention is already a threshold-everywhere
  statement — Gustafsson & Sjöberg's own `|Y(λ)|≤∆` **for all** `λ` in the
  band (verified firsthand, primary text), "3 dB axial-ratio bandwidth"
  (universal definitional convention, independently checked across multiple
  sources), and "at least 10 dB RCS reduction" (four independent sources,
  reproduced by #130's own `δ_budget` formula). Evidentiary strength is stated
  per example, not uniformly: strongest for Examples 1 and 6 (the field's own
  bandwidth *definitions* are minimax-shaped, not merely analogous to one),
  weaker for Example 7 (a structural transfer of ADR-0041's reasoning plus a
  convergent "guaranteed" phrasing, not an explicit anti-averaging citation of
  Yiğit & Duysak's own strength), and Example 2 has no field convention at all
  to check against (a Kind-A gap named as such, not filled).
- **Shape B — a coherent-sum aperture-synthesis problem (Examples 4, 5): a
  direct array-factor computation, not a per-cell aggregation formula at
  all — the deliberate departure from Shape A.** A beam-steered aperture is
  N cells contributing to *one* coherent far-field sum, not N independent
  compliance checks, so the primary objective is not built by aggregating a
  per-cell error metric (minimax or otherwise) — it is a single deterministic
  physical computation of the realized array factor itself:
  `Loss_dB = 10·log10(η(θ_want))`, where `η(θ_want) = |AF(θ_want)|²/(Σ|E_n|)²`
  and `AF` is the coherent sum over all cells' actually-achieved phases. This
  already correctly captures how per-cell phase errors combine — constructive
  and destructive interference are what the array-factor sum *is* — without
  needing a separate aggregation step. **A simpler proxy — averaging or
  RMS-ing the per-cell phase errors instead of computing the actual array
  factor — is explicitly rejected, not merely unused**: per
  `docs/example4-5-beam-steering-scoring-recipe.md`, the curve's ~55°
  coverage gap produces phase errors that are *deterministic and spatially
  clustered*, not random, and a handful of clustered errors can seed a
  predictable quantization/spurious lobe that an averaged or RMS'd proxy
  would hide. That characterization is `LITERATURE-SUPPORTED at
  search-synthesis confidence` (RIS/reconfigurable-reflectarray quantization
  literature; the classical Miller/Mailloux N-bit result as a sanity-check
  ceiling), not `CONFIRMED` — the source document's own confidence tiers
  are carried forward here, not upgraded. Example 4 (a single fixed beam)
  computes this once, at its one target angle; Example 5 (a re-biasable
  scan) computes it per commanded angle and then applies
  `minimax_over_scan_angles(...)` on top, since each stated look-angle in a
  scan request is still a "must hold" compliance point, even though the
  underlying per-angle quantity is a direct physical computation rather than
  an aggregated one.

**This split — not a single blanket rule — is the generalizable decision.** A
future eighth example gets charted correctly by asking "is this a compliance
bar (one quantity swept along an axis, checked everywhere) or a coherent-sum
aperture-synthesis problem (many contributors to one combined result)," not by
defaulting to minimax out of habit because it worked for Example 3. Importing
minimax across cells for Examples 4/5 "because that's what we did for
absorbers" would repeat the exact borrowed-convention error
`docs/requirement-derived-thresholds.md` was written to catch (the ±22.5°
incident, where a design's own internal quantization step was smuggled in as
if it were a customer-facing threshold).

**2. #129/ADR-0047's physical_bound table gains Example 1 under Gustafsson & Sjöberg, and a genuinely new family for Example 2.**

- **Example 1 (magnetic mirror) joins Examples 4/5/7 under Gustafsson &
  Sjöberg**, verified directly against the primary text (Gustafsson &
  Sjöberg, *Physical bounds and sum rules for high-impedance surfaces*,
  TEAT-7198/2010): the sum rule's own scope statement covers "arbitrary
  dielectric and magnetic materials above a perfect conductor," and its
  worked numerical example (§6.1) is a bare dielectric slab — structurally
  the closest case in the paper's own text to Example 1's function. **One
  caveat travels with this assignment and must not be dropped**: the bound's
  `µ_s^max` term is explicitly the *static* (DC, ω→0) permeability, the same
  requirement this project's Rozanov application already carries for
  absorbers (`docs/absorber-thickness-bandwidth-bound.md` §4). A
  Mie-resonance-induced effective permeability (the patent's own claimed
  µ_eff≈5→20 at resonance) is a resonant dispersion that returns to ≈1 away
  from resonance — it does **not** loosen this bound the way a true ferrite's
  high *static* µ_s would. Absent evidence otherwise (the patent's own FIG. 5F
  low-frequency asymptote was not independently re-checked in this pass),
  Example 1 should be treated as bound by the **non-magnetic case**,
  `Bλ₀/d ≤ π`, not a resonance-loosened one.
- **Example 2 (impedance-matched/transmissive) gets a new bound family: the
  Bode-Fano broadband-matching theorem**, not Rozanov or Gustafsson-Sjöberg —
  both of the latter require a PEC ground plane in their own derivations, and
  Example 2's function (letting a wave pass through unimpeded) structurally
  cannot have one, in the patent's own setup or in any sensible deployment.
  The specialization to a matched slab (rather than a lumped load) is
  verified firsthand: R. Fano (1950)'s foundational theorem, specialized by
  Presutti & Monticone, *"Focusing on bandwidth: achromatic metalens
  limits,"* Optica 7, 624–631 (2020) — `B·ln(1/|Γ|) ≤ λc/(L·(ε−εb))`, the same
  shape as Rozanov's `|lnρ₀|·Δλ ≤ 2π²µ_sd` (a product of fractional bandwidth
  and a log matching-quality term, bounded by thickness × a material-contrast
  term), specialized to a different boundary condition. A more directly
  on-point paper (Zheng, Hao & Li, IEEE TMTT 73(11), 2025) exists but is
  IEEE-paywalled and unverified — named as the next thing to chase, not
  incorporated.
- **Example 6 (polarization conversion) re-confirms, from primary text rather
  than by repetition, ADR-0047's existing finding that no bandwidth-vs-thickness
  bound exists in the literature for this function.** Abdelrahman & Monticone's
  single-frequency thickness-vs-efficiency limit remains usable only as a
  pointwise, non-bandwidth diagnostic, exactly as ADR-0047 already prescribed.
  A candidate near-miss (Doane, Sertel & Volakis, IEEE TAP 62(5), 2014 — whose
  2013 precursor was already cited in `docs/absorber-thickness-bandwidth-bound.md`
  §2.1) is excluded: its "impedance bandwidth" bounds a *fed* array's match to
  its own feed line, a different physical quantity than an *unfed* converter's
  conversion bandwidth.
- **Example 7 (checkerboard/coding-metasurface)'s existing Gustafsson-Sjöberg
  assignment is unchanged, but its `NO_PHYSICAL_BOUND` diffuse-scattering
  exemption from Rozanov gains a second, previously undocumented precondition**:
  redirecting energy elsewhere in space is only exempt from an absorption sum
  rule if there is somewhere for the redirected energy to go — a propagating
  diffracted order, which for a checkerboard's two-tile supercell (period
  `D` = twice the individual tile size) at normal incidence requires
  `D ≥ √2·λ` (42.4 mm at 10 GHz, 30.3 mm at 14 GHz, this project's own band)
  — the diagonal-order diffraction condition for a checkerboard's lattice,
  where `D` denotes the supercell period, not a single tile's own dimension;
  reading `D` as one tile would be off by a factor of 2. Below that period,
  there is no diffracted channel and
  every dB of specular reduction must come from absorption, which *is* fully
  Rozanov-bounded. This is a per-candidate check, not a constant, and hits
  hardest exactly where a coupon-scale supercell is smallest. **Provenance
  note:** this precondition and its two numeric values were contributed by a
  parallel research pass (working against ADR-0050's ambit) and relayed here,
  not independently re-derived from primary text in this ADR's own pass — the
  underlying grating-equation argument (a checkerboard's diagonal-order
  diffraction condition) is standard and was sanity-checked, but the specific
  source document behind the two numbers was not directly read.

## Considered and rejected

- **Blanket minimax across all seven examples, no per-family re-examination.**
  Rejected because it would have produced the wrong answer for Examples 4/5:
  minimizing worst-cell phase error across an aperture treats the aperture as
  N independent compliance checks, but the customer-facing quantity
  (gain/pointing loss) is a *coherent sum* — the right computation there is
  the actual array factor itself, not any per-cell aggregation (worst-case or
  averaged) standing in for it.
- **Treating Rozanov as the bound for Example 1 by proximity to the absorber
  family.** Rejected: a magnetic mirror wants `|Γ|→1` (total, 0°-phase
  reflection); Rozanov bounds how much can be *absorbed* (`|Γ|→0` is the
  interesting direction there) — opposite regimes of the same reflection
  coefficient. Example 1 belongs with the reflection-*phase* family (G&S),
  the same reasoning that already places Examples 4/5/7 there.
- **Leaving Example 2 unbounded rather than deriving the transmissive-surface
  case.** Rejected: the causality/passivity machinery both Rozanov and G&S
  build on (Bode-Fano) is not itself PEC-specific — only the *specific*
  boundary condition each of those two bounds already adopts is. The
  free-space-matched specialization exists in the open literature
  (Presutti & Monticone 2020, citing Fano 1950) and had simply never been
  connected to this project's registry before.
- **Assuming Example 1's resonant µ_eff≈20 loosens its Gustafsson-Sjöberg
  bound the way a ferrite's static µ_s would for Rozanov.** Rejected: G&S's
  own derivation requires the *static* (DC) permeability, and a Lorentzian
  resonance's effective permeability returns to ≈1 well away from resonance —
  the two situations only look similar because both involve "a large µ_eff
  number in the patent," not because the bound-relevant physics is the same.

## Consequences

- A future example's scoring recipe should start by classifying it as Shape A
  or Shape B (compliance bar vs. coherent-sum aperture problem) before
  picking an aggregation formula, rather than defaulting to ADR-0041's
  minimax by habit.
- #129/ADR-0047's physical_bound table now has five populated rows (Rozanov:
  Example 3; Gustafsson & Sjöberg: Examples 1, 4, 5, 7; Bode-Fano: Example 2)
  and one confirmed-empty row (Example 6, pointwise-diagnostic-only). A sixth,
  as-yet-unwritten row for Example 2's better-fitting candidate (Zheng, Hao &
  Li 2025) remains open pending IEEE access.
- Example 1's registry entry must carry the static-vs-resonant-µs caveat as a
  footnote, not silently compute `Bλ₀/d` against the patent's headline µ_eff≈20
  — doing so would silently overstate Example 1's achievable bandwidth by
  roughly the same factor the resonant/static permeability values differ by.
- Example 7's `NO_PHYSICAL_BOUND` exemption logic (wherever it is eventually
  implemented) needs a `D ≥ √2·λ` two-tile-supercell-period check before
  granting the exemption, not merely a "this is a diffuse/coding design"
  family check — tracked as a gap in [#465](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/465)'s implementation scope, since the Gustafsson-Sjöberg
  function this exemption sits beside also does not exist in code yet.
- None of the six examples' recipes are wired into `orchestration/solver.py`
  or `rf_tools/physical_bounds.py` by this ADR — it is a specification
  decision, not an implementation. #465 tracks the code-side G&S gap; no
  ticket yet tracks turning these six recipes into executable scoring
  functions.

## Corrections

**2026-09-10**: `docs/absorber-thickness-bandwidth-bound.md` §7.1's quoted
Eq. (5.1) small-angle asymptote was found to read `π²Φ/2` where the primary
text (Gustafsson & Sjöberg 2010, p.9) reads `(π/2)Φ` — a factor-of-π
transcription slip, discovered while independently verifying the primary
source for this ADR's Example 1 assignment. Fixed in place in that document
and logged as `docs/RUNNING-LISTS.md` §3 correction 67. Does not change any of
that document's actual Φ=π/2 (`2.6`) or Φ=π (`2π`) arithmetic, used
everywhere in this project as exact closed forms rather than the small-angle
approximation — only the asymptotic label itself was wrong.
