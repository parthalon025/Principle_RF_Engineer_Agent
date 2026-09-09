"""Tests for orchestration/approval_cli.py -- the local, human-only surface
that grants (or refuses) a design-loop step approval, and (issue #258
ticket 3) a design-release approval, end to end (see tests/test_approval_audit.py
for ticket 1).

Needs a real Postgres via DATABASE_URL (like tests/test_tooling.py):
`submit_pending_approval`/`decide_pending_approval` (and their release-gate
counterparts, `submit_pending_release_approval`/`decide_pending_release_approval`)
each own their connection lifecycle and commit for real, so this file follows
tests/test_tooling.py's `cleanup_designs` convention rather than the
rolled-back `db_conn` fixture for anything that goes through this module's
own top-level functions. `db_conn` is still used, read-only, to check the
audit trail and the backing `designs` row afterward.

Groups, matching the ticket's own non-negotiable constraints (loop-step gate
first, then the same shape of coverage for the release gate added by ticket
3):

  1. The fail-closed regression -- approval_callback=None still always
     raises, unmodified, for BOTH request_loop_step_approval and
     request_design_release_approval.
  2. The structural test -- request_loop_step_approval AND
     request_design_release_approval are absent, by name, from both tool
     registries, before and after this module exists.
  3. The happy path -- submit, list, show, approve -- reaching
     advance_design_loop_step with a real receipt, list excludes it after.
  4. Refusal -- loop state, the designs row, and every other table are left
     completely untouched; the audit trail still gets a full record.
  5. The pending-approvals listing itself -- finds a loop sitting at a
     gated step, excludes one that has already advanced past it.
  6. The release gate's own submit/list/show/approve/refuse flow (ticket 3)
     -- mints a real DesignReleaseApprovalReceipt, hands it back without
     touching the design's status (that's ticket 4's job), and a refusal
     leaves the designs row and the pending table completely untouched
     other than the audit record.
"""

from __future__ import annotations

import asyncio
import inspect
import os

import psycopg
import pytest
from dotenv import load_dotenv

from designs.release_approval import (
    DesignReleaseApprovalError,
    DesignReleaseApprovalReceipt,
    release_fingerprint_fields,
    request_design_release_approval,
)
from designs.service import read_design
from orchestration.approval import OrchestrationError, request_loop_step_approval
from orchestration.approval_audit import (
    GATE_DESIGN_RELEASE,
    GATE_LOOP_STEP,
    OUTCOME_APPROVED,
    OUTCOME_REFUSED,
    fetch_audit_records,
)
from orchestration.approval_cli import (
    ApprovalCliError,
    decide_pending_approval,
    decide_pending_release_approval,
    describe_pending_approval,
    describe_pending_release_approval,
    get_pending_approval,
    get_pending_release_approval,
    list_pending_approvals,
    list_pending_release_approvals,
    submit_pending_approval,
    submit_pending_release_approval,
)
from orchestration.design_loop import DesignStep
from orchestration.tooling import advance_design_loop_step, start_new_design_loop

load_dotenv()

REQUIREMENTS = {"R1": {"requirement": "gain >= 5 dBi over 2.4-2.5 GHz"}}

ARCHITECTURE_STEP_INPUT = {
    "decision": "rectangular microstrip patch on FR4",
    "rationale": "meets band/gain target with a simple, low-cost fabrication",
    "design_family": "PATCH",
}


@pytest.fixture
def cleanup_designs():
    """Mirrors tests/test_tooling.py's fixture of the same name (duplicated,
    not imported, matching that suite's own per-file convention)."""
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


# ---------------------------------------------------------------------------
# Group 1: the fail-closed regression. Nothing about approval_callback=None
# changed -- direct, unmodified proof.
# ---------------------------------------------------------------------------


def test_approval_callback_none_still_always_raises():
    with pytest.raises(OrchestrationError, match="No human-approval mechanism"):
        request_loop_step_approval(
            {"loop_id": "x", "iteration": 1, "step": "architecture", "content": {}},
            approved_by="a.human",
            approval_callback=None,
        )


