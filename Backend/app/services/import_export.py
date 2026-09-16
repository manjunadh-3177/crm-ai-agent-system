"""CSV import/export and bulk operation helpers."""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Account, Contact, Deal, DealLineItem, DealStage, Product
from app.schemas.crm import (
    AccountCreate,
    BulkDealStageUpdateRequest,
    BulkDeleteRequest,
    BulkOperationResponse,
    ContactCreate,
    ImportResultResponse,
    ImportRowError,
    ProductCreate,
)
from app.services.audit import log_audit


@dataclass(slots=True)
class CsvDefinition:
    entity: str
    headers: list[str]
    duplicate_field: str


CONTACTS_CSV = CsvDefinition(
    entity="contacts",
    headers=["first_name", "last_name", "email", "phone", "consent_sms", "consent_email"],
    duplicate_field="email",
)
ACCOUNTS_CSV = CsvDefinition(
    entity="accounts",
    headers=["name", "domain", "industry"],
    duplicate_field="name",
)
PRODUCTS_CSV = CsvDefinition(
    entity="products",
    headers=["name", "sku", "description", "price", "currency"],
    duplicate_field="sku",
)


async def export_contacts_csv(db: AsyncSession, *, team_id: UUID) -> str:
    contacts = list(
        (
            await db.execute(select(Contact).where(Contact.team_id == team_id).order_by(Contact.created_at))
        ).scalars()
    )
    return _write_csv(
        CONTACTS_CSV.headers,
        [
            {
                "first_name": contact.first_name,
                "last_name": contact.last_name,
                "email": contact.email,
                "phone": contact.phone or "",
                "consent_sms": str(contact.consent_sms).lower(),
                "consent_email": str(contact.consent_email).lower(),
            }
            for contact in contacts
        ],
    )


async def export_accounts_csv(db: AsyncSession, *, team_id: UUID) -> str:
    accounts = list(
        (await db.execute(select(Account).where(Account.team_id == team_id).order_by(Account.created_at))).scalars()
    )
    return _write_csv(
        ACCOUNTS_CSV.headers,
        [
            {
                "name": account.name,
                "domain": account.domain or "",
                "industry": account.industry or "",
            }
            for account in accounts
        ],
    )


async def export_deals_csv(db: AsyncSession, *, team_id: UUID) -> str:
    deals = list(
        (
            await db.execute(
                select(Deal)
                .options(selectinload(Deal.stage), selectinload(Deal.contact), selectinload(Deal.account))
                .where(Deal.team_id == team_id)
                .order_by(Deal.created_at)
            )
        ).scalars()
    )
    headers = [
        "name",
        "amount",
        "currency",
        "probability",
        "expected_close_date",
        "stage",
        "contact_email",
        "account_name",
    ]
    return _write_csv(
        headers,
        [
            {
                "name": deal.name,
                "amount": str(deal.amount) if deal.amount is not None else "",
                "currency": deal.currency,
                "probability": str(deal.probability) if deal.probability is not None else "",
                "expected_close_date": deal.expected_close_date.isoformat() if deal.expected_close_date else "",
                "stage": deal.stage.name if deal.stage else "",
                "contact_email": deal.contact.email if deal.contact else "",
                "account_name": deal.account.name if deal.account else "",
            }
            for deal in deals
        ],
    )


async def export_products_csv(db: AsyncSession, *, team_id: UUID) -> str:
    products = list(
        (await db.execute(select(Product).where(Product.team_id == team_id).order_by(Product.created_at))).scalars()
    )
    return _write_csv(
        PRODUCTS_CSV.headers,
        [
            {
                "name": product.name,
                "sku": product.sku,
                "description": product.description or "",
                "price": str(product.price),
                "currency": product.currency,
            }
            for product in products
        ],
    )


