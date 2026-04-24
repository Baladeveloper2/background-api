
import asyncio
import os
from sqlalchemy import text
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

async def repair():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url: return
    
    engine = create_async_engine(db_url.replace("pymysql", "aiomysql"))
    
    async with engine.connect() as conn:
        print(f"Repairing table 'notifications' in {engine.url.database}...")
        try:
            # Check if extra_data exists by trying to select it
            try:
                await conn.execute(text("SELECT extra_data FROM notifications LIMIT 0"))
                print("'extra_data' is already visible and functional.")
            except:
                print("'extra_data' is NOT visible. Attempting to add...")
                await conn.execute(text("ALTER TABLE notifications ADD COLUMN extra_data MEDIUMTEXT"))
                print("Added 'extra_data'")
            
            # Check if case_id exists
            try:
                await conn.execute(text("SELECT case_id FROM notifications LIMIT 0"))
                print("'case_id' is already visible.")
            except:
                print("'case_id' is NOT visible. Attempting to add...")
                await conn.execute(text("ALTER TABLE notifications ADD COLUMN case_id VARCHAR(36)"))
                print("Added 'case_id'")
            
            await conn.commit()
            print("Repair successful.")
        except Exception as e:
            print(f"Fatal Error: {e}")
            await conn.rollback()

if __name__ == "__main__":
    asyncio.run(repair())