def test_approval_callback_none_is_still_the_default():
    with pytest.raises(OrchestrationError, match="No human-approval mechanism"):
        request_loop_step_approval(
            {"loop_id": "x", "iteration": 1, "step": "architecture", "content": {}},
            approved_by="a.human",
        )


def test_release_approval_callback_none_still_always_raises():
    with pytest.raises(DesignReleaseApprovalError, match="No human-approval mechanism"):
        request_design_release_approval(
            {"design_id": 1, "design_key": "R1", "revision": "1", "target": "RELEASED"},
            approved_by="a.human",
            approval_callback=None,
        )


def test_release_approval_callback_none_is_still_the_default():
    with pytest.raises(DesignReleaseApprovalError, match="No human-approval mechanism"):
        request_design_release_approval(
            {"design_id": 1, "design_key": "R1", "revision": "1", "target": "RELEASED"},
            approved_by="a.human",
        )


# ---------------------------------------------------------------------------
# Group 2: structural -- request_loop_step_approval reaches neither tool
# registry, by name. Grep-based (agent/main.py's source) AND
# introspection-based (mcp_server/server.py's live registry), so a wrapper
# under a different name can't slip past a pure name search either.
# ---------------------------------------------------------------------------


def test_request_loop_step_approval_not_in_agent_all_tools():
    """Confirms both approval-minting functions -- the loop-step gate AND
    the release gate ticket 3 wires up a CLI surface for -- are absent from
    agent/main.py's own tool registry, by name (issue #258 story #16)."""
    import agent.main as agent_main

    names = {tool.name for tool in agent_main._ALL_TOOLS}
    assert "request_loop_step_approval" not in names
    assert "request_design_release_approval" not in names


def test_request_loop_step_approval_not_wrapped_as_a_function_tool_anywhere_in_agent_main():
    """Belt-and-braces over the by-name check above: no top-level callable
    in agent/main.py is *itself* named request_loop_step_approval, wrapped
    or not -- catches a hypothetical wrapper that renamed its .name but
    kept a tell-tale function name."""
    import agent.main as agent_main

    for attr_name in dir(agent_main):
        assert attr_name != "request_loop_step_approval"


def test_request_design_release_approval_not_wrapped_as_a_function_tool_anywhere_in_agent_main():
    """Same belt-and-braces check as the loop-step gate's, for the release
    gate (ticket 3)."""
    import agent.main as agent_main

    for attr_name in dir(agent_main):
        assert attr_name != "request_design_release_approval"


def test_request_loop_step_approval_not_registered_on_the_mcp_server():
    """Confirms both approval-minting functions are absent from the live
    MCP tool registry, by name -- already covered here for both names
    before ticket 3 added anything, and still true now (issue #258 story
    #16)."""
    import mcp_server.server as server

    registered_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "request_loop_step_approval" not in registered_names
    assert "request_design_release_approval" not in registered_names


def test_approval_cli_module_is_not_imported_by_either_tool_surface():
    """The new surface is a distinct, human-operated entry point -- not a
    channel agent/main.py or mcp_server/server.py could reach. Source-text
    check, so it holds even if a future edit imports it without calling
    anything (issue #258 story #15)."""
    import agent.main as agent_main
    import mcp_server.server as server

    for module in (agent_main, server):
        source = inspect.getsource(module)
        assert "approval_cli" not in source


