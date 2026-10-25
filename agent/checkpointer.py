"""
agent/checkpointer.py — Persistent MongoDB Atlas checkpointer factory.

LangGraph checkpoints preserve the full graph state across pauses, restarts,
and redeployments. Render containers have ephemeral disks, so storing
checkpoints in MongoDB Atlas guarantees that thread states waiting for
human sign-off survive cold restarts.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from app.config import get_settings
from agent.graph import build_agent_graph

logger = logging.getLogger("inboxpilot.checkpointer")

_compiled_agent = None
_checkpointer_instance = None


def get_checkpointer():
    """Return the configured checkpointer (MongoDBSaver in prod, MemorySaver in test/local)."""
    global _checkpointer_instance
    if _checkpointer_instance is not None:
        return _checkpointer_instance

    settings = get_settings()
    uri = settings.mongodb_uri
    if settings.demo_public:
        # Public demo: keep visitors' run state out of the real database.
        uri = ""

    if uri and ("mongodb+srv://" in uri or "mongodb://" in uri) and not uri.startswith("mongodb://test"):
        try:
            from langgraph.checkpoint.mongodb import MongoDBSaver
            from pymongo import MongoClient

            client = MongoClient(uri, serverSelectionTimeoutMS=2000)
            # Ping to verify
            client.admin.command("ping")
            saver = MongoDBSaver(client=client, db_name=settings.mongodb_db_name)
            logger.info("Connected to MongoDB Atlas checkpointer in database '%s'.", settings.mongodb_db_name)
            _checkpointer_instance = saver
            return _checkpointer_instance
        except Exception as exc:
            logger.warning(
                "Could not connect to MongoDB Atlas for checkpointer (%s). Falling back to MemorySaver.",
                exc,
            )

    logger.info("Using in-memory MemorySaver checkpointer.")
    _checkpointer_instance = MemorySaver()
    return _checkpointer_instance


def get_agent():
    """Return the compiled singleton LangGraph agent."""
    global _compiled_agent
    if _compiled_agent is None:
        checkpointer = get_checkpointer()
        _compiled_agent = build_agent_graph(checkpointer=checkpointer)
    return _compiled_agent
