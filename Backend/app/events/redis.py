"""Redis helpers for event publishing."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings


logger = logging.getLogger("acufy.events.redis")
EVENT_CHANNEL = "acufy:events"
EVENT_SOURCE_ID = f"{os.getpid()}"


def _import_redis_module():
    try:
        from redis import asyncio as redis_asyncio
    except ImportError:
        return None
    return redis_asyncio


async def get_redis_client():
    """Create a Redis client if Redis is configured and available in the environment."""
    settings = get_settings()
    if not settings.redis_url:
        return None

    redis_asyncio = _import_redis_module()
    if redis_asyncio is None:
        logger.warning("Redis package not installed; using in-memory event bus only.")
        return None

    return redis_asyncio.from_url(settings.redis_url, decode_responses=True)


async def publish_event(name: str, payload: dict[str, Any]) -> bool:
    """Publish an event to Redis when available."""
    client = await get_redis_client()
    if client is None:
        return False

    envelope = {
        "name": name,
        "payload": payload,
        "emitted_at": datetime.now(timezone.utc).isoformat(),
        "source_id": EVENT_SOURCE_ID,
    }

    try:
        await client.publish(EVENT_CHANNEL, json.dumps(envelope))
    except Exception:
        logger.warning("Redis publish failed for event %s; falling back to local-only handlers.", name)
        return False
    finally:
        await client.aclose()

    return True


async def check_redis_connection() -> bool:
    """Return whether Redis is reachable."""
    client = await get_redis_client()
    if client is None:
        return False

    try:
        return bool(await client.ping())
    except Exception:
        return False
    finally:
        await client.aclose()
