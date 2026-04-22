from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, extract
from datetime import datetime, timedelta
import traceback
from . import models, schemas
from .database import get_async_db
from .auth_routes import check_module_permission, get_current_user

router = APIRouter(prefix="/stats", tags=["stats"])

from fastapi.responses import StreamingResponse
import io
import pandas as pd

@router.get("", response_model=schemas.DashboardStats)
async def get_dashboard_stats(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    try:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Determine if we should filter by verifier
        user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
        role_name = (current_user.role_rel.name.upper() if current_user.role_rel else "").upper()
        
        is_customer = user_role == "CUSTOMER" or role_name == "CUSTOMER"
        is_admin = user_role in ["SUPER_ADMIN", "ADMIN", "MANAGER", "QA", "QC"] or role_name in ["SUPER ADMIN", "QC VERIFIER"]
        
        filter_verifier = not (is_admin or is_customer)
        filter_customer = is_customer
        
        # 1. Basic Counts
        filter_start = None
        filter_end = None
        if from_date:
            try:
                filter_start = datetime.strptime(from_date, "%Y-%m-%d")
            except: pass
        if to_date:
            try:
                filter_end = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)
            except: pass

        candidates_stmt = select(func.count(models.Case.id))
        if filter_verifier:
            candidates_stmt = candidates_stmt.filter(models.Case.assigned_to == current_user.id)
        if filter_customer:
            candidates_stmt = candidates_stmt.filter(models.Case.customer_id == current_user.customer_id)
        
        if filter_start:
            candidates_stmt = candidates_stmt.filter(models.Case.received_date >= filter_start)
        if filter_end:
            candidates_stmt = candidates_stmt.filter(models.Case.received_date < filter_end)
        candidates_res = await db.execute(candidates_stmt)
        total_candidates = candidates_res.scalar() or 0
        
        customers_res = await db.execute(select(func.count(models.Customer.id)))
        total_customers = customers_res.scalar() or 0

        # Current month entries for MoM comparison
        this_month_stmt = select(func.count(models.Case.id)).filter(models.Case.received_date >= today.replace(day=1))
        if filter_verifier:
            this_month_stmt = this_month_stmt.filter(models.Case.assigned_to == current_user.id)
        if filter_customer:
            this_month_stmt = this_month_stmt.filter(models.Case.customer_id == current_user.customer_id)
        this_month_res = await db.execute(this_month_stmt)
        current_month = this_month_res.scalar() or 0
        
        # 2. Activity today
        today_entry_stmt = select(func.count(models.Case.id)).filter(models.Case.received_date >= today)
        if filter_verifier:
            today_entry_stmt = today_entry_stmt.filter(models.Case.assigned_to == current_user.id)
        today_entry_res = await db.execute(today_entry_stmt)
        today_entry = today_entry_res.scalar() or 0
        
        comp_today_stmt = select(func.count(models.Case.id)).filter(models.Case.status == models.CaseStatus.COMPLETED, models.Case.completed_date >= today)
        if filter_verifier:
            comp_today_stmt = comp_today_stmt.filter(models.Case.assigned_to == current_user.id)
        comp_today_res = await db.execute(comp_today_stmt)
        completed_today = comp_today_res.scalar() or 0
        
        # 2b. Total Completed & Revenue
        total_comp_stmt = select(func.count(models.Case.id)).filter(models.Case.status == models.CaseStatus.COMPLETED)
        if filter_verifier:
            total_comp_stmt = total_comp_stmt.filter(models.Case.assigned_to == current_user.id)
        if filter_customer:
            total_comp_stmt = total_comp_stmt.filter(models.Case.customer_id == current_user.customer_id)
        
        if filter_start:
            total_comp_stmt = total_comp_stmt.filter(models.Case.completed_date >= filter_start)
        if filter_end:
            total_comp_stmt = total_comp_stmt.filter(models.Case.completed_date < filter_end)

        total_completed_res = await db.execute(total_comp_stmt)
        total_completed = total_completed_res.scalar() or 0

        rev_stmt = (
            select(func.sum(models.VerificationCheck.rate))
            .select_from(models.Case)
            .join(models.VerificationCheck, models.Case.id == models.VerificationCheck.case_id)
            .filter(models.Case.status == models.CaseStatus.COMPLETED)
        )
        if filter_verifier:
            rev_stmt = rev_stmt.filter(models.Case.assigned_to == current_user.id)
        if filter_customer:
            rev_stmt = rev_stmt.filter(models.Case.customer_id == current_user.customer_id)
        
        if filter_start:
            rev_stmt = rev_stmt.filter(models.Case.completed_date >= filter_start)
        if filter_end:
            rev_stmt = rev_stmt.filter(models.Case.completed_date < filter_end)
        total_revenue_res = await db.execute(rev_stmt)
        total_revenue = total_revenue_res.scalar() or 0.0
        
        # 3. Status Distribution
        status_stmt = select(models.Case.status, func.count(models.Case.id)).group_by(models.Case.status)
        if filter_verifier:
            status_stmt = status_stmt.filter(models.Case.assigned_to == current_user.id)
        if filter_customer:
            status_stmt = status_stmt.filter(models.Case.customer_id == current_user.customer_id)
        if filter_start:
            status_stmt = status_stmt.filter(models.Case.received_date >= filter_start)
        if filter_end:
            status_stmt = status_stmt.filter(models.Case.received_date < filter_end)
        
        status_res = await db.execute(status_stmt)
        status_counts = dict(status_res.all())
        
        interim_cases = sum(status_counts.get(s, 0) for s in [models.CaseStatus.PENDING, models.CaseStatus.VERIFICATION, models.CaseStatus.QC, models.CaseStatus.QA_PENDING])
        insufficient_cases = status_counts.get(models.CaseStatus.INSUFFICIENT, 0)
        pending_qc = status_counts.get(models.CaseStatus.QC, 0)
        
        # 4. Volume Dynamics (Last 6 Months)
        analysis_data = []
        for i in range(5, -1, -1):
            # Calculate months back
            m = today.month - i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            
            month_start = datetime(y, m, 1)
            # month_end calc
            if m == 12: next_month = datetime(y + 1, 1, 1)
            else: next_month = datetime(y, m + 1, 1)
            
            total_stmt = select(func.count(models.Case.id)).filter(models.Case.received_date >= month_start, models.Case.received_date < next_month)
            if filter_verifier:
                total_stmt = total_stmt.filter(models.Case.assigned_to == current_user.id)
            total_c = (await db.execute(total_stmt)).scalar() or 0
            
            comp_stmt = select(func.count(models.Case.id)).filter(models.Case.completed_date >= month_start, models.Case.completed_date < next_month)
            if filter_verifier:
                comp_stmt = comp_stmt.filter(models.Case.assigned_to == current_user.id)
            comp_c = (await db.execute(comp_stmt)).scalar() or 0
            
            analysis_data.append({
                "name": month_start.strftime("%b %y"),
                "total": total_c,
                "completed": comp_c,
                "pending": max(0, total_c - comp_c)
            })

        # 5. Verification Priority Queue (Counts by Type)
        # Schema expects list of { type: str, case: int, status: str, date: str }
        pending_checks_stmt = (
            select(models.VerificationCheck.check_type, func.count(models.VerificationCheck.id))
            .filter(models.VerificationCheck.status == models.CheckStatus.INTERIM)
            .group_by(models.VerificationCheck.check_type)
        )
        pc_res = await db.execute(pending_checks_stmt)
        verification_pending = []
        for ctype, count in pc_res.all():
            verification_pending.append({
                "type": ctype,
                "case": count,
                "status": "In Progress",
                "date": today.strftime("%d-%m-%Y")
            })

        # 6. Geo Data
        geo_stmt = select(models.Customer.city, func.count(models.Case.id)).join(models.Case).group_by(models.Customer.city)
        if filter_start:
            geo_stmt = geo_stmt.filter(models.Case.received_date >= filter_start)
        if filter_end:
            geo_stmt = geo_stmt.filter(models.Case.received_date < filter_end)
        geo_res = await db.execute(geo_stmt)
        geo_data = [{"name": r[0] or "REMOTE", "value": r[1], "color": "#3b82f6"} for r in geo_res.all()]

        # 7. Activity Log
        log_stmt = (
            select(models.AuditLog, models.User.email)
            .join(models.User)
        )
        if filter_verifier:
            log_stmt = log_stmt.filter(models.AuditLog.user_id == current_user.id)
        if filter_customer:
            # Customers should only see logs related to their cases
            log_stmt = log_stmt.join(models.Case, models.AuditLog.resource_id == models.Case.id).filter(models.Case.customer_id == current_user.customer_id)
            
        log_stmt = log_stmt.order_by(models.AuditLog.timestamp.desc()).limit(10)
        log_res = await db.execute(log_stmt)
        activity_log = [{
            "id": idx,
            "icon": "⚡",
            "action": log.action,
            "time": log.timestamp.strftime("%H:%M"),
            "user": email
        } for idx, (log, email) in enumerate(log_res.all())]

        return {
            "total_candidates": total_candidates,
            "current_month": current_month,
            "today_entry": today_entry,
            "today_entry_percent": 0.0,
            "insufficient_cases": insufficient_cases,
            "interim_cases": interim_cases,
            "total_clients": total_customers,
            "top_client": "Global Logistics Hub" if total_customers > 0 else "N/A",
            "pending_verification": interim_cases,
            "pending_qc": pending_qc,
            "completed_today": completed_today,
            "total_completed": total_completed,
            "total_revenue": float(total_revenue),
            "entry_pending_count": status_counts.get(models.CaseStatus.PENDING, 0),
            "verification_pending_count": status_counts.get(models.CaseStatus.VERIFICATION, 0),
            "case_analysis": analysis_data,
            "verification_pending": verification_pending,
            "today_data_entry": [],
            "today_execution": [],
            "today_qc": [],
            "geo_data": geo_data,
            "execution_stats": [],
            "activity_log": activity_log
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))

