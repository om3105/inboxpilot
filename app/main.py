"""
app/main.py — FastAPI Application for InboxPilot.

Endpoints:
  - GET  /health           : Liveness probe for Render
  - GET  /samples          : List preloaded sample emails and documents
  - POST /process          : Initiate agent run on inbound text/email/PDF
  - GET  /runs/{run_id}    : Inspect run state & human approval prompt
  - POST /runs/{run_id}/approve : Approve proposed database action (resumes thread)
  - POST /runs/{run_id}/reject  : Reject proposed action (resumes thread)
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Literal
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from langgraph.types import Command
from app.config import get_settings
from app.database import close_database
from app.models import RunStatus
from app.telemetry import trace_agent_run
from agent.checkpointer import get_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inboxpilot.api")

# Rate Limiter setup (5 requests/minute per IP)
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager: startup and cleanup."""
    logger.info("InboxPilot API starting up...")
    yield
    logger.info("InboxPilot API shutting down, closing database...")
    await close_database()


app = FastAPI(
    title="InboxPilot: Email & Document Ops Agent",
    description="Autonomous human-in-the-loop agent processing enterprise emails & documents.",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration for frontend live demos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Security Dependency ───────────────────────────────────────────────────────


def verify_demo_token(x_demo_token: str | None = Header(default=None, alias="X-Demo-Token")):
    """Check that mutating requests include the authorized demo token."""
    settings = get_settings()
    # If no token configured or matches settings, allow
    if not settings.demo_token:
        return True
    if x_demo_token != settings.demo_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Demo-Token header. Pass demo token configured on Render.",
        )
    return True


# ── Request / Response Schemas ────────────────────────────────────────────────


class ProcessRequest(BaseModel):
    raw_input: str = Field(..., description="Email body, raw .eml, or document text")
    input_source: Literal["email", "pdf", "text"] = Field(
        default="email", description="Input document format"
    )


class RejectRequest(BaseModel):
    reason: str = Field(default="", description="Reason for rejecting the proposed action")


class ProcessResponse(BaseModel):
    run_id: str
    status: str
    document_type: str | None = None
    extracted: dict[str, Any] | None = None
    proposed_action: dict[str, Any] | None = None
    draft_reply: dict[str, Any] | None = None
    tool_trace: list[str] = []
    requires_approval: bool = False
    message: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/health", tags=["System"])
async def health_check():
    """Healthcheck endpoint for Render / monitoring services."""
    return {
        "status": "healthy",
        "service": "inboxpilot",
        "version": "1.0.0",
    }


@app.get("/samples", tags=["Samples"])
async def list_samples():
    """Return preloaded sample documents for easy live demo testing."""
    samples_dir = "samples"
    results = []
    if os.path.exists(samples_dir):
        for fname in sorted(os.listdir(samples_dir)):
            fpath = os.path.join(samples_dir, fname)
            if os.path.isfile(fpath) and not fname.startswith("."):
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    results.append({
                        "filename": fname,
                        "type": "email" if fname.endswith(".eml") else "text",
                        "content": content,
                    })
                except Exception as exc:
                    logger.debug("Failed reading sample %s: %s", fname, exc)
    return {"samples": results}


@app.post(
    "/process",
    response_model=ProcessResponse,
    dependencies=[Depends(verify_demo_token)],
    tags=["Agent"],
)
@limiter.limit("15/minute")
async def process_document(request: Request, payload: ProcessRequest):
    """Initiate an agent run on an inbound email or document."""
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    agent = get_agent()
    config = {"configurable": {"thread_id": run_id}}

    initial_state = {
        "run_id": run_id,
        "raw_input": payload.raw_input,
        "input_source": payload.input_source,
        "tool_trace": [],
        "status": RunStatus.PROCESSING.value,
    }

    async with trace_agent_run(run_id=run_id, input_type=payload.input_source) as trace_meta:
        # Run agent until completion or interruption
        await agent.ainvoke(initial_state, config=config)
        state = await agent.aget_state(config)

    values = state.values
    is_paused = state.next == ("human_approval_gate",)

    current_status = RunStatus.AWAITING_APPROVAL.value if is_paused else values.get("status", RunStatus.COMPLETED.value)

    return ProcessResponse(
        run_id=run_id,
        status=current_status,
        document_type=values.get("document_type"),
        extracted=values.get("extracted"),
        proposed_action=values.get("proposed_action"),
        draft_reply=values.get("draft_reply"),
        tool_trace=values.get("tool_trace", []),
        requires_approval=is_paused,
        message=(
            "Action requires human approval before execution."
            if is_paused
            else "Processing complete."
        ),
    )


