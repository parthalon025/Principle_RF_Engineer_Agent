# LLM tool registration and registry-completeness patterns, read from the primary sources

**Research date:** 2026-09-09
**Informs:** an upcoming ADR on this repo's tool-registration process
**Trigger:** two real merged tickets this session (#276, #288) each shipped a fully-implemented,
fully-tested tool whose sibling was wired onto both `agent/main.py` and `mcp_server/server.py`,
but the new one onto neither — invisible to the model despite passing its own unit tests. Two
more (#271, #277) extended an already-registered tool's implementation with a new field but never
updated that tool's *exposed* docstring — the one the wrapper carries, not the one the internal
implementation function carries, which is the only one the model ever sees.

## What this is, and how much weight it carries

*In plain terms first, because the rest of this document leans on the words "tool," "docstring,"
and "schema" a lot:* a **tool** here is a Python function an LLM agent is allowed to call — think
"the model can ask to run `calculate_link_budget(freq_ghz=10)`." A **docstring** is the paragraph
of prose right under a function's `def` line describing what it does and what its arguments mean.
A **JSON schema** is the structured, machine-readable version of that same information — the
actual thing sent to the model alongside "here are your tools" on every turn. The question this
research answers is: in other frameworks, is the docstring *the* schema (one edit, one place), or
is the docstring one artifact and the schema a second, separately-maintained artifact (two edits,
two places, and — as this repo has now observed twice — an easy way for the two to drift or for
one to never get written at all)?

**This is desk research, not a working prototype or a benchmark.** Nothing here was run against
this repo's own code, and no claim below is a measurement — everything is either a quotation from
a primary source (real SDK source code, pinned to a commit; the actual official docs page; the
actual protocol spec text; a real GitHub issue) or an explicit statement that a claim could not be
verified. Since nothing here is `MEASURED`/`CALCULATED` in this programme's physics sense, the
provenance tag used throughout is simpler:

- **VERIFIED** — the exact source text was fetched and is quoted (or closely paraphrased with a
  citation) below. Where I re-fetched and hand-checked a claim myself during this write-up
  (rather than only trusting a research pass's paraphrase), it says so explicitly.
- **NOT VERIFIED** — a source could not be reached, or a targeted search came up empty. Recorded
  as an explicit gap, never filled from memory or inference.

**Method:** five parallel, narrowly-scoped research passes, one per numbered question in the
originating brief, each fetching primary sources directly (GitHub raw source, official docs,
the MCP spec site, live GitHub issues). Afterward, the highest-stakes and most surprising claims —
the wording of the MCP spec's `tools/list` per-client rule (across two spec versions), the Agents
SDK's own MCP tool-filtering docs, the docstring-parsing code path, and the two cited GitHub issue
numbers — were independently re-fetched and hand-quoted by me, not merely accepted from a
delegate's summary. That's noted per-section as "verified directly" below.

**Also read (read-only, to ground the closing Options section in what this repo actually has):**
`agent/main.py`, `mcp_server/server.py`, `policies/tool_policy.yaml`, `orchestration/policy.py`,
`tests/test_mcp_server.py`, `tests/test_agent_roles.py`. No file was modified.

---

## 1. OpenAI Agents SDK's `@function_tool` — the docstring already *is* the schema, but nothing scans for you

**Source:** `openai/openai-agents-python`, pinned commit `83c737fd0b8d9a53bd39fa2a0856070417bb0bd3`
(fetched 2026-09-09) — `src/agents/tool.py` and `src/agents/function_schema.py`; official docs at
`openai.github.io/openai-agents-python/tools/`.

**Where it lives.** `function_tool` is a decorator in `src/agents/tool.py`. Its own docstring
states the contract plainly (quoted verbatim): *"Decorator to create a FunctionTool from a
function. By default, we will: 1. Parse the function signature to create a JSON schema for the
tool's parameters. 2. Use the function's docstring to populate the tool's description. 3. Use the
function's docstring to populate argument descriptions."* `VERIFIED` (direct source fetch).

**How the docstring becomes a schema.** The actual parsing lives in `src/agents/function_schema.py`,
in `generate_func_documentation()`. It uses the third-party **griffe** library to parse the
docstring text: `Docstring(doc, lineno=1, parser=resolved_style).parse()`, with the docstring
*style* (Google/NumPy/Sphinx) auto-detected by regex, breaking ties `sphinx > numpy > google`. The
function-level description is pulled from the first plain-text section of the parsed docstring;
per-argument descriptions are pulled by matching each parameter's name against the docstring's
parsed parameter list. Those two extracted values then flow straight into the Pydantic model the
SDK builds for the tool's arguments — each field's `description=` comes from the matched docstring
text — and into the tool's own top-level `description`. `VERIFIED` (direct source fetch,
re-confirmed by me independently — I re-fetched `function_schema.py` and quoted the griffe call,
the style-detection literal, and the `Field(..., description=field_description)` line myself,
separately from the delegate's read).

**So: does editing only the docstring change what the model sees, with no other file touched?**
Structurally, **yes** — there is no separate stored copy of the description anywhere in this path;
it is re-derived from the current docstring text every time `function_tool`/`function_schema` runs.
*In plain terms: the SDK doesn't keep a second copy of "what this tool does" anywhere — it reads
the comment block under the function every time and turns it into the schema on the spot, so
editing the comment IS editing the schema.* Caveat, stated plainly: this is a structural read of
the code path, not something I executed as a live before/after test this session — I did not spin
up the SDK and diff a schema before and after a docstring edit. `VERIFIED` (source-level), `NOT
VERIFIED` (as an executed regression).

**Auto-discovery: confirmed absent.** The official docs page shows only the manual pattern —
`Agent(name=..., tools=[fetch_weather, read_file])` — and no page in the docs, and no code path in
the repo, scans a module or package for `@function_tool`-decorated functions and builds a tool list
automatically. A developer must build the list by hand, every time. `VERIFIED` (docs fetched;
absence confirmed by the delegate's search of both docs and source, not independently re-searched
by me byte-for-byte — flagging that the *absence* claim rests on one pass's search, not two).

**Why this matters for this repo:** this piece of the SDK is not the source of the #276/#288
failure mode — the SDK already collapses "write the docstring" and "expose the description" into
one edit for a *single* function. The repo's actual exposure comes from having **two** separate
`@function_tool`/`@mcp.tool()` wrapper functions per tool (see §5 below and the Options section) —
a problem this SDK feature does not touch, because it operates per-function, not across the two
files this repo hand-keeps in sync.

---

## 2. The Agents SDK's own MCP integration — a single-source-of-truth path already exists, built by OpenAI

**Source:** same repo/commit; `src/agents/mcp/server.py`, `src/agents/mcp/manager.py`,
`src/agents/mcp/util.py`; `docs/mcp.md`. The "Tool Filtering," caching, and basic-usage passages
below were **re-fetched and quoted by me directly** from `docs/mcp.md` during this write-up, not
only from a delegate's paraphrase.

**A first-party adapter exists, and it removes the per-tool wrapper entirely.** `MCPServerStdio`,
`MCPServerSse` (marked deprecated as a transport), and `MCPServerStreamableHttp` — all in
`src/agents/mcp/server.py` — let an already-running MCP server's tools become callable by an Agent
directly:

```python
agent = Agent(
    name="Assistant",
    instructions="Use the MCP tools to answer the questions.",
    mcp_servers=[server],
    model_settings=ModelSettings(tool_choice="required"),
)
```

No hand-written wrapper function is written per tool in the agent's own code — the MCP server *is*
the tool source. `VERIFIED` (direct fetch of `docs/mcp.md`).

**What gets forwarded automatically, and the one real caveat.** `src/agents/mcp/util.py`'s
`to_function_tool` builds each `FunctionTool` with `description=` and `params_json_schema=` taken
directly off the MCP tool object returned by the server's `tools/list` — not hand-authored in agent
code. The caveat, from the source itself: *"MCP spec doesn't require the inputSchema to have
`properties`, but OpenAI spec does"* — so the SDK patches in an empty `properties: {}` when the MCP
server omitted it, and optionally runs a strictness-tightening pass when
`convert_schemas_to_strict` is set. So: automatic, but passed through a small compatibility shim,
not a byte-identical passthrough. `VERIFIED` (delegate's direct source fetch; not independently
re-fetched by me).

**Per-role tool subsetting is SDK-native — a direct substitute for this repo's `ROLES` dict.**
Quoted directly from `docs/mcp.md`, "Tool filtering" (I re-fetched this myself):

> *"Use `create_static_tool_filter` to configure simple allow/block lists... For more elaborate
> logic pass a callable that receives a `ToolFilterContext`."*

`ToolFilterContext` exposes *"the active `run_context`, the `agent` requesting the tools, and the
`server_name"* — meaning a filter function can branch on which agent (role) is asking, e.g. "only
`systems`-role agents see `run_hfss_simulation`." One MCP server, many agents, each seeing a
different tool subset — decided at the SDK layer, not by hand-building a second `ROLES` dict in
`agent/main.py`. `VERIFIED` (directly re-fetched and quoted by me).

**Caching has a real operational implication.** Quoted directly: *"Set it to `True` only if you are
confident that the tool definitions do not change frequently. To force a fresh list later, call
`invalidate_tools_cache()` on the server instance."* With caching off (the pattern shown in the
basic example), a docstring edit on the MCP server side is picked up on the very next agent run,
automatically. With caching on, a long-running process would keep serving a stale description until
someone calls `invalidate_tools_cache()` or restarts it. `VERIFIED` (directly re-fetched by me).

**First-party worked examples** exist at `examples/mcp/` and `examples/hosted_mcp/` in the same
repo, per the docs' own "Further reading" links. `NOT independently verified` — I did not fetch
these example files myself, only the docs page that names them.

---

## 3. The MCP spec — per-client tool filtering is now (barely, newly) in-spec, but only as an auth-scope mechanism

**Sources, both re-fetched and quoted directly by me:**
`https://modelcontextprotocol.io/specification/2025-06-18/server/tools` and
`https://modelcontextprotocol.io/specification/2026-07-28/server/tools`; plus
`https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1881` (SEP-1881).

**Baseline mechanics.** A server that supports tools declares `{"capabilities":{"tools":
{"listChanged": true}}}`; `tools/list` is a paginated request/response (`{cursor?: Cursor}` in,
a list of `Tool` objects — `name`, `title`, `description`, `inputSchema`, etc. — out);
`notifications/tools/list_changed` tells a subscribed client the set has changed. `VERIFIED`
(directly fetched, both versions).

**The finding: the spec changed underneath this exact question, and only recently.** I fetched
both the 2025-06-18 and the 2026-07-28 spec pages myself and diffed the "Capabilities" section by
hand. The **2025-06-18** version says nothing at all about per-connection variation — its
Capabilities section is just the `listChanged` declaration, full stop. The **2026-07-28** version
(the current one as of this research) adds an entire paragraph that was not there before:

> *"Servers that declare the `tools` capability **MUST** respond to `tools/list` requests with the
> set of tools currently available to the requesting client. This set **MAY** be empty and **MAY**
> change over time..., but **MUST NOT** vary per-connection or as a side effect of other requests
> on the connection. The set **MAY** vary by the authorization presented on the request — for
> example, returning only the tools the caller's granted scopes permit — since credentials are
> per-request input, not connection state."*

`VERIFIED` (both spec pages fetched and quoted directly by me, independently, during this
write-up — this is not a passthrough of the delegate's claim).

*In plain terms:* the protocol explicitly **forbids** "this session/connection gets tool set A,
that session gets tool set B" as a property of which connection you happen to be on. It **allows**
"this API key/token gets tool set A, that token gets tool set B" — but only because the token is
defined as something attached to *each individual request*, not something the server is allowed to
remember about *the connection as a whole*. That is a real, specific distinction, not a technicality
free lunch: reproducing this repo's `systems`/`microwave`/`antenna` role split purely on the MCP
server side would mean minting a distinct credential/scope per role and having every request carry
one — not just remembering "this session is the antenna agent."

**Confirmed at the wire level: no client-supplied filter field exists.** `ListToolsRequest` extends
`PaginatedRequest`, whose only parameter is `{ cursor?: Cursor }` — no role, scope, or filter field
a client can pass. `VERIFIED` (delegate's direct fetch of the spec repo's `schema.ts`; **not**
independently re-fetched by me — flagging this one honestly since it's the one wire-level claim in
this section I did not personally re-check).

**A draft proposal formalizes exactly this pattern, and it is not yet finalized.** SEP-1881,
*"Scope-Filtered Tool Discovery,"* status **Draft** as of this research (I fetched the issue myself
and confirmed both the title and status directly): it proposes that *"an MCP server returns only
the tools authorized for the scopes contained in the client's current access token,"* omitting
unauthorized tools from `tools/list` entirely rather than returning them with an access-denied
error, and it explicitly frames itself as formalizing "a server behavior already happening in
practice" rather than introducing new capability — but it is still a **Draft**, not part of the
ratified spec. `VERIFIED` (directly fetched and confirmed by me). Companion proposals referenced in
the same thread — SEP-1880 "Tool-Level Scopes" and SEP-1821 "Dynamic Tool Search" — were **not**
independently fetched; `NOT VERIFIED`, noted rather than assumed.

**Bottom line for this section:** MCP itself gives this repo no session-based or role-remembered
tool-subsetting knob, only an auth-scope-based one, newly written into spec (absent as of
2025-06-18) and still partly in Draft (SEP-1881). The Agents-SDK-side `ToolFilterContext` from §2 —
a per-Agent-instance filter over one already-connected MCP server, no auth-scope modeling required
— is the more direct fit for what this repo's `ROLES` dict is actually doing today.

---

## 4. Other frameworks — the manual-list vs. reflection-based-auto-discovery split, in the wild

Two of the four named frameworks were researched in depth (LangChain and Semantic Kernel); the
delegate explicitly chose these two as a useful contrast pair and did not attempt LlamaIndex or
AutoGen — recorded here as `NOT RESEARCHED`, not as a negative finding about them.

### LangChain — same shape of problem this repo has, but only for half of it

**Source:** `github.com/langchain-ai/langchain`, `master` branch, commit `a4e7e510d3c353a0c0674ada231269bce2271adc` at fetch time — `libs/core/langchain_core/tools/{convert,structured,base}.py`.

Registration is **manual list-building**, not auto-discovery. The `@tool` decorator
(`tools/convert.py`) wraps one function into one `BaseTool`/`StructuredTool`. Grouping many tools
requires `BaseToolkit.get_tools()` (`tools/base.py`), which is declared `@abstractmethod` — every
concrete toolkit author must implement it themselves, typically by hand-populating a list. No
`inspect.getmembers`-style scan exists anywhere in this path. `VERIFIED` (delegate's direct source
read with line citations; not independently re-fetched by me).

The **description** the model sees, however, does come from one canonical place — *for tools built
through the decorator path*: `structured.py`'s `StructuredTool.from_function` falls back to
`source_function.__doc__ or None` when no explicit description is given; `convert.py`'s `@tool`
does the same (`tool_description = tool_description or dec_func.__doc__`). So editing only the
docstring is sufficient there too — **but only for that one construction path**. A hand-subclassed
`BaseTool` with its own `description = "..."` class attribute is a second, equally valid pattern in
the same framework, and *that* one would need a second edit if the docstring changed. `VERIFIED`
(delegate's direct source read, line-cited).

### Semantic Kernel (Python) — decorate the method, the framework finds it

**Source:** `github.com/microsoft/semantic-kernel`, `main` branch —
`python/semantic_kernel/functions/kernel_plugin.py` (lines 215–249, 409) and
`kernel_function_decorator.py` (lines 13, 62).

This is a genuine contrast to LangChain. `KernelPlugin.from_object()` takes a plugin instance or
class and **walks the whole thing via `inspect.getmembers`** — methods, plain functions, and
coroutine functions — keeping only those carrying a `__kernel_function__` marker:

```python
candidates = inspect.getmembers(plugin_instance, inspect.ismethod)
candidates.extend(inspect.getmembers(plugin_instance, inspect.isfunction))
candidates.extend(inspect.getmembers(plugin_instance, inspect.iscoroutinefunction))
functions = [
    KernelFunctionFromMethod(method=candidate, plugin_name=plugin_name)
    for _, candidate in candidates
    if hasattr(candidate, "__kernel_function__")
]
```

A second, independent instance of the same check exists at line 409. The decorator itself stamps
the description directly onto the function object at decoration time:
`setattr(func, "__kernel_function_description__", description or func.__doc__)`
(`kernel_function_decorator.py:62`). *In plain terms:* a developer decorates a method with
`@kernel_function` on a class, and that is the entire registration act — no separate list exists to
forget to update, because `from_object`'s scan finds every decorated method on the class by itself.
`VERIFIED` (delegate's direct source read with line citations; not independently re-fetched by me,
but the exact code shape — a metaclass-free `inspect.getmembers` scan gated on a decorator-set
attribute — is a well-known, easily-checkable pattern and internally consistent with the two
docstring quotes given).

**Why this pair matters for this repo:** LangChain shows "the same failure shape this repo has" —
a human-maintained list a developer must remember to update — confined to only the schema-grouping
half of the problem (the docstring-as-description half is already solved there). Semantic Kernel
shows what fully closing the gap looks like: decorate once, on the class, and let reflection do the
finding. **Framework-agnostically, this is exactly the shape of fix available to this repo without
adopting a different SDK** — see Option C/D below.

---

## 5. "Implemented but unreachable" as a failure mode — it is real, it recurs, and one real codebase already fixed half of it

### 5a. Two live, open, primary-source instances of the exact symptom

Both issues below were fetched and confirmed to exist by me directly (title and repo verified,
not taken on a delegate's word alone), because an issue number and repo name are exactly the kind
of specific claim that is easy to get subtly wrong and needs to be checked, not trusted.

1. **`NousResearch/hermes-agent` #51587** — *"MCP server tools connect and are enabled, but never
   surface into the agent's session toolset."* Confirmed real: the MCP server connects, tool
   discovery succeeds, configuration shows the tools enabled — but *"the agent does not have any
   mcp_shopmonkey_* tools in its toolset"* at run time, persisting across restarts. Filed **P1,
   no workaround**. `VERIFIED` (directly fetched by me). **Status: open as of this research — no
   confirmed structural fix has landed for this specific issue.** `NOT VERIFIED` as fixed.
2. **`github/copilot-sdk` #2356** — *"tools declared by a `custom_agents` agent are announced but
   not callable by the model."* Confirmed real: tools declared in an agent's own `tools:` list are
   reported as selected but silently never reach the model's callable set — *"no errors or
   warnings... only filesystem inspection or event analysis reveals the issue."* The only
   documented workaround is to route tools through a different mechanism (`available_tools`)
   entirely, not a fix to the broken path. `VERIFIED` (directly fetched by me). **Status: open, no
   structural fix confirmed.** `NOT VERIFIED` as fixed.

Both are real, on-point, and currently unresolved — reported here as **evidence the failure mode
recurs across unrelated codebases**, not as evidence anyone has shipped a fix for either.

### 5b. A real, shipped, structural fix — and a real, shipped, honest admission that it's only half the fix

`NousResearch/hermes-agent`'s own current developer docs (`website/docs/developer-guide/adding-tools.md`,
fetched directly) show the "add a tool" process **today**, and it is directly comparable to this
repo's process:

- **Step 1 — write the tool file.** A handler, a schema, an availability check, and a
  `registry.register(...)` call, in `tools/your_tool.py`.
- **Step 2 — "Register in Toolsets."** Quoted verbatim: *"In `toolsets.py`, add the tool name"* to
  either `_HERMES_CORE_TOOLS` (platform-wide) or a dedicated toolset. This step still exists and is
  still manual.
- **Step 3 — struck out, with an explanation why:** *"~~Add Discovery Import~~ (No longer needed) —
  Tool modules with a top-level `registry.register()` call are auto-discovered by
  `discover_builtin_tools()` in `tools/registry.py`. No manual import list to maintain — just create
  your file in `tools/` and it's picked up at startup."*

`VERIFIED` (directly fetched by me). The mechanism behind Step 3, per the delegate's direct read of
`tools/registry.py` (`NOT independently re-fetched by me`): a cheap text prefilter checks each file
in `tools/` for the literal words "registry" and "register," then `ast.parse`s only the files that
pass, looking for a **module-level** `registry.register(...)` call via a helper
`_is_registry_register_call()` — `discover_builtin_tools()` imports every file that qualifies,
memoizing the verdict on disk keyed by `(mtime_ns, size)` so it doesn't re-parse unchanged files
every startup.

**The important nuance for this repo's own problem:** Hermes Agent's own documentation is explicit
that removing the *import-list* step did **not** remove the *category-assignment* step, and that
skipping the surviving step reproduces exactly this repo's failure mode:

> *"you must still add the tool name to the appropriate list in `toolsets.py`... otherwise the tool
> registers but is never exposed to the agent."*

This is independent, real-world, currently-live confirmation that AST/reflection-based
auto-discovery genuinely eliminates *one* class of hand-maintained list (the "does this file get
imported at all" list — this repo's rough analogue is nothing, since Python imports at module load
already cover that here) **without** automatically eliminating a second, structurally different
class (the "which category/subset does this tool belong to" list — this repo's `tool_policy.yaml`
and `ROLES` assignment). The two are not the same problem and a fix for one does not imply a fix
for the other. `VERIFIED` (directly fetched by me).

### 5c. No named CI "registry completeness test" pattern was found

Searched directly for "tool registry completeness test," "reflection-based tool discovery," "assert
all tools registered," and related phrasing, both scoped to agent frameworks and broadened to
general Python CLI/plugin systems (Django management commands, Click command registries) per the
brief's own suggestion. **Result: no single named pattern and no specific real GitHub test file was
found** doing the canonical "`inspect.getmembers(module)` → diff against a registered set → assert
equal" shape. This is reported as a genuine negative result, not a stretch to a weak match: the
closest real artifact found is Hermes Agent's `discover_builtin_tools()` above, and that is a
**runtime auto-discovery mechanism**, not a **test-time completeness assertion** — a related idea,
not the same one. `NOT VERIFIED` — stated as an explicit gap rather than filled with an invented
example.

---

## What this repo already has — read directly, to ground the options below

Not part of the five brief items, but necessary context: the repo does not start from zero on this
problem.

- `agent/main.py` has **87** `@function_tool`-decorated wrappers; `mcp_server/server.py` has **87**
  `@mcp.tool()`-decorated wrappers — the counts currently match, consistent with
  `policies/tool_policy.yaml`'s own header comment that the two files are *"kept in sync by
  construction."* (Directly counted this session via `grep -c`, not from a doc's claim.)
- `orchestration/policy.py` already has a fail-closed completeness check for **one** of the four
  files — `assert_all_tools_categorized(tool_names)`, called once per tool surface at **import
  time**, raises if any registered tool name has no category anywhere in `tool_policy.yaml`:
  *"a tool NOT LISTED under any category here is refused too (fail closed)... precisely so a newly
  added tool can't ship unguarded just because nobody remembered to update this file."* This is,
  in miniature, exactly the "walk the registered names, assert every one is accounted for"
  discipline research item 5b went looking for — this repo already built it, for the categorization
  file specifically, and the file's own header records that a prior `/grill-with-docs` pass found
  it badly out of date against real tool names before this check existed.
- What that check does **not** cover: whether `agent/main.py` and `mcp_server/server.py` register
  the *same* set of names as each other (the exact #276/#288 failure — a tool present in one file
  and absent from the other can still pass `assert_all_tools_categorized` on each file
  individually, since each file's own name-set is compared only against `tool_policy.yaml`, never
  against the other file), and it says nothing about `tests/test_agent_roles.py`'s per-tool
  role assignments.
- `tests/test_mcp_server.py`'s `test_registered_tool_count_matches_old_plus_new` is the fragile
  count assertion named in the brief — currently a chain of ~30 hand-added `+ N` terms, each
  commented with the issue number that added it (lines 168–199 as read this session), which is
  exactly the shape the brief says has caused 5+ real merge conflicts.

---

## Limitations of this research

- Everything above is a **static read** of source, docs, and spec text — nothing was executed
  (no SDK was installed and run, no MCP server was actually queried live) to observe the described
  behavior in motion. Where that matters, it is flagged per-claim above (e.g. §1's docstring→schema
  claim).
- LlamaIndex and AutoGen (two of the four named frameworks in item #4) were not researched at all
  this pass — not a negative finding, an unresearched gap.
- SEP-1881 (§3) is a **Draft** proposal; its content, or its very existence, could change before
  any ratified spec version incorporates it.
- Neither GitHub issue in §5a has a confirmed structural fix landed as of this research date — both
  are cited as evidence the failure mode recurs, not as case studies in how it gets fixed.
- No causal "postmortem → structural fix" chain was found for Hermes Agent's own AST-based
  auto-discovery change (§5b) — only its current, shipped, documented before/after state. The
  originating issue or PR that motivated building `discover_builtin_tools()` was searched for and
  not found.
- A small number of citations (marked inline) rest on one research pass's fetch and were not
  independently re-confirmed by a second fetch during this write-up — each is flagged at the point
  it's used, rather than presented with the same confidence as the directly re-verified claims.

---

## Options for this repo

Each option below is a real, concrete tradeoff a human can pick from directly — not a disguised
recommendation. None is presented as "the" answer.

**Option A — Adopt the Agents-SDK-native MCP adapter; delete the `agent/main.py` wrapper layer.**
Point every role's `Agent(...)` at `mcp_servers=[server]` (§2) instead of a hand-built `tools=[...]`
list, and replace the `ROLES` dict's tool-subsetting with per-role `create_static_tool_filter`/
`ToolFilterContext` callables. `mcp_server/server.py` becomes the single place a tool is ever
registered; the #276/#288 failure mode (registered on one surface, absent from the other) becomes
*structurally impossible*, because there is only one surface left. **Tradeoff:** this is a rewrite,
not a patch — every one of the 87 `agent/main.py` wrappers and the `ROLES`-construction code
(`agent/main.py` ~2911–3077 as read this session) changes, and anything those wrappers currently do
*beyond* a plain passthrough to the implementation function (pre/post-processing, argument
renaming, etc. — not confirmed absent this session) would need to move somewhere else or be
re-justified. It also couples the repo's in-process tool calls to the Agents SDK's MCP transport
(stdio/SSE/streamable-HTTP round trip) where today they may be direct calls — a latency/architecture
change that needs its own evaluation, not a free consolidation.

**Option B — Keep both wrapper surfaces; replace the fragile pieces with a structural completeness
test.** Swap `tests/test_mcp_server.py`'s hand-incremented `expected = 11 + len(...) + 1 + 1 + ...`
chain (§ "What this repo already has") for a test that collects `agent/main.py`'s registered tool
names and `mcp_server/server.py`'s registered tool names and asserts **set equality** between them
— the direct, mechanical fix for the exact shape of the #276/#288 bug, and the kind of
reflection/introspection-based check research item 5b went looking for (no off-the-shelf named
pattern exists to borrow, per §5c, but the mechanism itself — walk both files' decorated symbols via
`inspect`, diff the two sets — is a same-day build, not a research problem). **Tradeoff:** cheap,
incremental, zero architecture change, and it extends a discipline this repo already half-has
(`assert_all_tools_categorized`, per the section above) to the one place it doesn't yet reach. But
it does not reduce the number of files a developer must edit — still 4–5 places per new tool — it
only guarantees a **loud, immediate test failure** instead of a silent gap when one of those edits
is missed. It also does nothing for the #271/#277 docstring-staleness failure mode: a set-membership
check can't tell that a wrapper's docstring is stale, only that the wrapper exists.

**Option C — Make the wrapper's docstring structurally incapable of drifting from the
implementation's.** Directly targets #271/#277. Since §1 confirms the SDK derives a tool's exposed
description from whatever docstring the *decorated function itself* carries, the fix is to stop
writing a second docstring on the wrapper at all — either decorate the implementation function
directly wherever architecturally possible, or, where a thin wrapper must stay (e.g. to adapt an
internal function's signature to the tool-calling convention), use `functools.wraps` (or an
equivalent explicit `wrapper.__doc__ = impl.__doc__`) so the wrapper's exposed docstring is *always*
a live reference to the implementation's, never an independently-typed copy — plus a cheap test
asserting that reference holds (e.g. `wrapper.__doc__ is impl.__doc__` or an equality check) so a
future edit that breaks the link fails loudly. **Tradeoff:** narrow and cheap — it fixes exactly the
docstring-divergence failure mode and nothing else (it does not touch the "wired onto neither
surface" failure from #276/#288, and doesn't reduce file count); it also requires auditing all 87
existing wrapper pairs once to establish the reference-not-copy pattern everywhere, and it only
helps where the wrapper's *only* job is passthrough — a wrapper that legitimately needs to describe
something different from its implementation (e.g. a narrower argument set) would need a real,
independently-justified docstring, and this pattern can't distinguish "legitimately different" from
"accidentally stale" without a human reading it.

**Option D — Extend this repo's own existing fail-closed pattern to cover role assignment and
cross-file parity, without adopting a new architecture.** `orchestration/policy.py`'s
`assert_all_tools_categorized()` (already real, already running at import time, per the section
above) is proof this repo can build and maintain exactly this kind of check itself. Generalize the
same idiom two ways: (1) an equivalent `assert_all_tools_have_role()` that fails import if any
registered tool name has no entry in whatever `tests/test_agent_roles.py` currently checks by hand,
and (2) fold Option B's cross-file set-equality check into the same import-time layer rather than a
separate pytest file, so a missing wrapper fails **at process start**, not just in CI. **Tradeoff:**
this is really Option B generalized and moved earlier in the pipeline (import time vs. test time) —
lowest-novelty, highest-consistency-with-existing-repo-idiom option, and it's the only one of the
four that treats all three currently-separate hand-sync points (category, role, cross-file parity)
as instances of one already-proven pattern rather than three different fixes. It carries the same
limitation as B: still 4–5 files to edit per tool, now with three fail-closed tripwires instead of
one, and it still does nothing for the docstring-staleness failure mode (pair with C for that).
