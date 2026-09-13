---
status: superseded-by-0053
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

## Corrections

### 2026-09-10 — a machine-blocked candidate is a Capability warning, not a `capability-verdict`

**What this ADR said:**

> A candidate blocked because no configured machine can make it is exactly
> a `capability-verdict` under ADR-0025's 2026-09-08 correction, so it
> resurfaces by query the day equipment changes rather than being lost.

**Why that was wrong.** ADR-0025's own 2026-09-09 correction — filed the
day after this ADR's text above was written, and never propagated back
here — narrowed `capability-verdict` to mean exactly one thing: a family
outside its own characterised **Validity box** for what the requirement
states (today, curvature exceeding `S ≤ 2·θ_max·R`). An equipment, ink or
material shortfall — "no configured machine can make it today" — is a
different case, split out into a separate **Capability warning**
mechanism (ADR-0030) that states the gap without dropping the candidate
from the batch at all.

**What is true instead.** A literature element the shop cannot yet build
does not sit as a *dropped* `capability-verdict` entry waiting to
resurface — under the corrected model it is never dropped in the first
place. It stays a candidate in ADR-0025's ledger, or is scored with a
Capability warning attached, per the requirement-target shape
ADR-0030/ADR-0035 describe. The equipment-change worklist this ADR
promised is built from unresolved Capability warnings, not from ledger
exclusions — exactly as ADR-0025's 2026-09-09 correction already
concluded for the fabrication-equipment case generally.

This is an **amendment, not a supersede** (ADR-0020): the decision that a
literature element enters as a candidate/hypothesis, never as a library
entry, until printed, is unchanged. Only the label naming *why* a
not-yet-buildable element is not yet an entry was wrong.

### 2026-09-10 — the Process record drops two of the six variables this ADR called "must derive", and §5's family test is stale by one plug-in

**The Decision stands, and neither item below moves it.** *"Only a printed
letter is in the library"* is untouched, and so is *"entries never expire;
they stop matching."* Point (a) below is about a **rotting artifact**, and
a rotting artifact argues **for** keeping the day-0 entry, not for deleting
it: if an ink is a different material at six months than it was on the day
it was opened, the entry printed on day 0 records something that is still
true about day-0 ink, and what is missing is the field saying *which day it
was*. Point (b) corrects a count in the family test, not the test's basis
in function-over-shape. Only the reasoning moved.

---

#### (a) The Process record holds four of the six process variables this ADR's own motivation named

**What this ADR said** (§4, and reproduced verbatim in `CONTEXT.md:659-661`):

> The key becomes `(element family, symbol, band, incidence-angle range,
> process)`. A **Process record** holds machine, ink and grade, substrate
> stack, pass count, achieved film thickness, and cure schedule.

**And what this ADR said four paragraphs earlier**, reproducing
`docs/element-library-prior-art.md:356` as the motivation for needing a
Process record at all:

> published element libraries are implicitly bound to a named laminate
> with **no stated rule for what invalidates an entry**, and this repo's
> process variables (ink, cure schedule, pass count, ink age, MXene
> oxidation) *"have no analogue in etched-copper practice, so no analogue
> policy exists to copy. Must derive."*

**Why that was wrong.** The source names **six** process variables — *"ink,
substrate, cure schedule, pass count, ink age and MXene oxidation"*
(`docs/element-library-prior-art.md:356`; this ADR's own parenthetical
reproduces five of them, dropping `substrate`, which the record *does*
carry). **The Process record carries four.** **Ink age and MXene oxidation
are absent** — the two that this ADR itself singled out in bold as having
no analogue in etched-copper practice, i.e. precisely the two that could
not be copied and had to be derived here.

The shipped table confirms it. `db/schema.sql:329-339`:

