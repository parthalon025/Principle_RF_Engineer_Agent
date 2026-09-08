---
status: accepted
---

# The alphabet admits only printed letters, and a letter's identity includes the process that made it

Ticket #207 on issue #104's wayfinder map asks how an element from the
literature enters the symbol alphabet, and when such an import is a new
*family* rather than a new *letter*.

The alphabet was always designed to grow. **#109** makes it a persistent
Element/Coding-Alphabet library; **ADR-0018** makes the family registry
an open interface rather than a hardcoded enum; **#131** established that
the architecture is standard reflectarray practice with published
libraries available to adopt rather than derive. It has already grown
that way once: **#138** imported Withayachumnankul, Fumeaux & Abbott's
interdigital-capacitor ELCs — **2.10–3.14 GHz (1.50×) at an identical
14 mm cell and 12 mm footprint, zero gap excursion**, quantised by
integer finger count — because the patent's own element did not solve the
problem theirs did.

What was never settled is the *pipeline*, and grilling it surfaced three
contradictions in what was already written down.

**One: no invalidation policy exists to copy.**
`docs/element-library-prior-art.md` §6 records it as an outright gap —
published element libraries are implicitly bound to a named laminate
with **no stated rule for what invalidates an entry**, and this repo's
process variables (ink, cure schedule, pass count, ink age, MXene
oxidation) *"have no analogue in etched-copper practice, so no analogue
policy exists to copy. Must derive."*

**Two: `CONTEXT.md` and #132 stated opposite models.** The glossary said
*"a pitch or validity-box change **invalidates** the whole alphabet's
entries, not one symbol's."* #132 said *"this run does not produce
results that later 'go stale'; it produces entries that are **valid for
exactly the conditions they were printed under**, and a different
condition is a different entry."* One expires entries; the other says
they never expire and merely stop matching.

**Three: the library key could not express its own identity rule.** The
key was `(element family, substrate stack, frequency band,
incidence-angle range)`, while #132 defines identity as *"geometry plus
ink plus thickness plus substrate plus band"* and insists *"the same
outline printed in carbon and in MXene is two letters, not one letter
under two conditions."* Those two letters collide on one key. Nothing in
it recorded ink, film thickness, cure, or which machine printed the
entry — so the store could not answer "which entries came from the old
printer," the question that matters the moment equipment changes.

## Decision

**1. #115 owns the constraint; this ADR owns the library.** #115 decides
the numbers (whether 50 µm is feature resolution, placement accuracy or
layer-thickness control; whether `R = 3T` or IPC-2223's 6× governs) and
whether a violating *design* is rejected outright or scored down. This
ADR decides how a *letter* enters the library, what it carries, and what
takes it out. Design-level versus letter-level.

**The consequence must be stated or each ticket will assume the other is
doing the work.** #130's claim is that an alphabet-built design is
*printable by construction*: if every letter printed, an assembly of
letters prints. So for **Tier B**, #115's per-design fabrication check is
a **backstop** — catching placement and registration *between* letters,
not the letters themselves. For **Tier A**, which #130 gives no alphabet
at all, #115 remains the **primary** gate. One check, two different jobs
depending on tier.

**2. Only a printed letter is in the library; a literature element
enters as a candidate, not an entry.** `element-library-prior-art.md` §5
records admission-by-printability as having **no prior art** — the field
admits an element when a simulation converges — and §4 records that a
per-letter `MEASURED` library is likewise unprecedented and is *"the
proposal's strongest single claim, precisely because nobody has done
it."* A library that accepts un-printed entries is just the simulated
library everyone else already has.

So a promising shape from a paper is imported as **the shape and a
hypothesis, never the numbers as an entry**. Its published response was
measured on someone else's substrate at someone else's frequency, so it
fails the validity box by construction. It lives, until printed, in
**ADR-0025's considered-and-dropped ledger** — no new store is built. A
candidate blocked because no configured machine can make it is exactly
a `capability-verdict` under ADR-0025's 2026-09-08 correction, so it
resurfaces by query the day equipment changes rather than being lost.

The library is therefore **openly mixed in what informed it and uniform
in what it holds**: every entry is printed and characterised here, while
the queue feeding it draws freely on published work. #138 is this
working correctly.

**3. Entries never expire; they stop matching.** #132's model is
adopted and the glossary's "invalidates" sentence is corrected to match.
An entry measured on a given ink and machine records something that
remains true about that ink on that machine; marking it invalid destroys
evidence bought with bench time, and answers a question nobody asked.
A configuration that no longer exists simply never matches a lookup.

**The cost is named rather than buried: an equipment change orphans the
whole library at once.** Every letter stays valid, none matches, and the
alphabet is empty until re-printed. Expiry has the identical practical
effect and additionally loses the data, so identity is strictly better —
but neither model spares the re-characterisation campaign. The escape
(a *transfer* rule predicting a new machine's letters from the old ones
plus the process delta) is deliberately not chartered here; see
Consequences.

**4. The process is a first-class object, and the key references it.**
The key becomes `(element family, symbol, band, incidence-angle range,
process)`. A **Process record** holds machine, ink and grade, substrate
stack, pass count, achieved film thickness, and cure schedule.

This names something the map already describes rather than inventing it:
the standing preference states that manufacturing and material figures
are *"measurements valid inside a stated box (pitch, ink, pass count,
cure, grade)"* and that *"quoted without their box they are
assumptions."* **That stated box is the Process record**, and it follows
that a library entry carrying no process reference is an assumption, not
a measurement.

