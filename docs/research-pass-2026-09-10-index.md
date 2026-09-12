# The MXene research pass of 2026-09-10 — what it produced, and where it landed

**Date:** 2026-09-10
**Ticket:** part of the wayfinder map [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104)
**Purpose:** an index. Three externally-written research documents were cross-checked against map #104, the ADR set, `docs/` and the code. This file is the entry point to everything that produced, and the record of a commit-history accident that makes it hard to find otherwise.

---

## Why this file exists

The work below reached `origin/main` inside a single squashed commit, **`762ee66`**, whose title is *"Chart Examples 1, 2, 4, 5, 6 and 7's scoring recipes (closes #467/NYS1) (#469)."*

That title describes a **different and unrelated** body of work that was merged in the same commit. A concurrent session branched from a local `main` that carried these commits but had not been pushed, and GitHub's squash collapsed both efforts into one.

**Nothing was lost.** The content was verified present file-by-file, and GitHub's squash preserved every individual commit message in `762ee66`'s body, so the reasoning is readable. But the individual commits are **not ancestors** of `origin/main` — `git log` and `git blame` on any file below will point at a commit whose subject line is about something else. This index is the map from the work to that commit.

*In plain terms: the filing cabinet is complete, but a week of work got filed under someone else's label. This is the note taped to the drawer.*

---

## 1. Findings about the world — new documents

Each is a first-hand read, not a summary of a summary. None of them is a decision; per ADR-0005 a decision is an ADR, and a finding about the world is not.

