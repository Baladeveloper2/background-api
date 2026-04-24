
import asyncio
import os
import sys
from sqlalchemy import select
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, '.')
from app.database import async_engine
from app import models

async def test_query():
    async with async_engine.connect() as conn:
        print("Testing Case query with insufficiency_count...")
        stmt = select(models.Case).limit(1)
        res = await conn.execute(stmt)
        row = res.fetchone()
        print(f"Result: {row}")
        print("QUERY SUCCESSFUL")

if __name__ == "__main__":
    asyncio.run(test_query())
