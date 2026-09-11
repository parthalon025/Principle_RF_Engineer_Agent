# Do the two Hugging Face resources (and anything else found there) help this program?

**Date:** 2026-09-11
**Trigger:** unsolicited research request — a user pointed to a Hugging Face dataset (`ClarusC64/metamaterial-resonance-coherence-drift-detection-v0.1`) and a Hugging Face model repo (`lamm-mit/MetaMaterialsDiscovery`), and asked whether either, or anything else on Hugging Face, is useful for this program.
**Scope:** the two named resources, read to the level of their actual row/file contents (not just their listing metadata), plus a systematic Hugging Face search sweep for RF/electromagnetic-metamaterial-adjacent datasets and models turned up in the same session. No ticket opened — this is a scouting note, matching the precedent set by `docs/elastodynamic-metamaterials-dataset-relevance.md`.

---

## Bottom line up front

**Neither named resource is usable, and nothing else found in the sweep clears this program's bar either — but for different reasons, and one of them is worth knowing precisely.**

- **`ClarusC64/metamaterial-resonance-coherence-drift-detection-v0.1` is not a physics dataset at all.** Its own rows say so. The 7 total records (6 train + 1 test) carry fields like `"constraints": "<=280 words"` and `"gold_checklist": "score+drift+flag+horizon+plan"`, and the single test row's `notes` field literally reads *"Model must output resonance_coherence_score, drift_rate, functional_property_risk_flag, failure_horizon_cycles, retune_or_rebuild_plan."* This is a prompt/grading fixture for testing whether a language model can produce a structured report against a checklist and a word limit — an LLM-evaluation dataset wearing a metamaterials-sounding name, not measured or simulated RF data. It also self-contradicts on the physics it claims: two rows label their platform `"optical meta"` / `"optical cloaking"` while reporting `measured_resonance_ghz` of 0.79 and 0.70 — sub-gigahertz. Optical metamaterials resonate at hundreds of terahertz; nothing operates in the optical regime at 0.7 GHz. That internal impossibility is on top of the structural evidence above, not instead of it.
- **`lamm-mit/MetaMaterialsDiscovery` is real, documented research — in the wrong physics domain.** It is an archive of three autonomous-agent runs (Fable 5.1 via Claude Code) that built mechanics solvers and ran fracture simulations on **hierarchical beam-network structures under quasi-static tensile load** — stiffness, peak load, work-to-failure, crack propagation. It never touches electromagnetics: no permittivity, no permeability, no S-parameters, no resonance, no Maxwell's equations anywhere in the README. This is mechanical metamaterials research (the same "wrong governing equation" problem the elastodynamic dataset had, per the existing `docs/elastodynamic-metamaterials-dataset-relevance.md`), except this one is not even a dataset in the training-data sense — it is a reproducibility archive (code, solvers, HTML apps, PDF reports) for someone else's mechanics study.
- **The broader sweep found nothing better.** One dataset (`CJJones/LLM_Training_Antenna_Design`) is explicitly synthetic marketing filler, confirmed by inspecting its actual rows. Two mmWave-band metasurface datasets exist but are either undocumented and currently broken (`astroboy1/metasurfaces_V1_30-90GHZ`) or in a different application domain entirely (`Bingxuan111/metasurface-real-eccv2026`, a computational-imaging/depth-estimation dataset built on *optical* metasurfaces, not RF). None of these were fetchable as `MEASURED` or `LITERATURE-SUPPORTED` RF unit-cell data in this program's sense (CLAUDE.md's charter: an element only enters the library after it is printed and measured, per ADR-0027).

**Net effect on this program: no change.** There is still no Hugging Face resource that can be cited, ingested, or trained against for this program's RF surface designs. The gap this closes is narrower — it establishes *that* these two specific pointers don't help and *why*, so nobody re-discovers and re-evaluates them later.

---

## 1. `ClarusC64/metamaterial-resonance-coherence-drift-detection-v0.1` — read at row level

### 1.1 What the listing claims

The dataset card describes itself as testing "whether a model can detect coherence loss" between three things that are supposed to move together: unit-cell geometry, simulated resonance, and measured scattering response. Tags: `tabular-classification`, `tabular-regression`, `materials`, `metamaterials`, `resonance`, `scattering`, `sem`, `simulation`, `drift`. Created 8 Feb 2026, 150 downloads, 0 likes, MIT license, single author (`ClarusC64`). No paper, no code repository, no instrument documentation, no citation of any kind is linked anywhere on the dataset page.

