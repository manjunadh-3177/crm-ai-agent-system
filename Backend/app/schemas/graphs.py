"""Schemas for graph workflow endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ORMBaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AgentRunRead(ORMBaseSchema):
    id: UUID
    graph_name: str
    event_name: str
    deal_id: UUID | None
    status: str
    result: str
    duration_ms: int
    created_at: datetime
    approval_id: UUID | None = None
    logs: list["AgentRunLogRead"] = []


class AgentRunLogRead(BaseModel):
    time: datetime
    action: str
    message: str
