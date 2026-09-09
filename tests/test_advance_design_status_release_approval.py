"""issue #258 ticket 4: the `advance_design_status` tool's `approval` param.

Ticket 3 (already merged, see `tests/test_approval_cli.py`) gave a human a
local CLI (`orchestration/approval_cli.py`'s `approve-release` subcommand)
that mints a real `DesignReleaseApprovalReceipt` and prints its `.to_dict()`
output. Until this ticket, nothing let that dict actually reach the RELEASED
gate: `agent/main.py`'s and `mcp_server/server.py`'s `advance_design_status`
tools were hardcoded to call `designs.service.update_design_status` with no
`approval` at all, so a release attempt always fell through to
`release_not_approved` no matter what a human had approved.

This file proves the last hop works, on BOTH tool surfaces, mirroring
`tests/test_calculation_tool_recording.py`'s `_invoke_agent_tool`/
`_invoke_mcp_tool` pattern (real `FunctionTool.on_invoke_tool` / `FastMCP.
call_tool` machinery, not a plain Python call, since `@function_tool`/
`@mcp.tool()` wrap the original function into a non-callable Tool object).

`designs.service.coerce_release_approval` -- the dict -> receipt coercion
both tool wrappers share -- gets its own direct unit coverage at the bottom
of this file for the one case a JSON tool boundary cannot exercise: an
already-constructed `DesignReleaseApprovalReceipt` passed straight through
(mirroring `orchestration.design_loop`'s `_coerce_receipt` no-op-passthrough
behavior for a non-dict). Everything reachable through the JSON boundary
(a dict, or nothing) is exercised end-to-end through both real tool
surfaces instead.

The `tests/test_designs_db.py::test_a_valid_release_receipt_releases_the_design`
/ `test_a_release_receipt_for_another_design_is_refused` pair already proves
this at the `designs.db`/`designs.service` layer below the tools; this file
is the equivalent proof one layer up, at the tools an agent (or a human
running the CLI's `approve-release` step first) actually calls.
"""

from __future__ import annotations

import asyncio
import json
import os

import psycopg
import pytest
from agents.tool_context import ToolContext
from dotenv import load_dotenv

import agent.main as agent_main
import mcp_server.server as mcp_module
from designs.release_approval import (
    DesignReleaseApprovalError,
    DesignReleaseApprovalReceipt,
    release_fingerprint_fields,
    request_design_release_approval,
)
from designs.service import coerce_release_approval
from designs.service import create_design as _create_design
from designs.service import read_design as _read_design
from designs.service import update_design_status as _service_update_design_status

load_dotenv()


@pytest.fixture
def cleanup_designs():
    """Same shape as `tests/test_designs_service.py`'s fixture of the same
    name: both tool wrappers commit their own connection via
    `designs.service`, so a rolled-back `db_conn` transaction can't isolate
    them -- cascade-delete the design afterward instead."""
    ids: list[int] = []
    yield ids
    if not ids:
        return
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM designs WHERE id = ANY(%s)", (ids,))
    finally:
        conn.close()


def _make_design_at_pass(cleanup_designs, design_key: str) -> tuple[int, str]:
    """A real `designs` row walked, via the service layer directly (no
    approval needed for any of these steps), all the way to PASS -- the
    only status RELEASED may legally follow other than CONDITIONAL-PASS.
    Returns (design_id, revision)."""
    created = _create_design(
        design_key=design_key,
        name="Release Approval Tool Fixture",
        revision="A",
        requirements={},
        architecture={},
    )
    design_id = created["design_id"]
    cleanup_designs.append(design_id)
    for status in ("ANALYSIS", "SIMULATION", "OPTIMIZATION", "VERIFICATION", "PASS"):
        result = _service_update_design_status(design_id=design_id, status=status)
        assert result["status"] == "updated", result
    return design_id, "A"


