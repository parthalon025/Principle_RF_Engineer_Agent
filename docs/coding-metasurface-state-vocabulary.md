# How the coding-metasurface literature names and counts a multi-state unit cell

**Serves:** the open schema question on the **Element/Coding-Alphabet library** (`CONTEXT.md`, "Element/Coding-Alphabet library" and "Process record"), whose key is `(element family, symbol, band, incidence-angle range, process)` with the *response* as the stored value. A latching cell — one printed part, two retained material states, two different reflection responses — produces two responses under one identical key. This document reports what the field's own convention is, so the repo can decide from evidence rather than invention.

**Scope check.** Research only. This settles a vocabulary question and reports a convention; it does not change the schema, and it does not re-open ADR-0040's own decisions (what a symbol carries, characterise-continuous/admit-quantised, the super-cell sizing rule). Those are treated as settled and are not re-litigated here.

---

## Direct answer, before the detail

**One physical cell with a state axis — and the field is explicit about this, but it uses two different words for the two things, and the repo's schema currently conflates them.**

In Cui's founding paper the physical object and the coding letter have *different names*:

- the physical thing is a **"particle"**, a **"unit cell"**, or (later literature) a **"meta-atom"**;
- the coding letter — `"0"`, `"1"`, `"00"`…`"11"` — is called an **"element"**.

A switchable cell is therefore **one particle that realises several elements**. Cui says this in one sentence, twice, without hedging:

> "we propose a unique metamaterial particle which has either "0" or "1" response controlled by a biased diode."

> "(a) The structure of metamaterial particle, which **behaves as "0" and "1" elements** when the biased diode is "OFF" and "ON"."

*In plain terms: the letter is what the cell is currently saying, not what the cell is. One switchable part can say two letters. The field's word "element" means the letter, not the part.*

**For the repo's schema, this maps cleanly onto "one entry with a state axis":** the library key (`element family, symbol, band, incidence angle, process`) identifies a *particle* — a printed part with a Process record. The stored *response* belongs to a `(particle, state)` pair. The collision the schema has no slot for is real and the field has already met it; the field's answer is a state index on the response, not a second physical entry.

**One important caveat that cuts the other way, stated plainly:** the field's own usage of the word *"element"* is not internally consistent, and the split above is a reading of the usage rather than a definition anyone published. In the *static* half of the same paper, "element" and "unit cell" are used interchangeably for two genuinely different printed patches (`w`=4.8 mm and `w`=3.75 mm). There, one element *is* one part, because a static cell has exactly one state and the two collapse. Nobody in this literature ever had to maintain a persistent, cross-run, process-keyed library, so **nobody has published a schema for this**. The field supplies a convention for *naming and counting*; it does not supply a database design. That part the repo must still choose.

---

## 1. Is the cell one thing that has states, or is each state a distinct element?

### The anchor: Cui, Qi, Wan, Zhao & Cheng (2014)

**Fetched in full** (arXiv:1407.8442, converted and filed at `knowledge/corpus/arxiv_1407_8442_coding_digital_programmable_metamaterials.md`). Note the title differs between versions: the arXiv preprint is *"Coding Metamaterials, Digital Metamaterials and **Programming** Metamaterials"*; the *Light: Science & Applications* **3**, e218 (2014) version of record reads *"…and **programmable** metamaterials"*, which is how ADR-0040 already cites it. The Nature-hosted version of record is behind an IdP redirect and **was not fetched**; the arXiv full text and the LSA abstract were both read directly and are substantively identical in every sentence quoted here. `LITERATURE-SUPPORTED`, full text.

**The static coding case — each letter is its own printed part.** Here "two kinds of unit cells" and "'0' and '1' elements" are used as synonyms, because each letter is a different patch:

> "we present "coding metamaterials" that are composed of only two kinds of unit cells with 0 and π phase responses, which we name as "0" and "1" elements."

> "Hence we use the patch particle with w=4.8mm as "0" element, and that with w=3.75 mm as "1" element."

> "In 2-bit coding, four kinds of unit cells with phase responses 0, π/2, π, and 3π/2 are required to mimic "00", "01", "10" and "11" elements."

Two patch widths, two elements. Four patch widths, four elements. **In the static case, one element per part is the field's counting — but only because each part has exactly one state.** This is not evidence for the "two entries" option; it is the degenerate case where the two options give the same answer.

