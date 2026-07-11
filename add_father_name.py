import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))
from app.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text('ALTER TABLE candidates ADD COLUMN father_name VARCHAR(255);'))
            await session.commit()
            print("Column father_name added successfully")
        except Exception as e:
            print(f"Error adding column: {e}")
            await session.rollback()

if __name__ == '__main__':
    asyncio.run(main())