async def import_contacts_csv(
    db: AsyncSession,
    file: UploadFile,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> ImportResultResponse:
    content = await file.read()
    return await _run_import_from_content(
        db,
        filename=file.filename or "contacts.csv",
        content=content,
        definition=CONTACTS_CSV,
        team_id=team_id,
        actor_id=actor_id,
        existing_values=await _load_existing_values(db, Contact, "email", team_id=team_id),
        row_builder=_build_contact_payload,
        row_creator=lambda payload: Contact(team_id=team_id, **payload.model_dump()),
    )


async def import_accounts_csv(
    db: AsyncSession,
    file: UploadFile,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> ImportResultResponse:
    content = await file.read()
    return await _run_import_from_content(
        db,
        filename=file.filename or "accounts.csv",
        content=content,
        definition=ACCOUNTS_CSV,
        team_id=team_id,
        actor_id=actor_id,
        existing_values=await _load_existing_values(db, Account, "name", team_id=team_id),
        row_builder=_build_account_payload,
        row_creator=lambda payload: Account(team_id=team_id, **payload.model_dump()),
    )


async def import_products_csv(
    db: AsyncSession,
    file: UploadFile,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> ImportResultResponse:
    content = await file.read()
    return await _run_import_from_content(
        db,
        filename=file.filename or "products.csv",
        content=content,
        definition=PRODUCTS_CSV,
        team_id=team_id,
        actor_id=actor_id,
        existing_values=await _load_existing_values(db, Product, "sku", team_id=team_id),
        row_builder=_build_product_payload,
        row_creator=lambda payload: Product(team_id=team_id, **payload.model_dump()),
    )


async def run_import_from_bytes(
    db: AsyncSession,
    *,
    entity: str,
    filename: str,
    content: bytes,
    team_id: UUID,
    actor_id: str | None = None,
    column_map: dict[str, str] | None = None,
) -> ImportResultResponse:
    """Run an import from in-memory file bytes for background jobs."""
    if entity == "contacts":
        if column_map:
            return await import_contacts_csv_mapped_content(
                db,
                filename=filename,
                content=content,
                team_id=team_id,
                actor_id=actor_id,
                column_map=column_map,
            )
        return await _run_import_from_content(
            db,
            filename=filename,
            content=content,
            definition=CONTACTS_CSV,
            team_id=team_id,
            actor_id=actor_id,
            existing_values=await _load_existing_values(db, Contact, "email", team_id=team_id),
            row_builder=_build_contact_payload,
            row_creator=lambda payload: Contact(team_id=team_id, **payload.model_dump()),
        )
    if entity == "accounts":
        return await _run_import_from_content(
            db,
            filename=filename,
            content=content,
            definition=ACCOUNTS_CSV,
            team_id=team_id,
            actor_id=actor_id,
            existing_values=await _load_existing_values(db, Account, "name", team_id=team_id),
            row_builder=_build_account_payload,
            row_creator=lambda payload: Account(team_id=team_id, **payload.model_dump()),
        )
    if entity == "products":
        return await _run_import_from_content(
            db,
            filename=filename,
            content=content,
            definition=PRODUCTS_CSV,
            team_id=team_id,
            actor_id=actor_id,
            existing_values=await _load_existing_values(db, Product, "sku", team_id=team_id),
            row_builder=_build_product_payload,
            row_creator=lambda payload: Product(team_id=team_id, **payload.model_dump()),
        )
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported import entity '{entity}'.")


async def bulk_delete_contacts(
    db: AsyncSession,
    payload: BulkDeleteRequest,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> BulkOperationResponse:
    return await _bulk_delete(
        db,
        model=Contact,
        ids=payload.ids,
        team_id=team_id,
        actor_id=actor_id,
        entity_type="contact",
    )


async def bulk_delete_products(
    db: AsyncSession,
    payload: BulkDeleteRequest,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> BulkOperationResponse:
    rows = list(
        (
            await db.execute(
                select(Product.id).where(Product.team_id == team_id, Product.id.in_(payload.ids))
            )
        ).scalars()
    )
    if not rows:
        return BulkOperationResponse(processed=0, skipped=len(payload.ids))

    referenced_ids = set(
        (
            await db.execute(
                select(DealLineItem.product_id).where(
                    DealLineItem.team_id == team_id,
                    DealLineItem.product_id.in_(rows),
                )
            )
        ).scalars()
    )
    deletable_ids = [row for row in rows if row not in referenced_ids]
    if deletable_ids:
        await db.execute(delete(Product).where(Product.team_id == team_id, Product.id.in_(deletable_ids)))
    await log_audit(
        db,
        action="bulk.updated",
        entity_type="product",
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={
            "operation": "bulk_delete",
            "processed_ids": [str(item) for item in deletable_ids],
            "skipped_ids": [str(item) for item in referenced_ids],
        },
    )
    await db.commit()
    return BulkOperationResponse(
        processed=len(deletable_ids),
        skipped=max(len(payload.ids) - len(deletable_ids), 0),
    )


async def bulk_update_deal_stage(
    db: AsyncSession,
    payload: BulkDealStageUpdateRequest,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> BulkOperationResponse:
    stage = await db.get(DealStage, payload.stage_id)
    if stage is None or stage.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stage not found.")

    deals = list(
        (
            await db.execute(
                select(Deal).where(Deal.team_id == team_id, Deal.id.in_(payload.ids))
            )
        ).scalars()
    )

    for deal in deals:
        deal.stage_id = payload.stage_id

    if deals:
        await log_audit(
            db,
            action="bulk.updated",
            entity_type="deal",
            actor_type="user",
            team_id=team_id,
            actor_id=actor_id,
            metadata={
                "operation": "bulk_stage",
                "stage_id": str(payload.stage_id),
                "processed_ids": [str(deal.id) for deal in deals],
            },
        )
        await db.commit()

    return BulkOperationResponse(processed=len(deals), skipped=max(len(payload.ids) - len(deals), 0))


async def _bulk_delete(
    db: AsyncSession,
    *,
    model: type[Any],
    ids: list[UUID],
    team_id: UUID,
    actor_id: str | None,
    entity_type: str,
) -> BulkOperationResponse:
    rows = list(
        (
            await db.execute(
                select(model.id).where(model.team_id == team_id, model.id.in_(ids))
            )
        ).scalars()
    )
    if not rows:
        return BulkOperationResponse(processed=0, skipped=len(ids))

    await db.execute(delete(model).where(model.team_id == team_id, model.id.in_(rows)))
    await log_audit(
        db,
        action="bulk.updated",
        entity_type=entity_type,
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"operation": "bulk_delete", "processed_ids": [str(item) for item in rows]},
    )
    await db.commit()
    return BulkOperationResponse(processed=len(rows), skipped=max(len(ids) - len(rows), 0))


async def _run_import_from_content(
    db: AsyncSession,
    *,
    filename: str,
    content: bytes,
    definition: CsvDefinition,
    team_id: UUID,
    actor_id: str | None,
    existing_values: set[str],
    row_builder: Callable[[dict[str, str]], Any],
    row_creator: Callable[[Any], Any],
) -> ImportResultResponse:
    await log_audit(
        db,
        action="import.started",
        entity_type=definition.entity,
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"filename": filename or f"{definition.entity}.csv"},
    )
    await db.commit()

    rows = _read_csv_rows_from_bytes(content, expected_headers=definition.headers)
    seen_values = set(existing_values)
    created = 0
    skipped = 0
    errors: list[ImportRowError] = []

    for row_number, row in rows:
        key = row.get(definition.duplicate_field, "").strip().lower()
        if key and key in seen_values:
            skipped += 1
            errors.append(
                ImportRowError(
                    row_number=row_number,
                    message=f"Duplicate {definition.duplicate_field} detected.",
                    row=row,
                )
            )
            continue

        try:
            payload = row_builder(row)
            model = row_creator(payload)
            db.add(model)
            await db.commit()
            created += 1
            if key:
                seen_values.add(key)
        except Exception as exc:
            await db.rollback()
            errors.append(
                ImportRowError(
                    row_number=row_number,
                    message=str(exc),
                    row=row,
                )
            )

    result = ImportResultResponse(
        entity=definition.entity,
        created=created,
        skipped=skipped,
        failed=len(errors) - skipped,
        errors=errors,
    )
    await log_audit(
        db,
        action="import.completed",
        entity_type=definition.entity,
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={
            "created": result.created,
            "skipped": result.skipped,
            "failed": result.failed,
        },
    )
    await db.commit()
    return result


async def _load_existing_values(
    db: AsyncSession,
    model: type[Any],
    field_name: str,
    *,
    team_id: UUID,
) -> set[str]:
    field = getattr(model, field_name)
    result = await db.execute(select(field).where(model.team_id == team_id))
    return {str(value).strip().lower() for value in result.scalars().all() if value}


def _read_csv_rows_from_bytes(raw: bytes, *, expected_headers: list[str]) -> list[tuple[int, dict[str, str]]]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV file must be UTF-8 encoded.") from exc

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV file is missing headers.")
    validate_headers(reader.fieldnames, expected_headers)

    return [(index, {key: (value or "").strip() for key, value in row.items()}) for index, row in enumerate(reader, start=2)]


def validate_headers(file_headers: list[str] | None, expected_headers: list[str]) -> None:
    normalized = [header.strip() for header in (file_headers or [])]
    if normalized != expected_headers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid CSV headers. Expected: {', '.join(expected_headers)}",
        )


def _write_csv(headers: list[str], rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _build_contact_payload(row: dict[str, str]) -> ContactCreate:
    return ContactCreate(
        first_name=row["first_name"],
        last_name=row["last_name"],
        email=row["email"],
        phone=row["phone"] or None,
        consent_sms=_parse_bool(row["consent_sms"]),
        consent_email=_parse_bool(row["consent_email"]),
    )


def _build_account_payload(row: dict[str, str]) -> AccountCreate:
    return AccountCreate(
        name=row["name"],
        domain=row["domain"] or None,
        industry=row["industry"] or None,
    )


def _build_product_payload(row: dict[str, str]) -> ProductCreate:
    return ProductCreate(
        name=row["name"],
        sku=row["sku"],
        description=row["description"] or None,
        price=Decimal(row["price"]),
        currency=row["currency"] or "USD",
        custom_fields={},
    )


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


# ── V1 Mapped Import ───────────────────────────────────────────────────────


async def preview_csv(file: UploadFile) -> dict:
    """Read CSV and return detected headers + first 5 data rows."""
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file must be UTF-8 encoded.",
        ) from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is missing headers.",
        )

    headers = list(reader.fieldnames)
    preview_rows: list[dict[str, str]] = []
    for _i, row in enumerate(reader):
        if _i >= 5:
            break
        preview_rows.append({k: (v or "").strip() for k, v in row.items()})

    return {"headers": headers, "preview": preview_rows}


async def import_contacts_csv_mapped(
    db: AsyncSession,
    file: UploadFile,
    *,
    team_id: UUID,
    actor_id: str | None = None,
    column_map: dict[str, str],
) -> ImportResultResponse:
    """Import contacts from any CSV using a caller-supplied column mapping.

    ``column_map`` maps CRM field → CSV header name, e.g.::

        {"name": "Full Name", "email": "Work Email", "phone": "Mobile"}

    Supported CRM fields: name, first_name, last_name, email, phone, account.
    ``name`` is split on the first space into first_name / last_name.
    If email already exists in the team → skip (duplicate).
    """
    raw = await file.read()
    return await import_contacts_csv_mapped_content(
        db,
        filename=file.filename or "contacts.csv",
        content=raw,
        team_id=team_id,
        actor_id=actor_id,
        column_map=column_map,
    )


async def import_contacts_csv_mapped_content(
    db: AsyncSession,
    *,
    filename: str,
    content: bytes,
    team_id: UUID,
    actor_id: str | None = None,
    column_map: dict[str, str],
) -> ImportResultResponse:
    """Import contacts with flexible column mapping from raw bytes."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file must be UTF-8 encoded.",
        ) from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is missing headers.",
        )

    await log_audit(
        db,
        action="import.started",
        entity_type="contacts",
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"filename": filename or "contacts.csv", "mapped": True},
    )
    await db.commit()

    # Pre-load existing emails for duplicate detection
    existing_emails: set[str] = await _load_existing_values(db, Contact, "email", team_id=team_id)
    seen_emails = set(existing_emails)

    # Reverse map: csv_header → crm_field
    header_to_field: dict[str, str] = {v: k for k, v in column_map.items() if v}

    created = 0
    skipped = 0
    errors: list[ImportRowError] = []

    for row_idx, row in enumerate(reader, start=2):
        # Apply mapping: build a crm-field keyed dict
        mapped: dict[str, str] = {}
        for csv_col, crm_field in header_to_field.items():
            mapped[crm_field] = (row.get(csv_col) or "").strip()

        # Split "name" → first_name / last_name
        if "name" in mapped and mapped["name"]:
            parts = mapped["name"].split(" ", 1)
            mapped.setdefault("first_name", parts[0])
            mapped.setdefault("last_name", parts[1] if len(parts) > 1 else "")

        # Email is the duplicate key
        email = mapped.get("email", "").strip().lower()
        if email and email in seen_emails:
            skipped += 1
            errors.append(
                ImportRowError(
                    row_number=row_idx,
                    message="Duplicate email — skipped.",
                    row=dict(row),
                )
            )
            continue

        try:
            contact = Contact(
                team_id=team_id,
                first_name=mapped.get("first_name") or "Unknown",
                last_name=mapped.get("last_name") or "",
                email=mapped.get("email") or None,
                phone=mapped.get("phone") or None,
                consent_email=True,
                consent_sms=False,
            )
            db.add(contact)
            await db.flush()
            await db.commit()
            created += 1
            if email:
                seen_emails.add(email)
        except Exception as exc:
            await db.rollback()
            errors.append(
                ImportRowError(row_number=row_idx, message=str(exc), row=dict(row))
            )

    result = ImportResultResponse(
        entity="contacts",
        created=created,
        skipped=skipped,
        failed=len(errors) - skipped,
        errors=errors,
    )
    await log_audit(
        db,
        action="import.completed",
        entity_type="contacts",
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"created": created, "skipped": skipped, "failed": result.failed},
    )
    await db.commit()
    return result
