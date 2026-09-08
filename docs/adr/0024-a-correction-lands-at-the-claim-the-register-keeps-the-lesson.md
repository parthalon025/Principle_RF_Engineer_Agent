---
status: accepted
---

# A correction lands at the claim; the register keeps the lesson

`docs/RUNNING-LISTS.md` §3 is this project's ledger of corrected claims, and it works:
forty-one entries, each naming the superseded claim and what replaced it, never deleted.
What has never been settled is whether logging a correction there **discharges** it.

In practice it has been treated as though it does, and that fails in a way the repo can
demonstrate rather than merely fear.

**`docs/absorber-scoring-conventions.md` still asserts, on `main`, that the reproduction
anchor is ground-backed** — at lines 14, 48, 62 and 349, collapsing absorptivity to
`A = 1 − |S₁₁|²` on the strength of it, calling that *"the single most useful simplification
in this document"* and tagging it `LITERATURE-SUPPORTED, and unanimous`. It is wrong;
§3 correction 25 says so in detail, and names two live downstream consequences. **The
document carries no strikethrough, no superseded marker, and no pointer to the correction.**
A reader who opens that file alone gets a false claim wearing a provenance tag and the word
"unanimous," with no way to know.

*In plain terms: the correction was filed somewhere the reader isn't.*

And the register alone does not prevent the error it records. §3 item 13 warned that phase
quantisation is characterised only for beam-forming, "not for absorption or backscatter
reduction, which is what this effort actually optimises." `docs/requirement-derived-thresholds.md`
then records what happened: a ±22.5° beam-forming constant was imported into a backscatter
design anyway, and — its own words — **"the same effort that wrote the warning imported the
convention."**

**Decision: a correction to a factual claim lands in the document that makes the claim. The
register records that the correction happened and what was learned from it; it never
discharges the correction on its own.**

## Why this is a decision and not a restatement

ADR-0020's final Consequence already says findings are *"corrected in `RUNNING-LISTS.md`
**and** the document that carried them."* That clause is right and this ADR does not overturn
it. But it is one half-sentence, filed as a consequence of an ADR about ADR numbering, with no
format attached and no statement of what the register is then **for** — and it is not being
followed. This ADR makes it load-bearing: it names the failure, gives the correction a shape,
and draws the line between the two homes so neither is doing the other's job.

Map #104 already applies exactly this rule to itself: *"This map states every preference
**once, in its corrected form**. Keeping the wrong version alongside the right one on the page
every session must read is how a skim-reader picks up the wrong one."* The map obeys it; the
documents do not. This ADR closes that inconsistency rather than opening a new question.

A small illustration of how quietly the failure spreads: #104 describes §3 as holding
*"Thirty-three of them."* It holds forty-one. The map that states the rule carries a stale
count of the register that records staleness — nobody's fault, and exactly the point. A number
restated in a second place drifts unless something forces it not to.

## The three payloads, which are not the same thing

§3 currently mixes three kinds of entry, and the mixing is why "log it" felt sufficient:

| | What it is | Where it belongs |
|---|---|---|
| **A wrong claim** | correction 4: MXene is 85× lossier than copper → actually ~9× at RF | **Fixed in every document that states it.** The wrong number must not be readable as current anywhere. |
| **A lesson** | "a DC conductivity ratio does not survive to RF once skin effect dominates" | **The register.** It is a class of error, not a number, and it prevents *future* mistakes rather than correcting a past one. |
| **An unresolved state** | item 33: two documents disagree about MXene's skin depth and neither cites a conductivity | **The register.** Nothing is wrong yet; something is *open*. Deleting or "fixing" it would destroy the signal. |

Only the first moves. The second and third are what the register is for, and this ADR does not
touch them.

## This is not duplication

ADR-0020 warns "cross-link, don't duplicate," and this does not violate it. The register entry
is an audit record — that a claim was believed, corrected, when, and on what evidence. The
document is not a second copy of that record; the document is simply **true**. A document
stating the right thing is not a duplicate of a note saying it used to state the wrong thing.

`docs/RUNNING-LISTS.md`'s own accumulation rule — *"a stale entry gets struck through and
dated, never deleted"* — is untouched. **This ADR removes nothing from the register.** It is
purely additive: the correction must *also* reach the claim.

## Format

At the claim, not in a preamble a skim-reader scrolls past. Two shapes, by whether the wrong
version is a live trap:

**Ordinary correction — state only the corrected version.** #104's rule: once, in its
corrected form. The register holds what it replaced.

**When the wrong version is re-derivable, one line at the claim.** Some errors regenerate: a
reader with a conductivity table will re-derive the DC ratio and get 85× again. There the
corrected claim carries its own inoculation, inline:

> ~9× versus copper at 10 GHz. *(A DC conductivity ratio gives ~85× and is wrong — above
> ~3 skin depths surface resistance goes as 1/√σ. `RUNNING-LISTS.md` §3 correction 4.)*

The test for which shape: **would a competent reader, working from sources, arrive at the wrong
version again?** If yes, inoculate. If no, state the corrected claim and let the register hold
the history.

A document whose *conclusions* rest on the corrected claim needs more than a line — it needs
its conclusions re-derived, or a header saying which of them are now unsupported.
`absorber-scoring-conventions.md` is that case: correction 25 names #133's fixture, format and
cost conclusions and #129's Rozanov headroom as both scoped on the wrong premise.

## Considered and rejected

**Register-only, as today.** Rejected on evidence, not principle: the register did not stop
item 13's trap from being walked into by the same effort that wrote it, and
`absorber-scoring-conventions.md` has carried a false claim, unmarked, since correction 25 was
written. A rule that requires every reader of any document to have first read a 664-line
register is a rule about reader diligence, and this repo has already recorded three separate
occasions where diligence was the thing that failed.

**Strikethrough in place, keeping both versions.** This is what
`docs/HANDOFF-metamaterial-printing-grill.md` does. Rejected as the default for exactly the
reason #104 gives — *"keeping the wrong version alongside the right one on the page every
session must read is how a skim-reader picks up the wrong one."* HANDOFF is a legitimate
exception because it is explicitly a historical record of what was believed when, and its own
header says the live map is elsewhere. A working reference document is not that.

**Edit silently and rely on git history.** Rejected for the reason ADR-0020 already gives: a
reader loads the document, not the blame view. Three stale sections shipped in this repo from
that assumption.

**Delete corrected entries from §3.** Rejected outright — it contradicts the register's own
accumulation rule, and an unbroken record of what was once wrong is worth more than a tidy
list. Nothing is removed.

## Consequences

- **A backlog exists and this ADR creates it.** Every §3 entry correcting a claim that some
  document still states needs that document fixed. `absorber-scoring-conventions.md` is the
  known instance; the sweep will find whether there are others, and its scope is a separate
  ticket.
- **`ready-for-agent` work that touches a document with an open §3 correction fixes it, or
  says why not.** Otherwise the backlog is created and never worked.
- **A correction that changes an accepted decision still follows ADR-0020**, which governs
  decision records. This ADR governs everything else — findings, measurements, what a paper
  says — and the two do not overlap.
- **The register gets *more* useful, not less.** Once corrections live at their claims, §3 is
  read for what it is uniquely good at: the lessons and the open states. Today those are
  buried among stale-number entries that should have been fixed at source.
