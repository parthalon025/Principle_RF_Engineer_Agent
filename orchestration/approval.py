"""Loop-step human-approval gate (issue #46, Phase 12).

Per this project's non-negotiable constraint (README.md, docs/
BUILD_PLAN.md's Phase 12 "Never allow autonomous manufacturing release",
this ticket's own framing): a consequential, non-calculation/non-simulation
step in the design-iteration loop must never proceed on a flippable
boolean -- it requires a real, HMAC-SHA256-signed receipt bound to the
exact fingerprint of the one specific decision it approves.

`LoopStepApprovalReceipt` is its own dedicated receipt type with its own
signing key, deliberately not interchangeable with any other approval
concept this project might ever grow: "may this loop advance past its
ARCHITECTURE/MEASUREMENT/REDESIGN_DECISION step" is a business-level
decision, structurally distinct from any other kind of gate, and mixing
receipt types would let one kind of approval silently satisfy an unrelated
gate. `check_loop_step_approval_gate` below does a bare
`isinstance(receipt, LoopStepApprovalReceipt)` check, so anything else is
rejected outright -- a plain string/boolean, a forged dict, or a receipt
type belonging to a different gate entirely.

THE MECHANISM:

  1. `request_loop_step_approval(fingerprint_fields, approved_by,
     approval_callback)` is the ONLY way to obtain a `LoopStepApprovalReceipt`.
     It does nothing consequential itself -- no step action runs, no state
     advances -- it only decides whether to grant a receipt.

  2. THIS CODEBASE DOES NOT WIRE UP A REAL HUMAN-FACING APPROVAL UI/
     WORKFLOW. `approval_callback` defaults to None, and calling with
     `approval_callback=None` (the only way a Python callable cannot cross
     an agent/MCP JSON tool boundary, so the only way any agent/MCP tool
     wiring in this project could ever call it) ALWAYS raises
     OrchestrationError. This project's `orchestration/design_loop.py`
     deliberately does NOT wire this function up as its own agent/MCP tool
     (the ticket's tool-surface budget is three tools: start, advance,
     inspect -- see design_loop.py's module docstring) -- it is exercised
     directly in Python (by tests, and by any future human-approval
     workflow that supplies a real `approval_callback`).

  3. A receipt this function DOES grant is cryptographically bound (HMAC-
     SHA256, keyed by a random secret generated once per process at import
     time, never exposed) to a canonical fingerprint of the exact decision
     it approves (loop id, iteration, step, and the decision content --
     see design_loop.py's `_decision_fingerprint_fields`). A receipt
     granted for one decision cannot be replayed against a different one
     (different loop, different iteration, different step, or different
     decision content) -- the fingerprint mismatch is caught and named
     explicitly by `check_loop_step_approval_gate`. The signing key lives
     only in this process's memory (never persisted, logged, or returned to
     a caller), so a receipt cannot be forged without having gone through
     `request_loop_step_approval` in this same process, and does not
     survive a process restart.

This sandboxed test/CI environment satisfies NONE of these signals by
default (no approval callback exists anywhere in this project's agent/MCP
tool wiring) -- see tests/test_design_loop.py for the real, unmockable
proof.
"""

import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Process-local signing key for loop-step approval receipts. Generated once,
# at import time -- see this module's docstring for why this gate's receipt
# type (and its signing key) is deliberately its own, not shared with any
# other approval concept.
_LOOP_APPROVAL_SIGNING_KEY = secrets.token_bytes(32)


class OrchestrationError(RuntimeError):
    """Raised when a design-iteration-loop step's human-approval gate is not
    satisfied."""


