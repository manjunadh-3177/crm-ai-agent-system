"""Configure the active Twilio SMS webhook URL for the local CRM."""

import asyncio
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.services.sms import configure_twilio_webhook


async def main() -> None:
    result = await configure_twilio_webhook()
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
