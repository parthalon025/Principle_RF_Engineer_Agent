---
status: accepted
---

# The intended-effect library is a reference lookup over physics and the registry, never a record of the requirement, and ADR-0030 stands unamended

**ADR-0030** decided that a requirement's intended effect is *"another key
inside a requirement's own entry, beside `requirement` and `target`"* — an
open vocabulary, established by interview, provenance always `ASSUMED`, and
*"having none is a legal answer."* `designs/requirement_targets.py`'s
`propose_intended_effect` implements exactly that: it checks the string is
non-empty, tags it `ASSUMED`, and validates nothing else.

That leaves a real hole, and it is not the one ADR-0030 was answering.
CONTEXT.md names seven intended effects — *"absorbed, reflected in phase,
steered, transmitted, scattered diffusely, polarisation-converted, shielded
against"* — and says the mapping from one effect to the several **design
families** that might deliver it *"is the trade space a set of candidates is
drawn from."* But nothing in the tree held that mapping. So nothing could
answer three questions a design pass asks before it does anything else:
**what quantity is this effect graded on, on what fixture, and does anything
in `designs/design_families.py` actually serve it?**

The cost of not answering them is not abstract. A radome asks for
transmission and there is no transmissive family, so the only ground-less
two-port family in the registry — `ABSORBER_TRANSMISSIVE` — would take it by
elimination, and that family's `analysis_model` scores worst-in-band
**absorptivity**. Take MIL-R-7705B Table 1's own sample electrical limits
(`docs/military-requirements-vocabulary.md` §5): power reflection 2 %,
one-way power transmission 85–95 %. A radome reflecting 2 % and transmitting
92 % scores `A = 1 − 0.02 − 0.92 = 0.06` against ADR-0041's 0.90 default
absorption threshold, and **ranks last**. The same part scores 0.92 on
transmittance, which is what was asked for. *In plain terms: a window and a
sponge are graded on opposite things, and grading the window as a sponge puts
the best window in the room at the bottom of the class.*

## Decision

**The intended-effect library (`designs/intended_effects.py`) is a reference
lookup over two kinds of fact — facts about physics, and facts about this
repo's own registry — and never a record of any one requirement. ADR-0030
stands unamended: `intended_effect` remains an open-vocabulary key on a
Customer requirement, validated against nothing.**

Six parts, each load-bearing:

**1. It is a lookup, not a registry of requirements and not an intake
validator.** It holds no requirement rows and mints no provenance rung. It is
deliberately *not* imported by `designs/requirement_targets.py`, and
`tests/test_intended_effects.py` asserts that absence structurally rather
than trusting a comment — because the failure mode is silent: the day someone
wires this in at intake, an open vocabulary becomes a closed enum and ADR-0030
is superseded by accident.

