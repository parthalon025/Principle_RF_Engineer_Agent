---
status: accepted
---

# An absorber's success score rewards the single worst-absorbing frequency in the band, and reproduction is compared by Feature Selective Validation

Issue #110 ("For an absorber, what does the success score reward?"), a line item
on the #104 wayfinder map ("Printed metamaterial EM skin design loop"), asked
five separate questions about the absorber design family's success score: does
it reward the worst point in the band, the mean, or the peak; is −10 dB/90%
absorption a default or a hard rule; does frequency response just outside the
band count for anything; how does incidence angle — load-bearing for a design
meant to conform to a curved host — enter the score; and how is a reproduction
of the patent's Example 3 against Landy et al.'s measured curve judged. It
builds on **ADR-0038** (#117): a requirement carries a **threshold** that
prunes and an optional **objective** that scores, and **silence is
permissive** — an unstated customer value never becomes a hard prune on the
tool's own authority.

`docs/absorber-scoring-conventions.md` (2026-09-03) ran the literature-first
method #117 established: check for a doctrine before inventing one. It found
that the peak-versus-bandwidth trade is governed by a theorem, not a
heuristic — the **Rozanov bound**, `d ≥ (1/2π²µₛ)·|∫₀^∞ ln|r̃(λ)| dλ|` — and
four conventions adoptable without argument: `A = 1 − |S₁₁|² − |S₂₁|²`
(collapsing to `1 − |S₁₁|²` ground-backed), fractional-bandwidth reporting,
angle/polarization as pass/fail retention statements (TE and TM kept
separate), and the identity that 90% absorption, −10 dB reflectivity, and
"effective absorption bandwidth" are one quantity, not three. It flagged the
five questions above as genuinely undecided. #110 was then resolved through a
human interview, and every pick from that interview was checked a second time
against the literature in `docs/absorber-scoring-decision-confirmation.md`
(2026-09-04), which returned one **CONFIRMED**, one answered by #117's
existing rule rather than by the literature, one **NO CONVENTION FOUND, STILL
A JUDGMENT CALL**, and two **CONTRADICTED** — with the document's own caution
that "neither 'CONTRADICTED' verdict is a simple reversal": in both cases the
interview's instinct was right and its stated mechanism was not quite what
the literature does instead. A separate comment, posted while #110 was still
open, additionally shaped point 2 below by applying a test already learned
the hard way on #130: *"if a threshold cannot be expressed in the units the
requirement uses, it is an internal quantity and cannot be a threshold"* —
−10 dB passes that test, "it is simply not the customer's number."

## Decision

1. **The primary objective is worst-in-band absorptivity — a minimax
   formulation — never the mean and never the peak.** Score a candidate on
   its single worst-absorbing frequency inside the band the requirement
   states. `LITERATURE-SUPPORTED`: minimax absorptivity is an explicit,
   recurring, named objective function across three decades of RAM/RCS
   metaheuristic design (genetic algorithm, particle-swarm, artificial-bee-
   colony multilayer optimizers), not an invented rule. Yiğit & Duysak
   (2021, *Fully Optimized Multilayer Radar Absorber Design Using
   Multi-Objective ABC Algorithm*, Eq. 1) state the argument against
   averaging explicitly: *"it is not a consistent method to give the average
   values of the reflection coefficients relative to the all frequency band
   and angle of incidence [because] if the design has a very low reflection
   coefficient at any angle or frequency, it significantly reduces the
   average value and affects the general information about other values."*
   *In plain terms: a single lucky deep null can drag an average down and
   make a design that fails badly everywhere else look good on paper —
   exactly the failure this project's minimax choice is built to refuse.*
   The framing traces at least to Weile, Michielssen & Goldberg (1996), who
   pose broadband absorber design as minimizing the *maximum* reflection
   coefficient against thickness, compared explicitly against "the weighted
   Tchebycheff method" — a classical minimax scalarization.

   **Caveat found and kept, not smoothed over:** solar/thermal absorber
   optimization uses the *mean* instead, deliberately — one paper's genetic
   search of over 10¹⁷ candidate configurations fits directly to total
   captured energy, and a second names and compares "FFad" versus "FFavg" as
   an explicit choice. This is a real, application-level split, not a
   contradiction: a photon absorbed at any in-band wavelength is equally
   useful for energy capture, so a mean is the right quantity there, while a
   stealth/RCS requirement such as "reflectivity below −10 dB across
   8.5–10.5 GHz" must hold everywhere in the band, not on average — this
   project's Example 3 situation matches the minimax sub-literature, not the
   averaging one.

2. **−10 dB / 90% absorption is a reversible, one-pass default when the
   customer states no absorption threshold — never a hardcoded rule, and
   never used to redefine the band's own edges.** `CALCULATED`: −10 dB
   reflectivity ⇒ `|S₁₁|² = 0.100` ⇒ `A = 0.900` — one quantity, not three.
   Absent a customer-stated figure, the loop falls back to this default,
   **records that a gap was filled**, and lets any customer-stated figure
   override it without argument — the same shape of rule #117 already
   settled ("silence is permissive... no threshold, no pruning"), applied
   here to the absorption threshold instead of the bend-radius one. This
   must stay a *default*, never a hard prune, because the literature itself
   is inconsistent about the number (70–99% absorption, −6.99 to −20 dB all
   appear in practice) and its only standards-body relative, IEEE Std 1128,
   stops at 5 GHz, is non-mandatory, and standardizes *how to measure*
   reflectivity rather than *how to score* an absorber — real journal
   convention, but weaker evidence than a customer's own stated number. The
   band's frequency edges always come from the requirement as stated, never
   from a −10 dB contour search — a distinct, adjacent convention ("10 dB
   bandwidth" as *the* band) that exists in the literature purely as a
   device for comparing published designs to each other, not as a
   definition of any one customer's band.

3. **Off-band behavior gets its own separately-reported score — not blended
   into the ranking via an invented weight, not simple pass/fail, and not
   ignored** — checked by default over a margin of **10% of the required
   band's width past each edge**, reversible and overridable by the same
   mechanism as point 2. `NO CONVENTION FOUND, STILL A JUDGMENT CALL`, after
   a deeper, two-directional search turned up a precise reason rather than
   an empty one: filter and frequency-selective-surface (FSS) design has a
   real, quantitative, decades-old vocabulary for this exact shape of
   question — roll-off rate (`20n dB/decade` for an *n*th-order filter) and
   transition bandwidth (a "−3 dB to −20 dB" drop) — but it scores
   **transmission** (`S₂₁`), the wrong physical quantity: a ground-backed
   absorber has `S₂₁ = 0` at every frequency by construction (this
   project's own default, ADR-0017), so there is nothing for a roll-off
   calculation to be *about*. No RAM paper scores off-band absorptivity
   either; the closest near-miss, a multi-band terahertz metric
   `Δ = 2(f₂−f₁)/(f₁+f₂)` (Wang et al. 2019), is the same formula shape
   aimed at the opposite goal — it *minimizes* the gap between two *wanted*
   bands, where #110's margin wants a *larger* gap of correctly-low
   absorptivity outside one required band. This stays a decision, not a
   lookup, now with the dead ends documented rather than re-discoverable by
   accident.

4. **Incidence angle is scored via curvature-derived discrete zones, not a
   continuous sliding scale — revised from the interview's original
   continuous-sliding-scale pick after the literature contradicted it.**
   The angle range a candidate faces is still derived from the host
   surface's actual curvature, but the score checks pass/fail at a handful
   of representative angles/zones across that range rather than integrating
   continuously across it. `CONTRADICTED`: a literature pass aimed squarely
   at the conformal/curved/flexible/wearable absorber subfield — the one
   place a continuous range of local incidence angles is physically
   inherent — found that every such paper still reports discrete-angle
   threshold-retention statements, even where a full continuous angle-sweep
   curve is already sitting in the paper's own plotted data. The real
   precedent, Jang, Yoo & Lim (*"Conformal metamaterial absorber for curved
   surface,"* Optics Express 21(20):24163–24170, 2013), maps unit-cell
   design targets to physical *zones* on a bent surface (R = 15 cm, a
   41×10 unit-cell array), each zone checked at a conventional discrete
   benchmark angle (0°/30°/45°) rather than a continuum — and its own
   headline result reduces a continuous bistatic sweep it already has in
   hand (θ from −80° to 80°) down to single broadside-angle point
   comparisons. *In plain terms: the literature does use curvature to
   decide* where *on a bent surface to check — and it checks a handful of
   fixed angles there, never a continuously-graded score across the whole
   swept range, which is exactly the shape this decision adopts.* Nothing
   found gives a citation for "score = integral of absorption over swept
   incidence angle," so the original interview pick is retired in favor of
   the pattern every checked paper actually uses.

5. **Reproducing the patent's Example 3 against Landy et al.'s measured
   curve adopts Feature Selective Validation (FSV) — IEEE Std 1597.1-2008/
   2022 with companion practice IEEE Std 1597.2-2010 — not RMS error in
   dB.** `LITERATURE-SUPPORTED`: FSV is the field's actual formal standard
   for comparing an electromagnetic-simulation curve against measurement,
   "applicable to a wide variety of electromagnetic applications including
   electromagnetic compatibility, radar cross section, signal integrity, and
   antennas." It works by splitting the comparison in two rather than
   averaging every pointwise gap into one number: **ADM** (Amplitude
   Difference Measure, from each curve's low-pass "trend" component),
   **FDM** (Feature Difference Measure, from the high-frequency "feature"/
   resonant component via wavelet or Fourier decomposition), and
   **GDM** = √(ADM² + FDM²) as an overall figure, each binned into a
   six-level qualitative grade (Excellent…Very Poor) and summarized as
   **GRADE** and **SPREAD**. This is directly relevant, not merely
   preferred in the abstract: #142 already found the patent's stated
   resonant frequency and Landy's measured frequency disagree by roughly
   20%, and FSV was built specifically because naive point-by-point RMS
   error over-penalizes exactly this kind of small resonance-frequency
   shift in oscillatory, resonance-shaped EM data. This is a **separate
   mechanism entirely from real-design scoring (points 1–4)**: a
   curve-agreement check against one known published result, not a
   requirement-compliance score. A follow-up ticket, **#168**, was opened to
   spec FSV's actual implementation, since its primary standard text (and
   Duffy & Orlandi's original FSV theory papers) is IEEE-paywalled and
   unread here, and the ADM/FDM/GDM/GRADE/SPREAD mechanism is meaningfully
   more complex than a single number.

All five stay bound by the project's standing rule: **nothing here prunes or
scores against a number the customer didn't ask for and the tool didn't
explicitly flag as a filled-in guess.**

## Considered and rejected

- **Mean-in-band absorptivity as the primary objective.** Rejected for this
  project's stealth/RCS use case per Yiğit & Duysak (2021)'s argument above
  — kept as the right choice for a different application (solar/thermal
  energy capture), not rejected universally.
- **Peak absorptivity (`RL_min`) as the primary objective.** Rejected: the
  RAM literature carries a live critique that a very deep null is a
  coincidence of near-perfect impedance match at one frequency and one
  thickness, tunable to arbitrary depth for almost any lossy material, and
  therefore not discriminating — read only through secondary summary, its
  two primary sources (Yang et al. 2025, Adv. Electron. Mater.; AIP
  Advances 8, 015223) stranded behind Wiley and AIP paywalls.
- **RMS error in dB for the Example 3 reproduction check.** Rejected in
  favor of FSV: no paper anywhere reproduces Landy 2008's specific curve
  with a quantitative agreement statistic to begin with, and naive
  point-by-point differencing is exactly what over-penalizes the kind of
  resonance-frequency shift the patent-vs-Landy comparison already shows.
- **Filter/FSS roll-off rate and transition bandwidth for off-band
  scoring.** Rejected: real and quantitative, but scores transmission
  (`S₂₁`), the wrong physical quantity for a ground-backed absorber whose
  `S₂₁ = 0` by construction.
- **The multi-band "relative discrete distance"
  `Δ = 2(f₂−f₁)/(f₁+f₂)` (Wang et al. 2019) for the off-band margin.**
  Rejected: same formula shape, opposite objective — it minimizes the gap
  between two *wanted* bands, not a margin of correctly-low absorptivity
  outside one required band.
- **A continuous sliding score across the swept incidence-angle range** —
  the interview's original pick. Rejected once the literature pass found no
  citation for it anywhere: every conformal/curved-absorber paper checked,
  including the one real precedent (Jang et al. 2013), still reports
  discrete-angle threshold-retention statements even where a continuous
  angle-sweep curve was already sitting in the paper's own plotted data.
- **A −10 dB contour used to define the band's own edges.** Rejected: the
  requirement states the band; the contour is a device the literature uses
  to compare published designs to each other, not a definition of any one
  customer's band.
- **A hardcoded, non-reversible −10 dB/90% threshold.** Rejected: it would
  convert an unstated requirement into a hard prune on a literature figure
  the customer never cited, directly contradicting #117/ADR-0038's
  "silence is permissive" rule.

## Consequences

- The absorber design family's scoring path must express all five
  mechanisms above wherever it ranks a candidate or checks a reproduction:
  worst-in-band minimax as the primary objective; −10 dB/90% as a recorded,
  overridable default that never touches the band's own edges; a
  separately-reported off-band score at a 10%-past-each-edge default
  margin; curvature-derived discrete-zone pass/fail for incidence angle;
  and FSV, not RMS, for any comparison against a published measured curve.
- **#168 stays open and unresolved — carried forward, not settled here.**
  Beyond specifying FSV's implementation, #168 now also carries an
  uncountered challenge to the *reason* FSV was chosen at all: Landy's own
  resonance is only about 4% wide (FWHM — full width at half maximum, the
  standard way to state how narrow a resonance peak is), so the roughly
  20–25% frequency offset between the patent and Landy's curve is on the
  order of **five resonance-widths apart** — the two curves barely overlap.
  A feature-matching method like FSV may report near-total disagreement
  just as bluntly as RMS error would in that situation, which would
  undercut the stated justification for preferring it over RMS in the
  first place. This needs resolving on #168 before an implementation is
  built on the assumption that FSV is settled.
- **The reproduction comparison also needs the full two-port quantity,
  `A = 1 − |S₁₁|² − |S₂₁|²`, not the ground-backed reduction
  `A = 1 − |S₁₁|²`.** A later research pass found the patent's Example 3
  itself lets some signal pass through rather than fully blocking it,
  unlike this project's own designs, which are ground-backed by default
  (ADR-0017). `docs/absorber-scoring-decision-confirmation.md` was written
  before that finding landed, so whichever curve-agreement method is built
  on FSV must be wired to the full two-port absorption quantity for this
  specific comparison.
- **Off-band scoring's 10%-past-each-edge margin is recorded as a bare
  judgment call, not an inherited literature convention** — the deeper
  search this decision ran came back with a documented, specific reason
  (wrong physical quantity in the one adjacent field that has a
  convention) rather than a citation, and that absence must not be quietly
  dressed up as adopted practice in any later document.
- **Does not decide** FSV's internal implementation detail (the exact
  ADM/FDM/GDM formulas, the six-level grading bins, how GRADE/SPREAD fits
  the rest of the scoring code) — left entirely to #168. Does not change
  ADR-0038's threshold/objective mechanics; this ADR applies that
  mechanism to the absorber family's absorption threshold and to a newly
  separately-reported off-band score, rather than revising it. Does not
  touch the Rozanov-bound physical-realizability check for the absorber
  family, which is a separate mechanism (the family's `physical_bound`
  field is ADR-0018's territory; which bound applies to which family and
  why is ADR-0047's).
