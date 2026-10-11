"""
tools/draft_reply.py — Generates contextual responses to incoming emails/tickets.

Calls LLMProvider to generate a polite, operational reply based on the state.
"""

from __future__ import annotations

import logging
from typing import Any
from app.llm import LLMProvider
from app.models import DraftReply

logger = logging.getLogger("inboxpilot.tools.draft")


async def draft_reply(
    context: dict[str, Any],
    provider: LLMProvider | None = None,
) -> DraftReply:
    """Generate a typed draft reply email.

    Args:
        context: Operational state dict containing extracted info, lookup result, and proposed action.
        provider: Optional LLMProvider.

    Returns:
        Validated DraftReply model.
    """
    llm = provider or LLMProvider()
    try:
        return await llm.generate_draft(context)
    except Exception as exc:
        logger.error("Failed to generate draft reply: %s", exc)
        return llm._mock_draft(context)
