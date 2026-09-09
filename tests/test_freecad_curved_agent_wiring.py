"""Issue #317 (ADR-0032 prefactor audit): `agent/main.py`'s
`generate_freecad_curved_geometry` `@function_tool` wrapper declared only
`primitives`/`curvature`/`timeout_s`, while `mcp_server/server.py`'s sibling
`@mcp.tool()` registration also exposed `executable` (the same FreeCADCmd
path override `geometry.freecad_curved.run_freecad_curved_geometry` itself
accepts). An agent session had no way to point this tool at a non-default
FreeCADCmd install; the MCP surface already could.

This proves `executable` is now part of the agent-side wrapper's signature
and is forwarded through untouched, mirroring `tests/test_mcp_server.py`'s
`test_generate_freecad_curved_geometry_forwards_executable`-shaped coverage
for the sibling MCP tool surface, and `tests/test_ltspice_agent_wiring.py`'s
documented reason for going through the real `FunctionTool.on_invoke_tool`
machinery rather than a plain Python call: `@function_tool` wraps the
original function into a non-callable `Tool` object.
"""

from __future__ import annotations

import asyncio
import json

from agents.tool_context import ToolContext

import agent.main as agent_main


def _invoke_freecad_curved_agent_tool(**kwargs):
    all_tools = (t for role in agent_main.ROLES.values() for t in role.tools)
    tool = next(t for t in all_tools if t.name == "generate_freecad_curved_geometry")
    args_json = json.dumps(kwargs)
    ctx = ToolContext(
        context=None,
        tool_name="generate_freecad_curved_geometry",
        tool_call_id="test-call",
        tool_arguments=args_json,
    )
    raw = asyncio.run(tool.on_invoke_tool(ctx, args_json))
    return json.loads(raw) if isinstance(raw, str) else raw


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
    result = _invoke_freecad_curved_agent_tool(
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
