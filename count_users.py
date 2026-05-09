import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.User.full_name))
        names = [r[0] for r in res.all()]
        print(f"Total Users: {len(names)}")
        print(f"Names: {names}")

if __name__ == "__main__":
    asyncio.run(check())
