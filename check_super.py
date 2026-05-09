import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.User).filter(models.User.role == 'SUPER_ADMIN'))
        users = res.scalars().all()
        for u in users:
            print(f"Name: {u.full_name}, Email: {u.email}")

if __name__ == "__main__":
    asyncio.run(check())
