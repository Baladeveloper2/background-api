import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))
from app.database import AsyncSessionLocal
from app.models import Customer
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        r = await session.execute(select(Customer.name, Customer.industry, Customer.head_office))
        print(r.all())

if __name__ == '__main__':
    asyncio.run(main())
