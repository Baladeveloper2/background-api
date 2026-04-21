"""
fix_completed_case_statuses.py
==============================
One-time script to fix existing COMPLETED cases where verification checks
are stuck in INTERIM or VERIFICATION status instead of GREEN.

Rule:
  - Case status = COMPLETED
  - Check status = INTERIM or VERIFICATION or QC_PENDING
  → Update check status to GREEN (Clear/Verified)

Usage:
    python fix_completed_case_statuses.py
"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.database import async_engine
from sqlalchemy import text

STALE_STATUSES = ('INTERIM', 'VERIFICATION', 'QC_PENDING')

async def main():
    async with async_engine.begin() as conn:
        # Preview: count affected checks
        preview = await conn.execute(text("""
            SELECT COUNT(*) as cnt
            FROM verification_checks vc
            JOIN cases c ON c.id = vc.case_id
            WHERE c.status = 'COMPLETED'
              AND vc.status IN ('INTERIM', 'VERIFICATION', 'QC_PENDING')
        """))
        count = preview.scalar()
        print(f"Found {count} check(s) with stale status in COMPLETED cases.")

        if count == 0:
            print("Nothing to fix. All good!")
            await async_engine.dispose()
            return

        # Show details before fixing
        details = await conn.execute(text("""
            SELECT c.case_ref_no, vc.check_type, vc.status
            FROM verification_checks vc
            JOIN cases c ON c.id = vc.case_id
            WHERE c.status = 'COMPLETED'
              AND vc.status IN ('INTERIM', 'VERIFICATION', 'QC_PENDING')
            ORDER BY c.case_ref_no
        """))
        rows = details.fetchall()
        print("\nAffected checks:")
        for r in rows:
            print(f"  Case: {r.case_ref_no}  |  Check: {r.check_type}  |  Status: {r.status}")

        # Apply fix: set all stale checks to GREEN for COMPLETED cases
        result = await conn.execute(text("""
            UPDATE verification_checks vc
            JOIN cases c ON c.id = vc.case_id
            SET vc.status = 'GREEN'
            WHERE c.status = 'COMPLETED'
              AND vc.status IN ('INTERIM', 'VERIFICATION', 'QC_PENDING')
        """))
        print(f"\n✅ Fixed {result.rowcount} check(s) → status set to GREEN (Clear/Verified)")

    await async_engine.dispose()

asyncio.run(main())
