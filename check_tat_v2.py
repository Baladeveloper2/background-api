
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import models
from backend.app.database import AsyncSessionLocal
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        stmt = select(models.Case).filter(models.Case.case_ref_no.ilike('TAT%'))
        res = await db.execute(stmt)
        cases = res.scalars().all()
        print(f"Found {len(cases)} TAT cases")
        for c in cases:
            print(f"Ref={c.case_ref_no}, Status={c.status}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(check())
    finally:
        loop.close()
