from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import authenticate_request as get_current_user
from app.models.auth import AuthenticatedUser
from app.services.cache import get_revenue_summary
from app.services.reservations import (
    PropertyNotFound,
    RevenueServiceUnavailable,
    get_tenant_properties,
)

router = APIRouter()


def _get_tenant_id(current_user: AuthenticatedUser) -> str:
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant access is required")
    return current_user.tenant_id


@router.get("/dashboard/properties")
async def get_dashboard_properties(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[Dict[str, str]]:
    tenant_id = _get_tenant_id(current_user)

    try:
        return await get_tenant_properties(tenant_id)
    except RevenueServiceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Property data is temporarily unavailable",
        ) from error


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = _get_tenant_id(current_user)

    try:
        revenue_data = await get_revenue_summary(
            property_id,
            tenant_id,
            month,
            year,
        )
    except PropertyNotFound as error:
        raise HTTPException(status_code=404, detail="Property not found") from error
    except RevenueServiceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Revenue data is temporarily unavailable",
        ) from error

    return {
        "property_id": revenue_data["property_id"],
        "year": revenue_data["year"],
        "month": revenue_data["month"],
        "total_revenue": revenue_data["total"],
        "currency": revenue_data["currency"],
        "reservations_count": revenue_data["count"],
    }
