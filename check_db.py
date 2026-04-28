import asyncio
from app.database import async_engine
from app.models import Batch, Case, Customer
from sqlalchemy import select, func

async def run():
    try:
        async with async_engine.connect() as conn:
            # Check batches
            res = await conn.execute(select(func.count(Batch.id)))
            batch_count = res.scalar()
            print(f"DEBUG: Total Batches in DB: {batch_count}")
            
            # Check cases
            res = await conn.execute(select(func.count(Case.id)))
            case_count = res.scalar()
            print(f"DEBUG: Total Cases in DB: {case_count}")
            
            # Check cases per customer
            res = await conn.execute(select(Customer.name, func.count(Case.id)).join(Case).group_by(Customer.name))
            for row in res:
                print(f"DEBUG: Customer '{row[0]}' has {row[1]} cases")
                
            # Check batches per customer
            res = await conn.execute(select(Customer.name, func.count(Batch.id)).join(Batch).group_by(Customer.name))
            for row in res:
                print(f"DEBUG: Customer '{row[0]}' has {row[1]} batches")

    except Exception as e:
        print(f"ERROR: {str(e)}")
    finally:
        await async_engine.dispose()

if __name__ == "__main__":
    asyncio.run(run())