**The switchable case — one part, several letters.** The moment a diode appears, the vocabulary separates, and it separates consistently:

> "Secondly, we propose a unique metamaterial particle which has either "0" or "1" response controlled by a biased diode. Based on the particle, we present "digital metamaterials" with unit cells having either "0" or "1" state."

> "we propose a **unique** metamaterial particle … numerical results demonstrate the metamaterial particle to behave as "1" element with the diode on and "0" with the diode off."

> "We further propose a **unique** planar metamaterial particle in the subwavelength scale, which can realize **either "0" or "1" element** controlled by a biased diode."

> "The digital metasurface contains **30×30 identical unit cells**, and each includes a biased diode."

That last quote is the sharpest one for the repo's purposes. The array is **physically uniform** — thirty-by-thirty of one part, one geometry, one process — and the coding pattern lives entirely in the bias state. Under a "one entry per state" schema, a physically uniform array would be described by two library entries that differ in no manufacturable respect. Under a state-axis schema, it is one entry with two responses. The field's own description matches the second.

The word "unique" is doing deliberate work in Cui's prose: it is contrasted against the static case's *two kinds* of cell. The paper's whole claimed advance in its second half is collapsing two parts into one part with two states.

### Corroboration across the switchable literature

| Source | What it says | Fetch status |
|---|---|---|
| Li, Cui et al., *Electromagnetic reprogrammable coding-metasurface holograms*, **Nat. Commun. 8, 197 (2017)**, PMC5543116 | "the **state of each unit cell** of the coding metasurface can be switched between '1' and '0'"; "each unit cell can be independently programmed to realize the required '0' or '1' state"; "Each unit cell of the dynamic metasurface **assumes one of the two switchable states**: '0' and '1'" | Full text fetched via PMC; quotes returned verbatim from the fetched page |
| *Wideband 1-bit reconfigurable transmission metasurface unit cell … in Ka-band*, PMC10654510 | "The PIN diode exhibits **two distinct operating states**, denoted as states 1 and 2"; treats the cell "as a single reconfigurable element rather than two separate elements" | Full text fetched via PMC |
| Self-biased tri-state power-multiplexed digital metasurface, arXiv:1910.07353 (**already in this repo's corpus**) | "the two groups of meta-atoms possess the same **digital state** (0 or 1)"; "does not switch the **coding status** of the I-shape meta-atom"; "the self-biased **tri-state** (EM mirror, absorber, and diffuser) digital metasurface" | Read from the repo's own ingested copy, `knowledge/corpus/arxiv_1910_07353_self_biased_power_multiplexed_metasurface.md` |

The tri-state paper is worth singling out because it is the case that breaks any residual temptation toward one-entry-per-state. Its meta-atom has **three** operational states (mirror / absorber / diffuser), selected by incident power with no bias line at all. The paper calls it *one* meta-atom throughout and indexes its behaviour by state. Nobody writes "three meta-atoms."

**Confidence: `LITERATURE-SUPPORTED`, high.** Four independent sources, three read in full text, all describing a switchable cell as one cell with states. No source found that treats the states of a single switchable cell as separate physical elements.

---

## 2. What the field calls the state

**Dominant term: "state", almost always qualified — "coding state", "digital state", or bare "state".** There is no serious competitor for the *concept*; the disagreement is only in the qualifier, and it is mild.

- **"digital state"** is the term Cui's own lineage settled on and is the most defensible single choice. The 2014 paper uses bare `"0" or "1" state`; later work in the same line uses "digital state" explicitly (the repo's own corpus copy of arXiv:1910.07353: *"possess the same digital state (0 or 1)"*). A survey-level restatement found in search results puts it as: *"For a 1-bit metasurface element, the different electromagnetic field responses with opposite phases are denoted by digital states '0' and '1'."* `LITERATURE-SUPPORTED at search-synthesis confidence` for the claim that "digital state" *dominates recent work* — the individual quotes above are full-text, but the ranking of the two qualifiers is a synthesis, not a counted survey.
- **"coding state"** is used interchangeably and is common in the reconfigurable-metasurface/RIS engineering literature. arXiv:1910.07353 also uses **"coding status"** for the same idea.
- **"bit"** names the *control word*, not the cell's electromagnetic condition — "1-bit coding" means the alphabet has two letters, and a "bit of the control words" is a line on the FPGA (Cui: "Every five adjacent columns of unit cells share a control voltage, which corresponds to a single **bit** of the control words"). **"Bit" is a property of the alphabet and the control bus, not a name for a cell's state**, and using it as one would be a genuine misuse.
- **"phase state"** appears but is narrower and should be avoided as a schema term: a switchable cell's two states can differ in amplitude, in absorption, or in polarisation behaviour, not only in phase — the tri-state paper's mirror/absorber/diffuser triple is the counterexample.
- **"element"** — per §1 — names *the letter*, not the state and not the part, in careful usage. This is the term most likely to cause a collision with the repo's own existing vocabulary, where "element family" already means something closer to *part family*.

