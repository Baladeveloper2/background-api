import asyncio
import os
import sys
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import models, database

async def test_notifs():
    engine = database.engine
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as db:
        # Get a user first
        res = await db.execute(select(models.User).limit(1))
        user = res.scalar_one_or_none()
        if not user:
            print("No user found")
            return
        
        print(f"Testing for user: {user.email} (ID: {user.id})")
        
        stmt = (
            select(
                models.Notification,
                models.Case.case_ref_no,
                models.Case.status.label("case_status"),
                models.Candidate.name.label("case_name")
            )
            .outerjoin(models.Case, models.Notification.case_id == models.Case.id)
            .outerjoin(models.Candidate, models.Case.candidate_id == models.Candidate.id)
            .filter(models.Notification.user_id == user.id)
            .order_by(desc(models.Notification.created_at))
            .limit(5)
        )
        
        res = await db.execute(stmt)
        rows = res.all()
        print(f"Found {len(rows)} notifications")
        for row in rows:
            print(f"- {row.Notification.title} (Read: {row.Notification.is_read}) | Ref: {row.case_ref_no}")

if __name__ == "__main__":
    asyncio.run(test_notifs())
