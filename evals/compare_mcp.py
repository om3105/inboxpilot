"""
evals/compare_mcp.py — Benchmark comparison: Native DB Tool vs MCP Protocol Tool.

Compares:
  - Lookup Accuracy (%)
  - Latency (ms)
  - Architectural Decoupling / Interoperability
"""

import asyncio
import time
import json
from tools.lookup_record import lookup_record
from tools.mcp_client import mcp_lookup_record


async def compare():
    with open("evals/dataset.json", "r") as f:
        cases = json.load(f)

    # 1. Native Direct Lookup Benchmark
    start = time.perf_counter()
    native_correct = 0
    total = 0
    for c in cases:
        extracted = c.get("expected_extracted", {})
        doc_type = c.get("expected_doc_type")
        if doc_type == "leave_request" and extracted.get("employee_id"):
            total += 1
            res = await lookup_record("employees", {"employee_id": extracted["employee_id"]})
            if res.found:
                native_correct += 1
        elif doc_type == "invoice" and extracted.get("invoice_number"):
            total += 1
            res = await lookup_record("invoices", {"invoice_number": extracted["invoice_number"]})
            if res.found:
                native_correct += 1
        elif doc_type == "support_ticket" and extracted.get("ticket_id"):
            total += 1
            res = await lookup_record("tickets", {"ticket_id": extracted["ticket_id"]})
            if res.found:
                native_correct += 1

    native_duration_ms = (time.perf_counter() - start) * 1000

    # 2. MCP Protocol Tool Benchmark
    start = time.perf_counter()
    mcp_correct = 0
    for c in cases:
        extracted = c.get("expected_extracted", {})
        doc_type = c.get("expected_doc_type")
        if doc_type == "leave_request" and extracted.get("employee_id"):
            res = await mcp_lookup_record("employees", "employee_id", extracted["employee_id"])
            if res.found:
                mcp_correct += 1
        elif doc_type == "invoice" and extracted.get("invoice_number"):
            res = await mcp_lookup_record("invoices", "invoice_number", extracted["invoice_number"])
            if res.found:
                mcp_correct += 1
        elif doc_type == "support_ticket" and extracted.get("ticket_id"):
            res = await mcp_lookup_record("tickets", "ticket_id", extracted["ticket_id"])
            if res.found:
                mcp_correct += 1

    mcp_duration_ms = (time.perf_counter() - start) * 1000

    print("=" * 68)
    print("      BENCHMARK COMPARISON: NATIVE LOOKUP vs MCP PROTOCOL")
    print("=" * 68)
    print(f"| Metric                      | Native Direct Tool | MCP Tool Server |")
    print(f"|-----------------------------|--------------------|-----------------|")
    print(f"| Lookups Evaluated           | {total:<18} | {total:<15} |")
    print(f"| Lookup Accuracy (%)         | {(native_correct/total*100):.1f}%{'':<13} | {(mcp_correct/total*100):.1f}%{'':<10} |")
    print(f"| Total Benchmark Latency     | {native_duration_ms:.2f} ms{'':<10} | {mcp_duration_ms:.2f} ms{'':<7} |")
    print(f"| Avg Query Latency           | {(native_duration_ms/total):.2f} ms{'':<10} | {(mcp_duration_ms/total):.2f} ms{'':<7} |")
    print(f"| Interoperability Standard   | Internal Python    | JSON-RPC (MCP)  |")
    print("=" * 68 + "\n")


if __name__ == "__main__":
    asyncio.run(compare())
