# Measured RF-band dielectric properties for PET, polyimide (Kapton), and generic polymer

**Research date:** 2026-09-09
**Prompted by:** a continuation of `docs/manufacturing-equipment-api-research.md`'s finding that
Materials Project — the one materials database with a genuine free API — returns DFT-computed,
zero-frequency dielectric tensors for crystal structures, not the measured, frequency-dependent
loss tangent this project's **Material-property library** needs for purchasable flexible-electronics
substrates. **Scope:** find real, citable, *measured* RF-band (ideally 1–20 GHz) relative permittivity
(εr) and loss tangent (tanδ) for the three substrate materials this project's domain model already
names — PET film, polyimide (Kapton), and "generic polymer" (`CONTEXT.md`'s Ink-property library
and Family fallback bracket entries) — sourced from peer-reviewed papers or arXiv preprints, which
resolve to `LITERATURE-SUPPORTED` provenance per `CONTEXT.md`'s Evidence hierarchy.

Every value below is either **retrieved** (a primary source was actually fetched and read in this
session) or explicitly marked otherwise. Nothing here is a recalled number presented as checked.

---

## Bottom line up front

**A directly-measured, GHz-band, fully-cited εr/tanδ pair was found for all three materials — but
the PET number is internally inconsistent with the wider literature and should be treated with
caution, not taken as authoritative on its own.** Polyimide/Kapton has the strongest single source:
a NASA/JPL-adjacent radio-astronomy group's own resonator measurement, sweeping 0.05–20 GHz,
giving εr ≈ 3.37 and tanδ = 0.008–0.013 at room temperature on real DuPont Kapton stock
(arXiv:1206.1461). PET has a directly-retrieved, peer-reviewed, GHz-band measurement
(Betancourt & Castán, 2013) — but its extracted εr (≈1.14) is roughly a third of every other PET
value in the wider literature (~2.8–3.4), which is physically implausible for a bulk polymer and
points to a likely extraction-method artifact for this specific thin-substrate ring-resonator setup;
a second, independent 2025 source gives εr = 2.8 without a stated frequency or tanδ. "Generic
polymer" is the weakest of the three: the best directly-retrieved, tabulated, GHz-swept source
(NIST NISTIR 6537) measures ceramic-*loaded* polymer composites built for embedded-capacitor
applications, not neat unfilled polymer sheet of the kind this project would actually specify as a
"generic polymer" substrate — so its numbers (εr 3.8–39, tanδ 0.002–0.15 depending on filler
loading) bound a family, they do not characterize one representative material.

