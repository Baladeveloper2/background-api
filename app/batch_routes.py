from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, update, delete
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
from . import models, schemas
from .database import get_async_db
from .auth_routes import check_module_permission, limiter
from datetime import datetime

router = APIRouter(
    prefix="/batches",
    tags=["batches"]
)

async def get_next_batch_number(db: AsyncSession):
    year = datetime.now().year
    prefix = f"Batch_{year}_"
    # Find all batches for this year to determine the next sequence
    stmt = select(models.Batch.batch_no).filter(models.Batch.batch_no.like(f"{prefix}%"))
    res = await db.execute(stmt)
    batch_nos = res.scalars().all()
    
    max_seq = 0
    for bn in batch_nos:
        try:
            # Expected format: Batch_YEAR_SEQ (e.g., Batch_2026_001)
            parts = bn.split('_')
            if len(parts) >= 3:
                seq = int(parts[2])
                if seq > max_seq:
                    max_seq = seq
        except (ValueError, IndexError):
            continue
            
    return f"{prefix}{max_seq + 1:03d}"

@router.get("/next-batch-no")
async def read_next_batch_no(db: AsyncSession = Depends(get_async_db)):
    next_no = await get_next_batch_number(db)
    return {"next_batch_no": next_no}

@router.post("", response_model=schemas.Batch, dependencies=[Depends(check_module_permission("bvs", "batch", action="write"))])
@limiter.limit("5/minute")
async def create_batch(request: Request, batch: schemas.BatchCreate, db: AsyncSession = Depends(get_async_db)):
    if not batch.batch_no:
        batch.batch_no = await get_next_batch_number(db)
        
    db_batch = models.Batch(**batch.dict())
    db.add(db_batch)
    await db.commit()
    await db.refresh(db_batch)
    return db_batch

@router.get("/summary", response_model=List[schemas.BatchSummary])
async def read_batches_summary(
    response: Response,
    skip: int = 0,
    limit: int = 100,
    client: Optional[str] = None,
    batch_no: Optional[str] = None,
    filter_upload_date: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(check_module_permission("bvs", "verification", action="read"))
):
    # 1. Subquery for Case counts per batch
    case_counts = select(
        models.Case.batch_id,
        func.count(models.Case.id).label("actual_case_count"),
        func.sum(case((models.Case.status != models.CaseStatus.COMPLETED, 1), else_=0)).label("total_pending_count"),
        func.sum(case((models.Case.status == models.CaseStatus.PENDING, 1), else_=0)).label("pending_arrival_count"),
        func.sum(case((models.Case.status == models.CaseStatus.VERIFICATION, 1), else_=0)).label("verification_active_count"),
        func.sum(case((models.Case.status == models.CaseStatus.QC, 1), else_=0)).label("qc_active_count"),
        func.sum(case((models.Case.status == models.CaseStatus.QA_PENDING, 1), else_=0)).label("qa_pending_count"),
        func.sum(case((models.Case.status == models.CaseStatus.COMPLETED, 1), else_=0)).label("completed_count"),
        func.sum(case((models.Case.status.in_([models.CaseStatus.VERIFICATION, models.CaseStatus.QC]), 1), else_=0)).label("in_progress_count"),
        func.max(models.Case.completed_date).label("completed_date")
    ).group_by(models.Case.batch_id).subquery()

    # 2. Subquery for Check values
    check_values = select(
        models.Case.batch_id,
        func.sum(models.VerificationCheck.rate).label("total_check_value")
    ).join(models.VerificationCheck, models.Case.id == models.VerificationCheck.case_id)\
     .group_by(models.Case.batch_id).subquery()

    # 3. Main query
    stmt = select(
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
        case_counts.c.total_pending_count,
        case_counts.c.pending_arrival_count,
        case_counts.c.verification_active_count,
        case_counts.c.qc_active_count,
        case_counts.c.qa_pending_count,
        case_counts.c.completed_count,
        case_counts.c.in_progress_count,
        case_counts.c.completed_date,
        check_values.c.total_check_value
    ).join(models.Customer, models.Batch.customer_id == models.Customer.id)\
     .outerjoin(case_counts, models.Batch.id == case_counts.c.batch_id)\
     .outerjoin(check_values, models.Batch.id == check_values.c.batch_id)

    if client: stmt = stmt.filter(models.Customer.name.ilike(f"%{client}%"))
    if batch_no: stmt = stmt.filter(models.Batch.batch_no.ilike(f"%{batch_no}%"))
    if filter_upload_date: stmt = stmt.filter(func.date(models.Batch.upload_date) == filter_upload_date)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar() or 0
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"

    stmt = stmt.order_by(models.Batch.upload_date.desc()).offset(skip).limit(limit)
    res = await db.execute(stmt)
    results = res.all()

    summaries = []
    now = datetime.now()
    for r in results:
        age = (now.date() - (r.upload_date or now).date()).days
        total_value = float(r.total_check_value or 0)
        if total_value == 0 and r.case_rate and r.cases_count:
            total_value = r.case_rate * r.cases_count

        # Operational Status Hierarchy Logic
        if (r.total_pending_count or 0) == 0 and (r.actual_case_count or 0) >= (r.cases_count or 0):
            batch_status = "Completed"
        elif (r.qa_pending_count or 0) > 0:
            batch_status = "QA Pending"
        elif (r.qc_active_count or 0) > 0:
            batch_status = "In QC Stage"
        elif (r.verification_active_count or 0) > 0:
            batch_status = "Verifying"
        elif (r.actual_case_count or 0) < (r.cases_count or 0):
            batch_status = "Partial Entry"
        elif (r.pending_arrival_count or 0) > 0:
            batch_status = "Ready for Verif"
        else:
            batch_status = "Entry Pending"

        summaries.append({
            "id": r.id,
            "batch_no": r.batch_no,
            "customer_id": r.customer_id,
            "customer_name": r.customer_name,
            "upload_date": r.upload_date,
            "case_count": r.actual_case_count or 0,
            "intended_cases": r.cases_count or 0,
            "case_rate": r.case_rate or 0,
            "age_days": max(0, age),
            "pending_count": r.pending_arrival_count or 0,
            "verification_active_count": int(r.verification_active_count or 0),
            "qc_active_count": int(r.qc_active_count or 0),
            "qa_pending_count": int(r.qa_pending_count or 0),
            "completed_count": int(r.completed_count or 0),
            "tat": r.tat_days or 10,
            "total_value": total_value,
            "completed_date": r.completed_date,
            "file_url": r.file_url,
            "status": batch_status
        })
    return summaries

