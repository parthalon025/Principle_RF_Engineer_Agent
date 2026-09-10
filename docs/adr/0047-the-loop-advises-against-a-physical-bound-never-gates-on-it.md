---
status: accepted
---

# The loop advises against a per-family physical bound, and never gates a candidate for appearing to beat it

Issue #129 opened as a narrow question — is the patent's Example 3 anchor
design close to a theoretical thickness-versus-bandwidth limit — and closed
as a general one, because the narrow question turned out to be
unanswerable. A first research pass restated **K. N. Rozanov, "Ultimate
thickness to bandwidth ratio of radar absorbers," IEEE Trans. Antennas
Propag. 48(8), 1230–1234, 2000** from four citing sources (the paper itself
was stranded behind an IEEE Xplore 403), verified the restated inequality
arithmetically against two independent anchors — Rozanov's own abstract
headline of "1/17 of the largest operating wavelength" (calculated
1/17.15) and *Sci. Rep.* 9:16359's independently published constant of 172
(calculated 171.45) — and, cross-referencing #109's parallel work,
established that the bound is **per-family**, not one formula with a
constant swapped in (this is also the deciding fact behind ADR-0018's
choice to make `physical_bound` an open per-family field rather than a
fixed schema slot).

A later pass (2026-09-05) read Rozanov's paper first-hand rather than
through restatements, and it overturned three of the ticket's own working
inputs at once. The paper's opening sentence states the bound is derived
for "a slab … **overlying a perfectly reflecting plane** and illuminated at
**normal incidence**," and Eq. (6) is stated for "any **metal-backed**
magnetodielectric layer." Example 3 has no ground plane — per
`seven-example-design-unknowns.md` (lines 184–186, 202, 345) it is a
two-port device, and Landy suppresses transmission with a cut wire rather
than a reflector, which is why FIG. 7G plots a `|S₂₁|` trace at all
(absorbance there is `1 − |S₁₁|² − |S₂₁|²`). Two more inputs the ticket had
used were also wrong: the patent states verbatim that FIG. 7G's plot
"shows simulated scattering performance… over select frequencies ranging
from 8.5-10.5×10⁹ Hz (a sub-band of the X-band)" — a plot axis, not a
stated requirement band, and the bound is *linear* in that span, so every
headroom figure computed against it had scaled one-for-one with a
mislabeled number — and the 0.87 mm total thickness used throughout the
ticket was an arithmetic slip in the patent, superseded by #116's drawing
measurement of 0.15 mm conductor / 0.72 mm dielectric / 0.15 mm conductor,
1.02 mm total.

With the anchor question dead, the ticket resolved the question that
survives it: not "is this one design near the limit," but "should the loop
know the bound at all, for the designs it produces going forward" — which
matter under ADR-0017's default that this programme's own skins print
their own ground plane.

## Decision

**Advise, never gate.**

1. **Report the fraction of the limit a candidate achieves, computed
   against the candidate's own curve, not a rectangle.** The naive
   reading of any of these bounds assumes `|ρ| = 1` at every frequency
   outside the design band — a perfect mirror there — which is physically
   impossible for any real lossy structure and makes the naive bound "a
   ceiling on a ceiling." The number the loop reports is the integral of
   the candidate's own simulated response curve against the bound's
   inequality, not the candidate's band edges dropped into the rectangular
   form.
2. **Never fail a candidate for appearing to beat its family's bound.** A
   bound derived under stated assumptions — a perfectly reflecting
   backing, normal incidence, a specific stated band — being apparently
   exceeded means one of those assumptions was violated, not that physics
   was beaten. The **flag is the useful output**; refusing the candidate
   would throw away the diagnostic along with a design that may be
   perfectly buildable.
3. **The bound is per-family** (`physical_bound`, ADR-0018), and the three
   families this ticket resolved carry three structurally different
   answers:
   - **Absorbers** — Rozanov: `|ln ρ₀| · (λ_max − λ_min) ≤ 2π² · μ_s · d`
     (2π² = 19.739209), linear in thickness and static permeability,
     independent of permittivity.
   - **Beam steering by reflection phase (Examples 4, 5) and
     AMC-checkerboard backscatter reduction (Example 7)** — Gustafsson &
     Sjöberg: `B·λ₀/d ≤ 2.6` for the standard ±45° phase window. At the
     same thickness this is **roughly 5× harsher** than the absorber
     bound — at 9.5 GHz, 0.87 mm gives 7.2% against Gustafsson–Sjöberg
     versus 44.9% against Rozanov, and 2.0 mm gives 16.5% versus 87.8% —
     and published numerical designs already reach 82–99% of it.
   - **Polarisation conversion (Example 6)** — **no bandwidth bound exists
     in the literature.** Abdelrahman & Monticone (arXiv:2208.05533) give
     only a single-frequency thickness-versus-efficiency bound and state
     plainly that "more work is needed to extend these results to the
     problem of broadband maximization… establishing fundamental
     tradeoffs between bandwidth, thickness, and reflectance."
