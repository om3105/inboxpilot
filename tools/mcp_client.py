"""
tools/mcp_client.py — Stdio MCP client for the InboxPilot records server.

Spawns `python -m tools.mcp_server` as a subprocess and speaks JSON-RPC 2.0
over its stdin/stdout, so every lookup crosses a real process and protocol
boundary.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import os
import sys
from typing import Any

from app.models import LookupResult

PROTOCOL_VERSION = "2025-06-18"
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class MCPClient:
    """Minimal async MCP client over the stdio transport."""

    def __init__(self) -> None:
        self._proc: asyncio.subprocess.Process | None = None
        self._ids = itertools.count(1)

    async def __aenter__(self) -> "MCPClient":
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def start(self) -> dict[str, Any]:
        """Spawn the server and perform the initialize handshake."""
        self._proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "tools.mcp_server",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            cwd=_PROJECT_ROOT,
        )
        init = await self.request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "inboxpilot-client", "version": "1.0.0"},
        })
        await self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return init

    async def close(self) -> None:
        if self._proc is None:
            return
        if self._proc.stdin and not self._proc.stdin.is_closing():
            self._proc.stdin.close()
        try:
            await asyncio.wait_for(self._proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            self._proc.kill()
            await self._proc.wait()
        self._proc = None

    async def _send(self, msg: dict[str, Any]) -> None:
        assert self._proc and self._proc.stdin
        self._proc.stdin.write((json.dumps(msg) + "\n").encode())
        await self._proc.stdin.drain()

    async def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a request and wait for its response; raises on JSON-RPC errors."""
        assert self._proc and self._proc.stdout
        req_id = next(self._ids)
        await self._send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}})
        line = await self._proc.stdout.readline()
        if not line:
            raise ConnectionError("MCP server closed the connection")
        resp = json.loads(line)
        if resp.get("id") != req_id:
            raise RuntimeError(f"Mismatched response id {resp.get('id')} for request {req_id}")
        if "error" in resp:
            raise RuntimeError(f"MCP error {resp['error']['code']}: {resp['error']['message']}")
        return resp["result"]

    async def list_tools(self) -> list[dict[str, Any]]:
        return (await self.request("tools/list"))["tools"]

    async def lookup_record(self, collection: str, key: str, value: str) -> LookupResult:
        """Invoke the server's lookup_record tool."""
        result = await self.request("tools/call", {
            "name": "lookup_record",
            "arguments": {"collection": collection, "key": key, "value": value},
        })
        return LookupResult.model_validate_json(result["content"][0]["text"])
