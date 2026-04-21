"""
Run this script once to create the revoke_logs table in the database.
Usage: python create_revoke_logs.py
"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.database import async_engine
from sqlalchemy import text

async def main():
    async with async_engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS revoke_logs (
                id VARCHAR(36) NOT NULL,
                case_id VARCHAR(36) NOT NULL,
                user_id VARCHAR(36) NOT NULL,
                revoke_type VARCHAR(50) NOT NULL,
                from_status VARCHAR(50) NOT NULL,
                to_status VARCHAR(50) NOT NULL,
                notes TEXT,
                revoked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                INDEX ix_revoke_logs_case_id (case_id),
                INDEX ix_revoke_logs_user_id (user_id),
                INDEX ix_revoke_logs_revoked_at (revoked_at),
                FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """))
    print("SUCCESS: revoke_logs table created!")
    await async_engine.dispose()

asyncio.run(main())
