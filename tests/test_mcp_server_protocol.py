"""Real MCP stdio-protocol test for mcp_server/server.py (issue #85).

UNLIKE tests/test_mcp_server.py, which imports `mcp_server.server` as a
Python module and calls its functions directly, in-process -- this file
spawns `mcp_server/server.py` as the real, separate program it is
(`FastMCP("principal-rf-engineer")`, launched via `mcp.run()` under stdio
transport) and drives it over genuine MCP stdio JSON-RPC, using the `mcp`
package's own client primitives (`mcp.client.stdio.stdio_client` +
`mcp.ClientSession`) -- the same interface a real external MCP client
(Claude Desktop, another agent) would use. This proves the server process
itself works: protocol handshake, tool discovery, and JSON-RPC argument/
result marshalling, none of which a same-process function call exercises.

`calculate_wavelength` is the one tool exercised for the real round-trip
call: it is `read_only`/`calculation`-category (policies/tool_policy.yaml),
takes a plain numeric argument, and (with no design_id) returns a plain
float with no database connection or external binary involved -- keeping
this test's resource requirements at zero beyond the `mcp` package itself,
which mcp_server/server.py already depends on.
"""

import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from rf_tools.calculations import wavelength

REPO_ROOT = Path(__file__).resolve().parent.parent


def _server_params() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        cwd=str(REPO_ROOT),
    )


@pytest.mark.asyncio
async def test_lists_tools_over_the_real_protocol_and_finds_calculate_wavelength():
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()

    tool_names = {tool.name for tool in result.tools}
    assert "calculate_wavelength" in tool_names


@pytest.mark.asyncio
async def test_calls_calculate_wavelength_over_the_real_protocol_and_gets_correct_result():
    frequency_hz = 2.45e9
    expected = wavelength(frequency_hz)

    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("calculate_wavelength", {"frequency_hz": frequency_hz})

    assert result.isError is not True
    assert result.structuredContent is not None
    assert result.structuredContent["result"] == pytest.approx(expected)
