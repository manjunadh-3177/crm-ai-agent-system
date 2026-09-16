"""Schemas for admin endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ORMBaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AuditLogRead(ORMBaseSchema):
    id: UUID
    team_id: UUID | None
    actor_type: str
    actor_id: str | None
    action: str
    entity_type: str
    entity_id: str | None
    metadata_json: dict
    created_at: datetime
