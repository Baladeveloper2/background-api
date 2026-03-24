from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from . import models, schemas
from .database import get_db
import uuid
from datetime import datetime

from .auth_routes import check_module_permission

router = APIRouter(
    prefix="/cases",
    tags=["cases"]
)

@router.post("/", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
def create_case(case: schemas.CaseCreate, db: Session = Depends(get_db)):
    db_case = models.Case(**case.dict())
    db.add(db_case)
    db.commit()
    db.refresh(db_case)
    return db_case

@router.post("/create-full", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
def create_case_full(case_data: schemas.CaseCreateExtended, db: Session = Depends(get_db)):
    # 1. Create/Get Candidate
    candidate_dict = case_data.candidate.dict()
    db_candidate = models.Candidate(**candidate_dict)
    db.add(db_candidate)
    db.flush() # Get candidate ID

    # 2. Create Case
    case_ref = case_data.case_ref_no or f"BGV-{datetime.now().year}-{str(uuid.uuid4())[:8]}"
    db_case = models.Case(
        case_ref_no=case_ref,
        customer_id=case_data.customer_id,
        candidate_id=db_candidate.id,
        batch_id=case_data.batch_id,
        status=models.CaseStatus.PENDING,
        received_date=datetime.utcnow()
    )
    db.add(db_case)
    db.flush()

    # 3. Create Verification Checks
    for service in case_data.services:
        db_check = models.VerificationCheck(
            case_id=db_case.id,
            check_type=service,
            status=models.CheckStatus.INTERIM
        )
        db.add(db_check)
    
    db.commit()
    db.refresh(db_case)
    return db_case

from sqlalchemy.orm import joinedload

@router.get("/", response_model=List[schemas.CaseRead], dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
def read_cases(status: Optional[models.CaseStatus] = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # 1. Base query for cases with their relationships
    query = db.query(models.Case).options(
        joinedload(models.Case.candidate),
        joinedload(models.Case.customer),
        joinedload(models.Case.checks)
    )
    
    if status:
        query = query.filter(models.Case.status == status)
    
    # 2. Results
    cases_models = query.offset(skip).limit(limit).all()
    
    # 3. Transform to CaseRead format
    cases_read = []
    for case in cases_models:
        case_data = schemas.CaseRead.model_validate(case)
        if case.candidate:
            case_data.candidate_name = case.candidate.name
        if case.customer:
            case_data.customer_name = case.customer.name
        cases_read.append(case_data)
        
    return cases_read

@router.get("/{case_id}", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
def read_case(case_id: str, db: Session = Depends(get_db)):
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return db_case

@router.patch("/{case_id}", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
def update_case(case_id: str, case_update: schemas.CaseUpdate, db: Session = Depends(get_db)):
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    
    update_data = case_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_case, key, value)
    
    db.commit()
    db.refresh(db_case)
    return db_case

@router.patch("/{case_id}/full", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
def update_case_full(case_id: str, case_data: schemas.CaseCreateExtended, db: Session = Depends(get_db)):
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # 1. Update Candidate
    db_candidate = db.query(models.Candidate).filter(models.Candidate.id == db_case.candidate_id).first()
    if db_candidate:
        candidate_data = case_data.candidate.dict(exclude_unset=True)
        for key, value in candidate_data.items():
            setattr(db_candidate, key, value)
    
    # 2. Update Case Metadata
    db_case.case_ref_no = case_data.case_ref_no
    db_case.customer_id = case_data.customer_id
    db_case.batch_id = case_data.batch_id
    
    # 3. Update Verification Checks
    current_checks = {c.check_type: c for c in db_case.checks}
    new_services = set(case_data.services)
    
    # Remove checks that are no longer selected (only if they are still interim/pending)
    for check_type, check in current_checks.items():
        if check_type not in new_services:
            db.delete(check)
            
    # Add newly selected checks
    for service in new_services:
        if service not in current_checks:
            db_check = models.VerificationCheck(
                case_id=db_case.id,
                check_type=service,
                status=models.CheckStatus.INTERIM
            )
            db.add(db_check)
    
    db.commit()
    db.refresh(db_case)
    return db_case

@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
def delete_case(case_id: str, db: Session = Depends(get_db)):
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Delete linked checks first
    db.query(models.VerificationCheck).filter(models.VerificationCheck.case_id == case_id).delete()
    db.delete(db_case)
    db.commit()
    return None
