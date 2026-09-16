"""Create the sms_messages table if needed."""

import asyncio
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.db import create_all_tables


async def main() -> None:
    await create_all_tables()
    print("SMS schema updated.")


if __name__ == "__main__":
    asyncio.run(main())