### 1.2 What is actually in it

The Hub's own Dataset Viewer timed out repeatedly when queried through the standard preview API, so the two Parquet exports were fetched directly (`default/train/0000.parquet`, `default/test/0000.parquet` from the dataset's `refs/convert/parquet` branch) and read with `pyarrow`. Full contents, verbatim:

**Train split — 6 rows, 19 columns.** Every row has an `id` (`MRC-001` … `MRC-006`), a `meta_platform` (`"RF metasurface"`, `"cloaking shell"`, `"optical meta"`, `"RF negative index"`, `"optical cloaking"`), a `unit_cell_type` (`split-ring`, `fishnet`, `ring array`, `nano-antenna`, `nano-slot`), paired `simulated_resonance_ghz` / `measured_resonance_ghz` values, an `s11_min_db`, geometry-deviation and alignment-error percentages, thermal/humidity stress counters, a `resonance_coherence_score`, a `drift_rate`, a risk flag, a `failure_horizon_cycles`, a free-text `retune_or_rebuild_plan`, and — the two columns that settle what this dataset is — `constraints: "<=280 words"` and `gold_checklist: "score+drift+flag+horizon+plan"` on every single row.

**Test split — 1 row.** Same schema, but `resonance_coherence_score`, `drift_rate`, `functional_property_risk_flag`, `failure_horizon_cycles`, and `retune_or_rebuild_plan` are all `null`, and the `notes` field reads in full:

> `"Model must output resonance_coherence_score, drift_rate, functional_property_risk_flag, failure_horizon_cycles, retune_or_rebuild_plan"`

That is an instruction to a language model, stored as data. `gold_checklist` is the grading rubric for that instruction. This is the standard shape of an LLM structured-output eval: a handful of hand-authored scenario rows, one held out with its answer fields blanked, a word-count constraint, and a checklist naming exactly which fields a passing answer must fill in. **It is a fixture for testing or training a report-writing model, not a record of anything measured or simulated on a metamaterial.**

### 1.3 The numbers are also physically incoherent, independent of the above

Two rows (`MRC-004`, `MRC-006`) label their `meta_platform` `"optical meta"` and `"optical cloaking"` respectively, with `measured_resonance_ghz` of **0.79** and **0.70**. Optical-band electromagnetic resonance sits at hundreds of terahertz (visible light is roughly 400–750 THz); 0.7–0.79 GHz is UHF, six orders of magnitude off and squarely in the radio band this program actually works in. No real optical-metamaterial measurement would be reported this way. This is consistent with §1.2's finding — synthetic filler rows do not need to obey the physics their labels claim, because nothing generated or checked them against a simulator.

**Conclusion for §1: not usable at any tier.** Not `MEASURED` (nothing was fabricated or measured — the dataset's own test row asks a model to fill in values, meaning even the populated train-split numbers are unverifiable as anything other than plausible-sounding placeholders authored alongside the eval task). Not `LITERATURE-SUPPORTED` (no paper, no method, no instrument). Not even usable as a *methodology* reference the way the elastodynamic dataset's paper was, because there is no method here to borrow — no simulator, no measurement protocol, nothing but a grading rubric.

---

## 2. `lamm-mit/MetaMaterialsDiscovery` — real research, wrong physics

### 2.1 What it is

A Hugging Face **model** repository (used to host a large file archive, not model weights) from the MIT LAMM lab (Markus J. Buehler), publishing three independent runs in which an AI agent (Fable 5.1, operated through Claude Code) built its own mechanics solvers and used them to study **hierarchical metamaterial fracture** — planar beam-network structures under quasi-static tensile loading, tracking stiffness, peak load, work to failure, damage localization, and abrupt-vs-progressive fracture transitions. Each run's archive contains its solver source, an interactive browser application, simulation records (parameters, seeds, force–displacement histories), validation scripts, a written report with LaTeX source, and STL geometry exports. A companion image dataset (`lamm-mit/MetaMaterialsDiscoveryImages`) supplied the five reference images each run started from. Citation given (arXiv id not yet assigned as of the README's own text): Buehler, "Artificial intelligence agents autonomously build computational laboratories that reveal design principles of hierarchical metamaterial failure," 2026.

### 2.2 Why it does not transfer to this program

