import asyncio
import os
import sys

# Add current directory to path so we can import app
sys.path.append(os.path.join(os.getcwd(), "backend"))

from sqlalchemy import text
from app.database import async_engine

async def migrate():
    print("Starting removal of QC Flow Schema and adding Finalization columns...")
    async with async_engine.begin() as conn:
        # Drop columns on cases table
        columns_to_drop_cases = ["qa_id", "qc_id", "qc_remarks", "qc_revoke_count"]
        for col in columns_to_drop_cases:
            try:
                await conn.execute(text(f"ALTER TABLE cases DROP COLUMN {col}"))
                print(f"  - Successfully dropped cases.{col}")
            except Exception as e:
                print(f"  ! Skip dropping cases.{col}: {e}")

        # Add finalization columns to cases table
        columns_to_add_cases = [
            ("finalized_by", "VARCHAR(36)"),
            ("finalized_at", "DATETIME"),
            ("final_remarks", "TEXT")
        ]
        for col_name, col_def in columns_to_add_cases:
            try:
                await conn.execute(text(f"ALTER TABLE cases ADD COLUMN {col_name} {col_def}"))
                print(f"  + Successfully added cases.{col_name}")
            except Exception as e:
                print(f"  ! Skip adding cases.{col_name}: {e}")

        # Drop columns on verification_checks table
        columns_to_drop_checks = ["qc_verifier_id", "qc_status", "qc_remarks", "qc_reviewed_at"]
        for col in columns_to_drop_checks:
            try:
                await conn.execute(text(f"ALTER TABLE verification_checks DROP COLUMN {col}"))
                print(f"  - Successfully dropped verification_checks.{col}")
            except Exception as e:
                print(f"  ! Skip dropping verification_checks.{col}: {e}")

        # Add finalization columns to verification_checks table
        columns_to_add_checks = [
            ("finalized_by", "VARCHAR(36)"),
            ("finalized_at", "DATETIME"),
            ("final_remarks", "TEXT")
        ]
        for col_name, col_def in columns_to_add_checks:
            try:
                await conn.execute(text(f"ALTER TABLE verification_checks ADD COLUMN {col_name} {col_def}"))
                print(f"  + Successfully added verification_checks.{col_name}")
            except Exception as e:
                print(f"  ! Skip adding verification_checks.{col_name}: {e}")

    print("\nMigration completed successfully.")

if __name__ == "__main__":
    asyncio.run(migrate())
