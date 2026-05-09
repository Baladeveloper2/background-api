import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.User.id, models.User.full_name, models.User.email))
        users = res.all()
        for u in users:
            print(f"ID: {u[0]}, Name: {u[1]}, Email: {u[2]}")

if __name__ == "__main__":
    asyncio.run(check())
