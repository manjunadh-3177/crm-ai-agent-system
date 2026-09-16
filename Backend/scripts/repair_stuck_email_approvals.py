"""Repair approved email approvals stuck in queued/sending states."""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text

from app.core.db import AsyncSessionLocal


REPAIR_SQL = """
UPDATE agent_approvals
SET execution_status = 'failed',
    executed_at = COALESCE(executed_at, NOW()),
    execution_detail = COALESCE(execution_detail, 'Timed out during email delivery. Retry send is available.')
WHERE status = 'approved'
  AND type = 'email'
  AND COALESCE(execution_status, 'queued') IN ('queued', 'sending')
  AND decided_at < NOW() - INTERVAL '5 minutes';
"""


async def main() -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(REPAIR_SQL))
        await session.commit()
        print(f"Repaired {result.rowcount or 0} stuck approved email approvals.")


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
