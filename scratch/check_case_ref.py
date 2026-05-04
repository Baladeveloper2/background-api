import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.Case.case_ref_no).filter(models.Case.id == '34dfa821-1a7a-4d22-98f6-0014450a9783'))
        print(f"Case Ref: {res.scalar()}")

if __name__ == "__main__":
    asyncio.run(check())
