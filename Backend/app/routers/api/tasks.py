"""Tasks API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthContext, get_auth_context
from app.core.db import get_db
from app.schemas.crm import TaskCreate, TaskRead, TaskUpdate
from app.services.tasks import (
    create_task,
    delete_task,
    get_my_tasks,
    list_tasks,
    mark_done,
    update_task,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskRead])
async def get_tasks(
    status_filter: str | None = None,
    priority_filter: str | None = None,
    assigned_user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[TaskRead]:
    """Return tasks for the authenticated team."""
    return await list_tasks(
        db,
        team_id=auth.team_id,
        status_filter=status_filter,
        priority_filter=priority_filter,
        assigned_user_id=assigned_user_id,
    )


@router.get("/my", response_model=list[TaskRead])
async def get_personal_tasks(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[TaskRead]:
    """Return upcoming tasks assigned to the current user."""
    return await get_my_tasks(db, team_id=auth.team_id, user_id=auth.user_id)


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def post_task(
    payload: TaskCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> TaskRead:
    """Create a new task."""
    return await create_task(db, payload, team_id=auth.team_id, actor_id=auth.user_id)


@router.patch("/{task_id}", response_model=TaskRead)
async def patch_task(
    task_id: UUID,
    payload: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> TaskRead:
    """Update a task."""
    return await update_task(
        db,
        task_id,
        payload,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )


@router.post("/{task_id}/done", response_model=TaskRead)
async def post_task_done(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> TaskRead:
    """Mark a task as done."""
    return await mark_done(db, task_id, team_id=auth.team_id, actor_id=auth.user_id)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_route(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> None:
    """Delete a task."""
    await delete_task(db, task_id, team_id=auth.team_id, actor_id=auth.user_id)
