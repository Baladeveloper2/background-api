import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))
from app.database import AsyncSessionLocal
from app.models import AddressChangeRequest
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        try:
            r = await session.execute(select(AddressChangeRequest).limit(1))
            print(r.scalars().all())
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == '__main__':
    asyncio.run(main())
