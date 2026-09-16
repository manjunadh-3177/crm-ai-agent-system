"""Add contact availability fields used by two-way meeting scheduling."""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.db import engine


STATEMENTS = [
    "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS preferred_timezone VARCHAR(100)",
    "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS working_days VARCHAR(100)",
    "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS working_hours_start VARCHAR(20)",
    "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS working_hours_end VARCHAR(20)",
    "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS preferred_meeting_windows VARCHAR(255)",
    "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS blocked_days VARCHAR(255)",
]


async def main() -> None:
    async with engine.begin() as conn:
        for statement in STATEMENTS:
            await conn.execute(text(statement))
            print(f"Executed: {statement}")
    print("Contact availability schema updated.")


if __name__ == "__main__":
    asyncio.run(main())
