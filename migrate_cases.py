import asyncio
import os
import sys

from app.database import AsyncSessionLocal
from app.models import Case
from sqlalchemy import select, update

async def migrate_case_results():
    async with AsyncSessionLocal() as db:
        # Legacy status outcomes
        results_map = {
            "POSITIVE": "POSITIVE",
            "NEGATIVE": "NEGATIVE",
            "DISCREPANCY": "DISCREPANCY",
            "UNABLE TO VERIFY": "UNABLE TO VERIFY",
            "INSUFFICIENT": "INSUFFICIENT",
            "INSUFFICIENCY": "INSUFFICIENT",
            "HOLD": "HOLD",
            "QC_VERIFIED": "POSITIVE" # Usually implies positive or just verified
        }

        updated_count = 0
        
        # 1. Migrate cases where status is a legacy result
        for legacy_status, new_result in results_map.items():
            stmt = update(Case).where(Case.status == legacy_status).values(
                status="FINALIZED",
                final_result=new_result
            )
            res = await db.execute(stmt)
            updated_count += res.rowcount

        # 2. Also ensure completed/closed cases have at least some final result if possible
        # but let's just leave final_result as NULL for those unless they already have one, or maybe it's fine.
        
        # We should also ensure COMPLETED and CLOSED are mapped to FINALIZED for workflow status uniformity
        stmt2 = update(Case).where(Case.status.in_(["COMPLETED", "CLOSED"])).values(
            status="FINALIZED"
        )
        res2 = await db.execute(stmt2)
        updated_count += res2.rowcount
        
        await db.commit()
        print(f"Migration completed. Updated {updated_count} cases.")

if __name__ == "__main__":
    asyncio.run(migrate_case_results())
