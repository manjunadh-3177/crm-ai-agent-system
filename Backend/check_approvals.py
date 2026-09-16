
import asyncio
from sqlalchemy import select
from app.core.config import get_settings
from app.models import AgentApproval
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

async def check_approvals():
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        result = await session.execute(
            select(AgentApproval).order_by(AgentApproval.created_at.desc()).limit(5)
        )
        approvals = result.scalars().all()
        print(f"Found {len(approvals)} recent approvals")
        for a in approvals:
            print(f"ID: {a.id} | Status: {a.status} | Execution: {a.execution_status} | Detail: {a.execution_detail}")

if __name__ == "__main__":
    asyncio.run(check_approvals())
