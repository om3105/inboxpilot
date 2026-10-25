"""
agent/graph.py — Core LangGraph state machine workflow for InboxPilot.

Pipeline Topology:
  [START]
     │
     ▼
  classify_and_extract
     │
     ▼
  lookup_records
     │
     ▼
  decide_action  ───────(Discrepancy / Unknown)───────► needs_human_review ──► [END]
     │                                                         ▲
     ▼                                                         │
  draft_response                                               │
     │                                                         │
     ▼                                                         │
  human_approval_gate (interrupt() for human sign-off) ────────┘
     │
     ├── (Approved) ──► execute_update ──► [END]
     └── (Rejected) ──► handle_rejection ──► [END]
"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal
from datetime import date, datetime

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver

from app.models import (
    ActionType,
    AgentState,
    DocumentType,
    ExtractedEmail,
    LookupResult,
    ProposedAction,
    RunStatus,
)
from tools.read_email import read_email
from tools.read_pdf import read_pdf
from tools.extract_fields import extract_fields
from tools.lookup_record import lookup_record
from tools.draft_reply import draft_reply
from tools.apply_update import apply_update
from tools.send_reply import send_reply

logger = logging.getLogger("inboxpilot.agent")


# ── Helpers ───────────────────────────────────────────────────────────────────


def format_inr(amount: float | int | None) -> str:
    """Format a rupee amount with Indian digit grouping, e.g. 1200000 -> ₹12,00,000."""
    if amount is None:
        return "₹—"
    whole, frac = f"{float(amount):.2f}".split(".")
    head, tail = whole[:-3], whole[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    grouped = ",".join(groups + [tail]) if groups else tail
    return f"₹{grouped}" + (f".{frac}" if frac != "00" else "")


def compute_leave_days(start: str | None, end: str | None) -> int | None:
    """Return inclusive calendar days between ISO dates, 1 if dates are missing, None if invalid."""
    if not start:
        return 1
    try:
        start_d = date.fromisoformat(start)
        end_d = date.fromisoformat(end) if end else start_d
    except ValueError:
        return 1
    if end_d < start_d:
        return None
    return (end_d - start_d).days + 1


_INJECTION_PATTERNS = {
    "instruction_override": re.compile(r"\b(ignore|disregard|forget)\b.{0,30}\b(instructions|rules|prompts?)\b", re.I),
    "role_hijack": re.compile(r"\b(you are now|forget (that )?you are|act as|pretend to be)\b", re.I),
    "system_override": re.compile(r"\bsystem (override|prompt)\b", re.I),
    "sql_injection": re.compile(r"\b(drop\s+table|delete\s+from|update\s+\w+\s+set)\b|\bwhere\s+1\s*=\s*1\b", re.I),
    "secret_exfiltration": re.compile(r"\b(secret|api)[ _-]?keys?\b|\bbypass\s+auth", re.I),
}


def detect_injection(text: str) -> list[str]:
    """Return the names of prompt-injection patterns found in raw input."""
    return [name for name, pattern in _INJECTION_PATTERNS.items() if pattern.search(text or "")]


# ── Graph Node Implementations ────────────────────────────────────────────────


async def classify_and_extract_node(state: AgentState) -> dict[str, Any]:
    """Parse raw input (email/PDF/text) and extract typed structured entities."""
    raw = state.get("raw_input", "")
    source = state.get("input_source", "text")
    trace = list(state.get("tool_trace", []))

    text_to_extract = raw
    if source == "email":
        try:
            parsed_mail = read_email(raw)
            text_to_extract = f"From: {parsed_mail['sender']}\nSubject: {parsed_mail['subject']}\n\n{parsed_mail['body']}"
            trace.append("read_email")
        except Exception as exc:
            logger.warning("read_email parser encountered error (%s); falling back to raw.", exc)

    elif source == "pdf":
        try:
            text_to_extract = read_pdf(raw)
            trace.append("read_pdf")
        except Exception as exc:
            logger.warning("read_pdf parser failed: %s", exc)
            return {
                "status": RunStatus.NEEDS_HUMAN_REVIEW.value,
                "error": f"Failed to extract text from PDF: {exc}",
                "tool_trace": trace,
            }

    try:
        extracted: ExtractedEmail = await extract_fields(text_to_extract)
        trace.append("extract_fields")
        return {
            "document_type": extracted.document_type.value,
            "extracted": extracted.model_dump(),
            "security_flags": detect_injection(raw),
            "status": RunStatus.PROCESSING.value,
            "tool_trace": trace,
        }
    except Exception as exc:
        logger.error("Structured field extraction failed: %s", exc)
        return {
            "document_type": DocumentType.UNKNOWN.value,
            "status": RunStatus.NEEDS_HUMAN_REVIEW.value,
            "error": f"Extraction failed: {exc}",
            "tool_trace": trace,
        }


async def lookup_records_node(state: AgentState) -> dict[str, Any]:
    """Query MongoDB Atlas for matching business records based on extracted fields."""
    doc_type = state.get("document_type", "unknown")
    extracted = state.get("extracted", {})
    trace = list(state.get("tool_trace", []))

    if state.get("status") == RunStatus.NEEDS_HUMAN_REVIEW.value:
        return {}

    lookup_res: LookupResult = LookupResult(found=False, collection="", record={}, message="")

    if doc_type == DocumentType.LEAVE_REQUEST.value:
        emp_id = extracted.get("employee_id")
        emp_name = extracted.get("employee_name")
        sender = extracted.get("sender")

        if emp_id:
            lookup_res = await lookup_record("employees", {"employee_id": emp_id})
        elif sender and "@" in sender:
            lookup_res = await lookup_record("employees", {"email": sender})
        elif emp_name:
            lookup_res = await lookup_record("employees", {"name": emp_name})
        else:
            lookup_res = LookupResult(found=False, collection="employees", record={}, message="No employee identifier found in request")

    elif doc_type == DocumentType.INVOICE.value:
        inv_num = extracted.get("invoice_number")
        if inv_num:
            lookup_res = await lookup_record("invoices", {"invoice_number": inv_num})
        else:
            lookup_res = LookupResult(found=False, collection="invoices", record={}, message="No invoice number found in document")

    elif doc_type == DocumentType.SUPPORT_TICKET.value:
        tkt_id = extracted.get("ticket_id")
        if tkt_id:
            lookup_res = await lookup_record("tickets", {"ticket_id": tkt_id})
        else:
            lookup_res = LookupResult(found=False, collection="tickets", record={}, message="No ticket ID found in email")

    trace.append("lookup_record")
    return {
        "lookup_result": lookup_res.model_dump(),
        "tool_trace": trace,
    }


async def decide_action_node(state: AgentState) -> dict[str, Any]:
    """Formulate the proposed operational update or route to human review on discrepancy."""
    doc_type = state.get("document_type", "unknown")
    extracted = state.get("extracted", {})
    lookup_dict = state.get("lookup_result", {})
    record = lookup_dict.get("record", {})
    found = lookup_dict.get("found", False)

    # Inputs that look like prompt injection never get an automated write or reply
    flags = state.get("security_flags") or []
    if flags:
        return {
            "status": RunStatus.NEEDS_HUMAN_REVIEW.value,
            "error": f"Possible prompt injection detected: {', '.join(flags)}",
        }

    # Unclassifiable mail (spam, newsletters, vague requests) goes to a human, not an auto-reply
    if doc_type == DocumentType.UNKNOWN.value:
        return {
            "status": RunStatus.NEEDS_HUMAN_REVIEW.value,
            "error": "Could not classify document; no automated reply drafted",
        }

    # Discrepancy routing: if expected business record doesn't exist, flag for human review
    if not found and doc_type in [DocumentType.LEAVE_REQUEST.value, DocumentType.INVOICE.value, DocumentType.SUPPORT_TICKET.value]:
        return {
            "status": RunStatus.NEEDS_HUMAN_REVIEW.value,
            "error": f"Record not found: {lookup_dict.get('message', 'Unmatched record')}",
        }

    proposed: ProposedAction | None = None

    if doc_type == DocumentType.LEAVE_REQUEST.value and found:
        leave_type = extracted.get("leave_type") or "casual"
        emp_id = record.get("employee_id")
        days = compute_leave_days(extracted.get("leave_start"), extracted.get("leave_end"))
        if days is None:
            return {
                "status": RunStatus.NEEDS_HUMAN_REVIEW.value,
                "error": "Invalid leave date range: end date is before start date",
            }
        balance = record.get("leave_balance", {}).get(leave_type, 0)
        if balance < days:
            return {
                "status": RunStatus.NEEDS_HUMAN_REVIEW.value,
                "error": f"Insufficient {leave_type} leave balance: requested {days}, available {balance}",
            }
        
        proposed = ProposedAction(
            action_type=ActionType.DEDUCT_LEAVE,
            collection="employees",
            filter_query={"employee_id": emp_id},
            update_payload={"$inc": {f"leave_balance.{leave_type}": -days}},
            reason=f"Deduct {days} days of {leave_type} leave for employee {emp_id}",
        )

    elif doc_type == DocumentType.INVOICE.value and found:
        inv_num = record.get("invoice_number")
        if record.get("status") == "paid":
            # Already paid; no mutation required
            proposed = ProposedAction(
                action_type=ActionType.NONE,
                collection="invoices",
                filter_query={"invoice_number": inv_num},
                update_payload={},
                reason="Invoice is already marked as paid. No database write needed.",
            )
        else:
            proposed = ProposedAction(
                action_type=ActionType.MARK_INVOICE_PAID,
                collection="invoices",
                filter_query={"invoice_number": inv_num},
                update_payload={"$set": {"status": "paid", "paid_at": datetime.utcnow().isoformat()}},
                reason=f"Mark verified invoice {inv_num} ({format_inr(record.get('amount'))}) as paid",
            )

    elif doc_type == DocumentType.SUPPORT_TICKET.value and found:
        tkt_id = record.get("ticket_id")
        proposed = ProposedAction(
            action_type=ActionType.CLOSE_TICKET,
            collection="tickets",
            filter_query={"ticket_id": tkt_id},
            update_payload={"$set": {"status": "resolved", "resolved_at": datetime.utcnow().isoformat()}},
            reason=f"Resolve ticket {tkt_id} upon confirmation",
        )

    return {
        "proposed_action": proposed.model_dump() if proposed else {},
    }


async def draft_response_node(state: AgentState) -> dict[str, Any]:
    """Generate professional contextual draft reply."""
    trace = list(state.get("tool_trace", []))
    draft = await draft_reply(state)
    trace.append("draft_reply")
    return {
        "draft_reply": draft.model_dump(),
        "tool_trace": trace,
    }


async def human_approval_gate_node(state: AgentState) -> dict[str, Any]:
    """Human-in-the-loop interruption point before executing high-risk updates.

    Uses LangGraph's interrupt() to pause the execution and checkpoint the state.
    Resumes with the human's decision payload: {"decision": "approve" | "reject", "reason": "..."}
    """
    proposed = state.get("proposed_action", {})
    action_type = proposed.get("action_type")

    # If no mutation is needed or no action proposed, no human gate needed
    if not proposed or action_type in [ActionType.NONE.value, None]:
        return {
            "status": RunStatus.COMPLETED.value,
        }

    # Interruption point for human authorization
    user_response = interrupt({
        "message": "Human approval required before applying database mutation.",
        "run_id": state.get("run_id"),
        "proposed_action": proposed,
        "draft_reply": state.get("draft_reply"),
    })

    decision = "reject"
    reason = None
    if isinstance(user_response, dict):
        decision = user_response.get("decision", "reject")
        reason = user_response.get("reason")
    elif isinstance(user_response, str):
        decision = user_response

    return {
        "approval_decision": decision,
        "rejection_reason": reason,
        "status": RunStatus.APPROVED.value if decision == "approve" else RunStatus.REJECTED.value,
    }


async def execute_update_node(state: AgentState) -> dict[str, Any]:
    """Execute high-risk database mutation following human approval."""
    trace = list(state.get("tool_trace", []))
    proposed_data = state.get("proposed_action", {})
    
    if not proposed_data:
        return {"status": RunStatus.COMPLETED.value}

    action = ProposedAction.model_validate(proposed_data)
    result = await apply_update(action)
    trace.append("apply_update")

    if not result.get("success"):
        return {
            "status": RunStatus.FAILED.value,
            "error": result.get("error", "Database update did not modify any record"),
            "update_result": result,
            "tool_trace": trace,
        }

    update: dict[str, Any] = {
        "status": RunStatus.COMPLETED.value,
        "update_result": result,
        "tool_trace": trace,
    }

    # Runs that came from a real mailbox get their approved reply sent
    # (only if enabled, and never in public demo mode; see tools/send_reply.py).
    source = state.get("source_message")
    if source:
        reply = await send_reply(state.get("draft_reply") or {}, source)
        update["reply_result"] = reply
        if reply.get("sent"):
            trace.append("send_reply")

    return update


async def handle_rejection_node(state: AgentState) -> dict[str, Any]:
    """Finalize state after a human operator rejects the proposed action."""
    return {
        "status": RunStatus.REJECTED.value,
    }


async def needs_human_review_node(state: AgentState) -> dict[str, Any]:
    """Dead-letter node for runs with unparseable inputs or unresolvable discrepancies."""
    return {
        "status": RunStatus.NEEDS_HUMAN_REVIEW.value,
    }


# ── Conditional Routing Functions ─────────────────────────────────────────────


def route_after_decide(state: AgentState) -> Literal["needs_human_review", "draft_response"]:
    if state.get("status") == RunStatus.NEEDS_HUMAN_REVIEW.value:
        return "needs_human_review"
    return "draft_response"


def route_after_approval(state: AgentState) -> Literal["execute_update", "handle_rejection", "__end__"]:
    status = state.get("status")
    if status == RunStatus.APPROVED.value:
        return "execute_update"
    elif status == RunStatus.REJECTED.value:
        return "handle_rejection"
    return "__end__"


# ── Workflow Factory ──────────────────────────────────────────────────────────


def build_agent_graph(checkpointer=None):
    """Construct and compile the InboxPilot LangGraph workflow.

    Args:
        checkpointer: LangGraph BaseCheckpointSaver. If None, uses MemorySaver.
    """
    workflow = StateGraph(AgentState)

    # Register nodes
    workflow.add_node("classify_and_extract", classify_and_extract_node)
    workflow.add_node("lookup_records", lookup_records_node)
    workflow.add_node("decide_action", decide_action_node)
    workflow.add_node("draft_response", draft_response_node)
    workflow.add_node("human_approval_gate", human_approval_gate_node)
    workflow.add_node("execute_update", execute_update_node)
    workflow.add_node("handle_rejection", handle_rejection_node)
    workflow.add_node("needs_human_review", needs_human_review_node)

    # Wire edges
    workflow.add_edge(START, "classify_and_extract")
    workflow.add_edge("classify_and_extract", "lookup_records")
    workflow.add_edge("lookup_records", "decide_action")

    workflow.add_conditional_edges(
        "decide_action",
        route_after_decide,
        {
            "needs_human_review": "needs_human_review",
            "draft_response": "draft_response",
        },
    )

    workflow.add_edge("draft_response", "human_approval_gate")

    workflow.add_conditional_edges(
        "human_approval_gate",
        route_after_approval,
        {
            "execute_update": "execute_update",
            "handle_rejection": "handle_rejection",
            "__end__": END,
        },
    )

    workflow.add_edge("execute_update", END)
    workflow.add_edge("handle_rejection", END)
    workflow.add_edge("needs_human_review", END)

    saver = checkpointer if checkpointer is not None else MemorySaver()
    return workflow.compile(checkpointer=saver)


def get_graph_mermaid_diagram() -> str:
    """Return Mermaid diagram definition of the graph."""
    return """
graph TD
    __start__([START]) --> classify_and_extract[classify_and_extract]
    classify_and_extract --> lookup_records[lookup_records]
    lookup_records --> decide_action{decide_action}
    decide_action -->|Discrepancy / Error| needs_human_review[needs_human_review]
    decide_action -->|Valid Record| draft_response[draft_response]
    draft_response --> human_approval_gate{human_approval_gate: interrupt}
    human_approval_gate -->|Approved| execute_update[execute_update: apply_update]
    human_approval_gate -->|Rejected| handle_rejection[handle_rejection]
    human_approval_gate -->|No Action Needed| __end__([END])
    execute_update --> __end__
    handle_rejection --> __end__
    needs_human_review --> __end__
""".strip()
