"""
tools/lookup_record.py — MongoDB enterprise record lookup.

Queries collections: 'employees', 'invoices', or 'tickets'.
Falls back gracefully to mock in-memory stores if Atlas is unreachable,
ensuring offline tests and evals remain fast and resilient.
"""

from __future__ import annotations

import logging
from typing import Any
from app.config import get_settings
from app.models import DocumentType, LookupResult
from scripts.seed_db import get_mock_employees, get_mock_invoices, get_mock_tickets

logger = logging.getLogger("inboxpilot.tools.lookup")

# Fallback in-memory store for offline environments; shared with apply_update
# so approved mutations are visible to subsequent lookups.
MOCK_STORE = {
    "employees": {e["employee_id"]: e for e in get_mock_employees()},
    "invoices": {i["invoice_number"]: i for i in get_mock_invoices()},
    "tickets": {t["ticket_id"]: t for t in get_mock_tickets()},
}


def reset_mock_store() -> None:
    """Restore the in-memory store to seed data (used by tests)."""
    MOCK_STORE["employees"] = {e["employee_id"]: e for e in get_mock_employees()}
    MOCK_STORE["invoices"] = {i["invoice_number"]: i for i in get_mock_invoices()}
    MOCK_STORE["tickets"] = {t["ticket_id"]: t for t in get_mock_tickets()}


async def lookup_record(
    collection: str,
    query: dict[str, Any],
) -> LookupResult:
    """Query a MongoDB collection by query filter.

    Args:
        collection: 'employees', 'invoices', or 'tickets'
        query: MongoDB filter dict (e.g. {"employee_id": "EMP001"})

    Returns:
        LookupResult indicating found status and matched document.
    """
    if not collection:
        return LookupResult(
            found=False,
            collection="",
            record={},
            message="No target collection specified for lookup",
        )

    # 1. Try live MongoDB, except in public demo mode: the demo sandbox never
    #    reads or writes the real database.
    if not get_settings().demo_public:
        try:
            from app.database import get_database
            db = get_database()
            coll = db[collection]
            record = await coll.find_one(query)
            if record:
                # Clean Mongo _id for JSON serializability
                clean_rec = dict(record)
                if "_id" in clean_rec:
                    clean_rec["_id"] = str(clean_rec["_id"])
                return LookupResult(
                    found=True,
                    collection=collection,
                    record=clean_rec,
                    message=f"Record found in {collection}",
                )
            # Live query succeeded with no match: don't fall back to mock data,
            # or the agent could approve writes against records that don't exist.
            return LookupResult(
                found=False,
                collection=collection,
                record={},
                message=f"No record matching {query} found in {collection}",
            )
        except Exception as exc:
            logger.info("Live MongoDB lookup unavailable or timed out (%s); querying mock seed cache.", exc)

    # 2. Resilient fallback to mock cache
    cache = MOCK_STORE.get(collection, {})
    for doc in cache.values():
        matches = True
        for k, v in query.items():
            if str(doc.get(k, "")).lower() != str(v).lower():
                matches = False
                break
        if matches:
            clean_rec = dict(doc)
            return LookupResult(
                found=True,
                collection=collection,
                record=clean_rec,
                message=f"Record found in {collection} (local cache)",
            )

    return LookupResult(
        found=False,
        collection=collection,
        record={},
        message=f"No record matching {query} found in {collection}",
    )
