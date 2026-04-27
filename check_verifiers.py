import asyncio
import os
from app.database import AsyncSessionLocal
from app import models, enums
from sqlalchemy import select

async def check_verifiers():
    async with AsyncSessionLocal() as db:
        stmt = select(models.User).filter(models.User.role == enums.UserRole.VERIFIER)
        res = await db.execute(stmt)
        users = res.scalars().all()
        print(f"DEBUG_START")
        print(f"VERIFIER_COUNT:{len(users)}")
        for u in users:
            print(f"USER:{u.full_name}:STATUS:{u.status}:ROLE:{u.role}")
        print(f"DEBUG_END")

if __name__ == "__main__":
    asyncio.run(check_verifiers())
