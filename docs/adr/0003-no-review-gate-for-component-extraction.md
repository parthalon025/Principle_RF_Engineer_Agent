---
status: accepted
---

# No human review gate for automated component extraction

`components.specifications` is populated by LLM-driven structured
extraction from ingested datasheets/application notes (via
`extract_components`), and those values feed directly into engineering
calculations (`calculate_cascade_gain`, `calculate_noise_figure`, etc.).
The obvious instinct is to gate extracted rows behind a human confirmation
step before they're usable, mirroring how `docs/SECURITY.md` gates other
consequential actions. We rejected that: this company has no RF engineer
on staff, so a human reviewer could not judge whether an extracted gain or
noise-figure value is RF-plausible any better than the extractor already
tried to — a confirmation step would only reintroduce the bottleneck the
system exists to remove, without adding real judgment.

Instead, confidence is expressed entirely through provenance and
deterministic validation, both already load-bearing concepts in this
codebase. Extraction always writes to `components`, per field: a clean,
unambiguous single-value read is tagged `MANUFACTURER-SPECIFIED`; an
ambiguous or low-confidence read is tagged `INFERRED` instead. Separately,
each category's structured schema enforces hard physical bounds
(`nf_db >= 0`, `|S11| <= 1`, etc., matching the validation style already in
`rf_tools`'s domain modules) — a value that violates a bound is tagged
`UNKNOWN` with the violation recorded, which doesn't depend on the model's
own (potentially miscalibrated) confidence signal. Anywhere a component
spec is used in an actual engineering claim, `prompts/principal_engineer.md`'s
mandatory-provenance rule forces that qualifier to surface — an `INFERRED`
or `UNKNOWN` value shows up qualified, not laundered into an unqualified
fact — and the design-review workflow (PASS/CONDITIONAL PASS/FAIL/NOT
VERIFIED/BLOCKED) is where a shaky spec is meant to get caught, the same
mechanism `CONTEXT.md`'s evidence hierarchy already exists to serve.

## Considered options

Routing low-confidence extractions to a human "needs review" queue —
rejected because no one at the company has the RF expertise to review
them meaningfully; the queue would just accumulate unresolved items.
