"""
tools/mcp_server.py — Model Context Protocol (MCP) server for InboxPilot.

Exposes MongoDB database lookups as standard MCP tool definitions.
This decouples database access from the core agent, allowing any MCP-compliant
agent runtime (e.g. Claude Desktop, Cursor, LangChain MCP adapters) to interact
with enterprise records safely.
"""

from __future__ import annotations

import json
import sys
from typing import Any
from scripts.seed_db import get_mock_employees, get_mock_invoices, get_mock_tickets

# Cached records for MCP lookup protocol
RECORDS = {
    "employees": {e["employee_id"]: e for e in get_mock_employees()},
    "invoices": {i["invoice_number"]: i for i in get_mock_invoices()},
    "tickets": {t["ticket_id"]: t for t in get_mock_tickets()},
}

TOOLS = [
    {
        "name": "mcp_lookup_record",
        "description": "Lookup an enterprise record in employees, invoices, or tickets by query filter",
        "parameters": {
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


def handle_lookup(collection: str, key: str, value: str) -> dict[str, Any]:
    """Execute lookup in the target collection."""
    coll = RECORDS.get(collection, {})
    for doc in coll.values():
        if str(doc.get(key, "")).lower() == str(value).lower():
            return {"found": True, "collection": collection, "record": doc}
    return {"found": False, "collection": collection, "record": {}}


def handle_request(req: dict[str, Any]) -> dict[str, Any]:
    """Process incoming JSON-RPC protocol message."""
    method = req.get("method")
    req_id = req.get("id")

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    elif method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name == "mcp_lookup_record":
            res = handle_lookup(
                collection=args.get("collection", ""),
                key=args.get("key", ""),
                value=args.get("value", ""),
            )
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(res)}]},
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"},
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32600, "message": f"Unsupported method: {method}"},
    }


def main():
    """Run MCP server over stdio."""
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as exc:
            err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
            sys.stdout.write(json.dumps(err) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