**2. An unknown effect returns a miss.** `resolve_intended_effect` returns a
well-formed `EffectMiss` for anything unrecognised, and never raises. Every
other entry point (`families_serving`, `scoring_quantity`, `objective_sense`,
`physical_bound_for`) returns the same miss rather than raising, so the
guarantee cannot leak through a side door. A non-string argument is a miss
too: this is a lookup, not a validator. **An effect nobody has written a
profile for is the expected case, not an error** — ADR-0030's own worked
example is a requirement asking a surface to "behave as a magnetic mirror"
when no family served it (#220).

**3. Nothing gates. Only physics blocks anything.** Where the library knows an
effect has no family behind it, that is a `FamilyGap` handed to the caller —
shaped like a **Capability warning** (a precise `value`/`comparator`/`unit`
statement rather than prose, so the gap is queryable) but explicitly **not**
one: a Capability warning is about what the shop has loaded, and this is about
what this repo's own registry holds. It is not a `capability-verdict` either,
because it drops nothing. ADR-0028's "warn and proceed" governs; the charter's
"present equipment shapes the ranking and the warnings, never the search"
governs the same way for a registry gap.

**4. Objective sense is per quantity, not per effect, because that is where
the radome defect lives.** Both `absorbed` and `transmitted` *maximise their
own* scoring quantity, so comparing one sense against the other would look
harmless. The defect is one level down: asked about **absorptivity**, an
absorber wants it maximised and a radome wants it minimised. So each profile
carries `senses_by_quantity` — its own quantity plus every other quantity it
has a stated opinion about — and the opposition is pinned by test.

**5. A bound follows the mechanism, not the ask, so an effect carries a tuple
of bounds.** ADR-0047's per-family table is reproduced here keyed by effect
and split by mechanism: Rozanov for metal-backed absorbers, Gustafsson &
Sjöberg (~5× harsher) for reflection-phase steering and AMC-checkerboard
backscatter, **none published at all** for polarisation-conversion bandwidth
— a positive finding on the authors' own words, distinct from an unsearched
gap — and, for diffusion, `docs/absorber-thickness-bandwidth-bound.md` §7.3's
exemption. Backscatter reduction therefore carries **three** bound entries,
one per route, because they differ by more than a constant. Per ADR-0047 every
one of these **advises and never gates**.

**6. The diffusive exemption's two preconditions are encoded as data a caller
can check.** The exemption holds only when (a) the surface *redistributes*
rather than dissipates, and (b) the period is large enough to launch
propagating diffracted orders. The first is a statement about mechanism that
only the model can make, and its `check` is recorded as `None` — saying out
loud that no calculation discharges it. The second is arithmetic and is wired
to a real function: for a checkerboard at normal incidence the specular order
is cancelled by construction, so the first available channels are the
**diagonal** ones, which propagate only for supercell period
`D ≥ √2·λ` — **42.4 mm at 10 GHz, 30.3 mm at 14 GHz** (`CALCULATED`, verified
in test). Fail either precondition and the surface is back inside a bound and
the thickness bill is due. This advises; it never gates.

A default threshold is recorded **only where the literature has a
convention**, and its reversibility travels in the data rather than in a
comment: −10 dB / 90 % absorption is *"a reversible, one-pass default when the
customer states no absorption threshold — never a hardcoded rule, and never
used to redefine the band's own edges"* (ADR-0041 point 2), and the ±45° AMC
window is the same shape of default for reflection phase, being the window
Gustafsson & Sjöberg's own Eq. (5.1) is stated against. Six of the eight
effects get an explicit **none**, each with its reason recorded — not a
borrowed number from a different quantity on a different fixture.

## Considered and rejected

- **A closed enum of intended effects, validated at requirement intake.**
  This is the obvious design and it was seriously considered: it would catch
  a typo at the moment it is typed, guarantee every requirement lands on a
  profile, and let the loop dispatch on the effect the way it dispatches on
  `design_family`. **Rejected because it would supersede ADR-0030**, whose
  Decision states in terms that the vocabulary is *"open, not a closed enum,"*
  following **Optimizer class**, *"so an approach nobody needs yet has room."*
  Under ADR-0020's test — *would the Decision paragraph be rewritten?* — the
  answer is plainly yes, so this could not have landed as an amendment; it
  would have needed a superseding ADR and a fresh approval.

  It was also rejected on its own merits, twice over. ADR-0030's own
  justification remains live and unrefuted: *"A closed set would already be
  wrong: Examples 1 and 2 need an effect ('behave as a magnetic mirror') that
  no current family serves (#220)."* And this library's own findings make the
  case worse, not better — **three of the eight effects it holds have no
  design family at all**, two of them named in CONTEXT.md's seven. A closed
  enum validated at intake would be a vocabulary in which a majority of the
  gaps are unreachable: a customer could not state a requirement the programme
  cannot yet serve, which is exactly the information the programme most needs
  to surface.

  **What would have to change to revisit it.** Two things together, neither
  sufficient alone. First, every effect in the vocabulary would need a design
  family serving it, so that validating an effect no longer means refusing a
  legitimate ask — the gap report `effects_without_family()` is the direct
  test, and it is not empty. Second, ADR-0030's own reason would have to have
  expired: the vocabulary would have to have stopped growing, evidenced rather
  than assumed. Even then the right move is likely the one
  `designs/material_families.py` already takes for material names — **warn,
  naming what is known, and accept** — rather than reject, because an open
  registry cannot tell a typo from a genuinely new entry and warning is the
  charter's own answer to that.

- **Storing the effect profile on the `DesignFamily` object instead.**
  Rejected: it inverts the relationship CONTEXT.md is careful about. A family
  is a *mechanism*; an effect is what the customer *wants*. `REFLECTION_PHASE`
  serves two effects and `absorbed` is served by two families, so the mapping
  is many-to-many and belongs on neither side alone. ADR-0030 rejected the
  mirror-image move for the same reason — an effect is *"not a field on a
  family."*

- **Letting the library pick a family from a requirement's effect.**
  Rejected outright, and this is the line the library must never cross.
  `designs/design_families.py` states it at line 58: *"SELECTION STAYS
  HUMAN-AUTHORED … this module validates a family a human named; it never
  picks one."* ADR-0030 rejected the same thing in its own Consequences —
  *"Driving selection from a lookup table was considered and rejected as
  putting code in the business of choosing physics."* The library reports
  which families serve an effect; the choice stays the model's.

- **Resolving a customer ask like "reduce radar return" onto one effect.**
  Rejected for the same reason one level down. That ask is answerable by
  absorption, by diffusion, or by a checkerboard's phase cancellation — three
  physically different routes with different costs and different confidence,
  which is CONTEXT.md's own worked example of the trade space. Collapsing it
  silently would throw away the thing the charter promises to hand the reader.
  Such phrases therefore return a **miss that names the effects they could
  mean**, and resolve to none of them.

- **Recording the low-infrared-emissivity finding by editing CONTEXT.md's
  seven.** Rejected as out of scope and not this artifact's decision to make
  — see Consequences.

## Consequences

- **Three effects have no design family, and the report is now queryable.**
  `effects_without_family()` returns `transmitted`, `shielded against`, and
  `low infrared emissivity`. Two of those three are named in CONTEXT.md's own
  seven. Each carries what it costs today and the cheapest fix. This is a
  finding handed to a reader, not a refusal: nothing is blocked, and a
  requirement asking for any of them still runs.

- **`transmitted` is the sharpest gap because the architecture is not
  hypothetical.** ADR-0017's 2026-09-06 correction already records a printable
  bandpass FSS — square-loop slots in a ~15 µm printed metal layer, every
  feature clearing the 0.2 mm floor, a 62–80 % passband at about 0 dB
  insertion loss — and calls it *"the transmissive design ADR-0017 assumed did
  not exist."* The cheapest fix is a transmissive family in
  `designs/design_families.py` with `TRANSMITTANCE` as its scored quantity,
  `port_count=2`, `requires_ground_plane=False`, and an honest
  `UndeclaredAnalysisModel` until a passband model exists. **Not done here:**
  this ADR does not add that family, and `designs/design_families.py` is
  untouched.

- **`shielded against` may not be a scoreable ask under this programme's own
  default architecture, and that question is now on the record rather than
  latent.** Shielding effectiveness is a two-port transmission quantity,
  `SE_dB = −20·log₁₀|S₂₁|`. ADR-0017 makes every skin here print its own
  reflector by default, and a ground-backed structure has zero transmission by
  construction — which is why `DesignFamily.__post_init__` forces
  `requires_ground_plane=True` to pair with `port_count=1`. So `|S₂₁| = 0`,
  `SE` is unbounded, and the number carries **no design information for that
  architecture**. *In plain terms: asking a metal-backed skin how well it
  blocks radio is like asking a brick wall how well it blocks daylight — the
  answer is "totally", every time, and it tells you nothing about how to build
  a better wall.* Whether "shielded against" is a distinct effect or
  "transmitted" with the sense flipped is a glossary question, not a code one,
  and it is left open here.

- **Low infrared emissivity is a real behaviour absent from CONTEXT.md's
  seven, and this library names it without claiming it belongs in the
  glossary.** A radar-plus-infrared skin is live work —
  `docs/five-paper-absorber-corpus-findings.md` §4 calls it *"the architecture
  the DEVCOM context makes live"* and gives it a number: a resistive infrared
  overlay must exceed **407 Ω/sq** to leave a 90 % microwave absorption floor
  intact, **1,695 Ω/sq** for a 99 % floor (`CALCULATED`). Every continuous
  infrared-functional conductor in that corpus fails that by one to three
  orders of magnitude; every patterned one passes by two to three, because an
  infrared-scale period is microscopic at 10 GHz. So the conflict is
  continuous-versus-patterned and it is designable. **Whether it joins
  CONTEXT.md's seven is a separate decision** with its own owner
  (`/domain-modeling`, `docs/agents/domain.md`); this ADR deliberately does
  not make it, and nothing here edits CONTEXT.md.

- **`PATCH` serves none of the eight effects — a second gap, in the other
  direction.** `families_without_effect()` returns `("PATCH",)`. A patch
  antenna does not do something to an arriving wave; it radiates one, and
  "radiated" is not among CONTEXT.md's seven either. Recorded as a finding
  rather than fixed by minting a `radiated` profile, on the same reasoning as
  the emissivity case. The report earns its keep regardless: it is what makes
  adding a **seventh design family** without wiring it into this library fail
  loudly in test, instead of leaving a family no requirement can reach.

- **A discrepancy is reported and deliberately not adjudicated.**
  `designs/design_families.py` carries the Gustafsson & Sjöberg bound as an
  `UnreadPhysicalBound` — *"primary source NOT yet read by this programme"* —
  while `docs/absorber-thickness-bandwidth-bound.md` §7.1 quotes that paper's
  Eqs. (4.10), (4.11) and (5.1) verbatim from the open-access Lund author
  manuscript, and ADR-0047 states the resulting `B·λ₀/d ≤ 2.6` as settled
  content. Those cannot both be true. Each bound entry carries a
  `registry_state` field recording what the registry says alongside what the
  doc says, so a caller sees both rather than one silently winning. Resolving
  it means either reading the paper first-hand and replacing the marker, or
  correcting the doc — and it belongs at `designs/design_families.py` on a
  ticket, not here (ADR-0020: a correction lands at the claim that owns it).

- **This decides nothing about how `intended_effect` is produced.** ADR-0034
  owns that: a Requirement target and an Intended effect are extracted from a
  `CONFIRMED` **Requirements document**, not elicited as a single-shot answer.
  This library is read *after* that field exists, and never fills it in.

- **Not decided here:** whether the design loop should consult this library at
  the ARCHITECTURE step to warn when a stated effect has no family, and where
  such a warning would sit in the **Run report**'s trade-space lead
  (ADR-0025). The library returns the finding; nothing yet calls it. That
  wiring is its own ticket, and it must arrive as a warning under ADR-0028,
  never as a gate.
