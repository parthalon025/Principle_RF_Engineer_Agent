---
status: accepted
---

# The morning report leads with the trade space and records what was not tried

Issue #104's wayfinder map ("Printed metamaterial EM skin design loop")
sanctions two operating modes, the second an *unattended overnight* run
with a morning review, on the standing condition that everything decided
alone is "reversible and recorded." Ticket #125 ("What does an overnight
run hand the morning reviewer?") is the decision about what that morning
review actually sees. Grilling it against the code — rather than against
the planning docs, per `CLAUDE.md` — moved the question a long way from
where the ticket left it.

**Four findings reframed the ticket.**

*One: there is no unattended mode.* A search of every `.py` in the tree
for `unattended|overnight|morning` returns a single hit, a comment in
`tests/test_design_loop.py:71`. The mode is an intention recorded on the
map, not code. This ADR therefore designs the report and the run
together, rather than fitting a report to something already rigid.

*Two: the loop never prunes, because it never chooses.*
`run_candidate_search` receives its candidates as an argument
(`orchestration/solver.py:875`), drives every one inside the evaluation
budget, and appends a trail entry for each (`:1123`). It discards
nothing. The narrowing this ticket feared happens **upstream, in the LLM
role that composes the candidate list** — outside every module in the
repository, leaving no trace. *In plain terms: the record can tell you
what was tried and how it scored, and cannot tell you about the option
nobody put on the list.* No amount of instrumenting the solver reaches
it; the record has to be written at the moment of choosing.

*Three: the report is spoken, not written.* The `report` dict, including
its full `trail`, is a return value handed back to the calling agent and
never written to `designs.db`; only decision records and engineering
results are flushed. *So the night's reasoning currently lives in a chat
session and ends with it.*

*Four: the surface is larger than one boundary.* This repository is a
working integrated program — 82 MCP tools (`mcp_server/server.py`), six
LLM agent roles (Principal plus Systems, Microwave, Antenna, Test and
Verification, `agent/main.py:2285–2627`) against a real model client
(`:313`), with the design-loop tools principal-exclusive and specialists
reached by a one-way sequential handoff (`SPECIALIST_HANDOFFS`,
`:2766`). **No handoff is persisted anywhere**: a search of `designs/`,
`orchestration/` and `db/` returns two hits, both referring to a
*document* called the handoff document in `designs/material_properties.py`.
So a specialist's contribution to an overnight answer is a second
unrecorded decision surface, structurally identical to the first.

The steer that settled the ordering below: the report is judged by
whether it makes the *next* run produce a better design against the
customer's requirement, not by whether it is comfortable to read.

## Decision

**1. The report leads with the trade space; the ranked candidate list is
supporting detail.** #122 established that a requirement carries a
**threshold** (minimum acceptable — miss it and the candidate is out)
and optionally an **objective** (what the customer would actually like),
and that the gap between them is the trade space (JCIDS Enclosure B).
The headline of a morning report is where the best candidate sits
against both, which constraint is binding, and what relaxing it would
buy. *In plain terms: not "here are your top ten designs" but "you need
90% absorption, you are at 94%, you are six points short of what they
asked for, and the 2 mm thickness limit is what is costing you."*
"Best" means what #110 settled it to mean — the single worst-absorbing
frequency inside the required band, never the mean or the peak.

The ranked list is demoted because the ranking is already visible in the
numbers and does not tell a reviewer what to change. #128 is the worked
case: *"the plain carbon square that 'failed' reaches 100% absorption the
moment a customer allows 3.6 mm"* — a design a ranked list would have
shown near the bottom while saying nothing useful about it.

**2. What the run declined to try is recorded at the proposal boundary,
inside ADR-0022's existing batch record.** ADR-0022 already requires a
batch to state a Prediction per candidate and one Mechanism claim, in
the same tool call that launches the run. That record is extended with a
**considered-and-dropped ledger**: per entry, the family, whether it was
kept or dropped, one free-text reason, and a **reason kind** — see the
2026-09-08 correction below, which added that fourth field. No second
mechanism is built; the notebook already sits at the right moment.

The ledger is **structured, not prose**, and thin. The reason is
read-back, not authorship: the rejection memory of ADR-0026 needs a
lookup key, and an agent searching prose for "has this already been
refused" is right most of the time — which is the worst available
outcome, wrong occasionally and silently. A keyed entry is either found
or not. The write cost that would normally argue for prose does not
exist here: an LLM role emits these fields through a typed tool call, so
four named fields cost it no more than a sentence.

**No gate**, per the map's *"the loop fills unknowns; it does not block
on them"* and ADR-0022's own precedent for a missing prediction: a batch
that writes nothing here still runs, and the silence is itself recorded.

