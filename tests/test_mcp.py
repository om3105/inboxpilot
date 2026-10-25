"""
tests/test_mcp.py — MCP server protocol handling and end-to-end stdio client tests.
"""

import pytest

from evals.compare_mcp import compare
from tools.mcp_client import MCPClient
from tools.mcp_server import handle_request


@pytest.mark.asyncio
async def test_initialize_handshake():
    resp = await handle_request({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}},
    })
    assert resp["result"]["protocolVersion"] == "2025-06-18"
    assert resp["result"]["capabilities"] == {"tools": {}}


@pytest.mark.asyncio
async def test_notification_gets_no_response():
    assert await handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


@pytest.mark.asyncio
async def test_unknown_method_and_tool_errors():
    resp = await handle_request({"jsonrpc": "2.0", "id": 2, "method": "resources/list"})
    assert resp["error"]["code"] == -32601
    resp = await handle_request({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "nope"}})
    assert resp["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_stdio_client_round_trip():
    async with MCPClient() as client:
        tools = await client.list_tools()
        assert tools[0]["name"] == "lookup_record"
        assert "inputSchema" in tools[0]

        found = await client.lookup_record("employees", "employee_id", "EMP001")
        assert found.found and found.record["name"] == "Aarav Sharma"

        missing = await client.lookup_record("employees", "employee_id", "EMP999")
        assert not missing.found


@pytest.mark.asyncio
async def test_benchmark_native_and_mcp_agree():
    results = await compare(verbose=False)
    assert results["lookups"] > 0
    assert results["agreement_pct"] == 100.0
