
import asyncio
from sqlalchemy import text
from app.database import async_engine

async def check():
    async with async_engine.connect() as conn:
        print("Checking all databases...")
        res = await conn.execute(text("SHOW DATABASES"))
        for row in res.fetchall():
            print(row[0])

if __name__ == "__main__":
    asyncio.run(check())