| Document | What it settles |
|---|---|
| [`mxene-rf-band-electrical-properties.md`](mxene-rf-band-electrical-properties.md) | Map #104's *"no measured conductivity, permittivity or surface impedance for MXene exists anywhere in 8–12 GHz"* is **false as a blanket claim**. Rakhmanov et al. (*APL* 123(20):204105, 2023) measured sheet resistance **208 → 21 Ω/sq** for 4 → 40 nm spray-coated films across **8.2–12.4 GHz** on a WR-90 TRL-calibrated VNA, and reports **AC σ = 1.20×10⁶ S/m against DC four-point-probe 1.43×10⁶ S/m on the same films** — the first *direct* measurement of the DC-versus-RF question this programme had only ever argued physically. Recomputes the standing "~9× lossier than copper" preference to **~7.0×**. The gap survives, narrowed: **no X-band measurement on an extrusion-printed trace exists.** |
| [`ozden-broadband-supercell-primary-source.md`](ozden-broadband-supercell-primary-source.md) | The experiment [#187](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/187) asks for **was run and measured in X-band in 2016** (Ozden, Yucedag & Kocer, *AEU* 70:1062–1070). Lateral detuning of coplanar cells over **one shared spacer above one continuous ground plane** — verbatim *"No scaling is applied along the z-direction"*. The answer separates two quantities that were being conflated: on **width** it agrees with the repo's bench (flat), on **depth** it gains ~52 percentage points. There was never a contradiction — only a baseline difference. |
| [`encapsulation-em-coupling.md`](encapsulation-em-coupling.md) | The map's *"no source found characterises that coupling"* is overstated — `literature-validation-cases.md` Case 3 already held one. Quantifies three regimes against ADR-0033's cell: ~100 nm is EM-free; 20–50 µm costs **−0.70 % to −2.75 %**, retuned by **widening** the gap 19–75 µm (*away* from the feature floor); ≥1.8 mm walks the band off the bottom. |

## 2. Decisions — ADRs

| ADR | Decision |
|---|---|
| **0049** | The intended-effect library is a **reference lookup, not a record of the requirement** — ADR-0030 stands unamended. An unknown effect returns a miss and never rejects. |
| **0050** | The registry carries `postprocess` and `sweep_axes` as their own fields (ADR-0045's "must" stands at four, not three), and grows **`BANDPASS_FSS`** and **`SHIELD`** — **but not an infrared family**, argued and declined. |
| **0033** *(amended)* | Five dated corrections. The Decision stands; the *reasoning* moved — most importantly, the rejected-alternatives list rejected ink **thickness** and was silent on ink **formulation**, which reaches the target window. |
| **0027** *(amended)* | Two dated corrections. §5's family test named *three* per-family plug-ins; the shipped `DesignFamily` carries **four**. The live victim: a radome reuses all three named plug-ins, so the test as written files it as a *letter* under `ABSORBER_TRANSMISSIVE`, which scores worst-in-band **absorptivity** — ranking the best radome last. |

Both amendments follow ADR-0020: dated correction blocks, wrong passage quoted verbatim, **Decision paragraphs byte-identical**.

## 3. Code

- `designs/intended_effects.py` — new. The lookup behind ADR-0049, plus `GapReason` so the type can say *"refused in writing"* rather than *"not yet built."*
- `designs/design_families.py` — ADR-0050's fields and families, and a consistency test so the registry and the effects library **cannot silently drift apart** again.
- `rf_tools/sheet_impedance.py` — docstring scope only, no behaviour change: `min_overlay_sheet_resistance_ohm_sq` is **necessary but not sufficient** for a resonant patterned overlay (it models a purely resistive sheet); `grid_effective_permittivity` hardcodes air above and fails for any encapsulated stack.
- `simulation/palace.py` — a stale citation retargeted from the closed #289 to the open #362 / #361.

## 4. The register

`RUNNING-LISTS.md` §3 **corrections 49–66** — eighteen wrong beliefs, each naming the superseded claim and its replacement. §1 gained four stranded sources with the routes actually tried. §5 gained two annotations and **one claim explicitly refused**.

The correction worth knowing about if you read only one: **49**. A `CONFIDENCE: HIGH` ruling that *"no group has ever run #187's experiment"* was drawn from a five-paper corpus spanning 380–2300 nm, 10.90–22.91 µm, 400–3500 nm, 500–2000 nm and a review — **not one microwave paper.** A claim about "the published record" for an X-band question, from a corpus that never searched the band.

## 5. Tickets

Sixteen decision tickets, all sub-issues of #104: **#445–#457**, **#465**, **#470**, **#471**.

## 6. One thing in this pass that is NOT citable, and why

A second workflow scored 79 harvested candidates across eight intended effects, aiming to correct the source documents' MXene-titled framing. **Its ranking is contaminated and must not be cited.** Its own adversarial audit established why: the selection rule carried an explicit anti-MXene promotion penalty, and the flat cap across all effects meant every scored MXene candidate landed in the one effect decided by raw conductivity — where stocked silver's guaranteed floor already exceeds the best non-annealed MXene film. Five *measured* MXene candidates were scored, none reached the top rank, while two `CALCULATED`, never-built, in-house designs did. The provenance ladder ran backwards.

**Two findings from that pass are independent of the ranking and were verified by direct term search, so they stand** — and both are ticketed:
- **#470** — whole material classes absent from the sweep. Vacuum-metallised aluminium is the fielded incumbent for both shielding and low-IR and is **~17× lighter than the best MXene at equal shielding** (`ρ/σ` 1.35×10⁻⁴ vs 2.24×10⁻³), absent from a roster of 79. Carbonyl iron was the **only µₛ > 1 candidate in the entire pass**, on the one effect where static permeability is the sole term that raises the Rozanov ceiling.
- **#471** — the charter's opening physics has **zero coverage**. *Artificial magnetic conductor, high-impedance surface, Sievenpiper, reflection phase, in-phase bandwidth, magnetic mirror, AMC* — zero hits across all three documents. There is still not one X-band, printable, measured in-phase reflection number anywhere in this programme. That is a gap in **what was searched**, not in the field: Sievenpiper 1999 is three decades deep.

Recording a contaminated result alongside the sound ones is deliberate. A pass that reports only its good half is the failure this repo keeps logging corrections about.
