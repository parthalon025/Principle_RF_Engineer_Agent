# Verification-corpus candidates: a real microstrip patch antenna case for `tests/fixtures/`

Research findings for the first end-to-end fixture exercising requirement →
`designs/requirement_targets.py` → `rf_tools/calculations.py`'s `patch_*`
functions → `optimization.rf_objectives.optimize_patch_length_for_target_frequency`
→ `rf_tools/touchstone.py` → `rf_tools/correlation.py`, per `CONTEXT.md`'s
"there is no verification corpus yet for the simulator adapters or the
agent's end-to-end behavior."

**Scope note, confirmed with the requester mid-investigation**: this fixture
lives in `tests/fixtures/` and is **never** routed through `ingest_document`
or the knowledge base — it is evaluated purely as test data, not as a
knowledge-base document. Redistributability still applies exactly as
briefed (a `tests/fixtures/` file is still committed into the repo and
still needs real rights to redistribute).

**A hard criterion was added after this investigation was underway** (see
"The 50 µm / characterized-εr criterion" below): published geometry must
resolve to 0.05 mm (two decimal places in mm) or finer, and — because a 50
µm length change moves 2.45 GHz resonance by only ~4 MHz while
datasheet-nominal FR4 (εr = 4.4 ± 0.2) alone contributes ~50+ MHz of
uncertainty — the substrate's εr basis (measured/characterized vs.
datasheet-nominal vs. unstated) had to be checked and reported for every
candidate. This changes the ranking materially and is folded into the
candidate table below, not treated as an afterthought.

## Method

Every claim below was chased to the source that owns it: the repo's own
files (read directly), the installed `scikit-rf` package source and its
GitHub repository (read directly / via GitHub code search), a cloned copy
of one GitHub candidate repo, NCBI PMC's own article page (fetched
directly), and NASA NTRS's own citation pages. Where a primary source
could not be reached, that is stated explicitly rather than papered over —
see "What could not be verified" per candidate.

**MDPI's own site (`mdpi.com`) returned HTTP 403 Forbidden on every fetch
attempt in this session** — the article page, its PDF, and even MDPI's own
`/openaccess` policy page — evidently bot-blocked at the edge (Akamai). No
MDPI article's content could be read directly. Where an MDPI candidate is
discussed below, its license status is corroborated only via Semantic
Scholar/Unpaywall's aggregated metadata (which itself cites MDPI as the
license authority) and third-party summaries of MDPI's general open-access
policy — **not** verified against MDPI's own license statement on the
article page itself. This is flagged as an open unverifiable item, not
glossed over.

## Repo context that shaped the ranking

- `rf_tools/calculations.py`'s `patch_resonant_frequency_hz` and its
  supporting `patch_effective_permittivity`/`patch_length_extension_m`
  take exactly `(eps_r, w_m, h_m, l_m)` — a rectangular patch, Balanis
  transmission-line model. `optimization.rf_objectives.
  optimize_patch_length_for_target_frequency` (per the task brief; not
  independently re-read in this pass) takes the same shape. Any candidate
  that isn't a rectangular patch, or doesn't publish all four numbers,
  cannot drive ANALYSIS/OPTIMIZATION at all.
- `rf_tools/touchstone.py`/`measurement/external.py` consume a real
  `.sNp` file directly (`analyze_touchstone`, reused unmodified by
  `record_external_measurement`). A candidate with only a printed S11-vs-
  frequency plot requires hand-digitizing before it can enter the system
  the way a real lab Touchstone would.
- `rf_tools/correlation.py`'s `correlate_simulation_measurement` needs
  frequency-swept S-parameters on **both** the simulated and measured
  side — a simulation-only case cannot exercise it at all, no matter how
  good its data otherwise is.
- `docs/LICENSE_MATRIX.md` and `README.md`'s licensing section already
  draw the "software license vs. document/data rights" line this task
  asked to preserve; IEEE Xplore is explicitly marked "not ingested" in
  that matrix for the same reason applied here to any paywalled source.

## Ranked candidates

### 1. MDPI *Electronics* 10(12):1447 — "2×2 Textile Rectenna Array with Electromagnetically Coupled Microstrip Patch Antennas in the 2.4 GHz WiFi Band" (Lopez-Garde, Del-Rio-Ruiz, Legarda, Rogier, 2021)

<https://doi.org/10.3390/electronics10121447> · <https://www.mdpi.com/2079-9292/10/12/1447>

