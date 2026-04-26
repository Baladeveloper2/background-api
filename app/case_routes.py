from fastapi import APIRouter, Depends, HTTPException, status, Response, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, update, delete
from sqlalchemy.orm import contains_eager, joinedload, selectinload
from typing import List, Optional, Dict, Any
from . import models, schemas, enums
from .database import get_async_db, SessionLocal
import uuid
import asyncio
from datetime import datetime, timedelta
from fastapi.responses import StreamingResponse
import requests
import httpx
from pypdf import PdfWriter, PdfReader
from io import BytesIO
import pandas as pd
import io
from .ocr_utils import get_scanner
from . import notification_utils
from .ws import manager
from .cache import delete_cache, cache_response
from .auth_routes import check_module_permission, limiter, get_current_user, create_audit_log
from . import tat_utils
from .logging_config import logger

router = APIRouter(
    prefix="/cases",
    tags=["cases"]
)

@router.post("/bulk-mark-insufficient")
async def bulk_mark_insufficient(data: dict[str, Any], background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_async_db), current_user: models.User = Depends(get_current_user)):
    case_ids = data.get("case_ids", [])
    reason = data.get("reason", "Incomplete documentation")
    
    if not case_ids:
        raise HTTPException(status_code=400, detail="No cases selected")

    # Update cases
    await db.execute(
        update(models.Case)
        .where(models.Case.id.in_(case_ids))
        .values(status=enums.CaseStatus.INSUFFICIENT, comments=reason)
    )

    # Fetch assigned users to notify them their work is on hold
    stmt = select(models.Case).filter(models.Case.id.in_(case_ids))
    res = await db.execute(stmt)
    cases = res.scalars().all()

    notified_users = set()
    for c in cases:
        if c.assigned_to:
            notified_users.add(c.assigned_to)
            await notification_utils.create_notification(
                db, c.assigned_to,
                "Case Marked Insufficient",
                f"Protocol {c.case_ref_no} has been moved to Insufficiency: {reason}",
                enums.NotificationCategory.INSUFFICIENT_DOCS,
                case_id=c.id,
                background_tasks=background_tasks
            )
        
        # Audit Log
        log = models.AuditLog(
            user_id=current_user.id,
            action="BULK_INSUFFICIENT",
            details=f"Case {c.case_ref_no} flagged as insufficient: {reason}",
            resource_id=c.id
        )
        db.add(log)

    await db.commit()
    
    # Global workforce update signal
    await manager.broadcast({"type": "WORKFORCE_UPDATE", "source": "bulk_insufficient"})
    
    return {"message": f"Successfully moved {len(case_ids)} cases to Insufficiency.", "notified_user_count": len(notified_users)}

