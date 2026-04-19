from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
from . import models, schemas
from .database import get_async_db
import uuid

from .auth_routes import check_module_permission
from . import notification_utils

router = APIRouter(
    prefix="/verifications",
    tags=["verifications"]
)

@router.post("/checks", response_model=schemas.VerificationCheck, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def create_verification_check(check: schemas.VerificationCheckCreate, db: AsyncSession = Depends(get_async_db)):
    db_check = models.VerificationCheck(**check.dict())
    db.add(db_check)
    await db.commit()
    await db.refresh(db_check)
    return db_check

@router.get("/checks", response_model=List[schemas.VerificationCheck], dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
async def read_verification_checks(case_id: Optional[str] = None, type: Optional[str] = None, db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case).selectinload(models.Case.candidate),
        selectinload(models.VerificationCheck.case).selectinload(models.Case.customer)
    )
    if case_id:
        stmt = stmt.filter(models.VerificationCheck.case_id == case_id)
    if type:
        stmt = stmt.filter(models.VerificationCheck.check_type.ilike(f"%{type}%"))
    
    res = await db.execute(stmt)
    results = res.scalars().all()
    
    # Enrichment
    for check in results:
        case_obj = check.case
        if case_obj:
            check.case_ref = case_obj.case_ref_no
            if case_obj.candidate:
                check.candidate_name = case_obj.candidate.name
                check.given_address = case_obj.candidate.address_details.get("address", "") if case_obj.candidate.address_details else (case_obj.candidate.address or "")
            if case_obj.customer:
                check.customer_name = case_obj.customer.name
                
    return results

@router.patch("/checks/{check_id}", response_model=schemas.VerificationCheck, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def update_verification_check(check_id: str, check_update: schemas.VerificationCheckUpdate, db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.VerificationCheck).options(selectinload(models.VerificationCheck.case)).filter(models.VerificationCheck.id == check_id)
    res = await db.execute(stmt)
    db_check = res.scalar_one_or_none()
    
    if db_check is None:
        raise HTTPException(status_code=404, detail="Check not found")
    
    update_data = check_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_check, key, value)
    
    await db.commit()
    await db.refresh(db_check)
    return db_check

@router.patch("/checks/{check_id}/generate-link", response_model=schemas.VerificationCheck, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def generate_verification_link(check_id: str, db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.VerificationCheck).filter(models.VerificationCheck.id == check_id)
    res = await db.execute(stmt)
    db_check = res.scalar_one_or_none()
    
    if db_check is None:
        raise HTTPException(status_code=404, detail="Check not found")
    
    db_check.digital_token = str(uuid.uuid4())
    await db.commit()
    await db.refresh(db_check)
    return db_check

@router.get("/public/{token}", response_model=Dict[str, Any])
async def get_public_verification(token: str, db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case).selectinload(models.Case.candidate)
    ).filter(models.VerificationCheck.digital_token == token)
    res = await db.execute(stmt)
    db_check = res.scalar_one_or_none()
    
    if db_check is None:
        raise HTTPException(status_code=404, detail="Invalid or expired link")
    
    case_obj = db_check.case
    candidate = case_obj.candidate
    return {
        "check_id": db_check.id,
        "candidate_name": candidate.name,
        "check_type": db_check.check_type,
        "given_address": candidate.address_details.get("address", {}) if candidate.address_details else {}
    }

@router.post("/public/{token}")
async def submit_public_verification(token: str, submission: Dict[str, Any], db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.VerificationCheck).filter(models.VerificationCheck.digital_token == token)
    res = await db.execute(stmt)
    db_check = res.scalar_one_or_none()
    
    if db_check is None:
        raise HTTPException(status_code=404, detail="Invalid or expired link")
    
    # Update check data
    if not db_check.data:
        db_check.data = {}
    
    db_check.data["digital_data"] = submission
    db_check.status = models.CheckStatus.VERIFICATION
    db_check.verifier_remarks = "Digital Address submitted by candidate."
    
    await db.commit()
    
    # Notify verifier if assigned
    if db_check.case and db_check.case.assigned_to:
        await notification_utils.create_notification(
            db, db_check.case.assigned_to,
            "Form Submitted",
            f"Candidate has submitted form for Case {db_check.case.case_ref_no}.",
            models.NotificationCategory.FORM_SUBMITTED,
            case_id=db_check.case_id
        )
    
    return {"message": "Verification data submitted successfully"}
