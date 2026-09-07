---
status: accepted
---

# An interface property is its own library entry, keyed by an ordered material pair plus a surface preparation

The Material-property library holds facts about one substance
(`designs/material_properties.py`, ADR-0015). The Ink-property library proposed in
`docs/fabrication-capability-and-ink-library-spec.md` holds facts about one purchasable ink.
**Neither can hold a fact about two materials meeting**, and the repo already has a table full
of them: `docs/xband-absorber-substrate-shortlist.md` §5 tabulates adhesion as six substrates
× two conductors, with the cells genuinely differing per conductor — PET's silver adhesion is
tested to **ASTM D3359 cross-cut**, its MXene adhesion is *"not quantified"*; TPU's silver is
manufacturer-qualified, its MXene is *"Nothing found"*, `UNKNOWN`.

**Decision: interface properties get their own library, keyed by an *ordered* material pair
plus the surface preparation between them — `(deposited_material, onto_material,
surface_preparation, property)` — and never by a pair alone.**

*In plain terms: whether a printed layer sticks is not a fact about the ink or about what it
is printed on. It is a fact about that ink, on that surface, prepared that way — and change
any one of the three and the answer changes.*

## Why the preparation is in the key, not a note

This is the part that makes it a decision rather than a schema detail. §5's silicone row:

> Native PDMS is too hydrophobic/low-surface-energy to print on: *"the hydrophobicity of the
> PDMS surface prevented printing of the Ag NP ink on top of the native PDMS substrate."*
> Atmospheric-plasma or UV-ozone oxidation creates a hydrophilic silica layer, **after which
> printed patterns survive stringent adhesion tests**.

So silver-on-PDMS is simultaneously *"will not print at all"* and *"survives stringent
adhesion tests."* Both are true; they differ only in preparation. A row keyed on the pair
alone would have to pick one, and either choice is a false statement about the other case. A
key with `surface_preparation` — carrying an explicit `"none"` value rather than a null —
makes an untreated result impossible to mistake for a treated one.

## Why the pair is ordered

Which material is deposited *onto* which is not symmetric: printing silver onto PDMS and
casting PDMS over silver are different processes with different interfaces. The key is
therefore `(deposited_material, onto_material)`, not an unordered set.

This also generalises past ink-on-substrate at no extra cost, which matters because the
programme has three interfaces of the same shape: ink onto substrate, ink onto **host**
(in-situ printing, #105's decisive MXene advantage), and cured layer onto host (the
`laminate` stage). All three are "material A deposited onto material B," so one library
serves them and none needs a special case.

## What does NOT go in it

Two exclusions, both load-bearing, because without them this library swallows everything.

**A fact true of every counterpart is a single-material fact.** §5's own reading of the
silicone row is explicit: the pretreatment requirement *"is a property of the silicone
surface, not of the ink"* — *"Neither MXene nor silver escapes this."* That belongs in the
Material-property library as a property of PDMS. Only the outcome that varies by counterpart
is an interface property.

**A fact computable from two single-material facts is derived, never stored.** Cure
compatibility is the worked example: ACI SC1502 needs ≥ 120 °C, unstabilised PET tolerates
~80 °C, so "can this ink be cured on this substrate" falls out of two rows already held. This
is the same derive-don't-store rule the spec adopts for sheet resistance, and for the same
reason — a stored answer silently fixes inputs that should be looked up.

## Consequences

**It inherits ADR-0015's disciplines unchanged**: every citation is its own row and citations
are never collapsed; per-entry provenance from the same three tiers; a cited Family fallback
bracket on a miss; a miss returns `no_data` and the candidate is *excluded from selection with
the reason stated*, never silently dropped (#127, #108). It also carries the `method` field
added for the substrate migration, which here is unusually load-bearing: **ASTM D3359
cross-cut, a scotch-tape pull, and "printing was demonstrated" are three different claims**,
and §5 contains all three presented in adjacent cells.

**`UNKNOWN` is a value worth storing, not an empty row.** Four of §5's twelve cells are
`UNKNOWN` or "nothing found," and one — textile — is a *negative* finding: *"the literature's
finding is negative,"* weak interfacial bonding and poor wash fastness, with ALD priming
layers existing precisely because bare MXene ink does not bond. "Nobody has tested this" and
"this was tested and it fails" must not collapse into the same blank.

**The asymmetry must survive the schema.** §5's own header says *"the asymmetry the ticket
asked to keep visible. Shown, not averaged."* A shape permitting a merged "PDMS adhesion"
figure would defeat the table's stated purpose.

**It decides a live ranking.** §5's closing finding: the substrate with the best loss tangent
for an absorber — silicone at tan δ 0.10 — *"is also the one that will not accept a printed
conductor without a plasma or UV-ozone step."* An RF-only ranking puts silicone first. With
nowhere to hold that interface fact, the loop would rank it first and never surface the
process step, which is exactly the "smuggled assumption" failure #130 warns about.

## Considered and rejected

**Add a substrate axis to the Ink-property library.** Rejected: it makes every ink row carry a
substrate it has nothing to do with (viscosity and cure schedule are properties of the ink
alone), and it cannot express layer-onto-host, where neither material is an ink.

**Encode the pair as a compound material name in the existing library** — `"silver-on-PDMS"`.
Rejected: lookups are by material, so a compound name is invisible to every query for either
constituent, and it has nowhere to put the preparation.

**Treat adhesion as a per-requirement constraint rather than a stored fact.** Rejected: it is
a durable fact about two materials, not a fact about one customer's requirement, so it meets
#148's own test for what accumulates across runs.

**Plan-only**, per #104. No code accompanies this; implementation lands as its own
`ready-for-agent` issue, the way #154 built ADR-0015 once the decision was accepted.
