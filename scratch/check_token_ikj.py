import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.Insufficiency.token).filter(models.Insufficiency.token.ilike('%ikjR0%')))
        print(f"Token search result: {res.all()}")

if __name__ == "__main__":
    asyncio.run(check())
