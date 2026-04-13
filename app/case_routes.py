from fastapi import APIRouter, Depends, HTTPException, status, Response, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, update, delete
from sqlalchemy.orm import contains_eager, joinedload, selectinload
from typing import List, Optional, Dict, Any
from . import models, schemas
from .database import get_async_db, SessionLocal
import uuid
from datetime import datetime
from fastapi.responses import StreamingResponse
import requests
from pypdf import PdfWriter, PdfReader
from io import BytesIO

from .auth_routes import check_module_permission, limiter, get_current_user

router = APIRouter(
    prefix="/cases",
    tags=["cases"]
)

@router.post("", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def create_case(case: schemas.CaseCreate, db: AsyncSession = Depends(get_async_db)):
    if not case.case_ref_no:
        customer_res = await db.execute(select(models.Customer).filter(models.Customer.id == case.customer_id))
        customer = customer_res.scalar_one_or_none()
        customer_name = customer.name if customer and customer.name else "BGV"
        prefix = customer_name[:3].upper()
        
        count_res = await db.execute(select(func.count(models.Case.id)).filter(models.Case.customer_id == case.customer_id))
        count = count_res.scalar() or 0
        case.case_ref_no = f"{prefix}{str(count + 1).zfill(3)}"
        
    db_case = models.Case(**case.dict())
    db.add(db_case)
    await db.commit()
    res = await db.execute(
        select(models.Case).options(
            joinedload(models.Case.candidate),
            joinedload(models.Case.customer),
            selectinload(models.Case.checks)
        ).filter(models.Case.id == db_case.id)
    )
    db_case = res.unique().scalar_one()

    return db_case

@router.post("/create-full", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def create_case_full(case_data: schemas.CaseCreateExtended, db: AsyncSession = Depends(get_async_db)):
    # 1. Create/Get Candidate
    candidate_dict = case_data.candidate.dict()
    db_candidate = models.Candidate(**candidate_dict)
    db.add(db_candidate)
    await db.flush() # Get candidate ID

    # 2. Create Case
    if not case_data.case_ref_no:
        customer_res = await db.execute(select(models.Customer).filter(models.Customer.id == case_data.customer_id))
        customer = customer_res.scalar_one_or_none()
        customer_name = customer.name if customer and customer.name else "BGV"
        prefix = customer_name[:3].upper()
        count_res = await db.execute(select(func.count(models.Case.id)).filter(models.Case.customer_id == case_data.customer_id))
        count = count_res.scalar() or 0
        case_ref = f"{prefix}{str(count + 1).zfill(3)}"
    else:
        case_ref = case_data.case_ref_no

    db_case = models.Case(
        case_ref_no=case_ref,
        customer_id=case_data.customer_id,
        candidate_id=db_candidate.id,
        batch_id=case_data.batch_id,
        status=models.CaseStatus.PENDING,
        received_date=datetime.utcnow()
    )
    db.add(db_case)
    await db.flush()

    # 3. Create Verification Checks
    for service in case_data.services:
        rate = case_data.check_rates.get(service, 0.0) if case_data.check_rates else 0.0
        db_check = models.VerificationCheck(
            case_id=db_case.id,
            check_type=service,
            status=models.CheckStatus.INTERIM,
            rate=rate
        )
        db.add(db_check)
    
    await db.commit()
    
    # Reload with relationships for response validation
    stmt = select(models.Case).options(
        joinedload(models.Case.candidate),
        joinedload(models.Case.customer),
        selectinload(models.Case.checks)
    ).filter(models.Case.id == db_case.id)
    res = await db.execute(stmt)
    return res.unique().scalar_one()

@router.get("", response_model=List[schemas.CaseRead], dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
async def read_cases(
    response: Response,
    status: Optional[models.CaseStatus] = None, 
    batch_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    search: Optional[str] = None,
    search_name: Optional[str] = None,
    search_ref: Optional[str] = None,
    assigned: Optional[bool] = None,
    skip: int = 0, 
    limit: int = 200, 
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Base query for cases with their relationships
    stmt = select(models.Case).outerjoin(models.Case.candidate).options(
        contains_eager(models.Case.candidate),
        joinedload(models.Case.customer),
        joinedload(models.Case.batch),
        joinedload(models.Case.assigned_user),
        selectinload(models.Case.checks)
    )

    # 2. Assignment-based filtering (Data Isolation)
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.ADMIN, models.UserRole.MANAGER]:
        stmt = stmt.filter(models.Case.assigned_to == current_user.id)
    
    if status:
        stmt = stmt.filter(models.Case.status == status)
    if batch_id:
        stmt = stmt.filter(models.Case.batch_id == batch_id)
    if customer_id:
        stmt = stmt.filter(models.Case.customer_id == customer_id)
    if search:
        stmt = stmt.filter(or_(models.Case.case_ref_no.ilike(f"%{search}%"), models.Candidate.name.ilike(f"{search}%")))
    if search_name:
        stmt = stmt.filter(models.Candidate.name.ilike(f"{search_name}%"))
    if search_ref:
        stmt = stmt.filter(models.Case.case_ref_no.ilike(f"%{search_ref}%"))
    if assigned is not None:
        if assigned:
            stmt = stmt.filter(models.Case.assigned_to != None)
        else:
            stmt = stmt.filter(models.Case.assigned_to == None)
    
    # 2. Results
    count_stmt = select(func.count(func.distinct(models.Case.id))).select_from(stmt.subquery())
    total_count_res = await db.execute(count_stmt)
    total_count = total_count_res.scalar() or 0
    response.headers["X-Total-Count"] = str(total_count)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"

    stmt = stmt.order_by(models.Case.received_date.desc()).offset(skip).limit(limit)
    res = await db.execute(stmt)
    cases_models = res.unique().scalars().all()
    
    # 3. Transform to CaseRead format
    cases_read = []
    for case in cases_models:
        case_data = schemas.CaseRead.model_validate(case)
        if case.candidate: case_data.candidate_name = case.candidate.name
        if case.customer: case_data.customer_name = case.customer.name
        if case.batch:
            if not case_data.tat_days: case_data.tat_days = case.batch.tat_days
            case_data.batch_date = case.batch.upload_date
            case_data.batch_no = case.batch.batch_no
        if case.assigned_user: case_data.assigned_user_name = case.assigned_user.full_name
        cases_read.append(case_data)
    
    return cases_read

@router.get("/clients", response_model=List[str], dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
async def read_case_clients(db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.Customer.name).distinct().join(models.Case)
    res = await db.execute(stmt)
    return [r for r in res.scalars().all() if r]

@router.get("/report-stats", dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
async def get_report_stats(customer_id: Optional[str] = None, db: AsyncSession = Depends(get_async_db)):
    # 1. Pie Data: Status distribution
    stmt = select(models.Case.status, func.count(models.Case.id)).group_by(models.Case.status)
    if customer_id: stmt = stmt.filter(models.Case.customer_id == customer_id)
    res = await db.execute(stmt)
    pie_data = [{"name": str(s), "value": count} for s, count in res.all()]

    # 2. Aggregates
    base_stmt = select(models.Case)
    if customer_id: base_stmt = base_stmt.filter(models.Case.customer_id == customer_id)
    
    total_res = await db.execute(select(func.count(models.Case.id)).select_from(base_stmt.subquery()))
    total = total_res.scalar() or 0
    
    comp_res = await db.execute(select(func.count(models.Case.id)).filter(models.Case.status == models.CaseStatus.COMPLETED).select_from(base_stmt.subquery()))
    completed = comp_res.scalar() or 0
    
    tat_res = await db.execute(select(func.avg(models.Case.tat_days)).filter(models.Case.status == models.CaseStatus.COMPLETED).select_from(base_stmt.subquery()))
    avg_tat = tat_res.scalar() or 0

    return {
        "pie_data": pie_data,
        "total_cases": total,
        "completion_rate": round((completed / total * 100), 1) if total > 0 else 0,
        "avg_tat": round(float(avg_tat), 1)
    }

@router.get("/{case_id}", response_model=schemas.CaseRead, dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
async def read_case(case_id: str, db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.Case).options(
        joinedload(models.Case.candidate),
        joinedload(models.Case.customer),
        selectinload(models.Case.checks),
        joinedload(models.Case.batch)
    ).filter(models.Case.id == case_id)
    res = await db.execute(stmt)
    db_case = res.unique().scalar_one_or_none()
    
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
        
    case_data = schemas.CaseRead.model_validate(db_case)
    if db_case.candidate: case_data.candidate_name = db_case.candidate.name
    if db_case.customer: case_data.customer_name = db_case.customer.name
    if db_case.batch:
        case_data.batch_no = db_case.batch.batch_no
        case_data.batch_date = db_case.batch.upload_date
    return case_data

@router.patch("/{case_id}", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def update_case(case_id: str, case_update: schemas.CaseUpdate, db: AsyncSession = Depends(get_async_db)):
    res = await db.execute(select(models.Case).filter(models.Case.id == case_id))
    db_case = res.scalar_one_or_none()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    
    update_data = case_update.dict(exclude_unset=True)
    if update_data.get("status") == models.CaseStatus.COMPLETED and db_case.status != models.CaseStatus.COMPLETED:
        db_case.completed_date = datetime.utcnow()
    elif update_data.get("status") and update_data.get("status") != models.CaseStatus.COMPLETED:
        db_case.completed_date = None
        
    for key, value in update_data.items():
        setattr(db_case, key, value)
    
    await db.commit()
    res = await db.execute(
        select(models.Case).options(
            joinedload(models.Case.candidate),
            joinedload(models.Case.customer),
            selectinload(models.Case.checks)
        ).filter(models.Case.id == db_case.id)
    )
    db_case = res.unique().scalar_one()

    return db_case

@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def delete_case(case_id: str, db: AsyncSession = Depends(get_async_db)):
    res = await db.execute(select(models.Case).filter(models.Case.id == case_id))
    db_case = res.scalar_one_or_none()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    
    candidate_id = db_case.candidate_id
    
    # Delete related checks first (cascade)
    await db.execute(delete(models.VerificationCheck).filter(models.VerificationCheck.case_id == case_id))
    
    # Delete the case
    await db.delete(db_case)
    
    # Check if candidate has other cases, if not, delete candidate
    if candidate_id:
        other_cases_res = await db.execute(select(func.count(models.Case.id)).filter(models.Case.candidate_id == candidate_id, models.Case.id != case_id))
        count = other_cases_res.scalar() or 0
        if count == 0:
            await db.execute(delete(models.Candidate).filter(models.Candidate.id == candidate_id))
            
    await db.commit()
    return None

from .aws_utils import s3_client, aws_bucket

def _do_merge(case_id: str, docs: list, candidate_name: str, case_ref: str):
    """Sync Background Task for PDF Merge."""
    import logging
    merger = PdfWriter()
    for doc in docs:
        url = doc.get('url')
        if not url: continue
        try:
            content = requests.get(url, timeout=15).content
            if url.lower().endswith('.pdf'):
                merger.append(PdfReader(BytesIO(content)))
            else:
                from PIL import Image
                img = Image.open(BytesIO(content)).convert('RGB')
                buf = BytesIO(); img.save(buf, format='PDF'); buf.seek(0)
                merger.append(PdfReader(buf))
        except Exception as e: logging.error(f"Merge error: {e}")
    
    if len(merger.pages) > 0:
        out = BytesIO(); merger.write(out); out.seek(0)
        filename = f"{candidate_name}_{case_ref}_merged.pdf"
        if s3_client and aws_bucket:
            s3_key = f"merged/{case_id}/{filename}"
            s3_client.put_object(Bucket=aws_bucket, Key=s3_key, Body=out.getvalue(), ContentType='application/pdf')
            db = SessionLocal()
            c = db.query(models.Case).filter(models.Case.id == case_id).first()
            if c: c.merged_pdf_key = s3_key; db.commit()
            db.close()

@router.post("/{case_id}/merge-pdfs", status_code=202, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
@limiter.limit("10/minute")
async def merge_pdfs(case_id: str, request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_async_db)):
    res = await db.execute(select(models.Case).options(joinedload(models.Case.candidate)).filter(models.Case.id == case_id))
    db_case = res.unique().scalar_one_or_none()
    if not db_case or not db_case.candidate:
        raise HTTPException(status_code=404, detail="Case/Candidate not found")
    
    docs = db_case.candidate.documents or []
    background_tasks.add_task(_do_merge, case_id, docs, db_case.candidate.name, db_case.case_ref_no)
    return {"message": "PDF merge queued"}

@router.post("/bulk-allocate")
async def bulk_allocate(data: Dict[str, Any], db: AsyncSession = Depends(get_async_db)):
    case_ids = data.get("case_ids", [])
    user_id = data.get("user_id")
    if not user_id and user_id is not None: raise HTTPException(400, "User ID required")
    await db.execute(update(models.Case).where(models.Case.id.in_(case_ids)).values(assigned_to=user_id))
    await db.commit()
    return {"message": "Success"}
