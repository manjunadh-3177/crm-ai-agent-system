"""Redis-backed event worker."""

from __future__ import annotations

import asyncio
import json
import logging
import sys

from app.ai.agents.followup_agent import SUPPORTED_EVENTS, run_followup_agent
from app.core.db import AsyncSessionLocal
from app.events import EVENT_CHANNEL
from app.events.redis import get_redis_client

logger = logging.getLogger("acufy.worker.events")


async def run_worker() -> None:
    """Listen for Redis-published events and log them."""
    while True:
        client = await get_redis_client()
        if client is None:
            logger.warning("Redis unavailable; worker retrying in 5 seconds.")
            await asyncio.sleep(5)
            continue

        try:
            pubsub = client.pubsub()
            await pubsub.subscribe(EVENT_CHANNEL)
            logger.info("Worker subscribed to Redis channel %s", EVENT_CHANNEL)

            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue

                raw_data = message.get("data")
                if not isinstance(raw_data, str):
                    continue

                event = json.loads(raw_data)
                logger.info(
                    "WORKER EVENT %s payload=%s emitted_at=%s",
                    event.get("name"),
                    event.get("payload"),
                    event.get("emitted_at"),
                )
                if event.get("name") in SUPPORTED_EVENTS:
                    async with AsyncSessionLocal() as session:
                        try:
                            result = await run_followup_agent(
                                session,
                                event_name=event["name"],
                                payload=event.get("payload", {}),
                            )
                            logger.info(
                                "FOLLOWUP AGENT RESULT event=%s result=%s",
                                event["name"],
                                result,
                            )
                        except Exception:
                            logger.exception("FollowUpAgent failed for event %s", event.get("name"))
        except Exception:
            logger.exception("Worker lost Redis subscription; retrying in 5 seconds.")
            await asyncio.sleep(5)
        finally:
            await client.aclose()


def main() -> None:
    """Run the worker with Windows-friendly asyncio settings."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
