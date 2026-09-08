# Do the Inventors of US12089385B2 Publish Example 3 Anywhere Else?

**Research date:** 2026-09-03
**Ticket:** [#116](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/116), child of the wayfinder map [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104)
**Question:** US12089385B2's Example 3 — the X-band absorber that [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104)
uses as its blind fixed test goal — leaves two things ambiguous: whether `h₁` = 0.15 mm is a
metal layer or a second dielectric, and whether FIG. 7G's y-axis carries field magnitudes or
powers. Army Research Laboratory people publish heavily. **Is there a paper, conference
paper, technical report or thesis by Zaghloul, Nguyen or Adler that says outright?**

Provenance tags throughout are `CONTEXT.md`'s ladder — `MEASURED` → `SIMULATED` →
`CALCULATED` → `MANUFACTURER-SPECIFIED` → `LITERATURE-SUPPORTED` → `INFERRED` →
`ASSUMED` → `UNKNOWN`. No parallel scale is introduced.

---

## Bottom line up front

1. **No such publication exists in the open literature, and the search was thorough enough
   to say so with confidence rather than as a shrug.** Twenty-two publications by these
   three inventors were found and verified against primary bibliographic records. **None of
   them is about the Example 3 absorber, or about any absorber at all.** The strongest
   single piece of evidence is negative and comes from the patent itself: US12089385B2's
   "Other References" section lists **seven of the inventors' own prior papers** — the
   applicant's own statement of which of their publications this invention builds on — and
   every one of the seven is about *high-permeability metamaterial inserts*, *impedance
   matching*, or *dielectric gratings*. Not one is about absorption. §2 lists all seven.

2. **Neither ambiguity was resolved by a publication. Both were resolved anyway, from the
   patent's own drawings, by measuring them.** This document does not stop at "nothing
   found". The patent PDF's drawing sheets were rendered at high magnification and analysed
   numerically, and both questions now have answers with an audit trail:

   - **`h₁` = 0.15 mm is a CONDUCTOR, on *both* faces, not a second dielectric.** FIG. 7D
     is drawn as three layers — thin / thick / thin — and the `h₁` arrow brackets the top
     thin one *exactly*. Measured layer proportions are 16.3 % / 70.1 % / 13.7 %, which
     matches a 0.15 / 0.72 / 0.15 mm stack (14.7 / 70.6 / 14.7 %) to within half a
     percentage point and matches the "second dielectric" reading not at all. **`INFERRED`**
     — see §5 for the numbers.
   - **The consequence: the patent's own stated total thickness of 0.87 mm is wrong.** The
     drawing scales to **1.02 mm** = 0.72 + 2 × 0.15. The "0.72 + 0.15 = 0.87" arithmetic
     that the ticket flags is real but is a *slip in the prose* — it counts the metal once
     and forgets the metal on the underside, which FIG. 7C plainly shows is there.
   - **FIG. 7G's y-axis is mixed, and the mix is the standard sloppy one.** The Reflectance
     and Transmission traces are **field magnitudes** (|S₁₁| and |S₂₁|, linear, 0–1). The
     Absorbance trace is a **power** — A = 1 − |S₁₁|² − |S₂₁|². Reading the whole axis as
     power makes absorbance come out **negative** at three separate frequencies, which is
     physically impossible. **`INFERRED`** — see §6.

3. **The good news for the reproduction: getting `h₁` right matters much less than the
   ticket feared, *because* it is metal.** Radio waves only penetrate the top ~0.66 µm of
   copper at 10 GHz (the "skin depth"). At 0.15 mm the metal is 227 skin depths thick; at a
   normal 1 oz etched foil (35 µm) it is 53. Anything past about three skin depths behaves
   identically as far as the wave is concerned, so **0.15 mm and 35 µm of copper are
   electromagnetically the same surface.** The residual difference is purely geometric — the
   top resonator sits 0.115 mm higher, and its edge capacitance changes slightly. Had `h₁`
   been a *dielectric*, it would have thickened the spacer by 21 % (0.72 → 0.87 mm) and moved
   the resonance materially. **The expensive reading is the one that is wrong.**

4. **A bonus for the map's "not yet specified" list.** While cataloguing the inventors' work,
   two 2020–2021 papers turned up that publish **Example 7's element** — the circular
   inter-digitated self-phased cell — under its own name, with dimensions and phase curves.
   [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104) lists "how
   the other six patent examples get charted" as unspecified; for Example 7 there is now a
   published, citable source that is *not* the patent. See §4.

---

## 1. What was searched, and what came back empty

| Source | Result |
|---|---|
| **The patent's own "Other References" list** (via [FreePatentsOnline's full text of US12089385](https://www.freepatentsonline.com/12089385.html), which unlike Google Patents exposes the References Cited section as text) | **The single most productive source.** Seven inventor self-citations — see §2. Also 11 third-party citations, three of which are the absorber prior art Example 3 is built on. |
| **Google Scholar profile for Amir Zaghloul** ([citations?user=I4qqYesAAAAJ](https://scholar.google.com/citations?user=I4qqYesAAAAJ&hl=en)) | Full profile retrieved, ~95 items 2016–2025. The patent itself appears (2024). **No paper on skins, absorbers, or absorption.** |
| **Google Scholar full-text search**, `Zaghloul Nguyen "electromagnetic skin" metamaterial` | One result, unrelated (a 2017 consumer-electronics chapter using "skin" in "skin depth"). |
| **Crossref REST API** — author sweep on `Zaghloul` plus targeted title lookups | 153 distinct records surfaced; every genuine Amir I. Zaghloul RF record catalogued in §2–§4. **No absorber, no skin.** All 22 inventor works cited here were verified against Crossref, not recalled. |
| **Crossref, DOI prefix `10.21236`** — the prefix DTIC registers ARL technical reports under | Only **three** genuine Amir I. Zaghloul technical reports exist there, all 2013–2015 and all about antennas/CNT/EBG: [ADA574004](https://doi.org/10.21236/ada574004), [ADA608694](https://doi.org/10.21236/ada608694), [ADA608706](https://doi.org/10.21236/ada608706). **No ARL-TR on skins or absorbers.** |
| **arXiv API**, author and keyword queries | Zaghloul's arXiv presence is entirely the Hodge/Mishra communications-metasurface line (2019–2023). Nothing on absorbers or skins. |
| **DEVCOM ARL technical-reports index** ([arl.devcom.army.mil/arlreports](https://arl.devcom.army.mil/arlreports/)) | Covers 2024 onward only — the page states *"Starting in FY27, Technical Publishing will begin adding pre-2024 publications to the repository."* Zaghloul, Nguyen and Adler do not appear. |
| **Virginia Tech VTechWorks** (Zaghloul holds a joint VT appointment) | One item: a **2014** seminar, *"Metamaterials, Metasurfaces, and Nanotechnology, and their Applications to Antennas, Sensors, and Cognitive Radar"* ([item 76d535bb](https://vtechworks.lib.vt.edu/items/76d535bb-c9b7-4198-b19d-7b7ece9bf007)). Slides retrieved and read in full: six years before the patent filing, and about negative-index media, EBG surfaces and carbon nanotubes. **No absorber content.** |

### Stranded — checked, but the source would not open

| Source | What happened |
|---|---|
| **DTIC Public Search** (`discover.dtic.mil`) | **The service is down.** Verbatim: *"DTIC Public Search is offline while we enhance the capability. It will be back online soon."* Individual `apps.dtic.mil/sti/pdfs/AD*.pdf` documents still resolve if you already know the accession number, but there is no way to search by author right now. **This is the single biggest gap in this document** — an unpublished ARL technical report on the skin would live exactly there. The Crossref `10.21236` sweep is a partial substitute (DTIC registers DOIs for ARL reports) and it came back empty, but it is not a complete index. |
| **IEEE Xplore** | 403 to automated fetches, as the ticket predicted. Every IEEE item below is therefore cited from its **Crossref record** (title, authors, venue, date, DOI verified) — **abstracts and full texts were not read**. Six of the seven self-citations are IEEE/URSI conference papers, so their *contents* are `UNKNOWN`; only their existence and subject matter (from the title) are established. |
| **ResearchGate** profiles for [Zaghloul](https://www.researchgate.net/profile/Amir-Zaghloul) and [Quang Nguyen](https://www.researchgate.net/profile/Quang-Nguyen-93) | Appear in search results but block automated fetching. Nguyen's profile is summarised in search snippets as 22 publications / 65 citations — consistent with, and no larger than, what Crossref and Scholar already gave. |
| **Justia patents inventor page** | 403. Patent family checked directly on Google Patents instead — see §3. |
| **Tri-Service Metamaterial Review 2016** proceedings | Self-citation #2 below was an *invited talk* at this DoD workshop (BRICC, Arlington VA, 7–9 Nov 2016). **No public proceedings exist.** This is the only one of the seven with no retrievable record, and its title — "…Flexible Metamaterial Structures with Very Small Thickness" — is the closest in spirit to the patent of anything the inventors wrote. It is still a *permeability* paper by its title, not an absorber paper. |

---

## 2. The seven publications the inventors themselves cite in the patent

These are not a search result — they are the **applicant's own declaration**, in the patent's
References Cited, of which of their prior publications this invention rests on. If any paper
were going to describe Example 3, it would be one of these. None does.

| # | Citation | Covers Example 3? | Full dimensions + unambiguous stack? | Absorption curve with labelled y-axis? |
|---|---|---|---|---|
| 1 | Q. M. Nguyen, A. I. Zaghloul, T. K. Anthony, S. J. Weiss, "Using Multiple Resonances to Widen the Band for High-Permeability Spiral-Pair Metamaterials," *IEEE Antennas Wireless Propag. Lett.* **18**(5), May 2019. [DOI 10.1109/LAWP.2019.2908148](https://doi.org/10.1109/LAWP.2019.2908148) | **No** — spiral-pair magnetic metamaterial (Example 1/2 territory) | Not read (IEEE 403) | **No** — this is a permeability paper |
| 2 | A. I. Zaghloul, Q. Nguyen, S. J. Weiss, "Study on High Permeability Flexible Metamaterial Structures with Very Small Thickness," *Tri-Service Metamaterial Review* (invited), Arlington VA, Nov 2016. | **No** (by title) | **Unobtainable** — no public proceedings | **Unobtainable** |
| 3 | Q. Nguyen, A. I. Zaghloul, S. J. Weiss, "Wide-Band High Permeability Metamaterials," *IEEE Int. Symp. Antennas Propag.*, San Diego, Jul 2017. [DOI 10.1109/APUSNCURSINRSM.2017.8073024](https://doi.org/10.1109/APUSNCURSINRSM.2017.8073024) | **No** | Not read (IEEE 403) | **No** |
| 4 | Q. Nguyen, A. I. Zaghloul, M. J. Mencagli, N. Engheta, "The Constitutive Effective Parameters of Two-Dimensional Multilayered Dielectric Grating Slab," *ACES Symp.*, Denver, Mar 2018. [DOI 10.23919/ROPACES.2018.8364135](https://doi.org/10.23919/ROPACES.2018.8364135) | **No** — dielectric grating homogenisation | Not read | **No** |
| 5 | A. I. Zaghloul, Q. Nguyen, T. K. Anthony, S. J. Weiss, **E. D. Adler**, "Towards Experimental Verification of Permeability Upgrading Using Metamaterial Inserts," *URSI AT-RASC*, Gran Canaria, May 2018. [DOI 10.23919/URSI-AT-RASC.2018.8471318](https://doi.org/10.23919/URSI-AT-RASC.2018.8471318) | **No** — one of only two Adler-coauthored papers, and it is about permeability | Not read | **No** |
| 6 | Q. Nguyen, A. I. Zaghloul, "Impedance Matching Metamaterials Composed of ELC and NB-SRR," *IEEE Int. Symp. Antennas Propag.*, Boston, Jul 2018. [DOI 10.1109/APUSNCURSINRSM.2018.8609151](https://doi.org/10.1109/APUSNCURSINRSM.2018.8609151) | **Adjacent** — the ELC (electric-LC) resonator is the family the patent names as an alternative to Example 3's I-shape ERR, but this paper is about impedance matching, not absorption | Not read | **No** |
| 7 | A. I. Zaghloul, Q. Nguyen, T. K. Anthony, S. J. Weiss, **E. D. Adler**, "First-Principle versus NRW Retrieval of Metamaterial-Insert Constitutive Parameters Using Measured Scattering Matrix," *IEEE Int. Symp. Antennas Propag.*, Boston, Jul 2018. [DOI 10.1109/APUSNCURSINRSM.2018.8608192](https://doi.org/10.1109/APUSNCURSINRSM.2018.8608192) | **No** — parameter-retrieval methodology | Not read | **No** |

**In plain terms:** the applicant was asked "what did you publish that led to this?" and named
seven papers about making materials look more *magnetic* than they are, and about how to work
backwards from measured S-parameters to a material's effective properties. The absorber is not
in that lineage. **Eric Adler — the third inventor — appears on exactly two publications in the
entire corpus, #5 and #7, and both are permeability/retrieval papers.**

### What the patent cites *instead* for Example 3

Where the patent needed a citation for the absorber, it reached for **third-party** work, which
is itself informative about where Example 3's design came from:

> **CORRECTED 2026-09-08 (#246). The author lists previously given here were wrong, and the
> label claiming they came from the patent was wrong twice over.** The patent prints only
> *"Gu et al."*, *"Ghosh et al."* and *"Singh et al."* — **no author lists at all**, at either
> `knowledge/corpus/us_patent_12089385B2.txt` line 83 (References Cited) or line 1022 (the
> citing sentence). So names described here as "cited verbatim from the patent" could not have
> come from it. Two of the three were wholly wrong and the third had one name substituted.
> Now taken from Crossref's publisher-deposited metadata (`LITERATURE-SUPPORTED`):
>
> | | Previously recorded here | Actual |
> |---|---|---|
> | Gu | ~~Gu, Chen, Zhang, Xu, Ma, Wang, Zhang & Zhao~~ | **Gu, Barrett, Hand, Popa & Cummer** |
> | Ghosh | ~~…Chaurasiya…~~ | **…Kaiprath…** (other three correct) |
> | Singh | ~~Singh, Tyler, Zhang, Azad & Chen~~ | **Singh, Korolev, Afsar & Sonkusale** |

- **Gu, Barrett, Hand, Popa & Cummer**, "A broadband low-reflection metamaterial absorber,"
  *J. Appl. Phys.* **108**(6), 064913 (2010). DOI [10.1063/1.3485808](https://doi.org/10.1063/1.3485808).
  **Duke University, Dept. of Electrical and Computer Engineering and Center for Metamaterials
  and Integrated Plasmonics** — Landy's own department.
- **Ghosh, Bhattacharyya, Kaiprath & Srivastava**, "Bandwidth-enhanced polarization-insensitive
  microwave metamaterial absorber and its equivalent circuit model," *J. Appl. Phys.* **115**(10),
  104503 (2014). DOI [10.1063/1.4868577](https://doi.org/10.1063/1.4868577). IIT Kanpur.
- **Singh, Korolev, Afsar & Sonkusale**, "Single and dual band 77/95/110 GHz metamaterial
  absorbers on flexible polyimide substrate," *Appl. Phys. Lett.* **99**(26), 264101 (2011).
  DOI [10.1063/1.3672100](https://doi.org/10.1063/1.3672100). Tufts University.

Titles, journals, volumes, issues, pages and years are as printed in the patent and all three
check out exactly against Crossref; only the author lists were wrong, and those the patent never
gave. `LITERATURE-SUPPORTED` (Crossref publisher metadata, fetched 2026-09-08). All three are conventional
electric-resonator-plus-backing absorbers, and all three are the topology Example 3 uses. ~~**If the reproduction wants a labelled-axis absorption curve from a source that actually
explains its conventions, these are the papers to read — not the inventors'.**~~ **They have now
been read (#246), and the answer is no** — see `docs/example3-cited-absorber-papers.md`. None is
FIG. 7G's source, and the citing sentence turns out to attach them to *other embodiments the
patent did not build*, not to Example 3's provenance.

---

## 3. What the patent's own record adds

- **Application 17/123,902, filed 2020-12-16, granted 2024-09-10.** Priority date equals the
  filing date: **there is no provisional application, no parent, and no continuation.** The only
  other version of this document is the pre-grant publication **US20220192066A1** (16 Jun 2022),
  which is the same specification. So there is no sibling patent carrying more detail on
  Example 3 — a route worth eliminating, and now eliminated.
- **Attorney/agent: "U S ARMY RESEARCH LABORATORY."** Prosecuted in-house, not by outside
  counsel. Relevant only as a small explanation for the prose/drawing inconsistency found in
  §5: in-house patent drafting with no dedicated draftsman is where "add up the layer
  thicknesses" mistakes come from.
- **Nothing in the patent's prose ever states a conductor thickness, a conductor conductivity,
  or a y-axis convention.** The prose says only that inserts 752E₁ and 752E₂ "may be formed of a
  conductive metal, such as copper or gold" and are "attached to the top and bottom surfaces of
  the pliable thin film 751" (one film, metal on both faces). It calls FIG. 7G "a plot showing
  simulated scattering performance" and asserts "complete absorption, along with no reflection
  and no transmission." That is the whole of it.

---

## 4. The rest of the inventors' corpus — and what it *does* cover

Fifteen further inventor publications were catalogued (all DOIs verified via Crossref). None
covers Example 3, but the pattern is worth recording because it tells the map where the
*other* examples' published data lives.

**Examples 1 and 2 (dielectric-resonator metamaterials, permeability/permittivity upgrading)
are the group's main published line:**

- Q. M. Nguyen, T. K. Anthony, A. I. Zaghloul, "Free-Space-Impedance-Matched Composite
  Dielectric Metamaterial With High Refractive Index," *IEEE Antennas Wireless Propag. Lett.*
  **18**(12), Dec 2019. [DOI 10.1109/LAWP.2019.2951122](https://doi.org/10.1109/LAWP.2019.2951122)
  — **this is Example 2's objective stated as a paper title.**
- Q. Nguyen, A. I. Zaghloul, "Analytical Verification of Effective Constitutive Parameter
  Increasing Using Metamaterial Inserts," *URSI EMTS*, 2019. [DOI 10.23919/URSI-EMTS.2019.8931555](https://doi.org/10.23919/URSI-EMTS.2019.8931555)
- Q. Nguyen, A. I. Zaghloul, T. K. Anthony, "Design of Wideband Compact Electric-Inductive-
  Capacitive (ELC) Inclusions for Metamaterials," *URSI Radio Science Letters* **1**, 2019.
- Q. Nguyen, S. Liu, A. I. Zaghloul, "Extension of Snoek's Law to Higher RF Frequencies by
  Controlling Nanomagnetic Particle Parameters," *URSI EMTS*, 2019. [DOI 10.23919/URSI-EMTS.2019.8931482](https://doi.org/10.23919/URSI-EMTS.2019.8931482)
- Q. Nguyen, A. I. Zaghloul, "Susceptibility of Nanoparticles Studied by Landau-Lifshitz-Gilbert
  and Snoek's Equations," *IEEE APS*, 2019. [DOI 10.1109/APUSNCURSINRSM.2019.8888631](https://doi.org/10.1109/APUSNCURSINRSM.2019.8888631)
- Q. Nguyen, K. V. Mishra, A. I. Zaghloul, "Retrieval of Polarizability Matrix for
  Metamaterials," *IEEE COMCAS*, 2019. [DOI 10.1109/COMCAS44984.2019.8958421](https://doi.org/10.1109/COMCAS44984.2019.8958421)
- Q. Nguyen, M. Burnett, A. I. Zaghloul, M. J. Mencagli, N. Engheta, "Impedance-matched
  high-index ceramic microwave metamaterials at X-band," *ACES Symp.*, 2019.
- K. M. Price, M. M. Masaki, Q. M. Nguyen, J. M. Therrien, A. I. Zaghloul, "Tailoring
  Fe₈₀Co₂₀ Composite Material for High Permeability at High RF Frequency for Antenna
  Applications," *EuCAP*, Mar 2020. [DOI 10.23919/EUCAP48036.2020.9135523](https://doi.org/10.23919/EUCAP48036.2020.9135523)

**Examples 4 and 5 (self-phased reflective cells, phase-vs-parameter lookups):**

- Q. Nguyen, A. I. Zaghloul, "Design of Beam Steering Patch Arrays Using Self-Phased Metasurface
  Pixels," *IEEE APS*, 2020. [DOI 10.1109/IEEECONF35879.2020.9329451](https://doi.org/10.1109/IEEECONF35879.2020.9329451)
- Q. Nguyen, A. I. Zaghloul, "Concept of a Self-Phased Metasurface Pixel/Cell in Non-Reflective
  Mode," *IEEE APS*, 2020. [DOI 10.1109/IEEECONF35879.2020.9329919](https://doi.org/10.1109/IEEECONF35879.2020.9329919)
- Q. M. Nguyen, J. A. Hodge, A. I. Zaghloul, "Self-Phased Metasurface Pixels/Cells: Concept,
  Design and Applications," *URSI GASS*, 2021. [DOI 10.23919/URSIGASS51995.2021.9560456](https://doi.org/10.23919/URSIGASS51995.2021.9560456)

**Example 7 (circular inter-digitated ring pair, checkerboard scattering reduction) — the useful
find:**

- Q. M. Nguyen, J. A. Hodge, A. I. Zaghloul, "Circular Inter-Digitated Design for Self-Phased
  Reflective Pixel/Cell for Metasurfaces and Reflectarrays," *URSI GASS*, Aug 2020.
  [DOI 10.23919/URSIGASS49373.2020.9232414](https://doi.org/10.23919/URSIGASS49373.2020.9232414)
- J. A. Hodge, Q. M. Nguyen, A. I. Zaghloul, "Reflective Beam Steering of Metasurface Using
  Circular Inter-Digitated Self-Phased Pixels/Cells," *URSI GASS*, Aug 2020.
  [DOI 10.23919/URSIGASS49373.2020.9232014](https://doi.org/10.23919/URSIGASS49373.2020.9232014)
- **Q. M. Nguyen, J. A. Hodge, T. K. Anthony, A. I. Zaghloul, "Scattering Reduction Metasurfaces
  Using Circular Inter-Digitated Self-Phased Elements," *IEEE APS*, Dec 2021.
  [DOI 10.1109/APS/URSI47566.2021.9703772](https://doi.org/10.1109/APS/URSI47566.2021.9703772)**
  — *scattering reduction* is Example 7's function, and the *circular inter-digitated element*
  is Example 7's element. This is Example 7, published under its own name, in the year after the
  patent was filed.

**Also noted:** Q. M. Nguyen, A. I. Zaghloul, "Design Concept for Multiple-Band Multi-functional
Metasurfaces with Hybrid Feeding," *URSI AT-AP-RASC*, 2022.
[DOI 10.23919/AT-AP-RASC54737.2022.9814260](https://doi.org/10.23919/AT-AP-RASC54737.2022.9814260)

**Nothing whatsoever on Examples 3 and 6.** The absorber and the polarisation converter are the
two the group never wrote up. That is not proof they never did — but it is what the open record
shows after checking Scholar, Crossref, arXiv, DTIC's DOI prefix, the ARL report index and the
patent's own citation list.

> **A caution about these titles.** Only titles, authors, venues, dates and DOIs are verified
> here. The IEEE 403 means **none of these papers' contents were read**. The Example 7 claim
> above is an `INFERRED` match from title and element name, not a confirmed one. Someone with
> IEEE access should open the 2021 paper before the map relies on it.

---

## 5. Resolving `h₁` from the drawing — conductor, on both faces

No publication answers this, so the patent's own drawing was measured. Method: the Google
Patents PDF ([US12089385.pdf](https://patentimages.storage.googleapis.com/f5/d9/73/7d2e4472adfcb1/US12089385.pdf))
has **no text layer**, so sheet 11 (FIG. 7A–7D) was rendered to greyscale raster at 12×
magnification with PyMuPDF, thresholded at grey < 128, and the ink density of each pixel row
across the slab's interior was profiled and smoothed over a 24-pixel window (two halftone
periods, so the printer's dot pattern averages out and only real strata survive).

**What the profile shows.** FIG. 7D's "Left view" is not a uniform block. It has **three
strata** — a thin lightly-hatched band, a thick densely-hatched body, and a thin lightly-hatched
band. Boundaries, taken at the 50 % crossing points:

| Boundary | Row (px) |
|---|---|
| Slab top edge | 883 |
| Top thin band → dense core | 939 |
| Dense core → bottom thin band | 1180 |
| Slab bottom edge | 1227 |

| Stratum | Thickness (px) | Fraction of total |
|---|---|---|
| Top thin band | 56 | 16.3 % |
| Dense core | 241 | **70.1 %** |
| Bottom thin band | 47 | 13.7 % |
| **Total** | **344** | 100 % |

**And the `h₁` arrow brackets the top thin band exactly.** All ink in the 38-pixel-wide column
immediately to the right of the slab — the `h₁` leader arrow plus its label glyph — falls
between rows **882 and 944**. The top band runs 883 → 939. The arrow is measuring that band and
nothing else.

**Testing the two readings against the measured fractions:**

| Reading | Predicted fractions | Core fraction error |
|---|---|---|
| **`h₁` is metal on both faces**: 0.15 / 0.72 / 0.15 mm, total 1.02 mm | 14.7 % / **70.6 %** / 14.7 % | **0.5 pt** ✅ |
| **`h₁` is a second dielectric**: 0.72 + 0.15 mm, total 0.87 mm, two strata only | 82.8 % / 17.2 %, no third stratum | fails outright — the drawing has three strata, not two |
| **Total really is 0.87 mm** with a 0.72 mm core and thinner metal | core would be **82.8 %** | **12.7 pt** ❌ |

Setting the scale from the core (241 px = 0.72 mm → 335 px/mm) gives a top band of **0.167 mm**,
a bottom band of **0.140 mm** and a total of **1.028 mm** — against a predicted 0.15 / 0.15 /
1.02 mm. Agreement to better than 1 % on the total.

### Conclusion on `h₁`

**`h₁` = 0.15 mm is the CONDUCTOR thickness, and it applies to both faces.** `INFERRED` —
inferred from a quantitative reading of FIG. 7D, not stated anywhere in the patent or in any
publication.

Three things follow:

1. **The dielectric is 0.72 mm, not 0.87 mm.** The FR4 spacer between the I-shape electric ring
   resonator on top and the rectangular wire resonator underneath is `h` = 0.72 mm. That is the
   number the reproduction should model. The competing 0.87 mm reading is dead.
2. **The patent's stated total thickness of 0.87 mm is an error.** The drawing scales to 1.02 mm.
   The prose added the metal once and forgot the second layer. Example 3's heading — *"Thin
   (0.87 mm) Surface for Energy Absorbance at RF"* — is therefore wrong by 0.15 mm, and the
   coincidence that made this ambiguous ("0.72 + 0.15 = 0.87 exactly") is the *cause* of the
   error, not evidence for the dielectric reading.
3. **It barely matters for the simulation, which is the point.** Copper's skin depth — how far a
   radio wave gets into the metal before it has died away to 37 % — is
   δ = 1/√(π f μ₀ σ) = **0.66 µm at 10 GHz** for σ = 5.8 × 10⁷ S/m (`CALCULATED`). Plain-language
   version: *the wave only ever sees the top two-thirds of a micron of the metal.* At 0.15 mm the
   conductor is 227 skin depths deep; a 1 oz etched foil (35 µm) is 53. Both are far past the
   ~3 skin depths at which a conductor's surface impedance stops changing, so **the two are
   electromagnetically indistinguishable.** What does change is geometry: the top resonator sits
   0.115 mm further from the wire, and its edge fields change a little. That is a small
   perturbation. A 21 % thicker *dielectric* would not have been.

> **Fabrication note, which cuts the other way from the ticket's instinct.** The ticket says
> 0.15 mm of copper is "not a thickness anyone fabricates a resonator in", and for *etched foil*
> that is correct — it is roughly 6× a 1 oz foil. But this project's process is direct-ink-write
> on a Voltera NOVA, where conductor thickness is built up pass by pass and 0.15 mm is a stack of
> several passes rather than an impossibility. Whether that is worth doing (it is not, given the
> skin-depth argument above — it would waste ink for no RF benefit) is a separate question from
> whether it is *possible*. Cross-check against `docs/voltera-multilayer-capability.md`
> (branch `research/voltera-multilayer`) before the loop assumes a printed thickness.

---

## 6. Resolving FIG. 7G's y-axis — mixed conventions, and the mix is decidable

Again, no publication answers this, so the figure was digitised. Sheet 12 was rendered at 14×,
thresholded at grey < 160, and calibrated from the tick-label centroids: **S = 1 at row 1137.5,
S = 0 at row 3373.5** (2236 px per unit), **8.5 GHz at column 1910, 10.5 GHz at column 5010**.

**The y-axis is labelled with the bare letter "S".** Not "|S|", not "Magnitude", not
"Absorptivity" — just `S`, on a 0-to-1 linear scale, with three traces legended *Reflectance*,
*Transmission* and *Absorbance*. The patent never says what `S` means. That is the whole
ambiguity.

**Readings at three frequencies where the three curves are well separated** (values in units of
the y-axis, whatever it means):

| f (GHz) | Reflectance | Transmission | Absorbance |
|---|---|---|---|
| 8.53 | 0.971 | 0.127 | 0.048 |
| 8.75 | 0.951 | 0.108 | 0.085 |
| 10.47 | 0.986 | 0.085 | 0.025 |

**Test 1 — read the whole axis as power** (so the plotted Reflectance *is* |S₁₁|², already a
power, and absorption is whatever is left over: A = 1 − R − T):

| f (GHz) | 1 − R − T |
|---|---|
| 8.53 | **−0.098** |
| 8.75 | **−0.059** |
| 10.47 | **−0.071** |

**All three are negative.** A surface cannot absorb a negative amount of energy. Even allowing
generous digitisation error — the curve linewidths are 10–40 px, i.e. ±0.005 to ±0.018 in `S` —
the reflectance alone is 0.95–0.99 and the transmission 0.09–0.13, so their sum exceeds 1 by a
margin that no reading error closes. **This convention is impossible.**

**Test 2 — read Reflectance and Transmission as field magnitudes** (|S₁₁| and |S₂₁|), with the
Absorbance trace being the power that is left: A = 1 − |S₁₁|² − |S₂₁|²:

| f (GHz) | 1 − R² − T² | Plotted Absorbance | Residual |
|---|---|---|---|
| 8.53 | 0.0411 | 0.048 | 0.007 |
| 8.75 | 0.0839 | 0.085 | **0.001** |
| 10.47 | 0.0206 | 0.025 | 0.004 |

**Every residual is inside the digitisation error.** The arithmetic closes.

### Conclusion on FIG. 7G

**FIG. 7G mixes two conventions on one axis:**

- The **Reflectance** and **Transmission** traces are **field-magnitude S-parameters** —
  |S₁₁| and |S₂₁|, linear, dimensionless, 0 to 1.
- The **Absorbance** trace is a **power** — A = 1 − |S₁₁|² − |S₂₁|², also 0 to 1.

`INFERRED` — from arithmetic self-consistency across three independent frequencies, not from any
statement in the patent or a publication.

**In plain terms:** two of the three curves say *how big the wave is* coming back and going
through; the third says *what fraction of the energy was eaten*. Those are not the same kind of
number, and the axis label "S" does not warn you. This is a common and well-known sloppiness in
the metamaterial-absorber literature — it is exactly what you get from a MATLAB script that
plots `abs(S11)`, `abs(S21)` and `1-abs(S11).^2-abs(S21).^2` on the same axes — but it is a trap
if a scoring function assumes one convention throughout.

**What this means for the scoring function.** A reproduction that compares its own
`1 − |S₁₁|² − |S₂₁|²` against FIG. 7G's *Absorbance* trace is comparing like with like and is
correct. A reproduction that compares its own |S₁₁| against FIG. 7G's *Reflectance* trace is
also correct. **A reproduction that squares FIG. 7G's Reflectance before comparing, or that
compares its own |S₁₁|² against it, is wrong** — and would be wrong quietly, since both curves
sit in 0–1 and look plausible either way.

### Reading off the target curve

For the record, since this is the curve the reproduction is scored against, from the same
digitisation: **reflectance minimum at ≈ 9.2 GHz**, dipping to |S₁₁| ≈ 0.01–0.02, with
transmission |S₂₁| ≈ 0.09 at that point, giving an absorption peak of ≈ 0.99. The absorption
half-height width is narrow — absorbance is back below 0.1 by ≈ 9.6 GHz and below 0.05 by
≈ 8.6 GHz. **This is a narrowband absorber**, not the 8.5–10.5 GHz broadband absorber the
patent's "band 8.5–10.5 GHz" phrasing might suggest: 8.5–10.5 GHz is the *plotted sweep range*,
not the absorption band. `INFERRED` from the digitised figure; treat as approximate and
re-digitise properly if the score depends on the shoulders.

---

## 7. Numbers these publications give that the patent omits

**Almost none, because the relevant publications do not exist.** Honest answer: the hope behind
this ticket — that an ARL paper would supply the measured-versus-simulated comparison, the
fabrication method, the tolerances and the substrate sourcing that the patent leaves out —
**is not realisable from the open record.** Specifically:

- **Measured vs simulated for Example 3: nothing.** FIG. 7G is labelled "simulated" in the
  patent and there is no publication carrying a measurement. This *confirms* rather than fixes
  the asymmetry [#107](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/107)
  already flagged — Examples 1, 2 and 7 have measured curves in the patent; Example 3 has only a
  simulation, and now we know there is no measurement anywhere else either. **The provenance
  ceiling for Example 3's reference curve is `SIMULATED`, and it cannot be raised by reading.**
- **Fabrication method: nothing** beyond the patent's own generic citation to Kalpakjian &
  Schmid's *Manufacturing Engineering and Technology* (6th ed., 2009, ch. 16 p. 398), which is a
  textbook reference for etching/deposition in general, not a process for this part.
- **Tolerances: nothing.**
- **Substrate sourcing: nothing.** "FR4, εr = 4.8, tanδ = 0.017" is all there is, and the patent
  supplies no vendor, no laminate grade, no measurement frequency for those two numbers. Since
  FR4 is a woven-glass composite whose properties vary by weave and resin and are rarely
  specified at 10 GHz at all, that pair stays `ASSUMED` for X-band until measured — as
  [#107](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/107) already
  recorded.
- **Conductor conductivity: nothing.** "Copper or gold" with no σ. Given §5's skin-depth result,
  σ matters (it sets the surface resistance and hence some of the loss) but the *thickness* no
  longer does.

**What the corpus does supply that the patent omits, for other examples:** the Example 1/2 line
(§4) is a decade of measured permeability and permittivity retrieval work, and the Example 7 line
has three papers. If the map ever needs a non-patent source for those, it now has one. For
Example 3 it does not.

---

## 8. Direct answers to the ticket's questions

> **Were the inventors' publications found?**

**Yes — twenty-two of them, comprehensively, including the seven the applicant itself declared
relevant.** They are listed in §2 and §4 with verified citations and links.

> **Does any of them give Example 3's (or an equivalent absorber's) full dimensions with an
> unambiguous layer stack?**

**No. Not one of the twenty-two is about an absorber.** The group's published output covers the
patent's Examples 1, 2, 4, 5 and 7. Examples 3 and 6 are unpublished.

> **Does any publish a measured or simulated absorption curve with a labelled y-axis?**

**No.**

> **Is `h₁` a conductor or a dielectric?**

**A conductor**, 0.15 mm thick, on **both** faces — not a second dielectric. `INFERRED` from a
quantitative reading of FIG. 7D (§5), *not* from a publication. The dielectric is `h` = 0.72 mm.
The patent's stated 0.87 mm total is an arithmetic slip; the drawing scales to 1.02 mm.

> **What is FIG. 7G's y-axis?**

**Mixed.** Reflectance and Transmission are **field magnitudes** (|S₁₁|, |S₂₁|); Absorbance is a
**power** (1 − |S₁₁|² − |S₂₁|²). `INFERRED` from arithmetic self-consistency at three
frequencies (§6). Reading the whole axis as power gives negative absorbance and is impossible.

---

## 9. What this means for the ticket's decisions

This document supplies evidence, not the decisions — [#116](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/116)
still has to make them. But three of its four bullets are now better informed:

- **"Which reading of `h₁`, and on what basis"** — the conductor reading, on the basis of a
  measured layer-proportion match to within half a percentage point (§5). The basis is a
  drawing, so the value lands at `INFERRED`, not at `patent`-sourced.
- **"Which y-axis convention"** — mixed, decided by the impossibility of the alternative (§6).
  Also `INFERRED`.
- **"Whether a sensitivity check substitutes for certainty"** — the ticket proposed simulating
  both `h₁` readings and seeing which matches the published curve. **That check is now cheaper
  than it looked and probably still worth running, but for a different reason.** It is no longer
  a tie-break between two live hypotheses; it is a *confirmation* that the geometry read off the
  drawing reproduces the drawn curve. If a 0.72 mm-spacer model with metal on both faces lands
  on 9.2 GHz and a 0.87 mm-spacer model does not, that closes the loop with a second,
  independent line of evidence. If *neither* lands on 9.2 GHz, the problem is somewhere else
  entirely — the FR4 constants, the mesh, or the transcribed in-plane dimensions — and finding
  that out early is worth the solve on its own.
- **"What the loop does with a reference value it cannot verify"** — unchanged by this document,
  except that the two values in question are now specifically `INFERRED`, with a written basis
  and a reproducible method, rather than unknown. That is a real upgrade over an unresolved
  ambiguity, and it is still below `LITERATURE-SUPPORTED`. Whether a score computed against an
  `INFERRED` target inherits that rung is [#112](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/112)'s
  to settle.

---

## 10. Limits of this document

- **DTIC Public Search being offline is a genuine hole.** An unpublished ARL technical report on
  the electromagnetic skin is exactly the kind of document that would live there and nowhere
  else. The Crossref `10.21236` sweep is a partial substitute and came back empty, but it does
  not index everything DTIC holds. **This is worth re-running when DTIC's search returns.**
- **No IEEE full text was read.** All twenty-two citations are verified bibliographically
  (Crossref) but their contents are `UNKNOWN`. The judgement that none covers an absorber rests
  on titles, venues and the patent's own framing of its self-citations — strong, but not the
  same as having read them.
- **§5 and §6 are readings of a raster image of a printed drawing.** The method is documented and
  reproducible, and the margins are wide (0.5 pt vs 12.7 pt in §5; a sign error in §6), but they
  remain `INFERRED`. Neither is a statement by the patentee.
- **A patent drawing is not required to be to scale.** §5's argument works because this
  particular drawing *happens* to be to scale — the three strata reproduce a 0.15/0.72/0.15 stack
  to under 1 %. That is evidence, not proof; a draftsman who drew to scale on this figure could
  have drawn freehand on another.
- **§6's absorption-band description (the last paragraph of §6) is a coarse read** taken while
  digitising three calibration points. If the scoring function weights the band shoulders, the
  whole curve should be digitised properly rather than trusted from here.
- **Nothing export-controlled or non-public was sought or used.** Every source cited is openly
  published. The one inventor work with no public record — the 2016 Tri-Service Metamaterial
  Review talk — is noted as unobtainable and was not pursued further.
