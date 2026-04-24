
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import models
from backend.app.database import AsyncSessionLocal
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        stmt = select(models.Case).filter(models.Case.case_ref_no == 'TAT002')
        res = await db.execute(stmt)
        case = res.scalar()
        if case:
            print(f"CASE TAT002: Status='{case.status}'")
            # Also check for exact string matches in multiple forms
            stmt2 = select(models.Case).filter(models.Case.case_ref_no.ilike('%TAT%02%'))
            res2 = await db.execute(stmt2)
            for c in res2.scalars().all():
                print(f"MATCH: Ref={c.case_ref_no}, Status={c.status}")
        else:
            print("CASE TAT002 not found")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(check())
    finally:
        loop.close()
