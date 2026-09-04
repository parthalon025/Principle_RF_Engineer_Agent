# How Military and Aerospace Requirements Documents Express a Limit

**Research date:** 2026-09-03
**Issue:** [#122](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/122), part of map [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104); sharpens [#117](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/117)
**Scope:** What defence and aerospace requirements practice already uses to write down a limit, and which of it this repo can borrow for `designs/requirement_targets.py`.

---

## Bottom line up front

**Threshold/objective is real, and it is exactly what #117 needs.** Defence capability documents state most numeric attributes as a *pair* of values, not one: a **threshold** ("below this the system is not worth building") and an **objective** ("above this we would not pay for more"). The pair is defined in the JCIDS Manual, written into three-column tables in the Capability Development Document (CDD) and Capability Production Document (CPD), and — critically for us — carries an explicit convention for the case where there is no soft zone at all: you write **"Threshold = Objective."** In plain terms: *every requirement declares its own hard floor and its own nice-to-have ceiling, and a requirement with no nice-to-have says so out loud rather than staying silent.*

That answers **Q2** ("who decides whether a limit is hard or soft?") with: **the person stating it, per requirement, by supplying or omitting a second number** — never the quantity itself, and never the grammar alone. The grammar (`shall` vs `should`) does a different, coarser job: it separates binding from non-binding *prose*, and in a specification only `shall` text is contractual at all.

It also answers **Q1** ("is a constraint a distinct kind of thing from a requirement?") with a fairly firm **no, not as a separate object** — with one qualification worth taking seriously:

- **MIL-STD-961E** puts *everything* in Section 3 REQUIREMENTS and gives *everything* a matching entry in Section 4 VERIFICATION. Its own heading for what we would call a constraint is `A.3.16.2 Design and implementation constraints`, described as "the **requirements** that constrain the design and implementation of the entity" — a constraint is a requirement, differentiated by *what it bounds* (the design) rather than by *what kind of object it is*.
- **JCIDS** does have a paragraph literally called "Constraints," but it is prose about external inhibitors (treaties, logistics, manpower) with no value, unit or comparator — it is not a second structured requirement type.
- **NASA** treats constraints as a distinct *input* to requirements definition ("a condition that is to be met," dictated by orbital mechanics, an existing interface, a regulation, or the state of technology), which then get converted into ordinary `shall` requirements. Constraint is a *provenance/origin* label, not a different scoring object.

The genuinely useful distinction all three draw is **performance vs. detail**: performance requirements state *the required result*; detail requirements state *how it must be made*. MIL-STD-961E instructs that detail ("how to") requirements be used "only to the extent necessary." That is the real prune-vs-score axis — and it maps onto #117's derivation chain almost exactly.

**Where our model is genuinely missing something:** a second value per requirement (the objective), an explicit hard/soft or tier field, an origin/rationale field, and a verification-method field. Details in §7.

---

## Currency warning: read this before citing JCIDS to a customer

**JCIDS as a *process* was terminated in 2025.** The 20 August 2025 memorandum from the Secretary of Defense and Deputy Secretary of Defense, "Reforming the Joint Requirements Process to Accelerate Fielding of Warfighting Capabilities," directs the Vice Chairman of the Joint Chiefs of Staff to:

> "Effective immediately, commence the disestablishment of JCIDS and direct the Joint Requirements Oversight Council (JROC) to cease validating Component-level requirement documents to the maximum extent permitted by law. Military Service requirements determinations shall be the Military Services' responsibility. Within 120 days, instructions and manuals governing JCIDS will be rescinded…"
> — [SecDef/DepSecDef memorandum, 20 Aug 2025](https://www.newspacenexus.org/wp-content/uploads/2025/08/SecDef-Memo-20-Aug-2025.pdf), p. 1 (verified verbatim from the PDF)

Plain English: the *committee and paperwork machinery* that produced CDDs and CPDs is being dismantled and each Service now sets its own requirements. What the memo does **not** do is abolish the *vocabulary*. Threshold/objective pairs live on independently in the **Acquisition Program Baseline**, which is a statutory artefact, and KPP remains the standard term for a make-or-break performance parameter. The relabelling is visible even in the source hosting: DAU was renamed Warfighting Acquisition University (`waru.edu`) by a 7 Nov 2025 Secretary of War memorandum.

**Practical consequence for this repo:** a customer document arriving in 2026 may use this vocabulary, may use a Service-specific successor, or may be a plain MIL-PRF-style specification (which never used threshold/objective in the first place — see §5). Design the model around the *concepts*, not around the JCIDS document names.

**Could not verify:** the post-JCIDS successor guidance in detail. The successor memorandum PDF on `media.defense.gov` returned HTTP 403 to this session, and `dau.edu` / `waru.edu` / `acq.osd.mil` / `esd.whs.mil` all refuse automated fetches. The threshold/objective definitions below are therefore quoted from the **2009 and 2012 editions of the JCIDS Manual** (openly published, retrieved in full), not the final 2021 edition. The definitions were stable across those editions and are repeated verbatim in DoD acquisition training material, but treat the exact 2021 wording as unverified.

---

## 1. Threshold and objective — the two-number requirement

### What it is, plainly

Instead of "gain shall be at least 5 dBi," a defence capability document says "gain: threshold 5 dBi, objective 8 dBi." The threshold is the number below which the thing is not worth building. The objective is the number above which nobody would pay for more. The gap between them is officially called the **trade space** — the room the engineers are allowed to move in.

### Verbatim definitions

> "c. The **threshold value** for an attribute is the **minimum acceptable value** considered achievable within the available cost, schedule, and technology at low-to-moderate risk. Performance below the threshold value is not operationally effective or suitable or may not provide an improvement over current capabilities. The **objective value** for an attribute is the **desired operational goal** achievable but at higher risk in cost, schedule, and technology. Performance above the objective does not justify additional expense. **The difference between threshold and objective values sets the trade space** for meeting the thresholds of multiple KPPs."
> — *JCIDS Manual*, 31 July 2009, Enclosure B, para 1.c (retrieved via [acqnotes.com mirror](https://acqnotes.com/Attachments/JCIDS%20Manual%20-%2031%20July%202009.pdf); emphasis added)

> "b. … **Below the threshold value, the military utility of the system(s) becomes questionable.** … DOD components will, at a minimum, budget to achieve all stated thresholds."
> — *ibid.*, Enclosure B, para 1.b

### How the pair is actually written down

This is the part worth copying. The 19 Jan 2012 edition gives the drafting instruction and the table shape:

> "(d) Present each attribute in output-oriented, measurable, and testable terms. For each attribute, provide a **development threshold value representing the value below which performance is unacceptable**. Provide **objective values for attributes when the increased performance level provides significant increases in operational utility**. **If the objective and the threshold values are the same, indicate this by including the statement "Threshold = Objective."** … The PM may use this information to provide incentives for the developing contractor or to weigh capability tradeoffs between threshold and objective values."
> — *JCIDS Manual*, 19 Jan 2012, Enclosure B, para 3.a(6)(d) ([acqnotes.com mirror](https://acqnotes.com/Attachments/JCIDS%20Manual%20for%20the%20Operation%20of%20the%20JCIDS%20%2019%20Jan%202012.pdf))

And the tables themselves (Tables B-6, B-7, B-8 of that manual) are all three columns wide, one table per tier:

| Key Performance Parameter | Development Threshold | Development Objective |
|---|---|---|
| KPP 1 | *Value* | *Value* |

| Key System Attribute | Development Threshold | Development Objective |
|---|---|---|
| KSA 1 | *Value* | *Value* |

| Additional Performance Attribute | Development Threshold | Development Objective |
|---|---|---|
| Attribute 1 | *Value* | *Value* |

Two details that matter more than they look:

1. **The objective is optional; the threshold is not.** You always give the floor. You give the ceiling only "when the increased performance level provides significant increases in operational utility." So absence of an objective is meaningful data, not a gap.
2. **"Threshold = Objective" is written explicitly.** A requirement with no soft zone must *say so*. This is the direct precedent for making "is this hard or soft?" a per-requirement, human-supplied fact instead of something the loop infers.

A third, subtler point, on whether the threshold is a cliff or a slope:

> "A deeper review of trade-offs at and around threshold values may be beneficial to explore incremental return on investment **where particular thresholds are insensitive to small deviation** at great advantage in cost, performance, and schedule…"
> — *JCIDS Manual*, 31 July 2009, Enclosure B, Appendix A, para 3.c

Plainly: even the threshold is not always a hard cliff — some are worth renegotiating for a big cost saving, others are not, and that varies per requirement too. #117's "which constraint would I have to relax and by how much" diagnosis is the same idea from the other direction.

---

## 2. Requirement tiering: KPP / KSA / APA

### Plainly

Three levels of "how much does missing this hurt." Top tier kills the programme; middle tier gets a senior person's attention; bottom tier is recorded and tracked but does not, on its own, stop anything.

### Verbatim

> "e. **KPPs are those system attributes considered most critical or essential** for an effective military capability. The CDD and the CPD must contain sufficient KPPs to capture the minimum operational effectiveness, suitability, and sustainment attributes needed… **Failure to meet a CDD or CPD KPP threshold may result in a reevaluation or reassessment of the program or a modification of the production increments.** … The number of KPPs (beyond the required mandatory KPPs) should be kept to a minimum to maintain program flexibility."
> — *JCIDS Manual*, 31 July 2009, Enclosure B, para 1.e

> "f. **KSAs are those system attributes considered critical or essential for an effective military capability but not selected as KPPs.** KSAs provide decision makers with **an additional level of capability prioritization below the KPP** but with senior sponsor leadership control (generally 4-star level, Defense agency commander, or Principal Staff Assistant)."
> — *ibid.*, para 1.f

**APA (Additional Performance Attribute)** — the third tier — is not defined as a named term in the 2009 edition; it appears from the 2012 edition onward as its own table (Table B-8 above) alongside the KPP and KSA tables, i.e. same threshold/objective structure, lowest priority. The commonly quoted definition ("performance attributes… not important enough to be considered a KPP or KSA, but still appropriate to include in the CDD") comes from DoD acquisition training glossaries whose pages refused automated retrieval in this session; **treat that specific wording as unverified**, while the *existence* and *table structure* of the APA tier is verified verbatim from the 2012 manual.

### What each tier means for whether failing it kills the design

| Tier | Missing the threshold means | Prune or score? |
|---|---|---|
| **KPP** | Formal reassessment of the whole programme; validation of the requirement can be rescinded; possible restructure or cancellation | **Prune** — but by a *human review*, not automatically |
| **KSA** | Escalated to a very senior sponsor for a decision | **Score, loudly** — flagged for a human, not silently discarded |
| **APA** | Recorded and traded off within the programme | **Score** |

The important nuance for #117: **even a KPP miss does not automatically delete the candidate.** The language is "*may* result in a reevaluation or reassessment." Defence practice deliberately routes a hard-limit failure to a human rather than to a silent filter. That is a strong argument that our loop should report "this candidate fails a hard requirement" prominently rather than removing it from the output entirely — which is the same conclusion #117 reaches from "pruning is honest only when the loop says what it removed and why."

---

## 3. The `shall` / `should` / `will` / `may` convention

### Who defines it, for defence specifications

**MIL-STD-961E w/CHANGE 2, 9 January 2014**, *Defense and Program-Unique Specifications Format and Content*, paragraph 4.6.6 "Commonly used words and phrases" (retrieved in full from the [acqnotes mirror of the ASSIST original](https://acqnotes.com/wp-content/uploads/2014/09/MIL-STD-961-Defense-and-Program-Unique-Specifications-Format-and-Content-9-Jan-2014.pdf); the PDF carries "Source: https://assist.dla.mil"):

> "h. **"Shall", the emphatic form of the verb, shall be used throughout sections 3, 4, and 5 of the specification whenever a requirement is intended to express a provision that is binding.** … "Shall" shall not appear in sections 1, 2, or 6 of the specification.
>
> i. **"Will" may be used to express a declaration of purpose on the part of the Government.** It may be necessary to use "will" in cases when simple futurity is required.
>
> j. **Use "should" and "may" to express nonmandatory provisions.**
>
> k. **"Must" shall not be used to express a mandatory provision. Use the term "shall."**"

And, directly relevant to comparators:

> "e. In stating limitation, the phrase shall be stated thus: **"The diameter shall be not greater than …"** for the upper limit, or **"The diameter shall be not less than …"** for the lower limit."
> — *ibid.*, para 4.6.6.e

That is our `AT_MOST` and `AT_LEAST`, written out in words, in a 1970s-lineage standard. Our comparator vocabulary is already the right shape.

### The civil-side equivalent

**NASA/SP-2016-6105 Rev 2**, *NASA Systems Engineering Handbook*, Appendix C.1 "Use of Correct Terms" ([nasa.gov PDF](https://www.nasa.gov/wp-content/uploads/2018/09/nasa_systems_engineering_handbook_0.pdf), p. 197):

> "**Shall = requirement**
> **Will = facts or declaration of purpose**
> **Should = goal**"

Same three-way split, one word shorter. NASA's glossary makes the requirement/expectation boundary explicit and it reads like a description of our `PROPOSED` → `CONFIRMED` flow:

> "**Stakeholder Expectations:** A statement of needs, desires, capabilities, and wants that are **not expressed as a requirement (not expressed as a "shall" statement)** is referred to as an "expectation." **Once the set of expectations from applicable stakeholders is collected, analyzed, and converted into a "shall" statement, the expectation becomes a requirement.** Expectations can be stated in either qualitative (non-measurable) or quantitative (measurable) terms. **Requirements are always stated in quantitative terms.**"
> — *ibid.*, Appendix B Glossary, p. 191

Plainly: *the customer's prose is not yet a requirement; it becomes one when somebody turns it into a number with a `shall` in front of it.* That is precisely what `propose_target` / `confirm_target` do, and NASA agrees the conversion is a judgement call somebody has to own.

**INCOSE:** the *Guide to Writing Requirements* (INCOSE-TP-2010-006-04, V4, June 2023) is the civil-side rulebook the ticket asked about. **`incose.org` returned HTTP 403 to every fetch attempt in this session**, so no rule text is quoted here first-hand. A vendor whitepaper reproducing the guide's rule/characteristic table ([QRA Corp, *Automating the INCOSE Guide for Writing Requirements*](https://edu.qracorp.com/hubfs/Automating%20the%20INCOSE%20Guide%20for%20Writing%20Requirements.pdf)) lists characteristics including **"Abstraction — State 'what' must be done, not 'how' to do it"**, **"Tolerance — Define performance quantities with an appropriate range"**, **"Quantification — Provide measurable performance targets"**, and **"Rule R6: Use appropriate units when stating quantities"**. Rule numbers for Abstraction and Tolerance could not be extracted reliably from the whitepaper's multi-column layout and are **not asserted here**. The "Tolerance … appropriate range" characteristic is the same instinct as threshold/objective and is the one INCOSE idea most worth chasing down in the real guide later.

**ISO/IEC/IEEE 29148:2018** *Systems and software engineering — Life cycle processes — Requirements engineering* is the underlying international standard for the modal verbs (`shall` = requirement, `should` = recommendation, `may` = permission, `can` = possibility/capability). It is **paywalled**; `iso.org` also returned 403 to this session. Not quoted here.

### Answer to Q2

**The grammar does not decide hardness on its own — it only decides binding vs. non-binding, and in a specification the non-binding words are barely used at all.** MIL-STD-961E confines all requirement text to `shall`; `should`/`may` express "nonmandatory provisions" and Section 6 Notes, where softer language lives, "is not contractually binding" (para 5.11). So in a real defence specification, *everything in scope is hard*. Softness is expressed in the *capability* document instead, by the objective value sitting alongside the threshold.

So, for #117: **hardness is a per-requirement property supplied by the person stating the requirement**, expressed as a second number (objective) plus a tier (KPP/KSA/APA), and *never* a property of the quantity. Gain is not "inherently soft" and cure temperature is not "inherently hard" — a customer can state either as either.

---

## 4. Do they separate "constraints" from "performance requirements"?

Short answer: **they separate *performance* from *detail*, not *requirements* from *constraints*.** Constraints are a subcategory of requirement, or an input that becomes one.

### MIL-STD-961E: constraints are requirements

Section 3 of a specification is called REQUIREMENTS and takes everything:

> "5.8 SECTION 3 – REQUIREMENTS. This section shall define the requirements that the entity must meet to be acceptable. … a. **Each requirement shall be stated in such a way that an objective verification can be defined for it.** b. Each requirement should be cross-referenced to the associated verification. c. **Only requirements that are necessary, measurable, achievable, and verifiable shall be included.** d. **Requirements shall be worded to provide a definitive basis for acceptance or rejection.** … f. Requirements shall be worded such that each paragraph only addresses one requirement or topic."
> — MIL-STD-961E w/CH-2, para 5.8

And the closest thing to a "constraints section" is a *requirements* paragraph:

> "**A.3.16.2 Design and implementation constraints.** Where applicable, this paragraph should specify **the requirements that constrain the design and implementation** of the entity."
> — *ibid.*, Appendix A, para A.3.16.2

That is the sentence that settles **Q1**. A constraint *is* a requirement; the noun "constraint" describes what it acts on, not what kind of record it is.

### The real boundary: performance vs. detail

> "**3.35 Performance specification.** A specification that **states requirements in terms of the required results with criteria for verifying compliance, but without stating the methods for achieving the required results.** A performance specification defines the functional requirements for the item, the environment in which it must operate, and interface and interchangeability characteristics."
>
> "**3.13 Detail specification.** A specification that **specifies design requirements, such as materials to be used, how a requirement is to be achieved, or how an item is to be fabricated or constructed.** A specification that contains both performance and detail requirements is still considered a detail specification."
> — *ibid.*, paras 3.35 and 3.13

And the drafting rule, which is a policy statement about how much "how" the customer is allowed to impose:

> "5.8.1 … **Performance specifications shall not prescribe how a performance requirement is to be achieved by requiring the use of specific materials or parts** or detailed requirements for the design or construction of the item beyond those needed to ensure interchangeability with existing items."
>
> "5.8.2 … To the greatest extent possible, requirements in detail specifications shall be in terms of performance. **Detail specifications shall specify materials, design or construction requirements, or "how to" requirements only to the extent necessary to ensure the adequacy, safety, and interchangeability of the item being acquired.**"
> — *ibid.*, paras 5.8.1 and 5.8.2

Plainly: *say what you need, not how to build it — and if you must say how, justify it.* That is a direct, quotable answer to #117's "which constraints prune before scoring versus penalise within it": in defence practice, a customer naming a **material** (a detail requirement) is treated as an exception requiring justification, while a customer naming a **band, a mass, a thickness** (performance requirements) is the normal case. If #117 wants a principled default, "performance requirements score; detail requirements prune, and prune loudly because they should have been rare," is a defensible one with a standard behind it.

Note the asymmetry this creates for us: **a mixed document is classified by its strictest content** ("a specification that contains both performance and detail requirements is still considered a detail specification"). A single "must be MXene" clause reclassifies the whole requirement set as design-constrained. That is a useful thing for the loop to report back.

### JCIDS: "Constraints" exists but is prose

> "(11) **Constraints:** Identify any known constraints that could inhibit satisfying the need -- such as **arms control treaties, logistics support, transportation, manpower, training or non-military barriers.**"
> — *JCIDS Manual*, 19 Jan 2012, Enclosure B (JUON/JEON format), para (11)

No value, no unit, no comparator, no verification. It is context, not a scored object. **This is evidence against giving constraints their own structured model.**

### NASA: constraint as an origin, not a type

> "The project team should also identify the constraints that may apply. **A "constraint" is a condition that is to be met.** Sometimes a constraint is dictated by **external factors such as orbital mechanics, an existing system that must be utilized (external interface), a regulatory restriction, or the state of technology**; sometimes constraints are the result of the overall budget environment."
> — NASA/SP-2016-6105 Rev 2, §4.1.1.2.2 "Understand Stakeholder Expectations"

And in the requirement rationale guidance:

> "**Document Design Constraints:** Constraints imposed by the results from decisions made as the design evolves should be documented. **If the requirement states a method of implementation, the rationale should state why the decision was made to limit the solution to this one method of implementation.**"
> — *ibid.*, Table 4.2-2 Rationale box, p. 59

Plainly: *if you tell the engineers what to build rather than what to achieve, you owe them a written reason.* This is the missing half of #117's "attributable and recorded on the design" — defence/aerospace practice makes the *rationale* a required field, not an optional note.

---

## 5. A real published example: MIL-R-7705B, Radome, General Specification For

`MIL-R-7705B` (14 January 1975), *Radome, General Specification For*, covers "the general design and performance requirements for radomes used in flight vehicles and fixed ground installations." Retrieved in full from [everyspec.com](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-R/download.php?spec=MIL-R-7705B.024492.pdf). It is a scanned document with imperfect OCR; wording below is transcribed from the scan and lightly corrected for OCR damage where the meaning is unambiguous.

**Why it is worth reading:** it is the closest published thing to a customer specification for a conformal electromagnetic structure — an RF-transparent shaped skin whose electrical performance is specified separately from its construction. That is structurally our problem.

### Structure

- **Section 1 SCOPE** — classification into **Type** (I–VI), **Grade** (by safety and system criticality), **Class** (by general application), **Style** (by construction).
- **Section 3 REQUIREMENTS**
  - `3.3 Design and construction` — the *detail* half: materials, resins, reinforcement, sandwich cores, drain holes, structural loads, interchangeability, size and weight.
  - `3.4 Performance` → `3.4.1 Electrical requirements`, all with numeric limits in Table 1:
    - `3.4.1.1 Transmission` — "The minimum and average one-way power transmission through the radome **shall not be less than** the limits specified in table 1."
    - `3.4.1.2 Power reflection` — "The power reflected back into the antenna by the radome **shall not exceed** the value specified in table 1."
    - `3.4.1.3 Main-lobe beamwidth` — change at half-power points "**shall not exceed** the values specified in table 1."
    - `3.4.1.4 Pattern ripple`, `3.4.1.5 Side lobes` ("shall not increase by more than the limit specified"), `3.4.1.6 Axial ratio`, `3.4.1.7 Beam deflection`, `3.4.1.8 Beam deflection rate`, `3.4.1.9 Dielectric constant and loss tangent`.
- **Section 4 QUALITY ASSURANCE PROVISIONS** — classification of inspections: construction sample inspections, first article inspections, quality conformance inspections.

### Table 1, "Electrical Performance Characteristics"

The table's columns are **radome TYPE (I, II, III, IIIA, IV, V, VI)** and its rows are keyed by **applicable paragraph** (`3.4.1.1`, `3.4.1.2`, …), with a UNIT column. Sample values recovered from the scan: minimum/average transmission 95 %/85 % for one type, 85 %/75 % and 85 %/70 % for others; power reflection 2 %; beamwidth change 5 % or 10 %; sidelobe increase 2 dB.

**This is the most important structural finding in the whole example.** A MIL specification carries **one limit per requirement per product class** — not a threshold/objective pair. The "how good does it have to be" question is answered by *which class of product you bought*, decided before the specification is applied. Threshold/objective belongs to the *capability* document upstream; by the time it reaches a specification, the trade space has been spent and a single number remains.

For us: **a customer handing over a MIL-PRF/MIL-DTL-style specification will give single hard numbers; a customer handing over a capability-style requirements document will give pairs.** The model has to accept both, which is another argument for making the objective an *optional second value* rather than a required one.

### Export control

MIL-R-7705B is openly published on ASSIST/everyspec and is **not** export-controlled. No controlled or non-public material was sought or obtained for this note. The parts of the defence requirements world that *are* restricted — programme-specific System Requirements Documents, Technical Requirements Documents, actual populated KPP tables for a real radar or EW programme — are distribution-limited or ITAR-controlled (22 CFR Part 121 Category XI covers military electronics including radomes and antennas designed for military application). **No attempt was made to obtain any of those, and nothing in this note is inferred about their contents.** Everything above comes from openly published format standards, an openly published general specification, and openly published process manuals.

---

## 6. Verification method → our provenance ladder

### What the four methods are

**MIL-STD-961E** requires a verification for every requirement and names four ways:

> "5.9.1 Verification. Section 4 shall include all inspections to be performed … to determine that the item to be offered for acceptance conforms to the requirements in section 3 of the specification. **Verification may be accomplished by analysis, demonstration, examination, testing, or any combination thereof.**"
> — MIL-STD-961E w/CH-2, para 5.9.1

**NASA/SP-2016-6105 Rev 2** (p. 93) defines the same four ("examination" ≈ "inspection") in usable detail:

> "**Analysis:** The use of mathematical modeling and analytical techniques to predict the suitability of a design to stakeholder expectations based on calculated data or data derived from lower system structure end product verifications. Analysis is generally used when a prototype; engineering model; or fabricated, assembled, and integrated product is not available. **Analysis includes the use of modeling and simulation as analytical tools.** A model is a mathematical representation of reality. A simulation is the manipulation of a model. **Analysis can include verification by similarity of a heritage product.**"
>
> "**Demonstration:** Showing that the use of an end product achieves the individual specified requirement. It is generally a **basic confirmation of performance capability, differentiated from testing by the lack of detailed data gathering.**"
>
> "**Inspection:** The **visual examination of a realized end product.** Inspection is generally used to verify physical design features or specific manufacturer identification. … **Inspection can include inspection of drawings, documents, or other records.**"
>
> "**Test:** The use of an end product to obtain **detailed data** needed to verify performance… **Testing produces data at discrete points for each specified requirement under controlled conditions** and is the most resource-intensive verification technique."

NASA also makes the verification method a **stored field on the requirement**, decided when the requirement is written, not later:

> "**Verification method** — Captures the method of verification (test, inspection, analysis, demonstration) and **should be determined as the requirements are developed.**"
> — *ibid.*, Table 4.2-2 Requirements Metadata, p. 59

### The mapping

Our ladder (`CONTEXT.md`): `MEASURED` → `SIMULATED` → `CALCULATED` → `MANUFACTURER-SPECIFIED` → `LITERATURE-SUPPORTED` → `INFERRED` → `ASSUMED` → `UNKNOWN`.

| Verification method | What it actually is | Our nearest rung | Fit |
|---|---|---|---|
| **Test** | Detailed instrumented data from real hardware under controlled conditions | `MEASURED` | **Exact.** ADR-0013's externally-obtained Touchstone file *is* a test. |
| **Analysis** (simulation half) | Manipulating a model — "a simulation is the manipulation of a model" | `SIMULATED` | **Exact.** Palace/openEMS runs. |
| **Analysis** (closed-form half) | Mathematical prediction from calculated data | `CALCULATED` | **Exact.** `rf_tools/calculations.py`. |
| **Analysis** ("verification by similarity of a heritage product") | It worked on the last one, and this one is close enough | `LITERATURE-SUPPORTED` at best, honestly `INFERRED` | **Poor fit.** One named method spans three of our rungs. See below. |
| **Inspection** — of drawings, documents, records | Reading a datasheet or a drawing and checking the number | `MANUFACTURER-SPECIFIED` (datasheet) or `LITERATURE-SUPPORTED` (standard/paper) | **Good.** Matches `knowledge/provenance.py`'s existing source-type mapping. |
| **Inspection** — visual examination of realized hardware | Someone looked at the built object | *(none)* | **No rung.** See §7. |
| **Demonstration** | It was shown to work, without detailed data gathering | *(none)* | **No rung.** See §7. |

**Direction of the ladders.** Ours is an *evidence-strength* ladder ("measured beats simulated beats calculated"). Theirs is a *method-selection* ladder — you pick the cheapest method that is sufficient, and NASA is explicit that analysis is used "when a prototype… is not available." Both agree test is strongest and analysis is the fallback; ours additionally ranks *unverified* rungs (`INFERRED`, `ASSUMED`, `UNKNOWN`) that theirs has no equivalent for, because in their world an unverified requirement simply is not signed off. That is a genuine advantage of our model and should not be traded away.

---

## 7. Mapping table — their concept, our equivalent, what adoption costs

| Their concept | Plain language | Do we have it? | What adopting it would take |
|---|---|---|---|
| **Threshold value** | The number below which it is not worth building | **Yes** — `target["value"]` + `AT_LEAST`/`AT_MOST` | Nothing. Rename in docs only if desired. |
| **Objective value** | The number above which more is not worth paying for | **No** | Add an optional `objective_value` next to `value` in `propose_target`. Validate that it lies on the permissive side of `value` for the given comparator (for `AT_LEAST`, `objective ≥ value`; for `AT_MOST`, `objective ≤ value`). `None` means "no stated objective," which is meaningful, not missing. Then #93's success score can score *satisfaction* against threshold and *margin* against objective instead of an arbitrary margin curve. |
| **"Threshold = Objective"** | This one has no soft zone, and I am telling you so deliberately | **No** | Falls out of the above if you allow `objective_value == value` and treat it as distinct from `None`. Cheap, and it is the single most valuable borrowing here: it makes "hard" an *asserted* fact rather than an inferred one. |
| **KPP / KSA / APA tiering** | How badly missing this hurts: fatal / escalate / note | **No** | Add a `tier` enum to the target. Note the doctrine: even a KPP miss routes to a human ("*may* result in a reevaluation"), so `tier` should drive *reporting prominence and whether a human is asked*, not silent deletion. This is #117's prune-vs-score axis, already tiered by people who have argued about it for thirty years. |
| **`shall` (binding) vs `should`/`may` (nonmandatory)** | Contract language vs advice | **Partially** — `TargetStatus.UNSCOREABLE` captures "no defensible number," which is where most `should` prose lands | Consider recording the modal verb found in the source prose as evidence for a proposed `tier`. Do **not** let the loop decide hardness from grammar alone — MIL-STD-961E's own practice is that almost everything is `shall`, so grammar under-discriminates. |
| **`must` is banned; use `shall`** | Pick one word and stick to it | N/A | Nothing to adopt, but worth knowing when reading customer prose: in a MIL-conforming document, `must` is *not* a requirement marker. `shall` is. |
| **"shall be not greater than" / "not less than"** | Upper limit / lower limit | **Yes** — `AT_MOST` / `AT_LEAST` | Nothing. Our comparators match the standard's own phrasing 1:1. |
| **Performance requirement** (what result) | What the thing must achieve | **Yes** — this is what a requirement target already is | Nothing. |
| **Detail requirement** (how to build it) | Materials, construction, "use MXene" | **No** — and #117 needs it | This is the honest home for "constrain the substrate class," "conductor must be X," "cure below 40 °C." Model it as a requirement with a *categorical* rather than numeric target (a set of allowed values, not a number and comparator). That is the one shape our current model genuinely cannot express — `value`+`unit`+`comparator` cannot say "conductor ∈ {MXene, silver, copper}". |
| **"A spec with both is a detail spec"** | One "how" clause taints the whole document | **No** | A report-level flag: if any confirmed requirement is a detail requirement, say so at the top of the design's summary. Cheap and honest. |
| **Constraint (JCIDS sense)** | Prose about treaties, logistics, external blockers | **No, and probably should not** | Not a scored object anywhere in the source practice. If we want it, it is free-text context on the design, not a target. |
| **Constraint (NASA sense)** | A condition dictated from outside — physics, an existing interface, a regulation, the state of technology | **Partially** — our provenance tag carries some of this | This is an *origin* label, not a type. #117's "host surface → bend radius → substrate class" chain is exactly NASA's "constraint dictated by external factors." Capture it as a `source`/`origin` field, not a second object. |
| **Rationale (required field)** | Why this number, and if you named a method, why | **No** — we store the original prose, which is close but not the same | Add `rationale`. NASA requires it specifically when a requirement "states a method of implementation." That directly serves #117's "visible, arguable, attributable." Low cost, high value. |
| **Verification method** (test / analysis / inspection / demonstration), chosen when the requirement is written | How we will prove it, decided up front | **No** — we tag provenance *after the fact*, on the result | Add a `verification_method` field on the target. Distinct from provenance: one is a *plan*, the other is *what happened*. Having both lets the loop say "you said this would be proven by test; the best evidence we have is `SIMULATED`" — which is a genuinely useful gap report and something the repo cannot currently express at all. |
| **Requirement/verification cross-reference** | Every requirement has exactly one matching proof entry | **No** | Falls out of the field above. MIL-STD-961E para 5.8.b: "Each requirement should be cross-referenced to the associated verification." |
| **"Only requirements that are … measurable, achievable, and verifiable shall be included"** | If you cannot check it, do not write it down as a requirement | **Yes** — `mark_unscoreable` is exactly this, with the reason recorded | Nothing. Our handling is arguably *better*: we keep the unscoreable prose with a stated reason rather than deleting it. |
| **TBD vs TBR** | "Nobody knows" vs "here's my best guess, flagged for resolution, with an owner and a date" | **Partially** — `PROPOSED` + `ASSUMED` is TBR | Consider borrowing the *owner and by-when* half. NASA: "It is better to use a best estimate for a value and mark it 'To Be Resolved' (TBR) with the rationale along with what should be done to eliminate the TBR, **who is responsible for its elimination, and by when**." #104's "the loop fills unknowns; it does not block on them" is the same policy; NASA adds accountability for closing them. |
| **Class / Grade / Type / Style** (MIL-R-7705B) | Different limits for different product classes, in one document | **No** | Probably not worth adopting. Our loop serves one requirement at a time; MIL general specifications serve a whole product family. Noted so nobody mistakes the multi-column Table 1 for a threshold/objective pair. |
| **Trade space** (the gap between threshold and objective) | The room engineers are allowed to move in | **No** | Emerges automatically once `objective_value` exists. Worth naming explicitly in #93's scoring, because "how much trade space did this requirement leave?" is exactly the diagnosis #117 asks for when the candidate set comes back empty. |

### What does **not** map — where our model is genuinely missing something

1. **A second value per requirement.** Everything else in this note is an add-on; this one is structural. Our target is a point plus optional symmetric `tolerance`. Theirs is an *asymmetric interval with named ends*, where one end is a pass/fail line and the other is a diminishing-returns line. A symmetric `tolerance` on an `EQUALS` target cannot express "5 dBi is the floor and 8 dBi is where we stop caring." **This is the single largest gap.**
2. **Categorical requirements.** `value` + `unit` + `comparator` is a numeric-only model. "Conductor shall be one of {…}", "substrate shall be flexible", "shall not use a sintering step" are detail requirements with no number. #117 explicitly needs these (substrate class, named substrate, conductor material). Nothing in the current model can hold one. Note that this is *not* a "constraints need their own object" argument — MIL-STD-961E files them under REQUIREMENTS too; it is a "requirements need non-numeric targets" argument.
3. **Plan-versus-outcome for evidence.** Their verification method is chosen when the requirement is written and then discharged. Our provenance tag only exists once a result exists. We have no way to record "this was supposed to be proven by test" and therefore no way to report the shortfall.
4. **No provenance rung for "demonstration."** NASA's demonstration is real-hardware observation *without detailed data gathering* — someone flexed the sample around a mandrel and it did not crack. That is stronger than `SIMULATED` (it is real hardware) but weaker than `MEASURED` (no numbers). Our ladder has no seat for it, so such evidence has to be either overstated as `MEASURED` or understated as `INFERRED`. Given that #104 says "the NOVA is in hand" and bench work is available, this gap will be hit in practice, not theoretically.
5. **No provenance rung for "inspection of a realized end product."** Same shape: visual/physical examination of the actual built article. Distinct from inspecting a *drawing or datasheet*, which does map (`MANUFACTURER-SPECIFIED`).
6. **"Verification by similarity of a heritage product."** One of their named methods spans three of our rungs and arguably belongs at none of them. If someone argues "MXene worked on the last conformal build, so it will work here," our ladder makes that either `LITERATURE-SUPPORTED` (too generous — it was not published) or `INFERRED` (accurate but tells you nothing about *what* it was inferred from). CONTEXT.md's evidence hierarchy has "internal engineering history" as a rank but the provenance enum has no tag for it.
7. **Rationale as a required field.** We keep the original prose, which answers "what did the customer say"; NASA's rationale answers "why is the number what it is, and if you told us how to build it, why." Those are different questions and only the first is currently answerable.

### What we already have that they don't

Worth recording so it does not get traded away in the name of conformance:

- **Rungs for unverified values.** `INFERRED` / `ASSUMED` / `UNKNOWN` have no counterpart. In their world a requirement is either verified or open; there is no vocabulary for "we filled this in ourselves and here is how confident we are." #104's "the loop fills unknowns; it does not block on them" needs exactly that vocabulary, and borrowing their model wholesale would remove it.
- **`UNSCOREABLE` with a recorded reason.** MIL-STD-961E's answer to unmeasurable prose is "do not include it." Ours is "record it, say why it is unscoreable, and never invent a number" — strictly more informative, and it keeps the customer's actual words in the design.
- **Provenance stays `ASSUMED` after human confirmation.** Defence practice conflates "somebody signed it" with "it is now true." `requirement_targets.py`'s decision to keep `provenance` and `target_status` as separate axes is the more honest model, and this research found nothing to argue against it.

---

## 8. Direct answers to #117's two questions

**Q1 — is a "constraint" a distinct kind of thing from a "requirement"?**

**No.** Three independent bodies of practice put constraints inside the requirement set:
- MIL-STD-961E files them under Section 3 REQUIREMENTS as "the requirements that constrain the design and implementation" (para A.3.16.2), verified in Section 4 like anything else.
- JCIDS's "Constraints" paragraph is prose context with no value, unit or comparator — it is not a structured object at all.
- NASA calls a constraint "a condition that is to be met," an *input* that gets converted into an ordinary `shall` requirement, and tracks its externally-dictated origin in the requirement's rationale.

**But** the useful distinction they *do* draw is **performance ("what result") versus detail ("how to build it")**, with an explicit policy that detail requirements are the exception and need justification (MIL-STD-961E 5.8.1/5.8.2; NASA's rationale rule). That is a better axis than constraint-vs-requirement for #117's prune-vs-score question, and it comes with a ready-made reporting rule: a requirement set containing any detail requirement is a design-constrained set, and should be labelled as one.

What our model actually needs is not a second object — it is **non-numeric targets** on the object we already have.

**Q2 — who decides whether a limit is hard or soft?**

**The person stating it, per requirement, by supplying a second number.** Not the quantity (nothing is inherently hard), and not the grammar alone (in a defence specification everything binding says `shall`, so the verb under-discriminates).

The mechanism is: **threshold** = hard floor, **objective** = desired level, and when there is no soft zone the writer must write **"Threshold = Objective"** explicitly. Hardness is asserted, not inferred. Layered on top of that is a three-level tier (KPP / KSA / APA) recording how much a miss costs — and even the top tier routes a failure to a human ("*may* result in a reevaluation"), never to a silent filter.

---

## Sources

Primary, retrieved and quoted directly:

- **MIL-STD-961E w/CHANGE 2**, 9 January 2014, *Department of Defense Standard Practice: Defense and Program-Unique Specifications Format and Content*. PDF bears "Source: https://assist.dla.mil". Retrieved via [acqnotes mirror](https://acqnotes.com/wp-content/uploads/2014/09/MIL-STD-961-Defense-and-Program-Unique-Specifications-Format-and-Content-9-Jan-2014.pdf). Paras 3.13, 3.35, 4.6.6, 5.8, 5.8.1, 5.8.2, 5.9.1, 5.11, A.3.16.2.
- **MIL-R-7705B**, 14 January 1975, *Military Specification: Radome, General Specification For*. Retrieved from [everyspec.com](https://everyspec.com/MIL-SPECS/MIL-SPECS-MIL-R/download.php?spec=MIL-R-7705B.024492.pdf). Sections 1, 3.3, 3.4, 4, Table 1. Scanned; OCR imperfect.
- **NASA/SP-2016-6105 Rev 2**, *NASA Systems Engineering Handbook*. Retrieved from [nasa.gov](https://www.nasa.gov/wp-content/uploads/2018/09/nasa_systems_engineering_handbook_0.pdf). §4.1.1.2.2, Table 4.2-2 and Rationale box (p. 59), Methods of Verification (p. 93), Glossary (p. 191), Appendix C (p. 197).
- **JCIDS Manual**, 31 July 2009, *Manual for the Operation of the Joint Capabilities Integration and Development System*. Retrieved via [acqnotes mirror](https://acqnotes.com/Attachments/JCIDS%20Manual%20-%2031%20July%202009.pdf). Enclosure B paras 1.a–1.f, Appendix A para 3.c.
- **JCIDS Manual**, 19 January 2012. Retrieved via [acqnotes mirror](https://acqnotes.com/Attachments/JCIDS%20Manual%20for%20the%20Operation%20of%20the%20JCIDS%20%2019%20Jan%202012.pdf). Enclosure B para 3.a(6)(d), Tables B-6/B-7/B-8, JUON/JEON format para (11).
- **SecDef/DepSecDef memorandum**, 20 August 2025, *Reforming the Joint Requirements Process to Accelerate Fielding of Warfighting Capabilities*. Retrieved from [newspacenexus.org mirror](https://www.newspacenexus.org/wp-content/uploads/2025/08/SecDef-Memo-20-Aug-2025.pdf) (`media.defense.gov` returned 403).

Secondary, used only where labelled:

- QRA Corp, *Automating the INCOSE Guide for Writing Requirements* — [PDF](https://edu.qracorp.com/hubfs/Automating%20the%20INCOSE%20Guide%20for%20Writing%20Requirements.pdf). Used only for the INCOSE rule/characteristic names; rule numbers not asserted.

Could not be retrieved (403 / paywall) — nothing in this note is quoted from them:

- INCOSE, *Guide to Writing Requirements* V4 (INCOSE-TP-2010-006-04, June 2023) — `incose.org` returned 403.
- ISO/IEC/IEEE 29148:2018 — paywalled; `iso.org` returned 403.
- JCIDS Manual, 30 August 2021 (final edition) — `dau.edu` / `waru.edu` returned 403.
- DoDI 5000.85, *Major Capability Acquisition* — `esd.whs.mil` returned 403. The claim that the Acquisition Program Baseline carries threshold and objective values for cost, schedule and performance is therefore **unverified against the instruction itself**.
- Congressional Research Service IF12817, *Defense Primer: JCIDS* — `congress.gov` returned 403.

**Export control:** nothing controlled was sought or obtained. All sources above are openly published. Programme-specific System Requirements Documents, Technical Requirements Documents, and populated KPP tables for real radar/EW/radome programmes are distribution-limited or ITAR-controlled (22 CFR Part 121 Category XI covers military electronics including radomes and antennas designed for military application); **no claim is made about their contents.**
