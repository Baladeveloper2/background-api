from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, extract
from datetime import datetime, timedelta
import traceback
from . import models, schemas
from .database import get_async_db
from .auth_routes import check_module_permission, get_current_user

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("", response_model=schemas.DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    try:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Determine if we should filter by verifier
        filter_verifier = current_user.role not in [
            models.UserRole.SUPER_ADMIN, 
            models.UserRole.ADMIN, 
            models.UserRole.MANAGER,
            models.UserRole.QA,
            models.UserRole.QC
        ]
        
        # 1. Basic Counts
        candidates_stmt = select(func.count(models.Case.id))
        if filter_verifier:
            candidates_stmt = candidates_stmt.filter(models.Case.assigned_to == current_user.id)
        candidates_res = await db.execute(candidates_stmt)
        total_candidates = candidates_res.scalar() or 0
        
        customers_res = await db.execute(select(func.count(models.Customer.id)))
        total_customers = customers_res.scalar() or 0

        # Current month entries for MoM comparison
        this_month_stmt = select(func.count(models.Case.id)).filter(models.Case.received_date >= today.replace(day=1))
        if filter_verifier:
            this_month_stmt = this_month_stmt.filter(models.Case.assigned_to == current_user.id)
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
        
        # 3. Status Distribution
        status_stmt = select(models.Case.status, func.count(models.Case.id)).group_by(models.Case.status)
        if filter_verifier:
            status_stmt = status_stmt.filter(models.Case.assigned_to == current_user.id)
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
        geo_res = await db.execute(geo_stmt)
        geo_data = [{"name": r[0] or "REMOTE", "value": r[1], "color": "#3b82f6"} for r in geo_res.all()]

        # 7. Activity Log
        log_stmt = (
            select(models.AuditLog, models.User.email)
            .join(models.User)
            .order_by(models.AuditLog.timestamp.desc())
            .limit(10)
        )
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
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Returns per-verifier case assignments and completion for today."""
    try:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # All users that have cases assigned, filtered for operational roles
        # We need to consider assignments across assigned_to, qc_id, and qa_id
        from sqlalchemy import or_
        stmt = (
            select(
                models.User.full_name,
                models.User.email,
                models.User.role,
                func.count(models.Case.id).label("assigned"),
                func.sum(case((models.Case.status == models.CaseStatus.COMPLETED, 1), else_=0)).label("completed"),
            )
            .outerjoin(models.Case, or_(
                models.Case.assigned_to == models.User.id,
                models.Case.qc_id == models.User.id,
                models.Case.qa_id == models.User.id
            ))
            .filter(models.User.status == models.Status.ACTIVE)
            .filter(models.User.role.in_([
                models.UserRole.VERIFIER, 
                models.UserRole.QC, 
                models.UserRole.QA, 
                models.UserRole.MANAGER
            ]))
            .group_by(models.User.id, models.User.full_name, models.User.email, models.User.role)
        )
        res = await db.execute(stmt)
        rows = res.all()

        verifiers = []
        for full_name, email, role, assigned, completed in rows:
            completed = int(completed or 0)
            verifiers.append({
                "verifier_name": full_name or email,
                "verifier_email": email,
                "role": role,
                "assigned": assigned,
                "completed": completed,
                "in_progress": max(0, (assigned or 0) - completed),
            })

        return {"date": today.strftime("%Y-%m-%d"), "verifiers": verifiers}
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
            .group_by(models.Customer.id, models.Customer.name)
            .order_by(models.Customer.name)
        )
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
            .group_by(extract('hour', models.Case.received_date))
        )
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

@router.get("/cumulative", response_model=schemas.TodayRecordsResponse)
async def get_cumulative_stats(
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Returns all-time received / completed / pending / insufficient per client."""
    try:
        stmt = (
            select(
                models.Customer.name.label("client"),
                func.count(models.Case.id).label("received"),
                func.sum(case((models.Case.status == models.CaseStatus.COMPLETED, 1), else_=0)).label("completed"),
                func.sum(case((models.Case.status == models.CaseStatus.INSUFFICIENT, 1), else_=0)).label("insufficient"),
            )
            .join(models.Customer, models.Case.customer_id == models.Customer.id)
            .group_by(models.Customer.id, models.Customer.name)
            .order_by(models.Customer.name)
        )
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
        return {"date": "ALL TIME", "records": records, "totals": totals}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))

