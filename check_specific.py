
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import models
from backend.app.database import AsyncSessionLocal
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        stmt = select(models.Case).filter(models.Case.case_ref_no == 'TATO02')
        res = await db.execute(stmt)
        case = res.scalar()
        if case:
            print(f"CASE TATO02: Status='{case.status}'")
            # Also check TAT002
            stmt2 = select(models.Case).filter(models.Case.case_ref_no == 'TAT002')
            res2 = await db.execute(stmt2)
            case2 = res2.scalar()
            if case2:
                print(f"CASE TAT002: Status='{case2.status}'")
        else:
            print("CASE TATO02 not found")

if __name__ == "__main__":
    asyncio.run(check())
