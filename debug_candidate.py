import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select
from sqlalchemy.orm import selectinload

async def check():
    async with AsyncSessionLocal() as db:
        case_id = "23e3b8a7-7d9d-4a8c-bec3-68fc034c8098"
        stmt = select(models.Case).filter(models.Case.id == case_id).options(
            selectinload(models.Case.candidate),
            selectinload(models.Case.customer)
        )
        res = await db.execute(stmt)
        c = res.scalar_one_or_none()
        if c:
            cand_name = c.candidate.name if c.candidate else "None"
            cand_email = c.candidate.email if c.candidate else "None"
            print(f"FOUND: ID: {c.id} | Ref: {c.case_ref_no} | Name: {cand_name} | Email: {cand_email} | Status: {c.status} | Submitted At: {c.submitted_at} | Link Shared At: {c.link_shared_at}")
        else:
            print("Case 23e3b8a7-7d9d-4a8c-bec3-68fc034c8098 not found!")

if __name__ == "__main__":
    asyncio.run(check())
