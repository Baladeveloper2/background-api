
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import models
from backend.app.database import AsyncSessionLocal
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        stmt = select(models.Case).filter(models.Case.case_ref_no == 'IBM002')
        res = await db.execute(stmt)
        case = res.scalar()
        if case:
            print(f"CASE IBM002: Status='{case.status}'")
        else:
            print("CASE IBM002 not found")

if __name__ == "__main__":
    asyncio.run(check())
