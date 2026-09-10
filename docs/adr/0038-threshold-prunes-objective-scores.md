---
status: accepted
---

# A requirement carries a threshold that prunes and an objective that scores

Issue #117 ("What constraints can a customer requirement carry, and how do
they prune the candidate space?") was the keystone ticket #105 left behind:
#105 settled that MXene is scored on merit with no thumb on the scale, and
that a legitimate preference must enter as an explicit constraint rather
than a scoring bias, and that host surface is a per-requirement input, not
a project constant — but neither half is implementable until the loop has
a constraint vocabulary, and at the time it had none. The ticket asked six
questions: what a requirement can constrain, which constraints prune
versus penalise, where a constraint's provenance comes from, what the loop
does on silence, what it does when constraints admit nothing, and whether
a preference can be stated honestly without becoming a bias.

The resolution adopts the threshold/objective pair from defence
requirements practice rather than inventing a new "constraint" object.
Issue #122 ("How do military requirements documents express a limit, and
what can we borrow?") is the supporting research this decision draws its
vocabulary from — JCIDS Enclosure B and MIL-STD-961E — but #122 is a
finding, not a decision, and does not get its own ADR. A constraint is not
a distinct concept: MIL-STD-961E A.3.16.2 defines "design and
implementation constraints" as "the requirements that constrain the design
and implementation," and NASA practice treats a constraint the same way —
an input that becomes an ordinary requirement. The question this ticket
actually needed answered is not "is a constraint a new kind of thing" but
"what does one requirement carry, and how do its parts behave differently."

## Decision

1. **A requirement may carry two values for the same quantity: a
   threshold and an objective.** The **threshold** is the minimum
   acceptable value — miss it and the candidate is out. **This prunes.**
   The **objective** is the desired value — between the two, closer is
   better. **This scores.** One requirement, two numbers, two behaviours;
   not a separate "constraint" object alongside the requirement. The gap
   between the two values is the **trade space**, and it is where the
   solver actually works. Example: absorption `≥ 15 dB` threshold, `25 dB`
   objective means reject anything under 15 dB and rank the survivors by
   how close they get to 25 dB.

2. **Hardness is asserted, never inferred — by whoever supplies or omits
   the second number.**
   - **Threshold only** → a hard bound. Exceeding it buys nothing, and a
     missing objective is information, not an omission.
   - **Threshold and objective** → a hard floor plus a direction to
     optimise toward.
   - **Both equal** → stated explicitly as `Threshold = Objective`,
     following JCIDS practice, rather than left for a reader to notice the
     two numbers happen to match.
   A reader or a solver is never left to deduce whether a limit is hard.
   Grammar was considered and rejected as the signal for hardness: a real
   specification confines binding text to `shall` (MIL-STD-961E §4.6.6),
   so in scope every requirement reads as mandatory and the verb carries
   no discriminating signal.

3. **An unconfirmed threshold may prune for one pass; only a confirmed one
   prunes for good.** If hardness must be asserted rather than inferred, a
   limit the loop merely inferred from prose has not been asserted by
   anyone and cannot yet carry a threshold's full authority. Refined for
   an unattended run with nobody watching to confirm in real time:
   - A machine-proposed (`PROPOSED`) threshold may remove a candidate for
     the current pass, so the run still narrows and converges.
   - The removal is recorded — what was removed and on what reading — so
     a silent removal is never indistinguishable from a candidate that
     never existed.
   - Each pass re-derives its thresholds from the original requirement,
     never inheriting the previous pass's conclusions, so a guess gets one
     pass of influence and never permanent tenure.
   - Only a human-confirmed (`CONFIRMED`) threshold removes a candidate
     for good, confirmed in the morning review, in batch.

4. **What a requirement can constrain, first-class:** target band; host
   surface and the bend radius derived from it; cure-temperature ceiling;
   total thickness; mass; absorption depth and bandwidth — all expressible
   as threshold/objective pairs. The derivation chain **host surface →
   bend radius → substrate class → surviving conductors** stays a chain,
   and the customer may supply a value at any link; a value supplied
   further down the chain is more specific and overrides what the loop
   would otherwise have derived above it.

5. **Silence is permissive.** No stated host surface means no bend-radius
   threshold, so no substrate pruning, so every conductor stays in play.
   This follows directly from threshold-only-prunes: no threshold, no
   pruning — it is not a separate rule bolted on.

6. **An empty candidate set is a first-class result with a diagnosis, not
   a bare failure.** The trade-space vocabulary supplies the language for
   it: report which threshold would have to relax, and by how much, to
   admit anything.

