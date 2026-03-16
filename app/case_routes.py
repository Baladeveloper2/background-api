from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from . import models, schemas
from .database import get_db

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

@router.get("/", response_model=List[schemas.CaseRead], dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
def read_cases(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    results = db.query(
        models.Case,
        models.Candidate.name.label("candidate_name"),
        models.Customer.name.label("customer_name")
    ).join(models.Candidate, models.Case.candidate_id == models.Candidate.id)\
     .join(models.Customer, models.Case.customer_id == models.Customer.id)\
     .offset(skip).limit(limit).all()
    
    cases = []
    for case, cand_name, cust_name in results:
        case_dict = case.__dict__
        case_dict["candidate_name"] = cand_name
        case_dict["customer_name"] = cust_name
        cases.append(case_dict)
    return cases

@router.get("/{case_id}", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
def read_case(case_id: str, db: Session = Depends(get_db)):
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return db_case

@router.patch("/{case_id}", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
def update_case(case_id: str, case_update: schemas.CaseBase, db: Session = Depends(get_db)):
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    
    update_data = case_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_case, key, value)
    
    db.commit()
    db.refresh(db_case)
    return db_case