Keeping it as one referenced object rather than four more key fields
keeps the key short, leaves every prior entry intact and queryable when
equipment changes, and makes *"what did we measure on the old machine
versus the new one"* a plain lookup — which is also the only shape in
which the deferred transfer rule could ever be fitted.

**The Process record and the validity box are distinct and must not
merge.** The **validity box** (#130, after Marcuvitz) says where a
response may be *used* — band, incidence angle, neighbours. The
**Process record** says how the artifact was *made*. A letter printed on
one machine and valid across 8–12 GHz carries the band in the first and
the machine in the second. *In plain terms: one says what this thing is
good for, the other says where it came from.*

**5. A new family is decided by function, not by shape.** An import is a
new **family** if and only if it needs a different `physical_bound`,
`optimizer_class` or `simulation_adapter` (ADR-0018's three per-family
plug-ins). Otherwise it is a new **letter**, however unfamiliar it looks.

Munk's four-group taxonomy (centre-connected; loops; solid interior /
plate; combinations) is adopted as *organising* vocabulary and rejected
as the *deciding* test. #129 already established that the bandwidth bound
is a genuinely different function per family — Rozanov for absorbers,
Gustafsson & Sjöberg for reflection-phase steering, and polarisation
conversion has none in the literature at all — and that split does not
follow Munk's shape groups. A shape that looks novel but reuses all three
plug-ins is a letter; a familiar-looking shape needing a new bound is a
family.

## Considered and rejected

- **A library holding un-printed candidates with a status field.**
  Rejected: admission-by-printability is the architecture's
  differentiator (§5, §4 — both unprecedented), and a library that
  accepts simulated entries has given it away for convenience.
  ADR-0025's ledger already holds "considered, not taken forward" with
  a reason kind that distinguishes a capability block from a human one.
- **A separate candidate pool alongside the library.** Rejected as a
  third store duplicating the ledger's job.
- **Expiring entries on a process change** (the glossary's original
  model). Rejected: identical practical effect, and it destroys measured
  data to achieve it.
- **Importing a published element's response numbers directly.**
  Rejected on the validity box: those numbers were measured on another
  stack at another frequency, so they are not about our letter. The
  shape transfers; the results do not.
- **A seven-part composite key** carrying ink, thickness and cure
  inline. Rejected as brittle and unreadable, and it still could not
  express "which entries came from the old machine" as one query.
- **Munk's shape taxonomy as the family test.** Rejected per #129: the
  per-family bound does not follow shape.

## Consequences

- **`CONTEXT.md`'s Element/Coding-Alphabet library entry was stating a
  live falsehood** — the "invalidates" sentence contradicted #132.
  Corrected here, and logged as correction 42 in
  `docs/RUNNING-LISTS.md` §3, per the map's convention that a
  superseded claim is named where corrections live.
- **A transfer rule is fog, not a ticket.** It needs measured data from
  at least two processes to fit or validate against, and there are
  currently **zero** — #132 has not run and is blocked. *You cannot
  learn how results move between machines while you have only ever used
  one.* It becomes specifiable the moment a second process exists.
- **#115's body is amended** to record that library admission moved
  here, so whoever picks it up once #106 lands neither re-derives it nor
  assumes this ADR settled the numbers.
- **#207 blocks #132**, which cannot define its own pass/fail test
  without the admission gate this ADR establishes. The gate's *numbers*
  still wait on #115 and #106.
