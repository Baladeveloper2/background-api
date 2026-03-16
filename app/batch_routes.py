from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from . import models, schemas
from .database import get_db

from .auth_routes import check_module_permission

router = APIRouter(
    prefix="/batches",
    tags=["batches"]
)

@router.post("/", response_model=schemas.Batch, dependencies=[Depends(check_module_permission("bvs", "batch", action="write"))])
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
    from sqlalchemy import func
    from datetime import datetime
    
    results = db.query(
        models.Batch.id,
        models.Batch.batch_no,
        models.Customer.name.label("customer_name"),
        models.Batch.upload_date,
        func.count(models.Case.id).label("case_count"),
        func.sum(func.case([(models.Case.status != models.CaseStatus.COMPLETED, 1)], else_=0)).label("pending_count"),
        func.max(models.Case.completed_date).label("completed_date")
    ).join(models.Customer, models.Batch.customer_id == models.Customer.id)\
     .outerjoin(models.Case, models.Batch.id == models.Case.batch_id)\
     .group_by(models.Batch.id, models.Batch.batch_no, models.Customer.name, models.Batch.upload_date)\
     .all()

    summaries = []
    now = datetime.now()
    for r in results:
        age = (now - r.upload_date.replace(tzinfo=None)).days
        pending = r.pending_count or 0
        
        summaries.append({
            "id": r.id,
            "batch_no": r.batch_no or f"Batch_{r.id[:8]}",
            "customer_name": r.customer_name,
            "upload_date": r.upload_date,
            "case_count": r.case_count,
            "age_days": age,
            "pending_count": pending,
            "tat": 10,
            "total_value": r.case_count * 1000,
            "completed_date": r.completed_date,
            "status": "Entry Pending" if pending > 0 or r.case_count == 0 else "Entry Completed"
        })
    return summaries

@router.get("/", response_model=List[schemas.Batch], dependencies=[Depends(check_module_permission("bvs", "batch", action="read"))])
def read_batches(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Batch).offset(skip).limit(limit).all()

@router.get("/{batch_id}", response_model=schemas.Batch, dependencies=[Depends(check_module_permission("bvs", "batch", action="read"))])
def read_batch(batch_id: str, db: Session = Depends(get_db)):
    db_batch = db.query(models.Batch).filter(models.Batch.id == batch_id).first()
    if db_batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return db_batch
