"""The RELEASED human-approval gate for a design (issue #145; ADR-0007, ADR-0016).

`docs/OPERATIONS.md` states it outright -- "RELEASED requires human approval"
-- and ADR-0007 carries that into `designs.status` while deferring the
mechanism. This module is the mechanism.

In plain terms: marking a design RELEASED is the point where engineering work
becomes something a factory may build. That step must never happen because a
flag was flipped or a model decided it looked finished. It requires a receipt
that a specific named human approved this specific design at this specific
revision, signed so it cannot be edited or reused afterwards.

**Why a separate receipt type from `orchestration.approval`'s.** That module's
docstring sets the rule: an approval for one gate must never satisfy another,
because mixing receipt types lets one kind of approval silently pass an
unrelated check. "May this design loop advance past its MEASUREMENT step" and
"may this design be released for manufacture" are different questions asked of
different people at different moments. So this gate gets its own receipt class
and its own signing key, and each gate's `isinstance` check rejects the
other's receipt outright. `tests/test_design_release_approval.py` holds that
property in both directions.

**The human-facing approval workflow is `orchestration/approval_cli.py`.** As
with the loop gate, `approval_callback` defaults to `None`, and in that state
`request_design_release_approval` always raises rather than fabricating an
approval -- no agent/MCP tool in this codebase ever supplies one. The real
callback comes from a human running `uv run python -m orchestration.
approval_cli <subcommand>` locally, on the machine running the live session
(issue #258); that CLI calls `request_design_release_approval` directly and
unmodified, and is not importable from, and does not import, `agent/main.py`
or `mcp_server/server.py` (see that module's own docstring and
`tests/test_approval_cli.py`'s structural tests). Without a human running that
CLI, nothing can reach RELEASED -- which is the correct behaviour, not a gap
to route around.

Approvals are process-local and do not survive a restart, by design: the
signing key is generated at import.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from designs.models import DesignStatus

__all__ = [
    "DesignReleaseApprovalError",
    "DesignReleaseApprovalReceipt",
    "check_design_release_approval_gate",
    "release_fingerprint_fields",
    "request_design_release_approval",
]

# Process-local signing key for design-release receipts. Deliberately its own,
# not shared with orchestration/approval.py's loop-step key -- see the module
# docstring. Two receipts with identical contents therefore carry different
# tokens, so one cannot be retyped into the other's class and pass.
_RELEASE_APPROVAL_SIGNING_KEY = secrets.token_bytes(32)


class DesignReleaseApprovalError(RuntimeError):
    """Raised when the design-release approval gate is not satisfied."""


def _canonical_fingerprint(fields: dict[str, Any]) -> str:
    """A stable SHA-256 fingerprint of `fields`, order-independent."""
    canonical = json.dumps(fields, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sign(fingerprint: str, approved_by: str, granted_at: float) -> str:
    raw = f"{fingerprint}:{approved_by}:{granted_at!r}"
    return hmac.new(_RELEASE_APPROVAL_SIGNING_KEY, raw.encode("utf-8"), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class DesignReleaseApprovalReceipt:
    """Proof that a human approved releasing ONE specific design revision.

    Only ever constructed by `request_design_release_approval` below, or
    reconstructed field-for-field from its `to_dict()` output after crossing
    an agent/MCP JSON tool boundary.
    """

    token: str
    decision_fingerprint: str
    approved_by: str
    granted_at: float

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable form, for crossing a tool boundary and being
        rebuilt on the other side via `DesignReleaseApprovalReceipt(**d)`."""
        return {
            "token": self.token,
            "decision_fingerprint": self.decision_fingerprint,
            "approved_by": self.approved_by,
            "granted_at": self.granted_at,
        }


def release_fingerprint_fields(
    design_id: int,
    design_key: str,
    revision: int | str,
    target: DesignStatus | str = DesignStatus.RELEASED,
) -> dict[str, Any]:
    """The decision content a release receipt is bound to.

    `revision` is in here deliberately: approving revision 2 must not release
    revision 3. So is `design_key`, so a receipt cannot follow a row id that
    was reused. `designs.revision` is TEXT in the schema; an int is accepted
    too and fingerprinted by its string form.
    """
    return {
        "design_id": design_id,
        "design_key": design_key,
        "revision": revision,
        "target": str(target),
    }