@router.get("/daily", response_model=schemas.DailyReportResponse)
async def get_daily_report(db: AsyncSession = Depends(get_async_db)):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(
        models.Customer.name,
        func.count(models.Case.id).label("received"),
        func.sum(case((models.Case.status == models.CaseStatus.COMPLETED, 1), else_=0)).label("completed")
    ).join(models.Customer).filter(models.Case.received_date >= today).group_by(models.Customer.name)
    
    res = await db.execute(stmt)
    stats = [{"customer": r[0], "received": r[1], "completed": int(r[2] or 0), "pending": 0, "insufficient": 0} for r in res.all()]
    
    return {
        "date": today.strftime("%Y-%m-%d"), 
        "stats": stats, 
        "totals": {
            "customer": "ALL", 
            "received": sum(s["received"] for s in stats), 
            "completed": sum(s["completed"] for s in stats), 
            "pending": 0, 
            "insufficient": 0
        }
    }


@router.get("/verifier-daily", response_model=schemas.VerifierDailyResponse)
async def get_verifier_daily(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Returns per-verifier case assignments and completion filtered by date if provided."""
    try:
        filter_start = None
        filter_end = None
        if from_date:
            try: filter_start = datetime.strptime(from_date, "%Y-%m-%d")
            except: pass
        if to_date:
            try: filter_end = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)
            except: pass

        # All users that have cases assigned, filtered for operational roles
        from sqlalchemy import or_, distinct
        
        # Build date filters as case conditions
        date_cond = True
        if filter_start:
            date_cond = (models.Case.received_date >= filter_start)
        if filter_end:
            date_cond &= (models.Case.received_date < filter_end)

        stmt = (
            select(
                models.User.id,
                models.User.full_name,
                models.User.email,
                models.User.role,
                models.Role.name.label("custom_role_name"),
                func.count(distinct(case((date_cond, models.Case.id), else_=None))).label("assigned"),
                func.count(distinct(case(((models.Case.status == models.CaseStatus.COMPLETED) & date_cond, models.Case.id), else_=None))).label("completed"),
                func.count(distinct(case(((models.Case.status == models.CaseStatus.INSUFFICIENT) & date_cond, models.Case.id), else_=None))).label("insufficient"),
                func.count(distinct(case(((or_(models.Case.verifier_revoke_count > 0, models.Case.qc_revoke_count > 0)) & date_cond, models.Case.id), else_=None))).label("revoked"),
                func.sum(case((date_cond, models.VerificationCheck.rate), else_=0)).label("earnings")
            )
            .outerjoin(models.Case, or_(
                models.Case.assigned_to == models.User.id,
                models.Case.qc_id == models.User.id,
                models.Case.qa_id == models.User.id
            ))
            .outerjoin(models.Role, models.User.role_id == models.Role.id)
            .outerjoin(models.VerificationCheck, models.Case.id == models.VerificationCheck.case_id)
            .filter(models.User.status == models.Status.ACTIVE)
            .filter(models.User.role.in_([
                models.UserRole.VERIFIER, 
                models.UserRole.QC, 
                models.UserRole.QA, 
                models.UserRole.MANAGER
            ]))
            .group_by(models.User.id, models.User.full_name, models.User.email, models.User.role, models.Role.name)
        )
        
        res = await db.execute(stmt)
        rows = res.all()

        verifiers = []
        for v_id, full_name, email, role, custom_role_name, assigned, completed, insufficient, revoked, earnings in rows:
            completedCnt = int(completed or 0)
            insufficientCnt = int(insufficient or 0)
            revokedCnt = int(revoked or 0)
            assignedCnt = int(assigned or 0)
            
            # Map QA/QC to QC Verifier if no custom name
            u_role = role.value if hasattr(role, 'value') else str(role)
            display_role = custom_role_name
            if not display_role:
                if u_role in ["QA", "QC"]:
                    display_role = "QC Verifier"
                else:
                    display_role = u_role.replace('_', ' ').title()

            verifiers.append({
                "id": v_id,
                "verifier_name": full_name or email,
                "verifier_email": email,
                "role": display_role,
                "assigned": assignedCnt,
                "completed": completedCnt,
                "insufficient": insufficientCnt,
                "revoked": revokedCnt,
                "earnings": float(earnings or 0),
                "in_progress": max(0, assignedCnt - completedCnt - insufficientCnt),
            })

        return {"date": from_date or datetime.now().strftime("%Y-%m-%d"), "verifiers": verifiers}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))


@router.get("/today-records", response_model=schemas.TodayRecordsResponse)
async def get_today_records(
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Returns today's received / completed / pending / insufficient per client."""
    try:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        stmt = (
            select(
                models.Customer.name.label("client"),
                func.count(models.Case.id).label("received"),
                func.sum(case((models.Case.status == models.CaseStatus.COMPLETED, 1), else_=0)).label("completed"),
                func.sum(case((models.Case.status == models.CaseStatus.INSUFFICIENT, 1), else_=0)).label("insufficient"),
            )
            .join(models.Customer, models.Case.customer_id == models.Customer.id)
            .filter(models.Case.received_date >= today)
        )
        
        user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
        role_name = (current_user.role_rel.name.upper() if current_user.role_rel else "").upper()
        if user_role == "CUSTOMER" or role_name == "CUSTOMER":
            stmt = stmt.filter(models.Case.customer_id == current_user.customer_id)

        stmt = stmt.group_by(models.Customer.id, models.Customer.name).order_by(models.Customer.name)
        res = await db.execute(stmt)
        rows = res.all()

        records = []
        for client, received, completed, insufficient in rows:
            completed = int(completed or 0)
            insufficient = int(insufficient or 0)
            pending = max(0, received - completed - insufficient)
            records.append({
                "client": client or "Unknown",
                "received": received,
                "completed": completed,
                "pending": pending,
                "insufficient": insufficient,
            })

        totals = {
            "client": "TOTAL",
            "received": sum(r["received"] for r in records),
            "completed": sum(r["completed"] for r in records),
            "pending": sum(r["pending"] for r in records),
            "insufficient": sum(r["insufficient"] for r in records),
        }
        return {"date": today.strftime("%Y-%m-%d"), "records": records, "totals": totals}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))


