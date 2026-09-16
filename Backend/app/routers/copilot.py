from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.db import get_db
from app.core.auth import AuthContext, get_auth_context
from app.ai.copilot import route_copilot_intent

router = APIRouter(tags=["copilot"])

class CopilotChatRequest(BaseModel):
    message: str

@router.post("/ai/copilot/chat")
async def copilot_chat(
    payload: CopilotChatRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    return await route_copilot_intent(
        db,
        team_id=auth.team_id,
        user_id=auth.user_id,
        message=payload.message
    )
