import asyncio
import sys
sys.path.append(r'd:\project\backend')
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import AsyncSessionLocal
from app import models

async def dump_case(case_id):
    async with AsyncSessionLocal() as db:
        stmt = select(models.Case).options(selectinload(models.Case.checks)).filter(models.Case.id == case_id)
        res = await db.execute(stmt)
        case = res.scalar_one_or_none()
        if not case: return
        print(f"CASE:{case.case_ref_no}")
        for chk in case.checks:
            scope = (chk.data or {}).get("scope_of_work", "MISSING")
            print(f"CHECK:{chk.check_type}|SCOPE:{scope}")

if __name__ == "__main__":
    asyncio.run(dump_case("8dad88ef-b695-4fb6-8ac4-062d0af4d9f5"))
