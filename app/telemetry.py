"""
app/telemetry.py — Langfuse v4 (OpenTelemetry-native) observability wrapper.

Traces each agent run as a root "agent" observation, with LangGraph node,
tool, and LLM calls nested beneath it via the Langfuse LangChain callback.
The trace ID is derived deterministically from the run_id, so the initial
/process call and the later approve/reject resume land in the same trace.

If Langfuse credentials are not provided (e.g., local testing), it gracefully
acts as a pass-through without degrading performance or failing requests.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager, ExitStack
from typing import Any, AsyncGenerator

from app.config import get_settings

logger = logging.getLogger("inboxpilot.telemetry")

_langfuse_client = None


def get_langfuse():
    """Return Langfuse client if configured, else None."""
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client

    settings = get_settings()
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        try:
            from langfuse import Langfuse
            _langfuse_client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
            logger.info("Langfuse observability client initialized.")
        except Exception as exc:
            logger.warning("Failed to initialize Langfuse (%s). Tracing will be disabled.", exc)
            _langfuse_client = None
    return _langfuse_client


def shutdown_telemetry() -> None:
    """Flush buffered spans before the process exits."""
    if _langfuse_client is not None:
        try:
            _langfuse_client.shutdown()
        except Exception as exc:
            logger.debug("Langfuse shutdown error: %s", exc)


@asynccontextmanager
async def trace_agent_run(
    run_id: str,
    input_type: str,
    stage: str = "process",
) -> AsyncGenerator[dict[str, Any], None]:
    """Trace one agent invocation (process / approve / reject) for a run.

    Yields a metadata dict. ``metadata["callbacks"]`` holds LangChain callback
    handlers to pass in the LangGraph config so nodes and LLM calls are traced.
    """
    start_time = time.perf_counter()
    metadata: dict[str, Any] = {"run_id": run_id, "input_type": input_type, "stage": stage, "callbacks": []}
    client = get_langfuse()

    span = None
    with ExitStack() as stack:
        if client:
            try:
                from langfuse import Langfuse, propagate_attributes
                from langfuse.langchain import CallbackHandler

                trace_id = Langfuse.create_trace_id(seed=run_id)
                stack.enter_context(propagate_attributes(
                    session_id=run_id,
                    trace_name="inboxpilot_agent_run",
                    tags=["agentic_ai", "email_ops", input_type],
                ))
                span = stack.enter_context(client.start_as_current_observation(
                    trace_context={"trace_id": trace_id},
                    name=f"inboxpilot_{stage}",
                    as_type="agent",
                    metadata={"run_id": run_id, "input_type": input_type},
                ))
                metadata["callbacks"] = [CallbackHandler()]
            except Exception as exc:
                logger.debug("Langfuse trace initiation error: %s", exc)

        try:
            yield metadata
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            metadata["duration_ms"] = elapsed_ms
            if span:
                try:
                    span.update(
                        output={k: v for k, v in metadata.items() if k != "callbacks"},
                        metadata={"latency_ms": elapsed_ms},
                    )
                except Exception:
                    pass
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            metadata["status"] = "failed"
            metadata["error"] = str(exc)
            if span:
                try:
                    span.update(
                        level="ERROR",
                        status_message=str(exc),
                        output={"error": str(exc), "latency_ms": elapsed_ms},
                    )
                except Exception:
                    pass
            raise
