from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from typing import List
from . import models, schemas, database, auth_routes

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("", response_model=List[schemas.NotificationRead])
async def get_notifications(
    db: AsyncSession = Depends(database.get_async_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    """Fetch unread/recent notifications for the current user."""
    stmt = (
        select(models.Notification)
        .filter(models.Notification.user_id == current_user.id)
        .order_by(desc(models.Notification.is_read), desc(models.Notification.created_at))
        .limit(50)
    )
    res = await db.execute(stmt)
    return res.scalars().all()

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
