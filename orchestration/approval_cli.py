"""The local, human-only surface that grants (or refuses) a real
`LoopStepApprovalReceipt` (issue #258 ticket 2 of the 5-ticket chain; see
`orchestration/approval_audit.py`'s docstring for ticket 1).

WHY THIS MODULE EXISTS. `orchestration/approval.py`'s own module docstring
says plainly: "THIS CODEBASE DOES NOT WIRE UP A REAL HUMAN-FACING APPROVAL
UI/WORKFLOW" -- `request_loop_step_approval` takes an `approval_callback`
and nothing in this project's agent/MCP tool wiring has ever supplied one,
on purpose (issue #98). The result: a design loop driven from the agent
conversation stops dead at its first `ARCHITECTURE` step and can never
reach `accept_design`. This module is that missing callback's caller --
"the door", not a change to "the lock". It never modifies, wraps, or
reimplements `request_loop_step_approval`; it calls it directly, exactly
as `tests/test_design_loop.py` already does, with a plain closure for
`approval_callback` that returns what the human at this terminal typed.

WHY A CLI, AND WHY IT IS SELF-CONTAINED (not a channel into some OTHER,
already-running process). `orchestration/approval.py`'s signing key is
generated once, in memory, per PROCESS (`_LOOP_APPROVAL_SIGNING_KEY`,
generated at that module's import time) and deliberately never persisted --
a receipt minted in one process cannot validate in a different one. Issue
#258's own Implementation Decisions describe hosting the human-only surface
"inside the same running process that will later validate the receipt" --
but this project HAS no single such process to host it inside:
`orchestration/design_loop.py`'s own "STATE DESIGN" section is explicit
that "this project has no long-running server process -- each agent/MCP
tool call is a discrete request" and `DesignLoopState` is a plain dict the
CALLER holds and passes back in, never server-side state. There is no
already-running process for a side-channel to attach to and no durable
place, short of the caller's own held dict, where a mid-iteration loop
state (one sitting at ARCHITECTURE/MEASUREMENT/REDESIGN_DECISION, waiting)
exists at all -- see `db/schema.sql`'s `pending_loop_step_approvals` table
comment for the full accounting of what is and is not in Postgres at that
moment.

This module resolves that the only way that is actually true to the
architecture: it is SELF-CONTAINED. One `decide_pending_approval` call
mints the receipt AND immediately calls `advance_design_loop_step` with
it, inside the SAME process, the same way `tests/test_tooling.py`'s
`_grant_and_advance` helper already does in a test. The signing key that
mints the receipt and the signing key that checks it are, by construction,
the same key, because they are the same Python object in the same
interpreter -- never handed across a process boundary. Nothing here tries
to inject a receipt into some OTHER, concurrently-running agent/MCP server
process; the resulting new loop-state dict is handed back to the human
(printed, or written to `--out`) for them to carry back into whatever
conversation is driving the loop, the same way a receipt itself already
crosses the tool boundary as inert JSON (design_loop.py's `_coerce_receipt`).

A CLI is also the simplest way to satisfy issue #258's own "human-only by
construction, not by convention" requirement: nothing in `agent/main.py` or
`mcp_server/server.py` imports this module, spawns it as a subprocess, or
can reach it in any way -- there is no code path from an agent/MCP tool
call to a Python `import orchestration.approval_cli`, so "reachable only by
someone with direct local access to the machine" is true by the absence of
any such path, not by a permission check this module would have to get
right. This repo has no existing web UI and no `[project.scripts]` console
entry-point convention in `pyproject.toml` -- its established way to hand a
human a locally-run script is direct invocation
(`uv run python <path>`, e.g. `db/apply_schema.py`'s own docstring: "Usage:
uv run python db/apply_schema.py"). This module follows that existing
convention rather than inventing a new one: run it as
`uv run python -m orchestration.approval_cli <subcommand> ...`.

THE WORKFLOW, END TO END:

  1. A human driving a design loop (from the agent conversation, or a
     script) hits a gated step -- `advance_design_loop_step` raises
     `OrchestrationError` because `current_step` is in `GATED_STEPS` and no
     approval was supplied. The state dict they already hold (from
     `start_design_loop`/`advance_design_loop_step`) and the `step_input`
     they were about to submit are saved to two JSON files.
  2. `submit_pending_approval` (CLI: `submit`) registers that pending
     request in `pending_loop_step_approvals` -- computing the EXACT same
     `fingerprint_fields` `advance_loop_step` itself would check
     (`orchestration.design_loop._decision_fingerprint_fields`, imported
     and called directly here, never reimplemented) and storing them
     alongside the full state/step_input needed to complete the step later.
  3. `list_pending_approvals` (CLI: `list`) shows every request still
     sitting in that table -- across every design/loop, since a row is only
     ever deleted once it is resolved (approved or refused). This is a
     genuinely different question from `designs.service`'s own read
     patterns, which all key off an already-known `design_id`; this module
     adds nothing to `designs/service.py` and calls no function there.
  4. `describe_pending_approval` (CLI: `show <id>`) shows the human the
     full, unsummarized `fingerprint_fields` for one request, plus every
     `validity`-flagged (load-bearing) warning already recorded on any
     decision from that SAME loop iteration -- see `_load_bearing_warnings`.
  5. `decide_pending_approval` (CLI: `approve <id>` / `refuse <id>`) is the
     only place this module actually calls `request_loop_step_approval`.
     Approving supplies `approval_callback=lambda *_: True`; refusing
     supplies `approval_callback=lambda *_: False`, which makes
     `request_loop_step_approval` itself raise `OrchestrationError` -- read
     directly off that function's own body, not guessed. EITHER outcome
     writes exactly one `orchestration.approval_audit.append_audit_record`
     row (`gate=GATE_LOOP_STEP`) before anything else happens. Only a
     successful approval goes on to call
     `orchestration.tooling.advance_design_loop_step` with the minted
     receipt; a refusal returns immediately, so the loop's state, the
     `designs` row, and every other table are left completely untouched --
     exactly `check_loop_step_approval_gate`'s own existing behavior for a
     missing/invalid approval, never reimplemented here. The pending row is
     deleted only once its outcome is durable: after the advance succeeds
     (approve) or immediately after the audit record commits (refuse) -- a
     failure in between leaves the row in place rather than losing a
     request nobody has actually resolved yet.

WHAT THIS MODULE DOES NOT DO. It does not call `orchestration.approval.
request_loop_step_approval` with anything other than a real, freshly
supplied True/False from THIS invocation's own `decide` call -- no
environment variable, config flag, or magic string can satisfy it (issue
#258 story #31). It never constructs a `LoopStepApprovalReceipt` by hand.
It is not imported by, and does not import, `agent/main.py` or
`mcp_server/server.py` -- see `tests/test_approval_cli.py`'s structural
test for the two-sided proof that `request_loop_step_approval` itself
never reaches either tool registry, by name.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

import designs.db as designs_db
from orchestration.approval import (
    LoopStepApprovalReceipt,
    OrchestrationError,
    request_loop_step_approval,
)
from orchestration.approval_audit import (
    GATE_LOOP_STEP,
    OUTCOME_APPROVED,
    OUTCOME_REFUSED,
    append_audit_record,
)
from orchestration.design_loop import (
    GATED_STEPS,
    DesignLoopState,
    DesignStep,
    _decision_fingerprint_fields,
)
from orchestration.tooling import advance_design_loop_step

__all__ = [
    "ApprovalCliError",
    "decide_pending_approval",
    "describe_pending_approval",
    "get_pending_approval",
    "list_pending_approvals",
    "submit_pending_approval",
]


class ApprovalCliError(RuntimeError):
    """Raised for a malformed request to this surface -- an unknown
    request id, a non-gated current step, a missing identity -- as
    distinct from `OrchestrationError` (the underlying gate itself
    refusing). Checked before any database write, same convention as
    `orchestration.approval_audit.InvalidAuditRecordError`."""


def _connect() -> psycopg.Connection:
    return designs_db.get_connection()


def submit_pending_approval(
    loop_state: dict[str, Any],
    step_input: dict[str, Any],
    submitted_by: str,
) -> dict[str, Any]:
    """Register one pending gated-step approval request, computed from a
    caller-held `loop_state` dict (exactly `start_new_design_loop`'s or
    `advance_design_loop_step`'s own return shape) and the `step_input` the
    human is about to submit for `loop_state["current_step"]`.

    Raises `ApprovalCliError` -- naming exactly what's wrong, before any
    database write -- if `loop_state` carries no `design_id` (it did not
    come from `orchestration.tooling`), if `current_step` is not one of
    `GATED_STEPS`, or if `submitted_by` is blank.
    """
    if not submitted_by or not submitted_by.strip():
        raise ApprovalCliError(
            "submitted_by (the identity of the human registering this request) is required"
        )
    design_id = loop_state.get("design_id")
    if design_id is None:
        raise ApprovalCliError(
            "loop_state has no 'design_id' -- it must come from "
            "orchestration.tooling.start_new_design_loop (or a prior "
            "advance_design_loop_step call), not a bare "
            "orchestration.design_loop.DesignLoopState.to_dict()"
        )
    try:
        current_step = DesignStep(loop_state.get("current_step"))
    except ValueError as exc:
        raise ApprovalCliError(
            f"loop_state['current_step']={loop_state.get('current_step')!r} is not a "
            "recognized design-loop step"
        ) from exc
    if current_step not in GATED_STEPS:
        raise ApprovalCliError(
            f"loop_state is currently at step {current_step.value!r}, which is not "
            f"a gated step ({sorted(s.value for s in GATED_STEPS)}) -- there is "
            "nothing for a human to approve here."
        )

    state = DesignLoopState.from_dict(loop_state)
    fingerprint_fields = _decision_fingerprint_fields(state, current_step, step_input)

    conn = _connect()
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO pending_loop_step_approvals
                    (design_id, loop_id, iteration, step, fingerprint_fields,
                     loop_state, step_input, submitted_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    design_id,
                    state.loop_id,
                    state.iteration,
                    current_step.value,
                    Json(fingerprint_fields),
                    Json(loop_state),
                    Json(step_input),
                    submitted_by,
                ),
            )
            row = cur.fetchone()
            assert row is not None
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return row


def list_pending_approvals(design_id: int | None = None) -> list[dict[str, Any]]:
    """Every currently-pending gated approval request, oldest first.

    A row exists here if and only if it has not yet been resolved (see this
    module's docstring): `decide_pending_approval` deletes the row the
    moment its outcome is durable, so "pending" is exactly "still here" --
    no join against `approval_audit_log` is needed to exclude an already-
    decided request; there is nothing left to exclude.
    """
    conn = _connect()
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            if design_id is None:
                cur.execute("SELECT * FROM pending_loop_step_approvals ORDER BY submitted_at")
            else:
                cur.execute(
                    "SELECT * FROM pending_loop_step_approvals "
                    "WHERE design_id = %s ORDER BY submitted_at",
                    (design_id,),
                )
            return cur.fetchall()
    finally:
        conn.close()


def get_pending_approval(request_id: int) -> dict[str, Any] | None:
    """One pending request row by id, or None if it does not exist (already
    resolved, or never submitted)."""
    conn = _connect()
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM pending_loop_step_approvals WHERE id = %s", (request_id,))
            return cur.fetchone()
    finally:
        conn.close()


def _load_bearing_warnings(loop_state: dict[str, Any], iteration: int) -> list[dict[str, Any]]:
    """Every `validity`-flagged warning already recorded on a decision from
    THIS SAME loop iteration (issue #258 story #23/#21) -- read straight off
    `loop_state["decisions"]`, never re-derived. `design_loop.py`'s own
    calculation/simulation handlers already attach a `validity` list to
    `result` naming each load-bearing assumption (see
    `rf_tools/absorber.py`, `rf_tools/transmissive_absorber.py`); this
    walks every decision tagged with `iteration` and flattens whatever is
    there, tagging each entry with the step it came from so the human can
    tell which decision it belongs to. Never withholds one -- this project's
    "warn, never block" charter means every load-bearing warning on the
    table gets shown, not filtered to a subset."""
    warnings: list[dict[str, Any]] = []
    for decision in loop_state.get("decisions", []):
        if decision.get("iteration") != iteration:
            continue
        result = decision.get("result") or {}
        for entry in result.get("validity") or []:
            warnings.append({"step": decision.get("step"), **entry})
    return warnings


def describe_pending_approval(row: dict[str, Any]) -> dict[str, Any]:
    """The full, unsummarized view of one pending request a human reviews
    before deciding: which loop, which iteration, which step, the exact
    decision content the resulting receipt will be bound to (`orchestration.
    approval.request_loop_step_approval`'s own `fingerprint_fields`
    argument, verbatim -- never paraphrased), and every load-bearing warning
    already recorded for this iteration (see `_load_bearing_warnings`)."""
    return {
        "request_id": row["id"],
        "design_id": row["design_id"],
        "loop_id": row["loop_id"],
        "iteration": row["iteration"],
        "step": row["step"],
        "fingerprint_fields": row["fingerprint_fields"],
        "submitted_by": row["submitted_by"],
        "submitted_at": str(row["submitted_at"]),
        "warnings": _load_bearing_warnings(row["loop_state"], row["iteration"]),
    }


def _delete_pending(conn: psycopg.Connection, request_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM pending_loop_step_approvals WHERE id = %s", (request_id,))


def decide_pending_approval(
    request_id: int,
    decision: str,
    approved_by: str,
) -> dict[str, Any]:
    """Approve or refuse one pending request, by id. `decision` must be
    `"approve"` or `"refuse"`.

    Calls `orchestration.approval.request_loop_step_approval` directly and
    unmodified -- the ONLY call to it anywhere in this module -- with
    `fingerprint_fields` exactly as stored by `submit_pending_approval` and
    an `approval_callback` that returns `True` for an approval or `False`
    for a refusal; nothing else in this codebase decides that outcome. A
    refusal makes `request_loop_step_approval` itself raise
    `OrchestrationError` (read directly off that function's own body), which
    this function catches -- it is the expected shape of "refused", not an
    error in this module.

    EITHER outcome writes exactly one `orchestration.approval_audit.
    append_audit_record` row (`gate=GATE_LOOP_STEP`) before anything else
    observable happens. Only an approval goes on to call `orchestration.
    tooling.advance_design_loop_step` with the resulting receipt; a refusal
    returns immediately, so the loop's state, the backing `designs` row, and
    every table `advance_design_loop_step` could otherwise write to are left
    completely untouched -- this function never calls it on the refusal
    path, so there is no code path here that could touch loop state on a
    refusal.

    Raises `ApprovalCliError` for an unknown request id, an unknown
    `decision` value, or a blank `approved_by` -- checked before
    `request_loop_step_approval` is ever called.
    """
    if decision not in ("approve", "refuse"):
        raise ApprovalCliError(f"decision must be 'approve' or 'refuse', got {decision!r}")
    if not approved_by or not approved_by.strip():
        raise ApprovalCliError(
            "approved_by (the identity of the approving/refusing human) is required"
        )

    row = get_pending_approval(request_id)
    if row is None:
        raise ApprovalCliError(
            f"no pending approval request with id={request_id} -- it may already "
            "have been resolved, or never submitted (see submit_pending_approval)"
        )

    fingerprint_fields = row["fingerprint_fields"]
    approve = decision == "approve"

    def _callback(_fields: dict[str, Any]) -> bool:
        return approve

    conn = _connect()
    try:
        try:
            receipt: LoopStepApprovalReceipt | None
            try:
                receipt = request_loop_step_approval(
                    fingerprint_fields, approved_by=approved_by, approval_callback=_callback
                )
            except OrchestrationError:
                if approve:
                    # approval_callback above always returns True for an
                    # approve decision -- this branch is unreachable in
                    # practice (approved_by was already validated above)
                    # and exists only so a future change to
                    # request_loop_step_approval's own raise conditions
                    # cannot silently mint a fabricated receipt here.
                    raise
                receipt = None

            outcome = OUTCOME_APPROVED if receipt is not None else OUTCOME_REFUSED
            append_audit_record(conn, GATE_LOOP_STEP, fingerprint_fields, approved_by, outcome)

            if receipt is None:
                # Refusal: the gate was never satisfied, so nothing that
                # could touch loop state is called -- advance_design_loop_step
                # is not reachable from this branch at all.
                _delete_pending(conn, request_id)
                conn.commit()
                return {
                    "status": "refused",
                    "request_id": request_id,
                    "fingerprint_fields": fingerprint_fields,
                }

            conn.commit()
        except Exception:
            conn.rollback()
            raise
    finally:
        conn.close()

    # The receipt is now durable (the audit row committed above) even
    # though the receipt itself is not. Advancing the loop is a SEPARATE
    # action, on its own connection (orchestration.tooling.
    # advance_design_loop_step owns its own transaction, same as every
    # other top-level tooling call) -- if this raises, the pending row is
    # deliberately left in place rather than deleted, so the request is not
    # silently lost; the human can retry `decide` for the same id, which
    # mints a fresh (but fingerprint-identical) receipt and tries again.
    new_state = advance_design_loop_step(
        row["loop_state"], row["step_input"], approval=receipt.to_dict()
    )

    conn = _connect()
    try:
        _delete_pending(conn, request_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {"status": "approved", "request_id": request_id, "new_state": new_state}


# ---------------------------------------------------------------------------
# CLI. `uv run python -m orchestration.approval_cli <subcommand> ...` --
# this repo's own established convention for a locally-run script (see this
# module's docstring); there is no `[project.scripts]` entry in
# pyproject.toml to extend.
# ---------------------------------------------------------------------------


def _read_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _cmd_list(args: argparse.Namespace) -> int:
    _print(list_pending_approvals(design_id=args.design_id))
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    row = get_pending_approval(args.request_id)
    if row is None:
        print(f"no pending approval request with id={args.request_id}", file=sys.stderr)
        return 1
    _print(describe_pending_approval(row))
    return 0


def _cmd_submit(args: argparse.Namespace) -> int:
    loop_state = _read_json(args.state)
    step_input = _read_json(args.step_input)
    row = submit_pending_approval(loop_state, step_input, submitted_by=args.submitted_by)
    _print({"request_id": row["id"], "step": row["step"], "loop_id": row["loop_id"]})
    return 0


def _cmd_decide(decision: str, args: argparse.Namespace) -> int:
    result = decide_pending_approval(args.request_id, decision, approved_by=args.approved_by)
    if result["status"] == "approved" and args.out:
        Path(args.out).write_text(
            json.dumps(result["new_state"], indent=2, default=str), encoding="utf-8"
        )
    _print(
        {k: v for k, v in result.items() if k != "new_state"}
        | (
            {"new_state_written_to": args.out}
            if result["status"] == "approved" and args.out
            else {}
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="orchestration.approval_cli",
        description=(
            "Local, human-only surface for granting or refusing a design-loop "
            "step approval (issue #258). Never reachable from the agent "
            "conversation -- run this directly, at a terminal, on the machine "
            "you trust."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List every currently-pending gated approval request.")
    p_list.add_argument("--design-id", type=int, default=None)
    p_list.set_defaults(func=_cmd_list)

    p_show = sub.add_parser("show", help="Show one pending request's full fingerprint + warnings.")
    p_show.add_argument("request_id", type=int)
    p_show.set_defaults(func=_cmd_show)

    p_submit = sub.add_parser("submit", help="Register a new pending gated-step approval request.")
    p_submit.add_argument("--state", required=True, help="Path to the loop_state JSON file.")
    p_submit.add_argument("--step-input", required=True, help="Path to the step_input JSON file.")
    p_submit.add_argument("--submitted-by", required=True)
    p_submit.set_defaults(func=_cmd_submit)

    p_approve = sub.add_parser("approve", help="Approve a pending request and advance the loop.")
    p_approve.add_argument("request_id", type=int)
    p_approve.add_argument("--approved-by", required=True)
    p_approve.add_argument("--out", default=None, help="Path to write the loop's new state JSON.")
    p_approve.set_defaults(func=lambda a: _cmd_decide("approve", a))

    p_refuse = sub.add_parser("refuse", help="Refuse a pending request; loop state is untouched.")
    p_refuse.add_argument("request_id", type=int)
    p_refuse.add_argument("--approved-by", required=True, help="Identity of the refusing human.")
    p_refuse.set_defaults(func=lambda a: _cmd_decide("refuse", a))

    return parser


def main(argv: list[str] | None = None) -> int:
    from dotenv import load_dotenv

    load_dotenv()
    if "DATABASE_URL" not in os.environ:
        print("DATABASE_URL is not set -- see .env / README.md", file=sys.stderr)
        return 2
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ApprovalCliError, OrchestrationError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
