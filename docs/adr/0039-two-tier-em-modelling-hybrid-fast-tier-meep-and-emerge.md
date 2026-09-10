---
status: accepted
---

# Two-tier EM modelling: a hybrid fast tier, Floquet confirmation outer, Meep extended and EMerge adopted as solvers

Issue #104's wayfinder map ("Printed metamaterial EM skin design loop") needed
a computational shape for evaluating candidates: solving every
parameterisation of every alphabet letter at full-wave cost is `O(letters)`
and does not scale. Issue #111 asked what a cheaper tier could honestly do,
building on ADR-0018's decision to leave `simulation_adapter` and
`optimizer_class` as open, declared fields rather than closed two-value
enums — both already flagged a credible third value on the horizon (a future
periodic adapter; ML-direct inverse design). Two questions were contested
going in, neither with an obvious answer: whether effective-medium
homogenisation (Maxwell-Garnett, or NRW-style S-parameter inversion) is valid
as the basis of a fast tier at all, given that the regime a coded absorber
operates in is exactly the regime homogenisation is weakest in; and which of
the repo's simulation adapters (`simulation/palace.py`, `simulation/meep.py`,
`simulation/openems.py`, plus NEC2) can carry a lossy printed conductor under
a Floquet (periodic) boundary — the physics a per-shape fast-tier solve
actually needs.

