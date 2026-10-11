"""
tools/extract_fields.py — LLM-driven structured entity extraction.

Takes raw document text and extracts typed Pydantic fields (ExtractedEmail).
Includes exponential backoff retries.
"""

from __future__ import annotations

import asyncio
import logging
from app.llm import LLMProvider
from app.models import ExtractedEmail

logger = logging.getLogger("inboxpilot.tools.extract")


async def extract_fields(
    text: str,
    provider: LLMProvider | None = None,
    max_retries: int = 2,
) -> ExtractedEmail:
    """Extract structured enterprise fields with retry logic.

    Args:
        text: Raw document text.
        provider: LLMProvider instance (defaults to shared provider).
        max_retries: Number of attempts on failure.

    Returns:
        Validated ExtractedEmail model.
    """
    if not text or not text.strip():
        raise ValueError("Cannot extract fields from empty text")

    llm = provider or LLMProvider()
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            result = await llm.extract_structured(text)
            return result
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "Extraction attempt %d/%d failed: %s",
                attempt + 1,
                max_retries + 1,
                exc,
            )
            if attempt < max_retries:
                await asyncio.sleep(0.5 * (2 ** attempt))

    raise RuntimeError(f"Field extraction failed after {max_retries + 1} attempts: {last_exc}")
