import asyncio
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(models.Case.case_ref_no, models.Case.status))
        with open("db_status_output.txt", "w") as f:
            for ref, status in res.all():
                f.write(f"Case: {ref} | Status: {status}\n")

if __name__ == "__main__":
    asyncio.run(check())
