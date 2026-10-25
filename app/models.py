"""
Pydantic models shared across the entire application.

Design decisions:
─────────────────
1. **Separate models per concern** — ExtractedEmail, LookupResult, DraftReply,
   ProposedAction each own a clear slice of the pipeline.  This makes it easy
   to test, serialise to JSON, and explain in an interview.

2. **AgentState as a TypedDict** — LangGraph requires state to be a TypedDict
   (not a Pydantic model) because it uses key-level reducers. We define it
   here alongside the Pydantic models so the full schema lives in one file.

3. **Enums for fixed categories** — DocumentType and ActionType prevent
   stringly-typed bugs and let the LLM's structured output be validated
   automatically.

4. **Optional fields with defaults** — Real-world emails are messy; fields may
   be absent.  We never crash on a missing optional field.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────


class DocumentType(str, enum.Enum):
    """Categories the agent can classify an inbound document into."""
    LEAVE_REQUEST = "leave_request"
    INVOICE = "invoice"
    SUPPORT_TICKET = "support_ticket"
    UNKNOWN = "unknown"


class ActionType(str, enum.Enum):
    """Types of database mutations the agent may propose."""
    DEDUCT_LEAVE = "deduct_leave"
    MARK_INVOICE_PAID = "mark_invoice_paid"
    CLOSE_TICKET = "close_ticket"
    ESCALATE = "escalate"
    NONE = "none"  # no action needed


class RunStatus(str, enum.Enum):
    """Lifecycle states for a single agent run."""
    PROCESSING = "processing"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


# ── Pipeline stage models ─────────────────────────────────────────────────────


class ExtractedEmail(BaseModel):
    """Structured fields pulled from an inbound email or PDF by the LLM.

    The LLM returns JSON conforming to this schema.  Pydantic validates it,
    so a malformed LLM response surfaces as a clear ValidationError rather
    than a silent downstream bug.
    """
    sender: str = Field(default="", description="Email address or name of the sender")
    subject: str = Field(default="", description="Subject line")
    body: str = Field(default="", description="Full body text")
    document_type: DocumentType = Field(
        default=DocumentType.UNKNOWN,
        description="Classified category of the document",
    )

    # Leave-request specific
    employee_name: str | None = Field(default=None, description="Employee requesting leave")
    employee_id: str | None = Field(default=None, description="Employee ID if mentioned")
    leave_start: str | None = Field(default=None, description="Leave start date (ISO)")
    leave_end: str | None = Field(default=None, description="Leave end date (ISO)")
    leave_type: str | None = Field(default=None, description="e.g. casual, sick, earned")

    # Invoice specific
    invoice_number: str | None = Field(default=None, description="Invoice reference number")
    amount: float | None = Field(default=None, description="Invoice amount")
    vendor_name: str | None = Field(default=None, description="Vendor / supplier name")
    due_date: str | None = Field(default=None, description="Payment due date (ISO)")

    # Support-ticket specific
    ticket_id: str | None = Field(default=None, description="Support ticket ID")
    priority: str | None = Field(default=None, description="Ticket priority level")
    issue_summary: str | None = Field(default=None, description="Brief issue description")


class LookupResult(BaseModel):
    """Result of a database lookup — wraps whatever MongoDB returned."""
    found: bool = Field(description="Whether a matching record was found")
    collection: str = Field(default="", description="MongoDB collection queried")
    record: dict[str, Any] = Field(
        default_factory=dict,
        description="The matched document (empty dict if not found)",
    )
    message: str = Field(default="", description="Human-readable status")


class DraftReply(BaseModel):
    """An LLM-generated reply email or response message."""
    to: str = Field(default="", description="Recipient address")
    subject: str = Field(default="", description="Reply subject line")
    body: str = Field(default="", description="Reply body text")
    tone: str = Field(default="professional", description="Intended tone")


class ProposedAction(BaseModel):
    """A database write the agent wants to execute.

    This is the object presented to the human reviewer.  It contains enough
    context for them to understand *what* will change and *why*.
    """
    action_type: ActionType = Field(description="Category of the proposed change")
    collection: str = Field(description="Target MongoDB collection")
    filter_query: dict[str, Any] = Field(
        description="MongoDB filter to locate the document"
    )
    update_payload: dict[str, Any] = Field(
        description="The $set / $inc update to apply"
    )
    reason: str = Field(default="", description="Why the agent proposes this action")


# ── Agent state (LangGraph TypedDict) ─────────────────────────────────────────
# LangGraph needs a TypedDict, not a Pydantic model, because it merges state
# updates at the key level using reducers.  We keep it simple: each key maps
# to one of the Pydantic models above (serialised as a dict) or a primitive.

from typing import TypedDict


class AgentState(TypedDict, total=False):
    """Full state flowing through the LangGraph agent graph.

    Keys are added progressively — early nodes only populate a few keys,
    later nodes read from earlier ones and add their own.
    ``total=False`` means every key is optional, matching the progressive-
    enrichment pattern.
    """
    # Input
    run_id: str                       # unique run identifier
    raw_input: str                    # original email/PDF text
    input_source: str                 # "email", "pdf", or "text"

    # Classification & extraction
    document_type: str                # DocumentType value
    extracted: dict[str, Any]         # ExtractedEmail.model_dump()
    security_flags: list[str]         # prompt-injection patterns found in raw input

    # Lookup
    lookup_result: dict[str, Any]     # LookupResult.model_dump()

    # Decision & drafting
    proposed_action: dict[str, Any]   # ProposedAction.model_dump()
    draft_reply: dict[str, Any]       # DraftReply.model_dump()

    # Approval flow
    status: str                       # RunStatus value
    approval_decision: str | None     # "approve" | "reject" | None
    rejection_reason: str | None
    update_result: dict[str, Any]     # apply_update() execution summary

    # Metadata
    error: str | None                 # error message if the run failed
    created_at: str                   # ISO timestamp
    tool_trace: list[str]             # ordered list of tools called
