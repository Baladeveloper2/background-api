from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import Dict, Any
from . import models, schemas, notification_utils, email_utils
from .database import get_async_db
from datetime import datetime

router = APIRouter(prefix="/public", tags=["public"])

@router.get("/insufficiency/{token}", response_model=schemas.PublicInsufficiencyResponse)
async def get_public_insufficiency(token: str, db: AsyncSession = Depends(get_async_db)):
    """Fetch insufficiency details using a secure token (unauthenticated)."""
    stmt = (
        select(models.Insufficiency)
        .options(
            joinedload(models.Insufficiency.case).joinedload(models.Case.customer),
            joinedload(models.Insufficiency.case).joinedload(models.Case.candidate),
            joinedload(models.Insufficiency.check)
        )
        .filter(models.Insufficiency.token == token, models.Insufficiency.is_resolved == False)
    )
    res = await db.execute(stmt)
    insuff = res.unique().scalar_one_or_none()
    
    if not insuff:
        raise HTTPException(status_code=404, detail="Invalid or expired resolution link")
        
    # Check and append CANDIDATE_OPENED event
    existing_tl = list(insuff.timeline or [])
    has_opened = any(t.get("event") == "CANDIDATE_OPENED" for t in existing_tl)
    if not has_opened:
        existing_tl.append({
            "event": "CANDIDATE_OPENED",
            "title": "Candidate Opened Link",
            "description": "Candidate opened the secure document upload link.",
            "timestamp": datetime.utcnow().isoformat(),
            "actor": "Candidate (Self-Service Portal)"
        })
        insuff.timeline = existing_tl
        await db.commit()

    return {
        "id": insuff.id,
        "case_ref": insuff.case.case_ref_no or insuff.case.id,
        "candidate_name": insuff.case.candidate.name if insuff.case.candidate else "Candidate",
        "check_name": insuff.check.check_type if insuff.check else "General Verification",
        "customer_name": insuff.case.customer.name if insuff.case.customer else "Our Client",
        "message": insuff.message,
        "status": insuff.status
    }

@router.post("/insufficiency/{token}/submit")
async def submit_candidate_insufficiency(
    token: str, 
    data: schemas.PublicInsufficiencySubmit, 
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    """Candidate submits evidence via public portal."""
    stmt = select(models.Insufficiency).options(
        joinedload(models.Insufficiency.case).joinedload(models.Case.candidate)
    ).filter(models.Insufficiency.token == token)
    res = await db.execute(stmt)
    insuff = res.scalar_one_or_none()
    
    if not insuff:
        raise HTTPException(status_code=404, detail="Invalid token")
        
    # Update insufficiency lifecycle status
    insuff.documents = data.documents
    insuff.status = "CANDIDATE_RESPONDED"
    insuff.response_at = datetime.utcnow()
    insuff.updated_at = datetime.utcnow()
    
    # Append timeline event
    existing_timeline = list(insuff.timeline or [])
    existing_timeline.append({
        "event": "CANDIDATE_RESPONDED",
        "title": "Candidate Uploaded Document",
        "description": f"Candidate {insuff.case.candidate.name if insuff.case and insuff.case.candidate else 'Candidate'} uploaded document(s) via secure link.",
        "timestamp": datetime.utcnow().isoformat(),
        "actor": "Candidate (Self-Service Portal)",
        "details": {
            "remarks": data.remarks if hasattr(data, "remarks") else "Uploaded files",
            "documents_count": len(data.documents)
        }
    })
    insuff.timeline = existing_timeline
    
    # Add audit log
    candidate_name = insuff.case.candidate.name if insuff.case and insuff.case.candidate else "Candidate"
    audit_log = models.AuditLog(
        user_id=None,  # Unauthenticated public candidate action
        action="CANDIDATE_UPLOAD_EVIDENCE",
        resource_id=insuff.case_id,
        details=f"User: {candidate_name} (Candidate) | Role: CANDIDATE | IP: {request.client.host} | Action: CANDIDATE_UPLOAD_EVIDENCE | Remarks: Uploaded evidence documents."
    )
    db.add(audit_log)

    # Update case status if needed
    db_case = insuff.case
    if db_case.status == "INSUFFICIENT":
        # Check if all insufficiencies for this case are now uploaded or resolved
        from sqlalchemy import func
        rem_stmt = select(func.count(models.Insufficiency.id)).filter(
            models.Insufficiency.case_id == db_case.id,
            models.Insufficiency.status.in_(["INSUFFICIENT", "PENDING"]),
            models.Insufficiency.is_resolved == False
        )
        rem_res = await db.execute(rem_stmt)
        if rem_res.scalar() == 0:
            db_case.status = "VERIFICATION"  # Move back to queue
    
    # Notify stakeholders
    try:
        await notification_utils.notify_insufficiency_resolved(
            db, insuff.id, 
            background_tasks=background_tasks
        )
    except Exception:
        pass  # Best-effort notification
    
    await db.commit()
    
    return {"status": "success", "message": "Evidence submitted successfully"}