def request_design_release_approval(
    fingerprint_fields: dict[str, Any],
    approved_by: str | None = None,
    approval_callback: Callable[[dict[str, Any]], bool] | None = None,
) -> DesignReleaseApprovalReceipt:
    """The ONLY way to obtain a `DesignReleaseApprovalReceipt`.

    Does nothing consequential itself -- no status changes, nothing is written
    -- it is purely a decision-and-receipt step, kept separate from the write
    so a distinct, auditable approval action must happen first.

    `approval_callback` is called with `fingerprint_fields` and must return
    True for "a human approved this exact release". With no callback this
    function always raises: see the module docstring.
    """
    if approval_callback is None:
        raise DesignReleaseApprovalError(
            "No human-approval mechanism is configured in this codebase yet. "
            "request_design_release_approval() refuses to fabricate an "
            "approval on its own -- a design must never reach RELEASED "
            "autonomously (docs/OPERATIONS.md 'RELEASED requires human "
            "approval'; docs/adr/0007; docs/BUILD_PLAN.md's Phase 12 'Never "
            "allow autonomous manufacturing release'). Pass an explicit "
            "approval_callback wired to a real human-facing approval workflow "
            "once one exists; until then no design can be released."
        )
    if not approved_by:
        raise DesignReleaseApprovalError(
            "approved_by (the identity of the approving human) is required "
            "for an auditable release-approval receipt"
        )

    if not approval_callback(fingerprint_fields):
        raise DesignReleaseApprovalError(
            f"Design release was not approved (approval_callback returned a "
            f"falsy result for approved_by={approved_by!r})"
        )

    fingerprint = _canonical_fingerprint(fingerprint_fields)
    granted_at = time.time()
    return DesignReleaseApprovalReceipt(
        token=_sign(fingerprint, approved_by, granted_at),
        decision_fingerprint=fingerprint,
        approved_by=approved_by,
        granted_at=granted_at,
    )


def _problems_with(receipt: Any, fingerprint_fields: dict[str, Any]) -> list[str]:
    """Everything wrong with `receipt` as an approval for these fields."""
    if receipt is None:
        return [
            "no approval was provided -- a DesignReleaseApprovalReceipt from "
            "request_design_release_approval() is required"
        ]
    if not isinstance(receipt, DesignReleaseApprovalReceipt):
        return [
            "the approval must be a DesignReleaseApprovalReceipt returned by "
            "request_design_release_approval() (or reconstructed field-for-"
            f"field from its to_dict() output), not a bare "
            f"{type(receipt).__name__} -- a plain string/boolean token, or a "
            "receipt belonging to a different approval gate such as the "
            "design loop's, cannot be accepted here"
        ]

    problems: list[str] = []
    if receipt.decision_fingerprint != _canonical_fingerprint(fingerprint_fields):
        problems.append(
            "the approval receipt's decision_fingerprint does not match this "
            "release -- it was granted for a different design or revision; "
            "request approval again for this exact design revision"
        )
    expected = _sign(receipt.decision_fingerprint, receipt.approved_by, receipt.granted_at)
    if not hmac.compare_digest(expected, receipt.token):
        problems.append(
            "the approval receipt's signature is invalid -- it was not issued "
            "by request_design_release_approval() in this process (or the "
            "process that issued it has since restarted; approvals do not "
            "survive a restart, by design)"
        )
    return problems


def check_design_release_approval_gate(approval: Any, fingerprint_fields: dict[str, Any]) -> None:
    """Raise `DesignReleaseApprovalError` naming exactly what is missing
    unless `approval` is a valid receipt for THIS exact release --
    signature-verified and fingerprint-matched, not merely present."""
    problems = _problems_with(approval, fingerprint_fields)
    if problems:
        raise DesignReleaseApprovalError(
            "Design release refused: moving a design to RELEASED requires a "
            "distinct, auditable human-approval receipt (docs/OPERATIONS.md, "
            "docs/adr/0007, docs/BUILD_PLAN.md's Phase 12 'Never allow "
            "autonomous manufacturing release'). Missing/failed checks:\n"
            + "\n".join(f"  - {p}" for p in problems)
        )
