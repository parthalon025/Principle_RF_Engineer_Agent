# `R = 3T` versus IPC-2223's 6× rule — which governs bend-radius pruning

**Date:** 2026-09-11
**Ticket:** [#115](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/115) (third question, added 2026-09-08 after #114 surfaced the conflict) — part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104). Referenced as unknown #10 in `docs/RUNNING-LISTS.md` §4, and named "still open" in `docs/requirement-derived-thresholds.md`.
**Question:** US12089385B2 states its EM skin's minimum bend radius as `R = 3T`. The flex-circuit industry's IPC-2223 is commonly cited as `R = 6T` (static, single-sided). The patent's rule is twice as permissive. Which one should this project's own bend-radius validity checks actually enforce, and why?

Provenance tags follow `CONTEXT.md`'s ladder: `MEASURED` → `SIMULATED` → `CALCULATED` → `MANUFACTURER-SPECIFIED` → `LITERATURE-SUPPORTED` → `INTERNAL-HISTORY` → `INFERRED` → `ASSUMED` → `UNKNOWN`. Every patent quote below was read from `knowledge/corpus/us_patent_12089385B2.txt` in this session; every IPC-2223 figure was read from a live fetch of the cited page in this session — none is repeated from memory or from a secondary paraphrase already in this repo.

---

## Bottom line up front

**The two rules are not competing measurements of the same thing — one is a physically mismatched borrowing, the other is a reliability standard for exactly this kind of laminate. The project should default to IPC-2223's 6× rule, not the patent's 3×.**

1. **The patent's `R = 3T` is not derived from anything about flexible circuits, printed conductors, or laminates.** Claim 20 defines it via a formula the description (line 402, 436–438) cites verbatim from a *sheet-metal forming* textbook — Kalpakjian, Schmid & Musa, *Manufacturing Engineering and Technology*, 6th ed., Ch. 16, p. 398 — a formula for predicting cracking on the outside of a single cold-formed bend in ductile **metal**, parameterized by `r`, the tensile reduction of area (a metallurgical ductility figure from a uniaxial tension test to fracture). The patent backs out `r = 12.5%` to land on "3T," states no material test that produced it, and says outright: *"We thus assume the minimum bend radius R to be 3T generally"* (line 440, emphasis added) — `ASSUMED`, by the patent's own word choice, not derived or measured for this EM skin's actual stack.
2. **IPC-2223's 6× rule is a reliability figure developed by and for laminated flexible-circuit constructions** — conductor foil bonded to a flexible polymer film, the same physical class of object this project's own EM skins are. It is grounded in the same beam-bending strain approximation (`ε ≈ T/2R`) that engineering handbooks use for foil fatigue/cracking limits, and the implied allowable strain (≈ 8.3%) sits inside the 5–10% range independently cited for copper-foil ductility in flex laminates. It is not the same formula as the patent's, but on the *only* basis by which the two can be compared honestly — the strain each implies — the patent permits roughly double the peak bending strain IPC allows for a one-time static bend, and roughly 30× what IPC allows for a part that will be flexed repeatedly.
3. **IPC-2223 itself is paywalled** (confirming `docs/RUNNING-LISTS.md` §1's existing pattern for standards access). No copy of the primary text was reachable in this session. The numbers below rest on independent DFM-guide restatements, cross-checked across four sources, with the genuine spread between them stated rather than hidden — see §2 and §6.
4. **Nothing in this repo's code currently enforces either rule.** `grep` across `rf_tools/`, `designs/` finds `R = 3T` named only in docstrings (`designs/design_families.py:579`, ADR-0018, ADR-0045) as a planned spine field — there is no `min_bend_radius_mm` function, no pruning check, anywhere. This document settles which number that check should use once #115 builds it; it does not change any behaviour that exists today.
5. **This project's own already-written framework (`docs/requirement-derived-thresholds.md`) had already classified this correctly as "A + B" — a standards choice that must be *stated*, never silently inherited.** This document does not override that; it supplies the missing physical reasoning for what the *default* should be when a requirement is silent, which is what #115 actually needs to close.

---

## 1. The patent's rule, read from the primary text

### 1.1 What claim 20 states, verbatim

> "The electromagnetic skin of claim 1, wherein the pliable thin film has a minimum bend radius, R, of approximately 3T, in which R is defined as follow[s]:
>
> R = T(50/r − 1),
>
> where r is the tensile reduction of area of the pliable thin film and T is the thickness of the pliable thin film."
(`knowledge/corpus/us_patent_12089385B2.txt` lines 196–221, claim 20.)

### 1.2 What `T` means

Claim 20 itself says `T` is "the thickness of the pliable thin film" — the same `T` bounded by claim 7 ("the pliable thin film is less than or equal to 2 mm in thickness") and by the description's "by 'thin'… we mean less than about 2 mm in thickness" (line 400). Claim 1 defines the EM skin as "a pliable thin film; and sub-wavelength elements incorporated into and/or on" it — so `T` is the **whole flexible layer**, elements included, not a conductor-foil thickness in isolation. This matches how this project already carries it: `docs/xband-absorber-substrate-shortlist.md` computes `R = 2.6–6.0 mm` from the patent's own `0.87–2.0 mm` **total skin thickness**, and `docs/adr/0044` repeats the same pairing. `CALCULATED` (arithmetic on the patent's own stated numbers): `R = 3 × 0.87 mm = 2.61 mm` at the thin end, `R = 3 × 2.0 mm = 6.0 mm` at the thick end.

### 1.3 Where the formula actually comes from, and why "3T"

The description states the source and the reasoning in full (lines 400–440):

> "There is an inverse relationship between bendability and the tensile reduction of the area of the material. The minimum bend radius, R, may be approximated as follows: R = T(50/r − 1), … where r is the tensile reduction of area of the sheet metal, T is the thickness. (*Manufacturing Engineering and Technology*, 6th Ed. by Serope Kalpakjian, Steven R. Schmid, Hamidon Musa; Pearson Education (2009), Chap. 16, p. 398, herein incorporated by reference)."
>
> "A minimum bend radius R of zero means that the sheet can be folded over itself. For thin polymer sheet materials (e.g., less than about 2 mm in thickness), the minimum bend radius R is generally assumed to be zero. According to embodiments of the present invention, though, various sub-wavelength elements are incorporated into and/or the EM skin. These small elements (which may be rigid or less flexible than the film) affect the overall bendability. Thus, different receipt of the EM skin will have different minimum bend radius. **We thus assume the minimum bend radius R to be 3T generally** for embodiments of the EM skin."

Three things follow directly from this passage, all read off the patent's own words rather than inferred:

- **The formula's own source text says `r` is "the tensile reduction of area of the sheet metal"** (line 436) — the patent is quoting a **sheet-metal** forming formula outright, then applying it to a polymer film. This is not this project's inference; it is what the incorporated reference is *for*. Kalpakjian Ch. 16 covers sheet-metal bending, and the minimum-bend-radius-versus-ductility relationship it presents (`R = T(50/r − 1)`) predicts the onset of **surface cracking on the outer fiber of a single cold-formed bend** in a ductile metal — a fracture-mechanics criterion calibrated against tensile-test ductility of metals (mild steel, aluminum, brass, etc. in the textbook's own worked table), not against a laminate's fatigue life under repeated or sustained flexing.
- **The patent supplies no measured or cited `r` for its own "pliable thin film."** Solving its own formula backwards, `3 = 50/r − 1 ⟹ r = 12.5%`. `12.5%` tensile reduction of area is a plausible figure for a moderately ductile *sheet metal* in Kalpakjian's own table — it is not a property this patent reports having measured, or cited from anywhere, for the polymer film (or the film-plus-embedded-elements composite) it is actually claiming. `CALCULATED` (algebra on the patent's own stated formula and stated result), with the input `r = 12.5%` itself `UNKNOWN` — the patent never states it, only the "3T" conclusion it implies.
- **The patent's own text marks "3T" as an assumption, not a derivation.** It first states that for a bare thin polymer film, `R` "is generally assumed to be zero" — i.e. the sheet-metal formula, honestly applied to an unfilled ~2 mm polymer sheet with any physically reasonable ductility, would predict negligible minimum bend radius. The embedded metamaterial elements are then invoked as the reason a *nonzero* number is needed, but no test, citation, or further calculation connects "elements exist and are somewhat rigid" to the specific value `3T` rather than `2T`, `5T`, or any other multiple. The sentence is "we thus assume," not "we thus measured" or "we thus derive."

**Conclusion for §1:** `R = 3T` is a formula copied from a sheet-metal-cracking reference, fed an unstated and unmeasured ductility input, and used to produce a round number the patent explicitly calls an assumption to compensate — qualitatively, not quantitatively — for the extra stiffness of embedded elements it never characterizes. `LITERATURE-SUPPORTED` as a patent claim (this project's own source-type mapping ranks a patent below a peer-reviewed paper precisely because "a patent office examines for novelty… not for whether a stated number was measured correctly," per `CONTEXT.md`'s Patent entry) — and on top of that baseline discount, the number itself is the patent's own self-declared assumption, resting on an input that is never stated or sourced.

---

## 2. IPC-2223's rule — what is freely available, and what it says

### 2.1 Access

IPC-2223 ("Sectional Design Standard for Flexible/Rigid-Flexible Printed Boards") is sold by IPC and was not reachable as a primary text in this session — consistent with `docs/RUNNING-LISTS.md` §1's already-recorded pattern that IPC-adjacent standards are commonly paywalled. **Every number below is a secondary restatement** by a fabricator or PCB-design DFM guide, not the standard's own clause text, and is tagged `LITERATURE-SUPPORTED` on that basis (this project's `Partner research`/authority-rank discipline treats an unreviewed secondary web source below a patent, not above it — these are cited as the best available substitute, explicitly flagged as such, not as if they were primary).

### 2.2 What the sources say, and where they agree

Four independent DFM-guide pages were fetched and read in this session:

| Source | Static, single-sided/single-layer | Static, double-sided/multilayer | Dynamic, single-layer | Dynamic, multilayer |
|---|---|---|---|---|
| [JLCPCB, "Flexible PCB Bend Radius: Design Guide & Rules"](https://jlcpcb.com/blog/flexible-pcb-bend-radius) | **6×** | **12×** | **100×** | 100–150× |
| Web-search aggregation citing [RayPCB, "IPC 2223 Standard Explained"](https://www.raypcb.com/ipc-2223/) (direct fetch returned HTTP 503 this session; figures below are from the search engine's indexed excerpt of the same page, not a page Claude rendered directly, and are marked accordingly) | **6×** | **12×** | **100×** | 150–200× |
| [Epectec, "Flex Circuit Design: A Guide to Electrical and Mechanical Integration"](https://blog.epectec.com/flex-circuit-design-a-guide-to-electrical-and-mechanical-integration) | "as low as **6×**" | 10–35× ("complex, multi-layer constructions") | **100×** | increases further, no single number given |
| [HemeixinPCB, "How to Calculate the Flex PCB Bend Radius"](https://www.hemeixinpcb.com/company/news/425-how-to-calculate-the-flex-pcb-bend-radius.html) | **10×** | 10× (2-layer) / **20×** (multilayer) | **100×** | 150× (2-layer); multilayer "not recommended" |
| [PICA Manufacturing, worked example](https://picamfg.com/understanding-copper-limits-bend-radius-in-flex-pcbs/) | (0.5 mm double-sided → ~10 mm, i.e. **20×**) | — | (0.5 mm double-sided → ~20 mm, i.e. **40×**) | — |

**Honest reading of the spread:** three of five sources (JLCPCB, the RayPCB excerpt, Epectec) independently converge on **6×** for a single-sided/single-layer static bend and **12×** for double-sided/multilayer static, with all five agreeing on **100×** as the order of magnitude for a single-layer dynamic (repeatedly-flexed) bend. Two sources (HemeixinPCB, PICA) give higher multipliers for the same nominal case. **This project has no way to adjudicate the discrepancy without the primary standard**, so the number carried forward here is the majority reading — **6× static / 100× dynamic, single conductor layer** — stated explicitly as a secondary-source majority, not a verified clause quote. A design containing more than one conductor layer (this project's Tier B I-shape-over-wire-resonator stacks, e.g.) should use the higher multilayer figure (12×, per the majority sources), which is directly relevant here: this project's own EM skins are never single-layer in the flex-circuit sense — they carry printed elements plus, in several examples, a second conductor layer.

### 2.3 Whether it varies by conductor type or rigid-flex vs. pure-flex

None of the five sources state a *different* multiplier for copper versus another printed conductor (silver, carbon, MXene) — the multiplier is stated purely in terms of layer count and bend regime (static/dynamic), applied to the *total* flex-section thickness (copper + dielectric + adhesive + coverlay, per JLCPCB's explicit breakdown). IPC-2223 covers rigid-flex assemblies as well as pure flex; every source above discusses it as one design standard applying the same static/dynamic multiplier logic to the flexible sections of either construction — none states a separate rigid-flex-specific multiplier distinct from the flex-section rule. **This is a real limit of what could be confirmed without the primary text**: it is plausible the standard's actual clauses carry conductor-thickness or ductility-class dependent adjustment factors that no secondary source reproduces. Flagged, not glossed over.

### 2.4 The physical reasoning behind the multiplier

Two independent sources state the mechanism without a copular formula (JLCPCB: *"the outer part of the bend is subjected to tensile stress… the inner part to compressive stress"*, and stress that must not *"crack or delaminate the copper traces and polyimide substrate"*; HDI Circuit Board: *"the internal bend experiences compressive forces while the external bend experiences tensile forces,"* and recommends siting copper *"on the neutral axis… the point that experiences minimal strain."*). A separate web search for the underlying beam-bending relationship returned the standard thin-beam approximation used throughout flex-circuit engineering literature: the outer-fiber bending strain of a stack of total thickness `T` bent to radius `R` is

```
ε ≈ T / (2R)              (thin-beam approximation, conductor near the outer surface)
```

with copper foil ductility (elongation before fracture) independently cited in that search as **typically limiting outer-fiber strain to 5–10%** for flex-circuit copper. `LITERATURE-SUPPORTED` (secondary restatement; no single verbatim source ties the exact percentage to the exact multiplier, so this is presented as a plausibility cross-check, not a proof).

---

## 3. Are these "the same formula at two assumed strain limits," or genuinely different rules?

`docs/grilling-pass-2026-09-05.md` raised exactly this as the premise to re-examine before #115 closes: *"whether `R = 3T` and IPC-2223's 6× are two competing rules or the same strain formula at two assumed strain limits — if the latter, 'which rule governs' is the wrong question."* Having now read both derivations from source, the answer is: **not the same formula, but comparable only through a common strain lens — and that comparison still favors IPC.**

- **They are not literally the same formula.** The patent's `R = T(50/r − 1)` is Kalpakjian's sheet-metal-forming relation, driven by `r` (tensile reduction of area — a fracture-ductility parameter from a destructive tension test on **metal**). IPC's rule, as reconstructed from the sources above, is grounded in the simple thin-beam bending-strain approximation `ε ≈ T/(2R)`, driven by an allowable **elongation/fatigue strain** for copper foil bonded into a laminate. These measure different physical quantities (necking-to-fracture ductility of a bulk metal specimen, versus safe cyclic/sustained bending strain of a thin foil adhered to a dissimilar substrate) and come from different literatures (metal-forming versus flex-circuit reliability engineering).
- **They *can* be compared on one common, honest basis: the peak bending strain each implies**, using the same thin-beam approximation `ε ≈ T/(2R)` as the yardstick for both (this is the same approximation IPC's own multiplier is understood to encode, per §2.4; applying it to the patent's number is this project's own step, not the patent's).

  | Rule | Multiplier `k` (R = kT) | Implied strain limit `ε = 1/(2k)` |
  |---|---|---|
  | Patent, `R = 3T` | 3 | **16.7%** |
  | IPC-2223, static single-layer | 6 | **8.3%** |
  | IPC-2223, static multilayer | 12 | **4.2%** |
  | IPC-2223, dynamic single-layer | 100 | **0.5%** |

  `CALCULATED` (arithmetic; `ε = 1/(2k)` applied to each cited multiplier). Read this way, the patent's rule is not simply "twice as permissive" as IPC's headline 6× figure by coincidence — it corresponds to an implied strain allowance roughly **2×** IPC's static single-layer figure, **4×** IPC's static multilayer figure (the more relevant comparison for this project's multi-layer element stacks, §2.3), and **~33×** IPC's dynamic figure.

- **So the honest answer to the grilling-pass question is: genuinely different rules, reconcilable only approximately, and the reconciliation still shows the patent is not conservative.** They are not the same formula wearing two strain limits — they are two different physical models that happen to both reduce, under a shared simplifying approximation, to "radius is some multiple of thickness." The multiple each lands on is not an arbitrary choice of safety margin on an agreed formula; it reflects what each formula was built to predict, and IPC's was built to predict laminate/conductor bending reliability — the actual failure mode this project cares about — while the patent's was built to predict metal-sheet cracking during a single forming operation, fed an unstated ductility number.

---

## 4. Why the patent's rule is more permissive — the physical reasoning, plainly

*In plain terms first:* Bend a flat sandwich of materials around a curve, and the outer layer gets stretched while the inner layer gets squeezed — the tighter the curve, the more stretch. Something in the sandwich eventually cracks or peels apart if that stretch is too large. The patent's rule and IPC's rule are both guesses at "how much stretch is too much," but they come from two different worlds: the patent borrowed its guess from a table built for bending sheet steel and aluminum without cracking them **once**, in a factory press; IPC's rule comes from decades of the flex-circuit industry watching copper traces on plastic film actually fail — crack, delaminate, go open-circuit — after being bent and left, or bent and re-bent, in real products. The patent's number was never checked against that kind of failure. That is the whole reason it is looser: it is answering a related but different question, with a made-up input, from a field that has never had to keep a copper trace alive on the surface it's borrowed from.

Concretely, three separate reasons compound rather than one:

1. **Wrong failure criterion.** Kalpakjian's formula predicts *fracture during forming* — a one-time, monotonic bend to a permanent shape, where the metal either cracks on that single pass or it does not. IPC-2223's multipliers are calibrated against **laminate reliability**: conductor fatigue cracking, copper-to-dielectric delamination, and adhesive creep, under either a sustained static bend held for the part's service life or genuinely repeated dynamic flexing. These are different physics. A single-pass fracture limit for ductile metal has no reason to equal a laminate's long-term reliability limit, and nothing in the patent argues that it should — it simply reuses the formula because it is a "minimum bend radius" formula found in a manufacturing-engineering textbook, without checking whether that formula's failure mode matches the EM skin's.
2. **Wrong material class for the input parameter.** `r` (tensile reduction of area) is tabulated for metals with known crystal plasticity behaviour. The patent's actual pliable film is a polymer, and its actual load-bearing risk is the **embedded conductive elements and their bond to the film** — exactly the class of thing IPC-2223 exists to characterize, and exactly the class of thing Kalpakjian's table has no entry for. Applying a metal's `r = 12.5%` (backed out algebraically, never measured) to a polymer-plus-printed-conductor composite is a category error, not a conservative simplification.
3. **The correction for embedded elements is qualitative, not quantitative.** The patent's own logic chain is: bare thin polymer would have `R ≈ 0`; embedded elements make it stiffer; therefore assume `R = 3T`. Nothing ties the multiplier "3" to any property of the elements actually used (size, spacing, elastic modulus, areal coverage) — it is a placeholder acknowledging the effect exists, not a bound derived from it. IPC-2223's multipliers, by contrast, are explicitly keyed to what is physically in the stack (single- vs. multi-layer conductor, static vs. dynamic use) — the axis of variation that actually drives strain at the copper.

None of this means the patent's number is *wrong* for the specific device the inventors built and (presumably) bent without incident — a patent's worked examples can be true of the one embodiment tested. It means the number is not a general design rule this project can trust to generalize to a different conductor set (silver, carbon, MXene), a different element geometry, or a different service profile (a part bent once into a fixed shape versus one flexed repeatedly), because nothing about *why* 3T was chosen ties it to those variables. IPC-2223's multipliers were built to generalize across exactly that variation, which is the entire reason a standard exists instead of one company's own single-example assumption.

---

## 5. Recommendation for this project's bend-radius validity check

This aligns with, and sharpens, `docs/requirement-derived-thresholds.md`'s existing classification of this exact question as **"A + B"**: *"The host's radius of curvature is A [a requirement-stated value]. Which rule governs is a standards choice that should be stated, not inherited."* That framework's governing principle — **"a convention is a default, it is never a threshold"** — applies to both `R = 3T` and IPC-2223's 6×/12× equally: neither may become a silent, hard-coded pass/fail line. What follows is the missing piece: what the **default** should be when a customer requirement invokes no standard of its own.

1. **Default (Kind C, per `docs/requirement-derived-thresholds.md`'s own A/B/C framework, never hard-coded as a Kind A/B physics constant): enforce IPC-2223's multiplier, not the patent's, when no customer requirement states a bend-radius standard or supplies a measured/coupon bend-fatigue limit of its own.**
   - Use **6× total stack thickness** for a single-conductor-layer design, **12×** for a design with two or more conductor layers (this project's own Tier B element stacks — an I-shape resonator over a wire resonator, e.g. — are multilayer by this definition), both `LITERATURE-SUPPORTED` per §2.
   - If the requirement states the part will be repeatedly flexed or handled in service (an access panel, a roll-up antenna) rather than bent once into a fixed conformal shape, use the **dynamic** multiplier (≥100×) instead — the patent's `3T` speaks to neither regime, and this distinction is invisible if the project only ever compares against "IPC's 6×."
   - Reasoning: this project's own EM skins are laminated flexible conductor stacks on a polymer film — precisely IPC-2223's subject matter — while the patent's number is an admitted assumption borrowed from an unrelated failure mode in an unrelated material class (§1, §4). Preferring the number built for this project's actual construction over the number built for sheet-metal presses is not caution for its own sake; it is preferring the source whose failure criterion matches the thing being checked.
2. **Never silently prune on either number without stating which one is in force and why**, per the existing A/B/C rule — a candidate rejected by this check should carry the multiplier used, the resulting `R_min`, and its source (patent vs. IPC vs. requirement-stated vs. measured coupon) in the same place a `capability-verdict` states its reason, so the check is auditable and reversible if the requirement later states its own standard.
3. **A `MEASURED` bend-fatigue coupon result, once bench access exists (`docs/RUNNING-LISTS.md` §4 unknown #1), outranks both** — it would sit at the top of the Evidence hierarchy, above the `LITERATURE-SUPPORTED` rung both numbers in this document occupy. Until then, IPC-2223's figure is the better default specifically because it is closer, in kind, to a measurement: it reflects accumulated flex-circuit failure experience, where the patent's figure reflects one unstated algebraic assumption.
4. **Concretely, for the code this decision feeds:** the `R = 3T`, `T ≤ 2mm` spine-field language in `designs/design_families.py:579` (and its mirrors in `docs/adr/0018` and `docs/adr/0045`) should be read as "the patent's own stated construction parameter, not this project's validity-check rule" — when #115 implements the actual bend-radius pruning function, its default multiplier should be IPC-2223's, sourced per §2, with the multiplier and its provenance stated as a named, overridable input rather than compiled into the formula.
5. **This changes existing numbers already written down elsewhere in this repo, and they should be read accordingly rather than re-derived:** `docs/xband-absorber-substrate-shortlist.md` §4 already computed both figures side by side (`R = 6 mm` at the patent's own 2.0 mm ceiling under `3T`, versus `R = 12 mm` under IPC's static `6T`) and already flagged, correctly, that enforcing the patent's number "is the direction that costs reliability, not the safe direction" — this document supplies the derivation behind that flag. `docs/adr/0044`'s `2.6–6.0 mm` bend-radius figures (from `R = 3T` on the patent's `0.87–2.0 mm` skin) are patent-only figures and should be read as such, not as this project's own governing constraint — its conclusion that the large-radius host regime clears by "one to two orders of magnitude" under `3T` still holds under `6T`/`12T` (§1 of that ADR notes the margin halves, not disappears), so no prior conclusion in this repo that depended on bend radius clearing by a wide margin is invalidated by switching defaults — only the numeric margin itself changes.

---

## 6. Honest limits

- **The primary text of IPC-2223 was not reached.** Every multiplier in §2 is a secondary restatement, and the sources genuinely disagree at the margins (6× vs. 10× for single-layer static; 12× vs. 20× vs. "10–35×" for multilayer static). The **6×/12×/100× figures are carried forward as the majority reading across independently-authored sources**, not as a verified clause quote — anyone with access to the actual standard should correct this document against it before it is treated as settled.
- **One source (RayPCB) could not be fetched directly this session** (HTTP 503); its figures here come from a search engine's indexed excerpt of the same page, a weaker form of access than the other four sources, which were fetched and read directly.
- **No source, primary or secondary, was found stating a conductor-material-specific or rigid-flex-specific multiplier** distinct from the general layer-count/static-dynamic rule — §2.3's gap is real and not filled by anything found in this pass.
- **The strain-based reconciliation in §3 is this project's own step**, applying the thin-beam approximation to the patent's multiplier for comparison purposes; the patent does not itself claim to be expressing a strain limit, so §3's table should be read as "what strain limit the patent's number would imply if judged by IPC's own logic," not as something the patent itself asserts.
- **This document does not resolve what value of `T` a specific candidate design should use** (e.g. whether encapsulation thickness counts) — that is a design-time computation for whichever code implements #115's check, not a fact this research pass can settle from the two source documents alone.
