import os
import asyncio
from sqlalchemy import select, func
from dotenv import load_dotenv
from app.database import AsyncSessionLocal
from app import models

async def debug_counts():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(func.count(models.Customer.id)))
        print(f"Total Customers in DB: {res.scalar()}")

if __name__ == "__main__":
    asyncio.run(debug_counts())
