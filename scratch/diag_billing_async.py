import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select, func, text

FINAL_STATUSES = ['FINALIZED', 'COMPLETED', 'POSITIVE', 'NEGATIVE',
                  'DISCREPANCY', 'UNABLE TO VERIFY', 'QC_VERIFIED', 'CLOSED']

async def check():
    async with AsyncSessionLocal() as db:
        # 1. All distinct statuses
        print("=== DISTINCT case statuses ===")
        res = await db.execute(
            select(models.Case.status, func.count(models.Case.id).label('cnt'))
            .group_by(models.Case.status)
            .order_by(func.count(models.Case.id).desc())
        )
        for row in res.all():
            print(f"  {row.status!r:30} => {row.cnt}")

        # 2. is_billable distribution
        print("\n=== is_billable distribution ===")
        try:
            res2 = await db.execute(
                select(models.Case.is_billable, func.count(models.Case.id).label('cnt'))
                .group_by(models.Case.is_billable)
            )
            for row in res2.all():
                print(f"  is_billable={row.is_billable!r} => {row.cnt}")
        except Exception as e:
            print("  ERROR:", e)

        # 3. is_invoiced distribution
        print("\n=== is_invoiced distribution ===")
        try:
            res3 = await db.execute(
                select(models.Case.is_invoiced, func.count(models.Case.id).label('cnt'))
                .group_by(models.Case.is_invoiced)
            )
            for row in res3.all():
                print(f"  is_invoiced={row.is_invoiced!r} => {row.cnt}")
        except Exception as e:
            print("  ERROR:", e)

        # 4. Count matching all billing filters
        print("\n=== Count matching billing filters ===")
        cnt_stmt = (
            select(func.count(models.Case.id))
            .filter(models.Case.status.in_(FINAL_STATUSES))
            .filter(models.Case.is_invoiced == 0)
            .filter(models.Case.is_billable == 1)
        )
        res4 = await db.execute(cnt_stmt)
        print(f"  status IN FINAL + is_invoiced=0 + is_billable=1: {res4.scalar()}")

        # Without is_billable filter
        cnt2 = await db.execute(
            select(func.count(models.Case.id))
            .filter(models.Case.status.in_(FINAL_STATUSES))
            .filter(models.Case.is_invoiced == 0)
        )
        print(f"  status IN FINAL + is_invoiced=0 (no is_billable filter): {cnt2.scalar()}")

        # Without any filter except status
        cnt3 = await db.execute(
            select(func.count(models.Case.id))
            .filter(models.Case.status.in_(FINAL_STATUSES))
        )
        print(f"  status IN FINAL only: {cnt3.scalar()}")

        # 5. Sample 3 cases with their actual field values
        print("\n=== Sample 3 cases with final status ===")
        sample = await db.execute(
            select(models.Case)
            .filter(models.Case.status.in_(FINAL_STATUSES))
            .limit(3)
        )
        for c in sample.scalars().all():
            print(f"  ref={c.case_ref_no} status={c.status!r} is_billable={c.is_billable!r} is_invoiced={c.is_invoiced!r} customer_id={c.customer_id}")

if __name__ == "__main__":
    asyncio.run(check())
