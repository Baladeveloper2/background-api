from sqlalchemy import text
from app.database import engine

def migrate():
    with engine.connect() as conn:
        print("Adding created_at column to customers table...")
        try:
            conn.execute(text("ALTER TABLE customers ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
            conn.commit()
            print("Successfully added created_at column.")
        except Exception as e:
            print(f"Error adding column: {e}")

if __name__ == "__main__":
    migrate()
