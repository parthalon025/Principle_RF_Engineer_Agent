---
status: accepted
---

# Tool registration has one source of truth — the MCP server — not a second hand-written wrapper file

Two real bugs this session named the same root cause. Issue #276
(`lookup_nexar_part_data`) and issue #288 (`run_freecad_fem_mesh_geometry`)
were each fully implemented and fully tested, and each was invisible to the
model anyway: neither was ever added to `agent/main.py`'s `@function_tool`
list, only to `mcp_server/server.py`'s. Issues #271 and #277 are the same
failure at one remove — a tool's *existing* wrapper kept working, but its
exposed docstring was never updated for the new capability, so the model had
no way to discover it. All four trace to the same shape: this repo hand-
maintains **two** parallel registrations of the same tool (`agent/main.py`'s
`@function_tool` wrapper, `mcp_server/server.py`'s `@mcp.tool()` wrapper) —
each a second, independently-typed copy of the function's signature and
docstring — and nothing has ever checked that the two agree.

`docs/llm-tool-registry-completeness-patterns.md` researched how other
frameworks avoid this. The load-bearing finding: OpenAI's own Agents SDK
already ships `mcp_servers=[server]` — an Agent can consume an already-
running MCP server's tools directly, with **no** hand-written wrapper
function at all, and the SDK's `create_static_tool_filter`/
`ToolFilterContext` gives per-Agent tool subsetting natively (source:
`src/agents/mcp/server.py`, `docs/mcp.md`, quoted in full in that research
file). This is a direct, first-party substitute for what `agent/main.py`'s
`ROLES` dict does today by hand.

**Decision: retire `agent/main.py`'s wrapper layer. `mcp_server/server.py`
becomes the only place a tool is ever registered**, and every role's `Agent`
consumes it through `mcp_servers=[server]` plus a per-role
`create_static_tool_filter`/`ToolFilterContext` callable in place of the
hand-built `ROLES` tool lists. This is Option A of the four the research
laid out — the one that makes the #276/#288 failure *structurally
impossible* (there is only one surface left to forget) rather than merely
guarded against it.

## Considered and rejected

- **Cross-file set-equality test** (assert `agent/main.py`'s registered
  names == `mcp_server/server.py`'s). Cheap, same-day. Rejected as the
  standing architecture: it converts a silent gap into a loud test failure
  but leaves the duplication — and the four-file edit per new tool — in
  place forever. Worth keeping in mind as a stopgap if the full migration is
  ever paused partway.
- **Live-referenced docstrings** (`functools.wraps`/`__doc__` aliasing so a
  wrapper's exposed description can't drift from its implementation's).
  Fixes #271/#277's specific failure but not #276/#288's — a wrapper that
  doesn't exist yet has no docstring to alias. Namespace collapses onto one
  file under this ADR's decision anyway, since a tool decorated once has no
  second copy to keep live.
- **Generalizing `assert_all_tools_categorized()`** (the import-time check
  `orchestration/policy.py` already runs for `policies/tool_policy.yaml`
  categorization) to also cover role-assignment and cross-file parity.
  Same rejection as the set-equality test: it is this repo's own idiom, and
  a reasonable fallback, but a fail-closed check on a duplication is still a
  duplication.

## Consequences

- **This is a real rewrite, not a patch.** All 87+ `@function_tool` wrappers
  in `agent/main.py` and the `ROLES`-construction code go away; nothing in
  this ADR claims that work is done. A tracking issue for the migration
  itself should be filed separately and scoped/staged rather than attempted
  in one pass.
- **Needs a live behavior check before it ships**, not just a passing test
  suite. Today's tool call is a direct in-process Python call; after this
  change it routes through the Agents SDK's MCP client/transport layer.
  Nothing in this session confirmed that round trip is behaviorally
  identical (same latency class, same error surfacing, same argument
  coercion) for this repo's actual tool shapes — particularly the several
  `@function_tool(strict_mode=False)` wrappers whose whole reason for being
  is a schema shape (open-ended dicts, variable-length lists) the SDK's
  default strict mode rejects. That needs to survive the move to
  `to_function_tool`'s MCP-schema conversion path before this is trusted in
  production.
- **`policies/tool_policy.yaml`'s role-list may partly fold into the new
  per-role `ToolFilterContext` callables** — this ADR does not settle
  whether that file's categorization purpose (`read_only`/
  `approval_self_gated`/etc., enforced by `assert_all_tools_categorized()`)
  survives unchanged, merges into the filters, or splits. That is
  implementation work, not a re-litigation of this decision.
- **MCP itself gives no session/role-based tool filtering** (confirmed
  directly against the spec text in the research file) — only a newly-
  specified, still-Draft, auth-scope-based one (SEP-1881). The per-role
  split stays an Agents-SDK-side concern (`ToolFilterContext`), not
  something pushed onto the MCP server itself.

## Corrections

### 2026-09-09 — the live behavior check this ADR asked for ran, and half the tool surface fails it

**What this ADR said:**

> Nothing in this session confirmed that round trip is behaviorally
> identical (same latency class, same error surfacing, same argument
> coercion) for this repo's actual tool shapes — particularly the several
> `@function_tool(strict_mode=False)` wrappers whose whole reason for being
> is a schema shape (open-ended dicts, variable-length lists) the SDK's
> default strict mode rejects. That needs to survive the move to
> `to_function_tool`'s MCP-schema conversion path before this is trusted in
> production.

**What is true instead:** issue #319 ran that check
(`tests/test_mcp_tool_call_parity.py`). Latency and error-surfacing are
fine — a real `SimulatorError`-style exception is caught and turned into
plain text on both paths, just with different wording and envelope shape,
and the added stdio/MCP transport hop costs milliseconds, not a gross
regression. But for every tool whose implementation shells out to its own
subprocess (`run_nec2_simulation` and, by the same code shape, every other
`run_*_simulation` tool — NEC2++, openEMS, HFSS, Elmer, Palace, MEEP,
gprMax, Qucs, LTspice, ngspice, Xyce, gerber2ems — roughly half this repo's
real engineering tool surface), the round trip is not behaviorally
different, it does not complete at all: on native Windows the call hangs
indefinitely (confirmed with the raw `mcp` client, independent of the
OpenAI Agents SDK entirely — see the test file's module docstring),
root-caused to FastMCP's un-threaded synchronous tool dispatch combined
with `mcp`'s own Windows-specific subprocess-launch path, both third-party,
neither this repo's to patch directly. Confirmed Windows-specific, not a
general `mcp`/`anyio` defect: the same test suite run against the same code
inside a Linux container completes normally, in seconds, with no hang at
all — `tests/test_mcp_tool_call_parity.py`'s three affected tests branch on
platform for exactly this reason (CI runs `ubuntu-latest` only). The two other findings the same
verification pass turned up (a missing `env` pass-through and a 5-second
client-session timeout the SDK defaults to) were real bugs in this ADR's
own follow-on construction (`agent/mcp_roles.py`, issue #318) and are fixed
there, not corrections to this ADR's reasoning.

**Raised by:** issue #319, `tests/test_mcp_tool_call_parity.py`.

**The Decision is unaffected.** `mcp_server/server.py` remains the one
place a tool is registered, and nothing here disputes that direction. What
changes is the answer to the open question this ADR itself posed: it is not
"behaviorally identical, modulo wording" for the subprocess-shelling half
of the tool surface — it is "does not work yet." Issue #320 ("Contract:
delete the old `agent/main.py` wrapper layer") is blocked on this finding
in substance, not only on #319 closing formally: deleting the OLD direct-
call path today would take every `run_*_simulation` tool down on Windows
with no fallback. That blocker is recorded on #320 directly, not only
here. The upstream `mcp`/`anyio` limitation itself — third-party, not
this repo's code, and a distinct piece of work from #320's "delete the
old path" scope — is tracked separately as #372, so it has a home that
does not depend on either #319 or #320 staying open.
