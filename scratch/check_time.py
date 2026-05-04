import asyncio
from app.database import AsyncSessionLocal
from sqlalchemy import func, select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(func.now()))
        print(res.scalar())

if __name__ == "__main__":
    asyncio.run(check())
