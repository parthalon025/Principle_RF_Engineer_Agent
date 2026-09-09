"""Tests for orchestration/approval_cli.py -- the local, human-only surface
that grants (or refuses) a design-loop step approval end to end (issue #258
ticket 2 of the 5-ticket chain; see tests/test_approval_audit.py for
ticket 1).

Needs a real Postgres via DATABASE_URL (like tests/test_tooling.py):
`submit_pending_approval`/`decide_pending_approval` each own their
connection lifecycle and commit for real, so this file follows
tests/test_tooling.py's `cleanup_designs` convention rather than the
rolled-back `db_conn` fixture for anything that goes through this module's
own top-level functions. `db_conn` is still used, read-only, to check the
audit trail and the backing `designs` row afterward.

Five groups, matching the ticket's own non-negotiable constraints:

  1. The fail-closed regression -- approval_callback=None still always
     raises, unmodified.
  2. The structural test -- request_loop_step_approval is absent, by name,
     from both tool registries, before and after this module exists.
  3. The happy path -- submit, list, show, approve -- reaching
     advance_design_loop_step with a real receipt, list excludes it after.
  4. Refusal -- loop state, the designs row, and every other table are left
     completely untouched; the audit trail still gets a full record.
  5. The pending-approvals listing itself -- finds a loop sitting at a
     gated step, excludes one that has already advanced past it.
"""

from __future__ import annotations

import asyncio
import inspect
import os

import psycopg
import pytest
from dotenv import load_dotenv

from designs.service import read_design
from orchestration.approval import OrchestrationError, request_loop_step_approval
from orchestration.approval_audit import (
    GATE_LOOP_STEP,
    OUTCOME_APPROVED,
    OUTCOME_REFUSED,
    fetch_audit_records,
)
from orchestration.approval_cli import (
    ApprovalCliError,
    decide_pending_approval,
    describe_pending_approval,
    get_pending_approval,
    list_pending_approvals,
    submit_pending_approval,
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


# ---------------------------------------------------------------------------
# Group 2: structural -- request_loop_step_approval reaches neither tool
# registry, by name. Grep-based (agent/main.py's source) AND
# introspection-based (mcp_server/server.py's live registry), so a wrapper
# under a different name can't slip past a pure name search either.
# ---------------------------------------------------------------------------


def test_request_loop_step_approval_not_in_agent_all_tools():
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


def test_request_loop_step_approval_not_registered_on_the_mcp_server():
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
