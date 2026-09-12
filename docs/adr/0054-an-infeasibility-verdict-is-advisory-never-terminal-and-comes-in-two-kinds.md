---
status: accepted
---

# An infeasibility verdict is advisory, never terminal, and comes in two kinds: bound and exhaustion

Issue #532 (map #530, "Requirement in, verdict out") opened on a gap no
closed decision had actually filled: **no issue in this tracker uses the
word INFEASIBLE**, yet four closed decisions all assume the loop can say
it. #129 wants a bad design told apart from an impossible requirement;
#117 wants an empty candidate set to name which constraint would have to
relax and by how much; #127 wants "cannot work" told apart from "cannot be
evaluated"; #125/ADR-0025 wants a failed night to be a first-class
diagnosed outcome, not an empty list. `orchestration/solver.py` stops for
exactly four reasons today — `target_satisfaction`, `score_plateau`,
`evaluation_budget`, `gated_step_pending_approval` — and none of them
means "impossible." #229 already reports no loop step evaluates a family's
physical bound at all, even though `rf_tools/physical_bounds.py` has
working per-family bound functions (Rozanov for absorbers, Gustafsson &
Sjöberg for reflection-phase steering, Ludvig-Osipov et al. for
`BANDPASS_FSS`) that nothing calls.

The one branch that decided everything downstream of it: whether a bound
check against a *requirement* is the same act ADR-0047 forbade against a
*candidate*. ADR-0047 forbids failing or pruning a candidate whose curve
appears to beat its family's bound, specifically because the bound's own
assumptions (normal incidence, PEC backing, μs = 1) are escapable in this
design space — oblique incidence alone moves Rozanov's allowed bandwidth
by up to 43%, so gating on an apparent violation risks silently refusing a
buildable design. ADR-0047 also rejected hooking a feasibility check into
`REQUIREMENTS`, but only because that step is the loop's own
human-supplied starting input and not one `advance_design_loop_step` ever
advances past — a procedural objection, not a principled one. It never
decided the requirement-level question either way.

CLAUDE.md's warning contract ("warn, never block") and ADR-0028 settle
which way that gap closes: the loop's only hard stop is spending real
material, machine time or money, and a simulated solver run is none of
those. So a bound check has nothing to gate *on* — there is no resource
spend to refuse. That converts what looked like a candidate ADR-0047
question into a report-framing question ADR-0025 already answered once:
ADR-0025 already decided a failed run's report leads with the trade space
— which constraint is binding, what relaxing it would buy. A bound
verdict is that same headline, computed earlier and for a different
reason.

## Decision

**1. An infeasibility verdict is advisory, never terminal.** It never
stops a solver run and never withholds a candidate the run produced.
Instead it becomes the headline of the run's report, in the shape ADR-0025
already structures. A family that runs always returns whatever candidates
it found, verdict or not; the verdict changes what the report leads with,
not what it contains. This is what resolves the ADR-0047 question: since
nothing is refused, pruned, or suppressed, an infeasibility verdict is not
the act ADR-0047 forbids, and needs no exception from it — it is a gentler
act than the per-candidate reporting ADR-0047 already permits.

**2. Two kinds, both issued, distinguished by a `kind` field:**

- **`bound`** — a published per-family physical bound
  (`rf_tools/physical_bounds.py`) forbids the requirement. Computed against
  the requirement itself, once `ARCHITECTURE` has named a family and the
  requirement states a band — before or alongside a run, not after one.
  Its headline: *more search will not help; physics caps this.* Must name
  the assumption set the bound was evaluated under (each bound function's
  own docstring already states its Validity box — normal incidence, PEC
  backing, μs = 1, and so on), which doubles as the `assumed` field
  ADR-0028's warning contract requires, because the same escapable-
  assumptions concern ADR-0047 raised about candidate-level gating applies
  here without change.
- **`exhaustion`** — a run's `stop_reason` is `evaluation_budget` or
  `score_plateau` **and** the batch's ADR-0025 Considered-and-dropped
  ledger shows more than one family or material was actually tried.
  Without the ledger condition, the honest report is "we tried very
  little," not "infeasible" — a three-candidate batch hitting
  `evaluation_budget` is not evidence of anything. Its headline: *we
  searched hard within budget and found nothing; more or different search
  might still help* — the direct contrast with `bound`'s headline.

