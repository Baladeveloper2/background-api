from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import json
from typing import List, Optional
from . import models, schemas, auth_routes
from .database import get_db_sync as get_db

router = APIRouter(
    prefix="/candidates",
    tags=["candidates"]
)

@router.post("", response_model=schemas.Candidate, dependencies=[Depends(auth_routes.check_module_permission("recruit", "management", action="write"))])
def create_candidate(candidate: schemas.CandidateCreate, db: Session = Depends(get_db)):
    db_candidate = models.Candidate(**candidate.dict())
    db.add(db_candidate)
    db.commit()
    db.refresh(db_candidate)
    return db_candidate

@router.get("", response_model=List[schemas.Candidate], dependencies=[Depends(auth_routes.check_module_permission("recruit", "management", action="read"))])
def read_candidates(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    query = db.query(models.Candidate)
    
    if current_user.role == models.UserRole.CUSTOMER:
        query = query.filter(models.Candidate.customer_id == current_user.customer_id)
        
    if getattr(current_user, "zone_id", None):
        query = query.filter(models.Candidate.zone_id == current_user.zone_id)
    if getattr(current_user, "branch_id", None):
        query = query.filter(models.Candidate.branch_id == current_user.branch_id)
        
    return query.offset(skip).limit(limit).all()

@router.get("/{candidate_id}", response_model=schemas.Candidate, dependencies=[Depends(auth_routes.check_module_permission("recruit", "management", action="read"))])
def read_candidate(candidate_id: str, db: Session = Depends(get_db)):
    db_candidate = db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()
    if db_candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return db_candidate

async def check_candidate_update_access(current_user: models.User = Depends(auth_routes.get_current_user)):
    if current_user.role == models.UserRole.SUPER_ADMIN:
        return current_user
    
    # Check for either recruitment management or BVS verification write access
    perms = current_user.bvs_permissions or {}
    if isinstance(perms, str):
        try: perms = json.loads(perms)
        except: perms = {}
        
    role_perms = current_user.role_rel.permissions if current_user.role_rel else {}
    if isinstance(role_perms, str):
        try: role_perms = json.loads(role_perms)
        except: role_perms = {}
    
    # Role-based systemic access (matching auth_routes oversight logic)
    oversight_roles = [models.UserRole.QA, models.UserRole.QC, models.UserRole.MANAGER, models.UserRole.ADMIN]
    if current_user.role in oversight_roles: return current_user
    if current_user.role_rel and current_user.role_rel.name in ["Super Admin", "QC Verifier", "Verifier"]: return current_user

    # Granular permission check
    def has_write(p_obj, key):
        val = p_obj.get(key)
        if val is True: return True
        if isinstance(val, dict) and val.get("write"): return True
        if isinstance(val, str) and "W" in val.upper(): return True
        return False

    # Check Recruit Module or BVS Module
    if has_write(perms, "recruit") or has_write(role_perms, "recruit.management"): return current_user
    if has_write(perms, "bvs") or has_write(role_perms, "bvs.verification"): return current_user
    
    raise HTTPException(status_code=403, detail="Insufficient permissions to update candidate record")

@router.patch("/{candidate_id}", response_model=schemas.Candidate, dependencies=[Depends(check_candidate_update_access)])
def update_candidate(candidate_id: str, candidate_update: schemas.CandidateUpdate, db: Session = Depends(get_db)):
    db_candidate = db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()
    if db_candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    update_data = candidate_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_candidate, key, value)
    
    db.commit()
    db.refresh(db_candidate)
    return db_candidate

@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(auth_routes.check_module_permission("recruit", "management", action="delete"))])
def delete_candidate(candidate_id: str, db: Session = Depends(get_db)):
    db_candidate = db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()
    if db_candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    db.delete(db_candidate)
    db.commit()
    return None


# ─── Insufficiency Resolution Endpoints ─────────────────────────────────────

