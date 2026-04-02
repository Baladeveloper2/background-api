from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from . import models, schemas
from .database import get_db
import uuid

from .auth_routes import check_module_permission

router = APIRouter(
    prefix="/verifications",
    tags=["verifications"]
)

@router.post("/checks", response_model=schemas.VerificationCheck, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])

def create_verification_check(check: schemas.VerificationCheckCreate, db: Session = Depends(get_db)):
    db_check = models.VerificationCheck(**check.dict())
    db.add(db_check)
    db.commit()
    db.refresh(db_check)
    return db_check

@router.get("/checks", response_model=List[schemas.VerificationCheck], dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
def read_verification_checks(case_id: Optional[str] = None, type: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.VerificationCheck)
    if case_id:
        query = query.filter(models.VerificationCheck.case_id == case_id)
    if type:
        query = query.filter(models.VerificationCheck.check_type.ilike(f"%{type}%"))
    
    results = query.all()
    
    # Enrich with case info for specific views (like digital address check)
    for check in results:
        case = check.case
        if case:
            check.case_ref = case.case_ref_no
            if case.candidate:
                check.candidate_name = case.candidate.name
                check.given_address = case.candidate.address_details.get("address", "") if case.candidate.address_details else (case.candidate.address or "")
            if case.customer:
                check.customer_name = case.customer.name
                
    return results

@router.patch("/checks/{check_id}", response_model=schemas.VerificationCheck, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])

def update_verification_check(check_id: str, check_update: schemas.VerificationCheckUpdate, db: Session = Depends(get_db)):
    db_check = db.query(models.VerificationCheck).filter(models.VerificationCheck.id == check_id).first()
    if db_check is None:
        raise HTTPException(status_code=404, detail="Check not found")
    
    update_data = check_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_check, key, value)
    
    db.commit()
    db.refresh(db_check)

    # Check if all other checks for this case are also completed
    case = db_check.case
    if case:
        all_checks = db.query(models.VerificationCheck).filter(models.VerificationCheck.case_id == case.id).all()
        # If all checks are NOT in INTERIM or VERIFICATION status, move case to QC
        # This ensures they have been analyzed (GREEN/RED/AMBER)
        if all(c.status not in [models.CheckStatus.INTERIM, models.CheckStatus.VERIFICATION] for c in all_checks):
            case.status = models.CaseStatus.QC
            db.commit()
            
    return db_check

@router.patch("/checks/{check_id}/generate-link", response_model=schemas.VerificationCheck, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
def generate_verification_link(check_id: str, db: Session = Depends(get_db)):
    db_check = db.query(models.VerificationCheck).filter(models.VerificationCheck.id == check_id).first()
    if db_check is None:
        raise HTTPException(status_code=404, detail="Check not found")
    
    db_check.digital_token = str(uuid.uuid4())
    db.commit()
    db.refresh(db_check)
    return db_check

@router.get("/public/{token}", response_model=Dict[str, Any])
def get_public_verification(token: str, db: Session = Depends(get_db)):
    db_check = db.query(models.VerificationCheck).filter(models.VerificationCheck.digital_token == token).first()
    if db_check is None:
        raise HTTPException(status_code=404, detail="Invalid or expired link")
    
    # Return minimal data for public view
    case = db_check.case
    candidate = case.candidate
    return {
        "check_id": db_check.id,
        "candidate_name": candidate.name,
        "check_type": db_check.check_type,
        "given_address": candidate.address_details.get("address", {}) if candidate.address_details else {}
    }

@router.post("/public/{token}")
def submit_public_verification(token: str, submission: Dict[str, Any], db: Session = Depends(get_db)):
    db_check = db.query(models.VerificationCheck).filter(models.VerificationCheck.digital_token == token).first()
    if db_check is None:
        raise HTTPException(status_code=404, detail="Invalid or expired link")
    
    # Update check data with digital submission
    if not db_check.data:
        db_check.data = {}
    
    db_check.data["digital_data"] = submission
    db_check.status = models.CheckStatus.VERIFICATION  # Move to active verification status
    db_check.verifier_remarks = "Digital Address submitted by candidate."
    
    db.commit()
    return {"message": "Verification data submitted successfully"}