**Recommendation to whoever writes the schema, offered as a naming preference and not as a finding:** use **`state`** (or `digital_state`) for the axis, and keep it distinct from `symbol`. In Cui's terms the *symbol* is the letter the cell is currently saying and the *state* is the physical configuration that makes it say that; for a static letter the two are the same thing, which is why the distinction has been invisible here so far. A latching cell is precisely the case that pulls them apart.

---

## 3. Coding → digital → programmable: how Cui distinguishes the three, and where a switchable cell sits

**Read from the full arXiv text.** The progression is built in two steps, and the paper says so in its own first paragraph: *"we propose 'digital metamaterials' in two steps."*

| Term | What makes it that | Cui's own words |
|---|---|---|
| **Coding** metamaterial | A surface built from a **finite quantised alphabet** of phase responses, arranged in a designed **sequence**. Says nothing about whether the cells can change. | "composed of only two kinds of unit cells with 0 and π phase responses, which we name as '0' and '1' elements. By coding '0' and '1' elements with controlled sequences (i.e., 1-bit coding), we can manipulate electromagnetic (EM) waves" |
| **Digital** metamaterial | The cells are **switchable in place**: one particle carries both letters and is commanded into one of them. This is the step that introduces the state. | "we propose a unique metamaterial particle which has either '0' or '1' response controlled by a biased diode. Based on the particle, we present 'digital metamaterials' with unit cells having either '0' or '1' state." |
| **Programmable** (arXiv: "programming") metamaterial | A **controller** (FPGA) rewrites the sequence at run time, so **one fabricated surface has many functions**. | "By programming different coding sequences, a single digital metamaterial has distinct abilities in manipulating EM waves, realizing the 'programming metamaterials'." |

**Where a switchable-state cell sits: it is exactly the boundary between "coding" and "digital".** That is the paper's whole architecture. A coding metasurface can be entirely static — Cui's own 1-bit and 2-bit RCS-reduction demonstrations are etched copper on F4B with no active part anywhere, and they are fully "coding". What earns the word "digital" is the cell acquiring a state.

*In plain terms: "coding" means you built the surface out of a small fixed set of letters. "Digital" means each tile can be told which letter to be. "Programmable" means something on the board retells them, live.*

**Consequence the repo should notice.** A **latching** cell (non-volatile, retains its state with no standing bias) is **digital but not programmable** in this taxonomy — it has a state, but there is no FPGA rewriting it continuously. The same structure appears in the non-volatile phase-change literature (GST amorphous/crystalline), which is described as *"non-volatile, amorphous-crystalline transitions"* giving *"binary-level switching"*, with *"multi-state switching operation"* held out as the extension — `LITERATURE-SUPPORTED at search-synthesis confidence`; abstracts and search results only, no primary phase-change paper was fetched in this pass. A mechanically bistable analogue exists too (origami "mechanical bits", arXiv:2601.19632 — **abstract only, full text not fetched**), which speaks of *"bistable states"* and *"binary geometric states"* mapped to *"1-bit EM coding phases"* — again, states of a cell, not separate cells.

This matters for the repo because **ADR-0040 chose the quantised alphabet for admission-by-printability**, and a latching cell is the one device where one print buys two admitted letters. Nothing in Cui's framing obstructs that; it is the digital half of his own paper.

---

## 4. Is the library/lookup table indexed per element, or per element per state?

**Per (physical cell, state) — and the field shows this directly in its figure captions rather than stating it as a rule.** The honest form of the answer is: *the field does not maintain libraries at all in the sense this repo means, but where it tabulates, it tabulates per state.*

The cleanest evidence is a pair of figure captions in the same paper, describing the same kind of plot for the static and the switchable case:

