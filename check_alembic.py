
import asyncio
from sqlalchemy import text
from app.database import async_engine

async def check():
    async with async_engine.connect() as conn:
        print("Checking alembic_version...")
        try:
            res = await conn.execute(text("SELECT * FROM alembic_version"))
            row = res.fetchone()
            print(f"ALEMBIC VERSION: {row}")
        except Exception as e:
            print(f"No alembic_version table found: {e}")

if __name__ == "__main__":
    asyncio.run(check())
