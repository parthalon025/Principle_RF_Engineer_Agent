# Frequency-Selective Mode Imprinting in a Multistable Shell — Prior Art, and the Dispersion Anchor

**Research date:** 2026-09-13
**Trigger:** an unsolicited proposal for an **acoustic/elastic** device — a spherical shell of graded
mechanical resonators in which a drive frequency selects a standing-wave (spherical-harmonic) mode
shape, and bistable cells **latch** that mode so the pattern persists after the drive is switched
off. *"Cymatics, but the sand stays put, in 3D."*
**Scope:** three questions, in the order they gate the decision — (1) does the prior art for
frequency-selective mode imprinting exist; (2) is the presumed dispersion anchor (Liu *et al.* 2000)
real and does it say what it is claimed to say; (3) what cell-to-cell spread in switching threshold
and what hold time are actually **reported** for multistable lattices.
**Standing:** a scouting note. No ticket, no ADR, no code change. Every citation previously attached
to this idea was named from memory and never fetched; this document exists to replace those with
fetched primary sources or to say plainly that none was found.

> **The acoustic framing was superseded while this research was in progress, and this document is
> scoped to what was established before that pivot — it is not a complete survey.** The idea has
> been redirected to the electromagnetic domain: a metasurface that latches its own configuration
> and holds it with no sustained bias, rather than a mechanical shell latching a vibration mode.
> That EM line is being covered separately. This file is kept as **background explaining why the
> pivot happened**, plus the two findings that transfer across the domain change intact:
>
> - **§1 — has frequency-selective mode imprinting been demonstrated anywhere?** The conceptual
>   question is identical in EM, so the answer transfers whether it is a hit or a clean miss.
> - **§3 — cell-to-cell switching-threshold spread in multistable lattices.** Any latching surface
>   faces this, including one built from RF MEMS or phase-change cells.
>
> **§2 (the Liu *et al.* locally-resonant acoustic anchor) is now the least important part of this
> document.** It is kept because the verification was completed and it contains a real citation
> correction, not because it still bears on a live decision. §4.4 records what carries into EM.
> Nothing here was expanded after the pivot; the gaps listed in §1.6 and §6 stayed gaps.

**This document does not argue that the acoustic idea belonged in this repo.** That question is now
moot. `docs/elastodynamic-metamaterials-dataset-relevance.md` is the repo's standing precedent for
how the elastic/electromagnetic boundary has been drawn before (§5 below), kept for the record.

---

## Bottom line up front

**Q1 — prior art: PARTIALLY, and the two halves are split cleanly between two literatures that have
not been joined.**

- **The "latch a pattern remotely, and it stays" half is established.** Watkins, Bordiga, Mu,
  Tournat & Bertoldi write arbitrary bit patterns into a bistable metamaterial from a *single
  boundary excitation*, no local addressing, and the bits persist. Fetched, full text read
  ([arXiv:2508.20321](https://arxiv.org/abs/2508.20321)).
- **The "a drive frequency selects a spatial pattern, and the pattern is then made permanent" half
  is also established** — in acoustic holography/assembly, where a shaped ultrasound field arranges
  matter and the arrangement is fixed by **curing the surrounding medium**, including in 3D
  (Melde *et al.*, Nature 2016; Adv. Mater. 2018; Sci. Adv. 2023).
- **The specific combination the proposal names — a standing-wave *mode shape* of a structure,
  selected by drive frequency, latched by the structure's own multistable cells — was not found in
  any retrieved source.** That is a negative result from a directed search, not a proof of absence
  (§1.6 says exactly how hard I looked and where I did not look).

The near misses are what matter, and they split the idea along an unexpected line: **what is
missing is not the latching and not the frequency selection — it is the claim that the *selector*
is a spatial mode.** In every retrieved system the selector is either the **input amplitude/waveform
at one boundary** (Watkins *et al.*; Bertoldi group), a **hand press on the cell you want**
(Li *et al.* 2026; Sirote-Katz *et al.* 2024), or a **hologram that shapes the field in space**
(Melde *et al.*) — never "excite eigenmode ℓ and the ℓ-th harmonic pattern freezes in."

**Q2 — the dispersion anchor: the paper is real, I read its full text, and it does *not* say what
the idea attributes to it.** Liu, Zhang, Mao, Zhu, Yang, Chan & Sheng, *"Locally Resonant Sonic
Materials,"* **Science 289, 1734–1736 (2000)** — verified, full text fetched from the senior
author's own institutional copy. It reports a **measured sub-wavelength band gap** (lattice constant
300× smaller than the wavelength) and that is solid. But the phrase **"negative effective mass
density" does not occur in the paper**; the paper says **"effective negative elastic constants,"**
and Ping Sheng's own HKUST page states that in that publication *"the effect was wrongly attributed
to negative elastic constant, but this has been corrected in the subsequent publications."*
**Anyone citing Liu 2000 for negative effective mass density is citing the wrong paper.** The right
one is Liu, Chan & Sheng, *Phys. Rev. B* **71**, 014103 (2005). Details and the measured/modelled
split in §2.

**Q3 — the load-bearing assumption: nobody reports it.** After a directed search I found **no
published distribution of cell-to-cell switching thresholds** for a multistable mechanical
metamaterial — no percentage spread, no measured force histogram across an array, no hold-time
data. What exists instead is worse for the proposal than a bad number would be:

- The demonstrated systems are **tiny**: Watkins *et al.* — *"we focus on a metamaterial with
  N = 3 unit cells."* Ding & van Hecke — three hysterons. The proposal needs thousands on a sphere.
- Where a spread **is** reported it is of the *geometric/stiffness parameters*, not the threshold:
  **k_truss = 1428 ± 72 N/m** (≈ **5.0%**), **l₀ = 28.8 ± 1 mm** (≈ 3.5%), **θ₀ = 11.55 ± 0.14°**
  (≈ 1.2%), attributed to *"minute fabrication imperfections."*
- Threshold spread is treated in the literature as a **design variable, deliberately made large**
  (van Hecke's three hysterons are given pusher heights 0.23, 0.28, 0.33 precisely so they snap in a
  known order) — which is the opposite of the proposal's need for thousands of cells to share one
  threshold.
- **Hold time has a documented physical failure mode nobody has quantified for lattices:**
  *pseudo-bistability*, in which a viscoelastic snapped-through structure *"undergoes a slow
  creeping motion before rapidly accelerating"* back (Gomez, Moulton & Vella, JMPS 2019).

*In plain terms: the machinery the idea depends on has only ever been shown working on three cells
at a time, the one number that decides whether it scales to thousands has never been published, and
the polymers such cells are printed from are known to un-snap themselves eventually — with nobody
reporting how long "eventually" is.*

---

## 1. Q1 — prior art for frequency-selective mode imprinting

### 1.0 What would count as a hit

Stated precisely so the negative result means something. A direct hit needs **all four**:

| # | Requirement | Plain reading |
|---|---|---|
| A | A **spatially extended** multistable lattice (many cells, not one gate) | lots of little switches, not one switch |
| B | Excitation is a **global drive at a chosen frequency**, not per-cell addressing | you play one note at the whole thing |
| C | The **spatial pattern that gets latched is the standing-wave mode shape** at that frequency | the note picks the picture |
| D | The pattern **persists after the drive stops** | the sand stays put |

Every retrieved source below satisfies some subset. None satisfies all four.

### 1.1 The closest thing: remote writing by a boundary wave (A, B-ish, D — not C)

**Watkins, Bordiga, Mu, Tournat & Bertoldi, *"Arbitrary mechanical memory encoding via nonlinear
waves in bistable metamaterials,"* [arXiv:2508.20321](https://arxiv.org/abs/2508.20321), submitted
27 Aug 2025.** Full text fetched and read via the arXiv HTML rendering. Abstract, verbatim:

> "Mechanical metamaterials composed of bistable elements have recently emerged as promising
> platforms for mechanical memory. Traditional approaches to writing information in these systems
> typically rely on localized actuation or predefined coupling schemes, which are often
> labor-intensive or lack adaptability. In this work, we introduce a one-dimensional metamaterial
> consisting of mass-in-mass bistable units that are statically decoupled yet dynamically
> switchable, allowing arbitrary mechanical information to be encoded through nonlinear waves
> applied at the boundary of the system. Through a combination of experiments and simulations, we
> demonstrate that tailored input signals can selectively trigger state transitions deep within the
> structure, enabling remote and programmable bit writing."

What the drive actually is, verbatim from the text: a *"bipolar pulse (generated by providing a
single period of a sinusoidal electrical signal), characterized by an amplitude A and frequency f."*
So **frequency is one of the two knobs** — this is the single closest retrieved result to the
proposal's mechanism. The switching criterion is inertial:

