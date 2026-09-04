# Verification

Every serious design needs a verification matrix.

Minimum fields:

| Field | Description |
|---|---|
| requirement_id | Stable requirement identifier |
| requirement | Human-readable requirement |
| method | analysis / simulation / measurement / inspection / test |
| expected | threshold or expected behavior |
| actual | measured/calculated result |
| status | PASS / CONDITIONAL PASS / FAIL / NOT VERIFIED / BLOCKED |
| evidence | file/report/measurement reference |
| notes | limitations |

A release recommendation must not be PASS if a critical requirement is NOT VERIFIED.

---

## Verification corpus (issue #144)

The matrix above verifies a *design*. This package also verifies the *system*:
two harnesses that check the tools still produce good answers, not merely that
they run.

The distinction matters. Before these, you could change the embedding model,
the chunking, or the ranking, destroy retrieval quality, and watch the whole
suite stay green — because no test knew what a good result looked like.

### `retrieval_eval.py` — knowledge-base retrieval quality

A **golden query** is a question plus the documents that ought to answer it.
`golden_queries.json` holds six of them over the real corpus in
`knowledge/corpus/`, each verified against the source text before being
committed. `tests/test_retrieval_gate.py` runs them through the real search
and fails if mean recall drops below its threshold.

Three metrics, in plain terms:

| Metric | Question it answers |
|---|---|
| **Recall@k** | Of the documents that should have come back, how many appeared in the top k? |
| **Precision@k** | Of the results returned, how many were relevant? |
| **Reciprocal rank** | How far down the list was the first correct hit? |

Recall is what the gate decides on; the others are reported for context.

Two honest limits. The gate needs Postgres, so it runs in CI and not locally.
And CI configures no embedding backend, so search degrades to its lexical path
— meaning the gate measures **lexical** retrieval there. That is a real floor
and the half a chunking or ranking change breaks, but it is not the whole
picture. It is also why the queries read as keywords rather than questions:
lexical search ANDs every term, so a natural-language query only matches if one
chunk contains all of its content words.

### `simulator_reference_cases.py` — solver adapter validation

The simulator adapters are tested against fakes: they confirm we write the
right input deck and parse the output we are handed. Nothing confirms the
solver told us the truth. A **reference case** is a problem whose answer is
published independently of this codebase, so running it end to end tests the
physics rather than the plumbing.

The first case is a centre-fed thin half-wave dipole, whose feed impedance
(≈ 73 + j42.5 Ω — a 73-ohm resistor in series with a small inductor, which is
why 75-ohm coax exists) is among the most reproduced numbers in antenna
engineering.

**Status: never executed.** No full-wave solver is pip-installable and CI
installs none, so `tests/test_simulator_reference_cases.py`'s real-solve test
skips everywhere today. The case definitions, tolerances and checking logic are
tested and ready; the first actual run is unproven. This is the test that would
let `SIMULATED` mean *validated* simulation in `CONTEXT.md`'s evidence
hierarchy.
