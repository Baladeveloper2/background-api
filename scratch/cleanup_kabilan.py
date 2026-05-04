import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select, update

async def cleanup():
    async with AsyncSessionLocal() as db:
        # Find all open insufficiencies for KABILAN D (CL-CAP-001)
        res = await db.execute(
            select(models.Insufficiency)
            .join(models.Case)
            .filter(models.Case.case_ref_no == 'CL-CAP-001', models.Insufficiency.is_resolved == False)
        )
        insuffs = res.scalars().all()
        
        if len(insuffs) > 0:
            print(f"Found {len(insuffs)} open insuffs for KABILAN D. Resolving all but one per check...")
            # Group by check_id
            by_check = {}
            for i in insuffs:
                if i.check_id not in by_check:
                    by_check[i.check_id] = []
                by_check[i.check_id].append(i)
            
            for check_id, items in by_check.items():
                if len(items) > 1:
                    to_resolve = [i.id for i in items[1:]]
                    await db.execute(
                        update(models.Insufficiency)
                        .where(models.Insufficiency.id.in_(to_resolve))
                        .values(is_resolved=True, status='CLEARED_DUPLICATE')
                    )
            await db.commit()
            print("Cleanup complete.")
        else:
            print("No duplicates found for KABILAN D.")

if __name__ == "__main__":
    asyncio.run(cleanup())