> "when the accelerations of the outer masses are sufficiently large, the resulting inertial forces
> on the inner masses can overcome their energy barriers, causing them to switch states"

And the state persists: *"after the wave dies out, the metamaterial settles into the new state."*

**Why this is a near miss and not a hit — requirement C.** The selected object is a *bit string*,
chosen from an (A, f) phase map, in a **1D chain of N = 3 cells** (verbatim: *"we focus on a
metamaterial with N = 3 unit cells"*). Nothing in the paper frames the written pattern as a
**mode shape**, and with three cells there is no meaningful mode shape to select. The frequency
enters as *one coordinate of a lookup table over outcomes*, not as *the thing that picks the spatial
harmonic*.

*Plain-language reading: they can stand at one end of a three-link chain, give it one carefully
chosen shove, and set all three switches to whatever combination they want, and the combination
sticks. That is genuinely "write it in remotely, and it stays." It is not "play a note and the
matching pattern appears," because with three cells there is no pattern — only eight possible
combinations, read off a chart.*

**Publication status — flagged as unverified.** A search result presents this work as *Physical
Review Letters*, DOI `10.1103/pkk5-dykb`. The APS page returned **HTTP 403** to this session and the
arXiv record carries **no `journal-ref` field**. So the journal version is `UNVERIFIED`; cite the
arXiv preprint, which I did read.

### 1.2 The same group's follow-up confirms the selector is *amplitude*, not mode

**Watkins, Bordiga, Tournat & Bertoldi, *"Wave-based reading of mechanical memory in multistable
mass-in-mass metamaterials,"* [arXiv:2609.07889](https://arxiv.org/abs/2609.07889), submitted
7 Sep 2026.** Abstract fetched and read; the technical body read via the arXiv HTML rendering.
Verbatim from the abstract:

> "While it has been shown that information can be written into such metamaterials by applying
> global inputs, existing readout strategies rely predominantly on visual inspection. Here, we
> experimentally demonstrate a mass-in-mass bistable metamaterial with state-dependent stiffness
> that enables both writing and reading of mechanical information using only boundary-applied
> dynamic excitations. We further show that such metamaterial architecture functions as both a
> mechanical **sensor of input amplitude** and a reconfigurable wave-control device."

(Emphasis mine.) Writing is by *"large amplitude inputs"* crossing energy barriers; reading is by
*"nominally identical low-amplitude Ricker wavelet input signals"* whose echo differs by
configuration. **This paper states in its own abstract that the quantity the material resolves is
amplitude.** That is the single strongest piece of evidence that the frequency-picks-the-mode step
is genuinely not in this literature — the group closest to the idea built the amplitude version.

### 1.3 Frequency *does* trigger a latch — but on one element, not a pattern (B, D — not A, C)

**Bilal, Foehr & Daraio, *"Bistable metamaterial for switching and cascading elastic vibrations,"*
PNAS 114(18), 4603–4606 (2017).** Full text fetched from the
[author-hosted PDF at Caltech](https://www.daraio.caltech.edu/publications/PNAS-2017-Bilal-4603-6.pdf)
and text-extracted. Verbatim:

> "We couple the permanent magnets to a driven, magnetic cantilever (herein referred to as the gate
> …), designed to resonate at a frequency f₀ = 70 Hz. When the gate is excited by a relatively small
> mechanical signal, the resonance of the cantilever shifts the array of magnets … and tunes the
> transmission spectrum of the metamaterial … The energy potential of the gating system is bistable"

**This is a genuine instance of "drive at a resonance → a bistable element latches."** It is the
existence proof that requirement B + D is physically ordinary. But the latch is a **single gate
cantilever**, and what it controls is transmission, not a spatial pattern. Requirements A and C are
absent.

### 1.4 Frequency selects a pattern and the pattern is made permanent — but by curing, not latching (B, C, D — not A)

This is the other half of the idea, and it is thoroughly established, including in 3D.

- **Melde, Mark, Qiu & Fischer, *"Holograms for acoustics,"* Nature 537, 518–522 (2016)** — a
  3D-printed phase plate shapes an ultrasound field into an arbitrary 2D pressure image.
  *Record verified via the [Nature article page](https://www.nature.com/articles/nature19755) and
  multiple independent institutional records; abstract/record only, full text not fetched.*
- **Melde, Choi, Wu, Palagi, Qiu & Fischer, *"Acoustic Fabrication via the Assembly and Fusion of
  Particles,"* Adv. Mater. 30, 1704507 (2018)** — particles assemble on the high-pressure lines of
  the field and are then *fixed in a UV-triggered reaction*. *Record verified via the
  [Wiley article page](https://onlinelibrary.wiley.com/doi/full/10.1002/adma.201704507),
  [PubMed 29205522](https://pubmed.ncbi.nlm.nih.gov/29205522/) and the MPI-IS publication record;
  abstract/record only.*
- **Melde, Kremer, Shi, Seneca, Frey, Platzman, Degel, Schmitt, Schölkopf & Fischer, *"Compact
  holographic sound fields enable rapid one-step assembly of matter in 3D,"* Science Advances 9,
  eadf6182 (2023)** — multiple holographic fields assemble particles, hydrogel beads and cells into
  **3D** shapes, *"fixed via gelation of the surrounding medium."* *Science.org returned HTTP 403;
  record verified via [NASA ADS 2023SciA....9F6182M](https://ui.adsabs.harvard.edu/abs/2023SciA....9F6182M/abstract)
  and the MPI-IS record; abstract/record only, full text not fetched.*

And the frequency-sets-the-pattern relationship is stated explicitly in an open-access review I did
fetch (Gerlt *et al.* / *"The waves that make the pattern,"* [PMC8094912](https://pmc.ncbi.nlm.nih.gov/articles/PMC8094912/)),
which reports of the Melde line of work that *"PDMS particles were functionalized with UV-sensitive
linkers, patterned within a hydrogel, and subsequently UV radiated to retain the pattern after
switching off the ultrasound,"* and that *"ring size or line dimensions could be tuned by adjusting
the applied frequency."*

**This is, quite literally, "cymatics where the pattern stays, in 3D," and it is seven to ten years
old.** What it is *not* is the proposal's mechanism: the memory lives in a **cured matrix**, not in
the structure's own bistable cells, so it is single-use and not re-writable, and the patterned
objects are free particles in a fluid rather than resonators fixed in a shell.

*Plain-language reading: the "sand stays put" problem has already been solved once — by gluing the
sand down. The proposal's claim to novelty has to rest entirely on solving it a second way, with
latches instead of glue, so that it can be un-latched and re-written.*

### 1.5 Near misses that show which half is easy

| Work | What it does | A | B | C | D | Why it is not a hit |
|---|---|:--:|:--:|:--:|:--:|---|
| Watkins *et al.* 2025, [arXiv:2508.20321](https://arxiv.org/abs/2508.20321) | boundary pulse (A, f) writes arbitrary bits into bistable cells; state persists | ~ | ✔ | ✘ | ✔ | N = 3 cells; selected object is a bit string, not a mode shape |
| Watkins *et al.* 2026, [arXiv:2609.07889](https://arxiv.org/abs/2609.07889) | boundary excitation writes *and* reads mechanical memory | ~ | ~ | ✘ | ✔ | states the material is a *"sensor of input amplitude"* |
| Ferracin, Jin, Tournat & Raney 2026, [arXiv:2603.02433](https://arxiv.org/abs/2603.02433) | phonon pairs whose **beating envelope is resonant with the pinned kink's translational mode** depin a transition wave | ✔ | ✔ | ✘ | ~ | frequency is tuned to a *localised* kink mode, not a global standing-wave pattern; it moves a domain wall, it does not paint a pattern |
| Bilal, Foehr & Daraio, PNAS 2017 | resonant gate at f₀ = 70 Hz flips a bistable element | ✘ | ✔ | ✘ | ✔ | one element |
| Melde *et al.* 2016 / 2018 / 2023 | frequency- and hologram-set field patterns matter in 2D and 3D; pattern fixed | ✘ | ✔ | ✔ | ✔ | memory is in a cured matrix, not in multistable cells; not re-writable |
| Li *et al.*, Adv. Sci. 2026, [PMC13336889](https://pmc.ncbi.nlm.nih.gov/articles/PMC13336889/) | bistable dome array encodes waveguides; states persist, "shape memory" | ✔ | ✘ | ✘ | ✔ | verbatim: *"the bistable states were programmed through manual pressing"* — local addressing by hand |
| Sirote-Katz, Shohat, Merrigan, Lahini, Nisoli & Shokef, Nat. Commun. 15, 4008 (2024), [PMC11109184](https://pmc.ncbi.nlm.nih.gov/articles/PMC11109184/) | frustrated periodic metamaterial with an extensive set of disordered metastable states; history-dependent | ✔ | ✘ | ✘ | ✔ | verbatim: *"we can precisely control the states of the triangles by manipulating the squares around them"* — local addressing |
| Chen, Xia, Shi *et al.* (guided transition waves), PNAS 117 (2020) | transition waves steered along designed paths in multistable lattices | ✔ | ✘ | ✘ | ✔ | *record only, not fetched*; triggered locally, geometry steers the front |

Legend: ✔ satisfied, ~ partially, ✘ not satisfied, against requirements A–D of §1.0.

**What the table says, read across rather than down: requirement C is the only column that is empty
everywhere.** Frequency-triggered latching exists. Remote whole-body writing exists. Pattern
permanence exists. *Nobody has claimed that the latched pattern is the eigenmode.*

### 1.6 How hard I looked, and where I did not

Searched (English, general web search plus targeted fetches): acoustic and elastic metamaterials;
mechanical memory; multistable / bistable / phase-transition lattices; hysterons and Preisach
models; programmable and reconfigurable mechanical metamaterials; acoustic and mechanical
holography; acoustic patterning and assembly with subsequent curing; 4D printing and shape-memory
lattices; Chladni-plate and Faraday-wave pattern selection; "mode-selective" and "modal" writing;
transition-wave pinning; phononic transistors and logic; spherical-shell resonators and
spherical-harmonic mode classification; and a patent-database pass on bistable latching of
standing-wave patterns.

**Not covered, and each is a real gap:** (i) no systematic patent-family search beyond one keyword
pass — the Google Patents results returned only electronic bistable latches, which is a sign the
query was wrong for that corpus rather than that the art is absent; (ii) no non-English literature;
(iii) no search of the **MEMS/NEMS** literature, where "drive a membrane at a mode and latch it" is
a plausible place for this to already exist at micro scale; (iv) no search of the **origami/kirigami
self-folding-by-vibration** literature; (v) no citation-graph walk forward from Watkins *et al.*
2025, which is the single highest-yield unfetched move (§6).

---

## 2. Q2 — the dispersion anchor, verified and corrected

### 2.1 The paper exists, and I read all of it

**Liu, Zhang, Mao, Zhu, Yang, Chan & Sheng, *"Locally Resonant Sonic Materials,"* Science 289(5485),
1734–1736, 8 September 2000, DOI [10.1126/science.289.5485.1734](https://doi.org/10.1126/science.289.5485.1734).**

`science.org` returns HTTP 403 to this session. The **full three-page PDF was fetched from the senior
author's own institutional site** — [sheng.people.ust.hk](http://sheng.people.ust.hk/wp-content/uploads/2017/08/Locally-Resonant-Sonic-Materials.pdf)
— and text-extracted locally. Everything quoted in this section is from that full text.
*Transcription note: the extraction mangles the `fi`/`fl` ligatures (e.g. "reßector" for
"reflector"); I have restored them silently in the quotes and flag it here so the restoration is
visible rather than hidden.*

Abstract, verbatim:

> "We have fabricated sonic crystals, based on the idea of localized resonant structures, that
> exhibit spectral gaps with a lattice constant two orders of magnitude smaller than the relevant
> wavelength. Disordered composites made from such localized resonant structures behave as a
> material with effective negative elastic constants and a total wave reflector within certain
> tunable sonic frequency ranges. A 2-centimeter slab of this composite material is shown to break
> the conventional mass-density law of sound transmission by one or more orders of magnitude at 400
> hertz."

### 2.2 The correction — it does **not** say "negative effective mass density"

**A full-text search of the retrieved paper for the phrase "mass density" as an effective property
returns nothing.** Every occurrence of "mass density" in the paper is either the ordinary density of
a constituent (`ρ₁`, `ρ₂`), the *average* density of the sample, or the **"mass-density law"** of
sound transmission — a textbook rule about how much sound a heavy panel blocks. The negative
quantity in the paper is always an **elastic constant / modulus**:

> "Although the static elastic constant must be positive for maintaining structural stability,
> resonance-induced negative elastic constants should be possible, as demonstrated here at low sonic
> frequencies."

And the authors themselves later disowned that reading. Ping Sheng's HKUST research page
([sheng.people.ust.hk/?p=176](http://sheng.people.ust.hk/?p=176)), titled *"Negative dynamic mass
density and locally resonant sonic materials"*, says of this very paper, verbatim:

> "In the publication below, the effect was wrongly attributed to negative elastic constant, but
> this has been corrected in the subsequent publications."

**The correct primary source for negative effective mass density is therefore
Liu, Chan & Sheng, *"Analytic model of phononic crystals with local resonances,"* Phys. Rev. B 71,
014103 (2005),** DOI [10.1103/PhysRevB.71.014103](https://doi.org/10.1103/PhysRevB.71.014103) —
*record and abstract verified via the APS page and the HKUST group publication list; full text not
fetched.* Its stated result is that effective mass densities of three-component locally resonant
phononic crystals *turn negative close to the local resonances*, derived analytically for coated
spheres in a matrix (3D) and coated cylinders (2D).

**Why the distinction is load-bearing and not pedantry.** The proposal's whole mechanism rests on a
*heavy core on a soft spring* moving **out of phase** with the driving wave — that out-of-phase
inertia is exactly what "negative effective mass density" names. Citing the 2000 paper for it cites
a paper that attributed the same data to the *stiffness* instead, an attribution its own senior
author calls wrong. Under this repo's rule that research is the referee, a wrong-paper citation for
the mechanism you are actually claiming is the kind of thing that would have gone through unchecked.

**A finer point that explains how the error happened.** The 2000 paper *did* retrieve a negative
quantity from the measurement, but by **assuming the density and inverting for the modulus**:

> "Equation 1 can be used in conjunction with the transmission data … to do inversion for the
> effective κ₂ of a slab of homogeneous medium with the same transmission characteristics. **By
> letting ρ₂ = ρₑ be the average mass density of the sample**, an effective κ₂, here denoted by κₑ,
> was obtained. … close to the resonances the modulus actually turns negative"

(Emphasis mine.) *Plain-language reading: one measurement of how much sound gets through cannot on
its own tell you whether the "heaviness" or the "stiffness" went negative — they enter the answer
together. The 2000 paper pinned the heaviness to the ordinary average and let the stiffness absorb
the whole anomaly. The 2005 paper redid the bookkeeping and put the anomaly where it belongs, in the
heaviness.*

### 2.3 What was measured versus what was modelled

This repo cares about this split more than about the headline, so it is tabulated separately.

| Claim | Status | Evidence in the paper |
|---|---|---|
| Amplitude transmission vs frequency, 250 Hz to >1600 Hz, four-layer crystal | **`MEASURED`** | *"Sonic transmission was measured using a modified Bruel & Kjaer (B&K) two-microphone impedance measurement tube, type 4206."* |
| Transmission dips of the ordered sample at **380 Hz and 1350 Hz** | **`MEASURED` + `SIMULATED`, in agreement** | *"The theoretical predictions, with no adjustable parameters, are in good accord with the experimental results, in terms of the frequency positions of the dips (located at 380 and 1350 Hz)"* |
| Transmission dips of the **disordered** sample at **400 Hz and 1100 Hz** | **`MEASURED`** | *"The transmission coefficient of the composite sample … exhibits two significant dips centered at 400 and 1100 Hz"* |
| Absorption is negligible — it is a reflector, not an absorber | **`MEASURED`** | *"reflection coefficient as a function of frequency varies between 0.98 and 1, that is, within the measurement error. We conclude that absorption is negligible"* |
| 180° phase jumps at the resonances | **`MEASURED`** | *"there are observed 180° phase jumps, giving direct evidence for the underlying resonance mechanism"* |
| **Band structure** and the existence of a **complete** band gap | **`SIMULATED`** (multiple-scattering theory), explicitly hedged by the authors | *"transmission measurement in one direction alone does not establish the existence of a complete band gap"* |
| Displacement mode shapes at the two dips (core-on-spring; rubber "optical" mode) | **`SIMULATED`** | *"Calculated displacement configurations at the first (A) and second (B) dip frequencies"* |
| Effective modulus goes negative near resonance | **`INFERRED`** — inversion of measured transmission under an assumed density | see §2.2 |
| Negative effective **mass density** | **not in this paper** — see §2.2 | — |

### 2.4 Geometry and the sub-wavelength claim, as stated

Two samples, both verbatim from the paper.

**Sample 1 — ordered.** *"we used centimeter-sized lead balls as the core material, coated with a
2.5-mm layer of silicone rubber … arranged in an 8 × 8 × 8 simple cubic crystal with a lattice
constant of 1.55 cm … with epoxy as the hard matrix material."*
Transmission measured on *"effectively a four-layer sonic crystal."*

**Sample 2 — disordered.** *"a circular plate 2.1 cm thick and 9.8 cm in diameter, containing 48
volume % of randomly dispersed 10-mm lead spheres, each coated with a 3.5-mm layer of silicone
rubber."*

**The sub-wavelength claim, verbatim:** *"Note that at 500 Hz, the center of the lower frequency gap,
the lattice constant of our sonic crystal is 300 times smaller than that of longitudinal wavelength
in epoxy."*

**The mechanism, verbatim:** *"This low-frequency resonance may be understood as an oscillation, in
which the inner core provides the heavy mass and the silicone rubber provides the soft spring."*

*Plain-language reading: a heavy lead pellet wrapped in rubber is a weight on a spring. Get the
timing right and a whole grid of these weights sloshes back against the incoming sound and cancels
it — so the material blocks a 70-centimetre-long sound wave with a structure whose repeating unit is
1.55 cm. That 300-to-1 ratio is the whole point, and it is the part that is genuinely measured.*

**Verdict on Q2: the anchor is real, it is correctly attributed for the sub-wavelength band gap, and
it is mis-attributed for negative effective mass density.** Use Liu 2000 for the band gap; use Liu,
Chan & Sheng 2005 for negative mass density.

---

## 3. Q3 — the load-bearing assumption: threshold spread and hold time

The proposal latches a pattern by a **threshold**: cells at the antinodes cross their snap-through
barrier, cells at the nodes do not. That works only if thousands of cells share a threshold tightly
enough that the drive amplitude can sit between "node cell does not snap" and "antinode cell does."
So the whole idea turns on one number — the spread — and on one duration — how long a snapped cell
stays snapped.

### 3.1 The spread: nobody publishes it

**Finding: no retrieved source reports a measured distribution of switching thresholds across a
population of nominally identical multistable cells.** Not a histogram, not a standard deviation of
snap force, not a percentage. Searched specifically for "coefficient of variation" / "standard
deviation" of snap-through critical force across arrays, and for statistics of hysteron switching
fields. This is stated as a **negative finding of a directed search**, not as proof none exists.

The nearest published numbers, all from sources fetched and read:

| Quantity | Reported value | Source | What it is |
|---|---|---|---|
| Truss stiffness across the cells of the writing demo | **k_truss = 1428 ± 72 N/m** (≈ **5.0%**) | Watkins *et al.* 2025, [arXiv:2508.20321](https://arxiv.org/abs/2508.20321) | a **parameter** spread, not a threshold spread |
| Undeformed strut length | **l₀ = 28.8 ± 1 mm** (≈ **3.5%**) | same | same |
| Initial truss angle | **θ₀ = 11.55 ± 0.14°** (≈ **1.2%**) | same | same |
| Attribution of that spread | *"the slight variations in the parameters defining the von Mises trusses arise from minute fabrication imperfections"* | same | the authors' own words |
| Number of cells in the demonstration | **N = 3** | same | verbatim: *"we focus on a metamaterial with N = 3 unit cells"* |
| Number of hysterons characterised | **3** | Ding & van Hecke, [arXiv:2204.06488](https://arxiv.org/abs/2204.06488) | designed to differ |
| Designed pusher heights making them differ | **{h₁, h₂, h₃} = {0.23, 0.28, 0.33}** | same | spread is a **design choice** |
| Measured snapping strains (representative) | **ε⁺ = 0.18**, **ε⁻ = 0.13** | same | forward/reverse thresholds of one element |
| Threshold shifts caused by neighbours' states | *"small but systematic deviation between ε₂⁺(001) and ε₂⁺(101) indicates the presence of hysteron interactions"* | same | the threshold is **not** a property of the cell alone |
| Error bars, how obtained | *"three independent runs on two samples, and calculated our errorbar based on these six datasets"* | same | six datasets, three elements |

**Three things follow, and each one is bad for the proposal in a different way.**

1. **The ~5% figure is the wrong quantity, and the right quantity is probably worse.** Snap-through
   force is a strongly nonlinear function of the truss geometry — a von Mises truss's critical load
   scales roughly with the *cube* of its initial rise angle — so a 1.2% spread in θ₀ and a 5% spread
   in stiffness do not produce a ~5% spread in threshold; they produce something larger, and nobody
   has measured how much larger. Calling ±5% "the spread" would be citing a number that is both
   unverified for the purpose and probably optimistic. **`ASSUMED` at best; do not quote it as the
   threshold spread.**

2. **The literature wants the thresholds to differ.** Ding & van Hecke build three hysterons with
   deliberately staggered pusher heights so they snap in a controlled order; the ScienceDirect
   literature on multistable cylinders describes an uncontrolled stack snapping *in a seemingly
   random sequence influenced by minute manufacturing variations* (*record only; the ScienceDirect
   page was not fetched — see §7*). The proposal needs the **opposite** property — thousands of cells
   agreeing on one threshold — and no retrieved work has ever tried to achieve or measure that.

3. **The threshold is not even a property of a single cell.** van Hecke's measured
   *"hysteron interactions"* mean a cell's switching field depends on the states of its neighbours.
   On a shell where the intended pattern *is* a spatial arrangement of switched neighbours, that
   coupling is not a second-order correction — it is in the middle of the mechanism, and it is
   uncharacterised at any scale above three elements.

*Plain-language reading: the plan needs thousands of identical switches that all flip at the same
push. The published work has three switches, deliberately built to flip at different pushes, and it
reports how much the springs varied (about 5%) rather than how much the flipping point varied. And
it shows that a switch's flipping point changes depending on what its neighbours have already done.
Nobody has built or measured the thing the plan assumes.*

### 3.2 Hold time: a documented failure mode, unquantified for lattices

**Finding: no retrieved source reports a hold time for a latched state in a multistable
metamaterial.** What the literature does report is a named mechanism by which such states fail:

**Gomez, Moulton & Vella, *"Dynamics of viscoelastic snap-through,"* J. Mech. Phys. Solids 124,
781–813 (2019), preprint [arXiv:1807.05978](https://arxiv.org/abs/1807.05978)** — abstract/record
fetched, full text not fetched. Verbatim from the abstract:

> "it either immediately snaps back over the elastic timescale or it displays 'pseudo-bistability',
> in which it undergoes a slow creeping motion before rapidly accelerating"

*Plain-language reading: a plastic dome that has been pushed inside-out can look perfectly settled,
sit there for a long time, and then pop back out on its own. The material slowly relaxes out from
under the latch.*

Two further, weaker points, both `LITERATURE-SUPPORTED` from search-result synthesis and **not**
from fetched full text — flagged as such and not to be relied on without opening the sources:

- Durability of bistable auxetics is assessed by **cycles to failure**, with **10,000 loading
  cycles** used as a stated minimum durability level (*"Durable Bistable Auxetics Made of Rigid
  Solids,"* [arXiv:1711.09336](https://arxiv.org/abs/1711.09336) — record only).
- Viscoelastic composites are reported to **lose deployment accuracy after prolonged storage**
  (search-result synthesis over the composite bistable-shell creep literature — not fetched).

**The combination is what matters.** Cycle counts answer *"can I re-write it many times?"*
Pseudo-bistability answers *"will one write survive being ignored for a year?"* — and only the first
question has published numbers. For a device whose entire selling point is that the pattern persists
without power, **hold time is the headline specification and it is unmeasured.**

### 3.3 Scale: the gap between the literature and the proposal

| | Published demonstrations | The proposal |
|---|---|---|
| Cells | **3** (Watkins *et al.*; Ding & van Hecke); tens in dome arrays (Li *et al.*) | thousands, on a closed spherical shell |
| Dimension | **1D chain**, or a **2D** hand-pressed sheet | **3D**, doubly curved, closed |
| Write | boundary pulse (1D), or finger (2D) | global drive selecting a spherical harmonic |
| Threshold agreement required | **none** — differences are exploited | **tight** — thousands must share one threshold |

**This is not a "more engineering" gap.** Going from three cells to thousands inverts the property
the field has been exploiting: every retrieved demonstration *uses* threshold disorder to address
cells individually, and the proposal *needs it gone*.

---

## 4. What this changes about the idea

Stated as findings, not as a recommendation — per CLAUDE.md, warn, never block.

- **The idea is not a known result.** No retrieved source imprints a standing-wave mode shape into a
  multistable lattice by drive frequency. Under the charter's vocabulary this reads as a **new
  mechanism** — *"a different physical route to the same behaviour"* — which the charter permits and
  requires to arrive **as a hypothesis with a test attached**, not as a claim.
- **It is also not wholly new.** Three of its four requirements are separately demonstrated, one of
  them (permanent frequency-set 3D patterning) a decade ago and in commercial-adjacent use. A
  novelty claim has to be narrowed to requirement C — *the selector is the eigenmode* — or it will
  be met by prior art on first contact.
- **Its single most fragile assumption has no published number.** The threshold-spread question is
  not merely unanswered; it names an experiment nobody has run (§6).
- **One citation currently attached to it is wrong.** Liu 2000 does not support negative effective
  mass density (§2.2).

### 4.4 What transfers to the electromagnetic version, and what does not

Recorded for the agent working the EM line. Short, because the transfer is narrow and I did not
search the EM literature at all.

**Transfers as a question, not as an answer — §1.** "Does a global drive at a chosen frequency
imprint a *spatial mode shape* into a lattice of latching cells, such that the pattern persists
without power?" is the same question in EM. The acoustic answer — **the latching, the remote
whole-body writing and the permanence are each demonstrated, but the mode-as-selector is not** —
is **suggestive and nothing more**, because no EM search was run. **Treat §1.5's table as a
hypothesis about where the EM gap will also be, to be checked against the EM literature (RF MEMS
metasurfaces, phase-change GST/VO₂ metasurfaces, non-volatile reconfigurable intelligent surfaces),
not as a result imported from acoustics.** `INFERRED`, low confidence, and cheap to falsify.

**Transfers as a live risk — §3.** Threshold spread is not an acoustic problem; it is a problem of
**any surface whose state is set by a threshold discriminator**. An EM latching metasurface sets its
cells by some field, current, voltage or optical pulse crossing a per-cell threshold, so it needs
the same thing the acoustic version needed: thousands of cells whose thresholds agree tightly enough
that one drive level separates "switch" from "don't." The acoustic literature's answer — **nobody
publishes the distribution, and demonstrations run at N = 3** — should be read as a warning about
*what to go looking for in the EM sources*, since RF MEMS and phase-change cells have their own,
better-instrumented, and possibly already-published statistics (MEMS pull-in voltage spread and
GST/VO₂ set/reset threshold distributions are the obvious places to look). **This is the question
worth carrying across; the acoustic numbers themselves are not.**

**Does not transfer: anything numeric.** No frequency, dimension, modulus, threshold force or hold
time in this document has any bearing on an EM design, for the reasons
`docs/elastodynamic-metamaterials-dataset-relevance.md` §2.2 sets out — different governing
equations, different material parameters, wave speeds five to six orders of magnitude apart. §2's
sub-wavelength local-resonance result in particular is an *acoustic* result; it has a well-known
electromagnetic analogue, but that analogue has its own primary sources and this document is not
one of them.

---

## 5. On whether this belongs in this repo

Not decided here; recorded so the decision has the precedent in front of it.

`docs/elastodynamic-metamaterials-dataset-relevance.md` (2026-09-10) already settled a structurally
identical question — a mechanical/elastodynamic artefact offered to an electromagnetic program — and
its finding was that **the physics does not transfer numerically** (different governing equations,
different material parameters, wave speeds five to six orders of magnitude apart), while the
**method** can transfer as a pattern. Everything in that analysis applies verbatim to this proposal:
kHz–MHz elastic waves in centimetre-scale resonators share Bloch-periodic *mathematics* with GHz
electromagnetics and share no *numbers* with it.

The one genuinely new consideration this proposal raises, which that document did not face, is that
it is not a dataset to reuse but a **device concept in a different physics** — so the question is
not "can we use its numbers" (no) but "is this program's charter about printed conformal surfaces
wide enough to hold it." That is a human decision. What this document supplies is that the concept
is neither already-done nor already-refuted, and that its weakest point is a fabrication-statistics
question that this program — which owns printers and cares about print-to-print variation — is
unusually well placed to answer, and unusually likely to underestimate if it does not.

---

## 6. What is still unknown after this pass

| # | Unknown | Why it matters | Confidence that it is genuinely unknown |
|---|---|---|---|
| 1 | **The cell-to-cell switching-threshold distribution** for any multistable metamaterial, at any scale | The whole mechanism is a threshold discriminator; if the spread exceeds the node/antinode amplitude contrast, no drive amplitude works | **High** — directly searched, nothing found |
| 2 | **Hold time of a latched state** in a printed polymer lattice | The device's entire value is persistence without power; pseudo-bistability is a documented route to losing it | **High** — directly searched, only the mechanism is published, never a duration |
| 3 | Whether threshold spread **scales** with array size (does the tail get worse with N?) | A 1-in-1000 outlier is irrelevant at N = 3 and fatal at N = 3000 | **High** — no source got past N = 3 |
| 4 | Whether a **mode-shape-selected** latch exists in the **MEMS/NEMS** or **origami self-folding** literatures | The two most plausible places the art could hide; neither was searched | **Low** — this is a gap in my search, not in the world |
| 5 | Whether any **patent family** claims this | One keyword pass returned only electronic latches, which suggests a wrong query rather than an empty field | **Low** — search inadequate |
| 6 | Whether papers **citing** Watkins *et al.* 2025 have already extended it to 2D/3D and to mode selection | It is a year old and the obvious next step | **Low** — no citation-graph walk performed |
| 7 | Whether hysteron **interactions** help or hurt at lattice scale | On a shell the pattern *is* an arrangement of switched neighbours, so the coupling is in the mechanism, not beside it | **High** — measured only for 3 elements |

### The single move that would resolve the most

> **Read the two candidates below in light of the pivot.** They were written for the acoustic
> device. The **reading** move still pays, because it also tests whether the mode-as-selector gap is
> real rather than an artefact of my search. The **printing** move does not — nobody is building a
> mechanical shell now — but the question it was designed to answer (what is the threshold spread
> across a real population of latching cells?) is exactly the question the EM version inherits, and
> should be asked of RF MEMS and phase-change cells instead. See §4.4.

**Two candidates, and they resolve different questions — so the choice depends on which decision is
being made first.**

**If the question is "is it new?" — do the citation-graph walk forward from Watkins *et al.* 2025
([arXiv:2508.20321](https://arxiv.org/abs/2508.20321)) and Ferracin *et al.* 2026
([arXiv:2603.02433](https://arxiv.org/abs/2603.02433)), plus one proper patent-family search.**
This is a fetch, it costs an hour, and it closes unknowns 4–6 at once. These two papers sit exactly
on the boundary of the idea and are recent enough that anyone who has taken the next step has cited
them. **Do this one first** — it is cheap, and if it turns up a direct hit then unknowns 1–3 stop
mattering.

**If the question is "would it work?" — the experiment nobody has run is: print one batch of
N ≥ 100 nominally identical bistable cells and measure the snap-through force of every one of them,
individually, and publish the histogram.** That is unknown 1 in a single measurement, it is within
this program's existing print-and-measure capability, it needs no new physics, and it produces the
number the entire concept stands on. Run it twice — once immediately, once after the cells have sat
latched for a month — and it closes unknown 2 as well.

*In plain terms: spend an hour reading before spending a month printing; then, if the idea survives
the reading, print a hundred switches and weigh every one of them, because that single boring
histogram decides whether any of the rest is buildable.*

---

## 7. Provenance summary

| Claim | Label | Basis |
|---|---|---|
| No source demonstrates frequency-selected **mode-shape** latching | `LITERATURE-SUPPORTED` (negative finding) | Directed search, §1.6 lists coverage **and** gaps |
| Watkins *et al.* 2025 write arbitrary bits remotely by an (A, f) boundary pulse; states persist; N = 3 | `LITERATURE-SUPPORTED` | **Full text fetched and read** ([arXiv:2508.20321](https://arxiv.org/abs/2508.20321), HTML rendering) |
| Its PRL publication record and DOI `10.1103/pkk5-dykb` | `UNVERIFIED` | APS page HTTP 403; arXiv has no `journal-ref` |
| Watkins *et al.* 2026 states the material senses **input amplitude** | `LITERATURE-SUPPORTED` | **Abstract fetched verbatim**; body read via HTML rendering ([arXiv:2609.07889](https://arxiv.org/abs/2609.07889)) |
| Ferracin *et al.* 2026 depin kinks with a resonant phonon beat | `LITERATURE-SUPPORTED` | **Abstract fetched verbatim** ([arXiv:2603.02433](https://arxiv.org/abs/2603.02433)); full text not fetched |
| Bilal *et al.* 2017: resonant gate at 70 Hz flips a bistable element | `LITERATURE-SUPPORTED` | **Full text fetched** from the author-hosted PDF and text-extracted |
| Li *et al.* 2026 programs dome states by **manual pressing** | `LITERATURE-SUPPORTED` | **Full text fetched** ([PMC13336889](https://pmc.ncbi.nlm.nih.gov/articles/PMC13336889/)) |
| Sirote-Katz *et al.* 2024 addresses states **locally** | `LITERATURE-SUPPORTED` | **Full text fetched** ([PMC11109184](https://pmc.ncbi.nlm.nih.gov/articles/PMC11109184/)) |
| Melde *et al.* 2016 / 2018 / 2023: frequency-set patterns fixed by curing, incl. 3D | `LITERATURE-SUPPORTED` | Records verified (Nature / Wiley / PubMed / ADS / MPI-IS); **abstracts and records only, no full text**. The "UV-fixed to retain the pattern" and "tuned by adjusting the applied frequency" statements are quoted from a **fetched** open-access review, [PMC8094912](https://pmc.ncbi.nlm.nih.gov/articles/PMC8094912/), not from Melde *et al.* themselves |
| Liu *et al.* 2000 exists; abstract, geometry, dip frequencies, measured/modelled split | `LITERATURE-SUPPORTED` / `MEASURED` as tabulated in §2.3 | **Full three-page text fetched** from [the senior author's institutional copy](http://sheng.people.ust.hk/wp-content/uploads/2017/08/Locally-Resonant-Sonic-Materials.pdf) and text-extracted locally |
| Liu 2000 does **not** claim negative effective mass density | `VERIFIED` | Full-text search of the retrieved paper: every "mass density" is a constituent density, an average density, or the "mass-density law" |
| Sheng's own statement that the 2000 attribution was wrong | `LITERATURE-SUPPORTED` | **Fetched** from [sheng.people.ust.hk/?p=176](http://sheng.people.ust.hk/?p=176), quoted verbatim |
| Liu, Chan & Sheng, PRB 71, 014103 (2005) is the negative-mass-density source | `LITERATURE-SUPPORTED` | **Record and abstract verified** via the APS page; full text not fetched |
| Fabrication spread k_truss = 1428 ± 72 N/m, l₀ = 28.8 ± 1 mm, θ₀ = 11.55 ± 0.14° | `MEASURED` (by the cited authors) | **Fetched verbatim** from arXiv:2508.20321 |
| That ~5% is **not** the switching-threshold spread and is probably optimistic for it | `INFERRED` | This document's reasoning from the nonlinearity of von Mises snap-through; **no source states it** |
| No published distribution of cell-to-cell switching thresholds | `LITERATURE-SUPPORTED` (negative finding) | Directed search on "coefficient of variation"/"standard deviation" of snap-through force and on hysteron switching-field statistics |
| Hysteron switching fields depend on neighbours' states | `LITERATURE-SUPPORTED` | **Full text fetched** ([arXiv:2204.06488](https://arxiv.org/abs/2204.06488)), quoted verbatim |
| Pseudo-bistability: latched viscoelastic states creep then snap back | `LITERATURE-SUPPORTED` | **Abstract fetched verbatim** ([arXiv:1807.05978](https://arxiv.org/abs/1807.05978)); full text not fetched |
| 10,000 cycles as a bistable-auxetic durability threshold | `UNVERIFIED` | Search-result synthesis only; [arXiv:1711.09336](https://arxiv.org/abs/1711.09336) **not fetched** |
| Viscoelastic composites lose deployment accuracy after prolonged storage | `UNVERIFIED` | Search-result synthesis only; no source fetched |
| Uncontrolled multistable stacks snap in a "seemingly random sequence" from manufacturing variation | `UNVERIFIED` | Search-result synthesis of a ScienceDirect record; **not fetched** (§7 stranded) |
| Chen *et al.*, guided transition waves, PNAS 117 (2020) | `UNVERIFIED` | Record only; not fetched |

### What is stranded

| Source | Why | What is lost |
|---|---|---|
| Liu *et al.* 2000 at `science.org` | HTTP 403 | Nothing — the author-hosted full text was read instead. The figures (band structure, displacement fields) were not viewable, so all figure-derived statements here come from the caption and body text |
| Liu, Chan & Sheng, PRB 71, 014103 (2005) | APS paywall | The actual derivation of negative effective mass density. §2.2's correction rests on Sheng's own summary plus the PRB abstract, not on the derivation |
| Watkins *et al.* 2025 in PRL | APS HTTP 403 | Confirmation of the journal record and any changes between preprint and published version |
| Ma *et al.*, *"Acoustic Holographic Cell Patterning in a Biocompatible Hydrogel,"* Adv. Mater. (2020) | Wiley, not fetched | A first-hand statement of frequency-set patterning + fixing, rather than the review's paraphrase |
| Melde *et al.* 2016 / 2018 / 2023 full texts | Nature / Wiley / science.org paywalls | Whether the field pattern is described as a **structural eigenmode** or purely as a shaped travelling field — which is exactly requirement C |
| *"Controlled snapping sequence and energy absorption in multistable mechanical metamaterial cylinders,"* Int. J. Mech. Sci. (2021) | ScienceDirect, not fetched | The most likely single source for a real number on uncontrolled snapping-order variation |
| Keim / Shohat / van Hecke review, *"Mechanical memories in solids, from disorder to design"* ([arXiv:2405.08158](https://arxiv.org/abs/2405.08158)) | Abstract fetched; body not read | The best available survey of whether threshold statistics and aging are treated anywhere in this field. **This is the highest-value stranded item for Q3** |

---

## 8. Retrieved sources

1. Z. Liu, X. Zhang, Y. Mao, Y. Y. Zhu, Z. Yang, C. T. Chan & P. Sheng, *"Locally Resonant Sonic Materials,"* **Science 289(5485), 1734–1736 (2000)**, DOI [10.1126/science.289.5485.1734](https://doi.org/10.1126/science.289.5485.1734). Full text read from [the author-hosted copy](http://sheng.people.ust.hk/wp-content/uploads/2017/08/Locally-Resonant-Sonic-Materials.pdf).
2. P. Sheng, *"Negative dynamic mass density and locally resonant sonic materials,"* HKUST Physics research page — [sheng.people.ust.hk/?p=176](http://sheng.people.ust.hk/?p=176).
3. Z. Liu, C. T. Chan & P. Sheng, *"Analytic model of phononic crystals with local resonances,"* **Phys. Rev. B 71, 014103 (2005)**, DOI [10.1103/PhysRevB.71.014103](https://doi.org/10.1103/PhysRevB.71.014103) — record and abstract only.
4. A. A. Watkins, G. Bordiga, M. Mu, V. Tournat & K. Bertoldi, *"Arbitrary mechanical memory encoding via nonlinear waves in bistable metamaterials,"* [arXiv:2508.20321](https://arxiv.org/abs/2508.20321) (27 Aug 2025).
5. A. A. Watkins, G. Bordiga, V. Tournat & K. Bertoldi, *"Wave-based reading of mechanical memory in multistable mass-in-mass metamaterials,"* [arXiv:2609.07889](https://arxiv.org/abs/2609.07889) (7 Sep 2026).
6. S. Ferracin, D. Jin, V. Tournat & J. R. Raney, *"Phonon controlled mechanical memory via pinning and depinning of transition waves,"* [arXiv:2603.02433](https://arxiv.org/abs/2603.02433) (2 Mar 2026) — abstract only.
7. O. R. Bilal, A. Foehr & C. Daraio, *"Bistable metamaterial for switching and cascading elastic vibrations,"* **PNAS 114(18), 4603–4606 (2017)**, DOI [10.1073/pnas.1618314114](https://doi.org/10.1073/pnas.1618314114). Full text read from [the author-hosted PDF](https://www.daraio.caltech.edu/publications/PNAS-2017-Bilal-4603-6.pdf).
8. J. Ding & M. van Hecke, *"Sequential snapping and pathways in a mechanical metamaterial,"* **J. Chem. Phys. 156, 204902 (2022)**, preprint [arXiv:2204.06488](https://arxiv.org/abs/2204.06488).
9. Y. Sirote-Katz, D. Shohat, C. Merrigan, Y. Lahini, C. Nisoli & Y. Shokef, *"Emergent disorder and mechanical memory in periodic metamaterials,"* **Nat. Commun. 15, 4008 (2024)**, DOI [10.1038/s41467-024-47780-w](https://doi.org/10.1038/s41467-024-47780-w), read via [PMC11109184](https://pmc.ncbi.nlm.nih.gov/articles/PMC11109184/).
10. Li *et al.*, *"Programmable Elastic Wave Control Via Mechanical-Acoustic Interaction in Bistable Metamaterials,"* **Adv. Sci. (2026)**, DOI [10.1002/advs.76005](https://doi.org/10.1002/advs.76005), read via [PMC13336889](https://pmc.ncbi.nlm.nih.gov/articles/PMC13336889/).
11. M. Gomez, D. E. Moulton & D. Vella, *"Dynamics of viscoelastic snap-through,"* **J. Mech. Phys. Solids 124, 781–813 (2019)**, preprint [arXiv:1807.05978](https://arxiv.org/abs/1807.05978) — abstract only.
12. K. Melde, A. G. Mark, T. Qiu & P. Fischer, *"Holograms for acoustics,"* **Nature 537, 518–522 (2016)**, DOI [10.1038/nature19755](https://doi.org/10.1038/nature19755) — record only.
13. K. Melde, E. Choi, Z. Wu, S. Palagi, T. Qiu & P. Fischer, *"Acoustic Fabrication via the Assembly and Fusion of Particles,"* **Adv. Mater. 30, 1704507 (2018)**, DOI [10.1002/adma.201704507](https://doi.org/10.1002/adma.201704507) — record only.
14. K. Melde, H. Kremer, M. Shi, S. Seneca, C. Frey, I. Platzman, C. Degel, D. Schmitt, B. Schölkopf & P. Fischer, *"Compact holographic sound fields enable rapid one-step assembly of matter in 3D,"* **Sci. Adv. 9, eadf6182 (2023)**, DOI [10.1126/sciadv.adf6182](https://doi.org/10.1126/sciadv.adf6182) — record verified via [NASA ADS](https://ui.adsabs.harvard.edu/abs/2023SciA....9F6182M/abstract); full text not fetched.
15. *"The waves that make the pattern: a review on acoustic manipulation in biomedical research,"* **Materials Today Bio (2021)**, read via [PMC8094912](https://pmc.ncbi.nlm.nih.gov/articles/PMC8094912/).
16. `/home/user/Principle_RF_Engineer_Agent/docs/elastodynamic-metamaterials-dataset-relevance.md` — this repo's standing precedent on the elastic/electromagnetic boundary.
17. `/home/user/Principle_RF_Engineer_Agent/docs/absorber-thickness-bandwidth-bound.md` — read for citation and provenance conventions.
