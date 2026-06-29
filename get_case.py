import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))
from app.database import AsyncSessionLocal
from app.models import Case
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Case).limit(1))
        c = res.scalar_one_or_none()
        if c:
            print(f"Case ID: {c.id}")
        else:
            print("No cases")

if __name__ == '__main__':
    asyncio.run(main())
