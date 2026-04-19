from sqlalchemy.ext.asyncio import AsyncSession
from . import models, enums
import logging

logger = logging.getLogger(__name__)

async def create_notification(
    db: AsyncSession,
    user_id: str,
    title: str,
    message: str,
    category: enums.NotificationCategory,
    channel: enums.NotificationChannel = enums.NotificationChannel.SYSTEM,
    case_id: str = None
):
    """
    Creates a notification in the database and optionally triggers external channels (Email/SMS).
    """
    try:
        # 1. Create System Notification (In-App)
        notif = models.Notification(
            user_id=user_id,
            title=title,
            message=message,
            category=category,
            channel=channel,
            case_id=case_id
        )
        db.add(notif)
        await db.commit()

        # 2. Trigger External Channels if not just SYSTEM
        if channel == enums.NotificationChannel.EMAIL:
            await send_mock_email(user_id, title, message)
        elif channel == enums.NotificationChannel.SMS:
            await send_mock_sms(user_id, message)
        
        return notif
    except Exception as e:
        logger.error(f"Failed to create notification: {str(e)}")
        return None

async def send_mock_email(user_id: str, title: str, message: str):
    """Placeholder for real SMTP logic."""
    logger.info(f"[EMAIL DISPATCH] To User {user_id} | Subject: {title} | Body: {message}")

async def send_mock_sms(user_id: str, message: str):
    """Placeholder for SMS Gateway (e.g. Twilio)."""
    logger.info(f"[SMS DISPATCH] To User {user_id} | Message: {message}")

# --- Tactical Helper Dispatchers ---

async def notify_new_assignment(db: AsyncSession, user_id: str, case_ref: str, case_id: str):
    await create_notification(
        db, user_id, 
        "New Case Assigned", 
        f"Case {case_ref} has been assigned to your queue.",
        enums.NotificationCategory.CASE_ASSIGNED,
        case_id=case_id
    )
    # Also send email for assignments
    await create_notification(
        db, user_id, 
        "Assignment Alert", 
        f"A new case {case_ref} is available for verification.",
        enums.NotificationCategory.CASE_ASSIGNED,
        channel=enums.NotificationChannel.EMAIL,
        case_id=case_id
    )

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

async def notify_case_completed(db: AsyncSession, owner_id: str, case_ref: str, case_id: str):
    await create_notification(
        db, owner_id,
        "Case Finalized",
        f"Investigation for Case {case_ref} is now complete.",
        enums.NotificationCategory.CASE_COMPLETED,
        case_id=case_id
    )
