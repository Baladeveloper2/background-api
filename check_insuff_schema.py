
import asyncio
import sys
import os
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, '.')
from app.database import async_engine

async def main():
    async with async_engine.connect() as conn:
        try:
            res = await conn.execute(text("DESCRIBE insufficiencies"))
            columns = [row[0] for row in res.all()]
            print(f"COLUMNS: {','.join(columns)}")
        except Exception as e:
            print(f"ERROR: {e}")
    await async_engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