@router.get("/throughput", response_model=schemas.ThroughputResponse)
async def get_throughput_heatmap(
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Calculates hourly throughput for today and generates a load forecast."""
    try:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 1. Actual Load: Case entries per hour for today
        load_stmt = (
            select(
                extract('hour', models.Case.received_date).label('hour'),
                func.count(models.Case.id).label('load')
            )
            .filter(models.Case.received_date >= today)
        )
        
        user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
        role_name = (current_user.role_rel.name.upper() if current_user.role_rel else "").upper()
        if user_role == "CUSTOMER" or role_name == "CUSTOMER":
            load_stmt = load_stmt.filter(models.Case.customer_id == current_user.customer_id)
            
        load_stmt = load_stmt.group_by(extract('hour', models.Case.received_date))
        load_res = await db.execute(load_stmt)
        actual_load = {int(h): l for h, l in load_res.all()}
        
        # 2. Forecast: Average actions per hour for the last 7 days
        week_ago = today - timedelta(days=7)
        forecast_stmt = (
            select(
                extract('hour', models.Case.received_date).label('hour'),
                func.count(models.Case.id).label('total_load')
            )
            .filter(models.Case.received_date >= week_ago, models.Case.received_date < today)
            .group_by(extract('hour', models.Case.received_date))
        )
        forecast_res = await db.execute(forecast_stmt)
        forecast_raw = {int(h): l for h, l in forecast_res.all()}
        
        heatmap_data = []
        # Standard active hours (08:00 to 20:00)
        for h in range(8, 21, 2):
            hour_str = f"{str(h).zfill(2)}:00"
            load = actual_load.get(h, 0)
            # Forecast is weekly total / 7, or fallback to load + random variance if no history
            forecast = int(forecast_raw.get(h, 0) / 7) or (load + (10 if h < 16 else -10))
            if forecast < 10: forecast = 15 # baseline
            
            heatmap_data.append({
                "hour": hour_str,
                "load": load,
                "forecast": forecast
            })
            
        return {"date": today.strftime("%Y-%m-%d"), "data": heatmap_data}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))

@router.get("/export")
async def export_dashboard_data(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Generates Excel export of cases with full details."""
    try:
        # Determine filters
        user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
        role_name = (current_user.role_rel.name.upper() if current_user.role_rel else "").upper()
        is_customer = user_role == "CUSTOMER" or role_name == "CUSTOMER"
        is_admin = user_role in ["SUPER_ADMIN", "ADMIN", "MANAGER", "QA", "QC"] or role_name in ["SUPER ADMIN", "QC VERIFIER"]
        
        stmt = select(
            models.Case.case_ref_no,
            models.Candidate.name.label("candidate_name"),
            models.Customer.name.label("client_name"),
            models.Case.received_date,
            models.Case.completed_date,
            models.Case.status,
            models.Case.tat_days,
            models.Batch.batch_no
        ).join(models.Candidate, models.Case.candidate_id == models.Candidate.id)\
         .join(models.Customer, models.Case.customer_id == models.Customer.id)\
         .outerjoin(models.Batch, models.Case.batch_id == models.Batch.id)

        if not (is_admin or is_customer):
            stmt = stmt.filter(models.Case.assigned_to == current_user.id)
        if is_customer:
            stmt = stmt.filter(models.Case.customer_id == current_user.customer_id)

        if from_date:
            stmt = stmt.filter(models.Case.received_date >= datetime.strptime(from_date, "%Y-%m-%d"))
        if to_date:
            stmt = stmt.filter(models.Case.received_date < datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1))

        res = await db.execute(stmt)
        rows = res.all()

        # Convert to DataFrame
        data = []
        for r in rows:
            data.append({
                "Case Ref No": r.case_ref_no,
                "Candidate Name": r.candidate_name,
                "Client": r.client_name,
                "Received Date": r.received_date.strftime("%Y-%m-%d %H:%M") if r.received_date else "N/A",
                "Completed Date": r.completed_date.strftime("%Y-%m-%d %H:%M") if r.completed_date else "Pending",
                "Status": r.status,
                "SLA (Days)": r.tat_days,
                "Batch ID": r.batch_no or "Direct Entry"
            })

        df = pd.DataFrame(data)
        
        # Save to buffer
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Strategic Report')
        
        output.seek(0)
        
        headers = {
            'Content-Disposition': f'attachment; filename="BGV_Report_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx"'
        }
        return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))

