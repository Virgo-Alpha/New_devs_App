import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text

from app.core.database_pool import db_pool

logger = logging.getLogger(__name__)


class RevenueServiceUnavailable(Exception):
    """Raised when revenue cannot be read from the database."""


class PropertyNotFound(Exception):
    """Raised when a property does not belong to the authenticated tenant."""


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _format_currency(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


async def calculate_monthly_revenue(
    property_id: str,
    tenant_id: str,
    month: int,
    year: int,
) -> Dict[str, Any]:
    """Calculate a property's revenue for one local calendar month."""
    if not db_pool.session_factory:
        raise RevenueServiceUnavailable("Revenue database is unavailable")

    property_query = text("""
        SELECT timezone
        FROM properties
        WHERE id = :property_id AND tenant_id = :tenant_id
    """)

    try:
        async with db_pool.get_session() as session:
            property_result = await session.execute(property_query, {
                "property_id": property_id,
                "tenant_id": tenant_id,
            })
            property_row = property_result.fetchone()

            if not property_row:
                raise PropertyNotFound(property_id)

            try:
                property_timezone = ZoneInfo(property_row.timezone)
            except ZoneInfoNotFoundError as error:
                logger.exception(
                    "Invalid timezone %s for property %s and tenant %s",
                    property_row.timezone,
                    property_id,
                    tenant_id,
                )
                raise RevenueServiceUnavailable(
                    "Property timezone is invalid"
                ) from error

            next_year, next_month = _next_month(year, month)
            local_start = datetime(year, month, 1, tzinfo=property_timezone)
            local_end = datetime(
                next_year,
                next_month,
                1,
                tzinfo=property_timezone,
            )
            utc_start = local_start.astimezone(timezone.utc)
            utc_end = local_end.astimezone(timezone.utc)

            revenue_query = text("""
                SELECT
                    COALESCE(SUM(total_amount), 0) AS total_revenue,
                    COUNT(*) AS reservation_count,
                    COALESCE(MIN(currency), 'USD') AS currency
                FROM reservations
                WHERE property_id = :property_id
                  AND tenant_id = :tenant_id
                  AND check_in_date >= :utc_start
                  AND check_in_date < :utc_end
            """)
            result = await session.execute(revenue_query, {
                "property_id": property_id,
                "tenant_id": tenant_id,
                "utc_start": utc_start,
                "utc_end": utc_end,
            })
            row = result.fetchone()
    except (PropertyNotFound, RevenueServiceUnavailable):
        raise
    except Exception as error:
        logger.exception(
            "Revenue database query failed for property %s and tenant %s",
            property_id,
            tenant_id,
        )
        raise RevenueServiceUnavailable(
            "Revenue database is unavailable"
        ) from error

    total_revenue = Decimal(str(row.total_revenue))
    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "year": year,
        "month": month,
        "total": _format_currency(total_revenue),
        "currency": row.currency,
        "count": row.reservation_count,
    }


async def get_tenant_properties(tenant_id: str) -> List[Dict[str, str]]:
    """Return only properties owned by the authenticated tenant."""
    if not db_pool.session_factory:
        raise RevenueServiceUnavailable("Revenue database is unavailable")

    query = text("""
        SELECT id, name, timezone
        FROM properties
        WHERE tenant_id = :tenant_id
        ORDER BY name
    """)

    try:
        async with db_pool.get_session() as session:
            result = await session.execute(query, {"tenant_id": tenant_id})
            rows = result.fetchall()
    except Exception as error:
        logger.exception(
            "Property database query failed for tenant %s",
            tenant_id,
        )
        raise RevenueServiceUnavailable(
            "Property database is unavailable"
        ) from error

    return [
        {
            "id": row.id,
            "name": row.name,
            "timezone": row.timezone,
        }
        for row in rows
    ]
