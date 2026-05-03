import asyncio
import os
import sys
from datetime import datetime
sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from app.models import Case
from sqlalchemy import select, func

async def check():
    async with AsyncSessionLocal() as db:
        stmt = select(Case.status, func.count(Case.id)).group_by(Case.status)
        res = await db.execute(stmt)
        rows = res.all()
        print("Status Counts in DB:")
        for r in rows:
            print(f"Status: {r[0]} (Type: {type(r[0])}), Count: {r[1]}")

if __name__ == "__main__":
    asyncio.run(check())