This is the *same* failure mode already documented for the UCI 2D Elastodynamic Metamaterials dataset in `docs/elastodynamic-metamaterials-dataset-relevance.md`, and for the same underlying reason: **"metamaterial" spans multiple physics, and this repository's is mechanical, not electromagnetic.** Confirmed by a full read of the README: the governing physics is Euler–Bernoulli/Timoshenko beam mechanics (elastic members, irreversible failure, load redistribution), not Maxwell's equations. There is no permittivity, permeability, conductivity, S-parameter, resonance, or reflection-phase quantity anywhere in the document. Nothing here — not the mechanics models, not the fracture predictions, not the holdout-accuracy methodology — carries any numeric or structural meaning for an RF unit cell's electromagnetic response.

It is also, unlike the elastodynamic dataset, not structured as *training data* at all: there is no bitmap-in / property-out table to point a model at. It is a **reproducibility archive** — source code, applications, and reports for someone else's already-completed mechanics study. The closest thing to a transferable idea is the *meta*-methodology — an agent building its own physics solver from a prompt and reference images, then using it to run and audit its own experiments, including catching and later correcting its own width-control bug — which is a process precedent for autonomous agentic research generally, not a design-method precedent for this program's Maxwell-equation problem the way the elastodynamic paper's pixel-bitmap ML pipeline was.

**Conclusion for §2: not usable as data, and not a methodology fit either** — the elastodynamic dataset at least offered an ML *technique* (symmetry-reduced pixel bitmaps → interpretable model) that this program's charter already names as a legitimate design method. This repository offers a mechanics solver and a research-process story, neither of which this program needs; its own RF/EM full-wave tooling already exists and is not mechanics-based.

---

## 3. The broader sweep — what else Hugging Face has under RF/metamaterial-adjacent terms

Search scopes tried: `metasurface`, `frequency selective surface`, `S-parameters`, `unit cell electromagnetic`, `reflectarray`, `RCS radar cross section`, `microstrip patch antenna`, `antenna design`, `electromagnetic absorber`, `coding metasurface`, `programmable metasurface`, `inverse design metasurface`, run against Hugging Face's dataset, model, and paper search. Every non-empty result is listed; empty-result terms are not repeated in the table.

