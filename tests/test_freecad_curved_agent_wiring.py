"""Issue #317 (ADR-0032 prefactor audit): `agent/main.py`'s
`generate_freecad_curved_geometry` `@function_tool` wrapper declared only
`primitives`/`curvature`/`timeout_s`, while `mcp_server/server.py`'s sibling
`@mcp.tool()` registration also exposed `executable` (the same FreeCADCmd
path override `geometry.freecad_curved.run_freecad_curved_geometry` itself
accepts). An agent session had no way to point this tool at a non-default
FreeCADCmd install; the MCP surface already could.

This proves `executable` is now part of the agent-side wrapper's signature
and is forwarded through untouched, mirroring `tests/test_mcp_server.py`'s
`test_generate_freecad_curved_geometry_forwards_executable` (added alongside
this test to close the same gap on the MCP-side wrapper) for the sibling MCP
tool surface, and `tests/test_ltspice_agent_wiring.py`'s documented reason
for going through the real `FunctionTool.on_invoke_tool` machinery rather
than a plain Python call: `@function_tool` wraps the original function into
a non-callable `Tool` object (that file's own invoke-through-on_invoke_tool
helper now lives shared as `conftest.invoke_agent_tool`, after code review
of this same issue flagged the copy this file originally added as
duplicated code).
"""

from __future__ import annotations

from conftest import invoke_agent_tool

import agent.main as agent_main


def test_generate_freecad_curved_geometry_agent_tool_forwards_executable(monkeypatch):
    captured = {}

    def fake_run(primitives=None, curvature=None, timeout_s=600, executable=None):
        captured.update(
            primitives=primitives,
            curvature=curvature,
            timeout_s=timeout_s,
            executable=executable,
        )
        return {"provenance": "SIMULATED"}

    monkeypatch.setattr(agent_main, "_run_freecad_curved_geometry", fake_run)

    primitives = [{"kind": "box", "center_m": [0, 0, 0], "size_m": [0.01, 0.01, 0.001]}]
    curvature = {"kind": "cylinder", "radius_m": 0.5, "axis": "x"}
    result = invoke_agent_tool(
        "generate_freecad_curved_geometry",
        primitives=primitives,
        curvature=curvature,
        timeout_s=45,
        executable="/opt/freecad/bin/FreeCADCmd",
    )

    assert captured == {
        "primitives": primitives,
        "curvature": curvature,
        "timeout_s": 45,
        "executable": "/opt/freecad/bin/FreeCADCmd",
    }
    assert result == {"provenance": "SIMULATED"}