> **Figure 4.** "The 2-bit coding metasurface elements and their phase responses. (a) The '00', '01', '10', and '11' elements (from the left to the right) realized by the square metallic patches with different sizes. (b) **The phase responses of '00', '01', '10', and '11' elements**."

> **Figure 6.** "The metamaterial particle to realize digital metasurface and the corresponding phase responses. … (b) **The corresponding phase responses of the metamaterial particle as the biased diode is 'OFF' and 'ON'** in a range of frequencies."

Figure 4 is **four parts, four curves, indexed by element**. Figure 6 is **one particle, two curves, indexed by diode state**. That is precisely the per-element-per-state tabulation, drawn by the field, in the paper that founded the field. The switchable case is never redrawn as "two particles"; it is one particle whose response curve is a function of state.

The same shape recurs in every switchable source checked:

- PMC10654510: figure caption *"Simulation results of co-polarization transmission coefficient and phase of **two states**"* — one cell, response reported per state.
- Li/Cui 2017 (PMC5543116) reports *"the transmission phase difference between the '1' and '0' **states** … is ~180°"* and *"The reflection efficiency of the **meta-atom** when the biased diode is at the state of 'OFF' and 'ON'"* — the subject of the sentence is the single meta-atom; state is a qualifier on the measurement. Notably, that paper **does not publish a side-by-side amplitude/phase table** of the two states at all; it reports the difference between them.
- arXiv:1910.07353 (repo corpus): *"The overall EM functionality of the designed nonlinear metasurface is determined by the reflection phase/amplitude spectra of the occupying **digital elements** and their spatial distribution"* — the response belongs to the digital element (the letter-in-a-state), and the part is the meta-atom.

**What Cui's Table I is, and is not.** The paper's only actual table (Table I, "The optimized codes for different lattice numbers N") tabulates **code sequences against RCS reduction** — a design result per array size, not an element library. **There is no element-response lookup table in this paper.** Anyone citing Cui for a library schema is citing something that is not there.

**The honest limit of this answer.** The field's "library" is a published figure in a paper, regenerated per design, not a persistent accumulating store. What §4 establishes is the *indexing convention of the response* — response is a function of `(cell, state)` — and that is genuinely the question asked. It does not establish what a durable, process-keyed, cross-run store should look like, because no source surveyed maintains one. **The field has a naming and tabulation convention; it has no schema convention.** `LITERATURE-SUPPORTED` for the indexing, with the explicit caveat that the extension to a persistent database is this repo's own step.

---

## 5. What this means for the Element/Coding-Alphabet library, stated as evidence not as a decision

Not a decision — the ADR that settles this is someone else's to write. What the evidence supports and what it leaves open:

**Supported by the field's usage:**

