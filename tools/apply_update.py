"""
tools/apply_update.py — Applies high-risk database mutations.

REQUIRES HUMAN APPROVAL: This tool executes write operations against MongoDB
Atlas. It updates employee leave balances, marks invoices paid, or closes tickets.
"""

from __future__ import annotations

import logging
from typing import Any
from app.config import get_settings
from app.models import ProposedAction
from tools.lookup_record import MOCK_STORE

logger = logging.getLogger("inboxpilot.tools.apply_update")


async def apply_update(action: ProposedAction) -> dict[str, Any]:
    """Execute a database update following human approval.

    Args:
        action: Validated ProposedAction containing collection, filter, and update payload.

    Returns:
        dict summary of execution (success, matched_count, modified_count).
    """
    collection = action.collection
    filter_query = action.filter_query
    update_payload = action.update_payload

    # 1. Try live MongoDB, except in public demo mode: the demo sandbox never
    #    reads or writes the real database.
    if not get_settings().demo_public:
        try:
            from app.database import get_database
            db = get_database()
            coll = db[collection]
            result = await coll.update_one(filter_query, update_payload)
            return {
                "success": result.matched_count > 0,
                "matched_count": result.matched_count,
                "modified_count": result.modified_count,
                "collection": collection,
                "reason": action.reason,
                "mode": "mongodb_live",
            }
        except Exception as exc:
            logger.info("Live MongoDB unavailable (%s); executing on local mock store.", exc)

    # 2. Local fallback execution
    store = MOCK_STORE.get(collection, {})
    matched_key = None
    for k, doc in store.items():
        if all(str(doc.get(q_k, "")).lower() == str(q_v).lower() for q_k, q_v in filter_query.items()):
            matched_key = k
            break

    if not matched_key:
        return {
            "success": False,
            "matched_count": 0,
            "modified_count": 0,
            "error": f"No record matching {filter_query} in local store",
            "mode": "local_mock",
        }

    doc = store[matched_key]
    # Handle $set
    if "$set" in update_payload:
        for k, v in update_payload["$set"].items():
            doc[k] = v

    # Handle $inc
    if "$inc" in update_payload:
        for k, v in update_payload["$inc"].items():
            parts = k.split(".")
            if len(parts) == 2 and parts[0] in doc and isinstance(doc[parts[0]], dict):
                doc[parts[0]][parts[1]] = doc[parts[0]].get(parts[1], 0) + v
            else:
                doc[k] = doc.get(k, 0) + v

    return {
        "success": True,
        "matched_count": 1,
        "modified_count": 1,
        "collection": collection,
        "reason": action.reason,
        "mode": "local_mock",
    }
