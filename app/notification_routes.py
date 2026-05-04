from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from typing import List
from . import models, schemas, database, auth_routes

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("", response_model=list[schemas.NotificationRead])
async def get_notifications(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(database.get_async_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    """Fetch notifications for the current user with pagination."""

    stmt = (
        select(
            models.Notification,
            models.Case.case_ref_no,
            models.Case.status.label("case_status"),
            models.Candidate.name.label("case_name")
        )
        .outerjoin(models.Case, models.Notification.case_id == models.Case.id)
        .outerjoin(models.Candidate, models.Case.candidate_id == models.Candidate.id)
        .filter(models.Notification.user_id == current_user.id)
        .order_by(desc(models.Notification.created_at))
        .offset(skip)
        .limit(limit)
    )
    res = await db.execute(stmt)
    
    results = []
    for row in res:
        n = row.Notification
        results.append({
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "category": n.category,
            "channel": n.channel,
            "is_read": n.is_read,
            "case_id": n.case_id,
            "case_name": row.case_name,
            "case_ref": row.case_ref_no,
            "case_status": row.case_status,
            "extra_data": n.extra_data,
            "created_at": n.created_at
        })
    return results

@router.get("/{notification_id}", response_model=schemas.NotificationRead)
async def get_notification(
    notification_id: str,
    db: AsyncSession = Depends(database.get_async_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    """Fetch a single notification with full details."""
    stmt = (
        select(
            models.Notification,
            models.Case.case_ref_no,
            models.Case.status.label("case_status"),
            models.Candidate.name.label("case_name")
        )
        .outerjoin(models.Case, models.Notification.case_id == models.Case.id)
        .outerjoin(models.Candidate, models.Case.candidate_id == models.Candidate.id)
        .filter(models.Notification.id == notification_id)
        .filter(models.Notification.user_id == current_user.id)
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    n = row.Notification
    return {
        "id": n.id,
        "title": n.title,
        "message": n.message,
        "category": n.category,
        "channel": n.channel,
        "is_read": n.is_read,
        "case_id": n.case_id,
        "case_name": row.case_name,
        "case_ref": row.case_ref_no,
        "case_status": row.case_status,
        "extra_data": n.extra_data,
        "created_at": n.created_at
    }

@router.patch("/mark-read")
async def mark_notifications_read(
    payload: schemas.NotificationMarkRead,
    db: AsyncSession = Depends(database.get_async_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    """Mark a list of notifications as read."""
    stmt = (
        update(models.Notification)
        .where(models.Notification.id.in_(payload.notification_ids))
        .where(models.Notification.user_id == current_user.id)
        .values(is_read=1)
    )
    await db.execute(stmt)
    await db.commit()
    return {"status": "success"}
