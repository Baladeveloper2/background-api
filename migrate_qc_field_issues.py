import asyncio
import os
import sys

# Add current directory to path so we can import app
sys.path.append(os.getcwd())

from sqlalchemy import text
from app.database import async_engine

async def migrate():
    print("Starting Database Schema Migration for QC Field Issues...")
    async with async_engine.begin() as conn:
        print("Creating 'qc_field_issues' table...")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS qc_field_issues (
                id VARCHAR(36) PRIMARY KEY,
                case_id VARCHAR(36) NOT NULL,
                check_id VARCHAR(36),
                field_name VARCHAR(255) NOT NULL,
                issue_type ENUM('DATA_NOT_PROVIDED', 'DOCUMENT_UNCLEAR', 'FIELD_MISMATCH', 'VERIFICATION_INCOMPLETE', 'ADDITIONAL_PROOF_REQUIRED') NOT NULL,
                comment TEXT,
                raised_by VARCHAR(36) NOT NULL,
                assigned_to VARCHAR(36),
                status ENUM('OPEN', 'RESOLVED', 'CANCELLED') DEFAULT 'OPEN',
                resolved_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_qci_case_id (case_id),
                INDEX idx_qci_status (status),
                FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
                FOREIGN KEY (check_id) REFERENCES verification_checks(id) ON DELETE CASCADE,
                FOREIGN KEY (raised_by) REFERENCES users(id),
                FOREIGN KEY (assigned_to) REFERENCES users(id)
            ) ENGINE=InnoDB
        """))
        print("  + Table 'qc_field_issues' is ready.")
        
    print("\nMigration completed successfully. The system is now database-ready for field-level QC discrepancy tracking.")

if __name__ == "__main__":
    asyncio.run(migrate())
