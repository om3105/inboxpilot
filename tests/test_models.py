"""
tests/test_models.py — Unit tests for Phase 1 Pydantic domain models & AgentState.
"""

import pytest
from pydantic import ValidationError

from app.models import (
    ActionType,
    AgentState,
    DocumentType,
    DraftReply,
    ExtractedEmail,
    LookupResult,
    ProposedAction,
    RunStatus,
)


def test_extracted_email_defaults():
    email = ExtractedEmail()
    assert email.document_type == DocumentType.UNKNOWN
    assert email.sender == ""
    assert email.amount is None
    assert email.employee_id is None


def test_extracted_email_leave_request():
    email = ExtractedEmail(
        sender="aarav.sharma@acme.dev",
        subject="Leave Application",
        body="I need casual leave",
        document_type=DocumentType.LEAVE_REQUEST,
        employee_id="EMP001",
        employee_name="Aarav Sharma",
        leave_start="2024-10-24",
        leave_end="2024-10-25",
        leave_type="casual",
    )
    assert email.document_type == DocumentType.LEAVE_REQUEST
    assert email.employee_id == "EMP001"
    dump = email.model_dump()
    assert dump["employee_name"] == "Aarav Sharma"
    assert dump["document_type"] == "leave_request"


def test_lookup_result_structure():
    result = LookupResult(
        found=True,
        collection="employees",
        record={"employee_id": "EMP001", "name": "Aarav Sharma"},
        message="Employee record located",
    )
    assert result.found is True
    assert result.record["employee_id"] == "EMP001"


def test_draft_reply():
    draft = DraftReply(
        to="aarav.sharma@acme.dev",
        subject="Re: Leave Application",
        body="Your casual leave has been noted and submitted for approval.",
        tone="professional",
    )
    assert draft.to == "aarav.sharma@acme.dev"
    assert draft.tone == "professional"


def test_proposed_action_validation():
    action = ProposedAction(
        action_type=ActionType.DEDUCT_LEAVE,
        collection="employees",
        filter_query={"employee_id": "EMP001"},
        update_payload={"$inc": {"leave_balance.casual": -2}},
        reason="Deduct 2 days of casual leave for approved dates.",
    )
    assert action.action_type == ActionType.DEDUCT_LEAVE
    assert action.update_payload["$inc"]["leave_balance.casual"] == -2


def test_proposed_action_requires_fields():
    with pytest.raises(ValidationError):
        # Missing required collection and update_payload
        ProposedAction(action_type=ActionType.DEDUCT_LEAVE)  # type: ignore[call-arg]


def test_agent_state_keys():
    state: AgentState = {
        "run_id": "run-123",
        "raw_input": "Sample text",
        "input_source": "email",
        "document_type": DocumentType.LEAVE_REQUEST.value,
        "extracted": {"employee_id": "EMP001"},
        "status": RunStatus.AWAITING_APPROVAL.value,
        "tool_trace": ["read_email", "extract_fields", "lookup_record"],
    }
    assert state["run_id"] == "run-123"
    assert len(state["tool_trace"]) == 3
