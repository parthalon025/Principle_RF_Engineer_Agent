"""The RELEASED human-approval gate (issue #145, ADR-0007).

Mirrors `tests/test_approval.py`'s discipline for the design-loop gate. The
central property, and the reason this receipt type exists separately from
`LoopStepApprovalReceipt`: an approval for one gate must never satisfy
another. `orchestration/approval.py`'s module docstring states that rule;
these tests hold this gate to it in both directions.
"""

import dataclasses

import pytest

from designs.models import DesignStatus
from designs.release_approval import (
    DesignReleaseApprovalError,
    DesignReleaseApprovalReceipt,
    check_design_release_approval_gate,
    release_fingerprint_fields,
    request_design_release_approval,
)

FIELDS = {"design_id": 7, "design_key": "ADX-1", "revision": 2, "target": "RELEASED"}


def _granted(fields=None, approved_by="a.engineer"):
    return request_design_release_approval(
        fields or FIELDS, approved_by=approved_by, approval_callback=lambda _: True
    )


# --- the refusal to fabricate --------------------------------------------


def test_without_an_approval_callback_it_refuses_rather_than_approving():
    """No human-facing approval workflow is wired up in this codebase. The
    honest behaviour is to refuse, not to invent an approval -- the same
    stance orchestration/approval.py takes for the loop gate."""
    with pytest.raises(DesignReleaseApprovalError, match="No human-approval"):
        request_design_release_approval(FIELDS, approved_by="a.engineer")


def test_an_approval_callback_that_declines_grants_no_receipt():
    with pytest.raises(DesignReleaseApprovalError, match="not approved"):
        request_design_release_approval(
            FIELDS, approved_by="a.engineer", approval_callback=lambda _: False
        )


def test_the_approving_identity_is_required():
    with pytest.raises(DesignReleaseApprovalError, match="approved_by"):
        request_design_release_approval(FIELDS, approved_by="", approval_callback=lambda _: True)


def test_the_callback_receives_the_exact_fields_being_approved():
    seen = {}
    request_design_release_approval(
        FIELDS,
        approved_by="a.engineer",
        approval_callback=lambda fields: seen.update(fields) or True,
    )
    assert seen == FIELDS


# --- what the gate accepts ------------------------------------------------


def test_a_granted_receipt_passes_its_own_gate():
    check_design_release_approval_gate(_granted(), FIELDS)


def test_a_missing_approval_is_refused():
    with pytest.raises(DesignReleaseApprovalError, match="no approval was provided"):
        check_design_release_approval_gate(None, FIELDS)


def test_a_receipt_for_a_different_design_is_refused():
    """The receipt is bound to the exact design it approved."""
    other = dict(FIELDS, design_id=8)
    with pytest.raises(DesignReleaseApprovalError, match="fingerprint"):
        check_design_release_approval_gate(_granted(), other)


def test_a_receipt_for_an_earlier_revision_is_refused():
    """Approving revision 2 must not release revision 3."""
    with pytest.raises(DesignReleaseApprovalError, match="fingerprint"):
        check_design_release_approval_gate(_granted(), dict(FIELDS, revision=3))


def test_a_tampered_token_is_refused():
    forged = dataclasses.replace(_granted(), token="0" * 64)
    with pytest.raises(DesignReleaseApprovalError, match="signature"):
        check_design_release_approval_gate(forged, FIELDS)


def test_a_receipt_reassigned_to_another_approver_is_refused():
    """approved_by is inside the signature, so it cannot be edited after."""
    forged = dataclasses.replace(_granted(), approved_by="someone.else")
    with pytest.raises(DesignReleaseApprovalError, match="signature"):
        check_design_release_approval_gate(forged, FIELDS)


@pytest.mark.parametrize("bogus", [True, "APPROVED", 1, {"token": "x"}, object()])
def test_a_bare_truthy_value_is_not_an_approval(bogus):
    """A flippable boolean is exactly what this gate exists to reject."""
    with pytest.raises(DesignReleaseApprovalError, match="must be a"):
        check_design_release_approval_gate(bogus, FIELDS)


def test_a_receipt_survives_a_round_trip_through_its_dict_form():
    """Receipts cross the agent/MCP JSON tool boundary as plain dicts."""
    original = _granted()
    rebuilt = DesignReleaseApprovalReceipt(**original.to_dict())
    check_design_release_approval_gate(rebuilt, FIELDS)


# --- the cross-gate isolation property ------------------------------------


def test_a_design_loop_receipt_cannot_release_a_design():
    """The property orchestration/approval.py's docstring demands: one gate's
    approval must never satisfy another's. A human approving a loop step has
    not approved a manufacturing release."""
    from orchestration.approval import request_loop_step_approval

    loop_receipt = request_loop_step_approval(
        FIELDS, approved_by="a.engineer", approval_callback=lambda _: True
    )
    with pytest.raises(DesignReleaseApprovalError, match="must be a"):
        check_design_release_approval_gate(loop_receipt, FIELDS)


def test_a_release_receipt_cannot_advance_a_design_loop_step():
    """And the same in the other direction."""
    from orchestration.approval import OrchestrationError, check_loop_step_approval_gate

    with pytest.raises(OrchestrationError):
        check_loop_step_approval_gate(_granted(), FIELDS)


def test_the_two_receipt_types_do_not_share_a_signing_key():
    """Even with identical fields and approver, the tokens differ -- so a
    receipt cannot be retyped into the other gate's class and pass."""
    from orchestration.approval import request_loop_step_approval

    release = _granted()
    loop = request_loop_step_approval(
        FIELDS, approved_by="a.engineer", approval_callback=lambda _: True
    )
    assert release.decision_fingerprint == loop.decision_fingerprint
    retyped = DesignReleaseApprovalReceipt(
        token=loop.token,
        decision_fingerprint=loop.decision_fingerprint,
        approved_by=loop.approved_by,
        granted_at=loop.granted_at,
    )
    with pytest.raises(DesignReleaseApprovalError, match="signature"):
        check_design_release_approval_gate(retyped, FIELDS)


# --- the fingerprint helper -----------------------------------------------


def test_release_fingerprint_fields_pins_design_key_revision_and_target():
    fields = release_fingerprint_fields(
        design_id=7, design_key="ADX-1", revision=2, target=DesignStatus.RELEASED
    )
    assert fields == FIELDS


def test_fingerprint_fields_are_order_independent():
    """A dict built in a different order is the same approval."""
    receipt = _granted()
    check_design_release_approval_gate(receipt, dict(reversed(list(FIELDS.items()))))