def _canonical_fingerprint(fields: dict[str, Any]) -> str:
    """A stable SHA-256 fingerprint of `fields`."""
    canonical = json.dumps(fields, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LoopStepApprovalReceipt:
    """Proof that a human approved ONE specific design-loop step
    advancement. Only ever constructed by request_loop_step_approval below
    (or reconstructed field-for-field from its to_dict() output, e.g. after
    crossing an agent/MCP JSON tool boundary and back)."""

    token: str
    decision_fingerprint: str
    approved_by: str
    granted_at: float

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable form, for crossing the agent/MCP tool
        boundary and for reconstructing an equivalent
        LoopStepApprovalReceipt on the other side via
        LoopStepApprovalReceipt(**that_dict)."""
        return {
            "token": self.token,
            "decision_fingerprint": self.decision_fingerprint,
            "approved_by": self.approved_by,
            "granted_at": self.granted_at,
        }


def request_loop_step_approval(
    fingerprint_fields: dict[str, Any],
    approved_by: str | None = None,
    approval_callback: Callable[[dict[str, Any]], bool] | None = None,
) -> LoopStepApprovalReceipt:
    """The ONLY way to obtain a LoopStepApprovalReceipt. Does nothing
    consequential itself -- no design-loop step action runs, no loop state
    advances -- it is purely a decision-and-receipt step, deliberately kept
    separate from advance_loop_step so a distinct, auditable approval action
    must happen first.

    `fingerprint_fields` is the exact decision-content fingerprint the
    resulting receipt is bound to -- see design_loop.py's
    `_decision_fingerprint_fields`.

    `approval_callback`, if given, is called with `fingerprint_fields` and
    must return True/False for "a human approved this exact decision" /
    "not approved". THIS CODEBASE DOES NOT WIRE UP A REAL HUMAN-FACING
    APPROVAL UI/WORKFLOW, so `approval_callback` defaults to None, and when
    it is None this function ALWAYS raises OrchestrationError rather than
    fabricating an approval -- see this module's docstring, point 2.
    """
    if approval_callback is None:
        raise OrchestrationError(
            "No human-approval mechanism is configured in this codebase yet. "
            "request_loop_step_approval() refuses to fabricate an approval on "
            "its own -- the controlled design-iteration loop never advances "
            "past architecture decisions, physical measurement, or a "
            "redesign/iteration decision autonomously (README.md, docs/"
            "BUILD_PLAN.md's Phase 12 'Never allow autonomous manufacturing "
            "release'). Pass an explicit approval_callback wired to a real "
            "human-facing approval workflow once one exists; until then this "
            "function -- and therefore every advance_loop_step() call gated "
            "behind it -- structurally cannot proceed."
        )
    if not approved_by:
        raise OrchestrationError(
            "approved_by (the identity of the approving human) is required "
            "for an auditable approval receipt"
        )

    approved = approval_callback(fingerprint_fields)
    if not approved:
        raise OrchestrationError(
            f"Design-loop step advancement was not approved (approval_callback "
            f"returned a falsy result for approved_by={approved_by!r})"
        )

    fingerprint = _canonical_fingerprint(fingerprint_fields)
    granted_at = time.time()
    raw = f"{fingerprint}:{approved_by}:{granted_at!r}"
    token = hmac.new(_LOOP_APPROVAL_SIGNING_KEY, raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return LoopStepApprovalReceipt(
        token=token,
        decision_fingerprint=fingerprint,
        approved_by=approved_by,
        granted_at=granted_at,
    )


def _verify_loop_step_approval_receipt(
    receipt: Any, fingerprint_fields: dict[str, Any]
) -> list[str]:
    """Return a list of problems with `receipt` as an approval for
    `fingerprint_fields` (empty list == valid). Used by
    check_loop_step_approval_gate below."""
    problems: list[str] = []

    if receipt is None:
        problems.append(
            "no approval was provided -- a LoopStepApprovalReceipt from "
            "request_loop_step_approval() is required"
        )
        return problems

    if not isinstance(receipt, LoopStepApprovalReceipt):
        problems.append(
            "the approval must be a LoopStepApprovalReceipt returned by "
            "request_loop_step_approval() (or reconstructed field-for-field "
            f"from its to_dict() output), not a bare {type(receipt).__name__} "
            "-- a plain string/boolean token, or a receipt type belonging to "
            "a different approval gate, cannot be accepted here"
        )
        return problems

    expected_fingerprint = _canonical_fingerprint(fingerprint_fields)
    if receipt.decision_fingerprint != expected_fingerprint:
        problems.append(
            "the approval receipt's decision_fingerprint does not match this "
            "step's decision content -- it was granted for a different loop/"
            "iteration/step/decision; request approval again for this exact "
            "decision"
        )

    raw = f"{receipt.decision_fingerprint}:{receipt.approved_by}:{receipt.granted_at!r}"
    expected_token = hmac.new(
        _LOOP_APPROVAL_SIGNING_KEY, raw.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_token, receipt.token):
        problems.append(
            "the approval receipt's signature is invalid -- it was not issued "
            "by request_loop_step_approval() in this process (or the process "
            "that issued it has since restarted; approvals do not survive a "
            "restart, by design)"
        )

    return problems


def check_loop_step_approval_gate(approval: Any, fingerprint_fields: dict[str, Any]) -> None:
    """Raise OrchestrationError naming exactly what's missing unless
    `approval` is a valid LoopStepApprovalReceipt for THIS exact
    `fingerprint_fields` -- signature-verified and fingerprint-matched, not
    merely present. Called by advance_loop_step() for every gated step
    (ARCHITECTURE, MEASUREMENT, REDESIGN_DECISION -- see design_loop.py's
    GATED_STEPS), BEFORE that step's action runs or the loop advances."""
    missing = _verify_loop_step_approval_receipt(approval, fingerprint_fields)
    if missing:
        raise OrchestrationError(
            "Design-loop step advancement refused: this step requires a "
            "distinct, auditable human-approval receipt before the loop may "
            "proceed past it (README.md, docs/BUILD_PLAN.md's Phase 12 "
            "'Never allow autonomous manufacturing release'). Missing/failed "
            "checks:\n" + "\n".join(f"  - {m}" for m in missing)
        )
