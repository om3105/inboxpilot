"""
app/telemetry.py — Langfuse OpenTelemetry-native observability wrapper.

Traces model requests, tool calls, execution latency, and errors.
If Langfuse credentials are not provided (e.g., local testing), it gracefully
acts as a pass-through without degrading performance or failing requests.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
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


@asynccontextmanager
async def trace_agent_run(run_id: str, input_type: str) -> AsyncGenerator[dict[str, Any], None]:
    """Context manager tracing full agent run duration, latency, and status."""
    start_time = time.perf_counter()
    metadata: dict[str, Any] = {"run_id": run_id, "input_type": input_type, "status": "started"}
    client = get_langfuse()

    trace_context = None
    if client:
        try:
            trace_context = client.trace(
                name="inboxpilot_agent_run",
                id=run_id,
                metadata={"input_type": input_type},
                tags=["agentic_ai", "email_ops", input_type],
            )
        except Exception as exc:
            logger.debug("Langfuse trace initiation error: %s", exc)

    try:
        yield metadata
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        metadata["duration_ms"] = elapsed_ms
        if trace_context:
            try:
                trace_context.update(output=metadata, metadata={"latency_ms": elapsed_ms})
            except Exception:
                pass
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        metadata["status"] = "failed"
        metadata["error"] = str(exc)
        if trace_context:
            try:
                trace_context.update(status="ERROR", output={"error": str(exc), "latency_ms": elapsed_ms})
            except Exception:
                pass
        raise
