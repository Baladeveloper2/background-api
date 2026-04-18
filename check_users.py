import asyncio
from app.database import AsyncSessionLocal
from app.models import User
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User))
        users = res.scalars().all()
        for u in users:
            print(f"User: {u.full_name}, Role: {u.role}")

if __name__ == "__main__":
    asyncio.run(check())