@router.get("/cumulative", response_model=schemas.TodayRecordsResponse)
async def get_cumulative_stats(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Returns received / completed / pending / insufficient per client, filtered by date if provided."""
    try:
        filter_start = None
        filter_end = None
        if from_date:
            try: filter_start = datetime.strptime(from_date, "%Y-%m-%d")
            except: pass
        if to_date:
            try: filter_end = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)
            except: pass

        stmt = (
            select(
                models.Customer.name.label("client"),
                func.count(models.Case.id).label("received"),
                func.sum(case((models.Case.status == models.CaseStatus.COMPLETED, 1), else_=0)).label("completed"),
                func.sum(case((models.Case.status == models.CaseStatus.INSUFFICIENT, 1), else_=0)).label("insufficient"),
                func.sum(models.Case.verifier_revoke_count).label("v_revokes"),
                func.sum(models.Case.qc_revoke_count).label("qc_revokes"),
                func.sum(case((models.Case.status == models.CaseStatus.COMPLETED, case((models.Case.is_in_tat == 1, 1), else_=0)), else_=0)).label("in_tat")
            )
            .join(models.Customer, models.Case.customer_id == models.Customer.id)
        )
        
        if filter_start:
            stmt = stmt.filter(models.Case.received_date >= filter_start)
        if filter_end:
            stmt = stmt.filter(models.Case.received_date < filter_end)
        
        user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
        role_name = (current_user.role_rel.name.upper() if current_user.role_rel else "").upper()
        if user_role == "CUSTOMER" or role_name == "CUSTOMER":
            stmt = stmt.filter(models.Case.customer_id == current_user.customer_id)
            
        stmt = stmt.group_by(models.Customer.id, models.Customer.name).order_by(models.Customer.name)
        res = await db.execute(stmt)
        rows = res.all()

        records = []
        for client, received, completed, insufficient, v_revokes, qc_revokes, in_tat in rows:
            completedCnt = int(completed or 0)
            insufficientCnt = int(insufficient or 0)
            pending = max(0, received - completedCnt - insufficientCnt)
            
            tat_percent = (float(in_tat or 0) / float(completedCnt) * 100.0) if completedCnt > 0 else 0.0
            
            records.append({
                "client": client or "Unknown",
                "received": received,
                "completed": completedCnt,
                "pending": pending,
                "insufficient": insufficientCnt,
                "verifier_revoke_count": int(v_revokes or 0),
                "qc_revoke_count": int(qc_revokes or 0),
                "tat_percent": float(round(float(tat_percent), 1))
            })

        avg_tat = (sum(float(r["tat_percent"]) for r in records) / float(len(records))) if records else 0.0
        totals = {
            "client": "TOTAL",
            "received": sum(r["received"] for r in records),
            "completed": sum(r["completed"] for r in records),
            "pending": sum(r["pending"] for r in records),
            "insufficient": sum(r["insufficient"] for r in records),
            "verifier_revoke_count": sum(r["verifier_revoke_count"] for r in records),
            "qc_revoke_count": sum(r["qc_revoke_count"] for r in records),
            "tat_percent": float(round(float(avg_tat), 1))
        }
        return {"date": "ALL TIME", "records": records, "totals": totals}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))

@router.get("/verifier-daily/export")
async def export_executive_data(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Generates Excel export of executive performance stats."""
    try:
        # Reuse logic from get_verifier_daily
        res = await get_verifier_daily(from_date, to_date, db, current_user)
        verifiers = res.get("verifiers", [])
        
        data = []
        for v in verifiers:
            eff = ((v["completed"] + v["insufficient"]) / v["assigned"] * 100) if v["assigned"] > 0 else 0
            data.append({
                "Executive Name": v["verifier_name"],
                "Executive Email": v["verifier_email"],
                "Role": str(v["role"]),
                "Assigned Cases": v["assigned"],
                "Completed": v["completed"],
                "Pending": v["in_progress"],
                "Insufficient": v["insufficient"],
                "Revoked": v["revoked"],
                "Efficiency (%)": float(round(float(eff), 1))
            })
            
        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Executive MIS')
        
        output.seek(0)
        headers = {'Content-Disposition': f'attachment; filename="Executive_MIS_{datetime.now().strftime("%Y%m%d")}.xlsx"'}
        return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))

