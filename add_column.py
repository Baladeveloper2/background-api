import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))
from app.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text('ALTER TABLE address_change_requests ADD COLUMN proof_urls JSON;'))
            await session.commit()
            print("Column proof_urls added successfully")
        except Exception as e:
            print(f"Error adding column: {e}")
            await session.rollback()

if __name__ == '__main__':
    asyncio.run(main())