def test_neither_tool_registry_contains_any_name_from_approval_cli_public_surface():
    """CI-lock (issue #258 ticket 5, structural regression coverage): the two
    checks above name only the two approval-minting functions themselves
    (`request_loop_step_approval`, `request_design_release_approval`). This
    check is broader on purpose -- it scans the ACTUAL registered tool sets
    (agent/main.py's `_ALL_TOOLS`, by `.name`; mcp_server/server.py's live MCP
    registry, by `.name`) against `orchestration.approval_cli.__all__`,
    this module's own declared public surface (`submit_pending_approval`,
    `decide_pending_release_approval`, `list_pending_approvals`, etc. -- ten
    names, not two). A future tool that reached this module's functionality
    under one of ITS names, rather than under `request_loop_step_approval`'s,
    would still be caught here even though the two targeted checks above
    would not name it -- the same structural-guarantee spirit as
    tests/test_design_loop.py's `test_no_release_or_manufacturing_callable_
    exists_anywhere_in_the_package`, applied to this module's own surface
    instead of `orchestration.approval`'s."""
    import agent.main as agent_main
    import mcp_server.server as server
    import orchestration.approval_cli as approval_cli

    cli_public_names = set(approval_cli.__all__)

    agent_tool_names = {tool.name for tool in agent_main._ALL_TOOLS}
    overlap = cli_public_names & agent_tool_names
    assert not overlap, (
        f"agent/main.py registers a tool named after orchestration.approval_cli's "
        f"public surface: {sorted(overlap)} -- the AI agent must never be able to "
        "reach this module's approval-minting functionality under any name"
    )

    mcp_tool_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    overlap = cli_public_names & mcp_tool_names
    assert not overlap, (
        f"mcp_server/server.py registers a tool named after orchestration."
        f"approval_cli's public surface: {sorted(overlap)} -- the AI agent must "
        "never be able to reach this module's approval-minting functionality "
        "under any name"
    )


_BANNED_TOOL_NAME_SUBSTRINGS = ("release", "manufactur", "production")


def test_no_release_or_manufacturing_named_tool_is_registered_in_either_surface():
    """CI-lock (issue #258 ticket 5): the same `_BANNED_SUBSTRINGS` scan
    tests/test_design_loop.py already runs over `orchestration.approval`,
    `orchestration.design_loop`, and `orchestration.tooling` (by `dir()`),
    extended to what actually matters for THIS surface -- the registered
    tool NAMES an AI agent can call, in both registries. Deliberately scoped
    to registered tool names only (not every module attribute, the way
    test_design_loop.py's version is) -- `agent/main.py` and
    `mcp_server/server.py` both legitimately hold `advance_design_status`'s
    `approval` parameter and similar names that are not themselves a
    release/manufacturing action; scanning every attribute there would
    false-positive on those. Scanning tool NAMES catches a future tool
    registered under a new name (e.g. a hypothetical `trigger_manufacturing_
    run` or `release_design_for_print`) even though nobody thought to add a
    targeted test for it -- structural, not enumerated."""
    import agent.main as agent_main
    import mcp_server.server as server

    agent_tool_names = {tool.name for tool in agent_main._ALL_TOOLS}
    mcp_tool_names = {t.name for t in asyncio.run(server.mcp.list_tools())}

    for surface, names in (
        ("agent/main.py", agent_tool_names),
        ("mcp_server/server.py", mcp_tool_names),
    ):
        for name in names:
            lowered = name.lower()
            for banned in _BANNED_TOOL_NAME_SUBSTRINGS:
                assert banned not in lowered, (
                    f"{surface} registers a tool named {name!r}, which looks like a "
                    "release/manufacturing path -- none should ever be agent-"
                    "reachable (docs/BUILD_PLAN.md's Phase 12: 'Never allow "
                    "autonomous manufacturing release')"
                )


# ---------------------------------------------------------------------------
# Group 3: happy path -- submit, list, show, approve.
# ---------------------------------------------------------------------------


def test_submit_registers_a_pending_request_for_the_gated_step(cleanup_designs):
    state = start_new_design_loop("CLI-1", "CLI Test Design", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])
    assert state["current_step"] == DesignStep.ARCHITECTURE.value

    row = submit_pending_approval(state, ARCHITECTURE_STEP_INPUT, submitted_by="alice")

    assert row["design_id"] == state["design_id"]
    assert row["loop_id"] == state["loop_id"]
    assert row["iteration"] == 1
    assert row["step"] == DesignStep.ARCHITECTURE.value
    assert row["submitted_by"] == "alice"
    assert row["fingerprint_fields"] == {
        "loop_id": state["loop_id"],
        "iteration": 1,
        "step": "architecture",
        "content": ARCHITECTURE_STEP_INPUT,
    }


