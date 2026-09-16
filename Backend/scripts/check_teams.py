import asyncio
from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.models import Team

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Team))
        teams = result.scalars().all()
        for t in teams:
            print(f"ID: {t.id}, Name: {t.name}")

if __name__ == "__main__":
    asyncio.run(main())
