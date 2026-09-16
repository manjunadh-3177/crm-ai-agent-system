"""Product catalog service layer."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models import Product, Team
from app.schemas.crm import ProductCreate, ProductUpdate
from app.services.audit import log_audit


DEMO_PRODUCTS: list[dict[str, str | Decimal | None]] = [
    {
        "name": "CRM Starter Plan",
        "sku": "CRM-STARTER",
        "description": "Core CRM workspace for managing contacts, deals, and approvals.",
        "price": Decimal("99.00"),
        "currency": "USD",
    },
    {
        "name": "AI Outreach Addon",
        "sku": "AI-OUTREACH",
        "description": "AI-assisted lead summaries and outreach draft generation.",
        "price": Decimal("149.00"),
        "currency": "USD",
    },
    {
        "name": "Sales Analytics Pro",
        "sku": "ANALYTICS-PRO",
        "description": "Forecasting, pipeline analytics, and manager insight tools.",
        "price": Decimal("199.00"),
        "currency": "USD",
    },
    {
        "name": "Proposal Suite",
        "sku": "PROPOSAL-SUITE",
        "description": "Proposal generation and document drafting for active deals.",
        "price": Decimal("129.00"),
        "currency": "USD",
    },
    {
        "name": "Enterprise Support Pack",
        "sku": "ENT-SUPPORT",
        "description": "Priority support and onboarding services for large teams.",
        "price": Decimal("299.00"),
        "currency": "USD",
    },
]


async def list_products(db: AsyncSession, *, team_id: UUID) -> list[Product]:
    """Return all products for the active team."""
    result = await db.execute(
        select(Product).where(Product.team_id == team_id).order_by(Product.created_at.desc())
    )
    return list(result.scalars().all())


async def get_product_or_404(db: AsyncSession, product_id: UUID, *, team_id: UUID) -> Product:
    """Load one team-scoped product."""
    product = await db.get(Product, product_id)
    if product is None or product.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return product


async def create_product(
    db: AsyncSession,
    payload: ProductCreate,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> Product:
    """Create a product."""
    team = await db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")

    product = Product(team_id=team_id, **payload.model_dump())
    db.add(product)
    await db.flush()
    await log_audit(
        db,
        action="product.created",
        entity_type="product",
        entity_id=str(product.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"sku": product.sku, "price": str(product.price)},
    )
    await db.commit()
    await db.refresh(product)
    return product


async def update_product(
    db: AsyncSession,
    product_id: UUID,
    payload: ProductUpdate,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> Product:
    """Update a team-scoped product."""
    product = await get_product_or_404(db, product_id, team_id=team_id)
    updated_fields = payload.model_dump(exclude_unset=True)
    for field, value in updated_fields.items():
        setattr(product, field, value)

    await log_audit(
        db,
        action="product.updated",
        entity_type="product",
        entity_id=str(product.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"updated_fields": sorted(updated_fields.keys())},
    )
    await db.commit()
    await db.refresh(product)
    return product


async def delete_product(
    db: AsyncSession,
    product_id: UUID,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> None:
    """Delete a product."""
    product = await get_product_or_404(db, product_id, team_id=team_id)
    await log_audit(
        db,
        action="product.deleted",
        entity_type="product",
        entity_id=str(product.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"sku": product.sku, "name": product.name},
    )
    await db.delete(product)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product cannot be deleted while it is still attached to deal line items.",
        ) from exc


async def seed_demo_products_if_empty(db: AsyncSession, *, team_id: UUID) -> list[Product]:
    """Ensure the demo workspace has sample products."""
    result = await db.execute(select(Product).where(Product.team_id == team_id))
    existing = list(result.scalars().all())
    if existing:
        return existing

    seeded: list[Product] = []
    for product_data in DEMO_PRODUCTS:
        product = Product(
            team_id=team_id,
            name=str(product_data["name"]),
            sku=str(product_data["sku"]),
            description=str(product_data["description"]) if product_data["description"] else None,
            price=product_data["price"],
            currency=str(product_data["currency"]),
            custom_fields={},
        )
        db.add(product)
        seeded.append(product)

    await db.commit()
    for product in seeded:
        await db.refresh(product)
    return seeded
