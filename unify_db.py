
import asyncio
import os
import sys
from sqlalchemy import text
from dotenv import load_dotenv

# Path handling
sys.path.insert(0, os.path.dirname(__file__))

from app.database import async_engine

async def unify():
    load_dotenv()
    print(f"Targeting Database: {async_engine.url.render_as_string(hide_password=True)}")
    
    async with async_engine.connect() as conn:
        try:
            # notifications table
            res = await conn.execute(text("DESCRIBE notifications"))
            cols = [r[0] for r in res.fetchall()]
            
            if 'extra_data' not in cols:
                print("Patching notifications: adding extra_data")
                await conn.execute(text("ALTER TABLE notifications ADD COLUMN extra_data MEDIUMTEXT"))
            
            if 'case_id' not in cols:
                print("Patching notifications: adding case_id")
                await conn.execute(text("ALTER TABLE notifications ADD COLUMN case_id VARCHAR(36)"))
            
            # also update enums if they are missing
            # Aiven MySQL might be picky about Enum updates
            
            await conn.commit()
            print("Database unification complete.")
        except Exception as e:
            print(f"Error: {e}")
            await conn.rollback()

if __name__ == "__main__":
    asyncio.run(unify())