def test_submit_rejects_an_ungated_step(cleanup_designs):
    state = start_new_design_loop("CLI-2", "CLI Test Design", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])
    # Advance past ARCHITECTURE with a real approval so current_step becomes
    # ANALYSIS -- not a gated step.
    fields = {
        "loop_id": state["loop_id"],
        "iteration": state["iteration"],
        "step": "architecture",
        "content": ARCHITECTURE_STEP_INPUT,
    }
    receipt = request_loop_step_approval(
        fields, approved_by="alice", approval_callback=lambda f: True
    )
    state = advance_design_loop_step(state, ARCHITECTURE_STEP_INPUT, approval=receipt.to_dict())
    assert state["current_step"] == DesignStep.ANALYSIS.value

    with pytest.raises(ApprovalCliError, match="not a gated step"):
        submit_pending_approval(state, {"eps_r": 4.4}, submitted_by="alice")


def test_show_surfaces_full_fingerprint_and_warnings(cleanup_designs):
    state = start_new_design_loop("CLI-3", "CLI Test Design", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])
    row = submit_pending_approval(state, ARCHITECTURE_STEP_INPUT, submitted_by="alice")

    fetched = get_pending_approval(row["id"])
    described = describe_pending_approval(fetched)

    assert described["request_id"] == row["id"]
    assert described["fingerprint_fields"]["content"] == ARCHITECTURE_STEP_INPUT
    assert described["warnings"] == []  # nothing recorded yet this iteration


def test_approve_mints_a_real_receipt_and_advances_the_loop(cleanup_designs):
    state = start_new_design_loop("CLI-4", "CLI Test Design", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])
    row = submit_pending_approval(state, ARCHITECTURE_STEP_INPUT, submitted_by="alice")

    result = decide_pending_approval(row["id"], "approve", approved_by="alice")

    assert result["status"] == "approved"
    new_state = result["new_state"]
    assert new_state["current_step"] == DesignStep.ANALYSIS.value
    assert new_state["decisions"][-1]["step"] == DesignStep.ARCHITECTURE.value
    assert new_state["decisions"][-1]["approved_by"] == "alice"

    stored = read_design(state["design_id"])
    assert stored["decision_records"] == []  # not flushed yet -- iteration not over


def test_approved_request_is_excluded_from_the_pending_listing(cleanup_designs):
    state = start_new_design_loop("CLI-5", "CLI Test Design", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])
    row = submit_pending_approval(state, ARCHITECTURE_STEP_INPUT, submitted_by="alice")

    assert row["id"] in {r["id"] for r in list_pending_approvals(design_id=state["design_id"])}

    decide_pending_approval(row["id"], "approve", approved_by="alice")

    remaining = {r["id"] for r in list_pending_approvals(design_id=state["design_id"])}
    assert row["id"] not in remaining
    assert get_pending_approval(row["id"]) is None


def test_approve_writes_an_approved_audit_record(cleanup_designs, db_conn):
    state = start_new_design_loop("CLI-6", "CLI Test Design", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])
    row = submit_pending_approval(state, ARCHITECTURE_STEP_INPUT, submitted_by="alice")

    decide_pending_approval(row["id"], "approve", approved_by="alice")

    records = fetch_audit_records(db_conn, loop_id=state["loop_id"])
    assert len(records) == 1
    assert records[0]["gate"] == GATE_LOOP_STEP
    assert records[0]["outcome"] == OUTCOME_APPROVED
    assert records[0]["approved_by"] == "alice"
    assert records[0]["fingerprint_fields"]["content"] == ARCHITECTURE_STEP_INPUT


# ---------------------------------------------------------------------------
# Group 4: refusal -- loop state, the designs row, and every other table
# untouched; the audit trail still gets a complete record.
# ---------------------------------------------------------------------------