7. **A preference is expressible honestly as an objective carrying no
   threshold.** "Prefer MXene where it is competitive" becomes: threshold
   `conductor ∈ {MXene, silver, copper}` (nothing pruned among the three),
   objective `MXene`. The loop ranks toward MXene where nothing else
   separates candidates, and the preference is recorded, visible and
   arguable rather than baked into a scoring weight — satisfying #105's
   no-thumb-on-the-scale rule because the thumb is written down as a
   requirement.

8. **Six model changes follow, two of them blocking:**
   - **(Blocking) An optional second value per requirement.** The
     existing `tolerance` field is symmetric and cannot express an
     asymmetric interval with a pass/fail end and a diminishing-returns
     end. It must be optional: MIL-R-7705B (radome spec) carries single
     limits, so a product-specification customer gives one number and a
     capability-style customer gives two.
   - **(Blocking) A `ONE_OF` categorical comparator.** `value` + `unit` +
     `comparator` cannot hold "conductor ∈ {MXene, silver, copper}." This
     adds a new comparator and allows a non-numeric value — a new
     comparator, not a new object.
   - Rationale as a field, recording *why* a requirement exists next to
     the number — what a morning reviewer needs to judge a
     machine-proposed threshold.
   - Verification method, recorded when the requirement is written (how
     it will be proven: test / analysis / inspection / demonstration),
     distinct from provenance, which only exists after a result.
   - Two missing provenance rungs: *demonstration* (real hardware, no
     numbers) and *inspection of realized hardware* — both needed the
     moment the design is used in anger.
   - A provenance rung for heritage: `CONTEXT.md`'s evidence hierarchy
     ranks "internal engineering history," but the provenance enum has no
     tag for it, and "verification by similarity of heritage" currently
     spans three rungs without one of its own.

## Considered and rejected

- **A constraint as a distinct modeled object**, separate from the
  requirement. Rejected: MIL-STD-961E and NASA practice both treat a
  constraint as an ordinary requirement, and nothing here needs a new
  object — a requirement carrying two numbers instead of one is
  sufficient.
- **Prune-versus-score as the primary classification axis** (the ticket's
  original framing). Rejected in favor of the axis defence practice
  actually draws: **performance** ("what result is needed") versus
  **detail** ("how to build it," a pre-made engineering choice the
  customer imposed, per MIL-STD-961E 5.8.1/5.8.2). A requirement set
  containing any detail requirement is flagged a design-constrained set —
  one flag telling a reader the customer has already narrowed the design
  space, which is the visibility #105's no-thumb-on-the-scale rule wants.
- **Requirement grammar (e.g., "shall" vs. "should") as the hard/soft
  signal.** Rejected: MIL-STD-961E §4.6.6 confines all binding
  specification text to `shall`, so the verb carries no discriminating
  signal in a real document.
- **Waiting for a human before an inferred threshold may prune anything**
  (a strict reading of "hardness is asserted, never inferred"). Rejected
  for the unattended overnight mode: that reading would deadlock a run
  with nobody watching. A `PROPOSED` threshold prunes for one pass only,
  recorded and reversible, rather than waiting indefinitely.
- **KPP / KSA / APA tiering**, also borrowed from defence practice.
  Rejected: it ranks how badly failing a requirement hurts a *programme*,
  which is useful for acquisition decisions, not for scoring a single
  candidate. Threshold/objective already carries the pass/fail axis a
  candidate needs; layering a second tiering on top would give two
  vocabularies for one idea.

## Consequences

- The requirement model gains an optional second value and a `ONE_OF`
  categorical comparator as blocking work; rationale, verification
  method, and the two provenance additions (demonstration, heritage) are
  additive and can follow independently.
- ADR-0022's batch record and ADR-0025's morning report both build on the
  threshold/objective vocabulary this ADR establishes — ADR-0025 in
  particular treats the gap between threshold and objective as the trade
  space a morning report leads with.
- **A scope limit is carried forward, not resolved here**: reporting
  "which constraint would have to relax, and by how much" is tractable
  for a numeric threshold (name the binding one and the margin) but not
  for a categorical constraint such as this ticket's own `ONE_OF`
  material list, which has no "by how much" to report. ADR-0025 records
  this explicitly as a known gap on the map rather than forcing the
  categorical case through the numeric mechanism.
- This ADR does not decide the internal schema for the rationale,
  verification-method, or provenance-rung additions (items 3–6 of the six
  model changes) — only that they are needed. Their shape is left to the
  implementation ticket(s) that pick them up.