def _mint_valid_receipt(
    design_id: int, design_key: str, revision: str
) -> DesignReleaseApprovalReceipt:
    return request_design_release_approval(
        release_fingerprint_fields(design_id=design_id, design_key=design_key, revision=revision),
        approved_by="a.engineer",
        approval_callback=lambda _: True,
    )


def _invoke_agent_tool(**kwargs):
    all_tools = (t for role in agent_main.ROLES.values() for t in role.tools)
    tool = next(t for t in all_tools if t.name == "advance_design_status")
    args_json = json.dumps(kwargs)
    ctx = ToolContext(
        context=None,
        tool_name="advance_design_status",
        tool_call_id="test-call",
        tool_arguments=args_json,
    )
    raw = asyncio.run(tool.on_invoke_tool(ctx, args_json))
    return json.loads(raw) if isinstance(raw, str) else raw


def _invoke_mcp_tool(**kwargs):
    result = asyncio.run(mcp_module.mcp.call_tool("advance_design_status", kwargs))
    if isinstance(result, tuple):
        _, structured = result
        return structured.get("result", structured)
    return json.loads(result[0].text)


INVOKERS = {"agent": _invoke_agent_tool, "mcp": _invoke_mcp_tool}


@pytest.mark.parametrize("layer", ["agent", "mcp"])
def test_a_valid_receipt_releases_the_design_through_the_tool(layer, cleanup_designs):
    """The core regression this ticket exists to fix: a real receipt,
    minted exactly as the ticket-3 CLI mints one, reaches
    check_design_release_approval_gate and actually unlocks RELEASED."""
    design_id, revision = _make_design_at_pass(cleanup_designs, f"REL-{layer}-1")
    receipt = _mint_valid_receipt(design_id, f"REL-{layer}-1", revision)

    result = INVOKERS[layer](design_id=design_id, status="RELEASED", approval=receipt.to_dict())

    assert result["status"] == "updated", result
    assert result["design_status"] == "RELEASED"
    assert _read_design(design_id)["status"] == "RELEASED"


@pytest.mark.parametrize("layer", ["agent", "mcp"])
def test_no_approval_still_refuses_exactly_as_before(layer, cleanup_designs):
    """Regression guard (constraint 1): the default (no `approval` at all)
    must behave EXACTLY as it did before this ticket -- release_not_approved,
    design left at PASS."""
    design_id, _ = _make_design_at_pass(cleanup_designs, f"REL-{layer}-2")

    result = INVOKERS[layer](design_id=design_id, status="RELEASED")

    assert result["status"] == "release_not_approved", result
    assert _read_design(design_id)["status"] == "PASS"


@pytest.mark.parametrize("layer", ["agent", "mcp"])
def test_explicit_none_approval_still_refuses(layer, cleanup_designs):
    design_id, _ = _make_design_at_pass(cleanup_designs, f"REL-{layer}-3")

    result = INVOKERS[layer](design_id=design_id, status="RELEASED", approval=None)

    assert result["status"] == "release_not_approved", result
    assert _read_design(design_id)["status"] == "PASS"


@pytest.mark.parametrize("layer", ["agent", "mcp"])
def test_a_garbage_shaped_dict_is_refused_not_crashed(layer, cleanup_designs):
    """Constraint 3 + the ticket's explicit test list: a dict that doesn't
    even match DesignReleaseApprovalReceipt's fields must be refused
    cleanly (release_not_approved), never raise an unhandled TypeError out
    of the tool call."""
    design_id, _ = _make_design_at_pass(cleanup_designs, f"REL-{layer}-4")

    result = INVOKERS[layer](
        design_id=design_id, status="RELEASED", approval={"nonsense": "not a receipt"}
    )

    assert result["status"] == "release_not_approved", result
    assert _read_design(design_id)["status"] == "PASS"


