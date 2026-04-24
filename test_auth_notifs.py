import asyncio
import os
import sys
from sqlalchemy import select

sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal, async_engine
from app import models

async def debug():
    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(models.User))).scalars().all()
        for u in users:
            if "ADMIN" in str(u.role).upper():
                print(f"ADMIN_FOUND: {u.full_name} | {u.role} | {u.status}")
    await async_engine.dispose()

if __name__ == "__main__":
    asyncio.run(debug())
