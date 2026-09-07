---
status: accepted
---

# An LLM-proposed candidate states its prediction before the fast tier evaluates it, and no gate enforces it

Issue #104's wayfinder map already sanctions running the design loop
unattended overnight, on one stated condition: *"everything decided alone
must be reversible and recorded."* Issue #194 grilled what that recording
has to contain for the fast tier — the `ANALYSIS`/`SIMULATION`/
`OPTIMIZATION` span `orchestration/solver.py` drives without a human — and
found the gap. The loop already writes down what it expects before it pays
for a bench trip (`orchestration/lab_test_plan.py`, so that a trip
"confirms or refutes a stated prediction instead of being a fishing
expedition"), and `CORRELATION` scores that prediction against the
measurement afterwards. It writes down nothing before an evaluation that
costs a millisecond of arithmetic — which is where essentially all of its
guessing happens.

**Decision: a batch of LLM-proposed candidates carries a Prediction per
candidate and one Mechanism claim for the batch, recorded in the same tool
call that launches the run, and nothing refuses to run without them.**

*In plain terms: the machine writes down its guess, and its reason for
guessing, before it looks at the answer — and if it doesn't, the run
happens anyway and the silence is itself recorded.*

Three parts, each load-bearing:

**The record travels in the proposal.** `run_candidate_search` already
accepts an optional per-candidate `"note"`, already carried through as
`note_provenance="INFERRED"`. That slot becomes structured. Doing it this
way is not merely the smaller change: the ordering property — that the
prediction existed before the result — is then enforced by the shape of the
call itself, with no moment at which a prediction could be written after
the answer is known. A separate pre-registration step was considered and
rejected below.

**Two things are predicted, not one.** A **Prediction** is a value for the
quantity the Success score will measure — for an absorber, the single
worst-absorbing frequency in the required band (#110's minimax rule). A
**Mechanism claim** is the batch's stated reason, written as a testable
ordering ("the shortest candidate scores worst"). Predicting values alone
would miss the failure worth catching: a batch where every value lands
inside tolerance and the stated reason was still wrong. Being right and
being right *for the right reason* are different, and only the second
compounds across iterations.

**No gate.** #104's standing preference is that *"the loop fills unknowns;
it does not block on them,"* and the owner's steer on #194 was explicit:
better to fail with actual testing than to be too conservative. A candidate
proposed with no prediction records `no prediction stated` and runs. The
absence is a datum the morning review sees, not a refusal.

That last part is the one most likely to be misread as an oversight, so
state it the other way round: **the record is not a brake on failing fast,
it is what converts failing fast into learning fast.** Four hundred failed
candidates with nothing attached cannot be sorted into a physics failure, a
bad guess, and a broken evaluator. Four hundred carrying "expected 82, got
47, because I thought the gap dominated" can. Removing the gates makes the
record more load-bearing, not less.

## Why a second status axis, when the project has one confidence scale

#104 states flatly that `CONTEXT.md`'s provenance ladder is the only scale
and there is to be no parallel "provisional"/"beta" tag. **Prediction
status** (`PREDICTED` → `CONFIRMED`/`REFUTED`, plus `UNSCOREABLE`) is
admissible because it is not a confidence scale:

> **Provenance answers "how do we know this." Status answers "has anyone
> checked."**

Those are different questions about the same value, and the project has
already separated them once, for the same reason: a Requirement target is
permanently `ASSUMED` no matter how many humans confirm it, and
confirmation rides on `target_status` instead of inventing a stronger
provenance tier. A Prediction is permanently `INFERRED` on identical logic
— an LLM's reading of the physics is not evidence, and it does not become
`CALCULATED` because the solver later computed a matching number. If that
distinction ever stops being statable in one sentence, the axis has become
a parallel confidence scale and should be dropped.

## What makes a Prediction `REFUTED`

Its own stated tolerance, bounded by one rule: **a Prediction's tolerance
must be narrower than the decision it informs.** Against a 90% absorption
threshold, "82 ± 15" cannot separate a pass from a fail; it is
`UNSCOREABLE` by construction, never `CONFIRMED`.

The rule exists to close an obvious hole. A model that learns `REFUTED` is
bad can make itself unfalsifiable by widening its bands, and nothing else
in the design would notice. The countermeasure is to record the tolerance
*width* as its own reviewable number, so a widening trend appears as a
trend in the morning review rather than as a discovery months later.

Judging misses against the evaluator's own error bar instead — which would
separate "the LLM guessed badly" from "the model is wrong" — is the better
rule and is deferred, not rejected: #190 records that the fast tier's error
bar does not yet exist.

## What a miss may influence

- **The next batch's proposals: yes.** The LLM reads its own miss record
  before proposing again. This is the entire payoff, and it is not a thumb
  on the scale (#104): it changes *what gets proposed*, never *how a
  proposal is scored*. **The two must not be collapsed**, and this sentence
  exists so that a later reader cannot claim the distinction was never
  drawn.
- **The running residual: computed and reported on every candidate**, free,
  immediately, visible in the morning review.
- **The evaluator's published accuracy claim: only by human decision.** An
  evaluator that widened its own error bar from its own misses would
  absorb #190's known one-sided bias into a wider bar instead of exposing
  it. The loop should keep saying "I am off by 12% and always in the same
  direction," not quietly start claiming ±12%.

Consistent with #112, which already made a Success score a frozen snapshot
and its provenance profile display-only.

## Considered and rejected

- **A required argument that refuses to run without a prediction.**
  Recommended during grilling and withdrawn: it contradicts #104's
  fill-don't-block preference, and an optional discipline enforced by a
  gate produces a dataset with a hole shaped exactly like the cases where
  the model was least confident — which is the opposite of the intent.
- **Predictions as the price of unattended re-entry.** A softer version of
  the same gate, withdrawn for the same reason. The freedom being bought
  here is the LLM re-entering the loop between batches without a human
  turn; charging for it in refusals rather than in records reintroduces the
  bottleneck the overnight mode exists to remove.
- **A separate pre-registration step mirroring `lab_test_plan.py`.**
  Architecturally cleaner and it mirrors a pattern the project already
  trusts — but it adds a call that can be skipped, and pre-registration
  that is optional is not pre-registration.
- **Deriving predictions with a second LLM pass after the results are in.**
  Asking a model to reconstruct what it "meant" once it has seen the answer
  is precisely the failure this decision exists to prevent.
- **Storing no status at all**, freezing the predicted and actual values and
  leaving "was it right" to subtraction. Recommended during grilling and
  overruled by the owner in favour of the explicit vocabulary. The
  recommendation's concern — that a stored derived flag can go stale —
  is answered by the values themselves remaining frozen alongside it.
- **A cheap-model tier below the main model.** No fast/slow LLM split
  exists to extend: one model serves all six agent roles
  (`agent/main.py`), and the only small model in the tree is routed by
  data sensitivity, not cost (ADR-0004).

## Consequences

- **Unlimited failure in software; the gates at the bench are unchanged.**
  A failed fast-tier candidate costs milliseconds. A failed coupon costs a
  ≈180 × 180 mm print, machine time, materials and calendar days (#106).
  That asymmetry is why `MEASUREMENT` is gated and the solver's span is
  not, and the fail-freely steer applies only to the first. `GATED_STEPS`
  and ADR-0014 are untouched.
- **The fast tier is currently a biased ruler, and this decision runs
  against it deliberately.** #190 records an unrecovered term in the
  adopted closed-form model that biases predictions in a known direction on
  exactly the designs in play. Running freely risks learning a bias as
  physics — but volume is also the only way to *measure* a one-sided bias,
  and its direction is predicted in advance, which makes the running a real
  test. Conditional on every fast-tier number carrying that bias in its
  **Validity box**, so nothing downstream reads it as unbiased.
- **Both fast tiers are in scope** (#111's Tier A single-solve and Tier B
  alphabet-lookup). Tier B carries a second falsifiable claim Tier A does
  not — superposition itself — whose error bar has no prior art and must be
  derived; #111 has already chartered that experiment. A discipline with no
  slot for it would be the wrong shape.
- **LLM re-entry between batches is a new loop behaviour** and the one
  genuinely new capability this decision implies. `orchestration/solver.py`
  returns once and stops today.
- This is a plan-only decision (#104's map is explicitly plan-only); no
  code accompanies it. The structured `note` upgrade, the
  `no prediction stated` fill, the residual report and the re-entry
  behaviour land as separate issues once the design-loop spec is otherwise
  complete.