- **Rights**: Semantic Scholar's Graph API (queried directly this session)
  reports `openAccessPdf.status = "GOLD"`, `openAccessPdf.license =
  "CCBY"`, sourced from Unpaywall metadata — i.e. a CC-BY 4.0 gold-OA
  article, consistent with MDPI's general "all journal articles are CC BY
  4.0" policy (corroborated only via third-party summaries, since
  `mdpi.com/openaccess` itself 403'd every fetch attempt here). **This is
  a secondary-source confirmation, not a primary-source read of MDPI's own
  license line on the article** — flagged as unverified-at-the-primary-
  source, not stretched into a clean "yes."
- **Criterion 2 (measured + simulated)**: satisfied per the abstract and
  search-indexed content — both simulated and measured S11 stay below
  −10 dB across the 2.4 GHz WiFi band, and simulated/measured gain (8.7 /
  8.2 dBi at 2.45 GHz) are both reported. **Not independently confirmed
  from the article body** (site-blocked); this is the search-engine-
  indexed abstract/summary, treated here as directionally reliable but
  not primary-verified.
- **Criterion 3 (machine-readable data)**: no data-availability statement,
  Zenodo/figshare deposit, or GitHub companion repo was found by search.
  Everything indicates plot-only data; **no evidence found that a
  Touchstone or CSV export exists**.
- **Criterion 4 (geometry)**: could not be read (site-blocked). Unknown
  whether W/L/h/eps_r for the textile patch are even all published.
- **Criterion 5 (stated requirement)**: satisfied at the coarse level —
  "2.4 GHz WiFi band" rectenna is the paper's explicit design target — but
  the exact prose (VSWR/return-loss threshold, bandwidth) could not be
  confirmed.
- **Bonus relevance**: textile substrate, worn on a body — genuinely
  on-domain for this repo's "adaptive EM skin" / conformal-antenna target,
  more so than a rigid FR4 board.
- **The 50 µm / εr criterion**: **fails, almost certainly, even before
  checking the exact printed dimensions.** A textile substrate (felt,
  in this design family) has no standard controlled-dielectric datasheet
  the way Rogers/Taconic laminates do, and this paper's own abstract gives
  no permittivity figure at all in the indexed summary — textile εr is
  characteristically the *least* well-controlled substrate class in this
  entire literature (moisture content, weave tightness, and compression
  all shift it), the opposite of what the criterion needs. Even a
  best-case reading (precise geometry, if it exists) would be swamped by
  an uncharacterized textile εr exactly the way the criterion's own FR4
  example describes.
- **What would have to be filled in by hand**: everything geometric —
  W/L/h and any stated εr — since the article body was unreachable this
  session; plus a Touchstone-format conversion of whatever numeric S11
  values (if any) turn out to be recoverable from the PDF.

### 2. Zenodo dataset (10.5281/zenodo.15866821 / zenodo.org/records/15866865) — "Parametric simulation dataset of a 2.4 GHz patch antenna with slot for AI-based S11 prediction"

Paper: <https://pmc.ncbi.nlm.nih.gov/articles/PMC12830091/> (fetched
directly this session — primary source, not a secondary summary).

- **Rights**: **Confirmed directly from the PMC article page**: *"This is
  an open access article under the CC BY license
  (http://creativecommons.org/licenses/by/4.0/)."* The Zenodo dataset
  itself was not separately fetched to confirm its own license line
  matches the paper's (Zenodo records commonly, but don't always,
  independently restate CC-BY), so that one hop is a residual gap, but
  the license status here is on much firmer ground than candidate 1.
- **Criterion 2 (measured + simulated)**: **fails outright.** The article
  states, verbatim per the direct fetch: *"No experimental measurements
  were involved."* All 55,053 samples are CST Microwave Studio
  simulations. This alone disqualifies it as the fixture's data
  source — `rf_tools/correlation.py` has nothing to correlate against.
- **Criterion 3 (machine-readable data)**: strongest of any candidate here
  — real downloadable CSV/XLS, not a plot to digitize.
- **Criterion 4 (geometry)**: 12 geometric parameters are swept
  (patch/substrate/slot/feed-line dimensions) and recorded per sample in
  mm, but the PMC page's own codebook did not state decimal-place
  precision, and — more importantly — **substrate material/εr was not
  specified at all**: the paper says only that materials were "selected
  according to common dielectric properties used in wearable and IoT
  antenna research," no number, no tolerance, no measurement.
- **Criterion 5 (stated requirement)**: 2.4 GHz core target, 1.8–2.8 GHz
  secondary sweep — present but generic (IoT/wireless), not a specific
  prose customer requirement.