*Why this is the lever that matters:* the best achievable answer is
capped by what was tried. A night that considered one material and a
night that considered six produce identical-looking reports today, so a
reviewer cannot tell a thorough result from a narrow guess.

**3. The report is cut by leverage on the result, never by a fixed
count.** The primary axis is what would change the answer; "what changed
since the previous run" is the secondary axis. No top-N.

Two reasons. First, a structural one: an option that was never tried has
no score, so it can never rank into a top-N of scored things — it would
be invisible in exactly the case it matters most. Second, the precedent:
industrial alarm standards (EEMUA 191, ISA-18.2) put a manageable rate
near **1 alarm per 10 minutes**, a figure calibrated to an operator
watching alarms fire live and therefore not transferable to this shape,
and **ISA-18.2 retreated from its own fixed per-day KPI in 2016** while
keeping the underlying principle. *The industry most associated with
fixing alert overload by picking a number publicly gave up on the number
and kept the idea.* The transferable part is that past some volume a
human stops reading and starts rubber-stamping — which is a reason to
cap by importance, not to pick a magic threshold. The diffing half has
its own working precedent in BuildSheriff (ICSE 2022), which compares a
nightly run against a known-good baseline and reports only the delta.

**4. A failed night is the same object with a different stop reason, not
a separate error path.** "No candidate cleared the bar" and "the
constraints admitted nothing" are first-class outcomes carrying a
relaxation report. Some machinery exists: `report["stop_reason"]` and
`stop_detail` (`orchestration/solver.py:1186–1187`) already carry
`evaluation_budget`, `loop_completed`, `gated_step_pending_approval` and
`out_of_scope_step`.

**Scope limit, stated rather than papered over.** "Which constraint
would have to relax, and by how much" is tractable for a **numeric**
threshold — name the binding one and the margin by which it bound — and
is committed here. It is not tractable for a **categorical** constraint
such as #117's `ONE_OF` material list, which has no "by how much" to
report. *You can measure how far short of a number you fell; there is no
equivalent distance for "you only allowed these three materials."* The
categorical case is recorded as a known gap on the map rather than
pretended into the same mechanism.

**5. A specialist handoff is recorded — role, question, answer,
timestamp — and gets no new provenance rung.** Capture only, closing the
second unrecorded surface from finding four, so a wrong overnight number
has a traceable author.

Deliberately *not* promoted to a first-class scored input.
`CONTEXT.md` states that provenance is "a closed set" and that there is
"no path by which an LLM-estimated confidence becomes a `CALCULATED`
one." A specialist agent's answer is an LLM inference and already sits at
the bottom of the evidence hierarchy; minting a rung for it would
quietly promote it. Record who spoke; leave the ladder alone.

**6. The report is a small persisted record, written inside ADR-0011's
transaction.** It stores only what nothing else stores — the batch's
predictions and considered-and-dropped ledger, the recorded handoffs, the
stop reason, and the trade-space diagnosis — and **references** design,
decision and engineering-result rows for everything already persisted
rather than copying them, so the two cannot drift into disagreement.

Because ADR-0011 makes a flush all-or-nothing, this record is written
*inside* that transaction, not appended after it — the same collision
#152 found when it examined a publish/subscribe seam and concluded that
any such consumer must be designed inside the transaction rather than as
a fire-and-forget bus.

The justification for persisting is **cross-run learning, not
auditability**: the third night should start better informed than the
first, which is impossible if each starts blind. That is the same shape
as ADR-0015's Material-property library and the cache #151 is weighing.

## Considered and rejected

- **A ranked list as the headline.** Rejected: the ranking is already
  legible in the numbers, and it is silent on the one thing a reviewer
  acts on — what to change next. #128's carbon square is the
  demonstration.
- **A top-N cap on the review surface.** Rejected on the structural
  ground above (an untried option has no score and cannot rank) and on
  ISA-18.2's own retreat from a fixed figure.
- **Rebuilding the report on demand from existing rows, owning no
  storage.** Genuinely attractive — cheaper, and incapable of
  disagreeing with the database. Rejected because most of what this
  decision needs to show is not in those rows (findings two and three);
  a view can only render what already survives, which is the defect
  rather than the fix.
- **A prose "what I didn't try" note.** Rejected: unqueryable, so
  ADR-0026's rejection memory cannot read it back reliably, and the
  write-cost advantage that would justify it does not exist under a
  typed tool call.
- **Giving a specialist's answer its own provenance rung.** Rejected as
  a parallel confidence scale in the making, against `CONTEXT.md`'s
  closed set and the map's "one vocabulary for confidence."
- **Instrumenting the solver to detect pruning.** Rejected as
  unworkable, not merely inferior: the solver does not prune, so there
  is nothing there to observe.

## Consequences