Research merged via PR #179 (`docs/grilling-pass-2026-09-05.md`, a 48-agent
pass covering #111 and eleven other tickets) settled the physics question
against primary sources. Alù (*Phys. Rev. B* 84, 075153, 2011;
[arXiv:1012.1351](https://arxiv.org/abs/1012.1351)) shows NRW-style retrieval
*"often provides constitutive parameters with nonphysical frequency
dispersion, in particular near the inclusion resonances,"* and that this
holds even for electrically small cells because the wavelength that governs
validity is the eigenmodal one inside the array, which collapses toward the
lattice period at resonance — corroborated by Koschny, Markos, Smith &
Soukoulis (*Phys. Rev. E* 68, 065602(R), 2003;
[arXiv:cond-mat/0307361](https://arxiv.org/abs/cond-mat/0307361)) and Menzel
et al. ([arXiv:0908.2393](https://arxiv.org/abs/0908.2393)). But Alù's own
conclusion narrows the door rather than closing it: retrieved parameters
*"should not be used to deduce the permittivity and permeability of the
array"* but remain usable *"for predicting reflection and transmission of the
finite structure"* — which is all an absorption score needs, since
`A = 1 − |S₁₁|² − |S₂₁|²`. A parallel implementation sweep found the solver
side unable to host even that narrower use as first proposed:
`simulation/palace.py`'s material dict carries only `Attributes`,
`Permittivity`, `Permeability`, `LossTan` (`simulation/palace.py:576-587`) —
no conductivity field, no impedance boundary anywhere in the module, so it
cannot see a lossy conductor at all; `simulation/openems.py` can represent
conductivity (`kappa_s_m` → `<Kappa>`) but has no periodic boundary
whatsoever, only PMC symmetry planes valid at normal incidence, and meshing a
1–2 µm MXene film at X-band (λ₀ = 30 mm) would force a ~30,000:1 cell aspect
ratio against the FDTD Courant condition; NEC2 was separately found
structurally incapable. This is what superseded #109's earlier commitment to
`simulation_adapter = PALACE_FLOQUET`, made before Palace's conductivity gap
and openEMS's total incapacity were known.

## Decision

1. **The fast tier is a hybrid, not a single homogenisation step**: one
   **Floquet solve per shape family** extracts a lumped capacitance, and
   **closed-form algebra** (Luukkonen/Tretyakov for patches and strip grids,
   Costa et al. for the absorber stack) covers every size, substrate, angle
   and loss variation after that — `O(shapes)`, never `O(letters)`.
   **Maxwell-Garnett is superseded**: its dilute-inclusion assumption never
   fit dense, stacked resonators.

2. **The fast tier is a scattering surrogate only, never a
   material-property extractor.** Homogenisation/NRW-style retrieval is
   valid for predicting reflection and transmission of the finite structure
   (`A = 1 − |S₁₁|² − |S₂₁|²`) — never for reporting the array's own
   effective permittivity or permeability, per Alù (2011), corroborated by
   Koschny et al. (2003) and Menzel et al. The moment a retrieved parameter
   is fed into a mixing rule or compared between materials, it is being used
   invalidly, and that is by design rather than a hedge: **homogenisation is
   provably invalid near resonance, and resonance is exactly where an
   absorber works.**

3. **Two fast tiers, not one.** **Tier A** — a uniform surface, where one
   solve is the whole evaluation. **Tier B** — an aperture surface, where the
   cell solve populates a phase lookup/alphabet per #130. These are
   different evaluation shapes, not two settings of the same one.

4. **The patent's I-shaped ring resonators** have no closed-form model
   adoptable from the literature (per #131). For this shape family: run a
   handful of Floquet solves across its parameter range and **fit an
   empirical curve** to the results. Not a from-scratch first-principles
   derivation — a genuine unverified-research undertaking this project is
   not funding for one shape family right now — and not the full solve cost
   on every evaluation, since this is the patent's actual element and it
   will be evaluated often.

5. **Solver commitment: extend Meep, and adopt EMerge — two solvers,
   preserving a real cross-check.** Meep is already a project dependency and
   ships `meep.adjoint`, but its adapter currently sets no Bloch `k_point`;
   extending it is decided over adding a new dependency for that half.
   **EMerge** — a pure-Python FEM package with native `FloquetPort` and
   `PeriodicCell` support, pip-installable, 279 stars, last commit
   2026-08-23 at the time of this decision, real but less field-validated
   than the alternatives — is adopted alongside it, specifically so the
   design loop has two independently-implemented solvers to check against
   each other rather than one. **Palace is not usable for this**: its
   material model has no conductivity or impedance-boundary field at all
   (`simulation/palace.py:576-587`), so it cannot represent a lossy
   conductor. **openEMS is out entirely**: no periodic boundary whatsoever —
   only PMC symmetry planes, normal-incidence only — independent of its
   separate MXene-thickness meshing problem. **NEC2 is structurally
   incapable.** This supersedes #109's earlier commitment to
   `simulation_adapter = PALACE_FLOQUET`.

6. **The local-periodicity/superposition error budget gets derived now**,
   rather than deferred until a real requirement exists, using a documented
   one-afternoon method: build an extended unit cell, sweep the neighbour
   count, plot the error, stop once it drops under budget. It is validated
   against a published stand-in target — Cui et al.'s acceptance band of
   **10 dB radar-cross-section reduction while the two coded tile types stay
   between 145° and 215°** (±35° about 180°). This only matters for **Tier
   B** (alphabet-based) designs; Tier A (Example 3, one repeated element)
   does not need it. It is re-derived later against whatever a real
   requirement actually demands, per the map's standing rule that every
   threshold traces back to the requirement.

7. **Promotion to full-wave confirmation is by top score, filtered for
   diversity**: near-duplicates among the top-scoring candidates are skipped
   in favour of the next-best genuinely different design, so the expensive
   confirmation tier is never spent re-confirming near-identical candidates.

8. **An ML-direct inverse-design surrogate is a legitimate third tier**,
   alongside the fast and confirmation tiers — not a replacement for the
   fast tier, and not out of scope for this ticket. It is adopted once
   enough historical design data exists to train on, which is not yet the
   case. Chen's 2023 UIC dissertation validates one such approach — an
   autoencoder-decoder trained on ~30,000 HFSS simulations — on three real
   absorber-radome cases, the nearest existing precedent. Consistent with
   ADR-0018's `optimizer_class` already being left open for exactly this.

## Considered and rejected

- **Maxwell-Garnett effective-medium mixing as the fast tier's basis.**
  Rejected: its dilute-inclusion assumption never fit dense, stacked
  resonators.
- **Palace as the per-shape Floquet solver.** Rejected: its material model
  carries only `Attributes`, `Permittivity`, `Permeability`, `LossTan` — no
  conductivity field, no impedance boundary anywhere in the module — so it
  cannot represent a lossy conductor at all.
- **openEMS as a Floquet solver.** Rejected: no periodic boundary
  whatsoever, only PMC symmetry planes valid at normal incidence;
  separately, meshing a printed MXene film at X-band would force a
  ~30,000:1 cell aspect ratio against the FDTD Courant condition.
- **NEC2.** Rejected as structurally incapable.
- **A first-principles closed-form derivation for the I-shaped ring
  resonator.** Rejected for now: a genuine unverified-research undertaking
  this project is not funding for one shape family.
- **Paying the full Floquet solve cost on every evaluation of the I-shaped
  ring resonator.** Rejected: it is the patent's actual element and will be
  evaluated often, so the empirical curve is the cheaper choice.
- **Waiting for a real requirement before deriving the local-periodicity
  error budget.** Rejected in favour of deriving it now against Cui et al.'s
  published ±35° acceptance band as a stand-in target.
- **Treating the ML-direct inverse-design surrogate as a replacement for the
  fast tier, or as out of scope for this ticket.** Rejected: it is adopted
  as a genuine third tier, gated only on having enough historical data to
  train on.

## Consequences

- Implementation work is committed on both solver adapters:
  `simulation/meep.py` needs a Bloch `k_point` added to its periodic-boundary
  handling, and an EMerge adapter needs to be built with
  `FloquetPort`/`PeriodicCell` support, before the per-shape Floquet solve
  this ADR depends on can run for real.
- The I-shaped ring resonator's empirical curve is a standing simplification,
  not a placeholder for a first-principles model assumed to arrive later —
  no such derivation is planned unless the calculus changes.
- The local-periodicity error budget derived against Cui et al.'s stand-in
  target is provisional by design and must be re-run against any real
  requirement once one exists, per the map's own rule.
- **Flagged during this decision, since resolved:** the closed-form
  absorber-stack algebra this fast tier depends on (Costa et al.) was
  missing its thin-spacer correction (eq. 10) at the time of this decision.
  #190 has since recovered and verified it —
  `C₀^thin = C₀ − (2·D·ε₀/π) · log(1 − e^(−4πd/D))` (natural log), from
  Costa, Genovesi, Monorchio & Manara
  ([arXiv:1211.1902](https://arxiv.org/abs/1211.1902)) — and found the bias
  it corrects is **1–3% in frequency at #128's design point: a trim, not a
  redesign.** #190 is closed; cited here as resolved research context, not
  as part of this ADR's original reasoning.
- **Still open, not decided here:** #202's literature survey reports
  ML phase-surrogate errors that, if the underlying numbers hold up, would
  fit inside the phase budget — but training costs **~80,000 solves**, and
  #202 itself flags both figures as read off outside literature, not yet
  verified by this programme. Whether that replaces a Floquet solve for
  Example 7's tile phases is a live, unresolved question on #202 — this ADR
  does not decide it.
- This ADR does not decide when the ML-direct third tier's data threshold is
  met, only that it activates once it is.
- This is a plan-only decision, consistent with #104's map; no code changes
  accompany it.
- **This ADR is now the stable, correctable record of the solver
  commitment, replacing the one-comment version it superseded.** #109's own
  resolution committed to `simulation_adapter = PALACE_FLOQUET` in passing,
  before this ticket's own research found Palace cannot represent a lossy
  conductor at all — a commitment that had already changed once, in a
  comment, with nothing to correct. Any future change to which solvers this
  fast tier uses should land as a dated correction to this ADR (per
  ADR-0020's amend/supersede test), not as another one-off comment on #109,
  #111, or elsewhere.
