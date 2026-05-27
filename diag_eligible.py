import asyncio
import sys
sys.path.insert(0, '.')
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

FINAL_STATUSES = ['FINALIZED', 'COMPLETED', 'POSITIVE', 'NEGATIVE',
                  'DISCREPANCY', 'UNABLE TO VERIFY', 'QC_VERIFIED', 'CLOSED']

async def check():
    async with AsyncSessionLocal() as db:
        # Get TATA customer id
        res = await db.execute(
            select(models.Customer).filter(models.Customer.name.like('%TATA%'))
        )
        customers = res.scalars().all()
        print("=== Matching customers ===")
        for c in customers:
            print(f"  id={c.id} name={c.name!r} status={c.status!r}")

        for customer in customers:
            cid = customer.id
            print(f"\n=== Cases for {customer.name} (id={cid}) ===")

            # All cases for this customer
            all_res = await db.execute(
                select(models.Case.case_ref_no, models.Case.status,
                       models.Case.is_billable, models.Case.is_invoiced,
                       models.Case.completed_date)
                .filter(models.Case.customer_id == cid)
            )
            rows = all_res.all()
            print(f"  Total cases: {len(rows)}")
            for r in rows:
                print(f"    ref={r.case_ref_no} status={r.status!r} is_billable={r.is_billable} is_invoiced={r.is_invoiced} completed_date={r.completed_date}")

            # Eligible cases query (exactly as in billing_routes)
            stmt = (
                select(models.Case)
                .options(joinedload(models.Case.candidate), joinedload(models.Case.checks))
                .filter(models.Case.customer_id == cid)
                .filter(models.Case.status.in_(FINAL_STATUSES))
                .filter(models.Case.is_invoiced == 0)
                .filter(models.Case.is_billable == 1)
            )
            eligible_res = await db.execute(stmt)
            eligible = eligible_res.unique().scalars().all()
            print(f"\n  Eligible cases (billing query): {len(eligible)}")
            for c in eligible:
                print(f"    ref={c.case_ref_no} completed_date={c.completed_date}")

if __name__ == "__main__":
    asyncio.run(check())
