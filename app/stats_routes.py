from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from datetime import datetime, timedelta
import traceback
from . import models, schemas
from .database import get_db, engine
from .auth_routes import check_module_permission

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("", response_model=schemas.DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_module_permission("bms", "applicants"))
):
    try:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # ── KPIs ──
        # ── KPIs ──
        total_candidates = db.query(models.Candidate).count()
        total_customers = db.query(models.Customer).count()
        
        # Combine Case status counts into one query
        status_counts = dict(db.query(
            models.Case.status, 
            func.count(models.Case.id)
        ).group_by(models.Case.status).all())
        
        insufficient_cases = status_counts.get(models.CaseStatus.INSUFFICIENT, 0)
        
        # Today Entry
        today_batches = db.query(models.Batch).filter(models.Batch.upload_date >= today).count()
        today_candidates = db.query(models.Candidate).filter(models.Candidate.created_at >= today).count()
        today_entry = today_batches + today_candidates
        
        # Interim = cases neither completed nor insufficient (PENDING + VERIFICATION + QC)
        interim_cases = sum(status_counts.get(s, 0) for s in [models.CaseStatus.PENDING, models.CaseStatus.VERIFICATION, models.CaseStatus.QC])

        # Current month candidates
        first_of_month = today.replace(day=1)
        current_month = db.query(models.Candidate).filter(models.Candidate.created_at >= first_of_month).count()

        # Top customer
        top_cust = db.query(
            models.Customer.name,
            func.count(models.Case.id).label("cnt")
        ).join(models.Case, models.Case.customer_id == models.Customer.id
        ).group_by(models.Customer.name
        ).order_by(func.count(models.Case.id).desc()).first()
        top_customer = f"{top_cust[0]}({top_cust[1]})" if top_cust else ""

        # Pending verification & QC
        pending_verification = status_counts.get(models.CaseStatus.PENDING, 0) + status_counts.get(models.CaseStatus.VERIFICATION, 0)
        pending_qc = status_counts.get(models.CaseStatus.QC, 0)
        completed_today = db.query(models.Case).filter(
            models.Case.status == models.CaseStatus.COMPLETED,
            models.Case.completed_date >= today
        ).count()

        # ── Verification Pending ──
        vp_query = db.query(
            models.VerificationCheck.check_type,
            func.count(models.VerificationCheck.id)
        ).filter(
            models.VerificationCheck.status == models.CheckStatus.INTERIM
        ).group_by(models.VerificationCheck.check_type).all()

        verification_pending = [
            {"type": str(row[0]), "case": int(row[1]), "status": "Pending", "date": today.strftime("%d-%m-%Y")}
            for row in vp_query
        ]

        # ── Today Execution ──
        exec_query = db.query(
            models.VerificationCheck.check_type,
            func.count(models.VerificationCheck.id)
        ).filter(
            models.VerificationCheck.verified_date >= today,
            models.VerificationCheck.status.in_([models.CheckStatus.GREEN, models.CheckStatus.RED, models.CheckStatus.AMBER])
        ).group_by(models.VerificationCheck.check_type).all()

        today_execution = [{"type": str(row[0]), "count": int(row[1])} for row in exec_query]

        # ── Today QC ──
        qc_query = db.query(
            models.VerificationCheck.check_type,
            func.count(models.VerificationCheck.id)
        ).filter(
            models.VerificationCheck.verified_date >= today,
            models.VerificationCheck.status == models.CheckStatus.QC_PENDING
        ).group_by(models.VerificationCheck.check_type).all()
        today_qc = [{"type": str(row[0]), "count": int(row[1])} for row in qc_query]

        # ── Today Data Entry ──
        today_data_entry = []
        if today_entry > 0:
            today_data_entry = [{"user": current_user.full_name or current_user.email, "count": today_entry, "percent": 100.0}]

        # ── Case Analysis (monthly trend) - OPTIMIZED: Use Database Grouping ──
        twelve_months_ago = today - timedelta(days=365)
        # We group by month and status in the DB
        # Note: MySQL/SQLite date formatting differs, but func.strftime works for both in a limited way
        # Since this is for Render (PostgreSQL or MySQL usually), we'll try a generic approach or formatting
        
        # Simple approach: Fetch all counts grouped by month and status
        # For simplicity and compatibility, we'll fetch aggregated data
        monthly_stats = db.query(
            func.count(models.Case.id),
            models.Case.status,
            func.year(models.Case.received_date),
            func.month(models.Case.received_date)
        ).filter(models.Case.received_date >= twelve_months_ago
        ).group_by(
            func.year(models.Case.received_date),
            func.month(models.Case.received_date),
            models.Case.status
        ).all()

        grouped = {}
        # Ensure we have at least the last 6 months represented
        for i in range(5, -1, -1):
            d = today - timedelta(days=30 * i)
            m_key = d.strftime("%b %Y")
            grouped[m_key] = {"total": 0, "completed": 0, "sort_key": d.replace(day=1)}

        for count, status, year, month in monthly_stats:
            d = datetime(year, month, 1)
            m_key = d.strftime("%b %Y")
            if m_key not in grouped:
                grouped[m_key] = {"total": 0, "completed": 0, "sort_key": d}
            grouped[m_key]["total"] += count
            if status == models.CaseStatus.COMPLETED:
                grouped[m_key]["completed"] += count

        case_analysis = []
        sorted_keys = sorted(grouped.keys(), key=lambda k: grouped[k]["sort_key"])
        for k in sorted_keys:
            v = grouped[k]
            case_analysis.append({
                "name": k,
                "total": v["total"],
                "completed": v["completed"],
                "pending": v["total"] - v["completed"]
            })

        # ── Geo Data (Regional Mix) ──
        geo_query = db.query(
            models.Customer.city,
            func.count(models.Case.id)
        ).join(models.Case, models.Case.customer_id == models.Customer.id
        ).group_by(models.Customer.city).all()
        
        geo_data = []
        colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#6366f1"]
        for i, row in enumerate(geo_query):
            if row[0]: # city not null
                geo_data.append({
                    "name": str(row[0]),
                    "value": int(row[1]),
                    "color": colors[i % len(colors)]
                })

        # ── Execution Stats (Radar) ──
        exec_counts = db.query(
            models.VerificationCheck.check_type,
            func.count(models.VerificationCheck.id)
        ).group_by(models.VerificationCheck.check_type).all()
        
        execution_stats = []
        for row in exec_counts[:6]: # Limit to 6 for radar readability
            execution_stats.append({
                "subject": str(row[0]),
                "A": int(row[1]),
                "B": int(row[1]) + 5 # benchmark
            })

        # ── Activity Log (Live Feed) ──
        recent_logs = db.query(
            models.AuditLog,
            models.User.email
        ).join(models.User, models.User.id == models.AuditLog.user_id
        ).order_by(models.AuditLog.timestamp.desc()).limit(5).all()

        activity_log = []
        icons = {"LOGIN": "🔑", "CREATE": "📝", "DELETE": "🗑️", "UPDATE": "🔄", "BATCH": "📦"}
        for idx, (log, email) in enumerate(recent_logs):
            icon = "⚡"
            for k, v in icons.items():
                if k in log.action.upper():
                    icon = v
                    break
            activity_log.append({
                "id": idx, # use loop index for stable IDs
                "icon": icon,
                "action": log.action,
                "time": log.timestamp.strftime("%H:%M"),
                "user": email
            })

        return {
            "total_candidates": total_candidates,
            "current_month": current_month,
            "today_entry": today_entry,
            "today_entry_percent": round((today_entry / total_candidates * 100), 1) if total_candidates > 0 else 0.0,
            "insufficient_cases": insufficient_cases,
            "interim_cases": interim_cases,
            "total_clients": total_customers,
            "top_client": top_customer,
            "pending_verification": pending_verification,
            "pending_qc": pending_qc,
            "completed_today": completed_today,
            "case_analysis": case_analysis,
            "verification_pending": verification_pending,
            "today_data_entry": today_data_entry,
            "today_execution": today_execution,
            "today_qc": today_qc,
            "geo_data": geo_data,
            "execution_stats": execution_stats,
            "activity_log": activity_log
        }
    except Exception as e:
        import logging
        logging.error(f"ERROR IN GET_DASHBOARD_STATS: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/daily", response_model=schemas.DailyReportResponse)
