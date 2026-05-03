import asyncio
import os
import sys
# Add parent dir to path to import app
sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(text("SELECT id, case_ref_no, received_date, is_in_tat, status FROM cases"))
        rows = res.all()
        print(f"Total cases: {len(rows)}")
        for row in rows:
            print(row)

if __name__ == "__main__":
    asyncio.run(check())
