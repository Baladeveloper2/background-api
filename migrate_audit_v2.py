from sqlalchemy import text
from app.database import engine

def migrate():
    with engine.connect() as conn:
        print("Starting final migration: Adding missing columns...")
        try:
            conn.execute(text("ALTER TABLE cases ADD COLUMN assigned_at DATETIME NULL"))
            print("✓ Added assigned_at")
        except Exception as e:
            print(f"assigned_at error: {e}")
            
        try:
            conn.execute(text("ALTER TABLE cases ADD COLUMN assigned_id INT NULL"))
            print("✓ Added assigned_id (if using specialized relations)")
        except Exception as e:
            print(f"assigned_id error: {e}")

        conn.commit()
        print("Done.")

if __name__ == "__main__":
    migrate()