- **The 50 µm / εr criterion**: fails on both counts as reported — no
  stated decimal precision and no εr basis at all (not even
  datasheet-nominal). And it's moot regardless, since criterion 2 already
  disqualifies it from being the correlation fixture.

### 3. `scikit-rf`'s own `ring_slot` example network (`skrf.data.ring_slot`)

Verified directly from the installed package
(`.venv/lib/python3.12/site-packages/skrf/data/`) and from
`scikit-rf/scikit-rf`'s own GitHub source (`skrf/data/__init__.py`,
`doc/source/tutorials/Plotting.ipynb`, `doc/source/examples/vectorfitting/
vectorfitting_ex1_ringslot.ipynb`, `skrf/tests/test_network.py` — all read
directly via GitHub code search, not summarized secondhand).

- **Rights**: scikit-rf is BSD-3-Clause per this repo's own
  `docs/LICENSE_MATRIX.md` and `README.md`, and is **already a vendored
  dependency shipping this exact file on disk right now** — the cleanest
  redistribution story of any candidate in this report, since nothing
  new needs to be fetched or cleared.
- **Criterion 2 (measured + simulated)**: **genuinely satisfied**, and
  unusually well — `data/ring slot measured.s1p` (measured, "Created with
  mwavepy") and `data/ring slot.s2p` (the simulated/nominal network) are
  both present, and scikit-rf's own tutorial notebooks explicitly compare
  "the simulated reflection coefficient off the ring slot to a
  measurement" (`Plotting.ipynb`, read directly). This is a real,
  already-in-the-repo simulated-vs-measured pair.
- **Criterion 3 (machine-readable data)**: **already a real `.s1p`/`.s2p`
  Touchstone file**, sitting on disk today, directly loadable by
  `rf_tools.touchstone.analyze_touchstone` and
  `rf_tools.correlation.correlate_simulation_measurement` with zero
  conversion.
- **Criterion 4 (geometry)**: **fails.** This is a *ring slot* antenna
  (per the module docstring `"2-Port Network: 'ring slot', 75.0-110.0
  GHz, 201 pts"` — a W-band CPW-fed slot topology, not a rectangular
  microstrip patch), and neither the package nor its docs/tutorials
  publish eps_r/W/h/L for it — it is exactly the "bare network with no
  design context" the task's own lead-checking note warned might be all
  scikit-rf ships. `patch_resonant_frequency_hz` and
  `optimize_patch_length_for_target_frequency` cannot be driven against
  this case at all.
- **Criterion 5 (stated requirement)**: fails — no prose customer
  requirement exists for a teaching/demo network; it exists to
  demonstrate skrf's plotting/vector-fitting API, not to meet a design
  target. Its 75–110 GHz band is also far outside this repo's WLAN/ISM/
  adaptive-EM-skin target bands.
- **The 50 µm / εr criterion**: **not applicable** — there is no geometry
  published at all to hold to any precision, so the criterion cannot even
  be evaluated for this candidate.

### 4. GitHub — `aydnzn/A-rectangular-microstrip-patch-antenna` (Boğaziçi University coursework)

<https://github.com/aydnzn/A-rectangular-microstrip-patch-antenna> — cloned
directly this session (`git clone --depth 1`); contents inspected on disk:
`Project_report.pdf`, `Exercise.m`, `README.md`, `.DS_Store`.

- **Rights: fails outright.** **No `LICENSE` file exists anywhere in the
  repository** (confirmed by a full directory listing of the clone) and
  the `README.md` states no license terms. Absent an explicit license, the
  default under copyright law is "all rights reserved" — this repo cannot
  be committed into `tests/fixtures/` regardless of how good its data is.
  Recorded here as checked-and-rejected, not skipped.
- Everything else is reported only for completeness, since criterion 1
  already disqualifies it: it *is* a real rectangular patch, HFSS-designed
  and VNA-measured "in a lab at Bogazici University" (README, read
  directly from the clone), targeting 1.8 GHz GSM on "FR-4 Epoxy...
  dielectric constant of 4.4 and thickness of 1.6mm" — i.e. **datasheet-
  nominal FR4 εr**, not characterized, which would have failed the new εr
  criterion even had the license been clean. Exact dimension precision
  was not extracted from the PDF (moot given the license blocker), but
  the README's own framing ("width and length... were given") reads as
  ordinary HFSS-output precision, not a controlled-laminate
  characterization exercise.

### 5. NASA NTRS microstrip/conformal patch technical reports (public domain)

E.g. *Radiation and Scattering from Cylindrically Conformal Printed
Antennas* (NTRS 19940025369), *NASA Contractor Report NASA CR-137513,
"Microstrip Antenna Study"* (NTRS 19740021461), *NASA Technical Paper
2276, "Analysis of Rectangular..."* (NTRS 19840012667) — citations read
directly from NASA NTRS's own listing.

- **Rights**: strongest possible — a work of the U.S. Government is public
  domain, the same status `docs/LICENSE_MATRIX.md` already gives FCC eCFR
  text. No ambiguity, no attribution obligation even.
- **Criterion 2**: several of these reports (e.g. the FEM/prismatic-
  element validation report, NTRS 19950026401) explicitly compare
  simulated results "to reference calculations and measured data
  collected at the NASA Langley facilities" — real measured-vs-simulated
  comparisons exist in this literature.
- **Criterion 3**: **fails badly.** These are 1970s–1990s scanned-PDF
  technical reports. Data is printed plots and tables in a PDF, not a
  machine-readable Touchstone/CSV export — squarely the "only a printed
  graph" case the task asked to flag plainly.
- **Criterion 4/5**: varies by report and was not exhaustively checked
  page-by-page for every candidate report given the time this pass had —
  what's certain is that period-appropriate reporting precision (typically
  inches to 2–3 decimal places, or mm to one decimal) predates any
  expectation of 50 µm-class geometric reporting, and none of these
  reports characterize substrate εr the way a modern controlled-laminate
  paper would.