- A latching cell is **one library entry with a state axis**, not two entries. The physical part — the thing the Process record describes — is one thing, printed once, on one machine, in one ink, at one cure. Two entries would assert two parts where one was made, and would make a physically uniform 30×30 array (Cui's own) describable only as a mixture of two library entries that differ in nothing manufacturable.
- The response is the thing that carries the state index. `(element family, symbol, band, incidence-angle range, process) → response` becomes `… → {state: response}`, with a single-state map for every static letter already in scope. A static letter is the one-state degenerate case, which is why the schema has survived without the axis so far.
- The **Process record** argument points the same way independently of the literature. `CONTEXT.md` records #132's rule that "the same outline printed in carbon and in MXene is two letters, not one letter under two conditions" — the discriminator there is *how it was made*. A latching cell's two states are the same outline, same ink, same machine, same cure: **one Process record, therefore one made thing.** Splitting it into two entries would put two entries under one Process record for the first time, and would make "what did we print" un-countable from the library. The state is a `use` condition, not a `make` condition — which is the same **Validity box vs Process record** line `CONTEXT.md` already draws and explicitly forbids merging.

**Left open, and not answered by any source found:**

- **Whether `symbol` should absorb the state or stay orthogonal to it.** Cui's vocabulary distinguishes the letter (element) from the configuration that produces it (state), but he never had to key a database on both. If a latching cell's two states are two symbols, the state axis and the symbol axis are the same axis and the key needs nothing new; if a symbol is a target response and a state is a way of hitting it, they are different axes. **No source settles this**, and the repo must choose.
- **Whether a state is separately admissible.** ADR-0027's rule is that a letter enters by being printed and measured. A latching cell printed once but measured in only one of its two states is a real intermediate case with no precedent in the sources surveyed — the field prints and measures both states as a matter of course because a 1-bit cell is useless otherwise, so nobody has had to name the half-characterised case. The repo will meet it the first time a bench run is interrupted.
- **Whether state-to-state switching repeatability is a per-entry property, an alphabet property, or neither.** ADR-0040 put `Δφ_max` on the alphabet's record rather than per-symbol, on the reasoning that it is a property of the alphabet at a pitch. A latching cell's state-retention and switching endurance is structurally similar — a property of the *cell*, measured across states — and by the same reasoning might belong on the entry rather than on either state. **Not addressed by any source here**; flagged as the next question, not answered.
- **Multi-state beyond binary.** The tri-state paper shows the state axis is not inherently binary, so a schema that hard-codes two states will be wrong at the first three-state device. The evidence supports a general state axis, not a boolean flag.

---

## Sources

**Fetched and read in full text:**

- Cui, T. J., Qi, M. Q., Wan, X., Zhao, J. & Cheng, Q., *Coding metamaterials, digital metamaterials and programmable metamaterials*, **Light: Science & Applications 3, e218 (2014)**, DOI [10.1038/lsa.2014.99](https://doi.org/10.1038/lsa.2014.99); preprint [arXiv:1407.8442](https://arxiv.org/abs/1407.8442) (preprint title uses "Programming"). **Full text converted and filed at `knowledge/corpus/arxiv_1407_8442_coding_digital_programmable_metamaterials.md`.** Every Cui quote in this document is verbatim from that converted text; the LSA abstract was separately fetched and matches. *Conversion caveat: arXiv supplied no LaTeX source, so this is the naive single-column PDF fallback (pdfplumber). Prose and figure captions — everything quoted here — came through cleanly; the equations and the symbol subscripts did not, and Table I's column alignment is mangled. Do not quote equations from that file without checking the PDF.*
- Li, L., Cui, T. J. et al., *Electromagnetic reprogrammable coding-metasurface holograms*, **Nature Communications 8, 197 (2017)**, [PMC5543116](https://pmc.ncbi.nlm.nih.gov/articles/PMC5543116/) — fetched via PMC; unit-cell/state quotes returned verbatim. Reported here as returned by the fetch; individual sentences were not re-verified against the publisher PDF.
- *Wideband 1-bit reconfigurable transmission metasurface unit cell design in Ka-band with polarization hold and conversion*, [PMC10654510](https://pmc.ncbi.nlm.nih.gov/articles/PMC10654510/) — fetched via PMC. Same caveat.

**Read from this repo's own corpus (already ingested, not re-fetched):**

- `knowledge/corpus/arxiv_1910_07353_self_biased_power_multiplexed_metasurface.md` — *Self-biased Tri-state Power-Multiplexed Digital Metasurface Operating at Microwave Frequencies*, [arXiv:1910.07353](https://arxiv.org/abs/1910.07353). Quotes read directly from the ingested Markdown. The single most useful multi-state (non-binary) data point found.

**Abstract-only or search-synthesis, flagged as such and not load-bearing for the main finding:**

- *Self-locking non-volatile coding metasurfaces via origami-based mechanical bits*, [arXiv:2601.19632](https://arxiv.org/abs/2601.19632) — **abstract only**, full text not fetched. Used only for the observation that a mechanically bistable cell is described as one meta-atom with "bistable states" / "binary geometric states". A directly relevant paper for the repo's latching case and **worth a full ingest as a follow-up** — it was not done here because this task was scoped to the vocabulary question.
- Non-volatile phase-change (GST) metasurface literature — `LITERATURE-SUPPORTED at search-synthesis confidence` only. No primary source fetched. Used only for "non-volatile binary switching exists and multi-state is the stated extension".
- The claim that **"digital state" dominates "coding state" in recent work** is a search-level synthesis, not a counted survey. The individual quotes supporting each term are full-text; the ranking between them is not.

**Explicitly not obtained:**

- The *Light: Science & Applications* version of record at nature.com — a 303 redirect to an identity provider blocked the fetch. The arXiv full text stood in for it; the two agree on every quoted sentence against the fetched LSA abstract, but a line-by-line diff of preprint against version of record **was not performed**, and the title differs between them.
- No source anywhere in this pass publishes a **schema** for a persistent element library with a state axis. That absence is the real finding of §4, and it means the repo is choosing rather than inheriting — which is exactly the case where the choice belongs in an ADR with its reasoning attached.
