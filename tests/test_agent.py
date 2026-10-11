"""
tests/test_agent.py — Integration tests for LangGraph state machine & human-in-the-loop pauses.
"""

import pytest
import uuid
from langgraph.types import Command
from agent.graph import build_agent_graph, get_graph_mermaid_diagram
from app.models import DocumentType, RunStatus


@pytest.mark.asyncio
async def test_agent_leave_request_interruption_and_approval():
    """Verify that an actionable leave request pauses for approval and completes on resume."""
    agent = build_agent_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_input = {
        "run_id": thread_id,
        "raw_input": (
            "From: aarav.sharma@acme.dev\n"
            "Subject: Casual leave request\n\n"
            "Hi HR, I need 2 days casual leave from 2024-10-24 to 2024-10-25. My ID is EMP001."
        ),
        "input_source": "email",
        "tool_trace": [],
    }

    # 1. Run until interruption
    result = await agent.ainvoke(initial_input, config=config)

    # State snapshot should reflect interruption at approval gate
    state = await agent.aget_state(config)
    assert state.next == ("human_approval_gate",)
    assert state.values["document_type"] == DocumentType.LEAVE_REQUEST.value
    assert state.values["proposed_action"]["action_type"] == "deduct_leave"
    assert "draft_reply" in state.values

    # 2. Resume with human approval
    resume_cmd = Command(resume={"decision": "approve"})
    resumed_result = await agent.ainvoke(resume_cmd, config=config)

    final_state = await agent.aget_state(config)
    assert final_state.next == ()
    assert final_state.values["status"] == RunStatus.COMPLETED.value
    assert "apply_update" in final_state.values["tool_trace"]


@pytest.mark.asyncio
async def test_agent_leave_request_rejection():
    """Verify that rejecting a proposed mutation routes to handle_rejection."""
    agent = build_agent_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_input = {
        "run_id": thread_id,
        "raw_input": (
            "From: priya.patel@acme.dev\n"
            "Subject: Casual leave\n\n"
            "Applying for 2 days leave. EMP002."
        ),
        "input_source": "email",
        "tool_trace": [],
    }

    await agent.ainvoke(initial_input, config=config)
    
    # Reject
    resume_cmd = Command(resume={"decision": "reject", "reason": "Team sprint commitments"})
    await agent.ainvoke(resume_cmd, config=config)

    final_state = await agent.aget_state(config)
    assert final_state.values["status"] == RunStatus.REJECTED.value
    assert final_state.values["approval_decision"] == "reject"
    assert "apply_update" not in final_state.values["tool_trace"]


@pytest.mark.asyncio
async def test_agent_unknown_employee_routes_to_human_review():
    """Unknown employee ID gracefully diverts to needs_human_review without crashing."""
    agent = build_agent_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_input = {
        "run_id": thread_id,
        "raw_input": (
            "From: unknown.person@other.com\n"
            "Subject: Leave application\n\n"
            "I want 2 days off. My employee ID is EMP999."
        ),
        "input_source": "email",
        "tool_trace": [],
    }

    await agent.ainvoke(initial_input, config=config)

    state = await agent.aget_state(config)
    assert state.next == ()
    assert state.values["status"] == RunStatus.NEEDS_HUMAN_REVIEW.value


def test_mermaid_diagram():
    diagram = get_graph_mermaid_diagram()
    assert "graph TD" in diagram
    assert "human_approval_gate" in diagram
    assert "classify_and_extract" in diagram
