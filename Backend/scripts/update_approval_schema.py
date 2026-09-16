"""Add Stage 5B execution columns to agent_approvals without Alembic."""

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


SQL_STATEMENTS = [
    "ALTER TABLE agent_approvals ADD COLUMN IF NOT EXISTS executed_at TIMESTAMP WITH TIME ZONE NULL",
    "ALTER TABLE agent_approvals ADD COLUMN IF NOT EXISTS execution_status VARCHAR(50) NULL",
    "ALTER TABLE agent_approvals ADD COLUMN IF NOT EXISTS provider_message_id VARCHAR(255) NULL",
]


async def main() -> None:
    """Apply the lightweight Stage 5B schema updates."""
    async with engine.begin() as connection:
        for statement in SQL_STATEMENTS:
            await connection.execute(text(statement))
    print("Updated agent_approvals schema for Stage 5B.")


if __name__ == "__main__":
    asyncio.run(main())
