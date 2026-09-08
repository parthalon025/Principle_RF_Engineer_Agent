---
status: accepted
---

# The program warns and proceeds; the only hard stop is spending real material, machine time or money

`/grill-with-docs` on the program's purpose asked what should happen when the
agent is not confident. The alternatives were a refusal rule — withhold any
design whose load-bearing numbers are `ASSUMED` — and a warning rule: hand the
design over and say what is uncertain. **The warning rule is adopted.**

A refusal rule would jam the loop shut for a reason that has nothing to do
with safety. Early-stage numbers *are* assumed; that is what early means. A
program that refuses to speak until its inputs are measured would never
produce a first candidate, which defeats the purpose the charter states
(`CLAUDE.md`, "What this program is for").

**One hard stop survives: nothing that spends real material, machine time or
money happens without a human saying yes.** No print, no order, no release.
This costs nothing today — `orchestration/design_loop.py:94` records
`NO MANUFACTURING-RELEASE PATH`, and `policies/tool_policy.yaml:225` lists
`manufacturing_release` among capabilities that do not exist as implemented
tools — so the rule reserves a boundary rather than accepting a limit. It is
stated as a permanent principle so that a future implementation inherits it
instead of rediscovering it.

**A warning must earn its place.** Three parts, and one firing condition:
what is assumed, what it costs if that is wrong, and the cheapest way to find
out — fired only when the assumption is load-bearing, meaning that changing
it would change the decision. The gating logic does not disappear when the
gates do; it moves into *what gets flagged*. Warning on everything and
warning on nothing are the same outcome, and the first is the more dangerous
because it looks like diligence.

This sits alongside ADR-0022, which already applies the same posture to
predictions: a candidate states its prediction before evaluation, *and no
gate enforces it*.

## Consequences

- The three `GATED_STEPS` in `orchestration/design_loop.py` are **not**
  changed by this ADR. Issue #98 owns that work and says the design must come
  first; this ADR records the decision that should inform it, so the code
  change is tracked rather than arriving as a side effect of a docs commit.
- Warning quality becomes the whole safety story. With no expert review
  downstream (ADR-0009) and no gate to stop a bad candidate, a warning nobody
  reads is equivalent to no warning at all. The load-bearing test is what
  keeps the volume low enough to stay readable, and it is the first thing to
  re-examine if warnings start being ignored.
