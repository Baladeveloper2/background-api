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
        # Check IBM002 checks
        res = await session.execute(select(models.Case.id).filter(models.Case.case_ref_no == 'IBM002'))
        c_id = res.scalar()
        
        res = await session.execute(select(models.VerificationCheck.check_type, models.VerificationCheck.status).filter(models.VerificationCheck.case_id == c_id))
        checks = res.all()
        with open("checks_output.txt", "w") as f:
            f.write(f"IBM002 ID: {c_id}\n")
            for c_type, status in checks:
                f.write(f"Check: {c_type:20} | Status: {status}\n")

if __name__ == "__main__":
    asyncio.run(check())