def test_refuse_leaves_loop_state_completely_untouched(cleanup_designs):
    state = start_new_design_loop("CLI-7", "CLI Test Design", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])
    row = submit_pending_approval(state, ARCHITECTURE_STEP_INPUT, submitted_by="alice")

    result = decide_pending_approval(row["id"], "refuse", approved_by="bob")

    assert result["status"] == "refused"
    assert "new_state" not in result

    stored = read_design(state["design_id"])
    assert stored["status"] == "DRAFT"  # unchanged -- never flushed
    assert stored["decision_records"] == []
    assert stored["engineering_results"] == []


def test_refuse_writes_a_refused_audit_record(cleanup_designs, db_conn):
    state = start_new_design_loop("CLI-8", "CLI Test Design", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])
    row = submit_pending_approval(state, ARCHITECTURE_STEP_INPUT, submitted_by="alice")

    decide_pending_approval(row["id"], "refuse", approved_by="bob")

    records = fetch_audit_records(db_conn, loop_id=state["loop_id"])
    assert len(records) == 1
    assert records[0]["gate"] == GATE_LOOP_STEP
    assert records[0]["outcome"] == OUTCOME_REFUSED
    assert records[0]["approved_by"] == "bob"
    assert records[0]["fingerprint_fields"]["content"] == ARCHITECTURE_STEP_INPUT


def test_refused_request_is_excluded_from_the_pending_listing(cleanup_designs):
    state = start_new_design_loop("CLI-9", "CLI Test Design", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])
    row = submit_pending_approval(state, ARCHITECTURE_STEP_INPUT, submitted_by="alice")

    decide_pending_approval(row["id"], "refuse", approved_by="bob")

    remaining = {r["id"] for r in list_pending_approvals(design_id=state["design_id"])}
    assert row["id"] not in remaining


def test_decide_requires_approved_by(cleanup_designs):
    state = start_new_design_loop("CLI-10", "CLI Test Design", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])
    row = submit_pending_approval(state, ARCHITECTURE_STEP_INPUT, submitted_by="alice")

    with pytest.raises(ApprovalCliError, match="approved_by"):
        decide_pending_approval(row["id"], "approve", approved_by="")

    # still pending -- the bad call above never reached request_loop_step_approval
    assert get_pending_approval(row["id"]) is not None


def test_decide_unknown_request_id_raises(cleanup_designs):
    with pytest.raises(ApprovalCliError, match="no pending approval request"):
        decide_pending_approval(999_999_999, "approve", approved_by="alice")


# ---------------------------------------------------------------------------
# Group 5: the pending-approvals listing itself -- finds a loop sitting at
# a gated step, excludes one that has already advanced past it.
# ---------------------------------------------------------------------------


def test_listing_finds_a_loop_sitting_at_a_gated_step(cleanup_designs):
    state = start_new_design_loop("CLI-11", "CLI Test Design", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])
    row = submit_pending_approval(state, ARCHITECTURE_STEP_INPUT, submitted_by="alice")

    pending = list_pending_approvals()
    matching = [r for r in pending if r["id"] == row["id"]]
    assert len(matching) == 1
    assert matching[0]["step"] == DesignStep.ARCHITECTURE.value
    assert matching[0]["design_id"] == state["design_id"]


def test_listing_excludes_a_loop_that_has_already_advanced_past_its_gate(cleanup_designs):
    state = start_new_design_loop("CLI-12", "CLI Test Design", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])
    row = submit_pending_approval(state, ARCHITECTURE_STEP_INPUT, submitted_by="alice")

    decide_pending_approval(row["id"], "approve", approved_by="alice")

    pending_ids = {r["id"] for r in list_pending_approvals()}
    assert row["id"] not in pending_ids


def test_listing_scoped_to_one_design_id_ignores_other_designs(cleanup_designs):
    state_a = start_new_design_loop("CLI-13A", "CLI Test Design A", "A", REQUIREMENTS)
    cleanup_designs.append(state_a["design_id"])
    state_b = start_new_design_loop("CLI-13B", "CLI Test Design B", "A", REQUIREMENTS)
    cleanup_designs.append(state_b["design_id"])

    row_a = submit_pending_approval(state_a, ARCHITECTURE_STEP_INPUT, submitted_by="alice")
    submit_pending_approval(state_b, ARCHITECTURE_STEP_INPUT, submitted_by="alice")

    scoped = list_pending_approvals(design_id=state_a["design_id"])
    assert {r["id"] for r in scoped} == {row_a["id"]}