4. **The question as originally posed does not get an answer, and this
   ADR does not manufacture one.** "Is Example 3 near the limit" is dead
   for the reasons in Context — the bound does not apply to that device —
   and nothing here retries it against a corrected ground-plane
   assumption or a corrected band. What is decided is the loop's own
   future behaviour toward its own metal-backed designs, not a verdict on
   the patent anchor.

## Considered and rejected

- **Gating on the bound** — pruning or failing a candidate that appears
  to violate or exceed it. Rejected: three of Rozanov's assumptions
  (normal incidence, PEC backing, `μ_s = 1`) are escapable in this design
  space — oblique incidence alone moves the allowed bandwidth by up to
  43% (2 mm at −10 dB: 87.8% at boresight → 79.3% at 30° → 68.0% at 45° →
  50.8% at 60°) — so gating risks silently refusing a feasible design. The
  failure mode of over-advising is one wasted evaluation; the failure mode
  of gating on a violated assumption is a lost design.
- **Reporting against the rectangular out-of-band model** (`|ρ| = 1`
  everywhere outside the stated band). Rejected in favor of integrating
  the candidate's own simulated curve: the rectangular form is the
  loosest possible reading, and a design already at 70% of it may be at
  95% of what its own dispersion actually permits.
- **A single "% of limit" field shared across every family.** Rejected:
  the same number would report roughly 8% for a good polarisation
  converter and roughly 70% for a good absorber and mean nothing set
  against either — this is the load-bearing case for keeping
  `physical_bound` per-family under ADR-0018 rather than a shared scalar.
- **Locating a feasibility check at a `REQUIREMENTS` step**, as the first
  research pass proposed. Corrected, not merely deprioritized:
  `REQUIREMENTS` is the loop's own human-supplied starting input, not a
  step `advance_design_loop_step` ever advances past (`orchestration/
  design_loop.py`'s module docstring and `start_design_loop`), so nothing
  can live there in the sense the proposal meant.

## Consequences

- `physical_bound` stays a per-family registry field under ADR-0018,
  computed as a curve-integral fraction of the applicable family's bound
  and surfaced to a reviewer as a report, never used to prune a
  candidate from a batch.
- **A trap the implementation must carry forward:** the integral is over
  the *voltage* reflection coefficient `|ρ|`, not power `|ρ|²`. Getting
  this backward silently doubles every headroom figure — the ticket
  reconstructed a likely instance of exactly this error in a published
  *Sci. Rep.* figure, whose quoted "theoretical limit" of 6.7 mm matches
  the voltage-convention bound of 3.41 mm only once doubled.
- A stopping condition for the fast tier already exists
  (`orchestration/solver.py`'s `score_plateau` check, its own module
  docstring "DESIGN QUESTION 2"); this decision does not ask for a new
  one, and corrects the ticket's own earlier claim that no principled one
  exists.
- **The per-family bound table's canonical home, settled:** ADR-0018 (from
  #109) already settled the *mechanism* — `physical_bound` is a first-class,
  open, per-family registry field, not a shared scalar or a hardcoded enum.
  What ADR-0018 does not itself carry is a canonical table of *which* bound
  formula and citation applies to *which* family and *why*. **That table is
  this ADR's own content**, not a duplicate of ADR-0018: Rozanov for
  absorbers; Gustafsson & Sjöberg for reflection-phase steering (Examples 4,
  5) and AMC-checkerboard backscatter reduction (Example 7), ~5× harsher;
  none in the literature for polarisation conversion (Example 6); Nel,
  Skrivervik & Gustafsson for patch antennas (added later, under ADR-0018,
  per the note below) — together with the advise-never-gate scoring rule
  this ADR states. Issue #193's own instruction not to re-litigate governed
  the *bound choices themselves*, which stand as this ticket already made
  them; it did not exempt this backfill from stating where that table
  canonically lives, which #129's own resolving comment names this backfill
  batch as the place to settle.
- **Not decided here:** a proposal on the same thread to cache each
  bound's `CALCULATED` output across runs, keyed by material constants
  and thickness rather than by requirement, in a store structurally
  identical to ADR-0015's material-property library. The proposer's own
  words: "a follow-on once #129 itself resolves, not a substitute for
  resolving it" — it is not yet its own tracked issue.
- The per-family table this decision relies on keeps growing under
  ADR-0018 independently of this ADR: #109 later added diffusive/coding
  backscatter reduction (upgraded from structural inference to a
  systematic-search null result) and patch antennas (Nel, Skrivervik &
  Gustafsson, "Q-factor Bounds for Microstrip Patch Antennas," IEEE TAP
  71(4):3430–3440, 2023 — explicitly not the Chu limit). Neither addition
  changes the advise-never-gate rule this ADR states.
