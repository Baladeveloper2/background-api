import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.User.id, models.User.email).filter(models.User.email.in_(['hr@ITCglobal.com', 'itc@gmail.com'])))
        print(res.all())

if __name__ == "__main__":
    asyncio.run(check())
