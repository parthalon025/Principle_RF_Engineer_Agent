# Does a Flexible, εr ≈ 100 Material Exist for US12089385B2 Example 4?

**Research date:** 2026-09-04
**Ticket:** [#108](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/108)
**Question:** `docs/seven-example-design-unknowns.md` asserted, without independent sourcing,
that "any real εr ≈ 100 ceramic-loaded composite has tanδ ≫ 0 and is neither pliable
nor printable." Example 4 of US12089385B2 — a beam-steering element built from a
cylindrical hole (radius `r`, swept 0.2–1 mm) in a host slab with **εr = 100, µr = 1**
(the patent's own lossless simulation idealization, FIG. 8D), ground-backed, period
2.125 mm, at ~10 GHz — needs that host to be real. Since the whole program is a
*pliable* skin (the patent's own title), this question decides whether Example 4 is
buildable at all, or permanently excluded. Does any genuinely flexible material or
composite exist with εr in the 50–150 range and usable loss near 10 GHz — or is high
εr fundamentally coupled to rigid ceramic composition?

Provenance tags are `CONTEXT.md`'s ladder — `MEASURED` → `SIMULATED` → `CALCULATED` →
`MANUFACTURER-SPECIFIED` → `LITERATURE-SUPPORTED` → `INFERRED` → `ASSUMED` → `UNKNOWN`.
Per `CONTEXT.md`, a peer-reviewed paper is `LITERATURE-SUPPORTED`. No parallel
confidence vocabulary is introduced.

---

## Bottom line up front

Six findings, in descending order of how much they change the picture.

1. **No source found combines all three things the patent needs in one material: real
   flexibility, microwave characterization, and εr ≥ 50.** The published literature
   splits cleanly into two non-overlapping families. Family A is genuinely bendable
   *and* measured at GHz frequencies, but tops out at **εr ≈ 20–25** — roughly a fifth
   to a quarter of what Example 4 needs. Family B reaches εr well past 100 — even past
   1000 — but every one of those numbers, without exception, is measured at 1 kHz to a
   few MHz, never at microwave frequency. **In plain terms: nobody has published a
   material that both bends like a skin and behaves electrically like the patent's
   host at the frequency the patent actually operates at.** (§1)

2. **The "flexible + microwave" ceiling is about εr ≈ 20, and it has been the ceiling
   for twenty years.** The founding paper in this space — Koulouridis, Kiziltas, Zhou,
   Hansford & Volakis, *IEEE Trans. Microwave Theory Tech.* 54 (2006) — set out
   explicitly to build "conformal and pliable substrates for microwave applications,"
   and reached **εr = 20** with low loss in a PDMS-BaTiO₃ composite, tested only to
   1 GHz. Follow-on work pushing the same PDMS-ceramic approach to 20 GHz using higher
   ceramic loading (49 vol%) reached **εr = 23.51, tanδ < 0.047**. The best result of
   all in this family lands right on the patent's own 10 GHz: a polybutadiene-SrTiO₃
   composite reaches **εr = 21.1, tanδ = 0.0041, explicitly stated at 10 GHz** — but its
   flexibility claim is "high bending strength," a fracture-resistance number for a
   sheet under load, not the wrap-around-a-curve compliance of an elastomer (§1.1, §5).
   In twenty years of trying, nobody in this line of research has doubled that number.

3. **Every εr ≥ 100 result is a low-frequency capacitor-material result wearing a
   "flexible" label the paper never tests.** BaTiO₃-cyanoresin composite, εr = 133,
   is measured **at 1 kHz** (Chiang & Popielarz 2002). CCTO/P(VDF-TrFE), εr > 1000, is
   measured from **100 Hz to 1 MHz** (Zhang et al., *Sci. Rep.* 2016). CCTO-silicone
   resin, εr = 119 at 90 vol% ceramic loading, is likewise sub-MHz (Babu, Singh &
   Govindan, *Appl. Phys. A* 2012). None of the three reports a bend radius, a cycle
   count, or any mechanical flex test — "flexible" describes the polymer family used,
   not a measurement performed on the finished composite. **None of them says anything
   about what these materials do at 10 GHz, and there is good reason to expect it is
   not the same number** — high-εr ceramics like CCTO carry a well-documented
   Maxwell-Wagner relaxation that collapses their permittivity by orders of magnitude
   between MHz and GHz (§1.2, §3).

4. **One result gets close to the number and needs its own flag, not a dismissal.**
   A PVA/Ti₃C₂Tₓ MXene film, vacuum-filtered, reaches **ε′ = 3166, tanδ = 0.09, stated
   explicitly at X-band (8.2–12.4 GHz)** — the correct band — at only **10 wt% MXene**
   (Mirkhani, Zeraati et al., *ACS Appl. Mater. Interfaces* 2019). It is described as a
   "flexible thin film," but no bend-radius or cycle test was found for it in any
   source reachable from here. More importantly, the mechanism is not the patent's
   mechanism: this is a **percolative conductor network** (MXene conductivity
   σ ≈ 1.4×10⁶ S/m, close to a percolation threshold), not a bulk dielectric
   polarization. That distinction matters for a bend-durability question specifically:
   a percolation network's conductivity is set by which flakes are still touching,
   and repeated flexing is exactly the kind of mechanical insult — microcracking,
   flake reorientation — that changes flake-to-flake contact. **A percolative network
   is a plausible candidate for high εr near 10 GHz, but its bend-durability is an
   open, testable, and probably unfavorable question, not a solved one** (§1.3, §4).

5. **The physics is a documented engineering tradeoff, not a proven impossibility.**
   Reaching high εr through simple ceramic loading needs volume fractions of 50–90%
   before the composite's permittivity climbs into the hundreds — and multiple sources
   independently describe that same loading range as where composites "lose the
   desired mechanical properties and integrity," become brittle, and suffer
   particle agglomeration and voids. In plain language: **to make an insulator-plus-
   ceramic mixture conduct radio waves the way solid ceramic does, most of what you
   are printing has to become ceramic — and a sheet that is almost entirely stiff
   mineral powder does not bend.** The mixing-rule math backs this up: Maxwell-Garnett
   theory (the standard low-loading model) tracks measured εr well only up to roughly
   30–60% filler, after which composites need percolation-family models instead,
   because the physics has shifted from "diluted ceramic grains" to "the grains are
   starting to touch each other." The one architecture that reliably escapes this — 2D
   conductive fillers (MXene) exploiting interfacial charge accumulation instead of
   bulk ceramic content — is finding #4 above, and it swaps the brittleness problem for
   an unverified bend-durability problem instead of eliminating it (§2).

6. **Direct answer: not proven physically impossible, but not demonstrated either — and
   `docs/seven-example-design-unknowns.md`'s original claim holds up.** Nothing found in
   this search shows εr ≈ 100 and genuine, tested flexibility coexisting at any
   frequency, let alone at 10 GHz. The honest statement is narrower than "impossible":
   it is that **no one has published it**, across a research area (flexible high-k
   composites) that has been active since at least 2006 and has an obvious commercial
   motivator (energy-storage capacitors) pulling εr as high as possible. That is
   different from a hard materials-physics prohibition, and the field is still moving
   — but a design program relying on Example 4 today would be relying on a material
   that exists only inside the patent's own lossless simulation, not in the literature.
   The original `ASSUMED` tag was directionally correct; it now sits on
   `LITERATURE-SUPPORTED` ground instead of an unchecked assertion, and Example 4
   should stay flagged as excluded on current materials science, not merely
   "not yet sourced."

---

## 1. What the literature actually publishes, sorted by whether it was measured at microwave frequency

### 1.1 Family A — genuinely flexible *and* measured at GHz: ceiling is εr ≈ 20–25

These are composites where the paper itself performed a mechanical flex/strain test,
*and* reported permittivity at a stated microwave frequency (not just kHz/MHz). All
`LITERATURE-SUPPORTED`.

| Material system | εr | tanδ | Frequency | Filler loading | Flexibility evidence | Source |
|---|---|---|---|---|---|---|
| PDMS–BaTiO₃ | **20** | < 0.04 | to 1 GHz | not stated in abstract | Paper's own framing: "conformal and **pliable** (bendable) substrates" | Koulouridis, Kiziltas, Zhou, Hansford & Volakis, *IEEE Trans. Microw. Theory Tech.* 54(12), 4202–4208 (2006) |
| PDMS–MgCaTiO₂ | 8.5 | < 0.009 | to 1 GHz | not stated | same paper | same |
| PDMS–Ba₀.₅₅Sr₀.₄₅TiO₃ | **23.51** | < 0.047 | to **20 GHz** | 49 vol% | PDMS matrix; not separately bend-tested in the summary reached | Castro et al., "High-Permittivity and Low-Loss Electromagnetic Composites…," *J. Microelectron. Electron. Packag.* 13(3), 102 |
| PDMS–Ba₀.₅₅Sr₀.₄₅TiO₃ | 15.02 | < 0.042 | to 16 GHz | 39 vol% | same | same |
| PDMS–MgCaTiO₂ | 16.33 | < 0.021 | 0.4–20 GHz | 49 vol% | same | same |
| SrTiO₃@VTMS/polybutadiene | **21.1** | 0.0041 | **explicitly at 10 GHz** | 87.5 wt% | "high bending strength, 55.2 MPa" at 86 wt% — a **fracture-load** number, not an elastomeric bend-radius/cycle test (see §5 caveat) | Yang, Yuan, Li et al., *Appl. Surf. Sci.* 622, 156888 (2023) |
| SrTiO₃/PTFE laminate | 13.1 | 0.0055 | X-band | not stated | explicitly a "**dimensionally stable**" laminate — the paper's own word for *not* flexible | Rajesh, *Int. J. Appl. Ceram. Technol.* 6, 553 (2009) |
| Butyl rubber–SrTiO₃ | 13.2 | 0.0028 | 5 GHz | 42 vol% | tensile-tested, mechanically flexible | Thomas et al., *Int. J. Appl. Ceram. Technol.* (2011) |
| SrTiO₃/POE (polyolefin elastomer) | 11.0 | 0.01 | **900 MHz** | 40 vol% | **The best-evidenced flex test in this table**: a microstrip line on the composite was bent to different angles and its transmission coefficient was unchanged below 60°; separately, 90% elongation at break | Xiang, Wang, Yang et al., *J. Eur. Ceram. Soc.* 27(8–9), 3093–3097 (2007); *J. Electroceram.* 24, 20–24 (2010) |
| Silicone rubber–Ba(Zn₁/₃Ta₂/₃)O₃ | 6.6 | not stated | 5 GHz | not stated | "flexible and stretchable," mechanically tested | Namitha & Sebastian, *Mater. Res. Bull.* 48, 4911–4916 (2013) |
| Silicone rubber–BaBiLiTeO₆ | 6–8 | 0.02–0.05 | **1 MHz–26 GHz** | 0.25 vol fraction | "**stable dielectric response… even after several bending cycles**" — explicit bend-cycle test, widest frequency span found in this whole search | *J. Electron. Mater.* (2022), DOI 10.1007/s11664-022-09565-z |
| Silicone rubber–alumina (micro) | 5.89 | 0.009 | 5 GHz | 0.45 vol fraction | flexible elastomer matrix | ScienceDirect S0272884213002083 |
| CaCu₃Ti₄O₁₂/CoFe₂O₄/silicone rubber | **~50** (CCS-3, max) | `UNKNOWN` | "over the X-band" (EMI shielding context) | `UNKNOWN` | `UNKNOWN` — paywalled, could not confirm a bend test | Kumari, Meena, Salim et al., *J. Mater. Res.* 39, 2684–2695 (2024) |

**Reading this plainly.** Twenty years of researchers deliberately trying to build a
bendable, GHz-characterized high-εr substrate have not broken εr ≈ 25 with confidence,
and the one outlier that reports εr ≈ 50 at X-band (CCTO/CoFe₂O₄/silicone rubber) could
not be checked for whether it actually bends — its full text sits behind a paywall this
environment cannot reach (Springer returns an auth redirect, not open content). Even
taking that unconfirmed εr ≈ 50 at face value, it is still half of the patent's target.
**The single closest match to the patent's own 10 GHz operating point — SrTiO₃@VTMS/
polybutadiene at εr = 21.1, tanδ = 0.0041 — comes with a mechanical caveat that matters
more than it looks**: "bending strength" (55.2 MPa) is a flexural-fracture-strength
test, the number engineers use to describe how much a *rigid* sheet resists cracking
under a bending load, not how far a *pliable* material can be wrapped around a curve
without applied force and spring back. A stiff, high-filler-loading sheet can have
excellent bending strength and still be nothing like the patent's pliable skin. Only
one row in this table — SrTiO₃/POE, εr = 11.0 — has both a genuine elastomeric flex
test (bend-angle, transmission unaffected below 60°) and a GHz-adjacent frequency
(900 MHz), and it caps out at εr = 11.

### 1.2 Family B — εr ≥ 100, but never characterized above ~1 MHz

`LITERATURE-SUPPORTED` throughout; the flexibility claims (marked) are `ASSUMED` or
`UNKNOWN` because none of these papers performed a mechanical bend/flex test on the
finished composite — "flexible" describes the polymer chosen, not a result measured.

| Material system | εr | tanδ | Frequency measured | Filler loading | Flexibility claim | Source |
|---|---|---|---|---|---|---|
| BaTiO₃–cyanoethylated cellulose (cyanoresin) | **133** ("over 130") | not stated at this point | **1 kHz** | 51 vol% BaTiO₃ | Polymer matrix itself is high-εr and polar; no bend/flex test reported | Chiang & Popielarz, *Ferroelectrics* 275(1) (2002); NIST |
| CaCu₃Ti₄O₁₂ / P(VDF-TrFE) | **> 1000** (760 @ RT, > 1300 @ 75 °C) | ~0.1–0.35 | **100 Hz – 1 MHz** | 50 vol% CCTO | No mechanical characterization; authors' own framing calls this a "flexible" polymer choice, but the composite at 50 vol% ceramic is `ASSUMED` rigid, not tested | Zhang, Shan, Bass, Tong et al., *Sci. Rep.* 6, 35763 (2016) |
| CaCu₃Ti₄O₁₂–silicone resin (0–3 connectivity) | **119** | 0.35 | sub-MHz (weakly frequency-dependent up to the range tested) | **90 vol% CCTO** | "Silicone resin," not silicone rubber — a thermoset, not an elastomer; 90% by volume is a ceramic body with a binder, not a bendable sheet | Babu, Singh & Govindan, *Appl. Phys. A* 107(3), 697 (2012) |
| PVA/Ti₃C₂Tₓ MXene (solution cast) | 370.5 | 0.11 | **X-band, 8.2–12.4 GHz** | 10 wt% | described "flexible" but not bend-tested in reachable sources | Mirkhani, Zeraati et al., *ACS Appl. Mater. Interfaces* (2019) |
| PVA/Ti₃C₂Tₓ MXene (vacuum-filtered) | **3166** | **0.09** | **X-band, 8.2–12.4 GHz** | 10 wt% | same — see §1.3 flag | same |
| Ti₃C₂Tₓ / P(VDF-TrFE-CFE) | ~10⁵ near percolation | 5× rise (0.06→0.35) up to 10 wt% | not confirmed as GHz — percolative dielectric relaxations of this kind are conventionally measured kHz–MHz; `UNKNOWN` whether this specific figure holds at microwave | ~15 wt% MXene (percolation limit) | not tested | Tu, Jiang, Zhang & Alshareef, *ACS Nano* 12(4), 3369–3377 (2018) |

**The load-bearing observation here is the baseline the CCTO papers state themselves.**
Babu, Singh & Govindan (2012) note that bulk CCTO ceramic's own dielectric constant —
10⁴–10⁵ — is "nearly independent of frequency **up to 10 MHz**," which is the field's
own way of flagging that above that point it is *not* independent of frequency. CCTO's
giant permittivity is a Maxwell-Wagner interfacial-polarization effect (charge
piling up at internal grain boundaries), and that mechanism is well known to relax away
by several orders of magnitude somewhere in the MHz-to-GHz transition. **None of the
Family B papers measured through that transition**, so extrapolating any of these
εr ≥ 100 numbers to 10 GHz is not supported by the paper that produced them — it would
be an `ASSUMED` extrapolation across a frequency decade where the physics is known to
change, not a `LITERATURE-SUPPORTED` one.

### 1.3 The one genuine microwave-band ≥1000 result, and why it needs its own flag

The PVA/MXene vacuum-filtered film (ε′ = 3166, tanδ = 0.09, at 8.2–12.4 GHz — squarely
covering the patent's ~10 GHz) is the only result in this entire search that reports
both an εr comfortably above the patent's target *and* a genuinely microwave
frequency. It deserves to be taken seriously rather than waved off with Family B.

But two things separate it from being a real candidate for Example 4's host material:

- **The mechanism is conduction, not the patent's assumed lossless dielectric.**
  Ti₃C₂Tₓ MXene's own conductivity is reported at σ ≈ 1.4×10⁶ S/m — a genuinely
  metal-adjacent number, not a dielectric's. The huge permittivity is an interfacial
  (Maxwell-Wagner) charge-storage effect at a near-percolating conductive network, the
  same general mechanism as the CCTO papers above, just realized with a highly
  conductive 2D flake instead of a ceramic grain. FIG. 8D's εr = 100, µr = 1 spec is an
  explicit *lossless* idealization for a Floquet unit-cell solve — a conduction-driven
  mechanism with tanδ = 0.09 is a fundamentally different electromagnetic object, not
  a low-loss stand-in for it.
- **No flexibility-under-repeated-bending data exists for this specific film.** It is
  described as a "flexible thin film," which is plausible for a 10 wt%-loaded,
  vacuum-filtered film — much closer to the low-loading, low-brittleness end of the
  spectrum than a 90 vol% ceramic composite. But a percolative conductor network's
  properties are set by which flakes are in contact, and that is exactly the kind of
  microstructure that repeated bending (microcracking, flake reorientation, local
  delamination) is known to disturb in other percolative-filler systems (e.g., the
  CNF/MWCNT film in §3, which is bend-durable but only characterized at 1 kHz). Whether
  this MXene film's ε′ = 3166 survives 100, 1000, or even 10 bend cycles is an open,
  answerable, and unanswered question — not a demonstrated result.

**Honest framing:** this is the single most promising lead in the literature for
closing the gap between "flexible" and "εr near 100 at 10 GHz," and it is worth
flagging for anyone revisiting Example 4 later. It is not, as published, a verified
answer to the question.

---

## 2. Why high εr trends toward rigidity — the materials-science mechanism

Two mechanisms are documented in the literature, and they point in the same direction.

**Mechanism 1 — simple ceramic dilution needs a lot of ceramic.** The standard
mixing-rule models (Maxwell-Garnett for a dilute filler in a continuous matrix)
predict only a modest permittivity gain at moderate loading — "the magnitude of the
improvement is very limited (around several times) at a reasonable filler loading."
Composites in this search that reach εr ≥ 50 by simple dilution all needed **50–90
vol% ceramic** (CCTO-silicone resin at 90%, CCTO/P(VDF-TrFE) at 50%, SrTiO₃@VTMS/PB at
87.5 wt%). Maxwell-Garnett itself is only validated up to roughly 30% loading in the
sources found here; beyond that, researchers switch to Bruggeman or percolation-family
models because the underlying physics has shifted — the filler grains are starting to
touch and form conductive/polarizable chains through the material, not sitting
isolated in a sea of polymer.

**Mechanism 2 — high loading and brittleness are directly linked, and multiple
independent sources say so in the same terms.** A review of BaTiO₃/polypyrrole
composites states plainly: "higher concentration of the filler also induces
brittleness, severe deterioration of mechanical properties and flexibility in the
polymer matrix which restricts its applications to a narrow spectrum of electronic
devices" (*Synthesis and Characterization of BaTiO₃/Polypyrrole Composites with
Exceptional Dielectric Behaviour*, PMC6401699). A broader review of ceramic-filled
composites across polymer, metal and ceramic matrices independently concludes that at
loadings above ~50 vol%, composites suffer "aggregation, irregular dispersion, voids
and cracks, impairing the mechanical and dielectric properties" (*Structure-interface-
performance relationships of ceramic fillers in polymer, metal, and ceramic matrix
composites: A critical review*, ScienceDirect S2949822826010476). **Read together: the
same loading fraction that buys the permittivity also buys the brittleness, and it is
not a coincidence — it is the same microstructural change (more, closer, harder
particles) producing both effects.**

**The one documented escape route — and why it doesn't fully escape.** Filler
*geometry*, not just loading fraction, changes where this tradeoff bites. High-aspect-
ratio fillers (rods, platelets, 2D sheets like MXene) reach the percolation threshold
— the loading at which particles start touching and forming a network — at much lower
total volume fraction than spherical particles, because a thin plate needs far less
volume to bridge the same distance as a sphere. This is precisely why the MXene
composites in §1.3 reach huge permittivity at only 10–15 wt% loading instead of 50–90
vol%: they are exploiting connectivity, not bulk content. That is a real, physically
sound way to buy permittivity without paying the full brittleness cost of a 90%-ceramic
composite — **but it substitutes a different fragility**, because a near-percolating
network's properties depend on maintaining exactly those particle-to-particle contacts,
and mechanical flexing is a direct threat to that specific microstructure in a way it
is not for a bulk-ceramic composite's permittivity (which barely depends on any single
particle's neighbors). Neither route is free.

---

## 3. The highest εr found in ANY genuinely flexible, bend-tested composite — regardless of RF design intent

Widening the search past RF/microwave applications entirely, to ask only "what is the
highest permittivity anyone has reported in a material that was actually bent and
shown to survive it":

- **Cellulose nanofibril / oxidized multi-walled carbon nanotube film**: εr = **73.88**
  at **1 kHz** (up from 25.24 for pure cellulose), at 6.2 wt% MWCNT loading. The flex
  test is explicit and real: 2 cm × 2 cm samples were "bent manually to make the top
  edge meet the bottom edge and then released… repeated for a thousand times, no
  visible change." (Tao & Cao, *RSC Adv.* 10(18), 10799–10805, 2020.) This is the
  highest εr in this entire search paired with an actual, described bend-cycle test —
  but it tops out at 1 MHz in the paper's own frequency sweep, nowhere near 10 GHz, and
  like the MXene systems above it is a percolative conductive-filler (MWCNT) mechanism,
  not a low-loss dielectric — its baseline loss tangent (0.68–0.70) is already far too
  high to be a useful host at any frequency.
- **Transient dielectric elastomer** (for actuators/sensors): εr = 21 at 10 kHz, with
  genuine, extensive cyclic testing (one device survived 450,000 actuation cycles).
  Lower εr than the cellulose film, but the most rigorously flex-cycle-tested material
  found in this whole search. Frequency range tested: 0.05 Hz – 10⁶ Hz only. (Sheima et
  al., *ACS Appl. Mater. Interfaces* 14(35), 40257–40265, 2022.)

**Pattern, stated plainly:** the further a material's flexibility claim is backed by an
actual bend or cycle test — rather than just being made from a soft-sounding polymer —
the lower its reported permittivity, and the lower the frequency at which anyone
bothered to measure it. Nothing in this widened search changes the bottom line: no
material anywhere in this search is both genuinely bend-tested *and* reaches anywhere
near εr = 100 *and* is characterized near 10 GHz.

---

## 4. Direct answer against Example 4's actual spec

Example 4 (`docs/seven-example-design-unknowns.md` §2–3) needs a host slab with
**εr = 100, µr = 1**, explicitly a lossless idealization in the patent's own FIG. 8D,
ground-backed, period 2.125 mm, hole radius swept 0.2–1 mm, at ~10 GHz, and — because
this is a pliable-skin patent — implicitly flexible enough to conform with the rest of
the 0.87–2 mm-thick stack.

Nothing found in this search is a real-material candidate for that host:

- The closest **genuinely flexible + genuinely 10 GHz-characterized** materials
  (§1.1) reach εr ≈ 20–23, about a fifth of the target, and even the best of those
  (SrTiO₃@VTMS/PB) leans on a fracture-strength claim rather than an elastomeric
  bend test.
- The materials that reach εr ≥ 100 (§1.2) are uniformly measured at 1 kHz–1 MHz, four
  to seven orders of magnitude below 10 GHz, with no bend test performed, and the
  ceramics involved (CCTO in particular) are documented to lose most of their
  permittivity advantage well before reaching microwave frequency.
- The one candidate that is both microwave-characterized and reaches a huge number
  (§1.3, PVA/MXene at X-band) achieves it through a conductive percolation mechanism
  incompatible with the patent's lossless idealization, and has no published
  flex-durability data.

**This does not mean Example 4 is disprovable as physics — it means it is
unsupported by any published material.** A program betting on Example 4 today would
need either (a) a genuinely new material result nobody has published yet, most
plausibly by pushing the MXene-percolation route (§1.3/§2) toward lower loss and
confirmed bend durability, or (b) accepting Example 4 as excluded from the buildable
set on current materials science, consistent with `docs/seven-example-design-
unknowns.md`'s finding #4 that "three of the seven contradict the patent's own
host-material statement" and that Example 4 specifically "needs an unnamed εr = 100
host."

---

## What could not be verified

Stated plainly, without smoothing:

| Question | Status |
|---|---|
| CaCu₃Ti₄O₁₂/CoFe₂O₄/silicone rubber composite's exact loading fraction, precise X-band tanδ, and whether it was ever bend-tested | **Not verified.** Springer/*J. Mater. Res.* returned an authentication redirect to every fetch attempt; only the abstract-level εr ≈ 50 (CCS-3) figure and "X-band" frequency claim, both from secondary search summaries, could be recovered. |
| Whether the Ti₃C₂Tₓ/P(VDF-TrFE-CFE) εr ≈ 10⁵ near-percolation result (Tu et al. 2018) was measured at any frequency above 1 MHz | **Not verified.** The abstract/summary reachable from here does not state the measurement frequency explicitly; percolative dielectric composites of this type are conventionally characterized kHz–MHz, but that is an inference from field convention, not a statement in the source. |
| Whether the PVA/Ti₃C₂Tₓ MXene X-band films (Mirkhani, Zeraati et al. 2019) underwent any bend-radius or bend-cycle test | **Not found.** ACS Publications returned HTTP 403 to every direct fetch; PubMed's abstract page did not render the actual abstract text to this tool; all data on this paper comes from search-engine summaries of the abstract, which do not mention mechanical testing either way — its absence from the summary is not proof of its absence from the paper. |
| The Zhang et al. "interfacial buffer layer" BaTiO₃-epoxy result (εr = 7.5–8.5, tanδ = 0.02–0.03 at 8.2–12.5 GHz, 20 vol%) cited secondhand in an early search summary | **Not independently checked.** This figure surfaced only inside a WebSearch-engine synthesis discussing related work cited by Yao, Lin & Chang (2021); the primary Zhang et al. paper itself was not located or fetched directly. Treat as a lead, not a confirmed citation. |
| Whether SrTiO₃@VTMS/polybutadiene's "high bending strength" (55.2 MPa) reflects genuine wrap-around-a-curve pliability or only fracture resistance under a static bend-test load | **Ambiguous by convention, not by the source.** "Bending strength" (flexural strength, MPa) is the standard mechanical figure of merit for how much stress a specimen — including rigid ceramics — withstands before cracking in a three-point bend test. It is a real, useful number, but it does not by itself establish that a sheet can be wrapped around a small-radius curve without cracking, which is the property this program actually needs. The paper was not fetched in full; this is a caveat about what the abstract-level number can and cannot support, not a claim that the paper is wrong. |
| MDPI-hosted sources | **Not directly fetched.** MDPI returns HTTP 403 to automated fetches from this environment (a standing, documented limitation per other repo docs). Two MDPI-published sources used in this document (Yao, Lin & Chang 2021, *Polymers*; Mihai et al. 2023, *Materials*) were reached instead via their PMC mirrors, which were not blocked. |
| ScienceDirect-hosted full texts | **Not directly fetched** for any source in this document; ScienceDirect returns HTTP 403 to automated fetches from this environment, consistent with the standing caveat in `docs/xband-absorber-substrate-shortlist.md` and `docs/voltera-multilayer-capability.md`. Where a ScienceDirect-hosted paper's data appears above, it was recovered from a search-engine abstract summary, never the full text — flagged per-row above where load-bearing. |
| Springer/Nature auth-redirect sources (`srep35763`, the CCTO/silicone resin *Appl. Phys. A* paper, the *J. Mater. Res.* CCS-3 paper) | **Partially recovered.** `srep35763` eventually rendered after following its cookie-redirect chain and is treated as directly fetched above. The other two did not resolve past the redirect and rely on search-engine summaries only. |
| Local corpus check (`F:\data`, per global config's mandatory-research-corpus rule) | **Checked, zero relevant results.** A dedicated grep pass across `F:\data\arxiv-chunks` (~40,000 full-text papers), scoped to `cond-mat.mtrl-sci`, `cond-mat.soft`, `physics.optics`, `physics.class-ph`, `physics.ins-det`, found no paper on flexible high-permittivity composites, BaTiO₃/PVDF-based dielectrics, or ceramic-polymer flexibility tradeoffs. Root cause, not absence-of-evidence: this corpus's categorized content in those categories is almost entirely 2007, with no `physics.app-ph`/`eess.SP` category; its only recent slice (~2026 IDs) is exclusively CS/AI/ML papers. The flexible-high-k-composite field cited above (2006–2024) sits almost entirely outside this corpus's coverage window. Treat as a corpus coverage gap, not a negative finding. |

## Primary sources

**Family A — flexible and microwave-characterized:**
- Koulouridis, Kiziltas, Zhou, Hansford & Volakis, "Polymer–Ceramic Composites for
  Microwave Applications: Fabrication and Performance Assessment," *IEEE Trans.
  Microwave Theory Tech.* 54(12), 4202–4208 (2006). [IEEE Xplore](https://ieeexplore.ieee.org/document/4020461/)
- Castro et al., "High-Permittivity and Low-Loss Electromagnetic Composites Based on
  Co-fired Ba₀.₅₅Sr₀.₄₅TiO₃ or MgCaTiO₂ Microfillers for Additive Manufacturing and
  Their Application to 3-D Printed K-Band Antennas," *J. Microelectron. Electron.
  Packag.* 13(3), 102. [Meridian Allen Press](https://meridian.allenpress.com/jmep/article/13/3/102/36693/)
- Yang, Yuan, Li et al., "Ultra-high dielectric constant and thermal conductivity
  SrTiO₃@VTMS/PB composite for microwave substrate application," *Appl. Surf. Sci.*
  622, 156888 (2023). [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0169433223005640)
- Rajesh, "SrTiO₃-Filled PTFE Composite Laminates for Microwave Substrate
  Applications," *Int. J. Appl. Ceram. Technol.* 6, 553 (2009). [Wiley](https://ceramics.onlinelibrary.wiley.com/doi/10.1111/j.1744-7402.2009.02389.x)
- Thomas et al., "Mechanically Flexible Butyl Rubber–SrTiO₃ Composite Dielectrics for
  Microwave Applications," *Int. J. Appl. Ceram. Technol.* (2011). [Wiley](https://ceramics.onlinelibrary.wiley.com/doi/10.1111/j.1744-7402.2010.02584.x)
- Xiang, Wang, Yang et al., "Dielectric Properties of SrTiO₃/POE Flexible Composites
  for Microwave Applications," *J. Eur. Ceram. Soc.* 27(8–9), 3093–3097 (2007);
  "Low loss flexible SrTiO₃/POE dielectric composites for microwave application,"
  *J. Electroceram.* 24, 20–24 (2010). [Springer](https://link.springer.com/article/10.1007/s10832-008-9453-y)
- Namitha & Sebastian, "Microwave dielectric properties of flexible silicone rubber –
  Ba(Zn₁/₃Ta₂/₃)O₃ composite substrates," *Mater. Res. Bull.* 48, 4911–4916 (2013).
  DOI [10.1016/j.materresbull.2013.07.029](https://dx.doi.org/10.1016/j.materresbull.2013.07.029)
- "Silicone Rubber-BaBiLiTeO₆ Composites: Flexible Microwave Substrates for 5G
  Applications," *J. Electron. Mater.* (2022). DOI [10.1007/s11664-022-09565-z](https://link.springer.com/article/10.1007/s11664-022-09565-z)
- Kumari, Meena, Salim et al., "Dielectric and electromagnetic shielding behavior of
  CaCu₃Ti₄O₁₂/CoFe₂O₄/silicone rubber composites," *J. Mater. Res.* 39, 2684–2695
  (2024). DOI [10.1557/s43578-024-01416-3](https://link.springer.com/article/10.1557/s43578-024-01416-3) — **stranded behind an auth redirect; abstract-level only**

**Family B — high εr, sub-microwave frequency:**
- Chiang & Popielarz, "Polymer Composites with High Dielectric Constant,"
  *Ferroelectrics* 275(1) (2002). [NIST PDF](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=851768) · DOI [10.1080/00150190214285](https://www.tandfonline.com/doi/abs/10.1080/00150190214285)
- Zhang, Shan, Bass, Tong et al., "Process and Microstructure to Achieve Ultra-high
  Dielectric Constant in Ceramic-Polymer Composites," *Sci. Rep.* 6, 35763 (2016).
  DOI [10.1038/srep35763](https://www.nature.com/articles/srep35763)
- Babu, Singh & Govindan, "Dielectric properties of CaCu₃Ti₄O₁₂–silicone resin
  composites," *Appl. Phys. A* 107(3), 697 (2012). DOI [10.1007/s00339-012-6885-7](https://link.springer.com/article/10.1007/s00339-012-6885-7) — **stranded behind an auth redirect; abstract-level only**
- Mirkhani, Zeraati et al., "High Dielectric Constant and Low Dielectric Loss via
  Poly(vinyl alcohol)/Ti₃C₂Tₓ MXene Nanocomposites," *ACS Appl. Mater. Interfaces*
  (2019). DOI [10.1021/acsami.9b00393](https://pubs.acs.org/doi/10.1021/acsami.9b00393) — **403 to direct fetch; abstract-level only via search summary**
- Tu, Jiang, Zhang & Alshareef, "Large Dielectric Constant Enhancement in MXene
  Percolative Polymer Composites," *ACS Nano* 12(4), 3369–3377 (2018). DOI [10.1021/acsnano.7b08895](https://pubs.acs.org/doi/10.1021/acsnano.7b08895)

**Highest εr in genuinely bend-tested composites (any application):**
- Tao & Cao, "Flexible high dielectric thin films based on cellulose nanofibrils and
  acid oxidized multi-walled carbon nanotubes," *RSC Adv.* 10(18), 10799–10805 (2020).
  [PMC9050423](https://pmc.ncbi.nlm.nih.gov/articles/PMC9050423/) — fetched directly
- Sheima et al., "Transient Elastomers with High Dielectric Permittivity for
  Actuators, Sensors, and Beyond," *ACS Appl. Mater. Interfaces* 14(35), 40257–40265
  (2022). [PMC9900591](https://pmc.ncbi.nlm.nih.gov/articles/PMC9900591/) — fetched directly

**Microwave-regime BaTiO₃-epoxy (rigid-matrix comparison point):**
- Yao, Lin & Chang, "Dielectric Properties of BaTiO₃–Epoxy Nanocomposites in the
  Microwave Regime," *Polymers* 13(9), 1391 (2021). [PMC8123311](https://pmc.ncbi.nlm.nih.gov/articles/PMC8123311/) — fetched directly
- Mihai, Caruntu, Rotaru et al., "GHz–THz Dielectric Properties of Flexible
  Matrix-Embedded BTO Nanoparticles," *Materials* 16(3), 1292 (2023). [PMC9921476](https://pmc.ncbi.nlm.nih.gov/articles/PMC9921476/) — fetched directly

**Physics of the loading/flexibility tradeoff:**
- "Synthesis and Characterization of BaTiO₃/Polypyrrole Composites with Exceptional
  Dielectric Behaviour," [PMC6401699](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6401699/) — brittleness-at-high-loading statement, via search summary
- "Structure-interface-performance relationships of ceramic fillers in polymer, metal,
  and ceramic matrix composites: A critical review," *ScienceDirect*
  S2949822826010476 — via search summary
- "The paradigm of the filler's dielectric permittivity and aspect ratio in high-k
  polymer nanocomposites for energy storage applications," *J. Mater. Chem. C* 10(30),
  10823 — aspect-ratio/percolation-threshold discussion, via search summary

**Review context:**
- Hussain, Zahra, Abbas & Zhu, "Flexible Dielectric Materials: Potential and
  Applications in Antennas and RF Sensors," *Adv. Electron. Mater.* 10, 2400240
  (2024). DOI [10.1002/aelm.202400240](https://advanced.onlinelibrary.wiley.com/doi/10.1002/aelm.202400240) — **403 to direct fetch; summary-level only**

**Repo context:**
- `docs/seven-example-design-unknowns.md` — Example 4's full spec (εr = 100, µr = 1,
  FIG. 8D, hole radius 0.2–1 mm, period 2.125 mm, ~10 GHz), and the original unsourced
  claim this document verifies
- `docs/xband-absorber-substrate-shortlist.md`, `docs/voltera-multilayer-capability.md`
  — standing notes on MDPI/ScienceDirect 403s to automated fetches from this
  environment, reproduced again in this search
