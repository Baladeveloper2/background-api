from app.database import SessionLocal
from app import models
from sqlalchemy import select, update
import asyncio

async def fix_stale_dates():
    db = SessionLocal()
    try:
        # Clear completed_date for any case that is NOT COMPLETED
        stmt = update(models.Case).where(
            models.Case.status != models.CaseStatus.COMPLETED
        ).values(completed_date=None)
        
        result = db.execute(stmt)
        db.commit()
        print(f"Cleanup successful. Updated {result.rowcount} stale cases.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(fix_stale_dates())
