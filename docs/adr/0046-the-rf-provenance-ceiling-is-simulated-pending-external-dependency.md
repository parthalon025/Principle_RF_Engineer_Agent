---
status: accepted
---

# With no RF instruments on hand, the provenance ceiling for RF response is SIMULATED, and raising it is deferred pending an external dependency

Issue #133 ("No RF instruments: what is the provenance ceiling, and how is
the fixture modelled?"), filed against the wayfinder map #104, picked up
where #132 left off: #132 had already settled the "**settled fact**" that
"there is **no VNA and no free-space or waveguide fixture available**."
#133 asked what that means for the provenance rung RF response can carry,
and whether the loop should model the eventual measurement fixture at all.
The question had become load-bearing while still open — the map's own
Destination section was already quoting the ticket's anticipated finding as
established fact, so a premise the whole effort rests on was simultaneously
asserted, tracked as an open question, and flagged as possibly about to
change.

Two threads complicated a quick answer. First, a Cooperative Research and
Development Agreement (CRADA) with DEVCOM — the assignee of US12089385B2 —
is being pursued; Army Research Laboratory/DEVCOM facilities "include
anechoic chambers, vector network analysers and free-space measurement
benches," so a CRADA could lift the ceiling from a direction other than a
purchase. Second, a research pass into buying a measurement instead
(`docs/xband-measurement-service-options.md`) priced two university routes —
University of Kansas, external user with technician, one 8-hour day, ≈US
$2,271 (US$255 training + 8 × US$252/hr), and Texas A&M's iEMSL, assisted,
one day, ≈US$4,800 (US$4,500/day + US$300 membership), against a used-bench
purchase at US$13,000–30,000, with crossover at roughly 3–8 outsourced
sessions — but that same pass, and a follow-on grilling pass
(`docs/grilling-pass-2026-09-05.md` §1, PR #179), found its own fixture
conclusions had been scoped to the wrong measurement: a one-port Touchstone
`.s1p` (A = 1 − |S₁₁|²), which only holds when the article under test is
ground-backed. That same grilling pass carried a second, separate finding
this ticket must also inherit: *"`SIMULATED` does not currently mean
*validated* simulation in this repo — CONTEXT.md's 'Reference case' entry
says passing a reference case is what would earn that word, and no such
corpus exists. That is the honest ceiling today."*

## Decision

1. **The provenance ceiling for RF response is `SIMULATED`, today — and, at
   the time of this decision, an unvalidated `SIMULATED` at that.** There
   is no VNA, no measurement fixture and no chamber in this programme.
   Every RF-response number the loop produces — reflection, absorption,
   transmission versus frequency — is a full-wave or closed-form
   prediction, capped at `SIMULATED`, never `MEASURED`. `SIMULATED` does
   not by itself mean *validated*: CONTEXT.md's "Reference case" entry
   reserves that word for a simulation checked against a corpus of
   known-exact answers, and none existed when this ADR was written — the
   honest ceiling was "simulated, unvalidated." (`docs/meep-absorber-
   validation.md` has since supplied a first, narrow validated reference
   case; formalizing a "validated" tag distinct from bare `SIMULATED`
   remains an open item on map #104, not decided here.)
   **A simulation's own input provenance is a separate axis from this
   ceiling and is not lost:** ADR-0042 (#112) already carries a full
   per-input provenance profile on every score, so a simulation fed a
   `MEASURED` conductivity and one fed a `LITERATURE-SUPPORTED` guess are
   distinguishable in that profile even though both outputs are capped at
   `SIMULATED` — answering #133's own "Decide: what provenance a
   simulation on measured inputs carries" by cross-reference rather than
   by a new mechanism.

2. **Raising that ceiling is *deferred pending an external dependency* — a
   state distinct from "unresolved," and now a standing preference on map
   #104.** *Deferred pending an external dependency is a state, distinct
   from unresolved. A decision nobody here can make — because it waits on
   facility access, an agreement, or a third party — is recorded as
   deferred with the dependency named, not left open as though someone
   could just work harder at it. Decisions robust to either outcome
   proceed now regardless.* Two real routes exist, named rather than left
   implicit: buying a measurement (priced above), and partner facility
   access through the CRADA under pursuit with DEVCOM. Neither is work
   this project can do by trying harder, and neither is this project's to
   schedule.

3. **Decisions robust to either outcome proceed now.** Geometry, thickness
   and sheet resistance stay measurable on the bench today — by
   microscope, profilometer and four-point probe. These are the
   simulation's *inputs*, not its outputs, and measuring them is a genuine
   provenance upgrade even with the RF ceiling in place. Coupon geometry
   (#106) is the worked example: **≈180 × 180 mm, ≈60 × 60 cells at 3 mm
   pitch**, set by NPL good-practice guidance (specimens "more than 20
   wavelengths across for unfocussed techniques and 6 wavelengths for
   focussed techniques") — correct whether the measurement happens in a
   rented lab, a partner's chamber, or never.

4. **The fixture conclusions this ticket reached need rescoping for a
   two-port measurement, and only for the reproduction anchor.** Example 3
   (US12089385B2) is not ground-backed — Landy et al. suppress transmission
   with a cut wire rather than a ground plane, which is why FIG. 7G plots a
   non-zero `|S₂₁|` transmission trace — so its absorptivity is the full
   **A = 1 − |S₁₁|² − |S₂₁|²**, not the one-port A = 1 − |S₁₁|² the
   ticket's original `.s1p` / "no new format needed" / US$2,300–4,800
   chamber-quote findings assumed. That one-port simplification **is**
   genuinely valid for the programme's own designs, which print their own
   reflector by default (ADR-0017); it was applied by default to somebody
   else's device serving as the blind reproduction target instead — a
   category error recorded as `RUNNING-LISTS.md` §3 correction 25. The
   format and cost work for a two-port free-space measurement needs
   redoing before anyone spends money on it, but that is a shopping
   question, live only once the external dependency resolves.

## Considered and rejected

- **Resolving the fixture/ceiling question immediately, under the
  assumption that the CRADA lands.** Rejected: "deciding the fixture
  strategy under an assumption that may be overturned in weeks would be
  wasted work."
- **Holding the ticket open indefinitely until the CRADA's terms are
  known.** Rejected as equally wasteful — "so would stalling indefinitely
  on an agreement that might not land" — and it would have left the
  decisions robust to either outcome (coupon geometry, measured material
  inputs) undecided for no reason.

## Consequences

- The alphabet's letters (#130) are `SIMULATED`, and the per-letter
  `MEASURED` library — which #131 found has no prior art anywhere — stays
  unavailable until instruments are, whether bought or borrowed.
- **Unblocks, without resolving, #182** (open at time of writing): whether
  `accept_design` should require at least one `MEASURED`-provenance
  `CORRELATION` decision, with a `LITERATURE-SUPPORTED` carve-out (issue
  #116's term) for issue-#133-class instrumentation gaps. #182 is a live,
  undecided item on map #104 — this ADR names the dependency it inherits
  from #133's ceiling but does not adjudicate it.
- The map's *Out of scope* entry ruling out a search for a public X-band
  fixture is **amended, not deleted**: reproducing Example 3 on the real
  machine is the fixture for design purposes; buying or borrowing an
  actual measurement is now explicitly the deferred dependency, not a
  closed door.
- **Explicitly not decided here, and left in the map's fog:**
  - how externally obtained measured data — Landy's, or a bought
    measurement — actually enters ADR-0013's Touchstone intake path;
  - whether the loop should model the eventual fixture at all (free-space
    edge diffraction and finite-sample effects, or a waveguide simulator's
    higher-order modes), and when — contingent entirely on whether
    measurement becomes available;
  - whether the map's Destination wording ("validated by reproducing
    Example 3") needs rewording now that "validated" can, for the
    present, only mean simulated agreement with a published curve, not
    measured agreement.
- This ADR does not decide the CRADA's outcome or timeline. It commits
  only to treating the wait itself as a recorded, named state rather than
  silence.