@pytest.mark.parametrize("layer", ["agent", "mcp"])
def test_a_forged_receipt_dict_is_refused(layer, cleanup_designs):
    """Constraint 3: a dict with the RIGHT shape (all four receipt fields)
    but fabricated content -- never issued by
    request_design_release_approval() in this process -- must fail the
    signature check and be refused, not silently accepted."""
    design_id, _ = _make_design_at_pass(cleanup_designs, f"REL-{layer}-5")
    forged = {
        "token": "0" * 64,
        "decision_fingerprint": "1" * 64,
        "approved_by": "an.attacker",
        "granted_at": 0.0,
    }

    result = INVOKERS[layer](design_id=design_id, status="RELEASED", approval=forged)

    assert result["status"] == "release_not_approved", result
    assert _read_design(design_id)["status"] == "PASS"


@pytest.mark.parametrize("layer", ["agent", "mcp"])
def test_a_receipt_for_another_design_is_refused_at_the_tool_layer(layer, cleanup_designs):
    """Constraint 4, one layer up from
    tests/test_designs_db.py::test_a_release_receipt_for_another_design_is_refused:
    a receipt bound to one design/revision must not release a different
    design that happens to also be sitting at PASS."""
    approved_id, revision = _make_design_at_pass(cleanup_designs, f"REL-{layer}-6a")
    other_id, _ = _make_design_at_pass(cleanup_designs, f"REL-{layer}-6b")
    receipt = _mint_valid_receipt(approved_id, f"REL-{layer}-6a", revision)

    result = INVOKERS[layer](design_id=other_id, status="RELEASED", approval=receipt.to_dict())

    assert result["status"] == "release_not_approved", result
    assert _read_design(other_id)["status"] == "PASS"
    # The receipt's own design is untouched by the misdirected attempt.
    assert _read_design(approved_id)["status"] == "PASS"


# ---------------------------------------------------------------------------
# designs.service.coerce_release_approval -- the shared dict -> receipt
# coercion both tool wrappers call before handing `approval` to
# `_update_design_status`. A JSON tool boundary can only ever carry a dict
# or null, never a live Python object, so the "already-constructed receipt
# instance passes through unchanged" case (mirroring orchestration.
# design_loop's _coerce_receipt) is exercised directly here instead of
# through on_invoke_tool/call_tool.
# ---------------------------------------------------------------------------


def test_coerce_release_approval_rebuilds_a_receipt_from_its_to_dict_output():
    receipt = DesignReleaseApprovalReceipt(
        token="a" * 64, decision_fingerprint="b" * 64, approved_by="a.engineer", granted_at=123.0
    )
    rebuilt = coerce_release_approval(receipt.to_dict())
    assert rebuilt == receipt


def test_coerce_release_approval_passes_an_existing_receipt_through_unchanged():
    receipt = DesignReleaseApprovalReceipt(
        token="a" * 64, decision_fingerprint="b" * 64, approved_by="a.engineer", granted_at=123.0
    )
    assert coerce_release_approval(receipt) is receipt


def test_coerce_release_approval_passes_none_through_unchanged():
    assert coerce_release_approval(None) is None


def test_coerce_release_approval_does_not_raise_on_a_malformed_dict():
    """A dict missing/extra fields would raise TypeError from
    DesignReleaseApprovalReceipt(**approval); this function must not let
    that escape -- it hands the unchanged dict on to
    check_design_release_approval_gate, whose own isinstance check refuses
    it with a clear message instead."""
    malformed = coerce_release_approval({"nonsense": "not a receipt"})
    assert malformed == {"nonsense": "not a receipt"}


def test_coerce_release_approval_output_is_still_refused_by_the_real_gate():
    """End-to-end at the designs.db layer: a malformed dict, once coerced,
    still fails check_design_release_approval_gate rather than satisfying it."""
    from designs.release_approval import check_design_release_approval_gate

    coerced = coerce_release_approval({"nonsense": "not a receipt"})
    with pytest.raises(DesignReleaseApprovalError):
        check_design_release_approval_gate(
            coerced, release_fingerprint_fields(design_id=1, design_key="X", revision="A")
        )
