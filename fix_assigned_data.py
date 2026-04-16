from sqlalchemy import text
from app.database import engine

def fix_data():
    with engine.connect() as conn:
        print("Retroactive Data Fix: Populating 'assigned_at' for existing assignments...")
        try:
            # Set assigned_at = received_date for any case that has an assigned_to but assigned_at is null
            stmt = text("""
                UPDATE cases 
                SET assigned_at = received_date 
                WHERE assigned_to IS NOT NULL AND assigned_at IS NULL
            """)
            res = conn.execute(stmt)
            conn.commit()
            print(f"✓ Backfilled {res.rowcount} records.")
        except Exception as e:
            print(f"Error during data fix: {e}")

if __name__ == "__main__":
    fix_data()
