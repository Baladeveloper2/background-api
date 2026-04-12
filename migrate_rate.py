from app.database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        print("Migrating verification_checks table...")
        try:
            # Check if column exists
            result = conn.execute(text("SHOW COLUMNS FROM verification_checks LIKE 'rate'"))
            if not result.fetchone():
                print("Adding 'rate' column to verification_checks...")
                conn.execute(text("ALTER TABLE verification_checks ADD COLUMN rate FLOAT DEFAULT 0.0"))
                conn.commit()
                print("Column added successfully.")
            else:
                print("Column 'rate' already exists.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    migrate()
