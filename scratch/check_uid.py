import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.User.email, models.User.role).filter(models.User.id == 'cd72bf65-836e-4561-a12c-64dff28ac065'))
        print(res.one_or_none())

if __name__ == "__main__":
    asyncio.run(check())
