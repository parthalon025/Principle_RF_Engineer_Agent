"""Tests for orchestration/policy.py (the tool-permission enforcement layer
built out of `/grill-with-docs` on the RF tool orchestration flow -- see
that module's own docstring for the two-check design: `enforce()` as a
per-call gate for the two hard-gated categories, and
`assert_all_tools_categorized()` as an import-time completeness check).

Pure logic, no database, no DATABASE_URL needed -- mirrors
tests/test_design_loop.py's own no-DB discipline for testing
orchestration/approval.py (see that file's header): these tests exercise
orchestration/policy.py's real functions against the real
policies/tool_policy.yaml and the real tool list mcp_server/server.py
registers (the only tool registry left, since issue #573 deleted
agent/main.py's own wrapper layer in full), with no fakes/stubs needed
anywhere.
"""

import asyncio

import pytest

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


def test_assert_all_tools_categorized_accepts_every_real_mcp_tool():
    # The real regression-catching assertion: every tool mcp_server/server.py
    # actually registers must have a category in tool_policy.yaml, so the
    # code and the yaml can never silently drift apart. This is the ONLY
    # tool surface left to check (issue #573 deleted agent/main.py's own
    # wrapper layer in full -- see this file's own module docstring) --
    # before that, an equivalent assertion against agent.main._ALL_TOOLS
    # existed alongside this one; it's gone now for the same reason
    # agent/main.py's own import-time assert_all_tools_categorized() call
    # is gone.
    registered_names = [tool.name for tool in asyncio.run(mcp_server.server.mcp.list_tools())]
    assert_all_tools_categorized(registered_names)
