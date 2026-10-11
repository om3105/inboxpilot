"""
tools/mcp_client.py — Python client adapter for the InboxPilot MCP server.
"""

from __future__ import annotations

import json
from typing import Any
from app.models import LookupResult
from tools.mcp_server import handle_lookup


async def mcp_lookup_record(collection: str, key: str, value: str) -> LookupResult:
    """Invoke lookup over the Model Context Protocol (MCP) tool adapter."""
    raw_res = handle_lookup(collection=collection, key=key, value=value)
    return LookupResult(
        found=raw_res.get("found", False),
        collection=collection,
        record=raw_res.get("record", {}),
        message=f"MCP record lookup result for {key}={value}",
    )