**3. A third, distinct outcome: unscorable, never reported as
infeasible.** A family stalled at `ANALYSIS` for lack of a closed-form
model (`UndeclaredAnalysisModel`) or a material with no in-band data
cannot be evaluated at all — a different fact from "evaluated and found
wanting." This is the one outcome with genuinely no candidates: nothing
ran. It becomes a first-class output naming which capability is missing
(no analysis model / no material data / no bound formula, per #465)
rather than a raised exception the calling agent has to interpret and
potentially mis-report as infeasible. This ADR settles only the shape of
that outcome. #531's baseline already found two sub-cases with different
costs to fix — `REFLECTION_PHASE` and `DIFFUSIVE` have a working simulator
adapter that is simply never reached, unlike a family with no model at
all — and #482 (open) is already the ticket deciding whether and how the
`ANALYSIS` stall becomes escapable. Not re-argued here.

**4. A contradiction between two requirement rows is out of this
taxonomy entirely.** Two rows demanding mutually exclusive values at the
same operating point (#310) is a pre-flight validation failure — the input
was never coherent — not a claim that physics forbids a coherent ask.
Conflating the two would break the plain-language test this ticket set:
"is this impossible" reads very differently from "you asked for two
incompatible things." #310 (open, already scoped) owns whether and how
that gets caught; not re-argued here.

**5. One shared verdict schema for both kinds:** `kind` (`bound` |
`exhaustion`), the binding constraint named, a margin (nullable — see
point 6), provenance for every number in the judgement, and the ADR-0028
triple (`assumed` / `costs` / `cheapest_test`). A reviewer switching
between design families should not have to learn a new verdict shape each
time; the physics stays inside `physical_bounds.py`, only its output
normalizes into this shape.

**6. A categorical (`ONE_OF`) constraint has no numeric margin.**
ADR-0025 already named this gap without closing it: *"you can measure how
far short of a number you fell; there is no equivalent distance for 'you
only allowed these three materials.'"* The margin field is replaced, for
a categorical constraint, with a per-option reason list — for each option
in the allowed set, why it fails the other binding constraint (e.g.
"graphene ink: no published data above 12 GHz; carbon-loaded PU: measured
but 3 dB short of −10 dB target"). This stays actionable without inventing
a fake distance.

**7. A verdict is scoped to one `(requirement, family)` pair, always.**
It never assumes "the" family for a requirement. #534 (open) is still
deciding whether routing selects one family or runs several in parallel
and compares; a per-pair verdict composes under either outcome —
single-family routing calls it once, multi-family routing calls it once
per family and the reader sees the verdicts side by side.

**8. No new loop state.** A `bound` verdict is computed by the agent (or a
thin helper) calling `physical_bounds.py` directly once `ARCHITECTURE` has
recorded a family and the requirement has a band — no new `DesignStep`,
`GATED_STEPS` unchanged. An `exhaustion` verdict stays a read of the
existing `solver.py` `stop_reason` plus the ledger, computed by whoever
composes the run report — no fifth `stop_reason`, the four existing values
unchanged.

**9. `cheapest_test` may legitimately name a measurement nobody can
currently take.** Under the `SIMULATED` provenance ceiling (ADR-0046, no
VNA, no fixture), this will be common, not exceptional. That is CLAUDE.md's
"when stuck, name the missing measurement" — not a defect to paper over
with a substitute that is actionable today but dishonest about what would
actually settle the question.

## Considered and rejected

- **Terminal infeasibility** — stopping the run and returning only the
  verdict, no candidates. Rejected: nothing about a simulated run triggers
  ADR-0028's hard stop, so there is no resource-spend justification for
  refusing to run, and doing so anyway would silently throw away whatever
  the run could still have found — the exact failure mode ADR-0047 already
  named as worse than over-advising.
- **Amending ADR-0047 directly**, on the theory that a requirement-level
  bound check is a correction to what it settled. Rejected: ADR-0047 never
  decided the requirement-level question — it rejected a `REQUIREMENTS`-step
  hook for a structural reason unrelated to this one — so there is nothing
  in it to amend under ADR-0020. A new ADR that cites ADR-0047's
  escapable-assumptions precedent is the accurate relationship.
  This ADR also does not correct or supersede anything #104 settled on its
  own route; it extends ADR-0025's report structure and cites ADR-0047,
  neither of which it contradicts.
- **A fifth `solver.py` stop_reason for exhaustion, or a new `DesignStep`
  for the bound check.** Rejected: both verdicts are computable from
  information the loop already has (the existing four stop reasons, the
  existing ledger, the existing per-family bound functions) without adding
  state machinery. Keeping the surface small keeps the follow-up
  implementation ticket small.
- **Resolving #310's contradiction case or #482's escapability question
  inside this ADR.** Rejected: both are already open, already scoped
  tickets with their own decisions to make; re-arguing them here would be
  exactly the "quiet divergence" the map's Notes warn against, since
  neither is a decision #530 needs to make to close #532.
- **A single scoring bar for exhaustion (hitting `evaluation_budget` or
  `score_plateau` alone).** Rejected: a lazy, tiny batch can hit either
  reason and would be indistinguishable from a thorough search without the
  ledger condition, understating how little was actually tried.

## Consequences

- A follow-up `wayfinder:task` ticket implements the wiring: a verdict-
  construction function plus its two call sites (a post-`ARCHITECTURE`
  bound check via `physical_bounds.py`, and exhaustion-verdict composition
  in the run report via `solver.py`'s `stop_reason` and the ledger). No
  `DesignStep`, `GATED_STEPS`, or `stop_reason` changes are needed, per
  point 8.
- `physical_bounds.py` needs no interface change — its existing functions
  (e.g. `rozanov_max_fractional_bandwidth`, `ThinSkinWindow.is_empty`)
  already return the raw numbers a `bound` verdict normalizes; this ADR
  does not specify the verdict dataclass itself, leaving that to the
  implementation ticket.
- CONTEXT.md gains two new terms: **Infeasibility verdict** and
  **Unscorable**, filed alongside **Run report** and
  **Considered-and-dropped ledger**.
- **ADR-0025's own "Consequences" section is stale on one point**, and is
  corrected by this ADR rather than silently left to mislead a future
  reader: it names `orchestration/tooling.py:237`'s hardcoded
  `"alternatives": []` as a blocking prerequisite for its own
  Considered-and-dropped ledger. That line was fixed by #205 (closed,
  completed) — `tooling.py` now reads `decision.input.get("alternatives",
  [])` and carries `considered_and_dropped` through unchanged. The
  `exhaustion` verdict's ledger condition (point 2) therefore rests on
  working machinery, not a broken one; see the correction appended to
  ADR-0025.
