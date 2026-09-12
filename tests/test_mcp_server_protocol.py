"""Real stdio-protocol test for the MCP server (issue #85).

Every existing MCP server test (tests/test_mcp_server.py) imports
mcp_server.server as a Python module and calls its @mcp.tool()-decorated
functions directly, in-process. That proves the code *behind* the MCP
server is correct, but never that the server itself -- as a real external
MCP client would actually reach it -- works: tool discovery over the wire,
JSON-RPC argument marshalling, and the response round-trip are all
unverified by that suite.

This file closes that gap: it spawns mcp_server/server.py as a genuine
subprocess (`python -m mcp_server.server`, its real `mcp.run()` stdio
transport entry point) and drives it with the `mcp` package's own client
primitives (mcp.client.stdio.stdio_client + mcp.ClientSession) -- the same
library any real external MCP client (Claude Desktop, another agent) would
use. See issue #84 for the full rationale and issue #85 for this file's
acceptance criteria.

This follows this repo's established "spawn a real subprocess, no mocks"
testing convention (tests/test_nec2pp.py, tests/test_openems.py,
tests/test_ltspice.py) -- but here the process being spawned is this
repo's own real server code, not a fake standing in for a third-party
tool, and the interface is the `mcp` package's real client rather than raw
subprocess.run.

Tool choice for the round-trip call: calculate_wavelength -- a
read_only/calculation-category tool (policies/tool_policy.yaml) that takes
a plain numeric argument, returns a plain numeric result, and needs no
design_id, no database connection, and no external binary. Requires
nothing beyond the `mcp` package, already a core pyproject.toml dependency
backing mcp_server/server.py itself.

A future contributor adding wire-level (not just function-level)
verification for a new tool should extend this file.
"""

import sys
from contextlib import asynccontextmanager

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from rf_tools.patch_synthesis import wavelength

# The real server entry point (`if __name__ == "__main__": mcp.run()` in
# mcp_server/server.py), launched exactly as an external MCP client
# configured against this repo would launch it -- `python -m
# mcp_server.server` under stdio transport, no test-only entry point.
SERVER_PARAMS = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"])


@asynccontextmanager
async def connected_session():
    """Spawn the real server subprocess and complete the real MCP
    initialize handshake over stdio, yielding the connected session plus
    the handshake's own InitializeResult.

    Deliberately a plain async context manager, not a pytest(-asyncio)
    fixture: anyio's cancel scopes (which stdio_client/ClientSession use
    internally) must be entered and exited in the same asyncio Task, and a
    pytest-asyncio async-generator fixture's teardown runs in a different
    Task than the test body -- tearing this down across that boundary
    raises "Attempted to exit cancel scope in a different task than it was
    entered in". Used as `async with connected_session() as (session,
    init_result):` inline in each test instead, keeping setup, use, and
    teardown in one task."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            init_result = await session.initialize()
            yield session, init_result


@pytest.mark.asyncio
async def test_server_process_starts_and_completes_handshake():
    """A bare regression like a syntax error or crash-on-import in
    mcp_server/server.py would break a real external MCP client's connection
    attempt outright -- this confirms the subprocess actually starts and the
    protocol handshake completes, something test_mcp_server.py's
    function-level tests (which only ever import the module, never spawn
    it) wouldn't necessarily catch the same way."""
    async with connected_session() as (_, init_result):
        assert init_result.serverInfo.name == "principal-rf-engineer"


@pytest.mark.asyncio
async def test_list_tools_includes_calculate_wavelength():
    """A real MCP client's tool-discovery round trip: over the actual wire
    protocol, confirm a known, stable tool name is advertised. Catches a
    tool silently dropped from registration (but still present as a Python
    function on mcp_server.server) -- a regression no in-process test of
    that module's functions would ever exercise."""
    async with connected_session() as (session, _):
        result = await session.list_tools()
        names = {tool.name for tool in result.tools}
        assert "calculate_wavelength" in names


@pytest.mark.asyncio
async def test_call_tool_calculate_wavelength_matches_underlying_function():
    """The full JSON-RPC round trip for one real, deterministic tool call:
    tool discovery already proven above, then call_tool with known inputs,
    asserting the decoded result matches what rf_tools.calculations.
    wavelength already returns for the same input -- the way a real
    external MCP client calling this tool would experience it. This is
    NOT a re-test of wavelength()'s own math (test_calculations.py already
    covers that); it is a check that nothing is lost or mangled crossing
    the JSON-RPC argument-marshalling / response-serialization boundary."""
    frequency_hz = 2.4e9
    expected = wavelength(frequency_hz)

    async with connected_session() as (session, _):
        result = await session.call_tool("calculate_wavelength", {"frequency_hz": frequency_hz})

        assert result.isError is False
        # FastMCP's structured-content channel: the decoded, correctly-typed
        # result a real client would read programmatically.
        assert result.structuredContent == {"result": expected}
        # And the plain-text content block every MCP client also receives,
        # decoded the way a client without structured-content support would.
        assert float(result.content[0].text) == pytest.approx(expected)