from pydantic import BaseModel
from datetime import datetime
import uuid
import os
from . import email_utils

singular_router = APIRouter(
    prefix="/candidate",
    tags=["candidate"]
)

class NotifyCandidateRequest(BaseModel):
    subject: str
    message: str
    due_date: str
    attachment_url: Optional[str] = None
    send_sms: bool = True
    send_email: bool = True
    send_whatsapp: bool = True
    token: Optional[str] = None

class ClearInsufficiencyRequest(BaseModel):
    remarks: str
    verified_by: Optional[str] = None
    resolution_date: Optional[str] = None
    documents: Optional[List[dict]] = []

class CandidateResponseRequest(BaseModel):
    remarks: str
    documents: List[dict] = []

def get_case_by_id_or_candidate_id(db: Session, candidate_id: str):
    case = db.query(models.Case).filter(models.Case.id == candidate_id).first()
    if not case:
        case = db.query(models.Case).filter(models.Case.candidate_id == candidate_id).first()
    return case

@router.get("/{candidate_id}/insufficiency")
@singular_router.get("/{candidate_id}/insufficiency")
def get_candidate_insufficiency(candidate_id: str, db: Session = Depends(get_db)):
    case = get_case_by_id_or_candidate_id(db, candidate_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case/Candidate not found")
        
    insuff = db.query(models.Insufficiency).filter(
        models.Insufficiency.case_id == case.id,
        models.Insufficiency.is_resolved == False
    ).order_by(models.Insufficiency.created_at.desc()).first()
    
    if not insuff:
        return {"active": False}
        
    raised_user = db.query(models.User).filter(models.User.id == insuff.raised_by).first()
    raised_by_name = raised_user.full_name if raised_user else "Verifier"
    
    check_name = "General Check"
    if insuff.check:
        check_name = insuff.check.check_type
        
    return {
        "active": True,
        "id": insuff.id,
        "case_id": insuff.case_id,
        "check_id": insuff.check_id,
        "check_name": check_name,
        "status": insuff.status,
        "message": insuff.message,
        "raised_by": raised_by_name,
        "created_at": insuff.created_at.isoformat() if insuff.created_at else None,
        "due_date": insuff.due_date.isoformat() if insuff.due_date else None,
        "notification_count": insuff.notification_count,
        "last_notified_at": insuff.last_notified_at.isoformat() if insuff.last_notified_at else None,
        "response_at": insuff.response_at.isoformat() if insuff.response_at else None,
        "timeline": insuff.timeline or []
    }

@router.post("/{candidate_id}/notify")
@singular_router.post("/{candidate_id}/notify")
async def notify_candidate_insufficiency(
    candidate_id: str,
    req: NotifyCandidateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    case = get_case_by_id_or_candidate_id(db, candidate_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case/Candidate not found")
        
    insuff = db.query(models.Insufficiency).filter(
        models.Insufficiency.case_id == case.id,
        models.Insufficiency.is_resolved == False
    ).order_by(models.Insufficiency.created_at.desc()).first()
    
    if not insuff:
        raise HTTPException(status_code=404, detail="No active insufficiency found")
        
    try:
        due_date_parsed = datetime.fromisoformat(req.due_date.replace("Z", ""))
    except Exception:
        due_date_parsed = datetime.utcnow()
        
    insuff.due_date = due_date_parsed
    insuff.notification_count += 1
    insuff.last_notified_at = datetime.utcnow()
    insuff.status = "PENDING_RESPONSE"
    
    # Generate token if not exist (using client-pre-generated token if available)
    if not insuff.token:
        if req.token:
            insuff.token = req.token
        else:
            insuff.token = str(uuid.uuid4())
        
    # Send email outreach using template
    candidate = case.candidate
    if req.send_email and candidate and candidate.email:
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        upload_link = f"{frontend_url}/candidate/insufficiency/{insuff.token}"
        check_name = insuff.check.check_type if insuff.check else "Verification Check"
        await email_utils.send_insufficiency_email(
            to_email=candidate.email,
            candidate_name=candidate.name,
            case_ref=case.case_ref_no or case.id,
            check_name=check_name,
            custom_message=req.message,
            upload_link=upload_link
        )
        
    # Append timeline event
    channels = []
    if req.send_email: channels.append("Email")
    if req.send_sms: channels.append("SMS")
    if req.send_whatsapp: channels.append("WhatsApp")
    
    existing_tl = list(insuff.timeline or [])
    existing_tl.append({
        "event": "Candidate Notified",
        "title": "Candidate Notified",
        "description": f"Notification sent via: {', '.join(channels)}",
        "timestamp": datetime.utcnow().isoformat(),
        "actor": current_user.full_name or current_user.email,
        "details": {
            "subject": req.subject,
            "message": req.message,
            "due_date": req.due_date,
            "channels": channels
        }
    })
    insuff.timeline = existing_tl
    
    # Audit Log
    audit = models.AuditLog(
        user_id=current_user.id,
        action="NOTIFY_CANDIDATE",
        resource_id=case.id,
        details=f"User: {current_user.full_name or current_user.email} | Role: {current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)} | IP: {request.client.host} | Action: NOTIFY_CANDIDATE | Remarks: {req.message}"
    )
    db.add(audit)
    
    db.commit()
    return {"status": "success", "message": "Notification sent successfully"}

@router.post("/{candidate_id}/clear-insufficiency")
@singular_router.post("/{candidate_id}/clear-insufficiency")
def clear_candidate_insufficiency(
    candidate_id: str,
    req: ClearInsufficiencyRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    case = get_case_by_id_or_candidate_id(db, candidate_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case/Candidate not found")
        
    insuff = db.query(models.Insufficiency).filter(
        models.Insufficiency.case_id == case.id,
        models.Insufficiency.is_resolved == False
    ).order_by(models.Insufficiency.created_at.desc()).first()
    
    if not insuff:
        raise HTTPException(status_code=404, detail="No active insufficiency found")
        
    try:
        resolved_at_parsed = datetime.fromisoformat(req.resolution_date.replace("Z", "")) if req.resolution_date else datetime.utcnow()
    except Exception:
        resolved_at_parsed = datetime.utcnow()

    insuff.is_resolved = True
    insuff.status = "RESOLVED"
    insuff.resolved_at = resolved_at_parsed
    insuff.resolved_by = current_user.id
    insuff.resolved_remarks = f"Verified By: {req.verified_by or current_user.full_name or current_user.email}\nRemarks: {req.remarks}"
    if req.documents:
        insuff.documents = req.documents
    
    # Update check status back to VERIFICATION
    if insuff.check:
        insuff.check.status = "VERIFICATION"
        
    # Auto-resolve case status if no more open insufficiencies
    from sqlalchemy import func
    rem_open = db.query(func.count(models.Insufficiency.id)).filter(
        models.Insufficiency.case_id == case.id,
        models.Insufficiency.is_resolved == False
    ).scalar()
    
    if rem_open == 0:
        if case.status in ["INSUFFICIENT", "INSUFFICIENCY", "ON_HOLD"]:
            case.status = "WIP"
            
    # Add audit log
    audit_log = models.AuditLog(
        user_id=current_user.id,
        action="RESOLVE_INSUFFICIENCY",
        resource_id=case.id,
        details=f"User: {current_user.full_name or current_user.email} | Role: {current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)} | IP: {request.client.host} | Action: RESOLVE_INSUFFICIENCY | Remarks: {req.remarks}"
    )
    db.add(audit_log)
    
    # Append timeline event
    existing_tl = list(insuff.timeline or [])
    existing_tl.append({
        "event": "Resolved",
        "title": "Resolved",
        "description": f"Insufficiency cleared. Verified by {req.verified_by or current_user.full_name or current_user.email}.",
        "timestamp": resolved_at_parsed.isoformat(),
        "actor": current_user.full_name or current_user.email,
        "details": {
            "remarks": req.remarks,
            "resolved_at": resolved_at_parsed.isoformat()
        }
    })
    insuff.timeline = existing_tl
    
    db.commit()
    return {"status": "success", "message": "Insufficiency cleared successfully"}

@router.post("/{candidate_id}/response")
@singular_router.post("/{candidate_id}/response")
def submit_candidate_response(
    candidate_id: str,
    req: CandidateResponseRequest,
    db: Session = Depends(get_db)
):
    case = get_case_by_id_or_candidate_id(db, candidate_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case/Candidate not found")
        
    insuff = db.query(models.Insufficiency).filter(
        models.Insufficiency.case_id == case.id,
        models.Insufficiency.is_resolved == False
    ).order_by(models.Insufficiency.created_at.desc()).first()
    
    if not insuff:
        raise HTTPException(status_code=404, detail="No active insufficiency found")
        
    insuff.documents = req.documents
    insuff.status = "CANDIDATE_RESPONDED"
    insuff.response_at = datetime.utcnow()
    insuff.updated_at = datetime.utcnow()
    
    # Append timeline event
    existing_tl = list(insuff.timeline or [])
    existing_tl.append({
        "event": "Candidate Responded",
        "title": "Candidate Responded",
        "description": "Evidence and response submitted by candidate.",
        "timestamp": datetime.utcnow().isoformat(),
        "actor": "Candidate (Self-Service Portal)",
        "details": {
            "remarks": req.remarks,
            "documents_count": len(req.documents)
        }
    })
    insuff.timeline = existing_tl
    
    db.commit()
    return {"status": "success", "message": "Response submitted successfully"}

@router.post("/{candidate_id}/review")
@singular_router.post("/{candidate_id}/review")
def review_candidate_response(
    candidate_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    case = get_case_by_id_or_candidate_id(db, candidate_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case/Candidate not found")
        
    insuff = db.query(models.Insufficiency).filter(
        models.Insufficiency.case_id == case.id,
        models.Insufficiency.is_resolved == False
    ).order_by(models.Insufficiency.created_at.desc()).first()
    
    if not insuff:
        raise HTTPException(status_code=404, detail="No active insufficiency found")
        
    insuff.status = "UNDER_REVIEW"
    insuff.updated_at = datetime.utcnow()
    
    # Audit Log
    audit = models.AuditLog(
        user_id=current_user.id,
        action="REVIEW_INSUFFICIENCY",
        resource_id=case.id,
        details=f"User: {current_user.full_name or current_user.email} | Role: {current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)} | IP: {request.client.host} | Action: REVIEW_INSUFFICIENCY | Remarks: Started review of candidate response."
    )
    db.add(audit)

    # Append timeline event if not already present
    existing_tl = list(insuff.timeline or [])
    has_reviewed = any(t.get("event") == "Verifier Reviewed" for t in existing_tl)
    if not has_reviewed:
        existing_tl.append({
            "event": "Verifier Reviewed",
            "title": "Verifier Reviewed",
            "description": "Verifier has started reviewing the submitted documents.",
            "timestamp": datetime.utcnow().isoformat(),
            "actor": current_user.full_name or current_user.email
        })
        insuff.timeline = existing_tl
    
    db.commit()
    return {"status": "success", "message": "Insufficiency status updated to Under Review"}

@router.get("/{candidate_id}/timeline")
@singular_router.get("/{candidate_id}/timeline")
def get_candidate_insufficiency_timeline(candidate_id: str, db: Session = Depends(get_db)):
    case = get_case_by_id_or_candidate_id(db, candidate_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case/Candidate not found")
        
    insuff = db.query(models.Insufficiency).filter(
        models.Insufficiency.case_id == case.id
    ).order_by(models.Insufficiency.created_at.desc()).first()
    
    if not insuff:
        return []
        
    return insuff.timeline or []
