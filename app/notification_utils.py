from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any, Optional
from datetime import datetime
from . import models, enums
from .ws import manager
import logging
import json

logger = logging.getLogger(__name__)

async def create_notification(
    db: AsyncSession,
    user_id: str,
    title: str,
    message: str,
    category: enums.NotificationCategory,
    channel: enums.NotificationChannel = enums.NotificationChannel.SYSTEM,
    case_id: Optional[str] = None,
    extra_data: Optional[dict[str, Any]] = None,
    background_tasks: Optional[Any] = None
):
    """
    Creates a notification record. COMMITTING IS DEFERRED to the caller.
    """
    try:
        notif = models.Notification(
            user_id=user_id,
            title=title,
            message=message,
            category=category,
            channel=channel,
            case_id=case_id,
            extra_data=extra_data
        )
        db.add(notif)
        await db.flush() # Get the ID for the WebSocket message
        
        logger.info(f"Notification created in DB: id={notif.id} for user_id={user_id}")

        # Real-time WebSocket Broadcast (Direct to User)
        try:
            # We don't await this to keep the API response snappy
            import asyncio
            asyncio.create_task(manager.send_personal_message(str(user_id), {
                "type": "NEW_NOTIFICATION",
                "data": {
                    "id": notif.id,
                    "title": notif.title,
                    "message": notif.message,
                    "category": category.value if hasattr(category, 'value') else category,
                    "case_id": case_id,
                    "extra_data": extra_data,
                    "created_at": datetime.utcnow().isoformat()
                }
            }))
            logger.info(f"WebSocket broadcast task scheduled for user_id={user_id}")
        except Exception as ws_err:
            logger.error(f"WebSocket notification push failed: {str(ws_err)}")

        return notif
    except Exception as e:
        logger.error(f"Failed to create notification: {str(e)}")
        return None

# --- Specialized Stakeholder Alerting ---

async def get_users_by_role(db: AsyncSession, roles: list[enums.UserRole]):
    """Helper to fetch all users with given roles."""
    stmt = select(models.User).filter(models.User.role.in_(roles), models.User.status == "ACTIVE")
    res = await db.execute(stmt)
    return res.scalars().all()

async def notify_new_assignment(db: AsyncSession, user_id: str, case_ref: str, case_id: str, candidate_name: str):
    """Triggered when Super Admin assigns a case to a verifier."""
    await create_notification(
        db, user_id, 
        "New Case Assigned", 
        f"Case {case_ref} for {candidate_name} has been assigned to your queue for verification.",
        enums.NotificationCategory.CASE_ASSIGNED,
        case_id=case_id
    )

async def notify_allocation_to_admin(db: AsyncSession, admin_id: str, verifier_name: str, case_ref: str, case_id: str, candidate_name: str):
    """Notify the admin that an allocation they initiated was successful."""
    await create_notification(
        db, admin_id,
        "Allocation Confirmed",
        f"Protocol {case_ref} ({candidate_name}) successfully deployed to {verifier_name}.",
        enums.NotificationCategory.SYSTEM_ALERT,
        case_id=case_id
    )

async def notify_verification_completed(db: AsyncSession, case_id: str, case_ref: str, candidate_name: str, verifier_name: str):
    """Triggered when Verifier moves case to QC."""
    # Notify QC Verifiers and Super Admins
    recipients = await get_users_by_role(db, [enums.UserRole.QC, enums.UserRole.SUPER_ADMIN])
    for user in recipients:
        await create_notification(
            db, user.id,
            "Verification Completed - Action Required",
            f"Verifier {verifier_name} has completed verification for {case_ref} ({candidate_name}). Case has been moved to QC queue.",
            enums.NotificationCategory.QC_REPORT_READY,
            case_id=case_id
        )

async def notify_qc_completed(db: AsyncSession, case_id: str, case_ref: str, candidate_name: str, qc_name: str):
    """Triggered when QC Verifier completes quality check."""
    # Notify Super Admins
    recipients = await get_users_by_role(db, [enums.UserRole.SUPER_ADMIN])
    for user in recipients:
        await create_notification(
            db, user.id,
            "QC Finalized",
            f"QC Verifier {qc_name} has completed the quality check for Case {case_ref} ({candidate_name}).",
            enums.NotificationCategory.QA_REPORT_READY,
            case_id=case_id
        )

async def notify_case_closed(db: AsyncSession, case_id: str, case_ref: str, candidate_name: str):
    """Final notification when case status becomes COMPLETED/DISPATCHED."""
    # Notify Super Admins
    recipients = await get_users_by_role(db, [enums.UserRole.SUPER_ADMIN])
    for user in recipients:
        await create_notification(
            db, user.id,
            "Case Successfully Closed",
            f"Identity verification for Case {case_ref} ({candidate_name}) is now fully complete and the final report has been dispatched.",
            enums.NotificationCategory.CASE_COMPLETED,
            case_id=case_id
        )

# --- Legacy/Generic Helpers ---

async def notify_insufficient(db: AsyncSession, user_id: str, case_ref: str, case_id: str):
    await create_notification(
        db, user_id,
        "Insufficient Documents",
        f"Case {case_ref} requires additional documents for verification.",
        enums.NotificationCategory.INSUFFICIENT_DOCS,
        case_id=case_id
    )

async def notify_form_submitted(db: AsyncSession, admin_ids: list, candidate_name: str, case_id: str):
    for admin_id in admin_ids:
        await create_notification(
            db, admin_id,
            "Form Submitted",
            f"Candidate {candidate_name} has submitted the verification form.",
            enums.NotificationCategory.FORM_SUBMITTED,
            case_id=case_id
        )
