"""Issue #317 (ADR-0032 prefactor audit): `agent/main.py`'s `run_elmer_simulation`
`@function_tool` wrapper declared only `geometry`/`frequency_hz`/`timeout_s`,
while `mcp_server/server.py`'s sibling `@mcp.tool()` registration also exposed
`gmsh_executable`/`elmergrid_executable`/`elmersolver_executable` (the same
executable-path overrides `simulation.elmer.run_elmer_simulation` itself
accepts). An agent session had no way to point this tool at a non-default
gmsh/ElmerGrid/ElmerSolver install; the MCP surface already could.

This proves the three executable-override parameters are now part of the
agent-side wrapper's signature and are forwarded through untouched, mirroring
`tests/test_mcp_server.py`'s `test_run_elmer_simulation_calls_through` for the
sibling MCP tool surface, and `tests/test_ltspice_agent_wiring.py`'s documented
reason for going through the real `FunctionTool.on_invoke_tool` machinery
rather than a plain Python call: `@function_tool` wraps the original function
into a non-callable `Tool` object.
"""

from __future__ import annotations

import asyncio
import json

from agents.tool_context import ToolContext

import agent.main as agent_main


def _invoke_elmer_agent_tool(**kwargs):
    all_tools = (t for role in agent_main.ROLES.values() for t in role.tools)
    tool = next(t for t in all_tools if t.name == "run_elmer_simulation")
    args_json = json.dumps(kwargs)
    ctx = ToolContext(
        context=None,
        tool_name="run_elmer_simulation",
        tool_call_id="test-call",
        tool_arguments=args_json,
    )
    raw = asyncio.run(tool.on_invoke_tool(ctx, args_json))
    return json.loads(raw) if isinstance(raw, str) else raw


def test_run_elmer_simulation_agent_tool_forwards_executable_overrides(monkeypatch):
    captured = {}

    def fake_run(
        geometry=None,
        frequency_hz=None,
        timeout_s=1800,
        gmsh_executable=None,
        elmergrid_executable=None,
        elmersolver_executable=None,
    ):
        captured.update(
            geometry=geometry,
            frequency_hz=frequency_hz,
            timeout_s=timeout_s,
            gmsh_executable=gmsh_executable,
            elmergrid_executable=elmergrid_executable,
            elmersolver_executable=elmersolver_executable,
        )
        return {"provenance": "SIMULATED"}

    monkeypatch.setattr(agent_main, "_run_elmer_simulation", fake_run)

    geometry = {"domain": {"size_m": [0.01, 0.01, 0.01], "eps_r": 1.0}}
    result = _invoke_elmer_agent_tool(
        geometry=geometry,
        frequency_hz=2.4e9,
        timeout_s=90,
        gmsh_executable="/opt/gmsh/bin/gmsh",
        elmergrid_executable="/opt/elmer/bin/ElmerGrid",
        elmersolver_executable="/opt/elmer/bin/ElmerSolver",
    )

    assert captured == {
        "geometry": geometry,
        "frequency_hz": 2.4e9,
        "timeout_s": 90,
        "gmsh_executable": "/opt/gmsh/bin/gmsh",
        "elmergrid_executable": "/opt/elmer/bin/ElmerGrid",
        "elmersolver_executable": "/opt/elmer/bin/ElmerSolver",
    }
    assert result == {"provenance": "SIMULATED"}
