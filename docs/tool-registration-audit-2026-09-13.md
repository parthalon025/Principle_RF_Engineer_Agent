# Tool-registration audit (2026-09-13) — and a correction to issue #316's own premise

**Read this first, in plain terms:** issue #316 asks for four sequenced
tickets (a 0-th read-only audit, then Expand, Verify, Contract) to move this
repo's ~90 LLM tools off two hand-maintained registration files and onto one.
That work already happened. Issues #317 (audit) → #318 (expand) → #319
(verify) → #320 (contract) are all closed, plus three follow-on tickets
(#372, #376, #377) that did further real contraction once #320's own
investigation found the job was bigger than first scoped. This document is
the *current-state* re-audit the parent task asked for — it re-counts
everything from the code as it stands today rather than trusting any past
ticket's numbers — and it finds the registrations healthy: zero cross-file
registration gaps, no unfixed docstring drift, and both roles' tool sets
correctly assigned. The one thing this document does **not** do is create
three more Expand/Verify/Contract tickets, because that would duplicate
already-closed work and an already-open decision ticket (#479). See
"What this means for issue #316" at the end.

## Method

Counted directly from the code in this worktree, not from any prior
document's numbers: an AST walk of `agent/main.py` (matching functions
decorated `@function_tool`) and `mcp_server/server.py` (matching functions
decorated `@mcp.tool()`), extracting each tool's name, docstring, and
whether it carries `strict_mode=False`. Full script:
`/tmp` scratch path used for this session, reproducible with the description
below — nothing under `docs/` depends on the script itself. Role assignments
were read directly from `agent/main.py`'s `ROLE_SPECS`/`_ALL_TOOLS` and
`agent/mcp_roles.py`'s `MIGRATED_ROLE_TOOL_NAMES`.

## Finding 1 — tool counts, fresh as of this commit

- **`agent/main.py`: 59** `@function_tool`-decorated wrappers.
- **`mcp_server/server.py`: 96** `@mcp.tool()`-decorated wrappers.
- **Registration gap in the dangerous direction (wrapped in `agent/main.py`,
  absent from `mcp_server/server.py` — the exact #276/#288 failure shape):
  zero.** Every one of the 59 wrappers has a same-named registration on the
  MCP server.
- **The 37-tool difference (96 − 59) is exactly accounted for**, not a
  mismatch: those 37 tools are the ones issue #376 deleted from
  `agent/main.py` because they are used exclusively by the three roles
  (principal, systems, verification) that #377 first proved could run live
  on the new `mcp_servers=[server]` + `create_static_tool_filter`
  construction. They still exist — and are still registered — on
  `mcp_server/server.py`; they are simply no longer wrapped a second time in
  `agent/main.py`, because nothing needs that second copy anymore. Listed in
  full: `advance_design_loop_step`, `advance_design_status`,
  `calculate_free_space_path_loss`, `calculate_link_budget_margin`,
  `confirm_requirement_target`, `create_design`, `extract_components`,
  `index_document`, `ingest_3gpp_spec`, `ingest_arxiv_paper`,
  `ingest_document`, `ingest_etsi_ipr_declaration`, `ingest_etsi_standard`,
  `ingest_fcc_rule`, `ingest_patent`, `inspect_design_loop_state`,
  `lookup_3gpp_spec_status`, `lookup_digikey_component`,
  `lookup_digikey_product_details`, `lookup_mouser_component`,
  `lookup_nexar_component`, `lookup_nexar_part_data`,
  `mark_requirement_unscoreable`, `propose_requirement_target`,
  `read_design`, `read_document`, `reconcile_component_sources`,
  `record_decision`, `run_candidate_search`, `search_arxiv_papers`,
  `search_design_records`, `search_fcc_rules`, `search_ink_product`,
  `search_literature_for_capability_warning`, `search_uspto_patents`,
  `start_design_loop`, `verify_requirement` — 37 names, matching #376's own
  closing count exactly.

**Why this repo's older 87/89 and 96/96/96 counts don't match this
document's 59/96:** those are different points in the same migration, not a
disagreement. 87–89 (ADR-0032's original estimate) and 96 (the corrected
count, #320's own recount) both describe the *pre-contraction* state, when
`agent/main.py` still wrapped nearly every tool. 59 is the *current*,
*post-#376* count — the two files are no longer expected to carry the same
total, by design, because 37 tools' only remaining registration is on the
MCP server.

## Finding 2 — `strict_mode=False` tools

- **`agent/main.py`: 16** tools carry `strict_mode=False` (an
  `@function_tool`-only concept — it turns off the SDK's default JSON-schema
  strictness for an open-ended dict/list argument shape):
  `compile_lab_test_plan`, `correlate_simulated_and_measured`,
  `generate_freecad_curved_geometry`, `run_elmer_simulation`,
  `run_gprmax_simulation`, `run_hfss_simulation`,
  `run_kicad_gerber2ems_simulation`, `run_ltspice_simulation`,
  `run_meep_simulation`, `run_nec2_simulation`, `run_ngspice_simulation`,
  `run_openems_simulation`, `run_openparem_simulation`,
  `run_palace_simulation`, `run_qucs_simulation`, `run_xyce_simulation`.
- **`mcp_server/server.py`: 0**, and this is expected, not a gap.
  `@mcp.tool()` has no `strict_mode` parameter at all — an MCP tool's schema
  strictness is instead a property of the *consuming* Agent
  (`Agent.mcp_config["convert_schemas_to_strict"]`, confirmed in ADR-0032 to
  default to `False`), not of the registration decorator. Comparing "16" to
  "0" here would be comparing two different concepts, not finding a
  discrepancy — ADR-0032's own "24-28" estimate for this count was for the
  pre-contraction 96-tool `agent/main.py`; today's smaller 59-tool
  `agent/main.py` naturally carries fewer.

## Finding 3 — docstring drift between the two registrations

Every one of the 59 tools common to both files was diffed docstring-to-
docstring. **20 show some textual difference; zero show a substantive
behavioral-claim difference.** All 20 are the `mcp_server/server.py` copy
being a tighter, shorter edit of the same facts — trims like "unverified
end-to-end until it has been run against the real tool at least once"
shortening to rely on the preceding "none is installed in this environment"
already saying the same thing, or "Calculate return loss in dB from the
magnitude of the reflection coefficient (|Gamma|)" shortening to "from
|Gamma|". Checked line-by-line for every drifted tool, including all ten
`run_*_simulation` tools (the longest, most caveat-heavy docstrings in the
repo, and the ones with the largest raw character-count differences): every
number, every scope limit, every "NOT verified against a real binary"
caveat, and every safety-relevant claim (HFSS's licensed-workstation
confinement, ngspice's S-parameter scope limit, Palace's 0.056 dB / 0.91°
validation figures) is present and unchanged in both copies.

`correlate_simulated_and_measured` — the one substantive drift issue #316
names by name, and the one #317 already fixed (PR #333) — was re-checked
directly: both copies now say, identically in substance, that openEMS's
S-parameters are accepted via `"touchstone_file"` only for the single-port
`computed=True` case and honestly rejected otherwise. **No regression; the
fix holds.**

**No new drift beyond #317's original finding exists as of this commit.**

## Finding 4 — current per-role tool-set assignment

Two live sources of truth today, by design (ADR-0032's decision, as
implemented):

- **`agent/mcp_roles.py`'s `MIGRATED_ROLE_TOOL_NAMES`** owns the tool-name
  list outright for the three fully-migrated roles:
  - **principal** — 16 tools (design-record management, the design-loop
    tools, and the two search tools; deliberately small per this repo's own
    tool-selection-reliability testing).
  - **systems** — 33 tools (calculation/conversion tools plus every
    ingestion/lookup tool: 3GPP, ETSI, FCC, USPTO, arXiv, Digi-Key, Mouser,
    Nexar, ink).
  - **verification** — 4 tools (`read_document`, `search_knowledge`,
    `search_design_records`, `extract_components`).
  - Each name in these lists is verified live against the real MCP server's
    wire-level `tools/list` response by `tests/test_mcp_roles.py` (per that
    module's own docstring) — not just asserted in Python.
- **`agent/main.py`'s `ROLE_SPECS[key].tools`** still owns the tool-*object*
  list for the three roles that remain on the old direct-call path, because
  each holds at least one of the 15 tools that shell out to an external
  solver binary (`simulation/*.py`'s `subprocess.run()` callers, plus
  FreeCAD/arXiv/patent ingestion) and — per #372/#376's own investigation —
  needed to stay there until the Windows stdin-inheritance hang (#372) was
  fixed:
  - **microwave** holds the Qucs/LTspice/ngspice/Xyce solver tools plus
    calculation/conversion tools (confirmed at `agent/main.py:1836` onward).
  - **antenna** holds NEC2++/openEMS/HFSS/Elmer/Palace/MEEP/gprMax/
    gerber2ems/OpenParEM plus patch-antenna calculation tools (confirmed at
    `agent/main.py:1959` onward).
  - **test** holds all of the above solver tools plus Touchstone-file
    tooling and `compile_lab_test_plan` (confirmed at `agent/main.py:2044`
    onward).
  - `agent/mcp_roles.py`'s `_allowed_tool_names_for_role()` reads these
    three roles' filters *from* `ROLE_SPECS[key].tools` directly (not a
    second hand-copied list), so the old and new construction cannot drift
    apart for these three roles while both exist.
- **`_PRINCIPAL_DIRECT_TOOLS`, the list issue #316's own body worries about
  (`ROLE_SPECS`'s dead all-tools principal entry vs. the list actually
  used) no longer exists in `agent/main.py` at all.** Confirmed by direct
  search: zero references. Principal is fully migrated; its filter is
  sourced from `MIGRATED_ROLE_TOOL_NAMES["principal"]`, which was verified
  against `_PRINCIPAL_DIRECT_TOOLS`'s old 16-tool list at the time of #318
  and is now the sole copy. The 91-tool-principal reliability regression
  issue #316 was written to guard against cannot reoccur through this path,
  because there is no longer a second, larger list it could accidentally
  read from.
- **The provenance-integrity guardrail (issue #158,
  `_assert_calculated_provenance_is_tool_backed`) has its new home**, per
  issue #316's own user story 6: `agent/mcp_roles.py`'s
  `provenance_integrity_guardrail`, wired as an Agents-SDK `output_guardrail`
  on every migrated role's `Agent` (`agent/mcp_roles.py:445`). The original
  `_assert_calculated_provenance_is_tool_backed` (`agent/main.py:2358`)
  remains live for the three still-old-path roles.

## What this means for issue #316

Issue #316's body describes the problem and the desired end state
accurately, and its Implementation/Testing Decisions sections are exactly
right about what was needed — but its body was written 2026-09-09 and was
never updated as the work it called for actually landed. Concretely:

| #316's ask | Status | Evidence |
|---|---|---|
| 0th audit ticket | **Done** | #317, closed, PR #333 — found and fixed `correlate_simulated_and_measured`'s drift |
| Expand (new `mcp_servers=[server]` + `create_static_tool_filter` path, old path untouched) | **Done** | #318, closed, PR #339 |
| Verify (behavioral parity: latency, error surfacing, argument coercion) | **Done** | #319, closed, PR #373 |
| Contract (delete old wrapper layer) | **Done for 3 of 6 roles; intentionally deferred for the other 3** | #320 (closed, narrowed scope), #376 (closed, PR #463, did the narrowed 37-tool deletion), #377 (closed, PR #441, proved live-conversation viability first) |

Two real blockers surfaced during that work and are also already resolved or
tracked:

- **The Windows subprocess-hang blocker** that stopped microwave/antenna/
  test from migrating (#372) is fixed (PR #475) — root cause was solver-
  subprocess stdin inheriting the MCP transport's own stdin pipe, not a
  blocked event loop as first suspected.
- **Whether the fix unblocks a full migration of the remaining three roles**
  is already an open, explicitly-scoped investigation ticket:
  **issue #479** ("Investigate whether microwave/antenna/test can now fully
  migrate off the old wrapper layer"). Two smaller, independent gaps
  disclosed during #372's verification are also already filed:
  **#477** (cancelling/timing out a solver call doesn't kill its
  subprocess) and **#478** (a running solver call blocks its whole session
  from answering anything else).

**Recommendation, not an action taken unilaterally by this pass:** issue
#316 should either be closed with a comment pointing at #317/#318/#319/#320/
#372/#376/#377 as the work that satisfied it (leaving #479/#477/#478 as the
correctly-scoped, already-filed remaining work), or have its body edited to
strike the "create four sub-tickets" instruction and replace it with a
pointer to the same chain — so a future reader doesn't repeat this same
re-discovery. This document's own findings support either path; picking
between them is a judgment call for whoever owns the tracker, not something
this read-only audit pass settles on its own.

**This audit deliberately does not create three new Expand/Verify/Contract
sub-issues of #316.** Doing so would duplicate #318/#319/#320's already-
merged work and collide with #479's already-open, already-correctly-scoped
investigation of the one genuine remaining question (should the last three
roles migrate too). Filing three more tickets that restate work already
closed would itself become exactly the kind of stale-documentation hazard
this repo's own `CLAUDE.md` warns about under "Planning docs are not a
status source."

## Limitations of this audit

- This is a static, read-only re-count against the code as of this commit.
  It does not re-run `tests/test_mcp_roles.py`, `tests/test_mcp_server.py`,
  or `tests/test_mcp_tool_call_parity.py` itself — it trusts their titles
  and the closed issues' own acceptance criteria as evidence those checks
  already passed, rather than re-executing them.
- The docstring-drift check compares exact docstring text via Python's
  `ast` module; a semantic drift expressed through *code* differences (the
  wrapper actually behaving differently from the implementation function it
  wraps, not just describing it differently) is out of scope for a
  docstring diff and was not checked here.
- `#479`'s own investigation (six-server connection-manager scaling,
  mid-handoff-to-unconnected-role behavior at 6 roles, and interaction with
  #477/#478) was not attempted or re-verified by this pass — it is cited as
  the correctly-scoped ticket for that work, not redone here.