# ---------------------------------------------------------------------------
# Group 6: the release gate (issue #258 ticket 3) -- submit/list/show/
# approve/refuse for a pending DESIGN RELEASE decision, mirroring group 3/4/5
# above but for designs.release_approval.request_design_release_approval.
# A successful approval here mints a real DesignReleaseApprovalReceipt and
# hands it back -- it deliberately does NOT touch the design's status
# (ticket 4's job; designs.service.update_design_status doesn't get called
# from this module at all).
# ---------------------------------------------------------------------------


def _new_design(cleanup_designs, design_key: str) -> dict:
    """A real `designs` row, via the same start_new_design_loop path every
    other test in this file already uses (it creates the design in DRAFT
    status with an empty architecture) -- then read back in full via
    read_design, exactly the shape a human would have on hand to submit a
    release-approval request for."""
    state = start_new_design_loop(design_key, "CLI Release Test Design", "A", REQUIREMENTS)
    cleanup_designs.append(state["design_id"])
    return read_design(state["design_id"])


def test_submit_release_registers_a_pending_release_request(cleanup_designs):
    design = _new_design(cleanup_designs, "CLI-R1")

    row = submit_pending_release_approval(design, submitted_by="alice")

    assert row["design_id"] == design["design_id"]
    assert row["design_key"] == design["design_key"]
    assert row["revision"] == design["revision"]
    assert row["target"] == "RELEASED"
    assert row["submitted_by"] == "alice"
    assert row["fingerprint_fields"] == release_fingerprint_fields(
        design["design_id"], design["design_key"], design["revision"]
    )


def test_submit_release_rejects_a_design_missing_design_id(cleanup_designs):
    with pytest.raises(ApprovalCliError, match="design_id"):
        submit_pending_release_approval(
            {"design_key": "K", "revision": "1", "status": "DRAFT"}, submitted_by="alice"
        )


def test_submit_release_rejects_an_already_released_design(cleanup_designs, db_conn):
    design = _new_design(cleanup_designs, "CLI-R2")
    with db_conn.cursor() as cur:
        cur.execute("UPDATE designs SET status = 'RELEASED' WHERE id = %s", (design["design_id"],))
    db_conn.commit()
    design = read_design(design["design_id"])

    with pytest.raises(ApprovalCliError, match="RELEASED"):
        submit_pending_release_approval(design, submitted_by="alice")


def test_show_release_surfaces_the_full_fingerprint(cleanup_designs):
    design = _new_design(cleanup_designs, "CLI-R3")
    row = submit_pending_release_approval(design, submitted_by="alice")

    fetched = get_pending_release_approval(row["id"])
    described = describe_pending_release_approval(fetched)

    assert described["request_id"] == row["id"]
    assert described["design_id"] == design["design_id"]
    assert described["design_key"] == design["design_key"]
    assert described["revision"] == design["revision"]
    assert described["fingerprint_fields"] == release_fingerprint_fields(
        design["design_id"], design["design_key"], design["revision"]
    )


def test_approve_release_mints_a_real_receipt_without_touching_design_status(cleanup_designs):
    design = _new_design(cleanup_designs, "CLI-R4")
    row = submit_pending_release_approval(design, submitted_by="alice")

    result = decide_pending_release_approval(row["id"], "approve", approved_by="alice")

    assert result["status"] == "approved"
    receipt_dict = result["receipt"]
    receipt = DesignReleaseApprovalReceipt(**receipt_dict)
    assert receipt.approved_by == "alice"

    from designs.release_approval import _canonical_fingerprint

    expected_fingerprint = _canonical_fingerprint(
        release_fingerprint_fields(design["design_id"], design["design_key"], design["revision"])
    )
    assert receipt.decision_fingerprint == expected_fingerprint

    # Ticket 3 explicitly does NOT flip the design's status -- that's ticket
    # 4's job, once advance_design_status accepts a receipt at all.
    stored = read_design(design["design_id"])
    assert stored["status"] == "DRAFT"


