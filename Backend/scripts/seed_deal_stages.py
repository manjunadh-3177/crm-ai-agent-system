"""Seed default pipeline stages for existing teams."""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.db import AsyncSessionLocal
from app.models import DealStage, Team


DEFAULT_STAGES: list[tuple[str, bool]] = [
    ("Lead", False),
    ("Qualified", False),
    ("Meeting", False),
    ("Proposal", False),
    ("Negotiation", False),
    ("Won", True),
    ("Lost", True),
]


async def main() -> None:
    """Create default stages for every team that does not already have them."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Team).order_by(Team.created_at))
        teams = result.scalars().all()

        created_count = 0
        for team in teams:
            existing_result = await session.execute(
                select(DealStage).where(DealStage.team_id == team.id)
            )
            existing_stage_names = {stage.name for stage in existing_result.scalars().all()}

            for position, (name, is_closed) in enumerate(DEFAULT_STAGES, start=1):
                if name in existing_stage_names:
                    continue

                session.add(
                    DealStage(
                        team_id=team.id,
                        name=name,
                        position=position,
                        is_closed=is_closed,
                    )
                )
                created_count += 1

        await session.commit()
        print(f"Seeded {created_count} deal stages.")


if __name__ == "__main__":
    asyncio.run(main())