- **A prerequisite blocks the rejection half.**
  `orchestration/tooling.py:237` hardcodes `"alternatives": []` for
  every `architecture_decision` and `redesign_decision` it persists,
  regardless of what the step input carried, so rejected options are
  discarded at the flush rather than merely unindexed. Filed as its own
  `ready-for-agent` issue; ADR-0026 cannot function until it lands.
- **`solver.py` returns once and stops.** LLM re-entry between batches —
  already noted on the map as the genuinely new loop behaviour — is a
  precondition for a multi-batch night, and is implementation work this
  plan-only map hands off.
- This ADR designs an artifact for a mode that does not yet exist. That
  is deliberate (finding one), and it means the implementation ticket
  covers both.

## Corrections

### 2026-09-08 — a ledger entry must say what *kind* of reason it carries, or a capability verdict freezes into a permanent one

**What this ADR said:**

> That record is extended with a **considered-and-dropped ledger**: per
> entry, the family, whether it was kept or dropped, and one free-text
> reason.

**Why three fields are not enough.** Those fields are correct for a
*human* decision, and wrong for a *machine* verdict, because ADR-0026
lets a later run read the ledger back to avoid re-proposing something
already refused. A shape dropped because its features fall below the
printer's feature floor lands in the ledger looking exactly like any
other rejection — so a later run would skip it **even after a finer
printer is in the room**.

That directly contradicts **ADR-0021**, which makes fabricability a
verdict evaluated per requirement against the *configured* capability at
scoring time, one that *"changes by itself if a capability is added"*,
and **#108**, which settled that *"band and fabrication capability are
both per-requirement/per-config inputs, never constants"* across three
independent stages (print / cure / laminate). *In plain terms: equipment
changes, and a note saying "we couldn't build this" must expire when the
machine that couldn't build it is replaced.*

**What is true instead.** A ledger entry carries a fourth field, its
**reason kind**, one of:

- **`human-decision`** — a person refused it. Carries forward
  permanently, under ADR-0026's named exception.
- **`capability-verdict`** — the configured fabrication capability
  cannot build it today. **Never read back as settled**; re-evaluated
  against the current capability on every run, per ADR-0021.
- **`engineering-judgment`** — the proposer set it aside on technical
  grounds. Carries forward *with its reasoning attached* and is
  overridable, since it is neither a person's decision nor a machine's
  measurement.

**The payoff beyond correctness.** The field makes the
equipment-change question answerable by query: *list every entry ever
dropped as a `capability-verdict`* is exactly the worklist of what a new
machine unlocks. Without the field that list cannot be reconstructed,
because the reason it would filter on was never recorded as data.

This is an **amendment, not a supersede** (ADR-0020): the decision — a
structured ledger written at the proposal boundary — stands unchanged.
It gained a distinction it was missing.

### 2026-09-09 — `capability-verdict` never meant equipment; the 2026-09-08 correction's fabrication mapping contradicted ADR-0021

**What the 2026-09-08 correction said:**

> - **`capability-verdict`** — the configured fabrication capability
>   cannot build it today. **Never read back as settled**; re-evaluated
>   against the current capability on every run, per ADR-0021.

**Why that was wrong, not just incomplete.** ADR-0021 decided the opposite
of what this correction cited it for: *"A candidate the configuration
cannot build in this pass is reported in the ranked output with its
reason attached... not deleted from it."* Mapping `capability-verdict` — a
`dropped` verdict, one that removes a family from the batch — onto exactly
the case ADR-0021 says must never be removed is a direct contradiction,
not a refinement of it. It surfaced during `/grill-with-docs` on ADR-0030,
which separately needed `capability-verdict` to also cover a family
excluded for exceeding its element's angular stability limit at a stated
curvature — two different triggers sharing one label, neither of which,
on inspection, was the fabrication-equipment case the 2026-09-08
correction actually named.

**What is true instead.** `capability-verdict` means exactly one thing: a
family is outside its own characterized **Validity box** for what the
requirement states — today, that's a curvature exceeding
`S ≤ 2·θ_max·R`. It re-evaluates against the requirement's own stated
properties, never against shop equipment. A shop not currently having the
ink, material, or printer resolution a family needs is a **Capability
warning** instead — a new, separate mechanism (see `CONTEXT.md`) that
states the gap in `Requirement target` shape and never drops the
candidate, which is what ADR-0021 required all along.

**The payoff.** The equipment-change worklist this correction originally
promised ("list every entry ever dropped as a `capability-verdict`...
exactly what a new machine unlocks") was itself built on the
contradiction — a machine unlocking a family it previously couldn't build
should never have removed that family from a report in the first place.
The real worklist is now built from unresolved Capability warnings, not
from ledger exclusions.

This is an **amendment, not a supersede** (ADR-0020): the ledger's
structure — a family, a kept/dropped flag, a reason, a reason kind —
stands unchanged. What changed is which situations `capability-verdict`
may describe.
