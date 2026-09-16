"""Tasks service layer."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.events import emit_event
from app.models import Account, Contact, Deal, Task, Team
from app.schemas.crm import TaskCreate, TaskUpdate
from app.services.audit import log_audit
from app.services.notifications import create_notification


def _detail_options():
    return (
        selectinload(Task.contact),
        selectinload(Task.deal),
        selectinload(Task.account),
    )


async def list_tasks(
    db: AsyncSession,
    *,
    team_id: UUID,
    status_filter: str | None = None,
    priority_filter: str | None = None,
    assigned_user_id: str | None = None,
) -> list[Task]:
    """Return tasks for a team."""
    query = select(Task).options(*_detail_options()).where(Task.team_id == team_id)
    
    if status_filter:
        query = query.where(Task.status == status_filter)
    if priority_filter:
        query = query.where(Task.priority == priority_filter)
    if assigned_user_id:
        query = query.where(Task.assigned_user_id == assigned_user_id)
        
    query = query.order_by(Task.due_at.nulls_last(), Task.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_my_tasks(
    db: AsyncSession, 
    *, 
    team_id: UUID, 
    user_id: str,
    limit: int = 5
) -> list[Task]:
    """Return next 5 due tasks for current user."""
    query = (
        select(Task)
        .options(*_detail_options())
        .where(
            Task.team_id == team_id,
            Task.assigned_user_id == user_id,
            Task.status == "open",
        )
        .order_by(Task.due_at.nulls_last(), Task.priority.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_task_or_404(db: AsyncSession, task_id: UUID, *, team_id: UUID) -> Task:
    """Return a task or raise 404."""
    query = select(Task).options(*_detail_options()).where(Task.id == task_id, Task.team_id == team_id)
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return task


async def create_task(
    db: AsyncSession,
    payload: TaskCreate,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> Task:
    """Create a new task."""
    await _validate_task_payload(db, payload, team_id=team_id)
    
    task = Task(team_id=team_id, **payload.model_dump())
    db.add(task)
    await db.flush()
    
    await log_audit(
        db,
        action="task.created",
        entity_type="task",
        entity_id=str(task.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"title": task.title},
    )

    # Notification for overdue task
    if task.due_at and task.due_at < datetime.now(timezone.utc) and task.status == "open":
        await create_notification(
            db,
            team_id=team_id,
            type="task.overdue",
            title="Task Overdue",
            message=f"Task '{task.title}' is overdue.",
            entity_type="task",
            entity_id=str(task.id),
        )

    await db.commit()
    
    # Emit event for real-time updates
    await emit_event("task.created", {"id": str(task.id), "team_id": str(team_id)})
    
    return await get_task_or_404(db, task.id, team_id=team_id)


async def update_task(
    db: AsyncSession,
    task_id: UUID,
    payload: TaskUpdate,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> Task:
    """Update an existing task."""
    task = await get_task_or_404(db, task_id, team_id=team_id)
    data = payload.model_dump(exclude_unset=True)
    
    # For validation, we need a complete picture if relations are changing
    if any(k in data for k in ["contact_id", "deal_id", "account_id"]):
        validation_payload = TaskCreate(
            title=data.get("title", task.title),
            description=data.get("description", task.description),
            due_at=data.get("due_at", task.due_at),
            priority=data.get("priority", task.priority),
            status=data.get("status", task.status),
            contact_id=data.get("contact_id", task.contact_id),
            deal_id=data.get("deal_id", task.deal_id),
            account_id=data.get("account_id", task.account_id),
            assigned_user_id=data.get("assigned_user_id", task.assigned_user_id),
        )
        await _validate_task_payload(db, validation_payload, team_id=team_id)
    
    for field, value in data.items():
        setattr(task, field, value)
        
    await log_audit(
        db,
        action="task.updated",
        entity_type="task",
        entity_id=str(task.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"updated_fields": sorted(data.keys())},
    )

    # Notification for overdue task
    if task.due_at and task.due_at < datetime.now(timezone.utc) and task.status == "open":
        await create_notification(
            db,
            team_id=team_id,
            type="task.overdue",
            title="Task Overdue",
            message=f"Task '{task.title}' is overdue.",
            entity_type="task",
            entity_id=str(task.id),
        )

    await db.commit()
    
    await emit_event("task.updated", {"id": str(task.id), "team_id": str(team_id)})
    
    return await get_task_or_404(db, task.id, team_id=team_id)


async def mark_done(
    db: AsyncSession,
    task_id: UUID,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> Task:
    """Mark a task as done."""
    task = await get_task_or_404(db, task_id, team_id=team_id)
    if task.status == "done":
        return task
        
    task.status = "done"
    
    await log_audit(
        db,
        action="task.completed",
        entity_type="task",
        entity_id=str(task.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={},
    )
    await db.commit()
    
    await emit_event("task.updated", {"id": str(task.id), "team_id": str(team_id)})
    
    from app.services.automations import run_trigger
    await run_trigger(db, "task.completed", {"id": str(task.id), "priority": task.priority, "status": task.status, "contact_id": str(task.contact_id) if task.contact_id else None, "deal_id": str(task.deal_id) if task.deal_id else None, "account_id": str(task.account_id) if task.account_id else None}, team_id)
    
    return task


async def delete_task(
    db: AsyncSession,
    task_id: UUID,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> None:
    """Delete a task."""
    task = await get_task_or_404(db, task_id, team_id=team_id)
    
    await log_audit(
        db,
        action="task.deleted",
        entity_type="task",
        entity_id=str(task.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"title": task.title},
    )
    await db.delete(task)
    await db.commit()
    
    await emit_event("task.deleted", {"id": str(task_id), "team_id": str(team_id)})


async def _validate_task_payload(db: AsyncSession, payload: TaskCreate, *, team_id: UUID) -> None:
    """Validate task payload data."""
    if payload.contact_id is not None:
        contact = await db.get(Contact, payload.contact_id)
        if contact is None or contact.team_id != team_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found.")
            
    if payload.deal_id is not None:
        deal = await db.get(Deal, payload.deal_id)
        if deal is None or deal.team_id != team_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found.")
            
    if payload.account_id is not None:
        account = await db.get(Account, payload.account_id)
        if account is None or account.team_id != team_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
