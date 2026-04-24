
import asyncio
from sqlalchemy import text
from app.database import async_engine

async def check():
    async with async_engine.connect() as conn:
        print("Attempting failing query...")
        sql = """
        SELECT notifications.id, notifications.user_id, notifications.title, notifications.message, 
               notifications.category, notifications.channel, notifications.is_read, notifications.case_id, 
               notifications.extra_data, notifications.created_at
        FROM notifications 
        LIMIT 1
        """
        try:
            res = await conn.execute(text(sql))
            row = res.fetchone()
            print(f"Success! Result: {row}")
        except Exception as e:
            print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(check())
