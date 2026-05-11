import asyncio
import os
import sys

# Add current directory to path so we can import app
sys.path.append(os.getcwd())

from sqlalchemy import text
from app.database import async_engine

async def migrate():
    print("Starting Database Schema Migration for Dynamic Workflow...")
    async with async_engine.begin() as conn:
        # 1. Update verification_checks table
        print("Updating 'verification_checks' table structure...")
        
        # We use individual try-except blocks for each column to handle cases where 
        # some might already exist from previous partial runs.
        
        try:
            await conn.execute(text("ALTER TABLE verification_checks ADD COLUMN confidence_score FLOAT DEFAULT 0.0"))
            print("  + Added 'confidence_score' column.")
        except Exception as e:
            print(f"  ! Skip 'confidence_score': {str(e)}")
            
        try:
            await conn.execute(text("ALTER TABLE verification_checks ADD COLUMN api_sync_status VARCHAR(100) DEFAULT 'NOT_SYNCED'"))
            print("  + Added 'api_sync_status' column.")
        except Exception as e:
            print(f"  ! Skip 'api_sync_status': {str(e)}")

        try:
            await conn.execute(text("ALTER TABLE verification_checks ADD COLUMN assigned_verifier_id VARCHAR(36)"))
            print("  + Added 'assigned_verifier_id' column.")
        except Exception as e:
            print(f"  ! Skip 'assigned_verifier_id': {str(e)}")

        # 2. Create verification_documents table
        print("Creating 'verification_documents' table...")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS verification_documents (
                id VARCHAR(36) PRIMARY KEY,
                check_id VARCHAR(36) NOT NULL,
                file_name VARCHAR(255) NOT NULL,
                file_url VARCHAR(512) NOT NULL,
                file_type VARCHAR(100),
                s3_key VARCHAR(255),
                uploaded_by_id VARCHAR(36) NOT NULL,
                uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_vdoc_check_id (check_id),
                FOREIGN KEY (check_id) REFERENCES verification_checks(id) ON DELETE CASCADE,
                FOREIGN KEY (uploaded_by_id) REFERENCES users(id)
            ) ENGINE=InnoDB
        """))
        print("  + Table 'verification_documents' is ready.")

        # 3. Create verification_logs table
        print("Creating 'verification_logs' table...")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS verification_logs (
                id VARCHAR(36) PRIMARY KEY,
                case_id VARCHAR(36) NOT NULL,
                check_id VARCHAR(36),
                action VARCHAR(255) NOT NULL,
                performed_by_id VARCHAR(36) NOT NULL,
                remarks TEXT,
                old_status VARCHAR(50),
                new_status VARCHAR(50),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_vlog_case_id (case_id),
                INDEX idx_vlog_check_id (check_id),
                FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
                FOREIGN KEY (check_id) REFERENCES verification_checks(id) ON DELETE CASCADE,
                FOREIGN KEY (performed_by_id) REFERENCES users(id)
            ) ENGINE=InnoDB
        """))
        print("  + Table 'verification_logs' is ready.")
        
    print("\nMigration completed successfully. The system is now database-ready for dynamic workflows.")

if __name__ == "__main__":
    asyncio.run(migrate())