@router.get("/clients", response_model=List[str], dependencies=[Depends(check_module_permission("bvs", "batch", action="read"))])
async def read_batch_clients(db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.Customer.name).distinct().join(models.Batch)
    res = await db.execute(stmt)
    return [r for r in res.scalars().all() if r]

@router.get("", response_model=List[schemas.Batch], dependencies=[Depends(check_module_permission("bvs", "batch", action="read"))])
async def read_batches(response: Response, skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_async_db)):
    count_res = await db.execute(select(func.count(models.Batch.id)))
    response.headers["X-Total-Count"] = str(count_res.scalar() or 0)
    res = await db.execute(select(models.Batch).offset(skip).limit(limit))
    return res.scalars().all()

@router.get("/{batch_id}", response_model=schemas.Batch, dependencies=[Depends(check_module_permission("bvs", "batch", action="read"))])
async def read_batch(batch_id: str, db: AsyncSession = Depends(get_async_db)):
    res = await db.execute(select(models.Batch).filter(models.Batch.id == batch_id))
    db_batch = res.scalar_one_or_none()
    if db_batch is None: raise HTTPException(404, "Batch not found")
    return db_batch

@router.patch("/{batch_id}", response_model=schemas.Batch, dependencies=[Depends(check_module_permission("bvs", "batch", action="write"))])
async def update_batch(batch_id: str, batch_update: schemas.BatchUpdate, db: AsyncSession = Depends(get_async_db)):
    res = await db.execute(select(models.Batch).filter(models.Batch.id == batch_id))
    db_batch = res.scalar_one_or_none()
    if db_batch is None: raise HTTPException(404, "Batch not found")
    for k, v in batch_update.dict(exclude_unset=True).items(): setattr(db_batch, k, v)
    await db.commit()
    await db.refresh(db_batch)
    return db_batch

@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(check_module_permission("bvs", "batch", action="write"))])
async def delete_batch(batch_id: str, db: AsyncSession = Depends(get_async_db)):
    res = await db.execute(select(models.Batch).filter(models.Batch.id == batch_id))
    db_batch = res.scalar_one_or_none()
    if db_batch is None: raise HTTPException(404, "Batch not found")
    
    # Cascade delete manual logic (or reliance on DB FKs)
    ids_res = await db.execute(select(models.Case.id).filter(models.Case.batch_id == batch_id))
    case_ids = ids_res.scalars().all()
    if case_ids:
        await db.execute(delete(models.VerificationCheck).where(models.VerificationCheck.case_id.in_(case_ids)))
        await db.execute(delete(models.Case).where(models.Case.id.in_(case_ids)))
    
    await db.delete(db_batch)
    await db.commit()
    return None
