import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.Insufficiency.token, models.Insufficiency.is_resolved))
        print(f"All tokens: {res.all()}")

if __name__ == "__main__":
    asyncio.run(check())
