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
into a non-callable `Tool` object (that file's own invoke-through-
on_invoke_tool helper now lives shared as `conftest.invoke_agent_tool`, after
code review of this same issue flagged the copy this file originally added
as duplicated code).
"""

from __future__ import annotations

from conftest import invoke_agent_tool

import agent.main as agent_main


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
    result = invoke_agent_tool(
        "run_elmer_simulation",
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
