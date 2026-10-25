"""
tests/test_tools.py — Unit tests for all 6 Phase 2 tools.
"""

import pytest
import os
from app.models import ActionType, DocumentType, ProposedAction
from tools.read_email import read_email
from tools.read_pdf import read_pdf
from tools.extract_fields import extract_fields
from tools.lookup_record import lookup_record
from tools.draft_reply import draft_reply
from tools.apply_update import apply_update


def test_read_email_sample():
    sample_path = "samples/leave_request_01.eml"
    assert os.path.exists(sample_path)
    parsed = read_email(sample_path)
    assert "aarav.sharma@acme.dev" in parsed["sender"]
    assert "Casual Leave Application" in parsed["subject"]
    assert "EMP001" in parsed["body"]


def test_read_email_plain_text():
    raw = "From: test@example.com\nSubject: Test Subject\n\nHello, this is a plain message."
    parsed = read_email(raw)
    assert parsed["sender"] == "test@example.com"
    assert parsed["subject"] == "Test Subject"
    assert "plain message" in parsed["body"]


def test_read_email_empty_raises():
    with pytest.raises(ValueError):
        read_email("   ")


def test_read_pdf_nonexistent():
    with pytest.raises(FileNotFoundError):
        read_pdf("nonexistent_file.pdf")


@pytest.mark.asyncio
async def test_extract_fields():
    text = (
        "From: aarav.sharma@acme.dev\n"
        "Subject: Casual leave request\n\n"
        "I need 2 days casual leave from 2024-10-24 to 2024-10-25. My ID is EMP001."
    )
    extracted = await extract_fields(text)
    assert extracted.document_type == DocumentType.LEAVE_REQUEST
    assert extracted.employee_id == "EMP001"
    assert extracted.leave_type == "casual"


@pytest.mark.asyncio
async def test_lookup_record_employee_found():
    result = await lookup_record("employees", {"employee_id": "EMP001"})
    assert result.found is True
    assert result.record.get("name") == "Aarav Sharma"
    assert result.record.get("department") == "Engineering"


@pytest.mark.asyncio
async def test_lookup_record_invoice_found():
    result = await lookup_record("invoices", {"invoice_number": "INV-2024-001"})
    assert result.found is True
    assert result.record.get("amount") == 4500.00


@pytest.mark.asyncio
async def test_lookup_record_not_found():
    result = await lookup_record("employees", {"employee_id": "EMP999"})
    assert result.found is False
    assert result.record == {}


@pytest.mark.asyncio
async def test_draft_reply():
    context = {
        "document_type": "leave_request",
        "extracted": {
            "sender": "aarav.sharma@acme.dev",
            "employee_name": "Aarav Sharma",
            "leave_type": "casual",
        },
    }
    draft = await draft_reply(context)
    assert draft.to == "aarav.sharma@acme.dev"
    assert "Leave Request" in draft.subject
    assert "Aarav Sharma" in draft.body


@pytest.mark.asyncio
async def test_apply_update_leave():
    action = ProposedAction(
        action_type=ActionType.DEDUCT_LEAVE,
        collection="employees",
        filter_query={"employee_id": "EMP001"},
        update_payload={"$inc": {"leave_balance.casual": -2}},
        reason="Deduct 2 casual leave days",
    )
    res = await apply_update(action)
    assert res["success"] is True
    assert res["modified_count"] == 1


@pytest.mark.asyncio
async def test_apply_update_visible_to_subsequent_lookup():
    action = ProposedAction(
        action_type=ActionType.DEDUCT_LEAVE,
        collection="employees",
        filter_query={"employee_id": "EMP001"},
        update_payload={"$inc": {"leave_balance.casual": -3}},
        reason="Deduct 3 casual leave days",
    )
    await apply_update(action)
    result = await lookup_record("employees", {"employee_id": "EMP001"})
    assert result.record["leave_balance"]["casual"] == 7


@pytest.mark.asyncio
async def test_apply_update_no_match_reports_failure():
    action = ProposedAction(
        action_type=ActionType.CLOSE_TICKET,
        collection="tickets",
        filter_query={"ticket_id": "TKT-999"},
        update_payload={"$set": {"status": "resolved"}},
        reason="Close nonexistent ticket",
    )
    res = await apply_update(action)
    assert res["success"] is False
    assert res["modified_count"] == 0