@router.get("/export")
async def export_mis_data(
    status: Optional[str] = None,
    customer_id: Optional[str] = None,
    customer_name: Optional[str] = None,
    search: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Generates structured MIS Excel report for cases."""
    try:
        stmt = select(models.Case).options(
            joinedload(models.Case.candidate),
            joinedload(models.Case.customer),
            joinedload(models.Case.assigned_user)
        )
        
        # Join Customer if client_name or search is used
        if customer_name or search:
            stmt = stmt.join(models.Customer, models.Case.customer_id == models.Customer.id)

        # RBAC for Customers
        user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
        role_name = (current_user.role_rel.name.upper() if current_user.role_rel else "").upper()
        if user_role == "CUSTOMER" or role_name == "CUSTOMER":
            stmt = stmt.filter(models.Case.customer_id == current_user.customer_id)
        else:
            if customer_id:
                stmt = stmt.filter(models.Case.customer_id == customer_id)
            if customer_name:
                stmt = stmt.filter(models.Customer.name == customer_name)

        if status and status != 'ALL':
            stmt = stmt.filter(models.Case.status == status)
        
        if search:
            stmt = stmt.join(models.Candidate).filter(or_(
                models.Case.case_ref_no.ilike(f"%{search}%"),
                models.Candidate.name.ilike(f"%{search}%")
            ))

        if from_date:
            try:
                f_date = datetime.strptime(from_date, "%Y-%m-%d")
                stmt = stmt.filter(models.Case.received_date >= f_date)
            except: pass
        if to_date:
            try:
                t_date = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                stmt = stmt.filter(models.Case.received_date <= t_date)
            except: pass

        stmt = stmt.order_by(models.Case.received_date.desc())
        res = await db.execute(stmt)
        # Using yield_per for memory efficiency if the driver supports it
        cases_gen = res.unique().scalars()

        output = io.BytesIO()
        import xlsxwriter
        workbook = xlsxwriter.Workbook(output, {'constant_memory': True, 'in_memory': True})
        worksheet = workbook.add_worksheet('Case MIS')
        
        # Headers
        headers = ["Case ID", "Candidate Name", "Client Name", "Status", "Received Date", "Completed Date", "Assigned To", "TAT (Days)", "SLA Status", "In-TAT Days", "Out-TAT Days"]
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)

        row_idx = 1
        from datetime import timezone
        now_dt = datetime.now(timezone.utc)

        for c in cases_gen:
            # Calculate In-TAT/Out-TAT
            total_days = 0
            if c.received_date:
                r_date = c.received_date
                if r_date.tzinfo is None: r_date = r_date.replace(tzinfo=timezone.utc)
                    
                e_date = c.completed_date or now_dt
                if e_date.tzinfo is None: e_date = e_date.replace(tzinfo=timezone.utc)
                    
                total_days = (e_date.date() - r_date.date()).days + 1
                total_days = max(1, total_days)
            
            allowed = c.tat_days or 10
            in_tat_days = total_days if total_days <= allowed else allowed
            out_tat_days = 0 if total_days <= allowed else total_days - allowed

            worksheet.write(row_idx, 0, c.case_ref_no)
            worksheet.write(row_idx, 1, c.candidate.name if c.candidate else "N/A")
            worksheet.write(row_idx, 2, c.customer.name if c.customer else "N/A")
            worksheet.write(row_idx, 3, c.status)
            worksheet.write(row_idx, 4, c.received_date.strftime("%Y-%m-%d %H:%M") if c.received_date else "N/A")
            worksheet.write(row_idx, 5, c.completed_date.strftime("%Y-%m-%d %H:%M") if c.completed_date else "In Progress")
            worksheet.write(row_idx, 6, c.assigned_user.full_name if c.assigned_user else "Unallocated")
            worksheet.write(row_idx, 7, allowed)
            worksheet.write(row_idx, 8, "In-TAT" if c.is_in_tat == 1 else "Out-TAT")
            worksheet.write(row_idx, 9, in_tat_days)
            worksheet.write(row_idx, 10, out_tat_days)
            row_idx += 1

        workbook.close()
        output.seek(0)
        
        filename = f"MIS_Export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        return StreamingResponse(
            output, 
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}, 
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f"Error exporting MIS data: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{case_id}/history", dependencies=[Depends(get_current_user)])
@cache_response(ttl=300, key_prefix="case_history")
async def get_case_history(case_id: str, db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.AuditLog, models.User.full_name).join(models.User, models.AuditLog.user_id == models.User.id).filter(models.AuditLog.resource_id == case_id).order_by(models.AuditLog.timestamp.desc())
    res = await db.execute(stmt)
    history = []
    for log, name in res.all():
        history.append({
            "id": log.id,
            "action": log.action,
            "details": log.details,
            "timestamp": log.timestamp,
            "user_name": name
        })
    return history

@router.post("", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def create_case(case: schemas.CaseCreate, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_async_db), current_user: models.User = Depends(get_current_user)):
    if not case.case_ref_no:
        customer_res = await db.execute(select(models.Customer).filter(models.Customer.id == case.customer_id))
        customer = customer_res.scalar_one_or_none()
        customer_name = customer.name if customer and customer.name else "BGV"
        prefix = customer_name[:3].upper()
        
        count_res = await db.execute(select(func.count(models.Case.id)).filter(models.Case.customer_id == case.customer_id))
        count = count_res.scalar() or 0
        case.case_ref_no = f"{prefix}{str(count + 1).zfill(3)}"
        
    # For Customer role, force their own customer_id
    user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
    if user_role == "CUSTOMER" or (current_user.role_rel and current_user.role_rel.name.upper() == "CUSTOMER"):
        case.customer_id = current_user.customer_id

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
    
    # Trigger Background Summary Refresh
    from .stats_service import refresh_dashboard_summary
    background_tasks.add_task(refresh_dashboard_summary, db, db_case.customer_id)

    return db_case

@router.post("/create-full", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def create_case_full(case_data: schemas.CaseCreateExtended, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_async_db), current_user: models.User = Depends(get_current_user)):
    # 1. Create/Get Candidate
    candidate_dict = case_data.candidate.dict()
    db_candidate = models.Candidate(**candidate_dict)
    db.add(db_candidate)
    await db.flush() # Get candidate ID

    # 2. Create Case with Collision-Aware Reference Generation
    if not case_data.case_ref_no:
        customer_res = await db.execute(select(models.Customer).filter(models.Customer.id == case_data.customer_id))
        customer = customer_res.scalar_one_or_none()
        customer_name = customer.name if customer and customer.name else "BGV"
        prefix = customer_name[:3].upper()
        
        # Get the current total count to start with
        count_res = await db.execute(select(func.count(models.Case.id)).filter(models.Case.customer_id == case_data.customer_id))
        count = count_res.scalar() or 0
        
        # Collision loop: Ensure unique reference number
        suffix_num = count + 1
        while True:
            case_ref = f"{prefix}{str(suffix_num).zfill(3)}"
            exists_res = await db.execute(select(models.Case.id).filter(models.Case.case_ref_no == case_ref))
            if not exists_res.scalar_one_or_none():
                break
            suffix_num += 1
    else:
        case_ref = case_data.case_ref_no

    # For Customer role, force their own customer_id
    user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
    target_customer_id = current_user.customer_id if (user_role == "CUSTOMER" or (current_user.role_rel and current_user.role_rel.name.upper() == "CUSTOMER")) else case_data.customer_id

    db_case = models.Case(
        case_ref_no=case_ref,
        customer_id=target_customer_id,
        candidate_id=db_candidate.id,
        batch_id=case_data.batch_id,
        status=models.CaseStatus.PENDING,
        received_date=datetime.utcnow(),
        file_no=case_data.file_no
    )
    db.add(db_case)
    await db.flush()

    # 3. Create Verification Checks
    for service in case_data.services:
        rate = case_data.check_rates.get(service, 0.0) if case_data.check_rates else 0.0
        # Get scope from map or global field
        check_scope = case_data.scope_of_work
        if case_data.check_scopes and service in case_data.check_scopes:
            check_scope = case_data.check_scopes[service]
            
        db_check = models.VerificationCheck(
            case_id=db_case.id,
            check_type=service,
            status=models.CheckStatus.VERIFICATION,
            rate=rate,
            data={"scope_of_work": check_scope} if check_scope else {}
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
    db_case = res.unique().scalar_one()

    # Trigger Background Summary Refresh
    from .stats_service import refresh_dashboard_summary
    background_tasks.add_task(refresh_dashboard_summary, db, db_case.customer_id)

    return db_case

@router.get("/allocation-stats", dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
async def get_allocation_stats(db: AsyncSession = Depends(get_async_db)):
    unallocated_stmt = select(func.count(models.Case.id)).filter(models.Case.assigned_to == None)
    allocated_stmt = select(func.count(models.Case.id)).filter(models.Case.assigned_to != None)
    
    unallocated_res = await db.execute(unallocated_stmt)
    allocated_res = await db.execute(allocated_stmt)
    
    return {
        "unallocated": unallocated_res.scalar() or 0,
        "allocated": allocated_res.scalar() or 0
    }

@router.get("/recommend-allocation")
async def recommend_allocation(db: AsyncSession = Depends(get_async_db)):
    """
    Analyzes workforce capacity and suggests the best verifiers for new assignments
    based on current load and completion trends.
    """
    # 1. Fetch all Verifiers
    stmt = select(models.User).filter(models.User.role == enums.UserRole.VERIFIER)
    res = await db.execute(stmt)
    verifiers = res.scalars().all()
    
    recommendations = []
    for v in verifiers:
        # Get active load
        load_res = await db.execute(select(func.count(models.Case.id)).filter(models.Case.assigned_to == v.id, models.Case.status.in_([enums.CaseStatus.VERIFICATION])))
        active_load = load_res.scalar() or 0
        
        # Get recent completions (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        comp_res = await db.execute(select(func.count(models.Case.id)).filter(models.Case.assigned_to == v.id, models.Case.completed_date >= seven_days_ago))
        velocity = comp_res.scalar() or 0
        
        # Calculate Score (Lower is better for assignment)
        # Score = Active Load / (Velocity + 1)
        score = active_load / (velocity + 1)
        
        recommendations.append({
            "user_id": v.id,
            "full_name": v.full_name,
            "active_load": active_load,
            "velocity_7d": velocity,
            "efficiency_score": round(float(score), 2),
            "recommend_rank": 0 # Placeholder
        })
        
    # Sort by score ascending
    recommendations.sort(key=lambda x: x["efficiency_score"])
    for i, rec in enumerate(recommendations):
        rec["recommend_rank"] = i + 1
        
    return recommendations

@router.post("/scan-escalations")
async def scan_escalations(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_async_db)):
    """
    Scans for cases that have crossed the Risk threshold and dispatches alerts.
    """
    # 1. Fetch all cases in transition (Verification or QC)
    stmt = select(models.Case).options(selectinload(models.Case.checks)).filter(models.Case.status.in_([enums.CaseStatus.VERIFICATION, enums.CaseStatus.QC]))
    res = await db.execute(stmt)
    cases = res.scalars().all()
    
    escalation_count: int = 0
    assigned_user_ids = set()
    
    for c in cases:
        if not c.received_date or not c.assigned_to:
            continue
            
        # Calculate Predictive TAT
        check_types = [chk.check_type for chk in c.checks]
        p_tat = tat_utils.calculate_predictive_tat(check_types)
        
        # Check if At Risk
        if tat_utils.check_is_at_risk(c.received_date, p_tat):
            # Dispatch Alert
            await notification_utils.notify_at_risk(
                db, c.assigned_to, 
                c.case_ref_no, 
                c.id, 
                p_tat,
                background_tasks=background_tasks
            )
            escalation_count = escalation_count + 1
            assigned_user_ids.add(c.assigned_to)
            
    await db.commit()
    return {"message": f"Scan complete. Dispatched {escalation_count} risk alerts to {len(assigned_user_ids)} team members."}

@router.post("/case/ping/{case_id}")
async def ping_case(case_id: str, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_async_db), current_user: models.User = Depends(get_current_user)):
    """
    Manually ping a verifier for a specific case.
    """
    stmt = select(models.Case).filter(models.Case.id == case_id)
    res = await db.execute(stmt)
    case_obj = res.scalar_one_or_none()
    
    if not case_obj:
        raise HTTPException(404, detail="Case not found")
    
    if not case_obj.assigned_to:
        raise HTTPException(400, detail="Case is not assigned to any verifier")
        
    await notification_utils.notify_ping(
        db, 
        case_obj.assigned_to, 
        case_obj.case_ref_no, 
        case_obj.id, 
        current_user.full_name or current_user.email,
        background_tasks=background_tasks
    )
    
    await db.commit()
    return {"message": f"Urgent ping dispatched to verifier for Case {case_obj.case_ref_no}"}

@router.get("", response_model=List[schemas.CaseRead], dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
async def read_cases(
    response: Response,
    status: Optional[models.CaseStatus] = None, 
    batch_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    customer_name: Optional[str] = None,
    search: Optional[str] = None,
    search_name: Optional[str] = None,
    search_ref: Optional[str] = None,
    assigned: Optional[bool] = None,
    assigned_to: Optional[str] = None,
    exclude_completed: Optional[bool] = None,
    skip: int = 0, 
    limit: int = 200, 
    sort: str = "received_date",
    order: str = "desc",
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Base query for cases with their relationships - Standardized Loading for Async
    stmt = select(models.Case).options(
        selectinload(models.Case.candidate),
        selectinload(models.Case.customer),
        selectinload(models.Case.batch),
        selectinload(models.Case.assigned_user).joinedload(models.User.role_rel),
        selectinload(models.Case.qa_user),
        selectinload(models.Case.qc_user),
        selectinload(models.Case.checks)
    )

    # Apply joins for filtering/sorting if needed (using selectinload for data, join for query)
    stmt = stmt.outerjoin(models.Case.candidate).outerjoin(models.Case.customer)


    # 2. Count for pagination - Optimized to avoid unnecessary joins
    base_count_stmt = select(func.count(models.Case.id))
    # Only join if we are filtering by fields in those tables
    if search or search_name or customer_name:
        base_count_stmt = base_count_stmt.outerjoin(models.Case.candidate).outerjoin(models.Case.customer)

    # Determine permission profile
    user_role_raw = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
    # Normalize: strip enum class name if present (e.g., 'USERROLE.QA' -> 'QA')
    user_role_clean = user_role_raw.split('.')[-1]
    
    role_rel_name = (current_user.role_rel.name.upper() if current_user.role_rel else "").upper()
    
    oversight_keywords = ["SUPER_ADMIN", "ADMIN", "MANAGER", "QA", "QC", "SUPER ADMIN", "QC VERIFIER"]
    is_oversight = any(k in user_role_clean for k in oversight_keywords) or \
                   any(k in role_rel_name for k in oversight_keywords)
    
    is_customer = "CUSTOMER" in user_role_clean or "CUSTOMER" in role_rel_name

    # Combined filtering logic
    if is_customer:
        stmt = stmt.filter(models.Case.customer_id == current_user.customer_id)
        base_count_stmt = base_count_stmt.filter(models.Case.customer_id == current_user.customer_id)
    elif not is_oversight:
        # For restricted users (Verifiers), show cases where they are involved in ANY capacity
        personal_filter = or_(
            models.Case.assigned_to == current_user.id,
            models.Case.qa_id == current_user.id,
            models.Case.qc_id == current_user.id
        )
        stmt = stmt.filter(personal_filter)
        base_count_stmt = base_count_stmt.filter(personal_filter)
    
    if status:
        stmt = stmt.filter(models.Case.status == status)
        base_count_stmt = base_count_stmt.filter(models.Case.status == status)
    if batch_id:
        stmt = stmt.filter(models.Case.batch_id == batch_id)
        base_count_stmt = base_count_stmt.filter(models.Case.batch_id == batch_id)
    if customer_id:
        stmt = stmt.filter(models.Case.customer_id == customer_id)
        base_count_stmt = base_count_stmt.filter(models.Case.customer_id == customer_id)
    if customer_name:
        stmt = stmt.filter(models.Customer.name == customer_name)
        base_count_stmt = base_count_stmt.filter(models.Customer.name == customer_name)
    if assigned_to:
        involvement_filter = or_(
            models.Case.assigned_to == assigned_to,
            models.Case.qa_id == assigned_to,
            models.Case.qc_id == assigned_to
        )
        stmt = stmt.filter(involvement_filter)
        base_count_stmt = base_count_stmt.filter(involvement_filter)
    if search:
        f = or_(models.Case.case_ref_no.ilike(f"%{search}%"), models.Candidate.name.ilike(f"{search}%"))
        stmt = stmt.filter(f)
        base_count_stmt = base_count_stmt.filter(f)
    if search_name:
        stmt = stmt.filter(models.Candidate.name.ilike(f"{search_name}%"))
        base_count_stmt = base_count_stmt.filter(models.Candidate.name.ilike(f"{search_name}%"))
    if search_ref:
        stmt = stmt.filter(models.Case.case_ref_no.ilike(f"%{search_ref}%"))
        base_count_stmt = base_count_stmt.filter(models.Case.case_ref_no.ilike(f"%{search_ref}%"))
    if assigned is not None:
        if assigned:
            active_filter = [models.Case.assigned_to != None, models.Case.status.notin_(['COMPLETED', 'completed', 'Completed'])]
            stmt = stmt.filter(*active_filter)
            base_count_stmt = base_count_stmt.filter(*active_filter)
        else:
            unassigned_filter = [models.Case.assigned_to == None, models.Case.status.notin_(['COMPLETED', 'completed', 'Completed'])]
            stmt = stmt.filter(*unassigned_filter)
            base_count_stmt = base_count_stmt.filter(*unassigned_filter)
    
    if exclude_completed:
        comp_filter = [models.Case.status.notin_(['COMPLETED', 'completed', 'Completed'])]
        stmt = stmt.filter(*comp_filter)
        base_count_stmt = base_count_stmt.filter(*comp_filter)
    


    total_count_res = await db.execute(base_count_stmt)
    total_count = total_count_res.scalar() or 0
    response.headers["X-Total-Count"] = str(total_count)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"

    # 4. Sorting logic
    sort_attr = getattr(models.Case, sort, None)
    if sort_attr is None:
        sort_attr = models.Case.received_date
        
    if order == "desc":
        stmt = stmt.order_by(sort_attr.desc())
    else:
        stmt = stmt.order_by(sort_attr.asc())
        
    stmt = stmt.offset(skip).limit(limit)
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
        if case.assigned_user: 
            case_data.assigned_user_name = case.assigned_user.full_name
            r_enum_val = str(case.assigned_user.role.value if hasattr(case.assigned_user.role, 'value') else case.assigned_user.role).upper()
            role_name = case.assigned_user.role_rel.name if case.assigned_user.role_rel else ("QC Verifier" if r_enum_val in ["QA", "QC"] else r_enum_val)
            case_data.assigned_user_role = role_name.upper()
        if case.qa_user: case_data.qa_user_name = case.qa_user.full_name
        if case.qc_user: case_data.qc_user_name = case.qc_user.full_name
        
        else:
            case_data.queue_age = "0h"
        
        # Calculate In-TAT/Out-TAT
        if case.received_date:
            from datetime import timezone
            now_dt = datetime.now(timezone.utc)
            
            r_date = case.received_date
            if r_date.tzinfo is None:
                r_date = r_date.replace(tzinfo=timezone.utc)
                
            e_date = case.completed_date or now_dt
            if e_date.tzinfo is None:
                e_date = e_date.replace(tzinfo=timezone.utc)
                
            diff_seconds = (e_date - r_date).total_seconds()
            # Use inclusive calendar days for TAT
            total_days = (e_date.date() - r_date.date()).days + 1
            total_days = max(1, total_days)
            
            allowed = case_data.tat_days or 10
            if total_days <= allowed:
                case_data.in_tat = total_days
                case_data.out_tat = 0
            else:
                case_data.in_tat = allowed
                case_data.out_tat = total_days - allowed
            
            # Predictive TAT Analysis
            check_types = [c.check_type for c in case.checks]
            p_tat = tat_utils.calculate_predictive_tat(check_types)
            case_data.predicted_tat = p_tat
            # Suppress risk alerts for archived protocols
            if str(case.status).upper() == "COMPLETED":
                case_data.is_at_risk = False
            else:
                case_data.is_at_risk = tat_utils.check_is_at_risk(case.received_date, p_tat)
            
        
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
        "completion_rate": float(round(float(completed / total * 100), 1)) if total > 0 else 0.0,
        "avg_tat": float(round(float(avg_tat or 0), 1))
    }

@router.get("/{case_id}", response_model=schemas.CaseRead, dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
async def read_case(case_id: str, db: AsyncSession = Depends(get_async_db), current_user: models.User = Depends(get_current_user)):
    stmt = select(models.Case).options(
        joinedload(models.Case.candidate),
        joinedload(models.Case.customer),
        selectinload(models.Case.checks),
        joinedload(models.Case.batch),
        joinedload(models.Case.assigned_user).joinedload(models.User.role_rel),
        joinedload(models.Case.qa_user),
        joinedload(models.Case.qc_user)
    ).filter(models.Case.id == case_id)
    res = await db.execute(stmt)
    db_case = res.unique().scalar_one_or_none()
    
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Tenancy/Isolation check
    user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
    if (user_role == "CUSTOMER" or (current_user.role_rel and current_user.role_rel.name.upper() == "CUSTOMER")) and db_case.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Unauthorized access to this case")
    if current_user.role == models.UserRole.VERIFIER and db_case.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized access to this case")
        
    # Dynamic fix for media visibility: Populate candidate.documents from address_details if empty
    if db_case.candidate and (not db_case.candidate.documents) and db_case.candidate.address_details:
        all_docs = []
        doc_mapping = {
            'addresses': 'Address',
            'employments': 'Employment',
            'educations': 'Education',
            'identities': 'Identity',
            'references': 'Reference',
            'criminal_records': 'Criminal',
            'drug_tests': 'Drug Test',
            'cibil_checks': 'CIBIL',
            'global_database_checks': 'Global Database'
        }
        
        addr_details = db_case.candidate.address_details
        for key, check_label in doc_mapping.items():
            section_items = addr_details.get(key, [])
            if isinstance(section_items, list):
                for item in section_items:
                    if isinstance(item, dict) and 'files' in item and isinstance(item['files'], list):
                        for f in item['files']:
                            if isinstance(f, dict):
                                doc_item = f.copy()
                                doc_item['check_type'] = check_label
                                all_docs.append(doc_item)
        
        db_case.candidate.documents = all_docs

    case_data = schemas.CaseRead.model_validate(db_case)
    if db_case.candidate: case_data.candidate_name = db_case.candidate.name
    if db_case.customer: case_data.customer_name = db_case.customer.name
    if db_case.batch:
        case_data.batch_no = db_case.batch.batch_no
        case_data.batch_date = db_case.batch.upload_date
    if db_case.assigned_user: 
        case_data.assigned_user_name = db_case.assigned_user.full_name
        r_enum_val = str(db_case.assigned_user.role.value if hasattr(db_case.assigned_user.role, 'value') else db_case.assigned_user.role).upper()
        role_name = db_case.assigned_user.role_rel.name if db_case.assigned_user.role_rel else ("QC Verifier" if r_enum_val in ["QA", "QC"] else r_enum_val)
        case_data.assigned_user_role = role_name.upper()
    if db_case.qc_user: case_data.qc_user_name = db_case.qc_user.full_name

    # Calculate In-TAT/Out-TAT for single view
    if db_case.received_date:
        from datetime import timezone
        now_dt = datetime.now(timezone.utc)
        
        r_date = db_case.received_date
        if r_date.tzinfo is None:
            r_date = r_date.replace(tzinfo=timezone.utc)
            
        e_date = db_case.completed_date or now_dt
        if e_date.tzinfo is None:
            e_date = e_date.replace(tzinfo=timezone.utc)
            
        diff_seconds = (e_date - r_date).total_seconds()
        # Use inclusive calendar days for TAT
        total_days = (e_date.date() - r_date.date()).days + 1
        total_days = max(1, total_days)
        allowed = case_data.tat_days or 10
        
        if total_days <= allowed:
            case_data.in_tat = total_days
            case_data.out_tat = 0
        else:
            case_data.in_tat = allowed
            case_data.out_tat = total_days - allowed

    return case_data
class BulkActionRequest(schemas.BaseModel):
    case_ids: List[str]
    action: str
    target_value: Optional[str] = None

@router.post("/face-match")
async def face_match(req: dict, current_user: models.User = Depends(get_current_user)):
    url1 = req.get("url1") # ID Photo
    url2 = req.get("url2") # Profile/Selfie Photo
    
    if not url1 or not url2:
        return {"success": False, "message": "Missing URLs"}
        
    try:
        from .ocr_utils import get_scanner
        
        scanner = get_scanner()
        
        # Download images asynchronously
        async with httpx.AsyncClient() as client:
            r1, r2 = await asyncio.gather(
                client.get(url1, timeout=10.0),
                client.get(url2, timeout=10.0)
            )
        
        if r1.status_code != 200 or r2.status_code != 200:
            return {"success": False, "message": "Failed to download images"}
            
        face1 = scanner.get_face(r1.content)
        face2 = scanner.get_face(r2.content)
        
        if face1 is None: return {"success": False, "message": "No face detected in Image 1"}
        if face2 is None: return {"success": False, "message": "No face detected in Image 2"}
        
        score = scanner.match_faces(face1, face2)
        
        return {
            "success": True,
            "match_score": round(score, 2),
            "is_match": score > 60, # Threshold for match
            "message": "Match successful" if score > 60 else "Potential mismatch"
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.post("/bulk-action", dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def bulk_action(req: schemas.BulkActionRequest, db: AsyncSession = Depends(get_async_db), current_user: models.User = Depends(get_current_user)):
    if not req.case_ids:
        return {"msg": "No cases provided"}
        
    update_data: Dict[str, Any] = {}
    if req.action == "assign":
        update_data["assigned_to"] = req.target_value
        update_data["assigned_at"] = datetime.utcnow()
    elif req.action == "status":
        update_data["status"] = req.target_value
        if req.target_value == models.CaseStatus.COMPLETED:
            update_data["completed_date"] = datetime.utcnow()
            # Attribute audit/completion to the actor
            if current_user.role == models.UserRole.QC:
                update_data["qc_id"] = current_user.id
            if current_user.role == models.UserRole.QA:
                update_data["qa_id"] = current_user.id
            
    if not update_data:
        return {"msg": "Invalid action"}
        
    from .ws import manager
    # Revoke Logic for Bulk
    if req.action == "status":
        for cid in req.case_ids:
            res_c = await db.execute(select(models.Case).filter(models.Case.id == cid))
            case_obj = res_c.scalar_one_or_none()
            if not case_obj: continue
            
            # QC Revoke: Moving back from QC or Completed
            if (case_obj.status in [models.CaseStatus.QC, models.CaseStatus.COMPLETED]) and req.target_value in [models.CaseStatus.VERIFICATION, models.CaseStatus.PENDING]:
                case_obj.qc_revoke_count += 1
                db.add(models.RevokeLog(
                    case_id=cid,
                    user_id=current_user.id,
                    revoke_type='QC',
                    from_status=case_obj.status,
                    to_status=req.target_value
                ))
            
            # QA/Lead Revoke: Moving back from QA to QC or Verifier
            if case_obj.status == models.CaseStatus.QA_PENDING and req.target_value in [models.CaseStatus.QC, models.CaseStatus.VERIFICATION, models.CaseStatus.PENDING]:
                # We'll treat QA-initiated revokes as QC revokes for the purpose of the current tracking dashboard
                case_obj.qc_revoke_count += 1
                db.add(models.RevokeLog(
                    case_id=cid,
                    user_id=current_user.id,
                    revoke_type='QC',
                    from_status=case_obj.status,
                    to_status=req.target_value
                ))
                
            # Insufficiency Logic: Marking as insufficient
            if req.target_value == models.CaseStatus.INSUFFICIENT and case_obj.status != models.CaseStatus.INSUFFICIENT:
                case_obj.insufficiency_count += 1
                db.add(models.InsufficiencyLog(
                    case_id=cid,
                    user_id=current_user.id,
                    from_status=case_obj.status,
                    notes="Bulk marked as insufficient"
                ))
            
            # Resolution Logic: Moving out of insufficient
            if case_obj.status == models.CaseStatus.INSUFFICIENT and req.target_value != models.CaseStatus.INSUFFICIENT:
                # Update latest log with resolution time
                res_log_stmt = select(models.InsufficiencyLog).filter(models.InsufficiencyLog.case_id == cid).order_by(models.InsufficiencyLog.marked_at.desc())
                res_log_exec = await db.execute(res_log_stmt)
                latest_log = res_log_exec.scalars().first()
                if latest_log and not latest_log.resolved_at:
                    latest_log.resolved_at = datetime.utcnow()

            # Update status and dates
            case_obj.status = req.target_value
            if req.target_value == models.CaseStatus.COMPLETED:
                case_obj.completed_date = datetime.utcnow()
            else:
                case_obj.completed_date = None
            
            if req.target_value == models.CaseStatus.COMPLETED:
                # TAT Logic
                if case_obj.batch_id:
                    res_batch = await db.execute(select(models.Batch).filter(models.Batch.id == case_obj.batch_id))
                    batch = res_batch.scalar_one_or_none()
                    if batch and case_obj.received_date:
                        diff = (datetime.utcnow() - case_obj.received_date).days
                        case_obj.is_in_tat = 1 if diff <= (batch.tat_days or 10) else 0

    await db.commit()

    verifier_name = "Verifier"
    if req.action == "assign" and req.target_value:
        v_res = await db.execute(select(models.User).filter(models.User.id == req.target_value))
        v_obj = v_res.scalar_one_or_none()
        if v_obj: verifier_name = v_obj.full_name

    # Trigger Notifications for Bulk
    bulk_case_info = []
    for cid in req.case_ids:
        # Re-fetch for reference info with candidate
        ref_res = await db.execute(select(models.Case).options(joinedload(models.Case.candidate)).filter(models.Case.id == cid))
        cbd = ref_res.scalar_one_or_none()
        if not cbd: continue
        candidate_name = cbd.candidate.name if cbd.candidate else "Candidate"
        
        # Track for admin summary
        bulk_case_info.append({"id": cid, "ref": cbd.case_ref_no, "candidate": candidate_name})

        if req.action == "assign" and req.target_value:
             # Standard assignment logic...
             update_stmt = update(models.Case).where(models.Case.id == cid).values(assigned_to=req.target_value, assigned_at=datetime.utcnow() if not cbd.assigned_at else cbd.assigned_at)
             await db.execute(update_stmt)
             await create_audit_log(db, current_user.id, "CASE_ASSIGNMENT", f"Case bulk-assigned to verifier via system operator", resource_id=cid)
             await manager.broadcast({"type": "CASE_UPDATED", "case_id": cid, "action": "bulk-assignment", "assigned_to": req.target_value})
             await notification_utils.notify_new_assignment(db, req.target_value, cbd.case_ref_no, cid, candidate_name)
        elif req.action == "status":
            old_s = cbd.status.value if hasattr(cbd.status, 'value') else cbd.status
            new_s = req.target_value.value if hasattr(req.target_value, 'value') else req.target_value
            await create_audit_log(db, current_user.id, "STATUS_CHANGE", f"Case status bulk-updated from {old_s} to {new_s}", resource_id=cid)
            if req.target_value == models.CaseStatus.INSUFFICIENT:
                await notification_utils.notify_insufficient(db, cbd.assigned_to, cbd.case_ref_no, cid)
            elif req.target_value == models.CaseStatus.COMPLETED:
                await notification_utils.notify_case_closed(db, cid, cbd.case_ref_no, candidate_name)
            elif req.target_value == models.CaseStatus.QC:
                await notification_utils.notify_verification_completed(db, cid, cbd.case_ref_no, candidate_name, current_user.full_name)

    # Notify Admin ONE summary instead of many small ones
    if req.action == "assign" and req.target_value:
        await notification_utils.create_notification(
            db, current_user.id,
            "Bulk Allocation Finalized",
            f"Successfully deployed {len(req.case_ids)} cases to {verifier_name}. All mission protocols are now active in the verifier queue.",
            enums.NotificationCategory.SYSTEM_ALERT,
            extra_data={"type": "BULK_ASSIGN", "verifier": verifier_name, "cases": bulk_case_info}
        )
    
    await db.commit()
    
    # Trigger Real-time Workforce Update
    await manager.broadcast({"type": "WORKFORCE_UPDATE", "source": "bulk_allocation"})
    
    return {"message": "Bulk allocation successful"}
    
    # Audit log and broadcast
@router.post("/auto-allocate")
async def auto_allocate(req: schemas.BulkActionRequest, db: AsyncSession = Depends(get_async_db), current_user: models.User = Depends(get_current_user)):
    if not req.case_ids:
        return {"msg": "No cases provided"}
        
    # 1. Fetch available verifiers
    res_users = await db.execute(select(models.User).filter(models.User.role == models.UserRole.VERIFIER, models.User.status == "ACTIVE"))
    verifiers = res_users.scalars().all()
    
    if not verifiers:
        return {"msg": "No active verifiers found", "success": False}
        
    # 2. Get current workloads
    # This counts cases with status PENDING or VERIFICATION assigned to each verifier
    workloads = {}
    for v in verifiers:
        count_res = await db.execute(select(func.count(models.Case.id)).filter(models.Case.assigned_to == v.id, models.Case.status != models.CaseStatus.COMPLETED))
        workloads[v.id] = count_res.scalar() or 0
        
    # 3. Assign cases greedily to verifier with least cases
    assigned_count = 0
    auto_assigned_info = []
    
    for cid in req.case_ids:
        # Find verifier with minimum workload
        target_v_id = min(workloads, key=workloads.get)
        
        # Update case
        await db.execute(
            update(models.Case).where(models.Case.id == cid).values(
                assigned_to=target_v_id,
                assigned_at=datetime.utcnow()
            )
        )
        
        # Increment workload for next iteration
        workloads[target_v_id] += 1
        assigned_count += 1
        
        # Audit log and broadcast
        await create_audit_log(db, current_user.id, "AUTO_ALLOCATION", f"Case automatically assigned to verifier", resource_id=cid)
        await manager.broadcast({"type": "CASE_UPDATED", "case_id": cid, "action": "auto-assignment"})
        
        # Trigger Notification
        ref_res = await db.execute(select(models.Case).options(joinedload(models.Case.candidate)).filter(models.Case.id == cid))
        cbd = ref_res.scalar_one()
        candidate_name = cbd.candidate.name if cbd.candidate else "Candidate"
        
        v_name = "Verifier"
        v_obj = next((u for u in verifiers if u.id == target_v_id), None)
        if v_obj: v_name = v_obj.full_name
            
        auto_assigned_info.append({"id": cid, "ref": cbd.case_ref_no, "candidate": candidate_name, "verifier": v_name})
        await notification_utils.notify_new_assignment(db, target_v_id, cbd.case_ref_no, cid, candidate_name)

    # Notify Admin ONE summary
    await notification_utils.create_notification(
        db, current_user.id,
        "Auto-Allocation Protocol Executed",
        f"Distributed {assigned_count} cases across active operational units. System load balancing complete.",
        enums.NotificationCategory.SYSTEM_ALERT,
        extra_data={"type": "AUTO_ALLOCATE", "cases": auto_assigned_info}
    )
    
    await db.commit()
    return {"msg": f"Successfully auto-allocated {assigned_count} cases", "success": True}

@router.patch("/{case_id}", response_model=schemas.Case, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def update_case(case_id: str, case_update: schemas.CaseUpdate, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_async_db), current_user: models.User = Depends(get_current_user)):
    stmt = select(models.Case).options(
        selectinload(models.Case.checks),
        joinedload(models.Case.candidate)
    ).filter(models.Case.id == case_id)
    res = await db.execute(stmt)
    db_case = res.scalar_one_or_none()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    
    old_status = db_case.status
    
    update_data = case_update.dict(exclude_unset=True)
    candidate_update_data = update_data.pop("candidate", None)
    services_update = update_data.pop("services", None)
    rates_update = update_data.pop("check_rates", {})
    scope_of_work = update_data.pop("scope_of_work", None)
    check_scopes = update_data.pop("check_scopes", None) or {}

    manual_received_date = update_data.get("received_date")
    manual_completed_date = update_data.get("completed_date")

    if update_data.get("status") == models.CaseStatus.COMPLETED and db_case.status != models.CaseStatus.COMPLETED:
        db_case.completed_date = manual_completed_date or datetime.utcnow()
        # TAT Performance tracking
        if db_case.batch_id and db_case.received_date:
            res_batch = await db.execute(select(models.Batch).filter(models.Batch.id == db_case.batch_id))
            batch = res_batch.scalar_one_or_none()
            if batch:
                diff = (datetime.utcnow() - db_case.received_date).days
                db_case.is_in_tat = 1 if diff <= (batch.tat_days or 10) else 0
        
        # Attribute completion credit...
        if current_user.role == models.UserRole.QC:
            db_case.qc_id = current_user.id
        elif current_user.role == models.UserRole.QA:
            db_case.qa_id = current_user.id
    elif update_data.get("status") in [models.CaseStatus.QA_PENDING, models.CaseStatus.QC_PENDING] and db_case.status not in [models.CaseStatus.QA_PENDING, models.CaseStatus.QC_PENDING]:
         if current_user.role in [models.UserRole.QA, models.UserRole.QC]:
            db_case.qa_id = current_user.id
         # Auto-propagate to checks
         for chk in db_case.checks:
            if chk.status in [models.CheckStatus.VERIFICATION, models.CheckStatus.INTERIM]:
                chk.status = models.CheckStatus.QC_PENDING
    elif update_data.get("status") and update_data.get("status") != models.CaseStatus.COMPLETED:
        # Revoke Logic for Single Update
        # QC Revoke: from QC/QA/Completed to Verification/Pending
        if (db_case.status in [models.CaseStatus.QC, models.CaseStatus.QA_PENDING, models.CaseStatus.COMPLETED]) and update_data.get("status") in [models.CaseStatus.VERIFICATION, models.CaseStatus.PENDING]:
            db_case.qc_revoke_count += 1
            db.add(models.RevokeLog(
                case_id=case_id,
                user_id=current_user.id,
                revoke_type='QC',
                from_status=db_case.status,
                to_status=update_data.get('status')
            ))
            # Reset checks to WIP so verifier can re-verify
            for chk in db_case.checks:
                if chk.status == models.CheckStatus.QC_PENDING:
                    chk.status = models.CheckStatus.VERIFICATION
            
        # Transition Revoke: from Completed back to QC/QA
        if db_case.status == models.CaseStatus.COMPLETED and update_data.get("status") in [models.CaseStatus.QC, models.CaseStatus.QA_PENDING]:
            db_case.qc_revoke_count += 1
            db.add(models.RevokeLog(
                case_id=case_id,
                user_id=current_user.id,
                revoke_type='QC',
                from_status=db_case.status,
                to_status=update_data.get('status')
            ))

        # Insufficiency Logic: Marking as insufficient
        if update_data.get("status") == models.CaseStatus.INSUFFICIENT and db_case.status != models.CaseStatus.INSUFFICIENT:
            db_case.insufficiency_count += 1
            db.add(models.InsufficiencyLog(
                case_id=case_id,
                user_id=current_user.id,
                from_status=db_case.status,
                notes=update_data.get("notes", "Marked as insufficient")
            ))
        
        # Resolution Logic: Moving out of insufficient
        if db_case.status == models.CaseStatus.INSUFFICIENT and update_data.get("status") and update_data.get("status") != models.CaseStatus.INSUFFICIENT:
            # Update latest log with resolution time
            res_log_stmt = select(models.InsufficiencyLog).filter(models.InsufficiencyLog.case_id == case_id).order_by(models.InsufficiencyLog.marked_at.desc())
            res_log_exec = await db.execute(res_log_stmt)
            latest_log = res_log_exec.scalars().first()
            if latest_log and not latest_log.resolved_at:
                latest_log.resolved_at = datetime.utcnow()

        if manual_completed_date is None:
            db_case.completed_date = None
        else:
            db_case.completed_date = manual_completed_date

    if update_data.get("assigned_to") and not db_case.assigned_at:
        db_case.assigned_at = datetime.utcnow()

    for key, value in update_data.items():
        if getattr(db_case, key) != value:
            # Simple audit log for status changes
            if key == "status":
                old_val = db_case.status.value if hasattr(db_case.status, 'value') else db_case.status
                new_val = value.value if hasattr(value, 'value') else value
                await create_audit_log(db, current_user.id, "STATUS_CHANGE", f"Case status updated from {old_val} to {new_val}", resource_id=case_id)
            elif key == "assigned_to":
                await create_audit_log(db, current_user.id, "CASE_ASSIGNMENT", f"Case assigned to user ID {value}", resource_id=case_id)
        setattr(db_case, key, value)
    
    # Update or Create Candidate
    if candidate_update_data:
        if db_case.candidate_id:
            res_cand = await db.execute(select(models.Candidate).filter(models.Candidate.id == db_case.candidate_id))
            db_candidate = res_cand.scalar_one_or_none()
            if db_candidate:
                for key, value in candidate_update_data.items():
                    if value is not None:
                        setattr(db_candidate, key, value)
        else:
            # Create new candidate if missing
            db_candidate = models.Candidate(**candidate_update_data)
            db.add(db_candidate)
            await db.flush()
            db_case.candidate_id = db_candidate.id

    # Sync Services/Checks & Scope of Work
    
    if services_update is not None:
        # 1. Get existing checks
        existing_checks_res = await db.execute(select(models.VerificationCheck).filter(models.VerificationCheck.case_id == case_id))
        existing_checks = {c.check_type: c for c in existing_checks_res.scalars().all()}
        
        # 2. Add or Update checks
        for svc in services_update:
            rate = rates_update.get(svc, 0.0)
            svc_scope = check_scopes.get(svc, scope_of_work)
            
            if svc in existing_checks:
                # Update rate if provided
                existing_checks[svc].rate = rate
                # Also update scope_of_work if provided (either per-check or global)
                if svc_scope is not None:
                    updated_data = dict(existing_checks[svc].data or {})
                    updated_data["scope_of_work"] = svc_scope
                    existing_checks[svc].data = updated_data
            else:
                # Create new
                new_check = models.VerificationCheck(
                    case_id=case_id,
                    check_type=svc,
                    status=models.CheckStatus.INTERIM,
                    rate=rate,
                    data={"scope_of_work": svc_scope} if svc_scope else {}
                )
                db.add(new_check)
        
        # 3. Remove checks not in services_update
        for svc_type in list(existing_checks.keys()):
            if svc_type not in services_update:
                await db.delete(existing_checks[svc_type])
    elif check_scopes or scope_of_work:
        # Update scope for all existing checks if services list not provided
        existing_checks_res = await db.execute(select(models.VerificationCheck).filter(models.VerificationCheck.case_id == case_id))
        for chk in existing_checks_res.scalars().all():
            svc_scope = check_scopes.get(chk.check_type, scope_of_work)
            if svc_scope is not None:
                if chk.data is None: chk.data = {}
                chk.data["scope_of_work"] = svc_scope
    
    # 4. Trigger Notifications (Enhanced Stakeholder Flow)
    candidate_name = db_case.candidate.name if db_case.candidate else "Candidate"
    
    if "status" in update_data:
        new_status = update_data["status"]
        
        # Auto-set completion metadata
        if new_status == models.CaseStatus.COMPLETED:
            if not db_case.completed_date:
                db_case.completed_date = datetime.utcnow()
            if not db_case.qc_id:
                db_case.qc_id = current_user.id
        
        # Scenario 1: Verifier finishes -> Moves to QC
        if old_status == models.CaseStatus.VERIFICATION and new_status == models.CaseStatus.QC:
            await notification_utils.notify_verification_completed(db, case_id, db_case.case_ref_no, candidate_name, current_user.full_name)
        
        # Scenario 2: QC finishes -> Moves to Completed
        elif old_status == models.CaseStatus.QC and new_status == models.CaseStatus.COMPLETED:
            await notification_utils.notify_qc_completed(db, case_id, db_case.case_ref_no, candidate_name, current_user.full_name)
            await notification_utils.notify_case_closed(db, case_id, db_case.case_ref_no, candidate_name)
        
        # Scenario 3: General Completion (In case it jumps to completed)
        elif old_status != models.CaseStatus.COMPLETED and new_status == models.CaseStatus.COMPLETED:
            await notification_utils.notify_case_closed(db, case_id, db_case.case_ref_no, candidate_name)

        # Scenario 4: Insufficient Flags
        elif new_status == models.CaseStatus.INSUFFICIENT:
            await notification_utils.notify_insufficient(db, db_case.assigned_to, db_case.case_ref_no, case_id)

    if "assigned_to" in update_data and update_data["assigned_to"]:
        await notification_utils.notify_new_assignment(db, update_data["assigned_to"], db_case.case_ref_no, case_id, candidate_name)

    await db.commit()
    res = await db.execute(
        select(models.Case).options(
            joinedload(models.Case.candidate),
            joinedload(models.Case.customer),
            selectinload(models.Case.checks)
        ).filter(models.Case.id == db_case.id)
    )
    db_case = res.unique().scalar_one()

    # Trigger Background Summary Refresh
    from .stats_service import refresh_dashboard_summary
    background_tasks.add_task(refresh_dashboard_summary, db, db_case.customer_id)
    
    return db_case

@router.get("/{resource_id}/verification-logs", response_model=List[schemas.AuditLogRead], dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
async def get_verification_logs(resource_id: str, db: AsyncSession = Depends(get_async_db)):
    # Note: I used DATABASE_get_async_db to avoid conflict with local variable if any, 
    # but the import is actually get_async_db in this file. Correcting to get_async_db.
    stmt = (
        select(models.AuditLog, models.User.full_name.label("user_full_name"))
        .outerjoin(models.User, models.AuditLog.user_id == models.User.id)
        .filter(models.AuditLog.resource_id == resource_id)
        .order_by(models.AuditLog.timestamp.desc())
    )
    res = await db.execute(stmt)
    results = []
    for log, full_name in res.all():
        log_data = schemas.AuditLogRead.model_validate(log)
        log_data.user_full_name = full_name
        results.append(log_data)
    return results

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
async def merge_pdfs(case_id: str, request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_async_db), current_user: models.User = Depends(get_current_user)):
    res = await db.execute(select(models.Case).options(joinedload(models.Case.candidate)).filter(models.Case.id == case_id))
    db_case = res.unique().scalar_one_or_none()
    if not db_case or not db_case.candidate:
        raise HTTPException(status_code=404, detail="Case/Candidate not found")
    
    # Tenancy check
    user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
    if (user_role == "CUSTOMER" or (current_user.role_rel and current_user.role_rel.name.upper() == "CUSTOMER")) and db_case.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Unauthorized access to this case")
    
    docs = db_case.candidate.documents or []
    background_tasks.add_task(_do_merge, case_id, docs, db_case.candidate.name, db_case.case_ref_no)
    return {"message": "PDF merge queued"}

@router.post("/bulk-allocate")
async def bulk_allocate(data: dict[str, Any], background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_async_db), current_user: models.User = Depends(get_current_user)):
    case_ids = data.get("case_ids", [])
    user_id = data.get("user_id")
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Bulk allocate requested for user_id: {user_id}, case_count: {len(case_ids)}")
    
    update_vals = {
        "assigned_to": user_id,
        "assigned_at": datetime.utcnow() if user_id else None,
        "status": models.CaseStatus.VERIFICATION if user_id else models.CaseStatus.PENDING
    }
    
    await db.execute(
        update(models.Case)
        .where(models.Case.id.in_(case_ids))
        .values(**update_vals)
    )
    
    # Trigger Real-time Notifications & Broadcasts
    if user_id:
        v_res = await db.execute(select(models.User).filter(models.User.id == user_id))
        v_obj = v_res.scalar_one_or_none()
        verifier_name = v_obj.full_name if v_obj else "Verifier"

        bulk_info = []
        for cid in case_ids:
            ref_res = await db.execute(select(models.Case).options(joinedload(models.Case.candidate)).filter(models.Case.id == cid))
            cbd = ref_res.scalar_one_or_none()
            if not cbd: continue
            
            candidate_name = cbd.candidate.name if cbd.candidate else "Candidate"
            bulk_info.append({"id": cid, "ref": cbd.case_ref_no, "candidate": candidate_name})
            await notification_utils.notify_new_assignment(db, user_id, cbd.case_ref_no, cid, candidate_name, background_tasks=background_tasks)
            await manager.broadcast({"type": "CASE_UPDATED", "case_id": cid, "action": "allocation"})

        # Notify Admin ONE summary
        await notification_utils.create_notification(
            db, current_user.id,
            "Allocation Strategy Finalized",
            f"Successfully deployed {len(case_ids)} cases to {verifier_name}. Mission protocols are now active.",
            enums.NotificationCategory.SYSTEM_ALERT,
            extra_data={"type": "BULK_ALLOCATE", "verifier": verifier_name, "cases": bulk_info}
        )

    await db.commit()
    await manager.broadcast({"type": "WORKFORCE_UPDATE", "source": "bulk_allocation"})
    return {"message": "Success"}

@router.post("/ocr-extract")
async def ocr_extract(data: Dict[str, str], background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_async_db)):
    url = data.get("url")
    if not url: raise HTTPException(status_code=400, detail="Document URL required")
    
    try:
        import requests
        import logging
        logger = logging.getLogger(__name__)
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch document")
            
        from .ocr_utils import get_scanner
        scanner = get_scanner()
        text = scanner.reader.readtext(response.content, detail=0)
        full_text = " ".join(text)
        
        # Basic parsing
        extracted = scanner.parse_id(full_text)
        
        return {
            "success": True,
            "extracted_data": extracted,
            "raw_text_debug": str(full_text)[:500] 
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{case_id}/ai-summary")
async def generate_ai_summary(case_id: str, db: AsyncSession = Depends(get_async_db), current_user: models.User = Depends(get_current_user)):
    stmt = select(models.Case).options(
        joinedload(models.Case.candidate),
        selectinload(models.Case.checks)
    ).filter(models.Case.id == case_id)
    
    res = await db.execute(stmt)
    db_case = res.unique().scalar_one_or_none()
    if not db_case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    # Tenancy Check
    user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
    if (user_role == "CUSTOMER" or (current_user.role_rel and current_user.role_rel.name.upper() == "CUSTOMER")) and db_case.customer_id != current_user.customer_id:
        raise HTTPException(status_code=403, detail="Unauthorized access to this case")
        
    checks = db_case.checks
    summary_parts = []
    
    # 1. Overall Status
    status_counts = {}
    for c in checks:
        status_counts[c.status] = status_counts.get(c.status, 0) + 1
    
    overall = "GREEN" if status_counts.get("GREEN") == len(checks) else "AMBER" if status_counts.get("RED") else "GREEN"
    if status_counts.get("RED"): overall = "RED"
    
    name = db_case.candidate.name if db_case.candidate else "The candidate"
    summary_parts.append(f"Verification Summary for {name}:")
    summary_parts.append(f"The overall verification status is {overall}.")
    
    # 2. Key Findings
    findings = []
    for c in checks:
        if c.status == "GREEN":
            findings.append(f"• {c.check_type}: Verified successfully with no discrepancies.")
        elif c.status == "RED":
            findings.append(f"• {c.check_type}: CRITICAL DISCREPANCY FOUND. {c.verifier_remarks or 'Verification failed.'}")
        elif c.status == "AMBER":
            findings.append(f"• {c.check_type}: Minor discrepancy noted. {c.verifier_remarks or 'Check results were clear with minor remarks.'}")
        else:
            findings.append(f"• {c.check_type}: Verification is currently {c.status}.")
            
    summary_parts.extend(findings)
    
    # 3. Final Conclusion
    if overall == "GREEN":
        summary_parts.append("\nConclusion: All provided credentials and background details have been verified as authentic. The candidate is cleared for further processing.")
    elif overall == "RED":
        summary_parts.append("\nConclusion: Due to critical discrepancies found in one or more verification modules, extreme caution is advised. Further internal review is recommended.")
    else:
        summary_parts.append("\nConclusion: The verification process revealed minor inconsistencies. Please review the specific notes for each module.")
        
    full_summary = "\n".join(summary_parts)
    
    # Save to DB
    db_case.ai_summary = full_summary
    await db.commit()
    
    return {"summary": full_summary}

@router.get("/{case_id}/comments", response_model=List[schemas.CaseComment])
async def read_case_comments(case_id: str, db: AsyncSession = Depends(get_async_db)):
    stmt = (
        select(models.CaseComment, models.User.full_name.label("user_full_name"))
        .outerjoin(models.User, models.CaseComment.user_id == models.User.id)
        .filter(models.CaseComment.case_id == case_id)
        .order_by(models.CaseComment.created_at.asc())
    )
    res = await db.execute(stmt)
    results = []
    for comment, full_name in res.all():
        data = schemas.CaseComment.model_validate(comment)
        data.user_full_name = full_name
        results.append(data)
    return results

@router.post("/{case_id}/comments", response_model=schemas.CaseComment)
async def create_case_comment(
    case_id: str, 
    comment: schemas.CaseCommentCreate, 
    db: AsyncSession = Depends(get_async_db), 
    current_user: models.User = Depends(get_current_user)
):
    db_comment = models.CaseComment(
        case_id=case_id,
        user_id=current_user.id,
        content=comment.content
    )
    db.add(db_comment)
    await db.commit()
    
    # Reload with user name
    res = await db.execute(
        select(models.CaseComment, models.User.full_name.label("user_full_name"))
        .outerjoin(models.User, models.CaseComment.user_id == models.User.id)
        .filter(models.CaseComment.id == db_comment.id)
    )
    comment_model, full_name = res.one()
    data = schemas.CaseComment.model_validate(comment_model)
    data.user_full_name = full_name
    
    # Broadcast to WebSockets
    from .ws import manager
    await manager.broadcast({
        "type": "NEW_COMMENT",
        "case_id": case_id,
        "user": full_name,
        "content": comment.content
    })
    
    return data

# ─── Revoke Log Endpoints ────────────────────────────────────────────────────

@router.get("/{case_id}/revoke-logs", dependencies=[Depends(get_current_user)])
async def get_case_revoke_logs(case_id: str, db: AsyncSession = Depends(get_async_db)):
    """Return all revoke events for a specific case."""
    stmt = (
        select(models.RevokeLog, models.User.full_name, models.Case.case_ref_no, models.User.role, models.Role.name.label("custom_role_name"))
        .outerjoin(models.User, models.RevokeLog.user_id == models.User.id)
        .outerjoin(models.Role, models.User.role_id == models.Role.id)
        .outerjoin(models.Case, models.RevokeLog.case_id == models.Case.id)
        .filter(models.RevokeLog.case_id == case_id)
        .order_by(models.RevokeLog.revoked_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "id": r.id,
            "case_id": r.case_id,
            "case_ref_no": ref_no,
            "user_id": r.user_id,
            "user_name": full_name,
            "user_role": custom_role_name if custom_role_name else ("QC Verifier" if str(role.value if hasattr(role, 'value') else role).upper() in ["QA", "QC"] else str(role.value if hasattr(role, 'value') else role).replace('_', ' ').title()),
            "revoke_type": r.revoke_type,
            "from_status": r.from_status,
            "to_status": r.to_status,
            "notes": r.notes,
            "revoked_at": r.revoked_at.isoformat() if r.revoked_at else None,
        }
        for r, full_name, ref_no, role, custom_role_name in rows
    ]

@router.get("/revoke-logs/all", dependencies=[Depends(get_current_user)])
async def get_all_revoke_logs(
    revoke_type: Optional[str] = None,
    user_id: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db)
):
    """Global revoke tracking: list all revoke events with filters."""
    stmt = (
        select(models.RevokeLog, models.User.full_name, models.Case.case_ref_no, models.User.role, models.Role.name.label("custom_role_name"))
        .outerjoin(models.User, models.RevokeLog.user_id == models.User.id)
        .outerjoin(models.Role, models.User.role_id == models.Role.id)
        .outerjoin(models.Case, models.RevokeLog.case_id == models.Case.id)
        .order_by(models.RevokeLog.revoked_at.desc())
    )
    if revoke_type:
        stmt = stmt.filter(models.RevokeLog.revoke_type == revoke_type.upper())
    if user_id:
        stmt = stmt.filter(models.RevokeLog.user_id == user_id)
    if from_date:
        try:
            dt = datetime.fromisoformat(from_date)
            stmt = stmt.filter(models.RevokeLog.revoked_at >= dt)
        except ValueError:
            pass
    if to_date:
        try:
            dt = datetime.fromisoformat(to_date)
            stmt = stmt.filter(models.RevokeLog.revoked_at <= dt)
        except ValueError:
            pass

    result = await db.execute(stmt)
    rows = result.all()

    # Aggregate counts per user
    user_summary: Dict[str, Any] = {}
    all_logs = []
    for r, full_name, ref_no, role, custom_role_name in rows:
        u_role_val = str(role.value if hasattr(role, 'value') else role).upper()
        ur_string = custom_role_name if custom_role_name else ("QC Verifier" if u_role_val in ["QA", "QC"] else u_role_val.replace('_', ' ').title())
        log = {
            "id": r.id,
            "case_id": r.case_id,
            "case_ref_no": ref_no,
            "user_id": r.user_id,
            "user_name": full_name,
            "user_role": ur_string,
            "revoke_type": r.revoke_type,
            "from_status": r.from_status,
            "to_status": r.to_status,
            "notes": r.notes,
            "revoked_at": r.revoked_at.isoformat() if r.revoked_at else None,
        }
        all_logs.append(log)

        key = r.user_id
        if key not in user_summary:
            user_summary[key] = {
                "user_id": r.user_id,
                "user_name": full_name,
                "user_role": ur_string,
                "verifier_revoke_count": 0,
                "qc_revoke_count": 0,
                "total_revoke_count": 0,
                "cases": set()
            }
        if r.revoke_type == "VERIFIER":
            user_summary[key]["verifier_revoke_count"] += 1
        elif r.revoke_type == "QC":
            user_summary[key]["qc_revoke_count"] += 1
        user_summary[key]["total_revoke_count"] += 1
        user_summary[key]["cases"].add(ref_no)

    summary = []
    for v in user_summary.values():
        v["cases"] = list(v["cases"])
        summary.append(v)

    return {"logs": all_logs, "user_summary": summary}

# ─── Insufficiency Log Endpoints ───────────────────────────────────────────

@router.get("/{case_id}/insufficiency-logs", dependencies=[Depends(get_current_user)])
async def get_case_insufficiency_logs(case_id: str, db: AsyncSession = Depends(get_async_db)):
    """Return all insufficiency events for a specific case."""
    stmt = (
        select(models.InsufficiencyLog, models.User.full_name, models.Case.case_ref_no, models.User.role, models.Role.name.label("custom_role_name"))
        .outerjoin(models.User, models.InsufficiencyLog.user_id == models.User.id)
        .outerjoin(models.Role, models.User.role_id == models.Role.id)
        .outerjoin(models.Case, models.InsufficiencyLog.case_id == models.Case.id)
        .filter(models.InsufficiencyLog.case_id == case_id)
        .order_by(models.InsufficiencyLog.marked_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "id": r.id,
            "case_id": r.case_id,
            "case_ref_no": ref_no,
            "user_id": r.user_id,
            "user_name": full_name,
            "user_role": custom_role_name if custom_role_name else str(role.value if hasattr(role, 'value') else role).replace('_', ' ').title(),
            "from_status": r.from_status,
            "notes": r.notes,
            "marked_at": r.marked_at.isoformat() if r.marked_at else None,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        }
        for r, full_name, ref_no, role, custom_role_name in rows
    ]

@router.get("/insufficiency-logs/all", dependencies=[Depends(get_current_user)])
async def get_all_insufficiency_logs(
    user_id: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db)
):
    """Global insufficiency tracking: list all events with filters."""
    stmt = (
        select(models.InsufficiencyLog, models.User.full_name, models.Case.case_ref_no, models.User.role, models.Role.name.label("custom_role_name"), models.Customer.name.label("customer_name"))
        .outerjoin(models.User, models.InsufficiencyLog.user_id == models.User.id)
        .outerjoin(models.Role, models.User.role_id == models.Role.id)
        .outerjoin(models.Case, models.InsufficiencyLog.case_id == models.Case.id)
        .outerjoin(models.Customer, models.Case.customer_id == models.Customer.id)
        .order_by(models.InsufficiencyLog.marked_at.desc())
    )
    if user_id:
        stmt = stmt.filter(models.InsufficiencyLog.user_id == user_id)
    if from_date:
        try:
            dt = datetime.fromisoformat(from_date)
            stmt = stmt.filter(models.InsufficiencyLog.marked_at >= dt)
        except ValueError:
            pass
    if to_date:
        try:
            dt = datetime.fromisoformat(to_date)
            stmt = stmt.filter(models.InsufficiencyLog.marked_at <= dt)
        except ValueError:
            pass

    result = await db.execute(stmt)
    rows = result.all()

    all_logs = []
    user_summary = {}

    for r, full_name, ref_no, role, custom_role_name, customer_name in rows:
        u_role_val = str(role.value if hasattr(role, 'value') else role).upper()
        log = {
            "id": r.id,
            "case_id": r.case_id,
            "case_ref_no": ref_no,
            "customer_name": customer_name,
            "user_id": r.user_id,
            "user_name": full_name,
            "user_role": custom_role_name if custom_role_name else u_role_val.replace('_', ' ').title(),
            "marked_at": r.marked_at.isoformat() if r.marked_at else None,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            "notes": r.notes,
        }
        all_logs.append(log)

        key = r.user_id
        if key not in user_summary:
            user_summary[key] = {
                "user_id": r.user_id,
                "user_name": full_name,
                "user_role": log["user_role"],
                "total_marked": 0,
                "total_resolved": 0,
                "cases": set()
            }
        user_summary[key]["total_marked"] = int(user_summary[key].get("total_marked", 0)) + 1
        if r.resolved_at:
            user_summary[key]["total_resolved"] = int(user_summary[key].get("total_resolved", 0)) + 1
        user_summary[key]["cases"].add(ref_no)

    summary = []
    for v in user_summary.values():
        v["cases"] = list(v["cases"])
        summary.append(v)

    return {"logs": all_logs, "user_summary": summary}
