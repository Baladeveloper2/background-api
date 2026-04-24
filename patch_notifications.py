
import asyncio
import sys
import os
from sqlalchemy import text
from dotenv import load_dotenv

# Add current directory to path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from app.database import async_engine

async def patch():
    load_dotenv()
    print("Starting notification table patch...")
    
    async with async_engine.connect() as conn:
        # Check existing columns in notifications
        try:
            result = await conn.execute(text("DESCRIBE notifications"))
            columns = [row[0] for row in result.fetchall()]
            print(f"Current columns in notifications: {columns}")
            
            # Add extra_data if missing
            if 'extra_data' not in columns:
                print("Adding 'extra_data' column to notifications...")
                await conn.execute(text("ALTER TABLE notifications ADD COLUMN extra_data MEDIUMTEXT"))
                print("Successfully added 'extra_data'")
            else:
                print("'extra_data' already exists.")

            # Add case_id if missing
            if 'case_id' not in columns:
                print("Adding 'case_id' column to notifications...")
                await conn.execute(text("ALTER TABLE notifications ADD COLUMN case_id VARCHAR(36)"))
                # Add foreign key
                await conn.execute(text("ALTER TABLE notifications ADD CONSTRAINT fk_notifications_case_id FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE"))
                print("Successfully added 'case_id' and foreign key constraint")
            else:
                print("'case_id' already exists.")
            
            await conn.commit()
            print("Patch completed successfully.")
            
        except Exception as e:
            print(f"Error during patch: {e}")
            await conn.rollback()

if __name__ == "__main__":
    asyncio.run(patch())
