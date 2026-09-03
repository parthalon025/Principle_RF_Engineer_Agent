---
status: accepted
---

# The automated propose-then-test solver is a new, additive tool; it never bypasses the design loop's approval gates

The original ask this `/grill-with-docs` session worked from was a
continuous requirement → prototype → external-test → iterate loop that
works through candidates toward a goal, surfacing how close each attempt
gets — described during grilling as an "automated problem solver" that
"proposes a solution, then tests it," scoring each attempt with "a
percentage of success." This ADR records the shape that settled into.

**It is a new, separate agent/MCP tool, not a modification to
`orchestration/design_loop.py`'s existing 9-step state machine.** The
9-step loop (`REQUIREMENTS → ARCHITECTURE → ANALYSIS → SIMULATION →
OPTIMIZATION → VERIFICATION → MEASUREMENT → CORRELATION →
REDESIGN_DECISION`), its handlers, and `GATED_STEPS` are untouched by this
decision. The new tool orchestrates that existing loop from outside it: the
LLM proposes a candidate, the tool drives the proposal through the loop's
already-ungated steps (`ANALYSIS`/`SIMULATION`/`OPTIMIZATION`) to test it,
and surfaces a score.

**Corrected after implementation (issue #95):** this paragraph originally
named `CORRELATION` in that span as well. It is not, and the narrowing is
load-bearing rather than an oversight, so the ADR is amended here rather
than left to read as a dropped requirement. `CORRELATION` compares a
simulated result against a *measured* one, so the solver could only reach
it two ways: after a real `MEASUREMENT` decision, which is gated and needs
the lab trip the solver exists to defer — making it moot — or via a
caller-supplied `measured=` override, which would let an agent hand the
loop "measured" values that never passed through the `MEASUREMENT` gate.
The second is a softer, easier-to-miss version of exactly the bypass this
ADR forbids: no receipt is forged, but unapproved evidence enters the
design's record anyway. Excluding `CORRELATION` from the solver's span
closes that path by construction. Note this narrows only what the SOLVER
drives; `CORRELATION` remains a scoreable step (see below) when a human
reaches it through the loop's normal, gated route.

Considered and rejected:
building this as new branches or shortcuts inside `design_loop.py` itself —
rejected because every one of this project's existing design-loop ADRs
(0009, 0010, 0011) and its module docstring already establish that state
machine as a fixed, narrow, deliberately-not-extended contract; wrapping it
is additive, changing it is not.

**The score is a deterministic proximity-to-target number, `CALCULATED`
provenance — never an LLM-estimated confidence standing in for one.** It
measures how close a step's actual numeric result (an achieved frequency, a
simulated gain, an optimized dimension) lands to the customer requirement's
own stated numeric target. This follows directly from this project's
foundational, repo-wide discipline that the LLM is never trusted to do RF
arithmetic (README's evidence hierarchy: `MEASURED > SIMULATED >
CALCULATED > ... > INFERRED > ASSUMED`) — a plausible-sounding LLM-invented
percentage sitting next to genuine `CALCULATED` numbers would corrode the
one property that makes this project's provenance tagging worth trusting at
all. Only a step whose result is numeric and comparable to a stated
requirement target is scoreable this way: `ANALYSIS`, `SIMULATION`,
`OPTIMIZATION`, `VERIFICATION`, `CORRELATION`. `ARCHITECTURE` and
`REDESIGN_DECISION` are human judgment calls with no number to be close to,
and are not scored. An optional LLM-authored narrative note, tagged
`INFERRED`, may ride alongside a score for context a formula cannot capture
(manufacturability risk, fabrication-tolerance concerns) — but it never
substitutes for the number, and is always labeled at its own, lower,
honestly-stated evidence tier.

**The solver never loosens or bypasses `ARCHITECTURE`/`MEASUREMENT`/
`REDESIGN_DECISION`'s existing approval gates.** This was raised and
explicitly re-confirmed during grilling, not assumed: "the original steps
still exist." A candidate the solver proposes and tests still requires the
same real `LoopStepApprovalReceipt` (`orchestration/approval.py`) to
actually advance the loop past any gated step — the solver's score is
decision-support information handed to the human at that checkpoint, not a
credential that substitutes for their approval. Considered and rejected:
loosening `ARCHITECTURE`'s gate specifically, to let the solver auto-try
several candidate architectures in the simulated-only phase and auto-pick
the best-scoring one before a human ever sees the rejected ones. Rejected
because this project's "never allow autonomous manufacturing release"
constraint (README, `docs/BUILD_PLAN.md` Phase 12, ADR-0010, ADR-0011) is
the single most load-bearing, repeatedly-reinforced rule in the codebase,
enforced structurally with a cryptographically-bound receipt rather than a
flippable flag — a new tool built to make design work faster is not
sufficient reason to carve the first exception into it.

## Consequences

- This ADR records a shape decision made *ahead of* implementation — no
  code for this tool exists yet. Implementation is a separate, later step
  that builds against this ADR, not something this session produced.
- The solver tool's own approval surface (if it proposes an `ARCHITECTURE`
  candidate for a human to approve) is the *existing* `request_loop_step_
  approval`/`LoopStepApprovalReceipt` machinery, reused as-is — this ADR
  introduces no new approval-gate design.
- A future feature that wants the solver to try multiple `ARCHITECTURE`
  candidates unattended would need its own `/grill-with-docs` session and
  its own ADR revisiting the rejected alternative above; this decision does
  not pre-approve that path, it forecloses it for now.
