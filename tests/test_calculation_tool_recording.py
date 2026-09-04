"""Integration tests for ticket #19: the optional `design_id` param every
`calculate_*`/`analyze_touchstone_file` tool wrapper gains in `agent/main.py`
and `mcp_server/server.py`.

Both wrapper layers are exercised independently (`agent`/`mcp` `layer`
parametrization) since they're two separate, hand-duplicated implementations
-- a copy-paste mistake in either one would otherwise go uncaught. Invocation
goes through each SDK's real tool-call machinery (`FunctionTool.on_invoke_tool`
for the `agents` SDK, `FastMCP.call_tool` for the MCP server), not a plain
Python call, since `@function_tool`/`@mcp.tool()` wrap the original function
into a non-callable Tool object.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

import numpy as np
import psycopg
import pytest
import skrf as rf
from agents.tool_context import ToolContext
from dotenv import load_dotenv
from psycopg.rows import dict_row

import agent.main as agent_main
import mcp_server.server as mcp_module
from designs.service import create_design

load_dotenv()


def _make_touchstone_file() -> str:
    tmp_dir = Path(tempfile.mkdtemp())
    f = rf.Frequency(1, 3, 3, unit="ghz")
    s = np.zeros((3, 2, 2), dtype=complex)
    s[:, 0, 0] = 10 ** (-20 / 20)
    s[:, 1, 0] = 10 ** (-3 / 20)
    ntwk = rf.Network(frequency=f, s=s, z0=50)
    path = tmp_dir / "recording_fixture.s2p"
    ntwk.write_touchstone(path.with_suffix(""))
    return str(path)


_TOUCHSTONE_PATH = _make_touchstone_file()

TOOL_KWARGS = {
    "calculate_wavelength": {"frequency_hz": 1_000_000_000.0},
    "calculate_vswr": {"reflection_coefficient_magnitude": 0.5},
    "calculate_return_loss": {"reflection_coefficient_magnitude": 0.5},
    "calculate_cascade_gain": {"gains_db": [10.0, -3.0, 20.0]},
    "calculate_noise_figure": {"noise_factors": [1.5, 2.0], "gains_linear": [10.0, 10.0]},
    "analyze_touchstone_file": {"path": _TOUCHSTONE_PATH},
}
TOOL_NAMES = list(TOOL_KWARGS)


def _invoke_agent_tool(tool_name: str, **kwargs):
    # Calculation tools live on the specialist roles now, not the principal
    # (issue #35's handoffs redesign scoped the principal down to design-record/
    # search/design-loop tools only) -- search every role's tools, not just
    # principal's, to find the one FunctionTool object each named tool is
    # wrapped into (the same object regardless of which role's list holds it).
    all_tools = (t for role in agent_main.ROLES.values() for t in role.tools)
    tool = next(t for t in all_tools if t.name == tool_name)
    args_json = json.dumps(kwargs)
    ctx = ToolContext(
        context=None, tool_name=tool_name, tool_call_id="test-call", tool_arguments=args_json
    )
    return asyncio.run(tool.on_invoke_tool(ctx, args_json))


def _invoke_mcp_tool(tool_name: str, **kwargs):
    result = asyncio.run(mcp_module.mcp.call_tool(tool_name, kwargs))
    if isinstance(result, tuple):
        _, structured = result
        return structured.get("result", structured)
    content = result
    return json.loads(content[0].text)


INVOKERS = {"agent": _invoke_agent_tool, "mcp": _invoke_mcp_tool}


@pytest.fixture
def design_id():
    """A real design row for wrapper-level `engineering_results` rows to
    reference. These wrappers commit their own connection via
    `designs.service` (mirroring `create_design`), so a rolled-back
    `db_conn` transaction (`tests/test_designs_db.py`'s isolation strategy)
    can't isolate them -- cascade-delete the design instead, same as
    `tests/test_designs_service.py`'s `cleanup_designs`."""
    result = create_design(
        design_key=f"REC-{os.urandom(4).hex()}",
        name="Tool Recording Fixture Design",
        revision="A",
        requirements={},
        architecture={},
    )
    yield result["design_id"]
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM designs WHERE id = %s", (result["design_id"],))
    finally:
        conn.close()


def _count_results(design_id: int) -> int:
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM engineering_results WHERE design_id = %s", (design_id,)
            )
            (count,) = cur.fetchone()
    finally:
        conn.close()
    return count


def _fetch_result(design_id: int) -> dict:
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM engineering_results WHERE design_id = %s", (design_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    assert row is not None
    return row


@pytest.mark.parametrize("tool_name", TOOL_NAMES)
@pytest.mark.parametrize("layer", ["agent", "mcp"])
def test_wrapper_with_design_id_records_one_row_and_returns_recorded_as(
    layer, tool_name, design_id
):
    invoke = INVOKERS[layer]
    result = invoke(tool_name, design_id=design_id, **TOOL_KWARGS[tool_name])

    assert _count_results(design_id) == 1
    row = _fetch_result(design_id)
    assert row["provenance"] == "CALCULATED"
    assert row["confidence"] is None
    assert row["tool_name"] == tool_name
    assert row["result_type"] == tool_name

    assert isinstance(result, dict)
    assert result["recorded_as"] == {"engineering_result_id": row["id"]}


@pytest.mark.parametrize("tool_name", TOOL_NAMES)
@pytest.mark.parametrize("layer", ["agent", "mcp"])
def test_wrapper_without_design_id_writes_no_row_and_keeps_return_shape(
    layer, tool_name, design_id
):
    invoke = INVOKERS[layer]
    result = invoke(tool_name, **TOOL_KWARGS[tool_name])

    assert _count_results(design_id) == 0
    if isinstance(result, dict):
        assert "recorded_as" not in result
    else:
        assert isinstance(result, float)
