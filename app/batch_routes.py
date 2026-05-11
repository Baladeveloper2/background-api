
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, update, delete, or_
from sqlalchemy.exc import IntegrityError

from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
from . import models, schemas
from .database import get_async_db
from .auth_routes import check_module_permission, limiter
from .cache import cache_response, clear_cache
from datetime import datetime

router = APIRouter(
    prefix="/batches",
    tags=["batches"]
)

async def get_next_batch_number(db: AsyncSession):
    year = datetime.now().year
    # Use a more descriptive prefix
    prefix = f"Batch_{year}_"
    
    # Extract only the sequence part using SQL if possible, or just fetch max
    stmt = select(func.max(models.Batch.batch_no)).filter(models.Batch.batch_no.like(f"{prefix}%"))
    res = await db.execute(stmt)
    max_bn = res.scalar()
    
    max_seq = 0
    if max_bn and '_' in max_bn:
        try:
            parts = max_bn.split('_')
            # The sequence is expected at the end: Batch_YYYY_SEQ
            if len(parts) >= 3:
                # Ensure we handle non-numeric parts gracefully
                seq_str = parts[-1]
                if seq_str.isdigit():
                    max_seq = int(seq_str)
        except (ValueError, IndexError):
            pass
            
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
        
    if not batch.cl_ref_no:
        customer_res = await db.execute(select(models.Customer).filter(models.Customer.id == batch.customer_id))
        customer = customer_res.scalar_one_or_none()
        sc = customer.short_code if customer and customer.short_code else (customer.name[:3].upper() if customer else "CL")
        
        # Count existing batches for this customer to get next sequence
        count_res = await db.execute(select(func.count(models.Batch.id)).filter(models.Batch.customer_id == batch.customer_id))
        count = count_res.scalar() or 0
        batch.cl_ref_no = f"CL-{sc}-{(count + 1):03d}"
        
    db_batch = models.Batch(**batch.dict())
    db.add(db_batch)
    try:
        await db.commit()
        await db.refresh(db_batch)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch number '{batch.batch_no}' or CL Ref '{batch.cl_ref_no}' already exists."
        )
    
    # Bust summary cache so new batch appears immediately
    await clear_cache("batches")
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
    current_user: models.User = Depends(check_module_permission("bvs", "batch", action="read"))
):
    # 1. Subquery for Case counts per batch
    case_counts = select(
        models.Batch.id.label("batch_uuid"),
        func.count(models.Case.id).label("actual_case_count"),
        func.sum(case((models.Case.status != models.CaseStatus.COMPLETED, 1), else_=0)).label("total_pending_count"),
        func.sum(case((models.Case.status == models.CaseStatus.PENDING, 1), else_=0)).label("pending_arrival_count"),
        func.sum(case((models.Case.status == models.CaseStatus.VERIFICATION, 1), else_=0)).label("verification_active_count"),
        func.sum(case((models.Case.status == models.CaseStatus.QC, 1), else_=0)).label("qc_active_count"),
        func.sum(case((models.Case.status == models.CaseStatus.QA_PENDING, 1), else_=0)).label("qa_pending_count"),
        func.sum(case((models.Case.status == models.CaseStatus.DOCUMENTS_SUBMITTED, 1), else_=0)).label("docs_submitted_count"),
        func.sum(case((models.Case.status == models.CaseStatus.LINK_SHARED, 1), else_=0)).label("link_shared_count"),
        func.sum(case((models.Case.status == models.CaseStatus.COMPLETED, 1), else_=0)).label("completed_count"),
        func.sum(case((models.Case.status.in_([models.CaseStatus.VERIFICATION, models.CaseStatus.QC]), 1), else_=0)).label("in_progress_count"),
        func.max(models.Case.completed_date).label("completed_date")
    ).select_from(models.Case).join(
        models.Batch, 
        or_(models.Case.batch_id == models.Batch.id, models.Case.batch_id == models.Batch.batch_no)
    ).group_by(models.Batch.id).subquery()

    # 2. Subquery for Check values
    check_values = select(
        models.Batch.id.label("batch_uuid"),
        func.sum(models.VerificationCheck.rate).label("total_check_value")
    ).select_from(models.Case).join(
        models.VerificationCheck, models.Case.id == models.VerificationCheck.case_id
    ).join(
        models.Batch,
        or_(models.Case.batch_id == models.Batch.id, models.Case.batch_id == models.Batch.batch_no)
    ).group_by(models.Batch.id).subquery()

    # 3. Main query
    stmt = select(
        models.Batch.id,
        models.Batch.batch_no,
        models.Batch.cl_ref_no,
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
        case_counts.c.docs_submitted_count,
        case_counts.c.link_shared_count,
        case_counts.c.completed_count,
        case_counts.c.in_progress_count,
        case_counts.c.completed_date,
        check_values.c.total_check_value
    ).join(models.Customer, models.Batch.customer_id == models.Customer.id)\
     .outerjoin(case_counts, models.Batch.id == case_counts.c.batch_uuid)\
     .outerjoin(check_values, models.Batch.id == check_values.c.batch_uuid)

    if client: stmt = stmt.filter(models.Customer.name.ilike(f"%{client}%"))
    if batch_no: stmt = stmt.filter(models.Batch.batch_no.ilike(f"%{batch_no}%"))
    if filter_upload_date: stmt = stmt.filter(func.date(models.Batch.upload_date) == filter_upload_date)
    
    # Tenancy check
    user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
    if user_role == "CUSTOMER" or (current_user.role_rel and current_user.role_rel.name.upper() == "CUSTOMER"):
        stmt = stmt.filter(models.Batch.customer_id == current_user.customer_id)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar() or 0
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"

    stmt = stmt.order_by(models.Batch.upload_date.desc(), models.Batch.batch_no.desc()).offset(skip).limit(limit)
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
        actual_count = int(r.actual_case_count or 0)
        intended_count = int(r.cases_count or 0)
        pending_total = int(r.total_pending_count or 0)

        if pending_total == 0 and actual_count > 0:
            batch_status = "Completed"
        elif (r.verification_active_count or 0) > 0 or (r.qc_active_count or 0) > 0 or (r.qa_pending_count or 0) > 0 or (r.docs_submitted_count or 0) > 0 or (r.link_shared_count or 0) > 0:
            batch_status = "In Progress"
        elif actual_count >= intended_count and actual_count > 0:
            batch_status = "Data Entry Completed"
        else:
            batch_status = "In Progress"

        summaries.append({
            "id": r.id,
            "batch_no": r.batch_no,
            "cl_ref_no": r.cl_ref_no,
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
    stmt = select(models.Customer.name).distinct()
    res = await db.execute(stmt)
    return sorted([r for r in res.scalars().all() if r])

@router.get("", response_model=List[schemas.Batch], dependencies=[Depends(check_module_permission("bvs", "batch", action="read"))])
async def read_batches(response: Response, skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_async_db), current_user: models.User = Depends(check_module_permission("bvs", "batch", action="read"))):
    stmt = select(models.Batch)
    user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
    if user_role == "CUSTOMER" or (current_user.role_rel and current_user.role_rel.name.upper() == "CUSTOMER"):
        stmt = stmt.filter(models.Batch.customer_id == current_user.customer_id)
        
    count_res = await db.execute(select(func.count()).select_from(stmt.subquery()))
    response.headers["X-Total-Count"] = str(count_res.scalar() or 0)
    res = await db.execute(stmt.offset(skip).limit(limit))
    return res.scalars().all()

@router.get("/{batch_id}", response_model=schemas.Batch, dependencies=[Depends(check_module_permission("bvs", "batch", action="read"))])
async def read_batch(batch_id: str, db: AsyncSession = Depends(get_async_db), current_user: models.User = Depends(check_module_permission("bvs", "batch", action="read"))):
    res = await db.execute(select(models.Batch).filter(models.Batch.id == batch_id))
    db_batch = res.scalar_one_or_none()
    if db_batch is None: raise HTTPException(404, "Batch not found")
    
    # Tenancy check
    user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
    if (user_role == "CUSTOMER" or (current_user.role_rel and current_user.role_rel.name.upper() == "CUSTOMER")) and db_batch.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Unauthorized access to this batch")
        
    return db_batch

@router.patch("/{batch_id}", response_model=schemas.Batch, dependencies=[Depends(check_module_permission("bvs", "batch", action="write"))])
async def update_batch(batch_id: str, batch_update: schemas.BatchUpdate, db: AsyncSession = Depends(get_async_db)):
    res = await db.execute(select(models.Batch).filter(models.Batch.id == batch_id))
    db_batch = res.scalar_one_or_none()
    if db_batch is None: raise HTTPException(404, "Batch not found")
    for k, v in batch_update.dict(exclude_unset=True).items(): setattr(db_batch, k, v)
    await db.commit()
    await db.refresh(db_batch)
    await clear_cache("batches")
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
    await clear_cache("batches")
    return None
