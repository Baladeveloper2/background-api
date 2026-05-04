from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from typing import List
from . import models, schemas, database, auth_routes

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("", response_model=List[schemas.NotificationRead])
async def get_notifications(
    skip: int = 0,
    limit: int = 50,
    type: str = "all", # "all", "unread"
    db: AsyncSession = Depends(database.get_async_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    """Fetch notifications for the current user with pagination and filtering."""

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
    )

    if type == "unread":
        stmt = stmt.filter(models.Notification.is_read == 0)

    stmt = stmt.order_by(desc(models.Notification.created_at)).offset(skip).limit(limit)
    res = await db.execute(stmt)
    
    results = []
    for row in res.all():
        n = row[0] # Notification object
        results.append({
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "category": n.category.value if hasattr(n.category, 'value') else n.category,
            "channel": n.channel.value if hasattr(n.channel, 'value') else n.channel,
            "is_read": n.is_read,
            "case_id": n.case_id,
            "case_name": row[3], # case_name label
            "case_ref": row[1],  # case_ref_no label
            "case_status": row[2], # case_status label
            "extra_data": n.extra_data,
            "created_at": n.created_at.isoformat() + ("Z" if n.created_at.tzinfo is None else "")
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
    
    n = row[0]
    return {
        "id": n.id,
        "title": n.title,
        "message": n.message,
        "category": n.category.value if hasattr(n.category, 'value') else n.category,
        "channel": n.channel.value if hasattr(n.channel, 'value') else n.channel,
        "is_read": n.is_read,
        "case_id": n.case_id,
        "case_name": row[3],
        "case_ref": row[1],
        "case_status": row[2],
        "extra_data": n.extra_data,
        "created_at": n.created_at.isoformat() + ("Z" if n.created_at.tzinfo is None else "")
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

@router.patch("/mark-all-read")
async def mark_all_notifications_read(
    db: AsyncSession = Depends(database.get_async_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    """Mark all notifications as read for the current user."""
    stmt = (
        update(models.Notification)
        .where(models.Notification.user_id == current_user.id)
        .where(models.Notification.is_read == 0)
        .values(is_read=1)
    )
    await db.execute(stmt)
    await db.commit()
    return {"status": "success"}

@router.patch("/{notification_id}/read")
async def mark_single_notification_read(
    notification_id: str,
    db: AsyncSession = Depends(database.get_async_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    """Mark a specific notification as read."""
    stmt = (
        update(models.Notification)
        .where(models.Notification.id == notification_id)
        .where(models.Notification.user_id == current_user.id)
        .values(is_read=1)
    )
    await db.execute(stmt)
    await db.commit()
    return {"status": "success"}