@app.get("/runs/{run_id}", response_model=ProcessResponse, tags=["Agent"])
async def get_run_status(run_id: str):
    """Retrieve current state and human-in-the-loop status for a run."""
    agent = get_agent()
    config = {"configurable": {"thread_id": run_id}}
    state = await agent.aget_state(config)

    if not state or not state.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run with ID '{run_id}' not found.",
        )

    values = state.values
    is_paused = state.next == ("human_approval_gate",)
    current_status = RunStatus.AWAITING_APPROVAL.value if is_paused else values.get("status", RunStatus.COMPLETED.value)

    return ProcessResponse(
        run_id=run_id,
        status=current_status,
        document_type=values.get("document_type"),
        extracted=values.get("extracted"),
        proposed_action=values.get("proposed_action"),
        draft_reply=values.get("draft_reply"),
        tool_trace=values.get("tool_trace", []),
        requires_approval=is_paused,
        message="Awaiting approval" if is_paused else f"Run status: {current_status}",
    )


@app.post(
    "/runs/{run_id}/approve",
    response_model=ProcessResponse,
    dependencies=[Depends(verify_demo_token)],
    tags=["Agent"],
)
@limiter.limit("20/minute")
async def approve_run(request: Request, run_id: str):
    """Authorize and execute the proposed database mutation."""
    agent = get_agent()
    config = {"configurable": {"thread_id": run_id}}
    state = await agent.aget_state(config)

    if not state or not state.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found.",
        )

    if state.next != ("human_approval_gate",):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Run '{run_id}' is not currently awaiting approval (next={state.next}).",
        )

    # Resume the graph
    resume_cmd = Command(resume={"decision": "approve"})
    await agent.ainvoke(resume_cmd, config=config)

    updated_state = await agent.aget_state(config)
    values = updated_state.values

    return ProcessResponse(
        run_id=run_id,
        status=values.get("status", RunStatus.COMPLETED.value),
        document_type=values.get("document_type"),
        extracted=values.get("extracted"),
        proposed_action=values.get("proposed_action"),
        draft_reply=values.get("draft_reply"),
        tool_trace=values.get("tool_trace", []),
        requires_approval=False,
        message="Proposed action approved and successfully executed.",
    )


@app.post(
    "/runs/{run_id}/reject",
    response_model=ProcessResponse,
    dependencies=[Depends(verify_demo_token)],
    tags=["Agent"],
)
@limiter.limit("20/minute")
async def reject_run(request: Request, run_id: str, payload: RejectRequest | None = None):
    """Reject the proposed database mutation."""
    agent = get_agent()
    config = {"configurable": {"thread_id": run_id}}
    state = await agent.aget_state(config)

    if not state or not state.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found.",
        )

    if state.next != ("human_approval_gate",):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Run '{run_id}' is not currently awaiting approval.",
        )

    reason = payload.reason if payload else "Rejected by operator"
    resume_cmd = Command(resume={"decision": "reject", "reason": reason})
    await agent.ainvoke(resume_cmd, config=config)

    updated_state = await agent.aget_state(config)
    values = updated_state.values

    return ProcessResponse(
        run_id=run_id,
        status=RunStatus.REJECTED.value,
        document_type=values.get("document_type"),
        extracted=values.get("extracted"),
        proposed_action=values.get("proposed_action"),
        draft_reply=values.get("draft_reply"),
        tool_trace=values.get("tool_trace", []),
        requires_approval=False,
        message=f"Action rejected: {reason}",
    )
