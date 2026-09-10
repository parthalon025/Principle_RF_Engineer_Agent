---
status: accepted
---

# Material is a variable the loop searches over; material properties are the constant, and MXene is a candidate scored on merit

Issue #105, part of #104's wayfinder map, found two statements about the
programme that agree only under a condition nobody had checked. The map
says material and substrate are **optimally chosen** from the customer
requirement — the loop searches them and returns whatever scores best —
and separately describes **MXene as the company's core premise**, for
large-radius flexible antennas. Those reconcile only if the requirements
the company targets always favour MXene on the merits, and
`docs/HANDOFF-metamaterial-printing-grill.md` gives reason to doubt it.
That document's stated justification for MXene is its **room-temperature
cure** — the Voltera NOVA controls material temperature only to 40 °C, so
silver (120–200 °C cure) and copper cannot share a process with a
substrate that must stay unbaked. But that argument only bites when the
substrate must be PET/TPU-class, which the patent's `R = 3T` rule (from
its 0.87–2.0 mm skin, a minimum bend radius of 2.6–6.0 mm) forces only at
tight bend radii. At large radii, polyimide is viable, polyimide tolerates
a 400 °C cure, and printed silver then beats MXene by roughly **15×** on
conductivity (10⁷ vs 6.9×10⁵ S/m). A loop that optimises honestly could
therefore recommend against the premise, most likely on exactly the
"large radial" requirements named as MXene's home ground.

The ticket posed three named dispositions and asked which the loop
implements: a **hard constraint** (MXene fixed as input; the loop searches
geometry and substrate only), a **scored candidate** (MXene competes with
silver and copper on every requirement), or a **default with a burden of
proof** (MXene wins ties and near-ties; the loop must clear a stated
margin before recommending against it, and must say why). Resolving it
required pinning down "large radial" first — a large *radius of
curvature* host, which weakens the MXene case per the arithmetic above,
versus a large *area* of conformal coverage, which does not — a same
ambiguity the handoff document had already flagged as its own Q20, noting
it "could substantially simplify the programme."

The resolution recorded on the ticket went through two rounds of
self-correction before settling. The first correction found that framing
large-radius hosts as **the company's target platforms** was wrong: the
host surface is a **per-requirement input**, not a standing property of
the effort, so the material answer is a function of what a given
requirement states, never a project-level assumption. The second
correction found that the pruning criterion active at tight curvature is
**not substrate class**: the handoff document's cure-compatibility matrix
marked silver ✗ on both PET and TPU, and that mark is wrong — silver
cures at 120 °C / 30 min on PET, and Intexar PE874, already on Voltera's
own materials list, cures at 130 °C on TPU film and select fabrics. What
actually prunes silver is **whether the part can leave the host and enter
an oven at all**, since the NOVA itself only reaches 40 °C. The Decision
below records that corrected, final form.

## Decision

1. **MXene is a candidate, scored on merit, with no thumb on the scale.**
   MXene competes with silver and copper on every requirement — no
   tie-break, no margin, no default. A scoring bias toward the house
   material would corrode the one property this repo is built on: that a
   number means what it says. When the loop ranks a non-MXene candidate
   first, it emits it and says why — usually one variable (a bend radius
   that admits a sinterable substrate, a cure ceiling the flexible options
   can't reach) — and naming it tells the reader what would have to change
   for the answer to flip. **Preference enters as an explicit constraint,
   never as a scoring bias**: if MXene should win, it wins because a
   stated constraint made it win — a cure ceiling, a substrate class, a
   drape requirement — not because the scorer was tuned to prefer it. A
   constraint is visible, arguable and recorded; a scoring bias is none of
   those.

2. **"Large radial" means large *radius of curvature*** — an aircraft
   wing, a hull, an sUAS body are representative examples — never large
   *area* of conformal coverage and never antenna ground-plane radials.
   The host surface itself is a **per-requirement input, supplied every
   time**, never a standing property of which platforms the company
   targets.

3. **MXene's decisive advantage is in-situ printing on a host that cannot
   be oven-baked** — not flexibility, not bend radius, and not substrate
   class. Two regimes follow from this:
   - **The part can be printed on a coupon and oven-cured before
     bonding.** Silver is available on PET, TPU, polyimide, silicone and
     textiles — the whole conductor set is live in both host-curvature
     regimes.
   - **The part must be printed in situ**, on an assembled airframe or a
     surface that cannot be baked. Nothing above 40 °C is possible, silver
     and copper are pruned, and MXene wins unaided — its room-temperature
     cure is the entire reason it can be used at all.

   Where a part can visit an oven, silver competes everywhere, including
   on PET and TPU — the most conformal substrates named in the original
   premise.

4. **Standing preference, restated here as the rule this decision is an
   instance of:** the only constants are physics, the machine and the
   material — everything else comes from the requirement. **Material is a
   *variable*; material *properties* are the constant.**

5. **Guardrail on this ADR's own reasoning** (`RUNNING-LISTS.md` §3
   correction 34, found on #113): US12089385B2 names neither MXene, nor
   silver, nor "ink." Full-text checks from two independent sources
   (Google Patents, FreePatentsOnline) return **NOT PRESENT** for `MXene`,
   `silver`, `ink` and `conductive material`; the only conductors the
   patent names are **copper and gold**. MXene's candidacy here rests
   strictly on its own physical merits — the 40 °C in-situ cure argument
   above — and **never** on a claim that the patent recommends or endorses
   it.

## Considered and rejected

- **Hard constraint** — MXene fixed as input, the loop searches geometry
  and substrate only. Rejected: "Honest about the business, dishonest
  about the physics," and it means the loop can never tell a reader when
  the premise is wrong.
- **Default with a burden of proof** — MXene wins ties and near-ties, and
  the loop must clear a stated margin before recommending against it.
  Rejected on the same ground as decision point 1: a default-wins-ties
  rule is a scoring bias wearing a margin as a disguise. If a preference
  is to survive, it has to arrive as a named, arguable constraint, not as
  a thumb the scorer carries by default.

## Consequences

- Representing **"can this part be printed in situ, or does it have oven
  access"** as a first-class, per-requirement constraint is now owed to
  the loop, not inferable from substrate class or bend radius alone. The
  ticket names this as feeding directly into #117 ("What constraints can a
  customer requirement carry, and how do they prune the candidate
  space?"), which now has a concrete, high-value example to design
  against.
- The substrate shortlist (#114) and the fabrication-constraint work
  (#115) both inherit the corrected criterion: bend radius alone does not
  decide the material question; oven-reachability does.
- This decision does not fix a bend-radius number, a substrate shortlist,
  or a margin/tie-break rule — those remain #114/#115/#117's territory. It
  settles only that no material, MXene included, receives a scoring
  exemption, and that any argument for MXene must be made on stated
  physical grounds rather than on the patent's supposed endorsement.