- **The 50 µm / εr criterion**: fails on both first-principles grounds
  above — this candidate class is included for completeness (public-
  domain rights are unimpeachable) but was not pursued further once the
  50 µm bar made it clearly moot without reading dozens of scanned PDFs on
  the chance one clears a bar it almost certainly can't.

## The 50 µm / characterized-εr criterion, applied across the board

None of the five candidates above satisfies it, and — as far as this
investigation reached, which did not exhaustively survey the literature —
**no candidate found in this pass publishes both (a) rectangular-patch
geometry to two decimal places in mm and (b) a measured/characterized εr
for the actual substrate coupon used**, as opposed to a datasheet-nominal
figure or no figure at all:

- The one candidate with a clean, primary-source-confirmed CC-BY license
  and machine-readable data (#2, the Zenodo/PMC dataset) states no
  substrate material or εr figure whatsoever, and its geometry precision
  is unstated.
- The candidate with genuinely real measured-vs-simulated data already
  sitting in this repo's own dependency (#3, `ring_slot`) has no geometry
  published at all — the criterion isn't failed so much as inapplicable.
- The one candidate with a real fabricated/measured rectangular patch and
  a specific dielectric constant (#4) uses "FR-4... dielectric constant of
  4.4" — precisely the datasheet-nominal case the coordinator's own
  reasoning (±0.2 tolerance → 50+ MHz uncertainty) was warning against —
  and is disqualified anyway on licensing.
- The candidate most likely to be well-instrumented (#1, peer-reviewed,
  CC-BY, real measured+simulated S11 and gain) could not be read at the
  primary source in this session at all, so its geometry precision and εr
  basis are simply unknown rather than confirmed-failing — an honest gap,
  not a quiet pass.

This is consistent with the coordinator's own framing: papers overwhelmingly
report antenna dimensions to one decimal place in mm (the "L = 30.6 mm"
convention), and a controlled-dielectric-laminate design with a
per-coupon-measured εr (rather than a datasheet nominal) is the exception,
not the rule, in the openly-licensed patch-antenna literature this
investigation was able to search and reach. **Finding both together, in one
candidate that also clears licensing and has real measured data, was not
achieved in this pass** — the honest read is that this combination is rare
enough that it likely requires either a metrology-focused paper (NIST/NPL-
style dielectric characterization work, not antenna-design literature) or
direct outreach to authors for supplementary data, neither of which this
research pass reached.

## Recommendation

**No single candidate satisfies all five original criteria plus the added
50 µm/εr bar.** Per the task's own instruction, that is reported plainly
rather than stretched.

The least-bad path, if a first fixture is still wanted now rather than
after further sourcing: **use `scikit-rf`'s own `ring_slot` Touchstone
pair (candidate #3) to exercise the mechanical/plumbing half of the
pipeline — `rf_tools.touchstone`, `rf_tools.correlation`,
`measurement.external.record_external_measurement` — since it is already
a real, license-clean, measured-vs-simulated Touchstone pair sitting on
disk in this repo's own dependency, needing zero new rights clearance.**
Its README-level fixture documentation would need to say plainly that it
is **not** usable to exercise `patch_resonant_frequency_hz` or
`optimize_patch_length_for_target_frequency` at all (wrong topology, no
geometry), so the ANALYSIS/OPTIMIZATION half of the loop stays untested by
this particular fixture — a second, separate fixture (hand-transcribed
numbers from a real, CC-BY, measured+simulated rectangular-patch paper,
most plausibly candidate #1 once its content can actually be read, with
its geometry precision and εr basis recorded honestly as whatever they
turn out to be — not stretched to imply 50 µm/characterized-εr confidence
they don't have) would be needed to cover that half.

That two-fixture split is itself the honest finding: **this repo's "first
end-to-end verification corpus" almost certainly cannot be one single real
case that satisfies every criterion at once** — it will need to be
assembled, and whatever fixture documentation goes with it should record
which precision limit (geometry rounding, or substrate εr uncertainty) is
the actual bottleneck on any 50 µm-level reasoning, per the coordinator's
own instruction not to let the fixture's documentation imply a precision
it doesn't have.

## What could not be verified (explicit, not a gap to paper over)

- **MDPI's site was unreachable to this session's fetch tooling** (403 on
  the article page, its PDF, and MDPI's own `/openaccess` policy page) —
  every claim about candidate #1's content rests on search-engine-indexed
  summaries and Semantic Scholar/Unpaywall metadata, not a direct read of
  the paper or MDPI's own license statement.
- Candidate #1's actual patch geometry (W/L/h), its stated εr (if any),
  and whether any supplementary/raw data exists were **not confirmed** for
  the same reason.
- The Zenodo record's own license line (candidate #2) was not separately
  fetched to confirm it restates the paper's CC-BY status — only the PMC
  article page itself was.
- NASA NTRS report bodies (candidate #5) were not opened page-by-page;
  their inclusion here rests on their citation-page abstracts plus the
  general, well-established fact of U.S. government public-domain status,
  not a confirmed read of any one report's exact dimensional precision.

## Orchestrator verification of the recommendation (run against this repo, not researched)

The research above was desk research; the two checks below were then executed
against the actual installed code. Both changed something material, so they
are recorded here rather than left for whoever implements the fixture to
rediscover.

**The recommended `ring_slot` pair does NOT correlate as-is.** `skrf.data.
ring_slot` is a **2-port** network (75–110 GHz, 201 points) while
`skrf.data.ring_slot_meas` is **1-port** (75–110 GHz, 101 points). Feeding
them straight to `rf_tools.correlation.correlate_simulation_measurement`
raises, by design:

```
CorrelationError: simulated network has 2 port(s) but measured network has
1 port(s) -- correlate_simulation_measurement requires both to have the
same port count
```

The fix is one line — extract S11 from the simulated 2-port first
(`ring_slot.s11`) — after which the pair correlates cleanly:

```
max |S11| magnitude difference: 3.045 dB
provenance: SIMULATED / MEASURED  ->  result CALCULATED
```

Two consequences worth carrying forward. First, any fixture built on this
pair has to do that port reduction explicitly, and should say why in a
comment, because the raw pair failing is the more obvious-looking thing to
"fix" by relaxing the port-count check in `correlation.py` — which would be
wrong, since that check is what stops a 1-port measurement being silently
compared against a 2-port simulation. Second, the differing frequency grids
(201 vs 101 points, stop frequency 110.0 vs 109.999999992 GHz) need no
special handling: `compare_touchstone` normalizes onto a common grid via
`interpolate_touchstone` already.

**The 3.045 dB delta is a feature, not a defect.** It is a real
measured-versus-simulated disagreement on real hardware data, which makes it
a load-bearing assertion: a fixture whose two sides agree perfectly (as a
synthetically-generated pair would) cannot catch a regression in the
normalization, interpolation, or renormalization path, because every wrong
answer still looks like zero difference. A non-trivial known delta can.

**MDPI's 403 is theirs, not our network.** The research pass could not reach
candidate #1 and honestly flagged it. Re-tested directly: `https://www.mdpi.
com/2079-9292/10/12/1447` and even `https://www.mdpi.com/` both return HTTP
403, while `https://doi.org/10.3390/electronics10121447` resolves normally
(302). So this is MDPI's own bot protection refusing automated fetches, not
a proxy or TLS problem at this end, and no amount of retrying from an agent
session will fix it. Verifying candidate #1's geometry and εr needs a human
opening the page in a browser, or the PMC/PubMed Central mirror if one
exists for that article.
