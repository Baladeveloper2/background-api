from app.database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        print("Migrating batches table...")
        try:
            result = conn.execute(text("SHOW COLUMNS FROM batches LIKE 'case_rate'"))
            if not result.fetchone():
                print("Adding 'case_rate' column to batches...")
                conn.execute(text("ALTER TABLE batches ADD COLUMN case_rate FLOAT DEFAULT 0.0"))
                conn.commit()
                print("Column added successfully.")
            else:
                print("Column 'case_rate' already exists.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    migrate()
