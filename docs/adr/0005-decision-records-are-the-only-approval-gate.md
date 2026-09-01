---
status: accepted
---

# Decision records get a human-approval gate; results and verification don't

`designs`, `engineering_results`, `decision_records`, and `verification_items`
are four tables scaffolded since the initial commit but never consumed by any
code. It would be consistent with ADR-0003 (no review gate for component
extraction) to treat all four the same way: write everything automatically,
no human in the loop, confidence expressed through provenance. We didn't.
`engineering_results` (auto-recorded whenever a calculation/simulation tool
runs with a `design_id`) and `verification_items` (explicit
`verify_requirement` calls, `NOT VERIFIED`/`PASS`/`FAIL`/`MARGINAL`) get no
gate — they're evidence, and ADR-0003's reasoning holds: there's no RF
engineer on staff to review a VSWR calculation any better than the
deterministic tool already computed it. `decision_records` is different: a
decision ("used a pi-network instead of an L-network here") is a judgment
call between real alternatives, not a mechanical read with a
physical-plausibility bound to fall back on — there's no honest way to
auto-approve "was this the right trade-off" the way `UNKNOWN` auto-flags a
negative noise figure. So `decision_records.approval_required` defaults
`true` and every new decision starts `approval_status = 'PENDING'`, meant to
eventually block `manufacturing_release` (an existing `tool_policy.yaml`
entry, not yet implemented).

## Consequences

The gate is not yet operative. Nothing currently checks `approval_status`
before anything happens — `manufacturing_release` doesn't exist yet, and the
human-facing way to review and flip a `PENDING` decision to `APPROVED` is
a future UI (tracked on the roadmap), not built in this session. Until both
land, a `PENDING` decision record is a structural fact recorded in the
database, visible only by reading a design back (`read_design`) or querying
directly — not yet a real block on anything. Treat this as a known,
temporary gap, not a finished access-control mechanism.

## Considered options

Gating all four tables identically (full ADR-0003 consistency) — rejected
because "is this decision correct" and "is this extraction/calculation
correct" are different kinds of question; the former has no deterministic
check to substitute for a human's judgment, so removing the gate would mean
removing the only honest signal that anyone should look at it.

Gating none of them (defer approval to whenever the UI exists) — rejected
because recording `PENDING` now costs nothing and means every future reader
of `decision_records` can already tell which decisions were, in fact, never
reviewed, once the gate becomes real.
