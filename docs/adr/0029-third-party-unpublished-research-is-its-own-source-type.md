---
status: accepted
---

# Third-party unpublished research is its own source type, ranked between a patent and internal history

The charter makes partner research a front door: work received from research
partners who have already proposed solutions is a primary input, not an
occasional extra. Today it has no honest way in.

`knowledge/models.py:37-43` closes the source-type set to `datasheet`,
`application_note`, `standard`, `textbook`, `paper`, `patent` and
`design_record`; `knowledge/ingest.py:99` raises on anything else. Every
existing option misfiles a partner's proposal:

- **`paper`** maps to `LITERATURE-SUPPORTED` at authority rank 40, tied with
  peer-reviewed literature and **above a granted patent** (rank 50). An
  unreviewed proposal would outrank published, examined work in every
  `search_knowledge` result, because retrieval sorts by authority rank before
  match score (`knowledge/search.py:137-140`). Overclaims.
- **`design_record`** sits at rank 60 but is defined as *"an internally-authored
  design/decision write-up"*, *"the engineering team's own precedent"*
  (`knowledge/models.py:21-27`, `knowledge/provenance.py:7-8`). Filing a
  partner's document here makes the corpus claim their work as ours. That is a
  provenance defect, not a labelling inconvenience.

**Decision: add a source type for third-party unpublished research**, ranked
between `patent` (50) and `design_record` (60). It is outside work, so it does
not inherit internal history's discount; it is unreviewed and unpublished, so
it does not reach the peer-reviewed tier. Its provenance maps to
`LITERATURE-SUPPORTED` — the evidence is somebody's stated technical result,
just not a published one — with the authority rank carrying the distinction,
which is exactly the mechanism `patent` already uses to sit below `paper`
(`knowledge/provenance.py`'s `PATENT_AUTHORITY_RANK`).

Rejected: reusing `authority_rank_override`. The parameter exists on
`knowledge/ingest.py:40` but is not exposed on the agent's `ingest_document`
tool (`agent/main.py:1389-1396`), so it is unreachable from any surface a user
has — and a per-document override would leave the *type* still wrong, which is
what search, extraction eligibility and future policy all key on.

## Consequences

- `author` and `revision` already exist on `ingest_document`
  (`knowledge/ingest.py:42-43`) and are likewise not exposed on the agent's
  tool. A partner source is useless without attribution, so exposing them is
  part of this change, not a follow-up.
- Component extraction stays restricted to `datasheet`/`application_note`
  (`knowledge/extract.py:61`), so the new type gets no structured field
  extraction — the same treatment `paper` and `patent` already receive.
- The evidence hierarchy in `CONTEXT.md` gains no new rung: this is a new
  *source type* resolving to an existing provenance value at a distinct
  authority rank, which is the extension point the model already has.
