"""Application event bus."""

from app.events.bus import (
    DEFAULT_EVENT_NAMES,
    emit_event,
    get_registered_events,
    register_default_handlers,
    register_handler,
)
from app.events.redis import EVENT_CHANNEL, check_redis_connection
from app.events.ws import WS_EVENT_NAMES, broadcast_ws_event, websocket_handler

register_default_handlers()
for event_name in WS_EVENT_NAMES:
    register_handler(event_name, websocket_handler)

__all__ = [
    "DEFAULT_EVENT_NAMES",
    "EVENT_CHANNEL",
    "WS_EVENT_NAMES",
    "broadcast_ws_event",
    "check_redis_connection",
    "emit_event",
    "get_registered_events",
    "register_default_handlers",
    "register_handler",
]
