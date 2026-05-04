import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(models.Insufficiency.id, models.Insufficiency.message, models.Insufficiency.is_resolved)
            .join(models.Case)
            .filter(models.Case.case_ref_no == 'CL-ITC-003')
        )
        data = res.all()
        with open('insuff_results.txt', 'w') as f:
            f.write(str(data))
        print("Done")

if __name__ == "__main__":
    asyncio.run(check())
