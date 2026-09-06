---
status: accepted
---

# Amend an ADR when the reasoning changed; supersede it when the decision changed

Issue #104's wayfinder map settled that **a decision is an ADR, or a
correction to one**. That rule needs a second half: what happens when an
already-accepted ADR turns out to be wrong. The repo has nineteen ADRs and
has never corrected one, so there is no precedent to follow, and the
question became live the moment ticket #188 found that ADR-0017's
Consequences section rests on a claim that is false.

Two distinct things can go wrong with an accepted decision record, and they
deserve different treatment:

- The **decision** is still right, but a **reason given for it** — a
  consequence, a rejected alternative, a scoping claim — turns out to be
  wrong. Nobody is disputing what was chosen.
- The **decision itself** is wrong, or the world moved, and the project is
  now choosing differently.

*In plain terms: sometimes you made the right call for a reason that
doesn't hold up, and sometimes you made the wrong call. Those need
different paperwork.*

**Decision: amend in place when the reasoning changed; supersede with a new
ADR when the decision changed.**

**Amending** keeps the ADR's number, its `status: accepted`, and its
Decision paragraph untouched. A dated correction block is added naming what
was wrong, what is true instead, and what raised it. The approval the ADR
already carries stays intact, because the thing that was approved has not
moved. ADR-0005 makes decision records the only approval gate, so
re-opening an undisputed decision to fix a footnote would spend an approval
on nothing.

**Superseding** writes a new ADR stating the new decision and flips the old
one's front matter to `status: superseded-by-00NN`. The old ADR keeps its
text: the record of what was believed, and why, is the point. A changed
decision needs a fresh record precisely so the old approval does **not**
silently carry over onto a choice nobody approved.

The test is a single question: **would the Decision paragraph be rewritten?**
If yes, supersede. If the Decision stands and only the surrounding argument
moves, amend.

## Format of a correction block

Appended at the end of the ADR, under its own heading, so a reader who
stops at the Decision never picks up the superseded reasoning by accident:

```markdown
## Corrections

### <YYYY-MM-DD> — <one-line summary of what was wrong>

**What this ADR said:** <verbatim quote of the wrong passage.>

**What is true instead:** <the correction, with its evidence.>

**Raised by:** <ticket, PR, or document.>

**The Decision is unaffected** because <why the choice still stands>.
```

Quoting the wrong passage verbatim matters. `docs/RUNNING-LISTS.md`'s own
practice is that a correction which does not name what it replaces leaves
the reader unable to tell whether their memory of the document is the old
version or the new one.

## Considered and rejected

- **Always supersede.** Clean and uniform, and it destroys the signal.
  A superseded ADR reads as "this was decided differently before", which is
  false when only a consequence was corrected — and it would have retired
  ADR-0017's genuinely-still-correct reflector default over a mistake in a
  scoping sentence.
- **Always amend.** Keeps history in one place, but lets a decision change
  under a record that still shows the original approval. That is exactly
  the failure ADR-0005 exists to prevent.
- **Edit the ADR silently and rely on git history.** Rejected for the
  reason the map already records: a reader loads the document, not the
  blame view. Three stale sections shipped in this repo from exactly that
  assumption.

## Consequences

- ADR-0017 is amended, not superseded, under this rule — its decision
  (print your own reflector, never assume the host is a ground plane) is
  undisputed; only its claim that no transmissive design exists here fails.
- Ticket resolutions stop being the place a decision lives. Under the map's
  rule, a resolution that changes an accepted decision must land as an ADR
  amendment or a superseding ADR, and the ticket links it.
- A correction block is not a substitute for `docs/RUNNING-LISTS.md` §3.
  That file is the ledger of every corrected *claim*, including findings
  and arithmetic that never reached an ADR; a correction block is the
  subset that lands on an approved decision. Cross-link, don't duplicate.
- This ADR governs decision records only. Findings — facts about the world,
  measurements, what a paper says — are corrected in `RUNNING-LISTS.md` and
  the document that carried them, and never needed an ADR to begin with.
