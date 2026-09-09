"""Code review on issue #287: `agent/main.py`'s `run_ltspice_simulation`
`@function_tool` wrapper (the tool object actually registered on the
microwave/test roles' tool lists -- see tests/test_agent_roles.py's
`test_microwave_and_test_roles_get_ltspice_simulation`) originally still
declared only `netlist`/`netlist_file`/`timeout_s`, so a `job` dict (the new
structured `.net` two-port S/Y/Z/H-parameter templating path added by this
ticket, see simulation/ltspice.py's `generate_ltspice_net_netlist`) could
never reach `simulation.ltspice.run_ltspice_simulation` through an actual
agent tool call -- an agent session could only hand-write a `.net` netlist
as raw text, exactly the pre-#287 status quo.

This proves `job` is now part of the wrapper's signature and is forwarded
through untouched, mirroring `tests/test_mcp_server.py`'s equivalent
`test_run_ltspice_simulation_forwards_job` for the sibling MCP tool surface,
and `tests/test_calculation_tool_recording.py`'s documented reason for going
through the real `FunctionTool.on_invoke_tool` machinery rather than a plain
Python call: `@function_tool` wraps the original function into a
non-callable `Tool` object, so a plain `agent_main.run_ltspice_simulation(...)`
call is not available to test in the first place.

Code review of issue #317 (a later user of this same invoke-through-
on_invoke_tool pattern) flagged this file's own `_invoke_ltspice_agent_tool`
helper as duplicated code once two more copies appeared; it now lives once,
as `conftest.invoke_agent_tool`.
"""

from __future__ import annotations

from conftest import invoke_agent_tool

import agent.main as agent_main


def test_run_ltspice_simulation_agent_tool_forwards_job(monkeypatch):
    captured = {}

    def fake_run(netlist=None, netlist_file=None, job=None, timeout_s=600):
        captured.update(netlist=netlist, netlist_file=netlist_file, job=job, timeout_s=timeout_s)
        return {"provenance": "SIMULATED"}

    monkeypatch.setattr(agent_main, "_run_ltspice_simulation", fake_run)

    job = {
        "components": [{"type": "V", "name": "V1", "n1": "in", "n2": "0", "ac_mag": 1.0}],
        "ports": [
            {"role": "input", "name": "V1"},
            {"role": "output", "kind": "V", "node": "in"},
        ],
        "analysis": {
            "type": "ac",
            "sweep_type": "dec",
            "points": 10,
            "start_freq_hz": 1e6,
            "stop_freq_hz": 1e8,
        },
    }

    result = invoke_agent_tool("run_ltspice_simulation", job=job, timeout_s=15)

    assert captured == {"netlist": None, "netlist_file": None, "job": job, "timeout_s": 15}
    assert result == {"provenance": "SIMULATED"}
