import asyncio
from app.database import async_engine
from app.models import Batch, Customer
from sqlalchemy import select

async def run():
    try:
        async with async_engine.connect() as conn:
            res = await conn.execute(select(Batch.customer_id, Batch.batch_no))
            for row in res:
                print(f"DEBUG: Batch {row[1]} has customer_id {row[0]}")
            
            res = await conn.execute(select(Customer.id, Customer.name))
            for row in res:
                print(f"DEBUG: Customer {row[1]} has ID {row[0]}")

    except Exception as e:
        print(f"ERROR: {str(e)}")
    finally:
        await async_engine.dispose()

if __name__ == "__main__":
    asyncio.run(run())