def test_approved_release_request_is_excluded_from_the_pending_listing(cleanup_designs):
    design = _new_design(cleanup_designs, "CLI-R5")
    row = submit_pending_release_approval(design, submitted_by="alice")

    assert row["id"] in {
        r["id"] for r in list_pending_release_approvals(design_id=design["design_id"])
    }

    decide_pending_release_approval(row["id"], "approve", approved_by="alice")

    remaining = {r["id"] for r in list_pending_release_approvals(design_id=design["design_id"])}
    assert row["id"] not in remaining
    assert get_pending_release_approval(row["id"]) is None


def test_approve_release_writes_an_approved_audit_record(cleanup_designs, db_conn):
    design = _new_design(cleanup_designs, "CLI-R6")
    row = submit_pending_release_approval(design, submitted_by="alice")

    decide_pending_release_approval(row["id"], "approve", approved_by="alice")

    records = [
        r
        for r in fetch_audit_records(db_conn)
        if r["gate"] == GATE_DESIGN_RELEASE
        and r["fingerprint_fields"].get("design_id") == design["design_id"]
    ]
    assert len(records) == 1
    assert records[0]["outcome"] == OUTCOME_APPROVED
    assert records[0]["approved_by"] == "alice"
    assert records[0]["fingerprint_fields"] == release_fingerprint_fields(
        design["design_id"], design["design_key"], design["revision"]
    )


def test_refuse_release_leaves_the_design_and_pending_table_untouched(cleanup_designs):
    design = _new_design(cleanup_designs, "CLI-R7")
    row = submit_pending_release_approval(design, submitted_by="alice")

    result = decide_pending_release_approval(row["id"], "refuse", approved_by="bob")

    assert result["status"] == "refused"
    assert "receipt" not in result

    stored = read_design(design["design_id"])
    assert stored["status"] == "DRAFT"

    assert get_pending_release_approval(row["id"]) is None


def test_refuse_release_writes_a_refused_audit_record(cleanup_designs, db_conn):
    design = _new_design(cleanup_designs, "CLI-R8")
    row = submit_pending_release_approval(design, submitted_by="alice")

    decide_pending_release_approval(row["id"], "refuse", approved_by="bob")

    records = [
        r
        for r in fetch_audit_records(db_conn)
        if r["gate"] == GATE_DESIGN_RELEASE
        and r["fingerprint_fields"].get("design_id") == design["design_id"]
    ]
    assert len(records) == 1
    assert records[0]["outcome"] == OUTCOME_REFUSED
    assert records[0]["approved_by"] == "bob"


def test_decide_release_requires_approved_by(cleanup_designs):
    design = _new_design(cleanup_designs, "CLI-R9")
    row = submit_pending_release_approval(design, submitted_by="alice")

    with pytest.raises(ApprovalCliError, match="approved_by"):
        decide_pending_release_approval(row["id"], "approve", approved_by="")

    assert get_pending_release_approval(row["id"]) is not None


def test_decide_release_unknown_request_id_raises(cleanup_designs):
    with pytest.raises(ApprovalCliError, match="no pending release approval request"):
        decide_pending_release_approval(999_999_999, "approve", approved_by="alice")


def test_listing_release_scoped_to_one_design_id_ignores_other_designs(cleanup_designs):
    design_a = _new_design(cleanup_designs, "CLI-R10A")
    design_b = _new_design(cleanup_designs, "CLI-R10B")

    row_a = submit_pending_release_approval(design_a, submitted_by="alice")
    submit_pending_release_approval(design_b, submitted_by="alice")

    scoped = list_pending_release_approvals(design_id=design_a["design_id"])
    assert {r["id"] for r in scoped} == {row_a["id"]}
