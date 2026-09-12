---
status: accepted
---

# The alphabet admits a Reference-Case-backed simulated letter, not only a printed one

Grilling session, 2026-09-12, triggered by a submitted requirement this
programme could not yet answer: a GPS L1/L2 (1575.42 MHz / 1227.60 MHz)
dual-band bandpass filter. The Element/Coding-Alphabet library is empty —
nothing has been printed yet — and ADR-0027 restricts growth to exactly one
route: print it, measure it, then it is a letter. That route needs bench
access this programme does not have today, for a two-layer stacked geometry
nobody has designed yet either. The requirement's owner (Justin McFarland)
decided the programme should instead let an AI propose candidate geometry,
simulate it, and grow the alphabet from simulated outcomes — which only
works if a simulated shape is allowed to become a letter at all.

*In plain terms: the library that's supposed to supply proven building
blocks has zero blocks in it, the only way in requires a printer and a
bench measurement this programme can't yet do, and the GPS filter idea
needs blocks nobody could print anyway (a two-patterned-layer stack is a
new physical design, not a known one). Waiting for hardware to fill the
library first was going to stall this indefinitely.*

## Decision

**This supersedes ADR-0027 section 2** ("Only a printed letter is in the
library; a literature element enters as a candidate, not an entry").

A **Symbol** is admitted as a **Letter** by either of two routes:

1. **Printed and measured** (ADR-0027's original route, unchanged): its
   characterised response carries `MEASURED` provenance, and the entry
   carries a **Process record** — machine, ink, substrate, cure, the works.
2. **Simulated**, new here: its characterised response carries `SIMULATED`
   provenance, produced by a solver path (adapter + problem class) that has
   a passing **Reference Case** for that problem class. The entry carries
   *no* Process record — nothing was printed, so there is nothing to
   record — and that absence is itself how a reader tells a simulated
   letter from a measured one without a new field: **Process record
   present means printed; absent means simulated.** No `generated`,
   `provisional` or similar flag is introduced. CONTEXT.md's Provenance
   entry already forbids a parallel confidence tag, and Process record's
   presence/absence already does this job for free.

**Provenance is never silently upgraded.** A letter admitted on `SIMULATED`
evidence keeps that provenance permanently. The existing **Evidence
hierarchy** (`MEASURED` > `SIMULATED` > ...) already ranks it below any
printed-and-measured entry with no new mechanism required — two letters of
the same shape, one measured and one simulated, are two separate entries
(identity already includes the process per ADR-0027 §4), and whichever one
is asked for by name is the one whose evidence class the caller gets.

**No admission is blocked for lacking a passing Reference Case.** ADR-0028
already settled this programme's general rule — warn, never block — for
every other candidate and warning mechanism in the registry, and a
Reference-Case gate that rejects a candidate outright would be a second,
uncharted exception to it. Instead: a simulated Symbol is admitted either
way, and the entry states, as a plain fact, **which Reference Case (if
any) validated the solver path that produced it**, or that none exists yet
for this problem class. This is the same shape a **Claim limit** already
uses on a Field bundle — a machine-readable statement of what the evidence
does and does not support, attached to the record rather than omitted or
guessed at. A two-layer coupled-FSS Symbol admitted today, before any
Reference Case for that problem class exists, says so on its face; the day
such a case is written and passes, new admissions in that class carry the
fact that they cleared it, and nothing about the earlier entry is rewritten
— it is simply true that it was simulated before validation existed for its
kind, which is a fact about history, not an error to correct.

**Cataloging a run's outcome** (admit as a Letter, keep as a candidate in
the Considered-and-dropped ledger, or drop) reuses machinery that already
exists rather than inventing a percentage:

1. **Threshold** (the Requirement target's hard floor) — a design that
   misses it is not catalogued, whatever its score.
2. **`score_percent` / Success score**, distance to Objective — ranks the
   candidates that clear Threshold. This is the only place a percentage
   appears, and it already existed before this ADR.
3. **The Reference-Case-backing fact above** — recorded, never used to
   block.

*In plain terms: three separate questions, kept separate on purpose —
"does it work at all" (Threshold), "how good is it" (`score_percent`), and
"how much should I trust this number" (Reference Case backing). Collapsing
them into one score would hide which one a bad reading came from.*

## Considered and rejected

- **Requiring a passing Reference Case as a hard admission gate.** This
  session's own first framing of the question. Rejected: it contradicts
  ADR-0028's warn-never-block rule that governs every other admission and
  warning path in this registry, and it would reject exactly the case that
  motivated this ADR — nobody has written a Reference Case for a coupled
  two-layer FSS yet, so a hard gate would leave the GPS filter idea exactly
  as stuck as ADR-0027 already left it.
- **A new `generated`/`provisional`/`simulated` status field on the
  Letter/Symbol record.** Rejected: Provenance's fixed nine-value set
  (already carrying `SIMULATED`) and Process record's presence-or-absence
  already distinguish a simulated entry from a measured one, in two places
  the schema already has. A third, parallel field would duplicate
  information the schema already states — precisely what CONTEXT.md's
  Provenance entry already rules out ("no parallel confidence vocabulary").
- **A raw percentage as the cataloging outcome, with no Threshold and no
  Reference-Case fact.** Rejected: a percentage alone can't distinguish "a
  mediocre design that happens to score 60%" from "a design that fails the
  customer's hard floor," and it says nothing about how much to trust the
  number in the first place. `score_percent`/Success score already exists
  for the ranking half; Threshold and the Reference-Case fact are what a
  bare percentage was missing.
- **Amending ADR-0027 in place instead of superseding it.** Rejected under
  ADR-0020's own test: would the Decision paragraph be rewritten? Yes —
  "only a printed letter is in the library" becomes "a printed letter or a
  Reference-Case-backed simulated letter is in the library." That is a
  changed decision, not a corrected reason, so ADR-0020 requires a
  supersession, not a correction block.

## Consequences

- `CONTEXT.md`'s **Letter** and **Element/Coding-Alphabet library** entries
  are corrected alongside this ADR to drop "only a printed letter is in the
  library" and state the two-route admission rule.
- ADR-0027's front matter is flipped to `status: superseded-by-0053`. Its
  text and reasoning stand untouched as the record of what this programme
  believed in 2026-09 and why — including the passage this ADR reverses.
- **The architecture's headline claim changes, and the change is a real
  loss, named rather than hidden.** ADR-0027 built toward "every letter is
  provably printable," so #130's "an alphabet-built design is printable by
  construction" held for any assembly of letters, unconditionally. That no
  longer holds unconditionally: a design assembled from `SIMULATED` letters
  is not proven printable, only proven-in-simulation. Anything that relied
  on #130's guarantee must now check each letter's Provenance rather than
  assume it — the guarantee becomes "every letter states whether it is
  proven printable, and if not, exactly what backs its number instead,"
  which is weaker but honest.
- **This unblocks the motivating case.** An AI-proposed two-layer FSS
  Symbol for a GPS L1/L2 dual-passband filter can enter the alphabet once
  simulated, without waiting on print/measurement hardware access that
  does not exist for a coupled two-layer geometry today, and without
  waiting on a Reference Case that does not exist yet either — it is
  admitted, and it says plainly that it hasn't cleared one.
- **A later print-and-measure campaign against a `SIMULATED` letter
  produces a new entry, not an upgrade of the old one.** ADR-0027 §3's
  "entries never expire, they stop matching" model already covers this:
  geometry plus process is identity, a `MEASURED` run is a different
  process than a `SIMULATED` one, so it is a second entry that happens to
  share a shape with the first, and the first stays exactly as true as it
  always was about what it is — a simulated result, now joined by a
  measured one.