| Repo | What it is | Verdict |
|---|---|---|
| [`CJJones/LLM_Training_Antenna_Design`](https://huggingface.co/datasets/CJJones/LLM_Training_Antenna_Design) | Card calls itself *"Procedurally generated... output as if generated by an optimization or simulation system,"* upsells a 100k-row version on Gumroad. Rows inspected directly (Parquet, 8,696 text rows): `"Input: Generate optimized antenna design for vhf band, type=ground-plane, config=enhanced"` / `"Output: Design ID=8dd2f533-..."` / `"Frequency=281654801.070 Hz, Material=silver"` — templated text fragments with a random UUID design id and a frequency/material pair with no stated derivation. **Confirmed synthetic filler, explicitly not simulator output despite the card's phrasing.** Exactly the kind of unverifiable, fabricated-looking-precise data CLAUDE.md's charter warns against treating as research. |
| [`astroboy1/metasurfaces_V1_30-90GHZ`](https://huggingface.co/datasets/astroboy1/metasurfaces_V1_30-90GHZ) (and the author's `_V20`, `_v3` siblings) | Image-modality, mmWave band name (30–90 GHz) in the title. No description, no task tags beyond `modality:image`, no README content retrievable through the Hub metadata tools. The Hub's own Parquet conversion fails with a cast error and lists 0 rows resolved. **Undocumented and currently unreadable through any tool used in this session** — not ruled out on physics grounds, ruled out on inability to verify what it contains without a manual, unstructured file-by-file download outside this session's scope. Worth a second look only if someone is willing to hand-inspect the raw (non-Parquet-converted) files. |
| [`Bingxuan111/metasurface-real-eccv2026`](https://huggingface.co/datasets/Bingxuan111/metasurface-real-eccv2026) | Real, documented, arXiv-linked (2503.15770) dataset — but it is *optical* metasurface data (nanophotonic wavefront encoding) for **monocular depth estimation**, an ECCV 2026 computational-imaging paper. Right word ("metasurface"), wrong band (optical, not RF) and wrong application (camera depth sensing, not antenna/reflector design). Same "physics regime mismatch" verdict as §2, plus an unrelated application domain on top. |

No results at all were returned for `frequency selective surface`, `S-parameters`, `unit cell electromagnetic`, `reflectarray`, `RCS radar cross section`, `microstrip patch antenna`, `electromagnetic absorber`, `coding metasurface`, `programmable metasurface`, or `inverse design metasurface` as dataset/model search terms — none of the vocabulary this program's own prior-art survey (`docs/element-library-prior-art.md`) uses to describe its design space currently has a Hugging Face-hosted dataset or model attached to it.

---

## 4. Existing prior art in this repo — confirmed absent

A repo-wide grep for `ClarusC64`, `lamm-mit`, `MetaMaterialsDiscovery`, `huggingface.co/datasets`, and `coherence.drift` returned no matches anywhere in the codebase or `docs/`. Neither resource has been referenced here before; this document is the first record of either being evaluated.

---

## 5. Recommendation

**Do not cite either resource, or any of the three sweep results, anywhere in this program's designs, warnings, or knowledge base.** Specifically:

- `ClarusC64/...` should not be ingested even provisionally — it is not mislabeled research, it is not research. There is nothing in it to downgrade to `UNVERIFIED`; the rows themselves are answer keys for an unrelated LLM-grading task.
- `lamm-mit/MetaMaterialsDiscovery` is legitimate work and could be worth watching for its *process* (agentic research methodology) if this program ever documents its own agent-driven-research approach for comparison, but it is out of scope for `docs/element-library-prior-art.md` or any RF-specific knowledge ingestion — it answers a mechanics question, not an electromagnetics one.
- `astroboy1/metasurfaces_V1_30-90GHZ` is the one genuinely open question in this sweep: right frequency band, right keyword, completely undocumented. If this program later wants to spend the time, the next step is a manual, non-Parquet download of the raw repository files (the Hub's automatic tabular conversion has already failed on it) to see what the images actually are before making any claim about them — that has not been done here and should not be assumed to resolve either way from this document.

No ticket is opened for this. If a future session wants to act on the `astroboy1` open question, that is the one item here with an actual next step attached.

---

## Sources

1. Dataset: [`ClarusC64/metamaterial-resonance-coherence-drift-detection-v0.1`](https://huggingface.co/datasets/ClarusC64/metamaterial-resonance-coherence-drift-detection-v0.1) — card metadata read via the Hub API; row contents read directly from `default/train/0000.parquet` and `default/test/0000.parquet` on the dataset's `refs/convert/parquet` ref, fetched and parsed with `pyarrow` in this session. All 7 rows quoted or described above are the complete dataset.
2. Model repository: [`lamm-mit/MetaMaterialsDiscovery`](https://huggingface.co/lamm-mit/MetaMaterialsDiscovery) — README.md read in full via the Hub filesystem tool.
3. Dataset: [`CJJones/LLM_Training_Antenna_Design`](https://huggingface.co/datasets/CJJones/LLM_Training_Antenna_Design) — card metadata plus first three rows of `default/train/0000.parquet`, fetched and parsed with `pyarrow`.
4. Dataset: [`astroboy1/metasurfaces_V1_30-90GHZ`](https://huggingface.co/datasets/astroboy1/metasurfaces_V1_30-90GHZ) — Hub metadata and dataset-structure API only; Parquet conversion reports a cast error and 0 resolved rows, so no content beyond the title and `modality:image` tag was retrievable in this session.
5. Dataset: [`Bingxuan111/metasurface-real-eccv2026`](https://huggingface.co/datasets/Bingxuan111/metasurface-real-eccv2026) — card metadata, including its own linked arXiv identifier 2503.15770, read via the Hub API.
6. `docs/elastodynamic-metamaterials-dataset-relevance.md` — this repo's existing precedent for evaluating a superficially-similar-sounding external "metamaterials" dataset against this program's RF/EM scope; its structure, provenance discipline, and "different governing equation" framing are reused here for §2.
7. `docs/element-library-prior-art.md` — read to confirm the RF/EM vocabulary used for the §3 search sweep and to confirm neither named resource nor any sweep result is already referenced there.

**Not retrieved / out of scope for this session:** the raw (non-Parquet) file listing of `astroboy1/metasurfaces_V1_30-90GHZ` and its two sibling repositories (`_V20`, `_v3`) — flagged in §5 as the one open item this document leaves for a future pass.
