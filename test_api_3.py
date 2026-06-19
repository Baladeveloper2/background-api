import asyncio
from app.database import async_engine
from sqlalchemy import text

async def check():
    async with async_engine.connect() as conn:
        res = await conn.execute(text("UPDATE users SET role = 'SUPER_ADMIN' WHERE role = 'ADMIN'"))
        await conn.commit()
        print("Rows affected:", res.rowcount)

asyncio.run(check())


