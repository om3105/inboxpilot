"""
tools/mcp_server.py — Model Context Protocol (MCP) server for InboxPilot.

Exposes enterprise record lookups as an MCP tool over the stdio transport
(newline-delimited JSON-RPC 2.0). Implements the lifecycle handshake
(initialize / notifications/initialized), tools/list, tools/call, and ping,
so any MCP-compliant client (e.g. Claude Desktop, Cursor, LangChain MCP
adapters) can call it. Lookups use the same backend as the native tool
(MongoDB Atlas with seed-data fallback).

Run:  python -m tools.mcp_server
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from tools.lookup_record import lookup_record

# stdout carries protocol messages only; all logging goes to stderr.
logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

SERVER_INFO = {"name": "inboxpilot-records", "version": "1.0.0"}
DEFAULT_PROTOCOL_VERSION = "2025-06-18"

TOOLS = [
    {
        "name": "lookup_record",
        "description": "Look up an enterprise record in employees, invoices, or tickets by a single field",
        "inputSchema": {
            "type": "object",
            "properties": {
                "collection": {
                    "type": "string",
                    "enum": ["employees", "invoices", "tickets"],
                    "description": "The enterprise database collection to query",
                },
                "key": {"type": "string", "description": "Field name to match (e.g. employee_id, invoice_number)"},
                "value": {"type": "string", "description": "Value to match"},
            },
            "required": ["collection", "key", "value"],
        },
    }
]


def _result(req_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


async def handle_request(req: dict[str, Any]) -> dict[str, Any] | None:
    """Process one JSON-RPC message. Returns None for notifications."""
    method = req.get("method")
    req_id = req.get("id")

    if "id" not in req:
        return None  # notifications (e.g. notifications/initialized) get no response

    if method == "initialize":
        params = req.get("params", {})
        return _result(req_id, {
            "protocolVersion": params.get("protocolVersion", DEFAULT_PROTOCOL_VERSION),
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        })

    if method == "ping":
        return _result(req_id, {})

    if method == "tools/list":
        return _result(req_id, {"tools": TOOLS})

    if method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name != "lookup_record":
            return _error(req_id, -32602, f"Unknown tool: {tool_name}")
        missing = [k for k in ("collection", "key", "value") if not args.get(k)]
        if missing:
            return _error(req_id, -32602, f"Missing required arguments: {missing}")

        res = await lookup_record(args["collection"], {args["key"]: args["value"]})
        return _result(req_id, {
            "content": [{"type": "text", "text": res.model_dump_json()}],
            "isError": False,
        })

    return _error(req_id, -32601, f"Method not found: {method}")


def _write(msg: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(msg, default=str) + "\n")
    sys.stdout.flush()


async def serve() -> None:
    """Read newline-delimited JSON-RPC from stdin until EOF."""
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break
        if not line.strip():
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            _write(_error(None, -32700, f"Parse error: {exc}"))
            continue
        try:
            resp = await handle_request(req)
        except Exception as exc:
            resp = _error(req.get("id"), -32603, f"Internal error: {exc}")
        if resp is not None:
            _write(resp)


def main():
    asyncio.run(serve())


if __name__ == "__main__":
    main()
