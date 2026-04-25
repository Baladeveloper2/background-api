import asyncio
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.Candidate).filter(models.Candidate.name.ilike('%GAYATHRI S%')))
        c = res.scalars().first()
        if c:
            print(f"Name: {c.name}")
            print(f"Address Details: {c.address_details}")
        else:
            print("Not found")

if __name__ == "__main__":
    asyncio.run(check())
