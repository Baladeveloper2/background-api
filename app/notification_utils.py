from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import Any, Optional, List
from datetime import datetime, timezone
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

        msg_payload = {
            "type": "NEW_NOTIFICATION",
            "data": {
                "id": notif.id,
                "title": notif.title,
                "message": notif.message,
                "category": category.value if hasattr(category, 'value') else category,
                "case_id": case_id,
                "case_ref": "", # Remove invalid attribute access
                "extra_data": extra_data,
                "is_read": 0,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        }

        # Real-time WebSocket Broadcast (Direct to User)
        try:
            if background_tasks:
                background_tasks.add_task(manager.send_personal_message, str(user_id), msg_payload)
                logger.info(f"WebSocket broadcast deferred to BackgroundTasks for user_id={user_id}")
            else:
                # Fallback for sync/legacy routes
                import asyncio
                asyncio.create_task(manager.send_personal_message(str(user_id), msg_payload))
                logger.info(f"WebSocket broadcast task scheduled (Immediate) for user_id={user_id}")
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

async def notify_new_assignment(db: AsyncSession, user_id: str, case_ref: str, case_id: str, candidate_name: str, background_tasks: Optional[Any] = None):
    """Triggered when Super Admin assigns a case to a verifier."""
    await create_notification(
        db, user_id, 
        "New Case Assigned", 
        f"Case {case_ref} for {candidate_name} has been assigned to your queue for verification.",
        enums.NotificationCategory.CASE_ASSIGNED,
        case_id=case_id,
        background_tasks=background_tasks
    )

async def notify_allocation_to_admin(db: AsyncSession, admin_id: str, verifier_name: str, case_ref: str, case_id: str, candidate_name: str, background_tasks: Optional[Any] = None):
    """Notify the admin that an allocation they initiated was successful."""
    await create_notification(
        db, admin_id,
        "Allocation Confirmed",
        f"Protocol {case_ref} ({candidate_name}) successfully deployed to {verifier_name}.",
        enums.NotificationCategory.SYSTEM_ALERT,
        case_id=case_id,
        background_tasks=background_tasks
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

async def notify_at_risk(db: AsyncSession, user_id: str, case_ref: str, case_id: str, tat_days: int, background_tasks: Optional[Any] = None):
    """Triggered when a case crosses the 70% TAT risk threshold."""
    await create_notification(
        db, user_id,
        "⚠️ SLA Risk Alert",
        f"Critical Update: Case {case_ref} is now 'AT RISK'. Current timeline exceeds 70% of the {tat_days}-day protocol. Immediate action required.",
        enums.NotificationCategory.INSUFFICIENT_DOCS, # Reusing critical icon
        case_id=case_id,
        background_tasks=background_tasks
    )

async def notify_ping(db: AsyncSession, user_id: str, case_ref: str, case_id: str, manager_name: str, background_tasks: Optional[Any] = None):
    """Manual ping from a manager to a verifier."""
    await create_notification(
        db, user_id,
        "🚨 URGENT PING",
        f"Manager {manager_name} is requesting an immediate status update on Case {case_ref}. Prioritize this mission.",
        enums.NotificationCategory.URGENT_PING,
        case_id=case_id,
        background_tasks=background_tasks
    )

from . import email_utils

async def notify_documents_submitted(
    db: AsyncSession,
    case_id: str,
    case_ref: str,
    candidate_name: str,
    customer_users: List[models.User] = [],
    background_tasks: Optional[Any] = None
):
    """
    Fired when a candidate submits their BGV form documents.
    Notifies:
      - The client (customer users) who owns the case
      - All internal SUPER_ADMIN / MANAGER / ADMIN users
    """
    title = "📋 Documents Submitted"
    message = f"Candidate {candidate_name} has submitted all required documents for Case {case_ref}. Please review and proceed with verification."

    # 1. Notify the client contacts
    for user in customer_users:
        try:
            await create_notification(
                db, user.id, title, message,
                enums.NotificationCategory.FORM_SUBMITTED,
                case_id=case_id,
                background_tasks=background_tasks
            )
            
            # Send Email to Customer
            if user.email:
                if background_tasks:
                    background_tasks.add_task(email_utils.send_submission_notification_email, user.email, candidate_name, case_ref)
                else:
                    await email_utils.send_submission_notification_email(user.email, candidate_name, case_ref)
        except Exception as e:
            logger.error(f"Failed to notify customer user {user.id}: {str(e)}")

    # 2. Notify internal team (Super Admins + Managers + Admins)
    try:
        internal_users = await get_users_by_role(
            db, [enums.UserRole.SUPER_ADMIN, enums.UserRole.ADMIN, enums.UserRole.MANAGER]
        )
        logger.info(f"Notify Internal Team: found {len(internal_users)} stakeholders")
        for user in internal_users:
            try:
                await create_notification(
                    db, user.id, title, message,
                    enums.NotificationCategory.FORM_SUBMITTED,
                    case_id=case_id,
                    background_tasks=background_tasks
                )
                
                # Send Email to Internal User
                if user.email:
                    if background_tasks:
                        background_tasks.add_task(email_utils.send_submission_notification_email, user.email, candidate_name, case_ref)
                    else:
                        await email_utils.send_submission_notification_email(user.email, candidate_name, case_ref)
            except Exception as e:
                logger.error(f"Failed to notify internal user {user.id}: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to fetch internal users for notification: {str(e)}")

async def notify_client_document_uploaded(
    db: AsyncSession,
    document_name: str,
    customer_id: str,
    customer_name: str,
    background_tasks: Optional[Any] = None
):
    """Notify super admins and admins that a client uploaded a new document to their vault."""
    internal_users = await get_users_by_role(
        db, [enums.UserRole.SUPER_ADMIN, enums.UserRole.ADMIN, enums.UserRole.MANAGER]
    )
    for user in internal_users:
        await create_notification(
            db, user.id,
            "Client Vault Upload",
            f"Client {customer_name} has uploaded a new document: {document_name}. Check the Client Vault.",
            enums.NotificationCategory.SYSTEM_ALERT,
            background_tasks=background_tasks
        )

async def notify_insufficiency_raised(
    db: AsyncSession,
    case_id: str,
    case_ref: str,
    candidate_name: str,
    check_id: str,
    check_name: str,
    raised_by_name: str,
    raised_by_role: str,
    message: str,
    customer_user_ids: List[str] = [],
    background_tasks: Optional[Any] = None
):
    """
    Triggered when an insufficiency is raised at the check level.
    Notifies:
      - Super Admin
      - Customer Users
    """
    title = f"❗ Insufficiency Raised: {check_name}"
    content = (
        f"Case: {case_ref} | Candidate: {candidate_name}\n"
        f"Check: {check_name}\n"
        f"Raised By: {raised_by_name} ({raised_by_role})\n"
        f"Reason: {message}"
    )
    
    extra_data = {
        "check_id": check_id,
        "check_name": check_name,
        "raised_by": raised_by_name,
        "raised_by_role": raised_by_role,
        "reason": message
    }

    # 1. Notify Super Admins
    try:
        super_admins = await get_users_by_role(db, [enums.UserRole.SUPER_ADMIN])
        for admin in super_admins:
            await create_notification(
                db, admin.id, title, content,
                enums.NotificationCategory.INSUFFICIENT_DOCS,
                case_id=case_id,
                extra_data=extra_data,
                background_tasks=background_tasks
            )
    except Exception as e:
        logger.error(f"Failed to notify admins of insufficiency: {str(e)}")

    # 2. Notify Customer Users
    for user_id in customer_user_ids:
        try:
            await create_notification(
                db, user_id, title, content,
                enums.NotificationCategory.INSUFFICIENT_DOCS,
                case_id=case_id,
                extra_data=extra_data,
                background_tasks=background_tasks
            )
        except Exception as e:
            logger.error(f"Failed to notify customer user {user_id} of insufficiency: {str(e)}")
async def notify_insufficiency_resolved(
    db: AsyncSession,
    insuff_id: str,
    background_tasks: Optional[Any] = None
):
    """
    Triggered when a candidate or client uploads documents for an insufficiency.
    Notifies:
      - Assigned Verifier (if any)
      - Super Admin
    """
    try:
        # Fetch insufficiency with related info
        stmt = select(models.Insufficiency).options(
            joinedload(models.Insufficiency.case).joinedload(models.Case.candidate),
            joinedload(models.Insufficiency.check)
        ).filter(models.Insufficiency.id == insuff_id)
        
        res = await db.execute(stmt)
        insuff = res.scalar_one_or_none()
        
        if not insuff:
            return

        case = insuff.case
        candidate_name = case.candidate.name if case.candidate else "N/A"
        check_name = insuff.check.check_type if insuff.check else "General"
        
        title = f"✅ Insufficiency Resolved: {candidate_name}"
        content = (
            f"Evidence submitted for check: {check_name}\n"
            f"Candidate: {candidate_name} | Case: {case.case_ref_no or case.id}\n"
            f"Status updated to: {insuff.status}"
        )
        
        # 1. Notify Super Admins
        super_admins = await get_users_by_role(db, [enums.UserRole.SUPER_ADMIN])
        for admin in super_admins:
            await create_notification(
                db, admin.id, title, content,
                enums.NotificationCategory.INSUFFICIENT_DOCS,
                case_id=case.id,
                background_tasks=background_tasks
            )
            
        # 2. Notify Assigned Verifier
        if case.assigned_to:
            await create_notification(
                db, case.assigned_to, title, content,
                enums.NotificationCategory.INSUFFICIENT_DOCS,
                case_id=case.id,
                background_tasks=background_tasks
            )

    except Exception as e:
        logger.error(f"Error in notify_insufficiency_resolved: {str(e)}")
