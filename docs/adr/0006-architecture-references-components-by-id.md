---
status: accepted
---

# `designs.architecture` references components by id, not free text

Issue #7 explicitly punted on this: "Referencing components from
`designs.architecture` (how a design actually points at a component row) —
noted as an open question during grilling but not resolved or built here."
Now that `components` rows exist and `decision_records`/`verification_items`
need to cite "this design uses part X for requirement Y" as real evidence,
leaving `architecture` as free text would mean a decision's evidence is a
string with no foreign key — undercutting the whole point of the citable,
provenance-tagged records this and the knowledge-ingestion epic both build.
`architecture` is a functional-block map,
`{block_name: {component_id, role, ...}}`, and `component_id` is validated
against a real `components` row at write time: a dangling reference is
rejected with a structured error, not written.

This is a deliberate asymmetry with `components.specifications`, where an
extracted field is allowed to be `INFERRED`/`UNKNOWN` rather than rejected —
that leniency exists because an extraction is a genuinely uncertain read of
a datasheet. A design author asserting "block X uses component Y" is not an
uncertain read; it's a claim about something that either exists in the
database or doesn't, so it gets checked, not qualified.
