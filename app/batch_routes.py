from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import List, Optional
from . import models, schemas
from .database import get_db
from .auth_routes import check_module_permission

router = APIRouter(
    prefix="/batches",
    tags=["batches"]
)

@router.post("", response_model=schemas.Batch, dependencies=[Depends(check_module_permission("bvs", "batch", action="write"))])
def create_batch(batch: schemas.BatchCreate, db: Session = Depends(get_db)):
    # Auto-generate batch_no if not provided
    if not batch.batch_no:
        data_count = db.query(models.Batch).count()
        batch.batch_no = f"Batch_{26331 + data_count}"
        
    db_batch = models.Batch(**batch.dict())
    db.add(db_batch)
    db.commit()
    db.refresh(db_batch)
    return db_batch

@router.get("/summary", response_model=List[schemas.BatchSummary])
def read_batches_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_module_permission("bvs", "verification", action="read"))
):
    from sqlalchemy import func, case
    from datetime import datetime
    
    # 1. Subquery for Case counts per batch to avoid Cartesian product
    case_counts = db.query(
        models.Case.batch_id,
        func.count(models.Case.id).label("actual_case_count"),
        func.sum(case((models.Case.status != models.CaseStatus.COMPLETED, 1), else_=0)).label("pending_count"),
        func.sum(case((models.Case.status == models.CaseStatus.COMPLETED, 1), else_=0)).label("completed_count"),
        func.max(models.Case.completed_date).label("completed_date")
    ).group_by(models.Case.batch_id).subquery()

    # 2. Subquery for Check values per batch (via Case)
    check_values = db.query(
        models.Case.batch_id,
        func.sum(models.VerificationCheck.rate).label("total_check_value")
    ).join(models.VerificationCheck, models.Case.id == models.VerificationCheck.case_id)\
     .group_by(models.Case.batch_id).subquery()

    # 3. Main query joining Batch with subqueries
    results = db.query(
        models.Batch.id,
        models.Batch.batch_no,
        models.Batch.customer_id,
        models.Customer.name.label("customer_name"),
        models.Batch.upload_date,
        models.Batch.cases_count,
        models.Batch.tat_days,
        models.Batch.case_rate,
        models.Batch.file_url,
        case_counts.c.actual_case_count,
        case_counts.c.pending_count,
        case_counts.c.completed_count,
        case_counts.c.completed_date,
        check_values.c.total_check_value
    ).join(models.Customer, models.Batch.customer_id == models.Customer.id)\
     .outerjoin(case_counts, models.Batch.id == case_counts.c.batch_id)\
     .outerjoin(check_values, models.Batch.id == check_values.c.batch_id)\
     .all()

    summaries = []
    now = datetime.now()
    for r in results:
        upload_date = r.upload_date or now
        age = (now.date() - upload_date.date()).days
        if age < 0: age = 0 
        pending = r.pending_count or 0
        actual_cases = r.actual_case_count or 0
        intended_cases = r.cases_count or 0
        
        # Total value is now driven by check rates primarily, fallback to case_rate for old data
        total_value = float(r.total_check_value or 0)
        if total_value == 0 and r.case_rate and intended_cases:
            total_value = r.case_rate * intended_cases

        summaries.append({
            "id": r.id,
            "batch_no": r.batch_no or f"Batch_{r.id[:8]}",
            "customer_id": r.customer_id,
            "customer_name": r.customer_name,
            "upload_date": r.upload_date,
            "case_count": intended_cases,
            "actual_cases": actual_cases,
            "intended_cases": intended_cases,
            "case_rate": r.case_rate or 0,
            "age_days": age,
            "pending_count": pending,
            "completed_count": int(r.completed_count or 0),
            "tat": r.tat_days or 10,
            "total_value": total_value,
            "completed_date": r.completed_date,
            "file_url": r.file_url,
            "status": "Entry Pending" if (actual_cases == 0 or actual_cases < intended_cases) else "Completed" if pending == 0 else "Verification In-Progress"
        })
    return summaries

@router.get("", response_model=List[schemas.Batch], dependencies=[Depends(check_module_permission("bvs", "batch", action="read"))])
def read_batches(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Batch).offset(skip).limit(limit).all()

@router.get("/{batch_id}", response_model=schemas.Batch, dependencies=[Depends(check_module_permission("bvs", "batch", action="read"))])
def read_batch(batch_id: str, db: Session = Depends(get_db)):
    db_batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
    if db_batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return db_batch

@router.patch("/{batch_id}", response_model=schemas.Batch, dependencies=[Depends(check_module_permission("bvs", "batch", action="write"))])
def update_batch(batch_id: str, batch_update: schemas.BatchUpdate, db: Session = Depends(get_db)):
    db_batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
    if db_batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    update_data = batch_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_batch, key, value)
    
    db.commit()
    db.refresh(db_batch)
    return db_batch

@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(check_module_permission("bvs", "batch", action="write"))])
def delete_batch(batch_id: str, db: Session = Depends(get_db)):
    db_batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
    if db_batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Manual cleanup to avoid IntegrityErrors with existing DB constraints
    case_ids = [c.id for c in db.query(models.Case.id).filter(models.Case.batch_id == batch_id).all()]
    if case_ids:
        db.query(models.VerificationCheck).filter(models.VerificationCheck.case_id.in_(case_ids)).delete(synchronize_session=False)
        db.query(models.Case).filter(models.Case.id.in_(case_ids)).delete(synchronize_session=False)
        
    db.delete(db_batch)
    db.commit()
    return None
