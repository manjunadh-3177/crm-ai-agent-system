"""Add Stage 5C execution detail column without Alembic."""

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


async def main() -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text("ALTER TABLE agent_approvals ADD COLUMN IF NOT EXISTS execution_detail VARCHAR(1000) NULL")
        )
    print("Updated agent_approvals schema for Stage 5C.")


if __name__ == "__main__":
    asyncio.run(main())
