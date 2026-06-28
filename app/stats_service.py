from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from . import models
from datetime import datetime, date
from .database import get_async_db_context

async def refresh_dashboard_summary(customer_id: str = None, summary_date: date = None):
    """Updates a single day's summary for a customer or globally."""
    if not summary_date:
        summary_date = date.today()
    
    async with get_async_db_context() as db:
    
    # 1. Calculate stats from Case table
    # Received today
    stmt_received = select(func.count(models.Case.id)).where(
        and_(
            func.date(models.Case.received_date) == summary_date,
            models.Case.customer_id == customer_id if customer_id else True
        )
    )
    res_received = await db.execute(stmt_received)
    received_count = res_received.scalar() or 0

    # Completed today
    stmt_completed = select(func.count(models.Case.id)).where(
        and_(
            func.date(models.Case.completed_date) == summary_date,
            models.Case.customer_id == customer_id if customer_id else True
        )
    )
    res_completed = await db.execute(stmt_completed)
    completed_count = res_completed.scalar() or 0

    # Total Pending (as of now)
    stmt_pending = select(func.count(models.Case.id)).where(
        and_(
            models.Case.status != "COMPLETED",
            models.Case.customer_id == customer_id if customer_id else True
        )
    )
    res_pending = await db.execute(stmt_pending)
    pending_count = res_pending.scalar() or 0

    # 2. Update or Create DashboardSummary record
    stmt_existing = select(models.DashboardSummary).where(
        and_(
            models.DashboardSummary.customer_id == customer_id,
            models.DashboardSummary.summary_date == summary_date
        )
    )
    res_existing = await db.execute(stmt_existing)
    summary = res_existing.scalar_one_or_none()

    if not summary:
        summary = models.DashboardSummary(
            customer_id=customer_id,
            summary_date=summary_date
        )
        db.add(summary)

    summary.total_received = received_count
    summary.total_completed = completed_count
    summary.total_pending = pending_count
    # Note: speed/risk can be added here if needed

    await db.commit()
