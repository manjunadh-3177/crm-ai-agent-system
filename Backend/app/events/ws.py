"""Team-scoped WebSocket notification manager."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from collections.abc import Awaitable
from typing import Any
from uuid import UUID

from fastapi import WebSocket

from app.events.redis import EVENT_CHANNEL, EVENT_SOURCE_ID, get_redis_client

logger = logging.getLogger("acufy.events.ws")

WS_EVENT_NAMES = {
    "approval.created",
    "approval.updated",
    "agent_run.created",
    "agent_run.completed",
    "deal.stage_changed",
    "sms.received",
    "sms.updated",
}


class ConnectionManager:
    """Track active team-scoped WebSocket connections."""

    def __init__(self) -> None:
        self._connections: defaultdict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, team_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[str(team_id)].add(websocket)

    def disconnect(self, team_id: UUID, websocket: WebSocket) -> None:
        self._disconnect_by_key(str(team_id), websocket)

    def _disconnect_by_key(self, team_key: str, websocket: WebSocket) -> None:
        self._connections[team_key].discard(websocket)
        if not self._connections[team_key]:
            self._connections.pop(team_key, None)

    async def broadcast(self, team_id: UUID | str, message: dict[str, Any]) -> None:
        team_key = str(team_id)
        stale: list[WebSocket] = []
        for websocket in self._connections.get(team_key, set()):
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(websocket)

        for websocket in stale:
            self._disconnect_by_key(team_key, websocket)


manager = ConnectionManager()
_redis_listener_task: asyncio.Task[None] | None = None


async def broadcast_ws_event(name: str, payload: dict[str, Any]) -> None:
    """Broadcast a supported event to the relevant team room."""
    if name not in WS_EVENT_NAMES:
        return

    team_id = payload.get("team_id")
    if not team_id:
        return

    await manager.broadcast(
        str(team_id),
        {
            "type": "event",
            "name": name,
            "payload": payload,
        },
    )


async def start_redis_ws_bridge() -> None:
    """Subscribe to Redis events so worker-generated updates reach WebSocket clients."""
    global _redis_listener_task
    if _redis_listener_task is None or _redis_listener_task.done():
        _redis_listener_task = asyncio.create_task(_redis_ws_bridge_loop())


async def stop_redis_ws_bridge() -> None:
    """Stop the background Redis listener."""
    global _redis_listener_task
    if _redis_listener_task is not None:
        _redis_listener_task.cancel()
        try:
            await _redis_listener_task
        except asyncio.CancelledError:
            pass
        _redis_listener_task = None


async def _redis_ws_bridge_loop() -> None:
    while True:
        client = await get_redis_client()
        if client is None:
            await asyncio.sleep(5)
            continue

        try:
            pubsub = client.pubsub()
            await pubsub.subscribe(EVENT_CHANNEL)
            logger.info("WebSocket bridge subscribed to Redis channel %s", EVENT_CHANNEL)

            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue

                raw_data = message.get("data")
                if not isinstance(raw_data, str):
                    continue

                event = json.loads(raw_data)
                if event.get("source_id") == EVENT_SOURCE_ID:
                    continue
                await broadcast_ws_event(
                    str(event.get("name")),
                    dict(event.get("payload") or {}),
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("WebSocket bridge lost Redis subscription; retrying in 5 seconds.")
            await asyncio.sleep(5)
        finally:
            await client.aclose()


def websocket_handler(name: str, payload: dict[str, Any]) -> Awaitable[None]:
    """Adapter so the event bus can fan out to WebSocket clients."""
    return broadcast_ws_event(name, payload)
