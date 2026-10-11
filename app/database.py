"""
Async MongoDB connection helper.

Design decisions:
- motor (async driver) for FastAPI request handlers — non-blocking I/O.
- pymongo (sync driver) for the seed script and LangGraph checkpointer,
  which both expect synchronous calls.
- A single get_database() factory so every module shares one connection
  pool instead of creating its own.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

# Module-level singletons — initialised on first call, reused thereafter.
_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


def get_database() -> AsyncIOMotorDatabase:
    """Return the shared async MongoDB database handle.

    We lazily create the client so importing this module doesn't
    immediately require a live MongoDB connection (helpful in tests).
    """
    global _client, _database
    if _database is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.mongodb_uri)
        _database = _client[settings.mongodb_db_name]
    return _database


async def close_database() -> None:
    """Gracefully close the MongoDB connection (called on app shutdown)."""
    global _client, _database
    if _client is not None:
        _client.close()
        _client = None
        _database = None
