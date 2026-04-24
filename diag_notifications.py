
import asyncio
from sqlalchemy import text
from app.database import async_engine

async def check():
    async with async_engine.connect() as conn:
        print("Checking column existence explicitly...")
        res = await conn.execute(text("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'notifications' AND COLUMN_NAME = 'extra_data'"))
        row = res.fetchone()
        if row:
            print(f"FOUND: {row[0]}")
        else:
            print("NOT FOUND")
            
        print("Executing DESCRIBE notifications...")
        res = await conn.execute(text("DESCRIBE notifications"))
        for row in res.fetchall():
            print(row)

if __name__ == "__main__":
    asyncio.run(check())
