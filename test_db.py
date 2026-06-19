import asyncio
from app.database import async_engine
from sqlalchemy import text

async def check():
    async with async_engine.connect() as conn:
        res = await conn.execute(text("SELECT COUNT(*) FROM batches"))
        batches_count = res.scalar()
        print(f"Total Batches in DB: {batches_count}")

        res2 = await conn.execute(text("SELECT COUNT(*) FROM customers"))
        customers_count = res2.scalar()
        print(f"Total Customers in DB: {customers_count}")

        res3 = await conn.execute(text("SELECT id, customer_id FROM batches LIMIT 5"))
        print("Batches samples:", res3.fetchall())

asyncio.run(check())
