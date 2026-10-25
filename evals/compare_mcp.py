"""
evals/compare_mcp.py — Benchmark comparison: native lookup tool vs MCP stdio server.

Both paths share the same backend (tools.lookup_record), so this measures:
  - Result agreement: does the MCP path return the same record as the native call?
  - Latency: per-lookup cost of the in-process call vs a JSON-RPC round trip to
    a separate server process, plus the one-time server startup + handshake.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time

from tools.lookup_record import lookup_record
from tools.mcp_client import MCPClient

_ID_FIELDS = {
    "leave_request": ("employees", "employee_id"),
    "invoice": ("invoices", "invoice_number"),
    "support_ticket": ("tickets", "ticket_id"),
}


def build_lookups(dataset_path: str = "evals/dataset.json") -> list[tuple[str, str, str]]:
    """Derive (collection, key, value) lookups from labelled dataset identifiers."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        cases = json.load(f)
    lookups = []
    for c in cases:
        target = _ID_FIELDS.get(c.get("expected_doc_type"))
        if not target:
            continue
        collection, key = target
        value = c.get("expected_extracted", {}).get(key)
        if value:
            lookups.append((collection, key, value))
    return lookups


def _stats(samples_ms: list[float]) -> dict[str, float]:
    ordered = sorted(samples_ms)
    return {
        "mean_ms": statistics.fmean(ordered),
        "p50_ms": statistics.median(ordered),
        "p95_ms": ordered[max(0, round(0.95 * len(ordered)) - 1)],
    }


async def compare(dataset_path: str = "evals/dataset.json", verbose: bool = True) -> dict:
    lookups = build_lookups(dataset_path)

    native_results, native_ms = [], []
    for collection, key, value in lookups:
        start = time.perf_counter()
        native_results.append(await lookup_record(collection, {key: value}))
        native_ms.append((time.perf_counter() - start) * 1000)

    start = time.perf_counter()
    async with MCPClient() as client:
        startup_ms = (time.perf_counter() - start) * 1000
        mcp_results, mcp_ms = [], []
        for collection, key, value in lookups:
            start = time.perf_counter()
            mcp_results.append(await client.lookup_record(collection, key, value))
            mcp_ms.append((time.perf_counter() - start) * 1000)

    agree = sum(
        n.found == m.found and n.record.get(k) == m.record.get(k)
        for n, m, (_, k, _) in zip(native_results, mcp_results, lookups)
    )
    results = {
        "lookups": len(lookups),
        "found": sum(r.found for r in native_results),
        "agreement_pct": round(agree / len(lookups) * 100, 1) if lookups else None,
        "native": _stats(native_ms),
        "mcp": _stats(mcp_ms),
        "mcp_startup_ms": startup_ms,
    }

    if verbose:
        n, m = results["native"], results["mcp"]
        print(f"\nNative lookup vs MCP stdio server — {results['lookups']} lookups "
              f"({results['found']} records found)\n")
        print("| Metric                | Native (in-process) | MCP (stdio JSON-RPC) |")
        print("|-----------------------|---------------------|----------------------|")
        print(f"| Result agreement      | baseline            | {str(results['agreement_pct']) + '%':<20} |")
        print(f"| Mean latency / lookup | {n['mean_ms']:>8.3f} ms         | {m['mean_ms']:>8.3f} ms          |")
        print(f"| p50 latency           | {n['p50_ms']:>8.3f} ms         | {m['p50_ms']:>8.3f} ms          |")
        print(f"| p95 latency           | {n['p95_ms']:>8.3f} ms         | {m['p95_ms']:>8.3f} ms          |")
        print(f"| One-time startup      | none                | {startup_ms:>8.1f} ms          |\n")
    return results


if __name__ == "__main__":
    asyncio.run(compare())
