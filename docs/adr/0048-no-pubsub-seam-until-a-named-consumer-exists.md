---
status: accepted
---

# No publish/subscribe seam on the persistence boundary until a real consumer exists, and any future one lives inside the ADR-0011 transaction

ADR-0011 drew one clean persistence boundary: `orchestration/design_loop.py`
stays a pure state machine, and every write lives in
`orchestration/tooling.py`'s `_flush_decisions`, fired at each
REDESIGN_DECISION boundary. Ticket #152 ("Should tooling.py's persistence
boundary become a publish/subscribe seam before more cross-run memory stores
get added?") asked whether that boundary should generalize into a
publish/subscribe seam ahead of sibling proposals it read as each wanting to
react to *"the same two moments — a CORRELATION result being recorded, and a
REDESIGN_DECISION being made"*: a simulator-trust ledger (#150), a
cross-design geometry cache (#151), and a "rejected-guess" ledger (#125). The
ticket's own worry was that bolting each onto `_flush_decisions` as its own
added call would grow that function into a longer special-case checklist, one
`if` at a time — but it also stated, as a design property to confirm rather
than assume, that such a seam *"doesn't give a subscriber any power a direct
call didn't already have (no subscriber may block or alter the flush it's
reacting to)."*

A 2026-09-05 research pass (`docs/grilling-pass-2026-09-05.md`,
§"#152 — pub/sub seam at the persistence boundary") checked the ticket's
premises against the tree rather than against the proposals themselves, and
three did not survive contact with the code. Of the four consumers the
ticket's case for a seam had accumulated by that point, two — ADR-0015's
Material-property library and an "Element/Coding-Alphabet library" the
ticket credited to ADR-0018 — turned out not to be candidates at all. The
resolution comment (2026-09-06) closed the ticket on those findings.

## Decision

1. **No publish/subscribe seam is built.** A grep across the repository's
   Python and SQL confirms no pub/sub, event-bus, hook-registry, outbox, or
   `LISTEN`/`NOTIFY` machinery exists anywhere today, and none is added by
   this decision. The deferral is not "no, never" — it is "not yet, and here
   is the test for when."

2. **The case for a seam does not hold against the tree as it stands.**
   - **Zero of the named candidate consumers exist in code.**
   - **Two of the four proposed consumers were misidentified.** ADR-0015's
     Material-property library (`designs/material_properties.py:501,554`)
     takes its own `conn` argument on a human-entry path and never routes
     through `tooling.py`'s boundary. The "Element/Coding-Alphabet library"
     does not exist in the repository; ADR-0018 is the design-family
     registry — an open interface for absorber/reflection-phase/patch
     families — and contains none of a coding-alphabet library's machinery.
   - **There is one flush moment, not two.** `orchestration/tooling.py`'s
     `_flush_target_for`/`_flush_decisions` show the only flush firing on a
     REDESIGN_DECISION transition; a CORRELATION decision is **batched into
     that same flush**, never saved separately. The arithmetic behind "six
     future hook-ups collapsing into one seam" reduces to three.

3. **The constraint that outlives the deferral: whenever a seam is built, it
   must live inside ADR-0011's transaction, not beside it.** The ticket's
   proposed design property — that a subscriber "doesn't give a subscriber
   any power a direct call didn't already have (no subscriber may block or
   alter the flush it's reacting to)" — collides directly with ADR-0011's
   fail-loud, all-or-nothing transaction guarantee (`orchestration/
   tooling.py`'s `_flush_decisions`: the whole batch commits or none does). A subscriber that cannot block cannot
   participate in that transaction; one that participates can block. Those
   two properties cannot both hold for the same subscriber, so whenever a
   real consumer first appears, the seam has to be designed **inside**
   ADR-0011's transaction, not as a fire-and-forget bus alongside it.

4. **The Rule of Three governs the timing.** Fowler, attributing the rule to
   Don Roberts (*Refactoring*): *"The first time you do something, you just
   do it. The second time… you wince…"* — the trigger for extracting a
   shared abstraction sits at the third occurrence. This repository has one
   persistence boundary today, with the rest anticipated: below the
   threshold by definition.

5. **The outbox pattern does not apply here.** Richardson's canonical
   formulation scopes the outbox pattern to the dual-write problem —
   atomically updating a local database *and* publishing to an external
   message broker across services. `tooling.py` writes to one database
   inside one transaction; there is no second system to keep in sync.

## Considered and rejected

- **Building a generalized event/subscriber mechanism now, ahead of a second
  real consumer.** Rejected: sizing a pub/sub mechanism around "more stores"
  risks shaping it for consumers that were never going to use it, and none
  of the four proposed consumers currently exists in code, and two of the
  four were never real candidates to begin with.
- **The outbox pattern**, as the standard answer to "a subscriber shouldn't
  block the publisher." Rejected: it solves atomic dual-writes across two
  systems, and this repository has one database and one transaction — the
  case the pattern was not built for.
- **Change-coupling / evolutionary-coupling analysis** (Zimmermann, Zeller,
  Weißgerber & Diehl, IEEE TSE 2005; Gall et al. 1998) as the objective test
  for whether the abstraction is due. Not applied: it is a lagging indicator
  that mines commit history for entities repeatedly changed together, and
  this repository does not yet have the history to mine.

## Consequences

- This does not decide whether the first real consumer — the simulator-trust
  ledger (#150), the design-history cache (#151), or the corpus bridge
  (#153), whichever lands first — would want the *same* subscription
  semantics (ordering, delivery, replay) as any consumer after it, or
  different ones. Sandi Metz's argument is that an abstraction goes wrong
  specifically when only-approximately-similar requirements get forced
  through it via added parameters and conditionals; that question stays
  open, because nobody can answer it until a second real consumer exists to
  compare against the first.
- A future subscriber wanting per-CORRELATION granularity may not get what
  it needs from this boundary at all, because the boundary batches a whole
  iteration's CORRELATION and REDESIGN_DECISION activity into one flush
  rather than exposing CORRELATION as its own moment. That mismatch is not
  solved here; it is named so the next ticket that reaches for this
  boundary does not rediscover it from scratch.
- ADR-0025 already builds on point 3 above: its persisted morning-report
  record is written *inside* ADR-0011's transaction rather than appended
  after it, citing this exact collision as precedent.
- What this does not decide: the internal shape of a future seam (a plain
  callback list, a small in-process event bus, or something else) is left
  unspecified, since no real consumer exists yet to design it against.