```sql
CREATE TABLE IF NOT EXISTS process_records (
    id BIGSERIAL PRIMARY KEY,
    machine TEXT NOT NULL,
    ink TEXT NOT NULL,
    ink_grade TEXT NOT NULL,
    substrate_stack TEXT NOT NULL,
    pass_count DOUBLE PRECISION NOT NULL,
    achieved_film_thickness_m DOUBLE PRECISION NOT NULL,
    cure_schedule TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

No ink lot. No receipt or open date. No print date. No measurement date.
The only time in the table is `created_at`, which is a row-insert
timestamp and **makes no claim about the artifact** — a coupon printed in
March and entered in September gets a September stamp, and nothing in the
schema says otherwise.

**What is true instead — and the clean split runs along this ADR's own
line.** §4 already separates *"where it came from"* from *"what it is good
for"*, and the two age questions fall on opposite sides of it:

- **Age-at-print** — how old the ink was when the artifact was made —
  belongs to the **Process record**. It is a fact about how the thing was
  made, alongside pass count and cure schedule.
- **Age-at-measurement**, and any usable shelf life derived from it,
  belong to the **Validity box**. They are facts about where the response
  may be *used*, alongside band and incidence angle.

*In plain terms: "the ink was three weeks old when we printed this" is part
of the recipe. "This measurement is good for six months" is part of the
label. They are different fields on different objects and merging them
would undo the distinction §4 is built on.*

**Urgency, stated honestly and conditionally — this is worth doing cheaply
now, not urgently.** The three configured ACI inks (SS1109 silver, SC1502
carbon, SI3104 insulator) do not measurably rot on this programme's
horizon, so nothing in the shop today is losing data to the gap. MXene is
the material where oxidation is a real, documented mechanism, and MXene is
**not stocked, not on Voltera's ink list, never printed on a NOVA**
(`docs/mxene-voltera-nova-printability.md` §6) and has **no row in the
shipped material-property seed data** — it is a candidate ADR-0044 keeps
live and scored on merit, not a material in inventory. So the cost of
waiting is currently near zero.

**What is not near zero is the cost of waiting past the first print.**
These fields **cannot be retrofitted onto a coupon that has already been
printed**: nobody can recover in October how old the ink was in September.
That is the whole argument for landing them before **#132**'s
characterisation run puts anything on a substrate — a cheap schema change
now, or an un-closable hole in the first entries the library ever holds.

**Raised by:** [#447](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/447)
("Does a library entry record when it was made, and how old it was when it
was measured?").

---

#### (b) §5's family test names three per-family plug-ins; the shipped registry has four

**What this ADR said:**

> **5. A new family is decided by function, not by shape.** An import is a
> new **family** if and only if it needs a different `physical_bound`,
> `optimizer_class` or `simulation_adapter` (ADR-0018's three per-family
> plug-ins). Otherwise it is a new **letter**, however unfamiliar it looks.

**Why that was wrong.** `DesignFamily` carries a **fourth** per-family
slot, `analysis_model` (`designs/design_families.py:316-347`). It is not
optional and not incidental — it is **required with no default,
deliberately**, and the code says why:

> Required, with no default, deliberately (#239): a family that forgets to
> state which analysis it needs cannot be constructed at all, rather than
> quietly inheriting another family's model.

The same file's docstring already lists all four together — *"the
family-specific parts (`physical_bound`, `analysis_model`,
`optimizer_class`, `simulation_adapter`) are declared as open values"* —
so the registry has been four-slotted since #239 and §5's *"if and only
if … three"* has been stale ever since.

**What is true instead.** §5's operative text is now:

> An import is a new **family** if and only if it needs a different
> `physical_bound`, `analysis_model`, `optimizer_class` or
> `simulation_adapter` (ADR-0018's per-family plug-ins, four as of #239).
> Otherwise it is a new **letter**, however unfamiliar it looks.

**This is not bookkeeping — the missing fourth slot has a live victim.** A
transmit-type bandpass FSS — a radome, a radar-transparent window — reuses
**all three of the named plug-ins**: it needs no different
`physical_bound` (a transmissive screen's thickness/bandwidth bound is
`UnreadPhysicalBound` here, exactly as `ABSORBER_TRANSMISSIVE`'s already
is), no different `simulation_adapter` (a periodic unit cell needs
`MEEP_FLOQUET` either way), and no `optimizer_class` at all (neither has
one). **So the test as written files it as a *letter* under
`ABSORBER_TRANSMISSIVE`** — whose `analysis_model`,
`TRANSMISSIVE_ABSORBER_BAND_RESPONSE`, scores *"what fraction of the
incident power this surface turns into heat at the single worst frequency
in the required band"*, i.e. worst-in-band **absorptivity**.

A radome wants transmission **maximised** and absorption **minimised**. So
the loop would **rank the best radome last** — the same shape of
confidently-wrong number #239 exists to prevent, one family over.

**The arithmetic, on the real measured case.** A screen-printed Ti₃C₂Tₓ
chessboard FSS reported at X-band average radar **transmittance 78%** and
**reflectivity as low as 16%** (*J. Alloys Compd.*, PII S0925838826025946;
recorded on [#453](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/453),
provenance `UNVERIFIED` — the primary paper has not been read here) has
absorptivity

```
A = 1 − |S₁₁|² − |S₂₁|²  =  1 − 0.16 − 0.78  =  0.06
```

Scored against the field's **−10 dB / A ≥ 0.900** absorber default
(`docs/absorber-scoring-conventions.md` §2, §11 — the two are the same
number when transmission is zero), **A = 0.06 reads as a catastrophic
failure: 6% of the bar.** It is in fact a near-ideal radome — 78% of the
radar energy goes straight through, which is the entire point of the part.

*In plain terms: a radar-see-through window and a radar absorber want
opposite things. One wants the energy to pass; the other wants it eaten.
Measuring the window with the absorber's ruler says it eats 6% of the
energy when it needs to eat 90%, and marks it a near-total failure — when
6% eaten is exactly what a good window does.*

**Why a reader could not have known.** Before this correction block,
`analysis_model` **appeared in no ADR and in no `CONTEXT.md` entry** —
grep across `docs/adr/` and `CONTEXT.md` returned zero hits in either, and
this block is now the first mention in any ADR. A reader applying the documented test
has no way to learn a fourth slot exists; the only place it is written down
is the dataclass. Which is why the amendment lands, and why the vocabulary
gap is worth closing separately.

**Deliberately not amended alongside this: ADR-0018.** It would be easy to
assume the same staleness reaches back to the ADR the test cites, and it
does not. ADR-0018 names `physical_bound` as *"the deciding factor"* and
says only that *"`optimizer_class` and `simulation_adapter` follow the same
open-value pattern … since both have a credible third value on the
horizon."* It makes **no exhaustive-list claim** anywhere, so a fourth
plug-in appearing falsifies nothing in it — that is ADR-0018's *"open
interface, not a fixed schema"* decision working exactly as designed.
ADR-0027 §5's *"if and only if … three"* **does** make that claim, which is
why the correction belongs here and only here. Stated so a later reader
does not conclude ADR-0018 was overlooked.

**Raised by:** [#453](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/453)
("Does a radar-transparent bandpass architecture need its own family, or is
it `ABSORBER_TRANSMISSIVE` with an inverted objective?"). The related
question of which *other* registry fields the documented vocabulary is
missing is [#455](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/455).

---

**Both are amendments, not a supersede** (ADR-0020). Neither Decision
paragraph is rewritten: (a) adds two fields to an object §4 already
defines and splits a third across a boundary §4 already draws, and (b)
corrects a count in a test whose basis — function, not shape — is
unchanged.
