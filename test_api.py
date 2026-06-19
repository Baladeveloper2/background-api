import asyncio
from app.database import async_engine
from sqlalchemy import text

async def check():
    async with async_engine.connect() as conn:
        res = await conn.execute(text("""
            SELECT COUNT(*) FROM batches b
            JOIN customers c ON b.customer_id = c.id
        """))
        print(f"Batches WITH matching Customer in DB: {res.scalar()}")
        
        res_orphans = await conn.execute(text("""
            SELECT COUNT(*) FROM batches b
            LEFT JOIN customers c ON b.customer_id = c.id
            WHERE c.id IS NULL
        """))
        print(f"Batches WITHOUT matching Customer: {res_orphans.scalar()}")

asyncio.run(check())
