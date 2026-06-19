import asyncio
from app.database import async_engine
from app import models
from sqlalchemy import select, func, case, or_

async def test_summary_query():
    async with async_engine.connect() as conn:
        try:
            # Recreate the exact case_counts subquery
            case_counts = select(
                models.Batch.id.label("batch_uuid"),
                func.count(models.Case.id).label("actual_case_count"),
                func.sum(case((~models.Case.status.in_(['FINALIZED', 'COMPLETED', 'POSITIVE', 'NEGATIVE', 'DISCREPANCY', 'UNABLE TO VERIFY', 'HOLD', 'INSUFFICIENT']), 1), else_=0)).label("total_pending_count"),
                func.sum(case((models.Case.status == models.CaseStatus.PENDING, 1), else_=0)).label("pending_arrival_count"),
                func.sum(case((models.Case.status == models.CaseStatus.VERIFICATION, 1), else_=0)).label("verification_active_count"),
                func.sum(case((models.Case.status == models.CaseStatus.QC, 1), else_=0)).label("qc_active_count"),
                func.sum(case((models.Case.status == models.CaseStatus.QA_PENDING, 1), else_=0)).label("qa_pending_count"),
                func.sum(case((models.Case.status == models.CaseStatus.DOCUMENTS_SUBMITTED, 1), else_=0)).label("docs_submitted_count"),
                func.sum(case((models.Case.status == models.CaseStatus.LINK_SHARED, 1), else_=0)).label("link_shared_count"),
                func.sum(case((models.Case.status.in_(['FINALIZED', 'COMPLETED', 'POSITIVE', 'NEGATIVE', 'DISCREPANCY', 'UNABLE TO VERIFY', 'HOLD', 'INSUFFICIENT']), 1), else_=0)).label("completed_count"),
                func.sum(case((models.Case.status.in_([models.CaseStatus.VERIFICATION, models.CaseStatus.QC]), 1), else_=0)).label("in_progress_count"),
                func.max(models.Case.completed_date).label("completed_date")
            ).select_from(models.Case).join(
                models.Batch, 
                or_(models.Case.batch_id == models.Batch.id, models.Case.batch_id == models.Batch.batch_no)
            ).group_by(models.Batch.id).subquery()

            check_values = select(
                models.Batch.id.label("batch_uuid"),
                func.sum(models.VerificationCheck.rate).label("total_check_value")
            ).select_from(models.Case).join(
                models.VerificationCheck, models.Case.id == models.VerificationCheck.case_id
            ).join(
                models.Batch,
                or_(models.Case.batch_id == models.Batch.id, models.Case.batch_id == models.Batch.batch_no)
            ).group_by(models.Batch.id).subquery()

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
                check_values.c.total_check_value
            ).join(models.Customer, models.Batch.customer_id == models.Customer.id)\
             .outerjoin(case_counts, models.Batch.id == case_counts.c.batch_uuid)\
             .outerjoin(check_values, models.Batch.id == check_values.c.batch_uuid)

            res = await conn.execute(stmt.limit(5))
            rows = res.fetchall()
            print("Query succeeded. Found rows:", len(rows))
            if len(rows) > 0:
                print("First row:", rows[0])
        except Exception as e:
            print("Query failed:", str(e))

asyncio.run(test_summary_query())
