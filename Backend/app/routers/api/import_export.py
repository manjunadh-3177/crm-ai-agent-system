"""CSV import/export routes — V1 with flexible column mapping."""

from __future__ import annotations

import base64
import json
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthContext, get_auth_context
from app.core.db import get_db
from app.jobs import IMPORT_QUEUE_THRESHOLD_BYTES, enqueue_background_job
from app.schemas.crm import ImportResultResponse, ImportRowError
from app.services.audit import log_audit
from app.services.import_export import (
    export_accounts_csv,
    export_contacts_csv,
    export_deals_csv,
    export_products_csv,
    import_accounts_csv,
    import_contacts_csv,
    import_contacts_csv_mapped,
    import_products_csv,
    preview_csv,
)


router = APIRouter(tags=["import-export"])


@router.get("/export/contacts.csv")
async def get_export_contacts_csv(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> Response:
    content = await export_contacts_csv(db, team_id=auth.team_id)
    await _log_export(db, team_id=auth.team_id, actor_id=auth.user_id, entity="contacts")
    return _csv_response(content, filename="contacts.csv")


@router.get("/export/accounts.csv")
async def get_export_accounts_csv(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> Response:
    content = await export_accounts_csv(db, team_id=auth.team_id)
    await _log_export(db, team_id=auth.team_id, actor_id=auth.user_id, entity="accounts")
    return _csv_response(content, filename="accounts.csv")


@router.get("/export/deals.csv")
async def get_export_deals_csv(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> Response:
    content = await export_deals_csv(db, team_id=auth.team_id)
    await _log_export(db, team_id=auth.team_id, actor_id=auth.user_id, entity="deals")
    return _csv_response(content, filename="deals.csv")


@router.get("/export/products.csv")
async def get_export_products_csv(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> Response:
    content = await export_products_csv(db, team_id=auth.team_id)
    await _log_export(db, team_id=auth.team_id, actor_id=auth.user_id, entity="products")
    return _csv_response(content, filename="products.csv")


@router.post("/import/contacts/preview")
async def post_import_contacts_preview(
    file: UploadFile = File(...),
    auth: AuthContext = Depends(get_auth_context),
) -> dict:
    """Upload a CSV and receive back its headers + first 5 rows for mapping."""
    return await preview_csv(file)


@router.post("/import/contacts/csv", response_model=ImportResultResponse)
async def post_import_contacts_csv_mapped(
    file: UploadFile = File(...),
    column_map: str = Form(...),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> ImportResultResponse:
    """Import contacts with flexible column mapping.

    Send as multipart/form-data:
    - ``file``: the CSV file
    - ``column_map``: JSON string mapping CRM field → CSV header,
      e.g. ``{"name":"Full Name","email":"Work Email","phone":"Mobile"}``
    """
    try:
        mapping: dict[str, str] = json.loads(column_map)
    except (json.JSONDecodeError, ValueError) as exc:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"column_map must be valid JSON: {exc}",
        ) from exc

    return await import_contacts_csv_mapped(
        db,
        file,
        team_id=auth.team_id,
        actor_id=auth.user_id,
        column_map=mapping,
    )


@router.post("/import/contacts", response_model=ImportResultResponse)
async def post_import_contacts(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> ImportResultResponse:
    content = await file.read()
    if len(content) >= IMPORT_QUEUE_THRESHOLD_BYTES:
        queue_result = await enqueue_background_job(
            "csv_import_job",
            "contacts",
            file.filename or "contacts.csv",
            base64.b64encode(content).decode("utf-8"),
            str(auth.team_id),
            auth.user_id,
            team_id=str(auth.team_id),
        )
        if queue_result.get("queued"):
            return ImportResultResponse(
                entity="contacts",
                created=0,
                skipped=0,
                failed=0,
                errors=[
                    ImportRowError(
                        row_number=0,
                        message=f"Queued background import job {queue_result['job_id']}.",
                        row={},
                    )
                ],
            )
    await file.seek(0)
    return await import_contacts_csv(db, file, team_id=auth.team_id, actor_id=auth.user_id)


@router.post("/import/accounts", response_model=ImportResultResponse)
async def post_import_accounts(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> ImportResultResponse:
    content = await file.read()
    if len(content) >= IMPORT_QUEUE_THRESHOLD_BYTES:
        queue_result = await enqueue_background_job(
            "csv_import_job",
            "accounts",
            file.filename or "accounts.csv",
            base64.b64encode(content).decode("utf-8"),
            str(auth.team_id),
            auth.user_id,
            team_id=str(auth.team_id),
        )
        if queue_result.get("queued"):
            return ImportResultResponse(
                entity="accounts",
                created=0,
                skipped=0,
                failed=0,
                errors=[
                    ImportRowError(
                        row_number=0,
                        message=f"Queued background import job {queue_result['job_id']}.",
                        row={},
                    )
                ],
            )
    await file.seek(0)
    return await import_accounts_csv(db, file, team_id=auth.team_id, actor_id=auth.user_id)


@router.post("/import/products", response_model=ImportResultResponse)
async def post_import_products(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> ImportResultResponse:
    content = await file.read()
    if len(content) >= IMPORT_QUEUE_THRESHOLD_BYTES:
        queue_result = await enqueue_background_job(
            "csv_import_job",
            "products",
            file.filename or "products.csv",
            base64.b64encode(content).decode("utf-8"),
            str(auth.team_id),
            auth.user_id,
            team_id=str(auth.team_id),
        )
        if queue_result.get("queued"):
            return ImportResultResponse(
                entity="products",
                created=0,
                skipped=0,
                failed=0,
                errors=[
                    ImportRowError(
                        row_number=0,
                        message=f"Queued background import job {queue_result['job_id']}.",
                        row={},
                    )
                ],
            )
    await file.seek(0)
    return await import_products_csv(db, file, team_id=auth.team_id, actor_id=auth.user_id)


def _csv_response(content: str, *, filename: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _log_export(
    db: AsyncSession,
    *,
    team_id: UUID,
    actor_id: str | None,
    entity: str,
) -> None:
    await log_audit(
        db,
        action="export.generated",
        entity_type=entity,
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"filename": f"{entity}.csv"},
    )
    await db.commit()
