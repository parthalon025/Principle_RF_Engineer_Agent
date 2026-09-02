"""Tests for orchestration/policy.py (the tool-permission enforcement layer
built out of `/grill-with-docs` on the RF tool orchestration flow -- see
that module's own docstring for the two-check design: `enforce()` as a
per-call gate for the two hard-gated categories, and
`assert_all_tools_categorized()` as an import-time completeness check).

Pure logic, no database, no DATABASE_URL needed -- mirrors
tests/test_design_loop.py's own no-DB discipline for testing
orchestration/approval.py (see that file's header): these tests exercise
orchestration/policy.py's real functions against the real
policies/tool_policy.yaml and the real tool lists agent/main.py and
mcp_server/server.py register, with no fakes/stubs needed anywhere.
"""

import asyncio

import pytest

import agent.main
import mcp_server.server
from orchestration.policy import PolicyError, assert_all_tools_categorized, enforce

# ---------------------------------------------------------------------------
# enforce() -- per-call gate
# ---------------------------------------------------------------------------


def test_enforce_is_a_no_op_for_a_read_only_tool():
    assert enforce("read_document") is None


def test_enforce_is_a_no_op_for_a_calculation_tool():
    assert enforce("calculate_wavelength") is None


def test_enforce_raises_for_a_blocked_by_default_tool():
    with pytest.raises(PolicyError) as exc_info:
        enforce("arbitrary_shell")
    assert "arbitrary_shell" in str(exc_info.value)


def test_enforce_raises_for_an_approval_required_tool():
    with pytest.raises(PolicyError) as exc_info:
        enforce("manufacturing_release")
    assert "manufacturing_release" in str(exc_info.value)


# ---------------------------------------------------------------------------
# assert_all_tools_categorized() -- import-time completeness check
# ---------------------------------------------------------------------------


def test_assert_all_tools_categorized_raises_for_an_uncategorized_tool_name():
    with pytest.raises(PolicyError) as exc_info:
        assert_all_tools_categorized(["some_totally_made_up_tool_name"])
    assert "some_totally_made_up_tool_name" in str(exc_info.value)


def test_assert_all_tools_categorized_accepts_every_real_agent_tool():
    # The real regression-catching assertion: every tool agent/main.py
    # actually registers must have a category in tool_policy.yaml, so the
    # code and the yaml can never silently drift apart.
    assert_all_tools_categorized([tool.name for tool in agent.main._ALL_TOOLS])


def test_assert_all_tools_categorized_accepts_every_real_mcp_tool():
    # Same regression-catching assertion for the other tool surface.
    registered_names = [tool.name for tool in asyncio.run(mcp_server.server.mcp.list_tools())]
    assert_all_tools_categorized(registered_names)
