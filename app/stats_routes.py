from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, extract
from datetime import datetime, timedelta
import traceback
from . import models, schemas
from .database import get_async_db
from .auth_routes import check_module_permission

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("", response_model=schemas.DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(check_module_permission("bms", "applicants"))
):
    try:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 1. Basic Counts
        candidates_res = await db.execute(select(func.count(models.Case.id)))
        total_candidates = candidates_res.scalar() or 0
        
        customers_res = await db.execute(select(func.count(models.Customer.id)))
        total_customers = customers_res.scalar() or 0

        # Current month entries for MoM comparison
        this_month_res = await db.execute(select(func.count(models.Case.id)).filter(models.Case.received_date >= today.replace(day=1)))
        current_month = this_month_res.scalar() or 0
        
        # 2. Activity today
        today_entry_res = await db.execute(select(func.count(models.Case.id)).filter(models.Case.received_date >= today))
        today_entry = today_entry_res.scalar() or 0
        
        comp_today_res = await db.execute(select(func.count(models.Case.id)).filter(models.Case.status == models.CaseStatus.COMPLETED, models.Case.completed_date >= today))
        completed_today = comp_today_res.scalar() or 0
        
        # 3. Status Distribution
        status_stmt = select(models.Case.status, func.count(models.Case.id)).group_by(models.Case.status)
        status_res = await db.execute(status_stmt)
        status_counts = dict(status_res.all())
        
        interim_cases = sum(status_counts.get(s, 0) for s in [models.CaseStatus.PENDING, models.CaseStatus.VERIFICATION, models.CaseStatus.QC])
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
            total_c = (await db.execute(total_stmt)).scalar() or 0
            
            comp_stmt = select(func.count(models.Case.id)).filter(models.Case.completed_date >= month_start, models.Case.completed_date < next_month)
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
