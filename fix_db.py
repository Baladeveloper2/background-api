import asyncio
from app.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as db:
        await db.execute(text("UPDATE users SET role='SUPER_ADMIN' WHERE role='SUPER ADMIN'"))
        await db.execute(text("UPDATE users SET role='SYSTEM_ADMIN' WHERE role='System Admin'"))
        await db.execute(text("UPDATE users SET role='DATA_ENTRY' WHERE role='DATA ENTRY'"))
        await db.commit()
        print('DB rows updated.')

asyncio.run(main())
