import asyncio
from app.database import AsyncSessionLocal
from app import models
from sqlalchemy import select, update

async def cleanup():
    async with AsyncSessionLocal() as db:
        # Find all open insufficiencies for David D (CL-ITC-003)
        res = await db.execute(
            select(models.Insufficiency)
            .join(models.Case)
            .filter(models.Case.case_ref_no == 'CL-ITC-003', models.Insufficiency.is_resolved == False)
            .order_by(models.Insufficiency.created_at.desc())
        )
        insuffs = res.scalars().all()
        
        if len(insuffs) > 1:
            print(f"Found {len(insuffs)} open insuffs for David D. Resolving {len(insuffs)-1} duplicates...")
            # Keep the newest one, resolve the others
            to_resolve = [i.id for i in insuffs[1:]]
            await db.execute(
                update(models.Insufficiency)
                .where(models.Insufficiency.id.in_(to_resolve))
                .values(is_resolved=True, status='CLEARED_DUPLICATE')
            )
            await db.commit()
            print("Cleanup complete.")
        else:
            print("No duplicates found for David D.")

if __name__ == "__main__":
    asyncio.run(cleanup())
