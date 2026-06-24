import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal

columns_to_add = [
    "ocr_progress INT DEFAULT 0",
    "ocr_started_at DATETIME",
    "ocr_completed_at DATETIME",
    "ocr_duration_ms INT DEFAULT 0",
    "ocr_json JSON",
    "ocr_engine VARCHAR(50)",
    "ocr_error TEXT",
    "ocr_version VARCHAR(50) DEFAULT '2.0'",
    "last_retry_at DATETIME",
    "document_type VARCHAR(100) DEFAULT 'Unknown'",
    "confidence_score FLOAT DEFAULT 0.0",
    "extracted_data JSON",
    "confidence_scores JSON",
    "fraud_flags JSON",
    "review_status VARCHAR(50) DEFAULT 'PENDING'",
    "is_verified BOOLEAN DEFAULT FALSE",
    "candidate_id VARCHAR(36)",
    "batch_id VARCHAR(36)"
]

async def fix_db():
    async with AsyncSessionLocal() as session:
        for col in columns_to_add:
            try:
                await session.execute(text(f"ALTER TABLE ocr_extractions ADD COLUMN {col}"))
                await session.commit()
                print(f"Added {col.split()[0]}")
            except Exception as e:
                # Might already exist
                await session.rollback()
                pass
                
        # Also let's ensure related tables are created if missing
        # Actually sqlalchemy create_all is better for tables that don't exist at all.
        print("Finished adding missing columns.")

if __name__ == "__main__":
    asyncio.run(fix_db())
