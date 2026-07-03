from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from datetime import datetime
from typing import Optional

from .database import get_async_db, get_read_db
from . import models, schemas, enums, notification_utils
from .auth_routes import get_current_user

router = APIRouter()

@router.post("/insufficiencies/{id}/respond")
async def client_respond_insufficiency(
    id: str,
    data: schemas.ClientRespondInsufficiencyRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Client submits their response and documents for an insufficiency."""
    stmt = select(models.Insufficiency).filter(models.Insufficiency.id == id).options(joinedload(models.Insufficiency.case))
    res = await db.execute(stmt)
    insuff = res.scalar_one_or_none()
    
    if not insuff:
        raise HTTPException(status_code=404, detail="Insufficiency not found")
        
    if insuff.status not in ["PENDING", "NEED_MORE_INFO"]:
        raise HTTPException(status_code=400, detail="Cannot respond to this insufficiency at the current status")
        
    now = datetime.utcnow()
    insuff.status = "SUBMITTED_BY_CLIENT"
    insuff.case.status = enums.CaseStatus.SUBMITTED_BY_CLIENT
    insuff.response_at = now
    if data.documents:
        insuff.documents = data.documents
    insuff.updated_at = now
    insuff.updated_by = current_user.id
    
    existing_tl = insuff.timeline or []
    existing_tl.append({
        "event": "SUBMITTED",
        "title": "Documents Submitted",
        "description": data.remarks,
        "timestamp": now.isoformat(),
        "actor": current_user.full_name or current_user.email
    })
    insuff.timeline = existing_tl
    
    # Add a case comment for audit
    comment = models.CaseComment(
        case_id=insuff.case_id,
        user_id=current_user.id,
        content=f"Client responded to insufficiency: {data.remarks}"
    )
    db.add(comment)
    
    await db.commit()
    
    # Notify verifier, admin, allocator
    import asyncio
    asyncio.create_task(notification_utils.notify_insufficiency_resolved(db, insuff.id))

    return {"message": "Response submitted successfully"}

@router.get("/insufficiencies/review/queue")
async def get_insufficiency_review_queue(
    client_id: Optional[str] = None,
    candidate_id: Optional[str] = None,
    check_id: Optional[str] = None,
    priority: Optional[str] = None,
    verifier_id: Optional[str] = None,
    db: AsyncSession = Depends(get_read_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get the queue of insufficiencies waiting for review."""
    stmt = select(models.Insufficiency).filter(
        models.Insufficiency.status == "SUBMITTED_BY_CLIENT",
        models.Insufficiency.is_resolved == False
    ).options(
        joinedload(models.Insufficiency.case).joinedload(models.Case.candidate),
        joinedload(models.Insufficiency.check)
    )
    
    if client_id:
        stmt = stmt.join(models.Case).filter(models.Case.customer_id == client_id)
    if candidate_id:
        stmt = stmt.join(models.Case).filter(models.Case.candidate_id == candidate_id)
    if check_id:
        stmt = stmt.filter(models.Insufficiency.check_id == check_id)
    if priority:
        stmt = stmt.filter(models.Insufficiency.priority == priority)
    
    res = await db.execute(stmt)
    items = res.unique().scalars().all()
    
    results = []
    for i in items:
        results.append({
            "id": i.id,
            "case_id": i.case_id,
            "case_ref_no": i.case.case_ref_no if i.case else None,
            "candidate_name": i.case.candidate.full_name if i.case and i.case.candidate else None,
            "customer_id": i.case.customer_id if i.case else None,
            "check_name": i.check.check_type if i.check else None,
            "priority": i.priority,
            "due_date": i.due_date,
            "status": i.status,
            "message": i.message,
            "raised_by": i.raised_by,
            "created_at": i.created_at,
            "response_at": i.response_at
        })
        
    return results

@router.post("/insufficiencies/{id}/review")
async def verifier_review_insufficiency(
    id: str,
    data: schemas.VerifierReviewInsufficiencyRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Verifier approves, rejects, or requests more info on a submitted insufficiency."""
    stmt = select(models.Insufficiency).filter(models.Insufficiency.id == id).options(joinedload(models.Insufficiency.case), joinedload(models.Insufficiency.check))
    res = await db.execute(stmt)
    insuff = res.scalar_one_or_none()
    
    if not insuff:
        raise HTTPException(status_code=404, detail="Insufficiency not found")
        
    if insuff.status not in ["SUBMITTED_BY_CLIENT", "UNDER_REVIEW"]:
        raise HTTPException(status_code=400, detail="Insufficiency is not in SUBMITTED state")
        
    action = data.action.upper()
    now = datetime.utcnow()
    existing_tl = insuff.timeline or []
    
    if action == "MARK_UNDER_REVIEW":
        insuff.status = "UNDER_REVIEW"
        insuff.case.status = enums.CaseStatus.UNDER_REVIEW
        insuff.updated_at = now
        insuff.updated_by = current_user.id
        existing_tl.append({
            "event": "UNDER_REVIEW",
            "title": "Review Started",
            "description": "Verifier has started reviewing the response",
            "timestamp": now.isoformat(),
            "actor": current_user.full_name or current_user.email
        })
        insuff.timeline = existing_tl
        await db.commit()
        return {"message": "Insufficiency marked as under review"}

    if action == "APPROVE":
        insuff.status = "ACCEPTED"
        insuff.is_resolved = True
        insuff.resolved_at = now
        insuff.resolved_by = current_user.id
        insuff.resolved_remarks = data.remarks or "Documents Accepted"
        
        existing_tl.append({
            "event": "ACCEPTED",
            "title": "Documents Accepted",
            "description": data.remarks or "Documents Accepted by Verifier",
            "timestamp": now.isoformat(),
            "actor": current_user.full_name or current_user.email
        })
        
        # Resolve the specific check
        if insuff.check_id:
            check_stmt = select(models.VerificationCheck).filter(models.VerificationCheck.id == insuff.check_id)
            check_res = await db.execute(check_stmt)
            check = check_res.scalar_one_or_none()
            if check:
                check.status = enums.CheckStatus.WIP
        
        # Check if there are any other unresolved insufficiencies for this case
        rem_stmt = select(func.count(models.Insufficiency.id)).filter(
            models.Insufficiency.case_id == insuff.case_id,
            models.Insufficiency.is_resolved == False,
            models.Insufficiency.id != id
        )
        rem_res = await db.execute(rem_stmt)
        remaining = rem_res.scalar() or 0
        if remaining == 0:
            insuff.case.status = enums.CaseStatus.WIP # Move case back to WIP
            # Notify Allocator (Super Admin / Admin)
            allocators = await notification_utils.get_users_by_role(db, [enums.UserRole.SUPER_ADMIN, enums.UserRole.ADMIN])
            for user in allocators:
                await notification_utils.create_notification(
                    db, user.id, "Verification Continued",
                    f"Insufficiencies for case {insuff.case.case_ref_no} have been resolved. It is back in WIP.",
                    enums.NotificationCategory.SYSTEM_ALERT,
                    case_id=insuff.case_id
                )
            
    elif action == "REJECT":
        if not data.remarks:
            raise HTTPException(status_code=400, detail="Remarks are mandatory for REJECT action")
            
        insuff.status = "PENDING_CLIENT_RESPONSE"
        insuff.case.status = enums.CaseStatus.PENDING_CLIENT_RESPONSE
        existing_tl.append({
            "event": "REJECTED",
            "title": "Documents Rejected",
            "description": data.remarks,
            "timestamp": now.isoformat(),
            "actor": current_user.full_name or current_user.email
        })
        # Notify Customer Users
        customer_users = await db.execute(select(models.User).filter(models.User.customer_id == insuff.case.customer_id))
        for user in customer_users.scalars().all():
            await notification_utils.create_notification(
                db, user.id, "Documents Rejected",
                f"Your submitted documents for check {insuff.check.check_type if insuff.check else 'General'} were rejected. Reason: {data.remarks}",
                enums.NotificationCategory.INSUFFICIENT_DOCS,
                case_id=insuff.case_id
            )
        
    elif action == "NEED_MORE_INFO":
        if not data.remarks:
            raise HTTPException(status_code=400, detail="Remarks are mandatory for NEED_MORE_INFO action")
            
        insuff.status = "PENDING_CLIENT_RESPONSE"
        insuff.case.status = enums.CaseStatus.PENDING_CLIENT_RESPONSE
        existing_tl.append({
            "event": "NEED_MORE_INFO",
            "title": "Need More Information",
            "description": data.remarks,
            "timestamp": now.isoformat(),
            "actor": current_user.full_name or current_user.email
        })
        # Notify Customer Users
        customer_users = await db.execute(select(models.User).filter(models.User.customer_id == insuff.case.customer_id))
        for user in customer_users.scalars().all():
            await notification_utils.create_notification(
                db, user.id, "More Information Needed",
                f"Additional information requested for check {insuff.check.check_type if insuff.check else 'General'}: {data.remarks}",
                enums.NotificationCategory.INSUFFICIENT_DOCS,
                case_id=insuff.case_id
            )
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
        
    insuff.timeline = existing_tl
    insuff.updated_at = now
    insuff.updated_by = current_user.id
    
    comment = models.CaseComment(
        case_id=insuff.case_id,
        user_id=current_user.id,
        content=f"Verifier {action} insufficiency: {data.remarks or ''}"
    )
    db.add(comment)
    
    await db.commit()
    return {"message": f"Insufficiency {action.lower()}ed successfully"}
