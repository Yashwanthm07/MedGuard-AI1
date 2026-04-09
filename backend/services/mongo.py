"""MongoDB connection helper using Motor (async MongoDB driver).

This module provides a small, optional integration layer that initializes a
Motor `AsyncIOMotorClient` when a `MONGODB_URI` (or related env var) is present.
Other parts of the application can import `get_db()` to obtain the async
database object. If no URI is configured, `get_db()` returns `None` and
callers should fall back to in-memory behavior.
"""
from __future__ import annotations

import os
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient

_mongo_client: Optional[AsyncIOMotorClient] = None
_db = None

ENV_NAMES = ["MONGODB_URI", "MONGO_URI", "MONGODB_URL", "DATABASE_URL"]


def _find_mongo_uri() -> Optional[str]:
    for name in ENV_NAMES:
        v = os.getenv(name)
        if v:
            return v
    return None


async def connect_to_mongo(app=None) -> None:
    """Initialize Motor client if a MongoDB URI is configured.

    Sets `app.state.mongo_client` and `app.state.mongodb_db` when available.
    """
    global _mongo_client, _db
    uri = _find_mongo_uri()
    if not uri:
        _mongo_client = None
        _db = None
        if app is not None:
            app.state.mongo_client = None
            app.state.mongodb_db = None
        return

    # Create client and pick a default DB (either from the URI or default to 'medguard')
    _mongo_client = AsyncIOMotorClient(uri)
    try:
        default_db = _mongo_client.get_default_database()
    except Exception:
        default_db = None

    _db = default_db if default_db is not None else _mongo_client.get_database("medguard")

    if app is not None:
        app.state.mongo_client = _mongo_client
        app.state.mongodb_db = _db


async def close_mongo_connection(app=None) -> None:
    """Close the Motor client and clear module state."""
    global _mongo_client, _db
    if _mongo_client is not None:
        try:
            _mongo_client.close()
        except Exception:
            pass

    _mongo_client = None
    _db = None
    if app is not None:
        app.state.mongo_client = None
        app.state.mongodb_db = None


def get_db():
    """Return the Motor database instance or `None` if not configured."""
    return _db


def get_client():
    """Return the Motor client instance or `None` if not configured."""
    return _mongo_client
