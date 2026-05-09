import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.Case.id, models.Case.status))
        cases = res.all()
        for c in cases:
            print(f"'{c[1]}'")

if __name__ == "__main__":
    asyncio.run(check())
