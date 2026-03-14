from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from . import models, schemas
from .database import get_db

from .auth_routes import check_module_permission

router = APIRouter(
    prefix="/verifications",
    tags=["verifications"]
)

@router.post("/checks", response_model=schemas.VerificationCheck, dependencies=[Depends(check_module_permission("bvs", "verification"))])

def create_verification_check(check: schemas.VerificationCheckCreate, db: Session = Depends(get_db)):
    db_check = models.VerificationCheck(**check.dict())
    db.add(db_check)
    db.commit()
    db.refresh(db_check)
    return db_check

@router.get("/checks", response_model=List[schemas.VerificationCheck], dependencies=[Depends(check_module_permission("bvs", "verification"))])
def read_verification_checks(case_id: str = None, db: Session = Depends(get_db)):
    query = db.query(models.VerificationCheck)
    if case_id:
        query = query.filter(models.VerificationCheck.case_id == case_id)
    return query.all()

@router.patch("/checks/{check_id}", response_model=schemas.VerificationCheck, dependencies=[Depends(check_module_permission("bvs", "verification"))])

def update_verification_check(check_id: str, check_update: schemas.VerificationCheckBase, db: Session = Depends(get_db)):
    db_check = db.query(models.VerificationCheck).filter(models.VerificationCheck.id == check_id).first()
    if db_check is None:
        raise HTTPException(status_code=404, detail="Check not found")
    
    update_data = check_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_check, key, value)
    
    db.commit()
    db.refresh(db_check)
    return db_check
