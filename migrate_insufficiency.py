
import asyncio
import sys
import os
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

# Add current directory to path so we can import app modules
sys.path.insert(0, '.')

from app.database import async_engine

async def main():
    print("Starting Insufficiency Tracking Migration...")
    
    async with async_engine.begin() as conn:
        # 1. Add insufficiency_count column to cases table
        print("Adding 'insufficiency_count' column to 'cases' table...")
        try:
            await conn.execute(text("ALTER TABLE cases ADD COLUMN insufficiency_count INT DEFAULT 0;"))
            print("SUCCESS: 'insufficiency_count' column added.")
        except Exception as e:
            if "Duplicate column name" in str(e):
                print("INFO: 'insufficiency_count' column already exists.")
            else:
                print(f"ERROR adding column: {e}")

        # 2. Create insufficiency_logs table
        print("Creating 'insufficiency_logs' table...")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS insufficiency_logs (
                id VARCHAR(36) NOT NULL,
                case_id VARCHAR(36) NOT NULL,
                user_id VARCHAR(36) NOT NULL,
                from_status VARCHAR(50) NOT NULL,
                notes TEXT,
                marked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                resolved_at DATETIME,
                PRIMARY KEY (id),
                INDEX ix_insufficiency_logs_case_id (case_id),
                INDEX ix_insufficiency_logs_user_id (user_id),
                INDEX ix_insufficiency_logs_marked_at (marked_at),
                FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """))
        print("SUCCESS: 'insufficiency_logs' table created.")

    print("Migration completed successfully!")
    await async_engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
