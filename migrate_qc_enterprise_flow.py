import asyncio
import os
import sys

# Add current directory to path so we can import app
sys.path.append(os.getcwd())

from sqlalchemy import text
from app.database import async_engine

async def migrate():
    print("Starting Enterprise QC Flow Schema Migration...")
    async with async_engine.begin() as conn:
        # 1. Update verification_checks table with new flow columns
        print("Checking 'verification_checks' table for extension...")
        
        columns_to_add = [
            ("qc_verifier_id", "VARCHAR(36)"),
            ("qc_status", "VARCHAR(50) DEFAULT 'PENDING_REVIEW'"),
            ("final_result", "VARCHAR(50)"),
            ("qc_remarks", "TEXT"),
            ("qc_reviewed_at", "DATETIME")
        ]
        
        for col_name, col_def in columns_to_add:
            try:
                await conn.execute(text(f"ALTER TABLE verification_checks ADD COLUMN {col_name} {col_def}"))
                print(f"  + Successfully added '{col_name}' column.")
            except Exception as e:
                # Swallow exceptions in case columns exist
                print(f"  ! Skip '{col_name}': Column likely already exists.")

    print("\nMigration of dynamic columns completed. Backend storage aligns with new Enterprise workflow.")

if __name__ == "__main__":
    asyncio.run(migrate())
