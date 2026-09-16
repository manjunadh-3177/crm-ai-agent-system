"""Simple in-memory event bus with optional Redis fan-out."""

from __future__ import annotations

import inspect
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from pprint import pformat
from typing import Any

from app.events.redis import publish_event


logger = logging.getLogger("acufy.events")

EventHandler = Callable[[str, dict[str, Any]], Any | Awaitable[Any]]

DEFAULT_EVENT_NAMES = [
    "contact.created",
    "contact.updated",
    "contact.deleted",
    "approval.created",
    "approval.updated",
    "agent_run.created",
    "agent_run.completed",
    "deal.created",
    "deal.updated",
    "deal.stage_changed",
]

_handlers: defaultdict[str, list[EventHandler]] = defaultdict(list)


def register_handler(name: str, handler: EventHandler) -> None:
    """Register a handler for an event name."""
    if handler not in _handlers[name]:
        _handlers[name].append(handler)


async def emit_event(name: str, payload: dict[str, Any]) -> None:
    """Emit an event to local handlers and Redis when available."""
    for handler in _handlers.get(name, []):
        result = handler(name, payload)
        if inspect.isawaitable(result):
            await result

    await publish_event(name, payload)


def get_registered_events() -> list[str]:
    """Return registered event names."""
    return sorted(name for name, handlers in _handlers.items() if handlers)


def register_default_handlers() -> None:
    """Register the default logging handler for supported events."""
    for event_name in DEFAULT_EVENT_NAMES:
        register_handler(event_name, _logging_handler)


def _logging_handler(name: str, payload: dict[str, Any]) -> None:
    """Log emitted events in a readable format."""
    logger.info("EVENT %s\n%s", name, pformat(payload, sort_dicts=True))