**Mandatory first step (local research corpus, `F:\data`) — result: expected coverage gap, no
data found.** Ripgrep searches across `F:\data\arxiv-chunks\` (933 category subdirectories) for
`kapton`, `polyimide`, and `PET film` returned **zero matches** for all three terms. A sanity check
confirms the corpus and search tooling both work — `permittivity` alone matches 453 files — so
this is a real null result, not a broken search. It is consistent with this corpus's documented
coverage gap (overwhelmingly April–December 2007 papers, plus an unrelated CS/AI/ML-only
2026 batch, with no `physics.app-ph` or `eess.SP` category present at all): the whole rest of this
research was conducted against the open web and arXiv directly, per that gap's own guidance not
to let a corpus null result stand in for a real search.

---

## Summary table

| Material | Best measured value found | Frequency | Method | Source | Provenance if adopted |
|---|---|---|---|---|---|
| **Polyimide (Kapton)** | εr = 3.37 (297 K); tanδ = 0.008 (≤3 GHz) to 0.013 (≤12 GHz) | 0.05–20 GHz (VNA sweep; fit ranges to 3/6/12 GHz shown) | Copper microstrip tee resonators on DuPont Pyralux AP-8555R (5 mil Kapton), *S*₂₁ fit in Microwave Office | Harris, Sieth, Lau, Church, Samoska & Cleary, arXiv:1206.1461 | `LITERATURE-SUPPORTED` |
| **PET** | εr = 1.098–1.182 (mean 1.142 ± 0.039); tanδ = 0.025–0.039 (mean 0.0314 ± 0.0072) — **flagged, see §2** | 2.33–4.74 GHz | Microstrip ring resonator, two ring geometries, CST-assisted extraction | Betancourt & Castán, *Progress In Electromagnetics Research C*, Vol. 38, pp. 129–140 (2013) | `LITERATURE-SUPPORTED`, with a caveat attached (see below) |
| **PET** (secondary, no frequency/tanδ) | εr = 2.8 ("PET foil / Mylar A", 250 µm) | not stated | not stated (compiled/typical value in a comparative table) | Lotfi, Janda, Reboun & Blecha, *Scientific Reports* (2025), DOI 10.1038/s41598-025-22948-6 | `LITERATURE-SUPPORTED`, incomplete (no frequency) |
| **Generic polymer** | εr 3.75–39 (5 films); tanδ 0.002–0.15 depending on film and frequency | 200 Hz–8 GHz (per-film tables) | Microstrip resonator (TV1) + LCR impedance analyzer (TV0), NIST/NCMS Embedded Decoupling Capacitance project | Obrzut, Chiang, Popielarz & Nozaki, NISTIR 6537 (2000) | `LITERATURE-SUPPORTED`, but materials are ceramic-loaded composites, not neat polymer — see §3 |

Plain English for the table: εr ("dielectric constant") says how much a material slows and
concentrates an electric field compared to empty space — a bigger number means the field is
squeezed more tightly into the substrate, which is why it changes an antenna's resonant size.
tanδ ("loss tangent") says what fraction of the wave's energy the material eats as heat on every
pass — a bigger number means more of the signal disappears instead of radiating.

---

## 1. Polyimide (Kapton) — the strongest of the three

**Harris, A.I., Sieth, M., Lau, J.M., Church, S.E., Samoska, L.A. & Cleary, K., "Note: Cryogenic
microstripline-on-Kapton microwave interconnects," arXiv:1206.1461** (submitted to *Review of
Scientific Instruments*; retrieved and read directly in this session, full PDF).

The group built copper microstrip "tee" resonators directly on **DuPont Pyralux AP-8555R** —
0.5 oz/ft² rolled copper bonded to both sides of **5 mil (≈127 µm) thick Kapton polyimide** — and
measured them on an Agilent 8722D VNA from 50 MHz to 20 GHz, fitting the substrate's dielectric
constant and loss tangent in Microwave Office against the measured *S*₂₁. Table I of the paper
(reproduced below) gives:

| Fit range (0.05 GHz to) | εr, 297 K | εr, 77 K | tanδ, 297 K | tanδ, 77 K |
|---|---|---|---|---|
| 3 GHz | 3.378 | 3.377 | 0.008 | 0.000 |
| 6 GHz | 3.372 | 3.370 | 0.012 | 0.006 |
| 12 GHz | 3.348 | 3.350 | 0.013 | 0.007 |

The paper states directly: *"the dielectric constant εr changed by a negligible amount between
room temperature and 77 K; a representative value for microwave frequencies is εr = 3.37... Loss
in the dielectric drops by a factor of approximately two on cooling, from tan δ = 0.013 to 0.007."*
A separate parallel-line test structure gave a slightly higher room-temperature tanδ = 0.018 over
0.05–12 GHz — the paper's own explanation is that this second structure's fit folds in more
metallization/coupling loss, not that Kapton's intrinsic loss changed. The authors report the
overall model fit is good to at least 20 GHz.

**Plain English:** at room temperature, in the 3–12 GHz band this project cares about, Kapton
lets roughly 1.2–1.3% of the signal's power leak away as heat per unit of the loss mechanism this
number describes (tanδ 0.008–0.013) — low enough that Kapton is a genuinely low-loss microwave
substrate, not just a mechanically flexible one.

This is a strong `LITERATURE-SUPPORTED` candidate for the Material-property library: real
commercial stock (DuPont Pyralux, a Kapton product), a stated thickness, a stated frequency
sweep spanning this project's 1–20 GHz target band, and a directly-retrieved, non-paywalled
primary source with the full derivation shown.

**Supplementary but not recommended as the primary citation:** NISTIR 6537's "Film D" (see §3)
is labelled by its own authors as "high-k polyimide" and gives εr = 12.5 (200 Hz) declining to
11.6 (6 GHz), tanδ = 0.01 (200 Hz) dropping to ~0.002 (1 MHz) then rising to ~0.011–0.012 through
the 265 MHz–6 GHz microwave range. This is a *ceramic-loaded* polyimide composite built for
embedded capacitors — its εr is roughly 3–4× a neat Kapton film's — so it answers a different
question than "what does plain Kapton do" and should not be conflated with the Harris et al. value.

---

## 2. PET — a measured GHz-band value exists, but it disagrees sharply with the rest of the literature

**Betancourt, D. & Castán, J., "Printed Antenna on Flexible Low-Cost PET Substrate for UHF
Applications," *Progress In Electromagnetics Research C*, Vol. 38, pp. 129–140 (2013)** — fully
open access, retrieved and read directly in this session (PIER journals are open-access by policy).

The authors built two microstrip **ring resonators** (radius 40 mm, width 3 mm, gap 200 µm) on
**125 ± 5 µm thick PET foil from MacDermid**, measured *S*₂₁ on an Anritsu MS4623B VNA, and
extracted εr and tanδ from the resonant-peak positions and −3 dB bandwidths (formulae from Gupta,
Garg, Bahl & Bhartia, *Microstrip Lines and Slotlines*). Their Table 1:

| Ring | Mode | f (GHz) | εr | tanδ |
|---|---|---|---|---|
| A | 1 | 2.40 | 1.098 | 0.039 |
| A | 2 | 4.74 | 1.122 | 0.026 |
| B | 1 | 2.33 | 1.165 | 0.036 |
| B | 2 | 4.62 | 1.182 | 0.025 |

The paper's own averaged result: **εr = 1.142 ± 0.039, tanδ = 0.0314 ± 0.0072**, over 2.33–4.74 GHz.

**This εr is flagged, not adopted at face value.** Every other PET value surfaced in this
research — the compiled εr = 2.8 in Lotfi et al. 2025 below, and multiple secondary/patent-literature
values search-summarized during this session (εr in the 2.99–4 range at sub-3 GHz, and a
frequently-cited "≈3" figure) — clusters around **2.8–3.4**, consistent with PET's well-known bulk
value. A measured εr of 1.14 is roughly what you would expect from a low-density foam, not a
~1.4 g/cm³ semicrystalline polymer film, and is not physically plausible for bulk PET. The paper
does not flag this itself, and this project's own methodology (`CONTEXT.md`'s "compare prediction
against result and say which broke") says a threefold disagreement with consensus, unflagged by
its own authors, is a sign the *extraction method* broke, not the material: a 125 µm-thick
dielectric is very thin relative to a 40 mm-radius ring resonator's field confinement, and the
paper does not discuss whether its formula (derived for standard-thickness microstrip substrates)
still holds at that thickness ratio. **Recommendation: if this value is entered into the
Material-property library, its provenance note must state the disagreement with the wider
literature explicitly** — do not let a single measured-and-cited number silently outrank the
consensus range just because it carries `LITERATURE-SUPPORTED` provenance; a wrong measurement is
still wrong evidence, and the Evidence hierarchy ranking measured/cited data above general web
material assumes the citation itself is sound.

**Lotfi, S., Janda, M., Reboun, J. & Blecha, T., "Comparative analysis of printed electronics
technologies in RF and microwave circuits," *Scientific Reports* 15 (2025), DOI
10.1038/s41598-025-22948-6** — open access via PMC (PMC12606361), retrieved directly. Table 1
lists **"PET foil (Mylar A)," εr = 2.8, thickness 250 µm**, with a qualitative note that this
material shows "notable performance limitations above 10 GHz, primarily due to higher dielectric
losses" — no numeric tanδ and no stated measurement frequency for the εr figure appear in the
retrieved main text (the paper references a Supplementary Table S1 comparing substrates "across
frequencies," which was not accessible in this session). This is a real, peer-reviewed, directly
retrieved εr for PET, consistent with the wider literature's ~2.8–3.4 cluster — but it is
incomplete as a Material-property library entry because it lacks the frequency and tanδ that
`(material, frequency, property)` keying requires.

**A specifically-checked lead that turned out not to help:** an IEEE MTT-S IMS 2016 conference
paper, "Microwave dielectric characterization of flexible plastic films using printed
electronics" (IEEE Xplore document 7501960), is repeatedly cited in secondary web sources as
reporting PET εr and tanδ from 50 MHz to 20 GHz — exactly the band this project wants. It is
paywalled; IEEE Xplore, the ResearchGate mirror, and the Springer-hosted "Inkjet-printed antenna
on thin PET substrate" follow-on paper (DOI 10.1007/s00542-016-3113-y, which explicitly says it
re-uses a microstrip-resonator PET characterization at UHF band) were all attempted and all
blocked (403/redirect-to-login) in this session. **Their existence and topical fit are confirmed;
their actual numbers are not** — flagged as `STRANDED` rather than fabricated from the secondary
paraphrase.

---

## 3. Generic polymer — the weakest fit, because the best data is for the wrong kind of material

**Obrzut, J., Chiang, C.K., Popielarz, R. & Nozaki, R., "Evaluation of Dielectric Properties of
Polymer Thin-Film Materials for Application in Embedded Capacitance," NIST NISTIR 6537
(September 2000)** — a NIST internal report, freely available, retrieved and read directly in
this session (full 49-page PDF).

Five thin polymer films (one FR4 reference plus four ceramic-loaded "polymer composites," labelled
Film A–E) were measured on custom low-frequency (ASTM D-150, 200 Hz–1 MHz) and high-frequency
(microstrip resonator + time-domain reflectometry, up to 8 GHz) test vehicles, with stated
measurement uncertainty (5% low-frequency, 2–8% high-frequency). Selected high-frequency rows:

| Film | Thickness | εr range (GHz band) | tanδ range (GHz band) |
|---|---|---|---|
| B | 50 µm | 3.93 → 3.79 (0.46–4.2 GHz) | 0.024 → 0.015 |
| D ("high-k polyimide") | 41 µm | 12.5 → 11.6 (0.2 kHz–6 GHz) | 0.01 → ~0.011 (non-monotonic, dips to 0.002 near 1 MHz) |
| E | 100 µm | 39.2 → 36.0 (0.2 kHz–7.9 GHz) | 0.008 → 0.010 |

**Why this is the weakest citation of the three:** every one of these films is explicitly a
"polymer composite containing high dielectric constant ferroelectric powders" (the report's own
Chapter 2) — built for embedded decoupling capacitors, a deliberately high-permittivity,
filler-loaded material, not the neat, low-loss, unfilled polymer sheet ("generic polymer") this
project's Family fallback bracket concept actually needs as a default when no specific-material
entry exists. Citing Film B's εr = 3.9 as "generic polymer" would be defensible only loosely (it is
the lowest-εr, least-filled film in the set, and its value happens to sit close to PET/PI's
unfilled range) — the honest statement is that this source characterizes a *family of loaded
composites spanning εr 3.8–39*, useful for bounding what a "generic polymer" family-fallback range
could look like at the high end, but it does not measure a single representative unfilled
material the way the Kapton and PET sources above do.

**A supplementary, higher-frequency data point:** Miriya Thanthrige, Barowski, Rolfes, Erni,
Kaiser & Sezgin, "Characterization of Dielectric Materials by Sparse Signal Processing with
Iterative Dictionary Updates," arXiv:2006.09093 (2020; retrieved directly) — measures **PMMA
(acrylic), PVC, and PTFE (Teflon)**, genuinely neat, unfilled, off-the-shelf polymers, and cross-
checks its own VNA-based free-space measurement against prior literature (its own Table II):
PMMA εr 2.58–2.61, PVC εr 2.738–2.89, PTFE εr 2.02–2.04. This is a clean, citable "generic
polymer" family range — but the measurement band is **75–330 GHz**, well outside this project's
1–20 GHz target, so it bounds the right kind of material at the wrong frequency, the mirror-image
problem to the NISTIR 6537 result above.

**No single source found in this research measures an unfilled, generic/commodity polymer sheet
in the 1–20 GHz band with both εr and tanδ reported and a citable method.** State this plainly
rather than splicing the two partial sources above into a synthetic number: if the Material-property
library needs a "generic polymer" family-fallback entry today, the two real options are (a) use
PET's own measured/compiled values (§2) as the stand-in, since PET *is* a generic, uncrosslinked
thermoplastic and already has a `LITERATURE-SUPPORTED` entry candidate, or (b) leave the family
fallback bracket unpopulated and say so, rather than construct a number from a ceramic-loaded
composite (NISTIR 6537) or a right-material-wrong-band source (arXiv:2006.09093).

---

## What could not be verified

1. **The IEEE MTT-S IMS 2016 paper's actual PET εr/tanδ table** (document 7501960) — topically
   the best-fitting single source found (PET, 50 MHz–20 GHz, vendor-data comparison), but paywalled
   at IEEE Xplore, ResearchGate, and its Springer follow-on; blocked in every access attempt this
   session. Its existence, title, and topical scope are confirmed via search-engine-indexed
   abstracts; its numbers are not.
2. **Whether Betancourt & Castán's anomalously low PET εr (1.14) is a known, documented artifact
   of the ring-resonator extraction formula at this thickness-to-radius ratio**, or an
   uncorrected error specific to this paper — no follow-up critique, erratum, or citing paper
   discussing this discrepancy was located in this session.
3. **Lotfi et al. 2025's Supplementary Table S1**, which the retrieved main text says compares
   substrate εr/tanδ "across frequencies" — not accessible via the PMC full-text fetch in this
   session; could contain a complete PET (and possibly polyimide) frequency-swept entry that would
   resolve gap #1 above.
4. **NISTIR 6537's exact base resin identity for Films B, C and E** — the report calls them
   "polymer composite" without naming the matrix polymer (epoxy is implied by the glass-transition
   behavior described, by analogy to the FR4 reference film, but never stated outright).

---

## Sources

Retrieved and read directly in this session:
1. [Harris, Sieth, Lau, Church, Samoska & Cleary, "Note: Cryogenic microstripline-on-Kapton microwave interconnects," arXiv:1206.1461](https://arxiv.org/abs/1206.1461) — Kapton εr/tanδ, 0.05–20 GHz, 297 K and 77 K.
2. [Betancourt & Castán, "Printed Antenna on Flexible Low-Cost PET Substrate for UHF Applications," PIER C 38:129–140 (2013)](https://www.jpier.org/issues/volume.html?paper=13012507) — PET ring-resonator εr/tanδ, 2.33–4.74 GHz.
3. [Lotfi, Janda, Reboun & Blecha, "Comparative analysis of printed electronics technologies in RF and microwave circuits," Scientific Reports (2025), DOI 10.1038/s41598-025-22948-6](https://pmc.ncbi.nlm.nih.gov/articles/PMC12606361/) — PET (Mylar A) εr = 2.8, 250 µm.
4. [Obrzut, Chiang, Popielarz & Nozaki, "Evaluation of Dielectric Properties of Polymer Thin-Film Materials for Application in Embedded Capacitance," NIST NISTIR 6537 (2000)](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=851756) — 5 polymer-composite films, 200 Hz–8 GHz.
5. [Miriya Thanthrige, Barowski, Rolfes, Erni, Kaiser & Sezgin, "Characterization of Dielectric Materials by Sparse Signal Processing with Iterative Dictionary Updates," arXiv:2006.09093](https://arxiv.org/abs/2006.09093) — PMMA/PVC/PTFE εr, 75–330 GHz.
6. [Olariu, Hamciuc, Neacsu, Hamciuc & Dimitrov, "Microwave Dielectric Properties of Polyimide Composites Based on TiO2 Nanotubes and Carbon Nanotubes," Digest J. Nanomaterials and Biostructures 14(1):37–44 (2019)](https://chalcogen.ro/37_OlariuMA.pdf) — read in full; not used as a primary citation because all samples are CNT/TiO2-loaded EMI-shielding composites, not a plain polyimide/Kapton film (noted for completeness, not cited above).
7. [Wang & Tretyakov, "Fast and Robust Characterization of Dielectric Slabs Using Rectangular Waveguides," arXiv:2109.00638](https://arxiv.org/abs/2109.00638) — read in full; contains no PET/polyimide/generic-polymer data (checked and ruled out).

Confirmed to exist and topically relevant, but content not accessible (paywalled or blocked) in this session:
8. "Microwave dielectric characterization of flexible plastic films using printed electronics," IEEE MTT-S IMS 2016, IEEE Xplore document [7501960](https://ieeexplore.ieee.org/document/7501960/) — PET/PEN/plastic-film εr/tanδ, 50 MHz–20 GHz; blocked at IEEE Xplore and ResearchGate.
9. Follow-on work by the same measurement approach, "Inkjet-printed antenna on thin PET substrate for dual band Wi-Fi communications," *Microsystem Technologies*, DOI [10.1007/s00542-016-3113-y](https://doi.org/10.1007/s00542-016-3113-y) — blocked by Springer login redirect.
10. Givot, Gregory, Salski, Zentis, Pettit, Karpisz & Kopyt, "A comparison of measurements of the permittivity and loss angle of polymers in the frequency range 10 GHz to 90 GHz," EuCAP 2021 — checked and **ruled out**: covers PMMA, polycarbonate, THV fluoropolymer, and PTFE, not PET, despite an initial search-summary error suggesting otherwise.

Local research corpus (`F:\data\arxiv-chunks\`, mandatory first step per this repo's global instructions):
11. Ripgrep searches for `kapton`, `polyimide`, `PET film` — zero matches across all three terms; `permittivity` alone returns 453 files, confirming the search itself is functional and the null result is a genuine coverage gap, not a tooling failure.
