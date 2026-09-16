"""Product catalog routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthContext, get_auth_context
from app.core.db import get_db
from app.schemas.crm import BulkDeleteRequest, BulkOperationResponse, ProductCreate, ProductRead, ProductUpdate
from app.services.import_export import bulk_delete_products
from app.services.products import create_product, delete_product, list_products, update_product


router = APIRouter(tags=["products"])


@router.get("/products", response_model=list[ProductRead])
async def get_products(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[ProductRead]:
    """Return the team's products."""
    return await list_products(db, team_id=auth.team_id)


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def post_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> ProductRead:
    """Create a product."""
    return await create_product(db, payload, team_id=auth.team_id, actor_id=auth.user_id)


@router.patch("/products/{product_id}", response_model=ProductRead)
async def patch_product(
    product_id: UUID,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> ProductRead:
    """Update a product."""
    return await update_product(
        db,
        product_id,
        payload,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def remove_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> Response:
    """Delete a product."""
    await delete_product(db, product_id, team_id=auth.team_id, actor_id=auth.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/products/bulk-delete", response_model=BulkOperationResponse)
async def post_bulk_delete_products(
    payload: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> BulkOperationResponse:
    """Delete multiple products for the active team."""
    return await bulk_delete_products(
        db,
        payload,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )
