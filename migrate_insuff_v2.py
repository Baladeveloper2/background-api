
import asyncio
import sys
import os
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, '.')
from app.database import async_engine

async def main():
    print("Applying Insufficiency Lifecycle Migration...")
    async with async_engine.begin() as conn:
        # Add documents column
        print("Adding 'documents' column to 'insufficiencies'...")
        try:
            # Using LONGTEXT or MEDIUMTEXT for JSONEncodedList
            await conn.execute(text("ALTER TABLE insufficiencies ADD COLUMN documents MEDIUMTEXT;"))
            print("SUCCESS: 'documents' column added.")
        except Exception as e:
            print(f"INFO: 'documents' column check: {e}")

        # Update status column length if needed (String(50))
        print("Updating 'status' column length...")
        try:
            await conn.execute(text("ALTER TABLE insufficiencies MODIFY COLUMN status VARCHAR(50);"))
            print("SUCCESS: 'status' column updated.")
        except Exception as e:
            print(f"INFO: 'status' column update: {e}")

    print("Migration completed!")
    await async_engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