def get_daily_report(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(check_module_permission("bms", "applicants"))
):
    try:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Query for cases received today, grouped by customer
        query = db.query(
            models.Customer.name,
            func.count(models.Case.id).label("received"),
            func.sum(case((models.Case.status == models.CaseStatus.COMPLETED, 1), else_=0)).label("completed"),
            func.sum(case((models.Case.status.in_([models.CaseStatus.PENDING, models.CaseStatus.VERIFICATION, models.CaseStatus.QC]), 1), else_=0)).label("pending"),
            func.sum(case((models.Case.status == models.CaseStatus.INSUFFICIENT, 1), else_=0)).label("insufficient")
        ).join(models.Customer, models.Case.customer_id == models.Customer.id
        ).filter(models.Case.received_date >= today
        ).group_by(models.Customer.name).all()

        stats = []
        total_received = 0
        total_completed = 0
        total_pending = 0
        total_insufficient = 0

        for row in query:
            stat = schemas.DailyStat(
                customer=row[0],
                received=int(row[1] or 0),
                completed=int(row[2] or 0),
                pending=int(row[3] or 0),
                insufficient=int(row[4] or 0)
            )
            stats.append(stat)
            total_received += stat.received
            total_completed += stat.completed
            total_pending += stat.pending
            total_insufficient += stat.insufficient

        totals = schemas.DailyStat(
            customer="TOTAL",
            received=total_received,
            completed=total_completed,
            pending=total_pending,
            insufficient=total_insufficient
        )

        return {
            "date": today.strftime("%A, %d %B %Y"),
            "stats": stats,
            "totals": totals
        }
    except Exception as e:
        import logging
        logging.error(f"ERROR IN GET_DAILY_REPORT: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
