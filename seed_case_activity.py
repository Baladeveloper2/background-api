import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta

# Add current directory to path
sys.path.append(os.getcwd())

from sqlalchemy import select
from app.database import AsyncSessionLocal

from app.models import Case, VerificationLog, User

async def seed_activity(case_id):
    print(f"Seeding realistic activity logs for Case: {case_id}")
    async with AsyncSessionLocal() as db:

        # Check if case exists
        stmt = select(Case).filter(Case.id == case_id)
        res = await db.execute(stmt)
        case = res.scalar_one_or_none()
        
        if not case:
            print(f"Error: Case {case_id} not found.")
            return

        # Get a system or verifier user
        stmt = select(User).limit(1)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        user_id = user.id if user else "system"

        # Create sequential logs
        base_time = datetime.utcnow() - timedelta(hours=5)
        
        logs = [
            VerificationLog(
                id=str(uuid.uuid4()), case_id=case_id, action="CASE_INITIALIZED",
                performed_by_id=user_id, remarks="Case Reports initialized in Dynamic Workspace.",
                created_at=base_time
            ),
            VerificationLog(
                id=str(uuid.uuid4()), case_id=case_id, action="API_SYNC_TRIGGERED",
                performed_by_id=user_id, remarks="Automated identity sync triggered with external providers.",
                created_at=base_time + timedelta(minutes=15)
            ),
            VerificationLog(
                id=str(uuid.uuid4()), case_id=case_id, action="DOCUMENT_UPLOADED",
                performed_by_id=user_id, remarks="Candidate submitted Education credentials via portal.",
                created_at=base_time + timedelta(hours=1)
            ),
            VerificationLog(
                id=str(uuid.uuid4()), case_id=case_id, action="AUDIT_COMPLETED",
                performed_by_id=user_id, remarks="Quality check passed for Education module.",
                created_at=base_time + timedelta(hours=3),
                old_status="IN_PROGRESS", new_status="GREEN"
            )
        ]

        db.add_all(logs)
        await db.commit()
        print(f"Successfully seeded {len(logs)} activity events.")

if __name__ == "__main__":
    # Using the ID from the user's screenshot
    target_id = "8dad88ef-b695-4fb6-8ac4-062d0af4d9f5"
    asyncio.run(seed_activity(target_id))
